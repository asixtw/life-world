"""Full FK catalog, including composite keys and inbound cross-schema edges."""
import json
from pathlib import Path


def catalog(c,backend):
    if backend=='sqlite':
        tables=[r['name'] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
        cols={t:[r['name'] for r in c.execute('PRAGMA table_info("'+t+'")').fetchall()] for t in tables}
        groups=[]
        for t in tables:
            by={}
            for r in c.execute('PRAGMA foreign_key_list("'+t+'")').fetchall():by.setdefault(r['id'],[]).append(r)
            for rows in by.values():
                rows=sorted(rows,key=lambda r:r['seq']);groups.append((t,tuple(r['from'] for r in rows),rows[0]['table'],tuple(r['to'] for r in rows)))
        return cols,groups
    rows=c.execute("SELECT t.relname AS table_name,a.attname AS column_name FROM pg_class t JOIN pg_namespace n ON n.oid=t.relnamespace JOIN pg_attribute a ON a.attrelid=t.oid WHERE n.nspname=current_schema() AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped").fetchall()
    cols={}
    for r in rows:cols.setdefault(r['table_name'],[]).append(r['column_name'])
    rows=c.execute("""SELECT f.oid::text AS key,ch.relname AS child,pa.relname AS parent,
      a.attname AS col,b.attname AS target,k.ord AS position,
      nc.nspname=current_schema() AND np.nspname=current_schema() AND f.convalidated AS safe
      FROM pg_constraint f JOIN pg_class ch ON ch.oid=f.conrelid JOIN pg_class pa ON pa.oid=f.confrelid
      JOIN pg_namespace nc ON nc.oid=ch.relnamespace JOIN pg_namespace np ON np.oid=pa.relnamespace
      CROSS JOIN LATERAL unnest(f.conkey,f.confkey) WITH ORDINALITY k(child_att,parent_att,ord)
      JOIN pg_attribute a ON a.attrelid=ch.oid AND a.attnum=k.child_att
      JOIN pg_attribute b ON b.attrelid=pa.oid AND b.attnum=k.parent_att
      WHERE f.contype='f' AND (nc.nspname=current_schema() OR np.nspname=current_schema())
      ORDER BY f.oid,k.ord""").fetchall()
    by={}
    for r in rows:
        if not r['safe']:raise ValueError('unreviewed_fk')
        by.setdefault(r['key'],[]).append(r)
    groups=[(rs[0]['child'],tuple(r['col'] for r in rs),rs[0]['parent'],tuple(r['target'] for r in rs)) for rs in by.values()]
    return cols,groups


# 已審核資料表形狀對應的外鍵契約（只在 PostgreSQL 比對；內容格式與 catalog() 相同）。
CONTRACTS={'alpha_034':'guest_fk_contract.json','unified_010':'guest_fk_contract_010.json'}


def verify_graph(groups,shape='alpha_034'):
    """實際外鍵必須與該形狀的契約完全相同；多一條、少一條或欄位不同都拒絕。"""
    actual=sorted([[a,list(b),c,list(d)] for a,b,c,d in groups])
    expected=json.loads(Path(__file__).with_name(CONTRACTS[shape]).read_text(encoding='utf-8'))
    if actual!=expected:raise ValueError('unreviewed_fk')
