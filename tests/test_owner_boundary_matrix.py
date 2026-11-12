"""Synthetic application isolation only; backend evidence is mandatory, not an RLS test."""
import os
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from app.main import create_app
from app.relationship_memory import FeatureStore
from conftest import onboard, register
from test_people import person, event, fact_body

@pytest.fixture
def owners(app, record_property):
    backend = app.state.service.db.backend
    assert backend == ('postgresql' if os.environ.get('LIFEWORLD_TEST_BACKEND') == 'postgresql' else 'sqlite')
    record_property('database_backend', backend)
    record_property('scope', 'synthetic_application_owner_boundary_not_RLS')
    with TestClient(app) as a, TestClient(app) as b:
        data=[]
        for n,c in enumerate((a,b)):
            _,g=onboard(c); me=register(c,'synthetic_matrix_'+str(n)); p=person(c,'Synthetic '+str(n))
            e=event(c,g,p,key='same-cross-owner-request')
            response=c.post('/api/people/'+p['id']+'/facts',json=fact_body(e['experience_id']))
            assert response.status_code==201,response.text
            data.append(dict(client=c,owner=me['owner_id'],goal=g,person=p,event=e,fact=response.json()))
        assert data[0]["owner"] != data[1]["owner"]
        yield app,data


def snapshot(row):
    c=row['client'];p=row['person']['id']
    paths={'state':'/api/state','people':'/api/people',
           'overview':'/api/people/'+p+'/overview',
           'sources':'/api/people/'+p+'/facts/'+row['fact']['id']+'/evidence'}
    result={}
    for key,path in paths.items():
        response=c.get(path);assert response.status_code==200,(path,response.text)
        result[key]=response.json()
    return result


@pytest.mark.parametrize('attacker',[0,1])
def test_cross_owner_read_list_mutate_nested_and_revoke(owners,attacker):
    app,rows=owners; own=rows[attacker]; target=rows[1-attacker];c=own['client']
    before=[snapshot(r) for r in rows];p=target['person'];f=target['fact'];e=target['event'];g=target['goal']
    for url in ['/api/goals/'+g['id'],'/api/people/'+p['id']+'/overview',
                '/api/people/'+p['id']+'/interactions',
                '/api/people/'+p['id']+'/facts/'+f['id']+'/evidence',
                '/api/people/'+own['person']['id']+'/facts/'+f['id']+'/evidence']:
        assert c.get(url).status_code==404,url
    assert [x['id'] for x in c.get('/api/people').json()['items']]==[own['person']['id']]
    assert c.get('/api/people',params={'q':p['name']}).json()['items']==[]
    assert [x['id'] for x in c.get('/api/state').json()['goals']]==[own['goal']['id']]
    attempts=[('patch','/api/people/'+p['id'],{'expected_revision':p['revision'],'followed':True}),
        ('patch','/api/interactions/'+e['interaction_event_id'],{'expected_revision':1,'kind':'call'}),
        ('post','/api/people/'+own['person']['id']+'/goals',{'request_id':'cross-link','goal_id':g['id']}),
        ('post','/api/people/'+own['person']['id']+'/facts',dict(fact_body(e['experience_id']),request_id='cross-source-new')),
        ('post','/api/people/'+own['person']['id']+'/connections',{'request_id':'cross-connect','other_person_id':p['id'],'label':'synthetic'}),
        ('post','/api/people/'+p['id']+'/facts/'+f['id']+'/sources/revoke',{'expected_revision':f['revision'],'experience_id':e['experience_id']}),
        ('post','/api/people/'+own['person']['id']+'/facts/'+f['id']+'/sources/revoke',{'expected_revision':f['revision'],'experience_id':e['experience_id']})]
    for method,url,body in attempts:
        response=getattr(c,method)(url,json=body);assert response.status_code==404,(url,response.text)
        assert [snapshot(r) for r in rows]==before
    # Identical request keys were accepted separately, never replaying another owner's receipt.
    assert rows[0]['event']['experience_id']!=rows[1]['event']['experience_id']

@pytest.mark.parametrize('deleting',[0,1])
def test_delete_personalization_only_affects_session_owner(owners,deleting):
    app,rows=owners;store=FeatureStore(app.state.service);app.state.feature_store=store
    for r in rows:
        store.configure(r['owner'],True,{'summary_style':'concise'});assert store.context(r['owner'])['features']
    target=rows[1-deleting];before=snapshot(target)
    with app.state.service.db.connect() as c:
        preserved=[dict(x) for x in c.execute('SELECT * FROM relationship_features WHERE owner_id=? ORDER BY subject_type,subject_id,feature_key',(target['owner'],)).fetchall()]
    assert preserved
    # The API has no target-owner field; an injected query must not switch session ownership.
    response=rows[deleting]['client'].delete('/api/personalization',params={'owner_id':target['owner']})
    assert response.status_code==200,response.text
    assert store.preferences(rows[deleting]['owner'])['enabled'] is False
    assert store.preferences(target['owner'])['enabled'] is True
    with app.state.service.db.connect() as c:
        assert c.execute('SELECT count(*) FROM relationship_features WHERE owner_id=?',(rows[deleting]['owner'],)).fetchone()[0]==0
        assert [dict(x) for x in c.execute('SELECT * FROM relationship_features WHERE owner_id=? ORDER BY subject_type,subject_id,feature_key',(target['owner'],)).fetchall()]==preserved
    assert snapshot(target)==before


def test_owner_boundaries_survive_fresh_database_instance(owners,record_property):
    app,rows=owners;old=app.state.service.db;states=[snapshot(r) for r in rows]
    cookies=[dict(r['client'].cookies) for r in rows];old.close()
    if old.backend=='postgresql':
        from app.postgres import PostgresDatabase
        fresh=PostgresDatabase(app.state.settings)
    else:
        from app.db import Database
        fresh=Database(old.directory)
    assert fresh is not old;assert fresh.backend==old.backend
    record_property('reopened_backend',fresh.backend)
    restarted=create_app(database=fresh,settings=app.state.settings,policy=app.state.service.policy,
                         clock=lambda:datetime(2026,10,27,7,tzinfo=timezone.utc))
    with TestClient(restarted) as a,TestClient(restarted) as b:
        for i,c in enumerate((a,b)):
            c.cookies.update(cookies[i]);r=dict(rows[i],client=c)
            assert snapshot(r)==states[i]
            assert c.get('/api/goals/'+rows[1-i]['goal']['id']).status_code==404
            assert c.get('/api/people/'+rows[1-i]['person']['id']+'/overview').status_code==404
