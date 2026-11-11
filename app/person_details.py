"""人物生日與任職的結構化服務；與Confirm共用連線，歷史不可因新值被刪除。"""
from uuid import uuid4
from pydantic import ValidationError
from .errors import require
from .schemas import BirthdayValue, EmploymentValue

BIRTH_FIELDS = ('birth_year','birth_month','birth_day')
WORK_FIELDS = ('company_name','job_title','employment_status','valid_from','valid_to')
SOURCE_FIELDS = ('source_kind','source_experience_id','evidence_type','source_quote','source_status')


def uid():
    return str(uuid4())


class PersonDetailsMixin:
    def _details_person(self,c,owner,pid,write=False):
        self._people_user(c,owner)
        row=self._owned(c,'people',pid,owner)
        if write and 'status' in dict(row):
            require(row['status']=='active',409,'person_archived','封存人物不可修改基本資料。')
        return row

    def _details_source(self,c,owner,source,experience_id=None):
        """自行記錄不造經歷；raw必須是本Owner有效原文，確認交易可綁剛建立的經歷。"""
        sid=source.source_experience_id
        if source.source_kind=='raw' and experience_id:
            require(sid is None or sid==experience_id,422,'source_mismatch','確認來源必須是本次經歷。')
            sid=experience_id
        if source.source_kind=='raw':
            require(sid is not None,422,'source_required','原文來源須指定正式經歷。')
        if sid:
            row=self._source_experience(c,owner,sid)
            story=c.execute('SELECT available FROM experience_stories WHERE experience_id=? AND owner_id=?',(sid,owner)).fetchone()
            require(story is not None and bool(story['available']),409,'source_unavailable','來源已撤回，請重新核對。')
            if source.source_kind=='raw':
                require(source.quote in row['raw_text'],422,'source_invalid','引用不在經歷原文。')
        return {'source_kind':source.source_kind,'source_experience_id':sid,'evidence_type':source.evidence_type,
                'source_quote':source.quote,'source_status':'active'}

    def _birthday_current(self,c,owner,pid):
        row=c.execute('SELECT * FROM person_basic_details WHERE person_id=? AND owner_id=?',(pid,owner)).fetchone()
        return dict(row) if row else None

    def _set_birthday(self,c,owner,pid,value,source,expected_revision,experience_id=None):
        self._details_person(c,owner,pid,True)
        current=self._birthday_current(c,owner,pid)
        actual=current['revision'] if current else 0
        require(actual==expected_revision,409,'revision_conflict','生日已有新版，請重新載入。')
        now=self.now().isoformat();record={'person_id':pid,'owner_id':owner,**value.model_dump(),
            **self._details_source(c,owner,source,experience_id),'confirmed_at':now,'revision':actual+1,'updated_at':now}
        if current:
            fields=(*BIRTH_FIELDS,*SOURCE_FIELDS,'confirmed_at','revision','updated_at')
            c.execute('UPDATE person_basic_details SET '+','.join(k+'=?' for k in fields)+' WHERE person_id=? AND owner_id=?',
                      tuple(record[k] for k in fields)+(pid,owner))
        else:
            fields=tuple(record)
            c.execute('INSERT INTO person_basic_details('+','.join(fields)+') VALUES ('+','.join('?' for _ in fields)+')',tuple(record.values()))
        kind='created' if not current else 'cleared' if value.birth_month is None else 'corrected'
        history={k:v for k,v in record.items() if k!='updated_at'}
        history={'id':uid(),**history,'change_kind':kind,'recorded_at':now}
        c.execute('INSERT INTO person_basic_detail_history('+','.join(history)+') VALUES ('+','.join('?' for _ in history)+')',tuple(history.values()))
        return record

    def _set_employment(self,c,owner,pid,value,source,expected_revision=0,employment_id=None,experience_id=None):
        self._details_person(c,owner,pid,True)
        current=None
        if employment_id:
            row=c.execute('SELECT * FROM person_employments WHERE id=? AND person_id=? AND owner_id=?',(employment_id,pid,owner)).fetchone()
            require(row is not None,404,'not_found','找不到可修改的任職紀錄。')
            current=dict(row)
        require((current['revision'] if current else 0)==expected_revision,409,'revision_conflict','任職已有新版，請重新載入。')
        merged={k:current[k] for k in WORK_FIELDS} if current else {}
        merged.update(value.model_dump(exclude_unset=True,mode='json'))
        try:
            validated=EmploymentValue.model_validate(merged).model_dump(mode='json')
        except ValidationError:
            # PATCH只帶部分欄位，須合併舊值後驗證；錯誤回422且不洩漏人物內容。
            require(False,422,'invalid_employment','任職至少填公司或職稱，且結束日期不得早於開始日期。')
        now=self.now().isoformat();record={'id':employment_id or uid(),'person_id':pid,'owner_id':owner,**validated,
            **self._details_source(c,owner,source,experience_id),'confirmed_at':now,
            'revision':(current['revision'] if current else 0)+1,'created_at':current['created_at'] if current else now,'updated_at':now}
        if current:
            fields=(*WORK_FIELDS,*SOURCE_FIELDS,'confirmed_at','revision','updated_at')
            c.execute('UPDATE person_employments SET '+','.join(k+'=?' for k in fields)+' WHERE id=? AND person_id=? AND owner_id=?',
                      tuple(record[k] for k in fields)+(record['id'],pid,owner))
        else:
            c.execute('INSERT INTO person_employments('+','.join(record)+') VALUES ('+','.join('?' for _ in record)+')',tuple(record.values()))
        history={k:v for k,v in record.items() if k not in ('id','created_at','updated_at')}
        history={'id':uid(),'employment_id':record['id'],**history,'change_kind':'corrected' if current else 'created','recorded_at':now}
        c.execute('INSERT INTO person_employment_history('+','.join(history)+') VALUES ('+','.join('?' for _ in history)+')',tuple(history.values()))
        return record

    def person_details(self,owner,pid):
        with self.db.connect() as c:
            self._details_person(c,owner,pid)
            return {'person':self._person(c,owner,pid),'birthday':self._birthday_current(c,owner,pid),
                'birthday_history':[dict(r) for r in c.execute('SELECT * FROM person_basic_detail_history WHERE person_id=? AND owner_id=? ORDER BY revision',(pid,owner))],
                'employments':[dict(r) for r in c.execute('SELECT * FROM person_employments WHERE person_id=? AND owner_id=? ORDER BY created_at,id',(pid,owner))],
                'employment_history':[dict(r) for r in c.execute('SELECT * FROM person_employment_history WHERE person_id=? AND owner_id=? ORDER BY employment_id,revision',(pid,owner))]}

    def write_person_details(self,owner,pid,data,kind,employment_id=None):
        """獨立詳情頁修改亦有去重及版本；與Confirm低階寫入共用，不開第二套人物主檔。"""
        with self.db.connect(write=True,owner=owner) as c:
            self._details_person(c,owner,pid,True)
            require(data.confirmed,422,'confirmation_required','請先核對要保存的資料。')
            operation='person-details:'+kind+':'+pid+(':'+employment_id if employment_id else '')
            cached,fingerprint=self._cached(c,owner,operation,data.request_id,data.model_dump(mode='json'))
            if cached:return cached
            if kind=='birthday':
                result=self._set_birthday(c,owner,pid,data.value,data.source,data.expected_revision)
            else:
                result=self._set_employment(c,owner,pid,data.value,data.source,getattr(data,'expected_revision',0),employment_id)
            self._remember(c,owner,operation,data.request_id,fingerprint,result)
            return result

    def withdraw_person_detail_source(self,owner,pid,data,kind,employment_id=None):
        """只撤回指定目前值的來源；保留原值/舊版本，不替使用者判斷其他資料或刪除經歷。"""
        with self.db.connect(write=True,owner=owner) as c:
            self._details_person(c,owner,pid,True)
            require(data.confirmed,422,'confirmation_required','請先確認撤回這筆人物資訊的來源。')
            operation='person-details:withdraw:'+kind+':'+pid+(':'+employment_id if employment_id else '')
            cached,fingerprint=self._cached(c,owner,operation,data.request_id,data.model_dump(mode='json'))
            if cached:return cached
            if kind=='birthday':
                current=self._birthday_current(c,owner,pid)
            else:
                row=c.execute('SELECT * FROM person_employments WHERE id=? AND person_id=? AND owner_id=?',(employment_id,pid,owner)).fetchone()
                current=dict(row) if row else None
            require(current is not None,404,'not_found','找不到可撤回來源的人物資料。')
            require(current['revision']==data.expected_revision,409,'revision_conflict','人物資料已有新版，請重新核對。')
            if current['source_status']!='withdrawn':
                now=self.now().isoformat()
                current.update(source_status='withdrawn',revision=current['revision']+1,updated_at=now)
                table='person_basic_details' if kind=='birthday' else 'person_employments'
                key='person_id' if kind=='birthday' else 'id'
                c.execute('UPDATE '+table+' SET source_status=?,revision=?,updated_at=? WHERE '+key+'=? AND owner_id=?',
                          ('withdrawn',current['revision'],now,pid if kind=='birthday' else employment_id,owner))
                # History append-only；source_withdrawn版保留原始quote/confirmed_at，不冒稱重新核對過內容。
                history={k:v for k,v in current.items() if k not in ('id','created_at','updated_at')}
                history.update(id=uid(),change_kind='source_withdrawn',recorded_at=now)
                if kind=='employment':history['employment_id']=employment_id
                history_table='person_basic_detail_history' if kind=='birthday' else 'person_employment_history'
                c.execute('INSERT INTO '+history_table+'('+','.join(history)+') VALUES ('+','.join('?' for _ in history)+')',tuple(history.values()))
            self._remember(c,owner,operation,data.request_id,fingerprint,current)
            return current

    def _apply_person_basic_candidates(self,c,owner,draft,data,refs,experience_id):
        """Confirm已建經歷後套用各人已核對的基本資料；任何失敗一併回滾獎勵/人物/經歷。"""
        linked=set()
        if data.story:
            linked={p.person_id for p in data.story.participants}|{m.person_id for m in data.story.mentions if m.person_id}
        seen=set()
        for kind,items in [('birthday',data.birthday_updates),('employment',data.employment_updates)]:
            for update in items:
                if not update.selected:continue
                pid=update.target.person_id or refs.get(update.target.client_ref)
                require(pid is not None and pid in linked,422,'target_not_linked','基本資料須指定本次核對的人物。')
                self._require_recordable_person(c,owner,pid)
                require(update.source_revision==draft['revision'],409,'source_revision_conflict','經歷來源已有新版，請重新核對。')
                key=(kind,pid,getattr(update,'employment_id',None) or getattr(update,'client_ref',None))
                require(key not in seen,422,'duplicate_basic_target','本次資料更新代碼重複。');seen.add(key)
                if kind=='birthday':self._set_birthday(c,owner,pid,update.value,update.source,update.expected_revision,experience_id)
                else:
                    require(update.employment_id is not None or bool(update.client_ref),422,'client_ref_required','新任職需要本次唯一代碼。')
                    self._set_employment(c,owner,pid,update.value,update.source,update.expected_revision,update.employment_id,experience_id)
