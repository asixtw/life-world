"""沿用draft_stories JSON保存核對資料；所有方法使用呼叫者交易，不建第二套人物資料庫。"""
import hashlib,json
from .errors import require
from .security import require_registered
from pydantic import ValidationError
from .schemas import (DraftReview,StoryInput,TargetedPersonUpdate,BirthdayValue,EmploymentValue,
    TargetBirthdayUpdate,TargetEmploymentUpdate,PersonDetailSource,DraftPersonCandidate,DraftBirthdayCandidate)


def source_hash(raw):return hashlib.sha256(raw.encode('utf-8')).hexdigest()


class DraftReviewMixin:
    def _normalize_draft_review(self,c,owner,raw,story,review):
        """保留未完成輸入；只撤銷失效來源的採用，不自動猜證據類型或覆寫手動資料。"""
        if review is None:return None
        review=review.model_copy(deep=True);digest=source_hash(raw)
        review.summary_needs_review=review.summary is not None and review.summary_source_sha256!=digest
        refs={p.client_ref for p in story.pending_people} if story else set()
        candidates=[*review.person_candidates,*review.birthday_candidates,*review.employment_candidates]
        if candidates:require_registered(self._onboarded(c,owner))
        for candidate in candidates:
            if candidate.target.person_id:self._owned(c,'people',candidate.target.person_id,owner)
            else:require(candidate.target.client_ref in refs,422,'candidate_target_missing','人物候選的待建目標不在本草稿中。')
            stale=candidate.source_kind=='raw' and (candidate.source_sha256!=digest or not candidate.quote or candidate.quote not in raw)
            if isinstance(candidate,DraftPersonCandidate):
                incomplete=not candidate.dimension or not candidate.value.strip() or not candidate.evidence_type
            else:
                # 自行記錄不虛構證據；原文候選必須明確提供得知依據。
                incomplete=candidate.source_kind=='raw' and not candidate.evidence_type
                try:
                    if isinstance(candidate,DraftBirthdayCandidate):
                        value=BirthdayValue.model_validate(candidate.value.model_dump())
                        incomplete=incomplete or (candidate.clear and value.birth_month is not None) or (not candidate.clear and value.birth_month is None)
                    elif candidate.employment_id:
                        require(candidate.target.person_id is not None,422,'candidate_target_missing','既有任職不可指向待建立人物。')
                        row=c.execute('SELECT id FROM person_employments WHERE id=? AND owner_id=? AND person_id=?',(candidate.employment_id,owner,candidate.target.person_id)).fetchone()
                        require(row is not None,404,'not_found','找不到指定人物的任職。')
                        incomplete=incomplete or not candidate.value.model_fields_set or candidate.expected_revision<1
                    else:
                        EmploymentValue.model_validate(candidate.value.model_dump(exclude_unset=True))
                except ValidationError:incomplete=True
            candidate.needs_review=bool(stale or incomplete)
            if candidate.needs_review:candidate.selected=False
        return review

    def _store_draft_content(self,c,owner,draft_id,raw,story,review):
        """相容舊StoryInput payload；新格式為有版本的story/review envelope，仍在同一列。"""
        self._store_draft_story(c,owner,draft_id,raw,story)
        if review is None:return
        normalized=self._normalize_draft_review(c,owner,raw,story,review)
        payload={'_format':'experience_draft_v2','story':story.model_dump(mode='json') if story else None,'review':normalized.model_dump(mode='json')}
        c.execute('INSERT INTO draft_stories VALUES (?,?) ON CONFLICT(draft_id) DO UPDATE SET payload=excluded.payload',(draft_id,json.dumps(payload,ensure_ascii=False)))

    def _prepare_review_confirm(self,c,owner,draft,data):
        """明確選用完整核對契約才套用人物候選；舊客戶端不得靜默丟棄已保存候選。"""
        stored=DraftReview.model_validate(draft['review']) if draft.get('review') is not None else None
        review=data.review or (stored if data.use_saved_review else None)
        if review is None:
            require(not (stored and (stored.person_candidates or stored.birthday_candidates or stored.employment_candidates)),409,'saved_review_required','此草稿含人物補充候選，請使用完整核對流程，不會靜默捨棄。')
            if stored and stored.summary_needs_review:
                require(data.reviewed_summary_sha256==source_hash(draft['raw_text']),409,'summary_source_review_required','原文已修改，請重新核對摘要。')
            return data
        require(not data.targeted_person_updates and not data.person_updates and not data.birthday_updates and not data.employment_updates,422,'ambiguous_review','不可混用兩份人物資訊候選。')
        story=data.story
        if story is None and 'story' not in data.model_fields_set and draft['story'] is not None:story=StoryInput.model_validate(draft['story'])
        review=self._normalize_draft_review(c,owner,draft['raw_text'],story,review)
        require(not review.summary_needs_review,409,'summary_source_review_required','原文已修改，請重新核對摘要。')
        if review.summary is not None:require(data.summary==review.summary.strip(),422,'review_summary_mismatch','最終摘要與核對內容不同，請重新核對。')
        require(data.tasks==[t.strip() for t in review.tasks],422,'review_tasks_mismatch','最終任務與核對內容不同，請重新核對。')
        updates=[]
        for candidate in review.person_candidates:
            if candidate.excluded:continue
            require(candidate.selected and not candidate.needs_review,409,'candidate_review_required','請逐項核對或排除人物候選，未完成不寫入。')
            updates.append(TargetedPersonUpdate(target=candidate.target,expected_person_revision=candidate.expected_person_revision,
                dimension=candidate.dimension,value=candidate.value,description=candidate.description,evidence_type=candidate.evidence_type,
                selected=True,source_kind=candidate.source_kind,source_revision=draft['revision'],quote=candidate.quote))
        birthdays=[];employments=[]
        for kind,items in [('birthday',review.birthday_candidates),('employment',review.employment_candidates)]:
            for candidate in items:
                if candidate.excluded:continue
                require(candidate.selected and not candidate.needs_review,409,'candidate_review_required','請逐項核對或排除人物基本資料候選。')
                source=PersonDetailSource(source_kind=candidate.source_kind,evidence_type=candidate.evidence_type,quote=candidate.quote)
                common={'target':candidate.target,'expected_revision':candidate.expected_revision,'source_revision':draft['revision'],'selected':True,'source':source}
                if kind=='birthday':birthdays.append(TargetBirthdayUpdate(**common,value=BirthdayValue.model_validate(candidate.value.model_dump())))
                else:employments.append(TargetEmploymentUpdate(**common,employment_id=candidate.employment_id,
                    client_ref=None if candidate.employment_id else candidate.candidate_ref,value=candidate.value))
        # 最後選擇的摘要/任務/候選與正式寫入同一交易；後續失敗會一併回滾。
        self._store_draft_content(c,owner,draft['id'],draft['raw_text'],story,review)
        return data.model_copy(update={'story':story,'targeted_person_updates':updates,'birthday_updates':birthdays,'employment_updates':employments})
