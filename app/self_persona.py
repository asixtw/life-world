"""Self Persona 與同意管理（2026-11-10 自 8445 的 app/roleplay.py 移植）。

- 「我的人設」存在 works／work_versions（kind=self_persona）；一人一份使用中的人設，改版只新增版本。
- 同意存在 data_consents：可授予、可撤回；同意只綁定當時的人設，撤回後要重新同意。
- 資料格式與 8445 相同，所以 8445 已建立的人設與同意可以直接讀取。
"""
import json
from typing import Annotated, List, Literal, Optional
from uuid import uuid4

from pydantic import Field, StrictBool, StrictInt, StringConstraints

from .character_cards import encoded
from .errors import require
from .schemas import Model

SELF_KIND, SELF_SCHEMA = 'self_persona', 'self_persona.v1'
CONSENT_SUBJECT, CONSENT_VERSION = 'self_persona', 'self-persona-ai-v1'
CONSENT_TEXT = ('我同意 Life World 在生成作品時，把「我的人設」內容傳送給 AI 服務（目前是 Google Gemini），'
                '讓 AI 依照這份人設扮演我。這是虛構演出，不代表我真的這樣說或做；我可以隨時撤回。')
Line = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SelfPersonaContent(Model):
    """可扮演的「我的人設」：公開簡介給其他人物看，其餘欄位只在 AI 扮演使用者本人時使用。"""
    display_name: str = Field(min_length=1, max_length=60)
    public_profile: str = Field(min_length=1, max_length=400)
    personality: str = Field(min_length=1, max_length=2000)
    speaking_style: str = Field(min_length=1, max_length=600)
    motivation: str = Field(default='', max_length=1500)
    values: str = Field(default='', max_length=1500)
    behavior: str = Field(default='', max_length=2000)
    knowledge: str = Field(default='', max_length=2000)
    relationships: str = Field(default='', max_length=2000)
    boundaries: str = Field(default='', max_length=1000)
    appearance: str = Field(default='', max_length=1000)
    sample_lines: List[Line] = Field(default_factory=list, max_length=3)
    truth_level: Literal['real', 'mixed', 'ideal'] = 'mixed'  # 真實的我／部分真實／理想中的我


class SelfPersonaSave(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: Optional[StrictInt] = Field(default=None, ge=1)  # 已有人設時必填，避免覆蓋其他分頁的修改
    content: SelfPersonaContent


class ConsentUpdate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    granted: StrictBool


class SelfPersonaMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾。"""

    @staticmethod
    def _active_self_persona(c, owner):
        return c.execute("SELECT id,owner_id,kind,title,status,current_version,revision,created_at,updated_at FROM works WHERE owner_id=? AND kind=? AND status='active'", (owner, SELF_KIND)).fetchone()

    @staticmethod
    def _active_consent(c, owner):
        return c.execute('SELECT * FROM data_consents WHERE owner_id=? AND subject=? AND purpose=? AND revoked_at IS NULL',
                         (owner, CONSENT_SUBJECT, 'ai_generation')).fetchone()

    @staticmethod
    def _consent_matches(consent, work_id, provider_name=None):
        """同意只授權當時的人設（與 Provider）；人設換了就要重新同意。"""
        return (consent is not None and work_id is not None
                and (provider_name is None or consent['provider_scope'] == provider_name)
                and consent['consent_version'] == CONSENT_VERSION
                and json.loads(consent['source_scope']) == {'kind': SELF_KIND, 'work_id': work_id})

    def _self_persona_view(self, c, owner, provider_name=None):
        work = self._active_self_persona(c, owner)
        persona = None
        if work is not None:
            row = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                            (work['id'], owner, work['current_version'])).fetchone()
            persona = {'work_id': work['id'], 'version_no': work['current_version'], 'revision': work['revision'],
                       'content': json.loads(row['content_json']), 'updated_at': work['updated_at']}
        consent = self._active_consent(c, owner)
        if not self._consent_matches(consent, work['id'] if work else None, provider_name):
            consent = None
        return {'persona': persona,
                'consent': None if consent is None else {'id': consent['id'], 'consent_version': consent['consent_version'],
                                                         'granted_at': consent['granted_at']},
                'consent_text': CONSENT_TEXT, 'consent_version': CONSENT_VERSION}

    def self_persona(self, owner, provider_name=None):
        with self.db.connect() as c:
            self._card_user(c, owner)
            return self._self_persona_view(c, owner, provider_name)

    def save_self_persona(self, owner, data):
        """建立或改版「我的人設」；舊版本保留。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'self_persona:save', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            content, now = data.content.model_dump(mode='json'), self.now().isoformat()
            work = self._active_self_persona(c, owner)
            if work is None:
                work_id = str(uuid4())
                c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) "
                          "VALUES (?,?,?,?,'active',1,1,?,?)", (work_id, owner, SELF_KIND, content['display_name'], now, now))
                c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                          "VALUES (?,?,1,NULL,'human',?,?,NULL,?)", (work_id, owner, SELF_SCHEMA, encoded(content), now))
            else:
                require(data.expected_revision is not None, 409, 'revision_required', '人設已存在，請重新整理後再保存。')
                self._revision(work, data.expected_revision)
                version_no = work['current_version'] + 1
                c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                          "VALUES (?,?,?,?,'human',?,?,NULL,?)", (work['id'], owner, version_no, work['current_version'], SELF_SCHEMA, encoded(content), now))
                c.execute('UPDATE works SET current_version=?,revision=revision+1,title=?,updated_at=? WHERE id=? AND owner_id=?',
                          (version_no, content['display_name'], now, work['id'], owner))
            result = self._self_persona_view(c, owner)
            self._remember(c, owner, 'self_persona:save', data.request_id, fingerprint, result)
            return result

    def set_self_persona_consent(self, owner, data, provider_name=None):
        """同意或撤回把人設送給 AI；撤回保留紀錄（revoked_at），重新同意建立新紀錄。"""
        with self.db.connect(write=True, owner=owner) as c:
            self._card_user(c, owner)
            cached, fingerprint = self._cached(c, owner, 'self_persona:consent', data.request_id, data.model_dump(mode='json'))
            if cached:
                return cached
            active, now = self._active_consent(c, owner), self.now().isoformat()
            if data.granted:
                work = self._active_self_persona(c, owner)
                require(work is not None, 409, 'self_persona_required', '請先建立「我的人設」再同意。')
                scope = provider_name or 'ai_provider'
                if not self._consent_matches(active, work['id'], scope):
                    if active is not None:
                        c.execute('UPDATE data_consents SET revoked_at=? WHERE id=? AND owner_id=? AND revoked_at IS NULL', (now, active['id'], owner))
                    c.execute('INSERT INTO data_consents(id,owner_id,subject,purpose,provider_scope,source_scope,consent_version,granted_at,revoked_at) '
                              "VALUES (?,?,?,'ai_generation',?,?,?,?,NULL)",
                              (str(uuid4()), owner, CONSENT_SUBJECT, scope, encoded({'kind': SELF_KIND, 'work_id': work['id']}), CONSENT_VERSION, now))
            elif active is not None:
                c.execute('UPDATE data_consents SET revoked_at=? WHERE id=? AND owner_id=? AND revoked_at IS NULL', (now, active['id'], owner))
            result = self._self_persona_view(c, owner, provider_name)
            self._remember(c, owner, 'self_persona:consent', data.request_id, fingerprint, result)
            return result
