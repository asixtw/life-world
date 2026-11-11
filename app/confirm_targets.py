"""最終確認的多人候選解析；必須在呼叫者同一交易內執行，不另開連線。"""
from .errors import require
from .security import require_registered
from .schemas import PersonCreate, PersonUpdateCandidate, StoryInput, StoryParticipant, StoryMention


class ConfirmTargetsMixin:
    def _require_recordable_person(self, c, owner, person_id, mention=False):
        """結構化010型別約束真人參與；提及只追溯來源，不冒充互動。"""
        row = self._owned(c, 'people', person_id, owner)
        fields = dict(row)
        if 'person_type' in fields:
            require(fields.get('status') == 'active', 409, 'person_archived', '封存人物不可加入新的經歷關聯。')
            if not mention:
                require(fields['person_type'] == 'real' and fields.get('person_subtype') != 'historical',
                        422, 'not_real_participant', '本人真實經歷的參與者不可使用虛構或歷史人物。')
        return row

    def _resolve_confirm_targets(self, c, owner, user, draft, data):
        """回傳解析後的Confirm、逐人更新及client_ref收據；所有失敗由外層交易回滾。"""
        if not (data.pending_people or (data.story and data.story.pending_people)) and not data.targeted_person_updates and not data.birthday_updates and not data.employment_updates:
            return data, [], {}
        require_registered(user)
        require(data.story_reviewed, 422, 'story_review_required', '請先核對所有人物與來源。')
        require(not data.person_updates and not (data.story and data.story.pending_person),
                422, 'ambiguous_person_updates', '請使用單一版本的人物更新契約。')
        story = data.story.model_copy(deep=True) if data.story else StoryInput()
        require(not (data.pending_people and story.pending_people),422,'ambiguous_person_updates','待建立人物只能使用一份已核對名單。')
        candidates=data.pending_people or story.pending_people
        story.pending_people=[]  # 草稿候選在此交易解析；正式故事只存人物ID與角色。
        refs = {}
        for candidate in candidates:
            require(candidate.client_ref not in refs, 422, 'duplicate_client_ref', '待建立人物代碼不可重複。')
            if candidate.relation == 'mention':
                require(candidate.start is not None and draft['raw_text'][candidate.start:candidate.start + len(candidate.name)] == candidate.name,
                        422, 'invalid_mention', '請核對人物提及的原文位置。')
            person = self._create_person(c, owner, PersonCreate(name=candidate.name))
            refs[candidate.client_ref] = person['id']
            if candidate.relation == 'mention':
                story.mentions.append(StoryMention(name=candidate.name, start=candidate.start,
                    end=candidate.start + len(candidate.name), person_id=person['id']))
            else:
                story.participants.append(StoryParticipant(person_id=person['id'], interacted=candidate.relation == 'interaction'))
        # 增補後重新經DTO與來源驗證，不能以model_copy繞過數量或角色重複保護。
        story = StoryInput.model_validate(story.model_dump())
        self._validate_story(c, owner, draft['raw_text'], story)
        linked = {p.person_id for p in story.participants} | {m.person_id for m in story.mentions if m.person_id}
        resolved = []
        for update in data.targeted_person_updates:
            require(update.source_revision == draft['revision'], 409, 'source_revision_conflict', '來源已有新版，請重新核對。')
            require(update.source_kind != 'raw' or bool(update.quote and update.quote in draft['raw_text']),
                    422, 'source_invalid', '來源片段不在目前經歷原文。')
            pid = update.target.person_id or refs.get(update.target.client_ref)
            require(pid is not None, 422, 'target_not_found', '找不到候選指定的人物。')
            row = self._require_recordable_person(c, owner, pid)
            require(pid in linked, 422, 'target_not_linked', '資訊目標必須屬於這次核對的人物。')
            if update.target.person_id:
                require(update.expected_person_revision is not None, 422, 'person_revision_required', '請提供人物版本。')
                self._revision(row, update.expected_person_revision)
            # 證據類型由DTO強制明確給定；不從manual/raw猜測，未勾選亦不得寫入。
            value = PersonUpdateCandidate(**{k: getattr(update, k) for k in PersonUpdateCandidate.model_fields})
            resolved.append((pid, value))
        return data.model_copy(update={'story': story}), resolved, refs

    def delete_draft(self, owner, draft_id, data):
        """只刪未確認且仍為指定版本的自有草稿；重試先查收據，不碰其他Owner素材。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._onboarded(c, owner)
            payload = {**data.model_dump(mode='json'), 'draft_id': draft_id}
            cached, fingerprint = self._cached(c, owner, 'delete_draft', data.request_id, payload)
            if cached:
                return cached
            draft = self._draft(c, owner, draft_id)
            require(draft['status'] == 'draft', 409, 'already_confirmed', '已確認經歷不能當作草稿刪除。')
            self._revision(draft, data.expected_revision)
            # 現有媒體識別API不持久化伺服器原檔；僅清理該草稿FK。
            # 其他未知FK保留資料庫fail-closed，不級聯刪除未審查的新表。
            c.execute('DELETE FROM draft_stories WHERE draft_id=?', (draft_id,))
            c.execute('DELETE FROM drafts WHERE id=? AND owner_id=?', (draft_id, owner))
            result = {'draft_id': draft_id, 'deleted': True}
            self._remember(c, owner, 'delete_draft', data.request_id, fingerprint, result)
            return result
