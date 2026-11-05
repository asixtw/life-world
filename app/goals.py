"""單一挑戰、實際日期安排與人工回顧；共用既有交易與帳本。"""  # 不另建第二套目標資料。
from calendar import monthrange  # 計算不同月份與閏年的天數。
from datetime import date, datetime, timedelta  # 分離當地日期與 UTC 時間。
from decimal import Decimal  # 精確保存習慣數量。
import json  # 保存排程與回顧快照。
from uuid import uuid4  # 產生固定識別碼。
from zoneinfo import ZoneInfo  # 使用目標固定時區。
from .errors import require  # 沿用可識別的領域錯誤。
from .schemas import format_decimal  # 沿用精確數量格式。


def encoded(value):  # 穩定序列化非產品文字資料。
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))  # 支援去重與歷史快照。


def planned_quantity(versions, day):
    """依日期取已確認標準，不依帳號後來變更的時區或目前用量回算。"""
    applicable = [v for v in versions if v['effective_from'] <= day]
    return applicable[-1]['quantity'] if applicable else versions[0]['quantity']


class GoalsMixin:  # 擴充既有服務，不更換技術或 owner。
    def _goal_today(self, user, goal=None):  # 目標建立後固定採當時的時區。
        return self.now().astimezone(ZoneInfo((goal or {}).get('schedule_timezone') or user['timezone'])).date()  # 帳號時區修改不移動舊挑戰。

    def _goal_status(self, goal, user):  # 只讀計算生命週期，不改帳本。
        if goal['status'] == 'completed': return 'completed'  # 已完成優先於日期判定。
        if goal['ended_at']: return 'ended'  # 舊實體狀態維持相容，公開狀態以結束欄位為準。
        if not goal['deadline']: return 'needs_setup'  # 舊資料不猜截止日。
        return 'awaiting_review' if self._goal_today(user, goal) > date.fromisoformat(goal['deadline']) else 'active'  # 截止日包含整個當天。

    @staticmethod  # 共用新建與回顧的排程驗證。
    def _validate_schedule(dates, weekdays, start, end):  # 驗證真實日期與星期。
        require(bool(dates) and len(dates) == len(set(dates)), 422, 'invalid_schedule', '每個習慣至少安排一天，日期不可重複。')  # 不默默刪除輸入。
        require(all(start <= day <= end for day in dates), 422, 'schedule_out_of_range', '習慣安排必須在目標起訖日期內。')  # 防止越界日期。
        require(len(weekdays) == len(set(weekdays)) and all(0 <= day <= 6 for day in weekdays), 422, 'invalid_weekdays', '星期必須是不重複的 0 至 6。')  # 回顧沿用同樣限制。

    def create_goal(self, owner, data):  # 同一交易保證只啟動一個目標。
        with self.db.connect(write=True, owner=owner) as c:  # 寫鎖序列化兩個視窗的競爭。
            user = self._owned_user(c, owner)  # 核對原帳號。
            require(bool(user['bio'] and user['name']), 409, 'bio_required', '請先完成 Bio。')  # 保留首次引導限制。
            cached, fingerprint = self._cached(c, owner, 'goal:create', data.request_id, data.model_dump(mode='json'))  # 先處理重試，再檢查單一名額。
            if cached: return cached  # 不因後來結束而重建舊請求。
            require(not c.execute("SELECT 1 FROM goals WHERE owner_id=? AND status='active' AND ended_at IS NULL", (owner,)).fetchone(), 409, 'open_goal_exists', '先完成或結束目前挑戰，再開始下一個目標。')  # 舊多目標與待回顧同樣阻擋。
            start = self._goal_today(user)  # 由伺服器決定開始日期。
            require(data.deadline >= start, 422, 'invalid_deadline', '截止日不可早於今天。')  # 不預填或推定期限。
            for action in data.actions: self._validate_schedule(action.dates, action.weekdays, start, data.deadline)  # 整批驗證後才建立。
            goal_id, now = str(uuid4()), self.now().isoformat()  # 唯一挑戰與提交時間。
            c.execute("INSERT INTO goals(id,owner_id,title,outcome,status,created_at,start_date,deadline,schedule_timezone) VALUES (?,?,?,?,'active',?,?,?,?)", (goal_id, owner, data.title, data.outcome, now, start.isoformat(), data.deadline.isoformat(), user['timezone']))  # 保存明確期限與固定時區。
            for position, action in enumerate(data.actions):  # 固定三個習慣，保留顯示順序。
                target = action.target or format_decimal(Decimal(action.per_occurrence) * len(action.dates))  # 新習慣依每次量推算安排總量。
                c.execute('INSERT INTO actions(id,goal_id,owner_id,title,unit,target,level,weekdays,position,per_occurrence,schedule_dates,cycle,target_is_derived) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (str(uuid4()), goal_id, owner, action.title, action.unit, target, action.level, encoded(action.weekdays), position, action.per_occurrence, encoded(sorted(day.isoformat() for day in action.dates)), action.cycle, (action.target is None)))  # 不將安排寫入貢獻或帳本。
            c.execute('INSERT INTO habit_quantity_versions(action_id,effective_from,quantity,created_at) SELECT id,?,per_occurrence,? FROM actions WHERE goal_id=?', (start.isoformat(), now, goal_id))
            c.execute('UPDATE users SET hatched_at=COALESCE(hatched_at,?) WHERE id=?', (now, owner))  # 只有第一個成功目標孵化 Lumi。
            result = self._goal(c, goal_id, owner)  # 組合已提交內容。
            self._remember(c, owner, 'goal:create', data.request_id, fingerprint, result)  # 與目標同交易去重。
            return result  # 交易完成後才回傳成功。

    def _goal(self, c, goal_id, owner):  # 擴充既有目標與精確累計。
        goal = self._goal_base(c, goal_id, owner)  # 保留既有貢獻、佐證與識別碼。
        user = self._owned_user(c, owner)  # 提供未設定舊目標的時區。
        goal['status'] = self._goal_status(goal, user)  # 公開統一生命週期。
        goal['today'] = self._goal_today(user, goal).isoformat()  # 前端編輯依原目標時區而非後來的帳號時區。
        for action in goal['actions']:
            action['dates'] = json.loads(action['schedule_dates']) if action['schedule_dates'] is not None else None
            action['quantity_versions'] = [dict(row) for row in c.execute('SELECT effective_from,quantity,created_at FROM habit_quantity_versions WHERE action_id=? ORDER BY effective_from', (action['id'],))]
            action['per_occurrence'] = planned_quantity(action['quantity_versions'], goal['today'])
        goal['pending_contributions'] = [dict(row) for row in c.execute('SELECT p.*,e.occurred_at,e.summary,a.title,a.unit FROM pending_contributions p JOIN experiences e ON e.id=p.experience_id JOIN actions a ON a.id=p.action_id WHERE p.owner_id=? AND p.goal_id=? ORDER BY e.occurred_at,p.id', (owner, goal_id))]  # 保留支持採計的真實來源。
        goal['reviews'] = [dict(row) for row in c.execute('SELECT id,decision,reflection,created_at,previous_state,new_state FROM goal_reviews WHERE owner_id=? AND goal_id=? ORDER BY created_at,' + self.db.audit_column('goal_reviews'), (owner, goal_id))]  # PG 以 identity 取代 rowid。
        goal['allowed_actions'] = ['record', 'complete', 'end', 'schedule'] if goal['status'] == 'active' else ['record', 'complete', 'extend', 'end'] if goal['status'] == 'awaiting_review' else ['setup', 'complete', 'end'] if goal['status'] == 'needs_setup' else []  # 前後端使用同一行為來源。
        return goal  # 不因讀取而改狀態或資料。

    def goal_dashboard(self, owner, goal_id):
        """同一唯讀快照彙整目標；正式貢獻才算投入，草稿與待採計分開。"""
        with self.db.connect() as c:
            user = self._owned_user(c, owner)
            goal = self._goal(c, goal_id, owner)
            today = date.fromisoformat(goal['today'])
            zone = ZoneInfo(goal['schedule_timezone'] or user['timezone'])
            days = { (today - timedelta(days=i)).isoformat(): {} for i in range(6, -1, -1) }
            confirmed_today = set()
            first = datetime.combine(today-timedelta(days=6), datetime.min.time(), zone).isoformat()
            last = datetime.combine(today+timedelta(days=1), datetime.min.time(), zone).isoformat()
            # 以 experience_id 去重，不把一段經歷的多個習慣貢獻算成多段故事。
            # PG 欄位是 timestamptz／boolean，不能沿用 SQLite 的 julianday 或整數比較。
            period_sql = 'e.occurred_at>=CAST(? AS timestamptz) AND e.occurred_at<CAST(? AS timestamptz)' if self.db.backend == 'postgresql' else 'julianday(e.occurred_at)>=julianday(?) AND julianday(e.occurred_at)<julianday(?)'
            for row in c.execute('SELECT e.id,e.summary,e.raw_text,e.occurred_at,k.action_id FROM experiences e JOIN contributions k ON k.experience_id=e.id AND k.owner_id=e.owner_id JOIN actions a ON a.id=k.action_id AND a.owner_id=e.owner_id WHERE e.owner_id=? AND e.goal_id=? AND a.goal_id=? AND ' + period_sql, (owner, goal_id, goal_id, first, last)):
                day = datetime.fromisoformat(row['occurred_at']).astimezone(zone).date().isoformat()
                if day in days:
                    days[day][row['id']] = {key: row[key] for key in ('id','summary','raw_text','occurred_at')}
                if day == goal['today']:
                    confirmed_today.add(row['action_id'])
            in_period = bool(goal['start_date'] and goal['deadline'] and goal['start_date'] <= goal['today'] <= goal['deadline'])
            habits = []
            for action in goal['actions']:
                planned = in_period and (goal['today'] in action['dates'] if action['dates'] is not None else today.weekday() in action['weekdays'])
                habits.append({'actionId':action['id'], 'title':action['title'], 'unit':action['unit'], 'progress':action['progress'], 'target':action['target'], 'plannedToday':planned, 'plannedQuantityToday':planned_quantity(action['quantity_versions'], goal['today']) if planned else None, 'confirmedToday':action['id'] in confirmed_today, 'scheduledDayCount':len(action['dates']) if action['dates'] is not None else None, 'nextScheduledDate':next((day for day in sorted(action['dates'] or []) if day>=goal['today']),None) if goal['status']=='active' else None, 'scheduleDates':action['dates'], 'quantityVersions':action['quantity_versions']})
            tasks = [dict(r) for r in c.execute('SELECT t.* FROM tasks t JOIN experiences e ON e.id=t.experience_id AND e.owner_id=t.owner_id WHERE t.owner_id=? AND e.goal_id=? AND NOT t.done ORDER BY t.id', (owner, goal_id))]
            drafts = [dict(r) for r in c.execute("SELECT id,raw_text,updated_at FROM drafts WHERE owner_id=? AND goal_id=? AND status='draft' ORDER BY updated_at DESC,id", (owner, goal_id))]
            return {'goal':{k:goal[k] for k in ('id','title','outcome','status','start_date','deadline','revision')}, 'goalId':goal_id, 'today':goal['today'], 'timezone':str(zone), 'updatedAt':self.now().isoformat(), 'habits':habits, 'openTasks':tasks, 'drafts':drafts, 'unconfirmedDraftCount':len(drafts), 'pendingContributions':[p for p in goal['pending_contributions'] if p['status']=='pending'], 'trend':{'status':'available','days':[{'date':day,'confirmedExperienceCount':len(rows),'experiences':sorted(rows.values(),key=lambda r:(r['occurred_at'],r['id']))} for day,rows in days.items()]}}

    def calendar(self, owner, goal_id, start=None, end=None):  # 用實際日期取代固定 28 日。
        with self.db.connect() as c:  # 使用同一讀取快照。
            user = self._onboarded(c, owner)  # 首目標限制保持。
            goal = self._goal(c, goal_id, owner)  # 核對所有權。
            first = date.fromisoformat(goal['start_date']) if goal['start_date'] else self._goal_today(user, goal)  # 舊目標只預覽，不寫回日期。
            last = date.fromisoformat(goal['deadline']) if goal['deadline'] else first + timedelta(days=27)  # 舊規律仍可讀取。
            start = start or min(max(self._goal_today(user, goal), first), last)  # 預設從可查看的當前日期開始。
            month, year = (1, start.year + 1) if start.month == 12 else (start.month + 1, start.year)  # 支援跨年。
            next_month = date(year, month, min(start.day, monthrange(year, month)[1]))  # 月底與閏年正確換月。
            end = end or min(last, next_month - timedelta(days=1))  # 預設實際一個月，不固定 28 天。
            require(first <= start <= end <= last and (end - start).days <= 366, 422, 'invalid_calendar_range', '請選目標期間內最多一年的有效日期區間。')  # 分頁查詢避免無限載入。
            dates_by_action = {a['id']: set(a['dates']) if a['dates'] is not None else None for a in goal['actions']}  # 日期集合避免反覆掃描長清單。
            result = []  # 依實際日期建立有界預覽。
            for offset in range((end - start).days + 1):  # 包含起訖兩天。
                day = start + timedelta(days=offset)  # 逐個日曆日計算。
                action_ids = [a['id'] for a in goal['actions'] if day.isoformat() in dates_by_action[a['id']]] if all(v is not None for v in dates_by_action.values()) else [a['id'] for a in goal['actions'] if (day.isoformat() in dates_by_action[a['id']] if dates_by_action[a['id']] is not None else day.weekday() in a['weekdays'])]  # 舊星期只用於未重新確認的行動。
                result.append({'date': day.isoformat(), 'action_ids': action_ids,
                               'planned_quantities': {a['id']: planned_quantity(a['quantity_versions'], day.isoformat()) for a in goal['actions'] if a['id'] in action_ids}})
            return result  # 回傳同一目標的實際安排。

    def _save_goal_contributions(self, c, owner, goal_id, experience_id, occurred_at, items):  # 經歷與目標進度分開決定。
        if not items: return  # 無貢獻經歷仍可保存。
        goal = self._goal(c, goal_id, owner)  # 交易內重新判定到期。
        require(goal['status'] not in {'completed', 'ended'}, 409, 'policy_required', '這次挑戰已收藏；可移除貢獻後保存經歷。')  # 歷史不再改正式投入。
        pending = goal['status'] in {'awaiting_review', 'needs_setup'}  # 不把到期後的活動默默累計。
        if not pending:
            # 只限制立即採計；到期或舊目標仍可保存為待處理，不猜測缺失的期間。
            require(bool(goal['start_date'] and goal['deadline'] and goal['schedule_timezone']), 409, 'goal_setup_required', '請先補齊目標期間與時區，或移除貢獻後保存經歷。')
            occurred = datetime.fromisoformat(occurred_at).astimezone(ZoneInfo(goal['schedule_timezone'])).date().isoformat()
            require(goal['start_date'] <= occurred <= goal['deadline'], 422, 'contribution_out_of_range', '這段經歷不在目標挑戰期間；請移除貢獻後保存經歷。')
        for item in items:  # 每項貢獻保留穩定來源。
            if pending:  # 先保存待處理，經歷照常確認。
                c.execute('INSERT INTO pending_contributions(id,owner_id,goal_id,experience_id,action_id,quantity) VALUES (?,?,?,?,?,?)', (str(uuid4()), owner, goal_id, experience_id, item.action_id, item.quantity))  # 此處不發獎。
            else:  # 進行中沿用原本貢獻交易。
                c.execute('INSERT INTO contributions VALUES (?,?,?,?,?)', (str(uuid4()), owner, experience_id, item.action_id, item.quantity))  # 實際投入由使用者確認。
        c.execute('UPDATE goals SET revision=revision+1 WHERE id=? AND owner_id=?', (goal_id, owner))  # 防止回顧頁忽略新保存資料。

    def review_goal(self, owner, goal_id, data):  # 設定舊目標、調整安排、延長或結束。
        with self.db.connect(write=True, owner=owner) as c:  # 與版本、歷史及去重一起提交。
            goal = self._goal(c, goal_id, owner)  # 先核對所有權，避免透露他人資源。
            user = self._onboarded(c, owner)  # 再核對自身引導狀態。
            payload = dict(data.model_dump(mode='json'), goal_id=goal_id)  # 去重包含完整選擇。
            operation = 'goal:review:' + goal_id  # 不同目標各自隔離。
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, payload)  # 相同成功請求可重試。
            if cached: return cached  # 不再延長或結束第二次。
            require(goal['revision'] == data.expected_revision, 409, 'revision_conflict', '目標已有更新，請重新檢視再確認。')  # 不覆寫新狀態。
            require(goal['status'] not in {'completed', 'ended'}, 409, 'goal_closed', '歷史目標只供回顧，不能恢復或修改。')  # 不提供重試捷徑。
            today, now = self._goal_today(user, goal), self.now().isoformat()  # 同一操作使用固定時間。
            if data.decision == 'end':  # 使用者明確結束。
                reason = 'expired' if goal['status'] == 'awaiting_review' else 'early_end'  # 區分結束原因。
                c.execute('UPDATE goals SET ended_at=?,end_reason=?,reflection=?,revision=revision+1 WHERE id=? AND owner_id=?', (now, reason, data.reflection, goal_id, owner))  # 不刪舊資料。
                c.execute("UPDATE pending_contributions SET status='unapplied' WHERE goal_id=? AND owner_id=? AND status='pending'", (goal_id, owner))  # 保留未採計歷史，不阻擋下一個。
            else:  # 延長或設定必須重新檢視排程。
                require(data.schedules is not None, 422, 'schedules_required', '請檢視三個習慣的安排。')  # 不靜默複製未確認安排。
                if data.decision == 'setup':  # 僅舊資料可補設定。
                    require(goal['status'] == 'needs_setup', 409, 'setup_not_needed', '此目標已完成日期設定。')  # 不繞過延長規則。
                    count = c.execute("SELECT COUNT(*) FROM goals WHERE owner_id=? AND status='active' AND ended_at IS NULL", (owner,)).fetchone()[0]  # 核對舊多目標。
                    require(count == 1, 409, 'legacy_multiple_goals', '請先完成或結束其他舊目標，再設定這次挑戰。')  # 不自動選擇或關閉。
                elif data.decision == 'extend':  # 延長可以在到期前或到期後進行。
                    require(goal['deadline'] is not None and data.deadline is not None and data.deadline > date.fromisoformat(goal['deadline']), 422, 'invalid_extension', '新的截止日必須晚於原截止日。')  # 不縮短既有挑戰。
                else:  # 單純修改未來安排。
                    require(goal['status'] == 'active', 409, 'review_required', '請先回顧或補齊目標設定。')  # 到期不能只改安排繞過回顧。
                    require(data.deadline is None or data.deadline.isoformat() == goal['deadline'], 422, 'invalid_deadline_change', '改截止日請使用延長挑戰。')  # 區分兩種操作。
                deadline = data.deadline or (date.fromisoformat(goal['deadline']) if goal['deadline'] else None)  # 不推定舊期限。
                require(deadline is not None and deadline >= today, 422, 'invalid_deadline', '請選今天或之後的截止日。')  # 已到期不能延到過去。
                start = date.fromisoformat(goal['start_date']) if goal['start_date'] else datetime.fromisoformat(goal['created_at']).astimezone(ZoneInfo(user['timezone'])).date()  # 舊開始日只在使用者確認設定時採用。
                require({s.action_id for s in data.schedules} == {a['id'] for a in goal['actions']}, 422, 'invalid_actions', '請核對這個目標的三個習慣。')  # 拒絕外部或重複 ID。
                for schedule in data.schedules:  # 先驗證全部，任一失敗回滾。
                    self._validate_schedule(schedule.dates, schedule.weekdays, start, deadline)  # 使用同一日期規則。
                    action = next(a for a in goal['actions'] if a['id'] == schedule.action_id)  # 找到原行動。
                    old_dates = action['dates'] or []  # 舊日期未設定時由使用者核對。
                    past = {d for d in old_dates if d < today.isoformat()}  # 過去安排由後端保留。
                    requested_past = {d.isoformat() for d in schedule.dates if d < today}  # 若送出舊日，仍須核對原內容。
                    require(not action['dates'] or not requested_past or requested_past == past, 422, 'past_schedule_locked', '過去安排保留不變，請只修改今天與未來日期。')  # 不允許刻意改寫歷史。
                    dates = sorted(past | {d.isoformat() for d in schedule.dates})  # 支援只提交未來安排且保留原日期。
                    versions = action['quantity_versions']
                    effective = (today + timedelta(days=1)).isoformat()
                    require(schedule.expected_effective_from is None or schedule.expected_effective_from.isoformat() == effective, 409, 'effective_date_changed', '已跨日，請重新核對新用量的生效日期。')
                    if schedule.per_occurrence is not None and schedule.per_occurrence != planned_quantity(versions, effective):
                        require(any(d >= effective for d in dates), 422, 'no_future_occurrence', '沒有明天起的執行日期，請先安排未來日期或延長挑戰。')
                        # 同日最後確認值覆蓋明日版本；前後內容仍留在 goal_reviews。
                        c.execute('INSERT INTO habit_quantity_versions(action_id,effective_from,quantity,created_at) VALUES (?,?,?,?) ON CONFLICT(action_id,effective_from) DO UPDATE SET quantity=excluded.quantity,created_at=excluded.created_at', (action['id'], effective, schedule.per_occurrence, now))
                        versions = [dict(row) for row in c.execute('SELECT effective_from,quantity,created_at FROM habit_quantity_versions WHERE action_id=? ORDER BY effective_from', (action['id'],))]
                    target = format_decimal(sum((Decimal(planned_quantity(versions, d)) for d in dates), Decimal('0'))) if action['target_is_derived'] else action['target']
                    c.execute('UPDATE actions SET title=?,schedule_dates=?,weekdays=?,cycle=?,target=? WHERE id=? AND owner_id=?', (schedule.title or action['title'], encoded(dates), encoded(schedule.weekdays), schedule.cycle, target, action['id'], owner))
                c.execute('UPDATE goals SET start_date=?,deadline=?,schedule_timezone=COALESCE(schedule_timezone,?),revision=revision+1 WHERE id=? AND owner_id=?', (start.isoformat(), deadline.isoformat(), user['timezone'], goal_id, owner))  # 新期限與三安排一起提交。
            updated = self._goal(c, goal_id, owner)  # 取得新生命週期與版本。
            snapshot = lambda value: {key: value[key] for key in ('id', 'status', 'start_date', 'deadline', 'schedule_timezone', 'revision', 'ended_at', 'end_reason', 'actions')}  # 不把過往回顧遞迴包入新快照。
            c.execute('INSERT INTO goal_reviews(id,owner_id,goal_id,decision,previous_state,new_state,reflection,created_at) VALUES (?,?,?,?,?,?,?,?)', (str(uuid4()), owner, goal_id, data.decision, encoded(snapshot(goal)), encoded(snapshot(updated)), data.reflection, now))  # 不寫 PG identity；保持原快照欄位。
            result = self._goal(c, goal_id, owner)  # 包含本次回顧紀錄。
            self._remember(c, owner, operation, data.request_id, fingerprint, result)  # 回顧重試不重複。
            return result  # 回傳新版本。

    def accept_pending(self, owner, goal_id, pending_id, data):  # 延長後逐筆人工採計，不重新確認經歷。
        with self.db.connect(write=True, owner=owner) as c:  # 同時處理採計、版本與去重。
            user = self._onboarded(c, owner)  # 核對帳號。
            goal = self._goal(c, goal_id, owner)  # 核對目標歸屬。
            pending = c.execute('SELECT p.*,e.occurred_at FROM pending_contributions p JOIN experiences e ON e.id=p.experience_id WHERE p.id=? AND p.goal_id=? AND p.owner_id=?', (pending_id, goal_id, owner)).fetchone()  # 不允許跨目標或跨帳號。
            require(pending is not None, 404, 'not_found', '找不到可採計的貢獻。')  # 不洩漏他人資料。
            operation = 'goal:pending:' + pending_id  # 每筆來源獨立去重。
            payload = dict(data.model_dump(mode='json'), goal_id=goal_id)  # 指紋包含數量與版本。
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, payload)  # 成功後可安全重試。
            if cached: return cached  # 不重複寫 contribution。
            require(goal['revision'] == data.expected_revision, 409, 'revision_conflict', '目標已有更新，請重新檢視。')  # 使用最新版本。
            require(goal['status'] == 'active' and pending['status'] == 'pending', 409, 'pending_not_applicable', '請先延長挑戰；歷史或已處理貢獻不能再次採計。')  # 不自動恢復歷史。
            occurred = datetime.fromisoformat(pending['occurred_at']).astimezone(ZoneInfo(goal['schedule_timezone'])).date()  # 依原目標時區判定活動日期。
            require(goal['start_date'] <= occurred.isoformat() <= goal['deadline'], 422, 'contribution_out_of_range', '這段經歷不在目前挑戰期間，請保留為未採計。')  # 不把期外活動硬塞入進度。
            c.execute('INSERT INTO contributions VALUES (?,?,?,?,?)', (str(uuid4()), owner, pending['experience_id'], pending['action_id'], data.quantity))  # 僅增加已人工確認進度。
            c.execute("UPDATE pending_contributions SET status='accepted',accepted_quantity=?,accepted_at=? WHERE id=? AND owner_id=?", (data.quantity, self.now().isoformat(), pending_id, owner))  # 保留原數量及採計量。
            c.execute('UPDATE goals SET revision=revision+1 WHERE id=? AND owner_id=?', (goal_id, owner))  # 同步版本。
            result = self._goal(c, goal_id, owner)  # 回傳更新後的目標。
            self._remember(c, owner, operation, data.request_id, fingerprint, result)  # 與採計同交易保存。
            return result  # 不呼叫獎勵函式。
