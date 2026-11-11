"""唯讀核對擬真交接ZIP與010快照/本機011目錄；不匯入、不執行附件SQL或模型。"""
import argparse,csv,hashlib,io,json,re
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
SCOPES={'User','Person','Relationship','Context'}


def norm_type(value):
    return {'timestamptz':'timestamp with time zone','int':'integer','int4':'integer','bool':'boolean'}.get(value,value)


def norm_default(value):return re.sub(r'::(?:text|character varying)$','',(value or '').strip())
def norm_fk(value):return re.sub(r'\s+','',value.replace('lw_core_draft.','')).lower()


def columns_diff(rows,columns,candidate=False):
    """逐欄比序號/型別/NULL/default，不把內容模板當DB欄位。"""
    expected={}
    for row in rows:
        if row['nullable'] not in ('YES','NO'):raise ValueError('invalid schema nullability')
        key=(row['table'],row['column'])
        if key in expected:raise ValueError('duplicate schema column')
        expected[key]=(int(row['ordinal']),norm_type(row['pg_type_candidate' if candidate else 'postgresql_type']),row['nullable']=='YES',norm_default(row['default']))
    actual={(x['table'],x['name']):(x['position'],norm_type(x['type']),x['nullable'],norm_default(x['default'])) for x in columns}
    return [{'column':'.'.join(k),'package':expected.get(k),'reference':actual.get(k)} for k in sorted(expected.keys()|actual.keys()) if expected.get(k)!=actual.get(k)]


def hidden_checks(tables):
    """Gold僅人工預期；檢查引用與順序，不執行推論、不宣稱模型成果。"""
    cases=tables['scenario_inputs'];gold=tables['expected_hidden_features'];blocked=tables['expected_blocked_features'];errors=[]
    def unique(rows,key):
        values=[x[key] for x in rows]
        if any(not x for x in values) or len(values)!=len(set(values)):errors.append('duplicate_or_empty_'+key)
    for rows,key in [(cases,'case_id'),(gold,'feature_key'),(blocked,'blocked_key')]:unique(rows,key)
    by_case={x['case_id']:x for x in cases};events={}
    for row in cases:
        # 撤回操作不是第二份原文；模擬資料不能作真人事實來源。
        if row['review_state'] in ('confirmed','draft'):
            key=(row['owner_key'],row['source_event_key'])
            if key in events and events[key]['raw_keyin_text']!=row['raw_keyin_text']:errors.append('conflicting_event_text:'+row['source_event_key'])
            events[key]=row
    for row in gold:
        case=by_case.get(row['case_id'])
        if row['feature_scope'] not in SCOPES:errors.append('invalid_scope:'+row['feature_key'])
        source=events.get((case['owner_key'],row['source_event_key'])) if case else None
        if not source:errors.append('missing_or_cross_owner_source:'+row['feature_key']);continue
        if not row['source_quote'] or row['source_quote'] not in source['raw_keyin_text']:errors.append('quote_not_in_source:'+row['feature_key'])
        if source['review_state']!='confirmed' or source['background_consent_state']!='consent_active':errors.append('ineligible_gold_source:'+row['feature_key'])
    for row in blocked:
        if row['case_id'] not in by_case or row['feature_scope'] not in SCOPES:errors.append('invalid_blocked_reference:'+row['blocked_key'])
    step_keys=[]
    for row in tables['interaction_steps']:
        key=(row['case_id'],int(row['step_no']));step_keys.append(key)
        if row['case_id'] not in by_case:errors.append('unknown_step_case')
        may=row['source_state']=='confirmed' and row['consent_state']=='active' and row['user_or_system_action'] in ('confirm','background_extract')
        if (row['may_background_extract']=='yes')!=may:errors.append('invalid_extract_gate:'+str(key))
    if len(step_keys)!=len(set(step_keys)):errors.append('duplicate_step')
    return {'counts':{'scenarios':len(cases),'gold':len(gold),'blocked':len(blocked),'steps':len(step_keys)},'gold_scopes':sorted({x['feature_scope'] for x in gold}),'errors':errors,'actual_model_execution':'NOT RUN' if not tables['actual_model_outputs_EMPTY'] else 'UNVERIFIED: CSV alone is not provider evidence','actual_output_rows':len(tables['actual_model_outputs_EMPTY'])}


def content_checks(tables):
    """中立內容模板的ID/引用/日期檢查；不生成正式ID/授權/獎勵或修補輸入。"""
    from datetime import date
    keys={'people':'person_key','birthdays':None,'employments':'employment_key','events':'event_key','goals':'goal_key','actions':'action_key','notes':'note_key','person_facts':'fact_key','relationships':'connection_key','tasks':'task_key'}
    errors=[];ids={};event_rows={}
    for table,key in keys.items():
        rows=tables.get(table,[]);values=[r.get(key,'') for r in rows] if key else []
        if key and (any(not x or x!=x.strip() for x in values) or len(values)!=len(set(values))):errors.append('invalid_or_duplicate_key:'+table)
        ids[table]=set(values)
    def ref(value,table,label,optional=False):
        if not value and optional:return
        if value not in ids[table]:errors.append('missing_reference:'+label)
    for r in tables.get('events',[]):
        event_rows[r['event_key']]=r;parsed={}
        for column in ['participants_keys','interacted_keys','mentioned_keys']:
            try:
                cell=r.get(column,'');values=cell.split(';') if cell else []
                if not isinstance(cell,str) or any(not v or v!=v.strip() or v.startswith('[') for v in values) or len(values)!=len(set(values)):raise ValueError()
                for key in values:ref(key,'people',r['event_key']+':'+column)
                parsed[column]=values
            except (ValueError,TypeError,AttributeError):errors.append('ambiguous_key_array:'+r['event_key']+':'+column)
        if 'participants_keys' in parsed and 'interacted_keys' in parsed and not set(parsed['interacted_keys'])<=set(parsed['participants_keys']):errors.append('interaction_not_participation:'+r['event_key'])
        ref(r.get('goal_key',''),'goals',r['event_key']+':goal',True)
    evidence={'stated_by_person','observed_by_user','documented_source'}
    for table in ['birthdays','employments','person_facts']:
        for r in tables.get(table,[]):
            ref(r.get('person_key'),'people',table+':person')
            if table!='person_facts' and r.get('source_kind') not in ('manual','raw'):errors.append('source_kind_required:'+table)
            if r.get('source_event_key'):ref(r['source_event_key'],'events',table+':source_event')
            if r.get('evidence_type') and r['evidence_type'] not in evidence:errors.append('invalid_evidence:'+table)
            if r.get('source_kind')=='raw' or table=='person_facts':
                source=event_rows.get(r.get('source_event_key'))
                if not source or not r.get('source_quote') or r['source_quote'] not in source['raw_text']:errors.append('invalid_content_source:'+table)
                if r.get('evidence_type') not in evidence:errors.append('evidence_required:'+table)
            if table=='birthdays':
                try:
                    year,month,day=[int(r[k]) if r.get(k) else None for k in ['birth_year','birth_month','birth_day']]
                    if month is None and day is None and year is None:continue
                    if month is None or day is None:raise ValueError()
                    date(year if year is not None else 2000,month,day)
                except (ValueError,TypeError):errors.append('invalid_birthday')
            if table=='employments':
                if not r.get('company_name','').strip() and not r.get('job_title','').strip():errors.append('empty_employment')
                if r.get('employment_status') not in ('current','past','unknown'):errors.append('invalid_employment_status')
                try:
                    start=date.fromisoformat(r['valid_from']) if r.get('valid_from') else None;end=date.fromisoformat(r['valid_to']) if r.get('valid_to') else None
                    if start and end and end<start:raise ValueError()
                except ValueError:errors.append('invalid_employment_dates')
            if table=='person_facts' and r.get('dimension') not in ('interests','food','skills','habits'):errors.append('invalid_fact_dimension')
    for r in tables.get('actions',[]):ref(r.get('goal_key'),'goals','action:goal')
    for table in ['tasks','notes','relationships']:
        for r in tables.get(table,[]):
            ref(r.get('source_event_key'),'events',table+':event',table=='notes')
            for key in (['person_key'] if table=='notes' else ['person_a_key','person_b_key'] if table=='relationships' else []):ref(r.get(key),'people',table+':'+key)
            if table=='relationships' and r.get('person_a_key')==r.get('person_b_key'):errors.append('self_relationship')
    return {'row_counts':{k:len(tables.get(k,[])) for k in keys},'status':'TEMPLATES_ONLY_NOT_IMPORT_READY' if not any(tables.values()) else 'READ_ONLY_LINT_NOT_IMPORT_APPROVAL','key_array_encoding':'CSV semicolon lists per workbook 07; not JSON text in CSV cells','errors':errors}


def workbook_rows(raw):
    """用標準OOXML讀取靜態欄位，不修改或重算來源工作簿。"""
    with ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())>128 or sum(x.file_size for x in z.infolist())>20_000_000:raise ValueError('unexpected workbook capacity')
        shared=[]
        if 'xl/sharedStrings.xml' in z.namelist():shared=[''.join(s.itertext()) for s in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',NS)]
        sheets={};formulas=0
        for name in z.namelist():
            if not re.fullmatch(r'xl/worksheets/sheet\d+\.xml',name):continue
            root=ET.fromstring(z.read(name));formulas+=len(root.findall('.//m:f',NS));rows=[]
            for row in root.findall('m:sheetData/m:row',NS):
                values=[]
                for cell in row.findall('m:c',NS):
                    column=re.match('[A-Z]+',cell.attrib['r']).group();position=0
                    for char in column:position=position*26+ord(char)-64
                    while len(values)<position:values.append('')
                    value=cell.find('m:v',NS);kind=cell.attrib.get('t')
                    values[position-1]=''.join(cell.find('m:is',NS).itertext()) if kind=='inlineStr' else shared[int(value.text)] if kind=='s' else value.text if value is not None else ''
                rows.append(values)
            sheets[Path(name).name]=rows
        return sheets,formulas


def local_catalog():
    """只讀已驗marker本機PG，使用Runtime角色讀catalog，不GRANT/DDL/清資料。"""
    from contextlib import closing
    from scripts.pg_integration_fixture import connect,DB
    with closing(connect(DB,runtime=True)) as raw,closing(raw.cursor()) as c:
        c.execute('BEGIN READ ONLY')
        c.execute("SELECT r.relname,a.attname,a.attnum,format_type(a.atttypid,a.atttypmod),NOT a.attnotnull,pg_get_expr(d.adbin,d.adrelid) FROM pg_class r JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_attribute a ON a.attrelid=r.oid LEFT JOIN pg_attrdef d ON d.adrelid=r.oid AND d.adnum=a.attnum WHERE n.nspname='lw_core_draft' AND r.relkind='r' AND a.attnum>0 AND NOT a.attisdropped ORDER BY r.relname,a.attnum")
        columns=[dict(zip(['table','name','position','type','nullable','default'],row)) for row in c.fetchall()]
        c.execute("SELECT r.relname,pg_get_constraintdef(k.oid) FROM pg_constraint k JOIN pg_class r ON r.oid=k.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='lw_core_draft' AND k.contype='f'")
        fks=list(c.fetchall());c.execute('ROLLBACK')
    return columns,fks


def audit(path,local=False):
    """path為原ZIP，回傳差異/引用metadata；不解壓、不改附件，local只讀marker目錄。"""
    if Path(path).stat().st_size>10_000_000:raise ValueError('unexpected bundle size')
    raw=Path(path).read_bytes();result={'package_sha256':hashlib.sha256(raw).hexdigest(),'environment':'read-only source inspection; no import/model/GCP writes'}
    with ZipFile(io.BytesIO(raw)) as z:
        if len(z.infolist())>64 or sum(x.file_size for x in z.infolist())>10_000_000:raise ValueError('unexpected bundle capacity')
        if any('..' in Path(x.filename).parts or x.filename.startswith('/') for x in z.infolist()):raise ValueError('unsafe bundle path')
        def csv_rows(name):return list(csv.DictReader(io.StringIO(z.read(name).decode('utf-8-sig'))))
        prefix='LifeWorld_Schema_Handoff/';base=csv_rows(prefix+'schema010_columns.csv');candidate=csv_rows(prefix+'schema011_candidate_columns.csv')
        result['schema010']={}
        for database in ['life_world_e2e','life_world_alpha']:
            snapshot=json.loads((ROOT/'docs/integration/2026-11-11/evidence/schema'/f'{database}.json').read_text());structure=snapshot['structure'];tables={r['name'] for r in structure['relations'] if r['kind']=='r'}
            cols=[x for x in structure['columns'] if x['table'] in tables]
            expected_fk={tuple(line.split('|',2)[:2])+ (norm_fk(line.split('|',2)[2]),) for line in z.read(prefix+'schema010_fk_compact.txt').decode().splitlines() if line}
            actual_fk={(x['table'],x['name'],norm_fk(x['definition'])) for x in structure['constraints'] if x['kind']=='f'}
            result['schema010'][database]={'snapshot_date':'2026-11-11 Owner supplied, not live GCP','tables':len(tables),'columns':len(cols),'column_differences':columns_diff(base,cols),'fk_count':len(actual_fk),'fk_differences':sorted(expected_fk^actual_fk)}
        names={r['table'] for r in candidate};result['schema011']={'package_tables':sorted(names),'package_columns':len(candidate),'cloud_snapshot_deployed':False,'local_catalog':'NOT RUN'}
        if local:
            cols,fks=local_catalog();expected={(line.split('|',1)[0],norm_fk(line.split('|',1)[1])) for line in z.read(prefix+'schema011_candidate_fk_compact.txt').decode().splitlines() if line};actual={(table,norm_fk(definition)) for table,definition in fks if table in names}
            result['schema011'].update(local_catalog='localhost marker PG18 only',column_differences=columns_diff(candidate,[x for x in cols if x['table'] in names],True),fk_count=len(actual),fk_differences=sorted(expected^actual))
        sheets,formulas=workbook_rows(z.read('Life_World_Schema_010_011_交接規格.xlsx'))
        wb010=[tuple(row[:6]) for row in sheets['sheet3.xml'][1:]];csv010=[tuple(row[k] for k in ['table','ordinal','column','postgresql_type','nullable','default']) for row in base]
        wb011=[tuple(row[:6]) for row in sheets['sheet4.xml'][1:]];csv011=[tuple(row[k] for k in ['table','ordinal','column','pg_type_candidate','nullable','default']) for row in candidate]
        result['workbook']={'sheets':len(sheets),'formulas':formulas,'schema010_csv_equal':wb010==csv010,'schema011_csv_equal':wb011==csv011,'fk010_rows':len(sheets['sheet5.xml'])-1,'fk011_rows':len(sheets['sheet6.xml'])-1,
            'fk010_compact_equal':{(r[0],r[1],norm_fk(r[2])) for r in sheets['sheet5.xml'][1:]}=={(parts[0],parts[1],norm_fk(parts[2])) for line in z.read(prefix+'schema010_fk_compact.txt').decode().splitlines() if line for parts in [line.split('|',2)]},
            'fk011_compact_equal':{(r[0],norm_fk(r[2])) for r in sheets['sheet6.xml'][1:]}=={(parts[0],norm_fk(parts[1])) for line in z.read(prefix+'schema011_candidate_fk_compact.txt').decode().splitlines() if line for parts in [line.split('|',1)]}}
        content={Path(n).stem.removesuffix('_content'):csv_rows(n) for n in z.namelist() if '/templates/' in n and n.endswith('.csv')}
        result['content']=content_checks(content)
        hidden={Path(n).stem:csv_rows(n) for n in z.namelist() if n.startswith('Hidden_AI_Tagging_Addendum_v1.1/') and n.endswith('.csv')};result['hidden']=hidden_checks(hidden)
        result['content']['unresolved_person_keys']=sorted({r['person_key'] for r in hidden['scenario_inputs']}-{r['person_key'] for r in content['people']})
        result['content']['missing_base_event_keys']=sorted({r['source_event_key'] for r in hidden['scenario_inputs'] if r['review_state'] in ('confirmed','draft')}-{r['event_key'] for r in content['events']})
        manifest=json.loads(z.read('Hidden_AI_Tagging_Addendum_v1.1/MANIFEST.json'));result['based_on_commit']=manifest['head_sha']
        if not re.fullmatch(r'[0-9a-f]{40}',result['based_on_commit']):raise ValueError('invalid source commit')
        import subprocess
        review_path='docs/integration/2026-11-11/migrations/011_person_basic_details.review.sql'
        old=subprocess.run(['git','show',result['based_on_commit']+':'+review_path],cwd=ROOT,capture_output=True)
        current=(ROOT/review_path).read_bytes();result['schema011']['review_sql_sha256']=hashlib.sha256(current).hexdigest()
        result['schema011']['review_sql_matches_package_base']=current==old.stdout if old.returncode==0 else 'NOT VERIFIED: source Git object unavailable'
        result['manifest_counts_match']=all(result['hidden']['counts'][k]==manifest[m] for k,m in [('scenarios','scenario_count'),('gold','expected_feature_count'),('blocked','blocked_feature_count')])
        result['unresolved_before_import']=['base content templates are empty; person/event keys require a complete owner-scoped world','CSV semicolon lists are documented; timezone, contribution quantities and explicit review intents still require mapping contract','S07 no-reward expectation conflicts with unconditional personal Confirm reward; do not change product rule silently','S08 simulation is a negative contamination fixture, not an approved theatre feature','actual model template lacks cost/reservation/source-version provenance; no actual AI run is proved']
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle');parser.add_argument('--local-pg',action='store_true');parser.add_argument('--output',required=True);args=parser.parse_args()
    result=audit(args.bundle,args.local_pg);Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'review_only':True,'import_approved':False,'schema010_differences':sum(len(v['column_differences'])+len(v['fk_differences']) for v in result['schema010'].values()),'schema011_differences':len(result['schema011'].get('column_differences',[]))+len(result['schema011'].get('fk_differences',[])) if args.local_pg else 'NOT RUN','hidden_errors':result['hidden']['errors'],'actual_ai':result['hidden']['actual_model_execution']},ensure_ascii=False))
