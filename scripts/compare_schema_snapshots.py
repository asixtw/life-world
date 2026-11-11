"""離線比較兩份Studio唯讀目錄，不連資料庫、不讀業務內容或改寫任何快照。"""
import argparse
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def compare(alpha,e2e):
    differences={}
    for category in sorted(set(alpha['structure'])|set(e2e['structure'])):
        left=alpha['structure'].get(category,[]);right=e2e['structure'].get(category,[])
        # 原始SQL已穩定排序；差異輸出仍按整筆定義，不能以表數相同取代結構比對。
        a={json.dumps(x,sort_keys=True,ensure_ascii=False):x for x in left}
        b={json.dumps(x,sort_keys=True,ensure_ascii=False):x for x in right}
        differences[category]={'equal':left==right,'only_alpha':[a[x] for x in sorted(a.keys()-b.keys())],'only_e2e':[b[x] for x in sorted(b.keys()-a.keys())]}
    privileges={}
    for name,role,data in [('alpha','lw_alpha_app',alpha),('e2e','lw_e2e_app',e2e)]:
        privileges[name]={row['table']:{k:row[k] for k in ('select','insert','update','delete')} for row in data['effective_runtime_privileges'] if row['role']==role}
    return {'structure_equal':alpha['structure']==e2e['structure'],
            'fingerprints_sha256':{'alpha':digest(alpha['structure']),'e2e':digest(e2e['structure'])},
            'structure_diff':differences,
            'runtime_table_privileges_equal':privileges['alpha']==privileges['e2e'],
            'runtime_table_privileges':privileges,
            'metadata_diff':{k:{'equal':alpha.get(k)==e2e.get(k),'alpha':alpha.get(k),'e2e':e2e.get(k)} for k in ['database_metadata','schema_metadata','migration_receipts','relation_acl','column_acl','roles','memberships','default_acl']},
            'not_proven':['sequence properties/effective privileges not included in original query','DB network/CLI reachability','migration execution/restore','application read/write compatibility']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--alpha',type=Path,required=True);parser.add_argument('--e2e',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();a=json.loads(args.alpha.read_text());e=json.loads(args.e2e.read_text())
    if a['database']!='life_world_alpha' or e['database']!='life_world_e2e':raise ValueError('snapshot database mismatch')
    args.output.write_text(json.dumps(compare(a,e),ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
