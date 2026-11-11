"""關係來源（Unified Schema 010）：我的紀錄與人物經歷都存在 person_connection_experience_sources。

兩種模式（RuntimeSettings.relation_source_store）：
- legacy_jsonb：Migration 010 之前。來源只在 person_connections.source_experience_ids（JSONB），只能引用我的紀錄。
  資料庫已經有關聯表（代表 Migration 已執行）卻仍在這個模式時，拒絕新增／修改關係，避免舊欄位與新表分岔。
- link_table：Migration 010 之後。正式讀寫來源只有關聯表；舊 JSONB 只是切換快照，不讀也不改。

API 一律維持 ID 陣列：source_experience_ids（我的紀錄）、source_person_experience_ids（人物經歷），
各自依 source_position 排序，沒有來源時回 []。替換來源一律在呼叫端的同一筆寫入交易內 Delete → Re-Insert
（Migration 後 lw_e2e_app 對關聯表只有 SELECT／INSERT／DELETE）。
"""
import json

from .errors import require

LEGACY = 'legacy_jsonb'
LINK = 'link_table'
STORES = (LEGACY, LINK)
MAX_SOURCES = 30  # 與 ConnectionCreate.source_experience_ids 上限一致
TABLE = 'person_connection_experience_sources'
KINDS = {'experience': ('experience_id', 'source_experience_ids'),
         'person_experience': ('subject_experience_id', 'source_person_experience_ids')}


def default_store(backend):
    """未明確設定時：SQLite 的結構一定含 010（只給單元測試），PostgreSQL 在 Migration 010 驗收前維持舊欄位。"""
    return LINK if backend == 'sqlite' else LEGACY


def link_table_exists(c, backend):
    """不假設關聯表存在：以目錄查詢判斷（不需要表權限，也不會因表不存在而讓交易失敗）。"""
    if backend == 'postgresql':
        return bool(c.execute("SELECT to_regclass('person_connection_experience_sources') IS NOT NULL").fetchone()[0])
    return c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='person_connection_experience_sources'").fetchone() is not None


def unique_ids(ids):
    """保留第一次出現的順序並去重；None 代表「沒有提供」，要和空陣列（清空）分開。"""
    return None if ids is None else list(dict.fromkeys(ids))


def read(c, owner, connection_ids):
    """回傳 {connection_id: {'source_experience_ids': [...], 'source_person_experience_ids': [...]}}。"""
    result = {cid: {'source_experience_ids': [], 'source_person_experience_ids': []} for cid in connection_ids}
    if not result:
        return result
    marks = ','.join('?' * len(result))
    rows = c.execute('SELECT connection_id,experience_id,subject_experience_id,source_position FROM ' + TABLE +
                     ' WHERE owner_id=? AND connection_id IN (' + marks + ')'
                     ' ORDER BY connection_id,source_position,experience_id,subject_experience_id', (owner, *result)).fetchall()
    for row in rows:
        if row['experience_id'] is not None:
            result[row['connection_id']]['source_experience_ids'].append(row['experience_id'])
        else:
            result[row['connection_id']]['source_person_experience_ids'].append(row['subject_experience_id'])
    return result


def replace(c, owner, connection_id, kind, ids):
    """在呼叫端的寫入交易內替換一種來源：先刪該類型，再依順序重新寫入（position 從 1 起算）。"""
    column = KINDS[kind][0]
    c.execute('DELETE FROM ' + TABLE + ' WHERE owner_id=? AND connection_id=? AND ' + column + ' IS NOT NULL', (owner, connection_id))
    for position, source_id in enumerate(ids, start=1):
        c.execute('INSERT INTO ' + TABLE + '(connection_id,owner_id,' + column + ',source_position) VALUES (?,?,?,?)',
                  (connection_id, owner, source_id, position))


def check_person_experience(c, owner, subject_experience_id, person_ids):
    """人物經歷來源：同帳號、未封存，且關係兩端至少一人是這段經歷的主體或參與者（被提及不算）。"""
    row = c.execute('SELECT id,status FROM subject_experiences WHERE id=? AND owner_id=?', (subject_experience_id, owner)).fetchone()
    require(row is not None, 404, 'not_found', '找不到可引用的人物經歷。')  # 他人的人物經歷同樣回 404，不透露是否存在
    require(row['status'] == 'active', 422, 'archived_source', '已封存的人物經歷不能作為關係來源。')
    marks = ','.join('?' * len(person_ids))
    linked = c.execute("SELECT 1 FROM subject_experience_people WHERE subject_experience_id=? AND owner_id=? AND role IN ('subject','participant')"
                       ' AND person_id IN (' + marks + ')', (subject_experience_id, owner, *person_ids)).fetchone()
    require(linked is not None, 422, 'unrelated_source', '來源人物經歷必須有這段關係的其中一人擔任主體或參與者。')


# ---- 關係類型與狀態（Unified Person P4）----
RELATION_KINDS = ('family', 'partner', 'friend', 'colleague', 'classmate', 'mentor', 'client', 'business', 'neighbor', 'rival', 'enemy', 'other')
ARCHIVED = 'archived'  # person_connections.confirmation_status：封存（不刪除）；其他值都視為使用中


def stored_relation_types(raw):
    """讀出儲存的關係類型陣列（PG 轉接層回傳 JSON 文字）；格式不符的項目略過，不修改資料。"""
    try:
        items = json.loads(raw) if isinstance(raw, str) else raw
    except ValueError:
        return []
    result = []
    for item in items if isinstance(items, list) else []:
        if isinstance(item, str):
            item = {'kind': item}
        if isinstance(item, dict) and isinstance(item.get('kind'), str):
            result.append(item)
    return result


def relation_types_view(raw):
    """本階段的 API 只呈現 kind；已儲存的方向與起迄資料留在資料庫，不輸出也不清除。"""
    return [{'kind': item['kind']} for item in stored_relation_types(raw)]


def merge_relation_types(raw, kinds):
    """依使用者選的 kind 重建陣列：原本就有的 kind 保留整個項目（含方向、起迄），新選的只存 kind；沒選的才移除。"""
    existing = {}
    for item in stored_relation_types(raw):
        existing.setdefault(item['kind'], item)
    return [existing.get(kind, {'kind': kind}) for kind in kinds]
