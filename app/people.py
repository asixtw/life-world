"""Person 360: shared views, explicit facts, provenance and real interactions."""  # 說明此模組的責任與實作邊界
from datetime import datetime  # 處理 UTC、發生時間與期限
from uuid import uuid4  # 產生不依賴名稱的唯一識別碼
import json  # 序列化資料與還原資料庫中的清單
import unicodedata  # 正規化搜尋與同值標籤的字寬

from .errors import require  # 共用領域錯誤與條件檢查
from .security import require_registered  # 共用密碼、工作階段與帳號權限檢查

DIMENSIONS = ('interests', 'food', 'skills', 'habits')  # 準備固定四維度識別碼：興趣、飲食、專長及互動習慣


def uid():  # 產生不依賴名稱的固定唯一識別碼
    return str(uuid4())  # 回傳產生不依賴名稱的固定唯一識別碼的結果


def js(value):  # 序列化 JSON 並保留中文字元
    return json.dumps(value, ensure_ascii=False)  # 回傳序列化 JSON 並保留中文字元的結果


class PeopleMixin:  # 人物完整頁、事實來源與互動事件的服務擴充
    def _people_user(self, c, owner):  # 要求完成初始旅程且已建立本機帳號
        user = self._onboarded(c, owner)  # 準備目前帳號及其身分資料
        require_registered(user)  # 驗證限制：條件不成立即拒絕操作，避免部分寫入
        return user  # 回傳要求完成初始旅程且已建立本機帳號的結果

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _revision(row, revision):  # 拒絕以舊版本覆蓋新版資料
        require(row['revision'] == revision, 409, 'revision_conflict', '資料已有新版，請重新載入後再修改。')  # 驗證限制：資料已有新版，請重新載入後再修改。

    @staticmethod  # 此共用檢查不需要讀取物件狀態
    def _resource(c, table, owner, item_id):  # 限定人物事實與事件資料表並檢查所屬帳號
        assert table in ('interaction_events', 'person_facts')  # 限制動態資料表或欄位名稱為程式內白名單
        row = c.execute('SELECT * FROM ' + table + ' WHERE id=? AND owner_id=?', (item_id, owner)).fetchone()  # 依白名單資料表、識別碼與所屬帳號查詢資源
        require(row is not None, 404, 'not_found', '找不到可存取的資料。')  # 驗證限制：找不到可存取的資料。
        return row  # 回傳限定人物事實與事件資料表並檢查所屬帳號的結果

    def _person_stats(self, c, owner, person_id):  # 以互動事件計數，只有實體見面計入見面次數
        row = c.execute('''SELECT COUNT(*) AS interactions,
            COALESCE(SUM(e.kind='in_person'),0) AS meetings, MAX(e.occurred_at) AS last_interaction_at
            FROM interaction_events e JOIN interaction_people p ON p.event_id=e.id
            WHERE e.owner_id=? AND p.person_id=?''', (owner, person_id)).fetchone()  # 查詢真實互動事件；值以參數傳入
        return dict(row)  # 回傳以互動事件計數，只有實體見面計入見面次數的結果

    def _person(self, c, owner, person_id):  # 組合多角色、標籤、統計與目標關聯
        p = dict(self._owned(c, 'people', person_id, owner))  # 準備目前人物的完整基本資料
        p['roles'], p['tags'], p['followed'] = json.loads(p['roles']), json.loads(p['tags']), bool(p['followed'])  # 保存「(p['roles'], p['tags'], p['followed'])」供後續驗證或回傳使用
        p['stats'] = self._person_stats(c, owner, person_id)  # 以互動事件計數，只有實體見面計入見面次數
        p['interaction_count'] = p['stats']['interactions']  # 保存「p['interaction_count']」供後續驗證或回傳使用
        p['last_interaction_at'] = p['stats']['last_interaction_at']  # 保存「p['last_interaction_at']」供後續驗證或回傳使用
        goals = self._person_goals(c, owner, person_id)  # 準備人物相關或帳號所屬的目標清單
        p['has_active_goal'] = any(g['status'] == 'active' for g in goals)  # 保存「p['has_active_goal']」供後續驗證或回傳使用
        p['goal_titles'] = [g['title'] for g in goals]  # 保存「p['goal_titles']」供後續驗證或回傳使用
        return p  # 回傳組合多角色、標籤、統計與目標關聯的結果

    def people_list(self, owner, q='', category='', followed_only=False, sort='priority', limit=50, offset=0):  # 共用人物查詢，依透明分層規則穩定排序
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._onboarded(c, owner)  # 要求先建立 Bio 與第一個目標蛋
            people = [self._person(c, owner, r['id']) for r in c.execute('SELECT id FROM people WHERE owner_id=?', (owner,)).fetchall()]  # 查詢人物基本資料；值以參數傳入
            query = unicodedata.normalize('NFKC', q).casefold().strip()  # 正規化搜尋文字，避免字寬或大小寫造成漏搜
            def matches(p):  # 比對姓名、角色、目標與已確認標籤及分類條件
                values = [r[0] for r in c.execute("SELECT value FROM person_facts WHERE person_id=? AND status IN ('confirmed','conflict')", (p['id'],))]  # 查詢已確認人物資訊；值以參數傳入
                text = ' '.join([p['name'], *p['roles'], *p['tags'], *p['goal_titles'], *values])  # 準備供搜尋比對的文字內容
                return (not query or query in unicodedata.normalize('NFKC', text).casefold()) and (not category or p['category'] == category) and (not followed_only or p['followed'])  # 回傳比對姓名、角色、目標與已確認標籤及分類條件的結果
            people = [p for p in people if matches(p)]  # 準備經權限或篩選條件限制的人物清單
            def recent(p):  # 將最近互動轉為降冪排序鍵；無日期者置後
                return -datetime.fromisoformat(p['last_interaction_at']).timestamp() if p['last_interaction_at'] else float('inf')  # 回傳將最近互動轉為降冪排序鍵；無日期者置後的結果
            if sort == 'name':  # 依目前條件選擇下一步處理分支
                people.sort(key=lambda p: (p['name'].casefold(), p['id']))  # 姓名忽略大小寫排序；同名以固定識別碼維持穩定順序
            elif sort == 'recent':  # 依目前條件選擇下一步處理分支
                people.sort(key=lambda p: (recent(p), p['name'].casefold(), p['id']))  # 最近互動優先；無日期者置後，同時間依姓名與識別碼排序
            else:  # 處理前述條件不成立的替代流程
                people.sort(key=lambda p: (not p['followed'], not p['has_active_goal'], recent(p), p['name'].casefold(), p['id']))  # 透明分層排序：關注優先 → 進行中目標 → 最近互動 → 姓名與固定識別碼
            return {'items': people[offset:offset + limit], 'total':len(people), 'offset':offset, 'limit':limit}  # 回傳共用人物查詢，依透明分層規則穩定排序的結果

    def edit_person(self, owner, person_id, data):  # 檢查版本後更新使用者明確送出的欄位
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner)  # 要求完成初始旅程且已建立本機帳號
            p = self._owned(c, 'people', person_id, owner)  # 準備目前人物的完整基本資料
            self._revision(p, data.expected_revision)  # 檢查樂觀鎖版本，避免覆蓋他人的較新修改
            fields = data.model_dump(exclude_unset=True, exclude={'expected_revision'})  # 準備本次明確提供的更新欄位
            for key, value in fields.items():  # 逐項處理清單中的資料，保留目前交易或查詢條件
                assert key in ('name', 'roles', 'tags', 'category', 'followed', 'notes', 'common_context')  # 限制動態資料表或欄位名稱為程式內白名單
                c.execute('UPDATE people SET ' + key + '=? WHERE id=? AND owner_id=?',
                          (js(value) if key in ('roles', 'tags') else int(value) if key == 'followed' else value, person_id, owner))  # 更新人物基本資料；值以參數傳入
            if 'roles' in fields:  # 依目前條件選擇下一步處理分支
                c.execute('UPDATE people SET role=? WHERE id=?', ('、'.join(fields['roles']), person_id))  # 更新人物基本資料；值以參數傳入
            c.execute('UPDATE people SET revision=revision+1 WHERE id=?', (person_id,))  # 更新人物基本資料；值以參數傳入
            return self._person(c, owner, person_id)  # 回傳檢查版本後更新使用者明確送出的欄位的結果

    def _person_goals(self, c, owner, person_id):  # 讀取明確目標關聯與舊經歷的上下文關聯
        # Older experience links remain contextual evidence, not promises by another person.
        rows = c.execute('''SELECT DISTINCT g.*,pg.label FROM goals g
            LEFT JOIN person_goals pg ON pg.goal_id=g.id AND pg.person_id=?
            WHERE g.owner_id=? AND (pg.person_id IS NOT NULL OR EXISTS
              (SELECT 1 FROM experiences x WHERE x.goal_id=g.id AND x.person_id=? AND x.owner_id=?))
            ORDER BY g.created_at,g.id''', (person_id, owner, person_id, owner)).fetchall()  # 查詢目標；值以參數傳入
        return [dict(r, link_kind='manual' if r['label'] is not None else 'experience') for r in rows]  # 回傳讀取明確目標關聯與舊經歷的上下文關聯的結果

    def link_person_goal(self, owner, person_id, data):  # 以可重送的提交建立人物與目標關聯
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner); self._owned(c, 'people', person_id, owner)  # 要求完成初始旅程且已建立本機帳號
            self._owned(c, 'goals', data.goal_id, owner)  # 限制查詢資料表並核對資源所屬帳號
            op = 'person:goal:' + person_id  # 準備分隔操作與人物的去重範圍
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 比較請求指紋，重送時回傳先前結果
            if cached: return cached  # 若為相同提交重送，沿用已保存結果
            c.execute('''INSERT INTO person_goals VALUES (?,?,?,?) ON CONFLICT(person_id,goal_id)
                         DO UPDATE SET label=excluded.label''', (person_id, data.goal_id, owner, data.label))  # 新增人物與目標關聯；值以參數傳入
            result = {'person_id':person_id, 'goal_id':data.goal_id, 'label':data.label}  # 準備本次操作的回傳資料
            self._remember(c, owner, op, data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳以可重送的提交建立人物與目標關聯的結果

    def _source_experience(self, c, owner, experience_id, person_ids=None):  # 要求來源是同帳號且與人物相關的已確認經歷
        row = c.execute('SELECT * FROM experiences WHERE id=? AND owner_id=?', (experience_id, owner)).fetchone()  # 執行目前交易中的參數化查詢
        require(row is not None, 404, 'not_found', '找不到可引用的已確認經歷。')  # 驗證限制：找不到可引用的已確認經歷。
        if person_ids is not None:  # 依人物選擇或人物資料狀態套用限制
            story = c.execute('SELECT reviewed FROM experience_stories WHERE experience_id=?', (experience_id,)).fetchone()  # 新故事以逐筆角色檢查來源
            linked = [r[0] for r in c.execute('SELECT person_id FROM experience_participants WHERE experience_id=?', (experience_id,))] if story and story['reviewed'] else [row['person_id']]  # 舊關聯不自動變成新事實
            require(any(pid in linked for pid in person_ids), 422, 'unrelated_source', '來源必須是與這位人物有關的已確認經歷。')  # 不能引用其他人的故事作本人陳述
        return row  # 回傳要求來源是同帳號且與人物相關的已確認經歷的結果

    def _events(self, c, owner, person_id):  # 以事件分組共同經歷，避免多筆原文重複算見面
        events = []  # 準備依發生時間排列的互動事件
        for row in c.execute('''SELECT e.* FROM interaction_events e JOIN interaction_people p ON p.event_id=e.id
                                WHERE e.owner_id=? AND p.person_id=? ORDER BY e.occurred_at DESC,e.id''', (owner, person_id)).fetchall():  # 查詢真實互動事件；值以參數傳入
            event = dict(row)  # 準備目前處理的互動事件
            event['experiences'] = [dict(x) for x in c.execute('''SELECT x.* FROM experiences x JOIN interaction_experiences l ON l.experience_id=x.id
                        WHERE l.event_id=? AND x.owner_id=? ORDER BY x.occurred_at,x.id''', (row['id'], owner))]  # 查詢已確認經歷；值以參數傳入
            events.append(event)  # 將目前資料加入結果清單
        return events  # 回傳以事件分組共同經歷，避免多筆原文重複算見面的結果

    def interactions(self, owner, person_id, kind=None):  # 列出人物互動事件，可依類型篩選
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._people_user(c, owner); self._owned(c, 'people', person_id, owner)  # 要求完成初始旅程且已建立本機帳號
            events = self._events(c, owner, person_id)  # 準備依發生時間排列的互動事件
            return {'items':[e for e in events if not kind or e['kind'] == kind]}  # 回傳列出人物互動事件，可依類型篩選的結果

    def _attach_interaction(self, c, owner, experience_id, person_id, data, occurred_at):  # 將經歷加入已選事件，或建立指定類型的新事件
        if not person_id:  # 依人物選擇或人物資料狀態套用限制
            require(not data.interaction_event_id and not any(p.selected for p in data.person_updates),
                    422, 'person_required', '更新人物與互動事件前請先選擇人物。')  # 驗證限制：更新人物與互動事件前請先選擇人物。
            return None  # 回傳將經歷加入已選事件，或建立指定類型的新事件的結果
        event_id = data.interaction_event_id  # 準備互動或積分事件的唯一識別碼
        if event_id:  # 依目前條件選擇下一步處理分支
            event = self._resource(c, 'interaction_events', owner, event_id)  # 準備目前處理的互動事件
            require(c.execute('SELECT 1 FROM interaction_people WHERE event_id=? AND person_id=?', (event_id, person_id)).fetchone(),
                    422, 'unrelated_interaction', '請選擇這位人物的互動事件。')  # 驗證限制：請選擇這位人物的互動事件。
            require(data.interaction_type == 'unknown' or data.interaction_type == event['kind'],
                    409, 'interaction_conflict', '互動類型不同，請先在時間線分類後再關聯。')  # 驗證限制：互動類型不同，請先在時間線分類後再關聯。
        else:  # 處理前述條件不成立的替代流程
            event_id = uid()  # 準備互動或積分事件的唯一識別碼
            c.execute('INSERT INTO interaction_events(id,owner_id,kind,occurred_at) VALUES (?,?,?,?)',
                      (event_id, owner, data.interaction_type, occurred_at))  # 新增真實互動事件；值以參數傳入
            c.execute('INSERT INTO interaction_people VALUES (?,?)', (event_id, person_id))  # 新增事件參與人物；值以參數傳入
        c.execute('INSERT INTO interaction_experiences VALUES (?,?)', (experience_id, event_id))  # 新增事件與經歷關聯；值以參數傳入
        return event_id  # 回傳將經歷加入已選事件，或建立指定類型的新事件的結果

    def edit_interaction(self, owner, event_id, data):  # 檢查版本後重新分類互動事件
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner)  # 要求完成初始旅程且已建立本機帳號
            event = self._resource(c, 'interaction_events', owner, event_id)  # 準備目前處理的互動事件
            self._revision(event, data.expected_revision)  # 檢查樂觀鎖版本，避免覆蓋他人的較新修改
            c.execute('UPDATE interaction_events SET kind=?,revision=revision+1 WHERE id=?', (data.kind, event_id))  # 更新真實互動事件；值以參數傳入
            return dict(self._resource(c, 'interaction_events', owner, event_id))  # 回傳檢查版本後重新分類互動事件的結果

    def merge_interactions(self, owner, event_id, data):  # 合併同一次互動，保留經歷與既有積分
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner)  # 要求完成初始旅程且已建立本機帳號
            target = self._resource(c, 'interaction_events', owner, event_id)  # 準備互動合併要保留的主要事件
            op = 'interaction:merge:' + event_id  # 準備分隔操作與人物的去重範圍
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 比較請求指紋，重送時回傳先前結果
            if cached: return cached  # 若為相同提交重送，沿用已保存結果
            self._revision(target, data.expected_revision)  # 檢查樂觀鎖版本，避免覆蓋他人的較新修改
            require(event_id not in data.source_event_ids and len(set(data.source_event_ids)) == len(data.source_event_ids),
                    422, 'invalid_merge', '請選擇不同的來源互動。')  # 驗證限制：請選擇不同的來源互動。
            for source_id in data.source_event_ids:  # 逐項處理清單中的資料，保留目前交易或查詢條件
                self._resource(c, 'interaction_events', owner, source_id)  # 限定人物事實與事件資料表並檢查所屬帳號
                c.execute('INSERT OR IGNORE INTO interaction_people SELECT ?,person_id FROM interaction_people WHERE event_id=?', (event_id, source_id))  # 新增事件參與人物；值以參數傳入
                c.execute('UPDATE interaction_experiences SET event_id=? WHERE event_id=?', (event_id, source_id))  # 更新事件與經歷關聯；值以參數傳入
                c.execute('DELETE FROM interaction_people WHERE event_id=?', (source_id,))  # 刪除事件參與人物；值以參數傳入
                c.execute('DELETE FROM interaction_events WHERE id=?', (source_id,))  # 刪除真實互動事件；值以參數傳入
            c.execute('UPDATE interaction_events SET revision=revision+1 WHERE id=?', (event_id,))  # 更新真實互動事件；值以參數傳入
            result = dict(self._resource(c, 'interaction_events', owner, event_id))  # 準備本次操作的回傳資料
            self._remember(c, owner, op, data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳合併同一次互動，保留經歷與既有積分的結果

    def _fact(self, c, owner, person_id, fact_id):  # 核對人物資訊的所屬帳號與人物
        fact = self._resource(c, 'person_facts', owner, fact_id)  # 準備目前處理的人物維度資訊
        require(fact['person_id'] == person_id, 404, 'not_found', '找不到此人物的資訊。')  # 驗證限制：找不到此人物的資訊。
        return fact  # 回傳核對人物資訊的所屬帳號與人物的結果

    def _fact_sources(self, c, fact_id, owner):  # 讀取仍有效、尚未撤回的經歷來源
        return [dict(r) for r in c.execute('''SELECT x.*,s.evidence_type,s.revoked_at FROM fact_sources s
            JOIN experiences x ON x.id=s.experience_id WHERE s.fact_id=? AND x.owner_id=? AND s.revoked_at IS NULL
            ORDER BY x.occurred_at,x.id''', (fact_id, owner))]  # 查詢人物資訊來源；值以參數傳入

    def _write_fact(self, c, owner, person_id, data, source_ids):  # 正規化同值資訊、增加來源並保留使用者指定的衝突
        self._owned(c, 'people', person_id, owner)  # 限制查詢資料表並核對資源所屬帳號
        for source_id in source_ids: self._source_experience(c, owner, source_id, [person_id])  # 逐項處理清單中的資料，保留目前交易或查詢條件
        normalized = unicodedata.normalize('NFKC', data.value).strip().casefold()  # 統一字寬與大小寫後辨識同值人物資訊
        old = c.execute('SELECT * FROM person_facts WHERE person_id=? AND dimension=? AND normalized_value=?',
                        (person_id, data.dimension, normalized)).fetchone()  # 執行目前交易中的參數化查詢
        other = None  # 準備指定衝突項或關係另一端的資料
        if data.conflicts_with:  # 依目前條件選擇下一步處理分支
            other = self._fact(c, owner, person_id, data.conflicts_with)  # 準備指定衝突項或關係另一端的資料
            require(other['dimension'] == data.dimension and other['normalized_value'] != normalized,
                    422, 'invalid_conflict', '衝突資訊需屬同一維度且內容不同。')  # 驗證限制：衝突資訊需屬同一維度且內容不同。
        fact_id = old['id'] if old else uid()  # 準備同值既有資訊或新資訊的識別碼
        require(old is None or old['status'] != 'archived', 409, 'archived_fact', '這項資訊已封存，請從人物資訊變更歷史明確重新採用。')  # 驗證限制：這項資訊已封存，請從人物資訊變更歷史明確重新採用。
        if not old:  # 依目前條件選擇下一步處理分支
            c.execute('''INSERT INTO person_facts(id,owner_id,person_id,dimension,value,normalized_value,description,status,created_at)
                         VALUES (?,?,?,?,?,?,?,'confirmed',?)''',
                      (fact_id, owner, person_id, data.dimension, data.value, normalized, data.description, self.now().isoformat()))  # 新增已確認人物資訊；值以參數傳入
        else:  # 處理前述條件不成立的替代流程
            c.execute("UPDATE person_facts SET revision=revision+1,status=CASE WHEN status='unavailable' THEN 'confirmed' ELSE status END WHERE id=?", (fact_id,))  # 更新已確認人物資訊；值以參數傳入
        for source_id in set(source_ids):  # 逐項處理清單中的資料，保留目前交易或查詢條件
            c.execute('''INSERT INTO fact_sources VALUES (?,?,?,NULL) ON CONFLICT(fact_id,experience_id)
                         DO UPDATE SET evidence_type=excluded.evidence_type,revoked_at=NULL''', (fact_id, source_id, data.evidence_type))  # 新增人物資訊來源；值以參數傳入
        if other:  # 依目前條件選擇下一步處理分支
            group = other['conflict_group'] or other['id']  # 準備同組衝突資訊的穩定識別碼
            c.execute("UPDATE person_facts SET conflict_group=?,status='conflict',revision=revision+1 WHERE id=? OR (person_id=? AND conflict_group=? AND status<>'archived')",
                      (group, other['id'], person_id, group))  # 更新已確認人物資訊；值以參數傳入
            c.execute("UPDATE person_facts SET conflict_group=?,status='conflict' WHERE id=?", (group, fact_id))  # 更新已確認人物資訊；值以參數傳入
        return dict(self._fact(c, owner, person_id, fact_id))  # 回傳正規化同值資訊、增加來源並保留使用者指定的衝突的結果

    def create_fact(self, owner, person_id, data):  # 明確確認來源後新增人物資訊，支援重送去重
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner); self._owned(c, 'people', person_id, owner)  # 要求完成初始旅程且已建立本機帳號
            op = 'person:fact:' + person_id  # 準備分隔操作與人物的去重範圍
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 比較請求指紋，重送時回傳先前結果
            if cached: return cached  # 若為相同提交重送，沿用已保存結果
            result = self._write_fact(c, owner, person_id, data, data.source_experience_ids)  # 準備本次操作的回傳資料
            self._remember(c, owner, op, data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳明確確認來源後新增人物資訊，支援重送去重的結果

    def _apply_person_updates(self, c, owner, person_id, experience_id, candidates):  # 只寫入使用者明確勾選的人物資訊
        for candidate in candidates:  # 逐項處理清單中的資料，保留目前交易或查詢條件
            if candidate.selected:  # 依目前條件選擇下一步處理分支
                require(person_id is not None, 422, 'person_required', '請先選擇人物。')  # 驗證限制：請先選擇人物。
                self._write_fact(c, owner, person_id, candidate, [experience_id])  # 正規化同值資訊、增加來源並保留使用者指定的衝突

    def fact_evidence(self, owner, person_id, fact_id):  # 回傳指定人物資訊與有效來源經歷
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._people_user(c, owner); self._owned(c, 'people', person_id, owner)  # 要求完成初始旅程且已建立本機帳號
            fact = self._fact(c, owner, person_id, fact_id)  # 準備目前處理的人物維度資訊
            return {'fact':dict(fact), 'sources':self._fact_sources(c, fact_id, owner)}  # 回傳回傳指定人物資訊與有效來源經歷的結果

    def resolve_fact(self, owner, person_id, fact_id, data):  # 人工採用一項資訊並封存同組衝突項
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner); fact = self._fact(c, owner, person_id, fact_id)  # 要求完成初始旅程且已建立本機帳號
            self._revision(fact, data.expected_revision)  # 檢查樂觀鎖版本，避免覆蓋他人的較新修改
            require(bool(self._fact_sources(c, fact_id, owner)), 409, 'source_required', '沒有有效來源，無法採用為正式資訊。')  # 驗證限制：沒有有效來源，無法採用為正式資訊。
            if fact['conflict_group']:  # 依目前條件選擇下一步處理分支
                c.execute("UPDATE person_facts SET status='archived',revision=revision+1 WHERE person_id=? AND conflict_group=? AND id<>?",
                          (person_id, fact['conflict_group'], fact_id))  # 更新已確認人物資訊；值以參數傳入
            c.execute("UPDATE person_facts SET status='confirmed',revision=revision+1 WHERE id=?", (fact_id,))  # 更新已確認人物資訊；值以參數傳入
            return dict(self._fact(c, owner, person_id, fact_id))  # 回傳人工採用一項資訊並封存同組衝突項的結果

    def revoke_fact_source(self, owner, person_id, fact_id, data):  # 撤回來源；最後來源失效時將資訊改為不可用
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner); fact = self._fact(c, owner, person_id, fact_id)  # 要求完成初始旅程且已建立本機帳號
            self._revision(fact, data.expected_revision)  # 檢查樂觀鎖版本，避免覆蓋他人的較新修改
            require(c.execute('SELECT 1 FROM fact_sources WHERE fact_id=? AND experience_id=? AND revoked_at IS NULL', (fact_id, data.experience_id)).fetchone(),
                    404, 'not_found', '找不到有效來源。')  # 驗證限制：找不到有效來源。
            c.execute('UPDATE fact_sources SET revoked_at=? WHERE fact_id=? AND experience_id=?', (self.now().isoformat(), fact_id, data.experience_id))  # 更新人物資訊來源；值以參數傳入
            has_sources = bool(self._fact_sources(c, fact_id, owner))  # 準備目前是否仍有未撤回的有效來源
            c.execute('UPDATE person_facts SET revision=revision+1,status=? WHERE id=?', (fact['status'] if has_sources else 'unavailable', fact_id))  # 更新已確認人物資訊；值以參數傳入
            return dict(self._fact(c, owner, person_id, fact_id))  # 回傳撤回來源；最後來源失效時將資訊改為不可用的結果

    def create_connection(self, owner, person_id, data):  # 核對兩端人物與來源後保存明確關係
        with self.db.connect(write=True) as c:  # 開啟可回滾的寫入交易，相關修改一起提交
            self._people_user(c, owner)  # 要求完成初始旅程且已建立本機帳號
            self._owned(c, 'people', person_id, owner); self._owned(c, 'people', data.other_person_id, owner)  # 限制查詢資料表並核對資源所屬帳號
            require(person_id != data.other_person_id, 422, 'invalid_connection', '請選擇另一位人物。')  # 驗證限制：請選擇另一位人物。
            for source_id in data.source_experience_ids: self._source_experience(c, owner, source_id, [person_id, data.other_person_id])  # 逐項處理清單中的資料，保留目前交易或查詢條件
            op = 'person:connection:' + person_id  # 準備分隔操作與人物的去重範圍
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 比較請求指紋，重送時回傳先前結果
            if cached: return cached  # 若為相同提交重送，沿用已保存結果
            a, b = sorted([person_id, data.other_person_id])  # 保存「(a, b)」供後續驗證或回傳使用
            c.execute('''INSERT INTO person_connections VALUES (?,?,?,?,?,?) ON CONFLICT(person_a,person_b)
                         DO UPDATE SET label=excluded.label,source_experience_ids=excluded.source_experience_ids''',
                      (uid(), owner, a, b, data.label, js(list(dict.fromkeys(data.source_experience_ids)))))  # 新增明確人物關係；值以參數傳入
            result = dict(c.execute('SELECT * FROM person_connections WHERE person_a=? AND person_b=?', (a,b)).fetchone())  # 執行目前交易中的參數化查詢
            self._remember(c, owner, op, data.request_id, fingerprint, result)  # 把成功回應與去重提交代碼一起記入交易
            return result  # 回傳核對兩端人物與來源後保存明確關係的結果

    def _notes(self, c, owner, person_id=None):  # 列出私人筆記及其引用來源
        rows = c.execute('SELECT * FROM notes WHERE owner_id=?' + (' AND person_id=?' if person_id else '') + ' ORDER BY created_at DESC,id',
                         (owner, person_id) if person_id else (owner,)).fetchall()  # 執行目前交易中的參數化查詢
        return [dict(r, source_experience_ids=[s[0] for s in c.execute('SELECT experience_id FROM note_sources WHERE note_id=?', (r['id'],))]) for r in rows]  # 查詢私人筆記引用來源；值以參數傳入

    def person_overview(self, owner, person_id):  # 組合人物三分頁需要的事實、來源與互動資料
        with self.db.connect() as c:  # 在同一讀取交易取得一致資料
            self._people_user(c, owner)  # 要求完成初始旅程且已建立本機帳號
            person = self._person(c, owner, person_id)  # 組合多角色、標籤、統計與目標關聯
            facts = {d:[] for d in DIMENSIONS}  # 準備依四個維度分組的已確認與衝突資訊
            for row in c.execute("SELECT * FROM person_facts WHERE person_id=? AND owner_id=? AND status IN ('confirmed','conflict') ORDER BY created_at,id", (person_id, owner)).fetchall():  # 執行目前交易中的參數化查詢
                facts[row['dimension']].append(dict(row, sources=self._fact_sources(c, row['id'], owner)))  # 將目前資料加入結果清單
            connections = []  # 準備人物間明確關係的顯示清單
            fact_history = [dict(r, sources=self._fact_sources(c, r['id'], owner)) for r in c.execute(
                "SELECT * FROM person_facts WHERE person_id=? AND owner_id=? AND status IN ('archived','unavailable') ORDER BY created_at,id",
                (person_id, owner)).fetchall()]  # 執行目前交易中的參數化查詢
            for row in c.execute('SELECT * FROM person_connections WHERE owner_id=? AND (person_a=? OR person_b=?)', (owner, person_id, person_id)).fetchall():  # 執行目前交易中的參數化查詢
                other = row['person_b'] if row['person_a'] == person_id else row['person_a']  # 準備指定衝突項或關係另一端的資料
                connections.append({'id':row['id'], 'label':row['label'], 'person':self._person(c, owner, other),
                                    'source_experience_ids':json.loads(row['source_experience_ids'])})  # 將目前資料加入結果清單
            tasks = [dict(r) for r in c.execute('''SELECT t.* FROM tasks t JOIN experiences x ON x.id=t.experience_id
                       WHERE t.owner_id=? AND x.person_id=? ORDER BY t.id''', (owner, person_id))]  # 查詢下一步待辦；值以參數傳入
            story_ids = c.execute('''SELECT s.experience_id FROM experience_stories s JOIN experience_participants p ON p.experience_id=s.experience_id
                JOIN experiences x ON x.id=s.experience_id WHERE s.owner_id=? AND s.reviewed=1 AND s.available=1 AND p.person_id=? ORDER BY x.occurred_at DESC,x.id DESC LIMIT 20''', (owner, person_id)).fetchall()  # 參與故事不要求有直接互動
            mention_ids = c.execute('''SELECT DISTINCT s.experience_id,x.occurred_at FROM experience_stories s JOIN experience_mentions m ON m.experience_id=s.experience_id
                JOIN experiences x ON x.id=s.experience_id WHERE s.owner_id=? AND s.reviewed=1 AND s.available=1 AND m.person_id=? AND m.status='matched' ORDER BY x.occurred_at DESC,s.experience_id DESC LIMIT 20''', (owner, person_id)).fetchall()  # 只將人工配對的提及列到人物卡
            return {'person':person, 'stats':person['stats'], 'facts':facts, 'interactions':self._events(c, owner, person_id),
                    'goals':self._person_goals(c, owner, person_id), 'tasks':tasks, 'connections':connections,
                    'notes':self._notes(c, owner, person_id), 'fact_history':fact_history,
                    'stories':[self._story_detail(c, owner, r[0]) for r in story_ids], 'mentions':[self._story_detail(c, owner, r[0]) for r in mention_ids]}  # 共同參與與提及分流，彼此不改統計
