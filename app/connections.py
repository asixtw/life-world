"""逐經歷的故事探索、人物參與與提及來源。"""  # 不從名字或合併事件推定人際關係
import json  # 保存草稿與人工更正歷史
from uuid import uuid4  # 為線索與歷史產生固定識別碼
from .errors import require  # 沿用一致的領域錯誤
from .security import require_registered  # 正式人物整理仍受帳號門檻保護


class ConnectionsMixin:  # 將故事來源與互動統計邊界集中管理
    def _validate_story(self, c, owner, raw, story):  # 核對人物所有權與精確來源位置
        if story.participants or story.mentions: require_registered(self._onboarded(c, owner))  # 純提及也不能繞過升級
        for p in story.participants: self._owned(c, 'people', p.person_id, owner)  # 每位參與者都須屬於本人
        for m in story.mentions:  # 每處原文人名獨立核對
            require(0 <= m.start < m.end <= len(raw) and raw[m.start:m.end] == m.name, 422, 'invalid_source_span', '提及位置與原始文字不符，請重新選取。')  # Unicode 位移與原句完全一致
            if m.person_id: self._owned(c, 'people', m.person_id, owner)  # 正式配對必須是可存取人物

    def _store_draft_story(self, c, owner, draft_id, raw, story):  # 在原草稿交易內保存尚未確認資料
        if story is None:  # 明確不整理人物時移除草稿延伸，不影響原文
            c.execute('DELETE FROM draft_stories WHERE draft_id=?', (draft_id,))  # 草稿沒有正式人物關聯
            return  # 保持舊 API 相容
        self._validate_story(c, owner, raw, story)  # 保存前驗證來源與人物
        c.execute('INSERT INTO draft_stories VALUES (?,?) ON CONFLICT(draft_id) DO UPDATE SET payload=excluded.payload', (draft_id, json.dumps(story.model_dump(), ensure_ascii=False)))  # 原子保存未核對候選

    def _story_row(self, c, owner, experience_id, manage=False):  # 所有來源讀取均檢查帳號及展示狀態
        row = c.execute('''SELECT x.*,s.title,s.reviewed,s.available,s.revision FROM experiences x
            JOIN experience_stories s ON s.experience_id=x.id WHERE x.id=? AND x.owner_id=? AND s.owner_id=?''', (experience_id, owner, owner)).fetchone()  # 只查同帳號正式經歷
        require(row is not None and (manage or (row['reviewed'] and row['available'])), 404, 'not_found', '這段故事尚未核對、已撤回，或無法存取。')  # 舊連結不能繞過來源失效
        return dict(row)  # 回傳權限內的原文與狀態

    def _story_detail(self, c, owner, experience_id, manage=False):  # 組合完整故事與逐筆人物證據
        result = self._story_row(c, owner, experience_id, manage)  # 先限制來源存取
        result['title'] = result['title'] or result['summary'][:80]  # 無標題時使用既有摘要，不造情境
        result['reviewed'], result['available'] = bool(result['reviewed']), bool(result['available'])  # 回傳明確狀態
        result['participants'] = [dict(r) for r in c.execute('''SELECT p.id,p.name,p.category,l.interacted FROM experience_participants l
            JOIN people p ON p.id=l.person_id WHERE l.experience_id=? AND p.owner_id=? ORDER BY p.name,p.id''', (experience_id, owner))]  # 不取事件人物聯集
        for p in result['participants']: p['interacted'] = bool(p['interacted'])  # 直接互動與參與分開呈現
        result['mentions'] = [dict(r) for r in c.execute('''SELECT m.*,p.name AS person_name FROM experience_mentions m
            LEFT JOIN people p ON p.id=m.person_id AND p.owner_id=m.owner_id WHERE m.experience_id=? AND m.owner_id=? ORDER BY m.start,m.id''', (experience_id, owner))]  # 每個原文位置有各自配對狀態
        if manage: result['history'] = [dict(r) for r in c.execute('SELECT action,before_json,after_json,created_at FROM story_history WHERE owner_id=? AND experience_id=? ORDER BY rowid', (owner, experience_id))]  # 本人可追溯人工更正
        return result  # 原文與摘要明確分離

    def story_detail(self, owner, experience_id, manage=False):  # 提供 HTTP 來源讀取
        with self.db.connect() as c:  # 使用一致讀取交易
            self._onboarded(c, owner)  # 必須完成首次目標旅程
            return self._story_detail(c, owner, experience_id, manage)  # 不使用前端假資料

    def stories(self, owner, person_id=None, involvement='participant', sort='recent', limit=20, offset=0):  # 以焦點查詢並在 SQL 分頁
        with self.db.connect() as c:  # 同一快照計算總數及頁面
            self._onboarded(c, owner)  # 拒絕未完成旅程存取
            if person_id: self._owned(c, 'people', person_id, owner)  # 人物焦點也核對所屬帳號
            clauses, args = ['s.owner_id=?', 'x.owner_id=?', 's.available=1', 's.reviewed=?'], [owner, owner, 0 if involvement == 'legacy' else 1]  # 未審閱來源只在管理清單
            if person_id:  # 依明確關聯角色分流
                if involvement == 'legacy': clauses.append('x.person_id=?')  # 不推測舊關聯是參與
                elif involvement == 'mention': clauses.append("EXISTS(SELECT 1 FROM experience_mentions m WHERE m.experience_id=x.id AND m.person_id=? AND m.status='matched')")  # 未配對姓名不歸到人物
                else: clauses.append('EXISTS(SELECT 1 FROM experience_participants p WHERE p.experience_id=x.id AND p.person_id=?)')  # 實際參與路徑
                args.append(person_id)  # 使用參數傳入人物 ID
            elif involvement == 'mention': clauses.append("EXISTS(SELECT 1 FROM experience_mentions m WHERE m.experience_id=x.id AND m.status='matched')")  # 無人物時仍僅列有已配對提及的故事
            base = ' FROM experience_stories s JOIN experiences x ON x.id=s.experience_id WHERE ' + ' AND '.join(clauses)  # 固定查詢片段，沒有使用者 SQL
            total = c.execute('SELECT COUNT(*)' + base, args).fetchone()[0]  # 先取得完整符合條件的數量
            order = 'ASC' if sort == 'oldest' else 'DESC'  # 只允許白名單時間排序
            ids = c.execute('SELECT x.id' + base + ' ORDER BY x.occurred_at ' + order + ',x.id ' + order + ' LIMIT ? OFFSET ?', [*args, limit, offset]).fetchall()  # 在資料庫分頁而非載入全部故事
            return {'items': [self._story_detail(c, owner, r[0], involvement == 'legacy') for r in ids], 'total': total, 'limit': limit, 'offset': offset}  # 只組合當頁來源

    def _write_story(self, c, owner, experience_id, raw, story):  # 在同一確認／修正交易保存角色
        self._validate_story(c, owner, raw, story)  # 先核對全部輸入才改資料
        c.execute('DELETE FROM experience_participants WHERE experience_id=?', (experience_id,))  # 更正只影響這一份來源
        c.execute('DELETE FROM experience_mentions WHERE experience_id=?', (experience_id,))  # 舊線索 ID 失效，歷史仍保留
        c.execute('UPDATE experience_stories SET title=?,reviewed=1 WHERE experience_id=?', (story.title, experience_id))  # 只接受人工審閱的標題與角色
        for p in story.participants: c.execute('INSERT INTO experience_participants VALUES (?,?,?)', (experience_id, p.person_id, int(p.interacted)))  # 參與本身不增加統計
        for m in story.mentions:  # 保存未配對或使用者指定的原文身分
            c.execute('INSERT INTO experience_mentions(id,owner_id,experience_id,name,start,end,status,person_id) VALUES (?,?,?,?,?,?,?,?)', (str(uuid4()), owner, experience_id, m.name, m.start, m.end, 'matched' if m.person_id else 'unmatched', m.person_id))  # 正式配對與原名分開

    def _attach_story_event(self, c, owner, experience_id, story, data, occurred_at):  # 只有人工指定直接互動者才接事件統計
        ids = [p.person_id for p in story.participants if p.interacted]  # 同場但未互動者不加入
        if not ids:  # 允許沒有互動的真實故事
            require(not data.interaction_event_id, 422, 'interaction_required', '關聯互動事件前，請確認至少一位直接互動人物。')  # 不隱式擴張出席或見面
            return None  # 純提及與獨處沒有互動事件
        event_id = data.interaction_event_id or str(uuid4())  # 可沿用同次互動
        if data.interaction_event_id:  # 沿用事件須限制帳號與類型
            event = self._resource(c, 'interaction_events', owner, event_id)  # 不接受別人的事件
            require(data.interaction_type == 'unknown' or data.interaction_type == event['kind'], 409, 'interaction_conflict', '互動類型不同，請先分類後再關聯。')  # 不能無聲改類型
            require(any(c.execute('SELECT 1 FROM interaction_people WHERE event_id=? AND person_id=?', (event_id, pid)).fetchone() for pid in ids), 422, 'unrelated_interaction', '請選擇與本次人物相關的互動事件。')  # 必須有共同直接互動者
        else: c.execute('INSERT INTO interaction_events(id,owner_id,kind,occurred_at) VALUES (?,?,?,?)', (event_id, owner, data.interaction_type, occurred_at))  # 類型由使用者選擇
        for pid in ids: c.execute('INSERT OR IGNORE INTO interaction_people VALUES (?,?)', (event_id, pid))  # 同事件不重複增加同一人物
        c.execute('INSERT INTO interaction_experiences VALUES (?,?)', (experience_id, event_id))  # 單筆來源只屬於一個事件
        return event_id  # 將原事件回執交回確認交易

    def _sync_story_event(self, c, experience_id):  # 人工更正後同步事件人物，仍保留舊未審閱記錄
        row = c.execute('SELECT event_id FROM interaction_experiences WHERE experience_id=?', (experience_id,)).fetchone()  # 找出受影響的已存在事件
        if not row:  # 舊無人物故事也可能由本人補確認直接互動
            ids = c.execute('SELECT person_id FROM experience_participants WHERE experience_id=? AND interacted=1', (experience_id,)).fetchall()  # 只採明確直接互動者
            if not ids: return  # 沒有直接互動不造事件
            x = c.execute('SELECT owner_id,occurred_at FROM experiences WHERE id=?', (experience_id,)).fetchone()  # 沿用原始日期與帳號
            event_id = str(uuid4())  # 為首次確認的互動建立固定 ID
            c.execute("INSERT INTO interaction_events(id,owner_id,kind,occurred_at) VALUES (?,?,'unknown',?)", (event_id, x['owner_id'], x['occurred_at']))  # 不猜測實體見面類型
            c.execute('INSERT INTO interaction_experiences VALUES (?,?)', (experience_id, event_id))  # 舊原文仍保持獨立來源
        else: event_id = row[0]  # 保留已有事件的分類與識別碼
        c.execute('DELETE FROM interaction_people WHERE event_id=?', (event_id,))  # 由每份原文的直接互動者重新組合統計名單
        c.execute('''INSERT OR IGNORE INTO interaction_people SELECT ?,p.person_id FROM experience_participants p
            JOIN interaction_experiences l ON l.experience_id=p.experience_id WHERE l.event_id=? AND p.interacted=1''', (event_id, event_id))  # 保留其他故事的明確互動者
        c.execute('''INSERT OR IGNORE INTO interaction_people SELECT ?,x.person_id FROM experiences x JOIN interaction_experiences l ON l.experience_id=x.id
            JOIN experience_stories s ON s.experience_id=x.id WHERE l.event_id=? AND s.reviewed=0 AND x.person_id IS NOT NULL''', (event_id, event_id))  # 尚未人工更正的舊統計不被遷移改寫
        c.execute('UPDATE interaction_events SET revision=revision+1 WHERE id=?', (event_id,))  # 避免與分類／合併修改互相覆蓋

    def _story_history(self, c, owner, experience_id, action, before, after):  # 保存人工操作來源及前後狀態
        c.execute('INSERT INTO story_history VALUES (?,?,?,?,?,?,?)', (str(uuid4()), owner, experience_id, action, json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False), self.now().isoformat()))  # 與操作同交易保存，不改積分帳本

    def edit_story_people(self, owner, experience_id, data):  # 人工確認舊故事或更正角色
        with self.db.connect(write=True) as c:  # 全部角色、版本與歷史原子提交
            self._people_user(c, owner)  # 人物寫入須正式帳號
            before = self._story_detail(c, owner, experience_id, True)  # 本人可修正待核對來源
            op = 'story:people:' + experience_id  # 去重範圍限定來源
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 相同提交不重做更正
            if cached: return cached  # 回原回執
            self._revision(before, data.expected_revision)  # 拒絕舊版本覆寫
            self._write_story(c, owner, experience_id, before['raw_text'], data.story)  # 驗證並保存新名單
            c.execute('UPDATE experience_stories SET revision=revision+1 WHERE experience_id=?', (experience_id,))  # 推進故事版本
            self._sync_story_event(c, experience_id)  # 更新已有事件的直接互動統計
            after = self._story_detail(c, owner, experience_id, True)  # 取得修正後資料
            self._story_history(c, owner, experience_id, 'people', {k: before[k] for k in ('title','participants','mentions')}, data.story.model_dump())  # 不遞迴保存歷史
            self._remember(c, owner, op, data.request_id, fingerprint, after)  # 回執與修改同交易
            return after  # 不呼叫獎勵或貢獻服務

    def match_mention(self, owner, mention_id, data):  # 人工核對原文所指身分
        with self.db.connect(write=True) as c:  # 版本、配對與歷史一致提交
            self._people_user(c, owner)  # 限制正式人物操作
            row = c.execute('SELECT * FROM experience_mentions WHERE id=? AND owner_id=?', (mention_id, owner)).fetchone()  # 不洩露別人線索
            require(row is not None, 404, 'not_found', '找不到這處人物提及，請重新載入來源。')  # 舊線索失效須重讀
            before = dict(row)  # 保留修正前內容
            self._story_row(c, owner, row['experience_id'])  # 已撤回來源不能靠重送取得原文
            op = 'mention:match:' + mention_id  # 分開每個來源位置的去重範圍
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 先檢查相同請求重送
            if cached: return cached  # 不增加版本或歷史
            self._revision(before, data.expected_revision)  # 同時編輯時不能互相覆寫
            if data.person_id: self._owned(c, 'people', data.person_id, owner)  # 人工候選也需所有權驗證
            c.execute('UPDATE experience_mentions SET status=?,person_id=?,revision=revision+1 WHERE id=?', (data.status, data.person_id, mention_id))  # 不改參與者名單
            after = dict(c.execute('SELECT * FROM experience_mentions WHERE id=?', (mention_id,)).fetchone())  # 回讀配對結果
            c.execute('UPDATE experience_stories SET revision=revision+1 WHERE experience_id=?', (row['experience_id'],))  # 人物整理頁須察覺配對變更
            self._story_history(c, owner, row['experience_id'], 'match', before, after)  # 保留取消／拒絕／更正歷史
            self._remember(c, owner, op, data.request_id, fingerprint, after)  # 保存去重回執
            return after  # 提及不發積分、不算見面

    def story_availability(self, owner, experience_id, data):  # 撤回派生探索來源，原經歷仍可讀
        with self.db.connect(write=True) as c:  # 展示狀態與歷史同交易
            self._people_user(c, owner)  # 本人正式帳號可管理故事
            before = self._story_row(c, owner, experience_id, True)  # 已撤回資料仍可恢復
            op = 'story:available:' + experience_id  # 限制來源範圍的去重 key
            cached, fingerprint = self._cached(c, owner, op, data.request_id, data.model_dump())  # 重試不反覆修改
            if cached: return cached  # 回原回執
            self._revision(before, data.expected_revision)  # 避免覆寫較新角色／配對
            c.execute('UPDATE experience_stories SET available=?,revision=revision+1 WHERE experience_id=?', (int(data.available), experience_id))  # 不刪原文與獎勵
            self._story_history(c, owner, experience_id, 'availability', {'available': bool(before['available'])}, {'available': data.available})  # 清楚記錄撤回與恢復
            after = self._story_detail(c, owner, experience_id, True)  # 回傳本人可管理狀態
            self._remember(c, owner, op, data.request_id, fingerprint, after)  # 保存成功結果
            return after  # 不呼叫人物統計或獎勵寫入
