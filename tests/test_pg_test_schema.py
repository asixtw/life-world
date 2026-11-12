"""Cloud Build Step 3 的 PostgreSQL 合成測試庫，必須和 Cloud Run 使用的 alpha 同一套結構。

規格：《表規格與擬真資料交接》v1.1（2026-11-12）——010 在 e2e／alpha 都是 42 張表，011 是生日／任職四張表；
relationship_features、relationship_memory_preferences 這一輪 PostgreSQL 不建。
這裡只檢查要執行的 DDL 與 GRANT 內容，不連任何資料庫（雲端或本機都不連）。
"""
import re

import pytest

from scripts import pg_test_bootstrap as bootstrap

NEW_011 = {'person_basic_details', 'person_basic_detail_history', 'person_employments', 'person_employment_history'}
HISTORY_011 = {'person_basic_detail_history', 'person_employment_history'}


def created(statements):
    return {name for statement in statements
            for name in re.findall(r'CREATE TABLE (?:lw_core_draft\.)?"?([a-z_]+)"?', statement)}


def test_ci_schema_is_the_alpha_010_snapshot_plus_011_only():
    snapshot = bootstrap.alpha_snapshot()
    alpha = {r['name'] for r in snapshot['structure']['relations'] if r['kind'] == 'r'}
    assert snapshot['database'] == 'life_world_alpha' and len(alpha) == 42
    statements = bootstrap.schema_statements()
    assert created(statements) == alpha | NEW_011
    assert not created(statements) & {'relationship_features', 'relationship_memory_preferences'}
    # 外鍵在所有主鍵／唯一鍵之後建立，參照的鍵一定已存在。
    keys = [i for i, s in enumerate(statements) if s.startswith('ALTER TABLE') and re.search(r' (PRIMARY KEY|UNIQUE)', s)]
    foreign = [i for i, s in enumerate(statements) if s.startswith('ALTER TABLE') and ' FOREIGN KEY' in s]
    assert keys and foreign and max(keys) < min(foreign)


def test_011_is_the_reviewed_file_with_only_its_environment_gate_removed():
    source = bootstrap.REVIEW_011.read_text(encoding='utf-8')
    ddl = bootstrap.reviewed_011_ddl(source)
    assert '$gate$' not in ddl and 'BEGIN;' not in ddl and 'COMMIT;' not in ddl
    statements = re.findall(r'CREATE (?:TABLE|INDEX)[^;]+;', source)
    assert len(statements) >= 4 and all(statement in ddl for statement in statements)  # 建表與索引逐字沿用審查稿
    # 審查稿的關卡結構一改就停止，不猜測要怎麼剝除。
    for broken in (source.replace('END $gate$;', 'END $other$;'), source + '\nDO $gate$ BEGIN END $gate$;\n'):
        with pytest.raises(ValueError):
            bootstrap.reviewed_011_ddl(broken)


def test_runtime_privileges_mirror_alpha_app_and_add_only_the_011_minimum():
    grants = bootstrap.runtime_grants()
    rows = [r for r in bootstrap.alpha_snapshot()['effective_runtime_privileges'] if r['role'] == 'lw_alpha_app']
    assert len(rows) == 42
    # alpha 待套用的權限（2026-11-12 Jerry 核准列入，與 011 一起等 Owner 核准後才在真實 alpha 執行）：只有刪除草稿。
    pending = set(bootstrap.PENDING_ALPHA_GRANTS)
    assert pending == {'GRANT DELETE ON "drafts" TO lw_app_role'} and pending <= set(grants)
    for row in rows:
        for privilege in ('select', 'insert', 'update', 'delete'):
            statement = 'GRANT ' + privilege.upper() + ' ON "' + row['table'] + '" TO lw_app_role'
            assert (statement in grants) == (row[privilege] or statement in pending), statement
    assert 'GRANT UPDATE ("revoked_at") ON "data_consents" TO lw_app_role' in grants  # alpha 既有的欄位權限
    assert not any('TRUNCATE' in g or ' ALL ' in g or 'lw_migrator' in g for g in grants)
    # 011：四表可讀可新增；目前值只開放指定欄位更新；History 不可更新或刪除（與 e2e 已執行的權限相同）。
    for table in NEW_011:
        assert 'GRANT SELECT, INSERT ON "' + table + '" TO lw_app_role' in grants
    assert not any(re.search(r'GRANT (UPDATE|DELETE)\b.* ON "(' + '|'.join(HISTORY_011) + ')"', g) for g in grants)
    basic = next(g for g in grants if g.startswith('GRANT UPDATE (') and g.endswith('ON "person_basic_details" TO lw_app_role'))
    assert '"owner_id"' not in basic and '"person_id"' not in basic and '"birth_day"' in basic
