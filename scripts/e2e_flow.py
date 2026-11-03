"""只使用既有 FastAPI 路由的合成驗收；報告不收錄 body／標頭／Cookie。"""
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import logging
import ssl
from uuid import uuid4

import httpx
from scripts.e2e_safety import require, validate_plan, check_token, SafetyError


def run_acceptance(plan, token, *, transport=None, ca_file=None, allow_local=False, retired=False):
    report = {'run_id':uuid4().hex,'mode':plan.get('mode') if plan.get('mode') in ('cloud','local-simulation') else 'invalid','started_at':datetime.now(timezone.utc).isoformat(),
              'passed':False,'checks':[],'database_cleanup':'requires_operator_sql'}
    checks = report['checks']
    current_step = 'preflight'
    def expect(name, condition):
        nonlocal current_step
        current_step = name
        checks.append({'name':name,'expected':True,'actual':bool(condition),'status':'PASS' if condition else 'FAIL',
                       'reason':None if condition else 'contract_mismatch'})
        if not condition: raise SafetyError('contract_mismatch')
    try:
        config = validate_plan(plan,allow_local=allow_local,retired=retired)
        check_token(token,config['audience']); expect('preflight',True)
        evidence = plan['snapshot_evidence']
        report['snapshot_provenance'] = {'batch_id':evidence['batch_id'],'captured_at':plan['captured_at'],
            'sources':{key:{field:record[field] for field in ('filename','export_started_at','exported_at','sha256','content_sha256')}
                       for key,record in evidence['sources'].items()}}
    except Exception as error:
        reason = str(error) if isinstance(error,SafetyError) else 'unsafe_or_malformed_configuration'
        checks.append({'name':'preflight','expected':'safe_target_and_token','actual':'rejected','status':'FAIL','reason':reason})
        return report
    for name in ('httpx','httpcore'): logging.getLogger(name).setLevel(logging.CRITICAL)
    verify = ssl.create_default_context(cafile=ca_file) if ca_file else True
    with ExitStack() as stack:
        def client(url, authenticated=True):
            return stack.enter_context(httpx.Client(base_url=url,transport=transport,verify=verify,timeout=20,
                follow_redirects=False,trust_env=False,headers={'X-Serverless-Authorization':'Bearer '+token} if authenticated else {}))
        main = client(config['audience'])
        def request(name, c, method, path, statuses=(200,), **kwargs):
            nonlocal current_step
            current_step = name
            # 主 Revision 永遠只做 GET，連建立訪客也不得對它嘗試。
            require(c is not main or method=='GET','main_write_forbidden')
            response = c.request(method,path,**kwargs); ok = response.status_code in statuses
            checks.append({'name':name,'expected':list(statuses),'actual':response.status_code,'status':'PASS' if ok else 'FAIL',
                           'reason':None if ok else 'unexpected_http_status'})
            if not ok: raise SafetyError('unexpected_http_status')
            return response
        def main_closed(suffix):
            request('main_health_'+suffix,main,'GET','/health'); request('main_ready_'+suffix,main,'GET','/ready')
            response = request('main_business_closed_'+suffix,main,'GET','/api/state',(503,))
            expect('main_gate_reason_'+suffix,response.json().get('error',{}).get('code')=='business_api_disabled')
        try:
            main_closed('before')
            if not retired:
                target = config['target']; anonymous = client(target,False)
                request('iam_anonymous_denied',anonymous,'GET','/health',(401,403))
                request('iam_invalid_token_denied',anonymous,'GET','/health',(401,403),headers={'X-Serverless-Authorization':'Bearer invalid-e2e-synthetic'})
                a,b = client(target),client(target)
                request('tag_health',a,'GET','/health'); request('tag_ready',a,'GET','/ready'); request('tag_api_health',a,'GET','/api/health')
                today = datetime.now(timezone.utc).date()
                def onboard(c, suffix):
                    guest = request('guest_'+suffix,c,'POST','/api/auth/guest',(201,),json={})
                    value = guest.json(); cookie = guest.headers.get('set-cookie','').lower()
                    expect('cookie_flags_'+suffix,all(flag in cookie for flag in ('secure','httponly','samesite=strict')))
                    me = request('session_'+suffix,c,'GET','/api/auth/me').json(); expect('session_owner_'+suffix,me['owner_id']==value['owner_id'])
                    profile = {'name':'E2E-'+report['run_id']+'-'+suffix,'bio':'synthetic only','timezone':'UTC'}
                    request('csrf_missing_'+suffix,c,'PUT','/api/profile',(403,),json=profile,headers={'Origin':target})
                    c.headers.update({'X-CSRF-Token':value['csrf_token'],'Origin':target})
                    request('origin_denied_'+suffix,c,'PUT','/api/profile',(403,),json=profile,headers={'Origin':'https://invalid.example.test'})
                    request('profile_'+suffix,c,'PUT','/api/profile',json=profile)
                    payload = {'request_id':report['run_id']+'-goal-'+suffix,'title':'E2E synthetic goal','outcome':'Synthetic verification',
                        'deadline':(today+timedelta(days=3)).isoformat(),'actions':[
                            {'title':'E2E habit '+str(i),'unit':'units','target':'10','per_occurrence':'0.5',
                             'dates':[today.isoformat(),(today+timedelta(days=1)).isoformat()],'weekdays':[],'level':i} for i in (1,2,3)]}
                    goal = request('goal_three_habits_'+suffix,c,'POST','/api/goals',(201,),json=payload).json()
                    expect('three_habits_'+suffix,len(goal['actions'])==3); return goal
                goal,other_goal = onboard(a,'A'),onboard(b,'B')
                request('owner_goal_isolation',b,'GET','/api/goals/'+goal['id'],(404,))
                def draft(when, label):
                    return request('draft_'+label,a,'POST','/api/experiences/drafts',(201,),json={
                        'raw_text':'LIFEWORLD_E2E_SYNTHETIC '+label,'goal_id':goal['id'],'occurred_at':when,
                        'contributions':[{'action_id':goal['actions'][0]['id'],'quantity':'0.123456'}]}).json()
                def confirmation(d, label):
                    return {'request_id':report['run_id']+'-'+label,'expected_revision':d['revision'],
                            'summary':'E2E synthetic confirmation','contributions':d['contributions'],'tasks':['E2E synthetic task']}
                d = draft(datetime.now(timezone.utc).isoformat(),'valid'); body = confirmation(d,'confirm')
                request('owner_write_isolation',b,'POST','/api/drafts/'+d['id']+'/confirm',(404,),json=body)
                confirmed = request('confirm',a,'POST','/api/drafts/'+d['id']+'/confirm',(201,),json=body).json()
                repeated = request('idempotent_retry',a,'POST','/api/drafts/'+d['id']+'/confirm',(201,),json=body).json()
                expect('same_receipt',confirmed==repeated and confirmed['points_awarded']==config['points'])
                request('owner_draft_isolation',b,'GET','/api/drafts/'+d['id'],(404,))
                fresh = client(target); fresh.cookies.update(a.cookies)
                state = request('fresh_session_persistent_read',fresh,'GET','/api/state').json()
                expect('one_reward_decimal',len(state['experiences'])==1 and len(state['rewards']['events'])==1 and
                       state['rewards']['total']==config['points'] and state['goals'][0]['actions'][0]['progress']=='0.123456' and len(state['tasks'])==1)
                other = request('other_owner_state',b,'GET','/api/state').json()
                expect('owner_has_no_foreign_data',len(other['goals'])==1 and other['goals'][0]['id']==other_goal['id'] and not other['experiences'] and other['rewards']['total']==0)
                # 自然領域錯誤位於 experiences INSERT 之後；不加入故障端點或繞過 CSRF。
                previous = datetime.combine(datetime.fromisoformat(goal['start_date']).date()-timedelta(days=1),datetime.min.time(),timezone.utc)
                bad = draft(previous.isoformat(),'rollback')
                failure = request('rollback_mid_transaction',a,'POST','/api/drafts/'+bad['id']+'/confirm',(422,),json=confirmation(bad,'rollback'))
                expect('rollback_expected_reason',failure.json().get('error',{}).get('code')=='contribution_out_of_range')
                saved = request('rollback_draft_preserved',a,'GET','/api/drafts/'+bad['id']).json()
                after = request('rollback_no_partial_state',fresh,'GET','/api/state').json()
                expect('rollback_state_unchanged',saved['status']=='draft' and after['experiences']==state['experiences'] and
                       after['rewards']==state['rewards'] and after['tasks']==state['tasks'] and after['goals']==state['goals'])
        except Exception as error:
            reason = (str(error) if isinstance(error,SafetyError) else
                      'transport_failure' if isinstance(error,httpx.RequestError) else 'response_or_contract_failure')
            checks.append({'name':'execution','step':current_step,'expected':'all_contracts','actual':'stopped','status':'FAIL','reason':reason})
        finally:
            try: main_closed('after')
            except Exception:
                checks.append({'name':'main_final_check','expected':'closed','actual':'failed','status':'FAIL','reason':'main_state_unverified'})
    report['passed'] = bool(checks) and all(x['status']=='PASS' for x in checks)
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    report['database_audit'] = 'requires_isolated_database_sql_assertions'
    return report
