"""資料契約稽核的正負例；不做匯入、不執行AI或Gold自動採納。"""
from copy import deepcopy
from scripts.audit_synthetic_handoff import hidden_checks,columns_diff


def sample():
    return {'scenario_inputs':[{'case_id':'case-a','owner_key':'owner-a','source_event_key':'event-a','review_state':'confirmed','background_consent_state':'consent_active','raw_keyin_text':'人物說喜歡閱讀。'}],
      'expected_hidden_features':[{'case_id':'case-a','feature_key':'gold-a','feature_scope':'Person','source_event_key':'event-a','source_quote':'喜歡閱讀'}],
      'expected_blocked_features':[{'case_id':'case-a','blocked_key':'blocked-a','feature_scope':'Person'}],
      'interaction_steps':[{'case_id':'case-a','step_no':'1','source_state':'confirmed','consent_state':'active','user_or_system_action':'confirm','may_background_extract':'yes'}],
      'actual_model_outputs_EMPTY':[]}


def test_valid_gold_and_empty_actual_are_not_a_model_run():
    result=hidden_checks(sample());assert result['errors']==[] and result['actual_model_execution']=='NOT RUN'
    data=sample();data['actual_model_outputs_EMPTY']=[{'run_id':'hand-entered'}]
    assert hidden_checks(data)['actual_model_execution'].startswith('UNVERIFIED')


def test_unknown_scope_quote_and_reference_are_flagged():
    data=sample();data['expected_hidden_features'][0].update(feature_scope='Personality',source_quote='不存在的引文')
    errors=hidden_checks(data)['errors'];assert 'invalid_scope:gold-a' in errors and 'quote_not_in_source:gold-a' in errors
    data['expected_hidden_features'][0]['source_event_key']='other-event';assert 'missing_or_cross_owner_source:gold-a' in hidden_checks(data)['errors']


def test_draft_revoked_and_unconsented_sources_cannot_be_positive_gold():
    for state,consent in [('draft','consent_active'),('confirmed','no_consent'),('confirmed','consent_revoked')]:
        data=sample();data['scenario_inputs'][0].update(review_state=state,background_consent_state=consent)
        assert 'ineligible_gold_source:gold-a' in hidden_checks(data)['errors']


def test_source_retraction_operation_does_not_overwrite_original_text():
    data=sample();operation=deepcopy(data['scenario_inputs'][0]);operation.update(case_id='withdrawal',review_state='source_withdrawn',raw_keyin_text='撤回此來源')
    data['scenario_inputs'].append(operation);assert hidden_checks(data)['errors']==[]
    operation['review_state']='confirmed';assert 'conflicting_event_text:event-a' in hidden_checks(data)['errors']


def test_different_owner_cannot_supply_gold_source_and_duplicate_ids_fail():
    data=sample();other=deepcopy(data['scenario_inputs'][0]);other.update(case_id='other',owner_key='owner-b',source_event_key='unrelated')
    data['scenario_inputs'].append(other);data['expected_hidden_features'][0]['case_id']='other'
    assert 'missing_or_cross_owner_source:gold-a' in hidden_checks(data)['errors']
    data['scenario_inputs'].append(other);assert 'duplicate_or_empty_case_id' in hidden_checks(data)['errors']


def test_schema_type_nullability_default_and_order_are_checked():
    package=[{'table':'table_a','column':'created_at','ordinal':'1','postgresql_type':'timestamptz','nullable':'NO','default':''}]
    reference=[{'table':'table_a','name':'created_at','position':1,'type':'timestamp with time zone','nullable':False,'default':None}]
    assert columns_diff(package,reference)==[]
    for key,value in [('position',2),('type','date'),('nullable',True),('default','now()')]:
        changed=deepcopy(reference);changed[0][key]=value;assert len(columns_diff(package,changed))==1


def test_content_stable_keys_references_and_interactions_are_distinct():
    from scripts.audit_synthetic_handoff import content_checks
    data={'people':[{'person_key':'a'},{'person_key':'b'}],'events':[{'event_key':'e','raw_text':'提到乙','participants_keys':'a','interacted_keys':'b','mentioned_keys':'b'}]}
    assert 'interaction_not_participation:e' in content_checks(data)['errors']
    data['events'][0]['interacted_keys']='';assert content_checks(data)['errors']==[]
    data['people'].append({'person_key':'a'});assert 'invalid_or_duplicate_key:people' in content_checks(data)['errors']


def test_content_birthdays_require_real_dates_and_no_guessed_year():
    from scripts.audit_synthetic_handoff import content_checks
    data={'people':[{'person_key':'p'}],'birthdays':[{'person_key':'p','birth_year':'','birth_month':'2','birth_day':'29','source_kind':'manual'}]}
    assert content_checks(data)['errors']==[]
    for year,month,day in [('2023','2','29'),('','2','31'),('1998','','')]:
        data['birthdays'][0].update(birth_year=year,birth_month=month,birth_day=day);assert 'invalid_birthday' in content_checks(data)['errors']


def test_content_manual_and_raw_sources_are_not_conflated():
    from scripts.audit_synthetic_handoff import content_checks
    data={'people':[{'person_key':'p'}],'employments':[{'employment_key':'j','person_key':'p','company_name':'合成組織','job_title':'','employment_status':'current','source_kind':'manual'}]}
    assert content_checks(data)['errors']==[]
    data['employments'][0]['source_kind']='raw';errors=content_checks(data)['errors'];assert 'invalid_content_source:employments' in errors and 'evidence_required:employments' in errors


def test_model_envelope_is_candidate_only_and_does_not_assign_owner_or_profile_version():
    import json
    from pathlib import Path
    contract=json.loads((Path(__file__).parents[1]/'docs/integration/2026-11-12_DATA_CONTRACT_AUDIT/HIDDEN_AI_OUTPUT_CONTRACT.json').read_text())
    fields=contract['properties']['candidates']['items']['properties']
    assert fields['adoption_state']=={'const':'candidate'} and 'owner_id' not in fields and 'profile_version' not in fields
    usage=contract['properties']['usage']['properties'];assert 'null' in usage['provider_cost_microusd']['type'] and usage['actual_invoice_cost_microusd']=={'const':None}
    assert set(fields['subject_type']['enum'])=={'user','person','relationship','context'}
