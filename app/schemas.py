from datetime import date, datetime  # 處理 UTC、實際日期與期限。
from decimal import Decimal, InvalidOperation  # 以精確十進位處理貢獻量，避免浮點誤差
from typing import List, Optional, Literal  # 宣告可選欄位、清單與受限字串型別
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # 使用 IANA 時區轉換日期與時間

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictBool, field_validator, model_validator  # 定義輸入模型、型別、長度與跨欄位驗證


def decimal_string(value):  # 驗證正數、上限與小數位數，避免浮點誤差
    if isinstance(value, bool):  # Python 將布林視為整數子類，須先拒絕以免 True 被當作 1
        raise ValueError('請填寫正數')  # 中止目前操作並向呼叫端傳遞錯誤
    try:  # 保護可能失敗的操作，交由下方例外分支處理
        value = Decimal(str(value))  # 先轉成字串再建立精確十進位數值
    except InvalidOperation:  # 處理此類預期例外並保留明確失敗結果
        raise ValueError('請填寫有效數字')  # 中止目前操作並向呼叫端傳遞錯誤
    if not value.is_finite() or value <= 0 or value > Decimal('1000000000000'):  # 拒絕 NaN、無限大、非正數與超過上限的值
        raise ValueError('數值必須大於 0 且不超過 10^12')  # 中止目前操作並向呼叫端傳遞錯誤
    if value.as_tuple().exponent < -6:  # 最多保留六位小數，避免不受限精度的輸入
        raise ValueError('最多六位小數')  # 中止目前操作並向呼叫端傳遞錯誤
    return format_decimal(value)  # 回傳驗證正數、上限與小數位數，避免浮點誤差的結果


def format_decimal(value):  # 輸出無科學記號且去除多餘尾零的十進位字串
    result = format(value, 'f')  # 準備本次操作的回傳資料
    return result.rstrip('0').rstrip('.') if '.' in result else result  # 回傳輸出無科學記號且去除多餘尾零的十進位字串的結果


class Model(BaseModel):  # 拒絕多餘欄位的共用輸入模型
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)  # 設定輸入欄位驗證策略


class Profile(Model):  # 個人介紹與時區輸入
    name: str = Field(min_length=1, max_length=80)  # 設定顯示稱呼的型別、預設值與輸入限制
    bio: str = Field(min_length=1, max_length=2000)  # 設定自我介紹的型別、預設值與輸入限制
    timezone: str = 'Asia/Taipei'  # 設定IANA 時區的型別、預設值與輸入限制

    @field_validator('timezone')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_timezone(cls, value):  # 確認 IANA 時區可解析
        try:  # 保護可能失敗的操作，交由下方例外分支處理
            ZoneInfo(value)  # 確認此 IANA 時區存在且可解析
        except (ZoneInfoNotFoundError, ValueError):  # 處理此類預期例外並保留明確失敗結果
            raise ValueError('請使用有效的 IANA 時區')  # 中止目前操作並向呼叫端傳遞錯誤
        return value  # 回傳已通過檢查的值


class Credentials(Model):  # 建立本機帳號的認證輸入（不裁切密碼）
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)  # 設定輸入欄位驗證策略
    username: str = Field(pattern=r'^[a-zA-Z0-9_]{3,30}$')  # 設定本機帳號名稱的型別、預設值與輸入限制
    password: str = Field(min_length=10, max_length=128)  # 設定登入密碼的型別、預設值與輸入限制

    @field_validator('username')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def normalize_username(cls, value):  # 統一帳號大小寫以避免重複
        return value.lower()  # 回傳統一帳號大小寫以避免重複的結果


class Login(Model):  # 登入與訪客衝突確認輸入
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)  # 設定輸入欄位驗證策略
    username: str = Field(min_length=1, max_length=128)  # 設定本機帳號名稱的型別、預設值與輸入限制
    password: str = Field(min_length=1, max_length=128)  # 設定登入密碼的型別、預設值與輸入限制
    discard_guest: bool = False  # 設定明確同意離開既有訪客身分的型別、預設值與輸入限制


class Action(Model):  # 單項行動的目標量、等級與每週規律
    title: str = Field(min_length=1, max_length=160)  # 設定標題的型別、預設值與輸入限制
    unit: str = Field(default='次', min_length=1, max_length=20)  # 設定行動計量單位的型別、預設值與輸入限制
    target: Optional[str] = None  # 舊累計目標保留；新習慣依安排推算。
    per_occurrence: str = '1'  # 每次預期量預設一次。
    dates: List[date] = Field(default_factory=list, max_length=10000)  # 保存實際安排日期。
    cycle: Literal['month', 'week'] = 'month'  # 預設按月編輯，可切換週。
    level: StrictInt = Field(default=1, ge=1, le=3)  # 保留舊養分設定。
    weekdays: List[StrictInt] = Field(default_factory=list, max_length=7)  # 允許只安排單日。

    @field_validator('target', 'per_occurrence', mode='before')  # 數量沿用精確正數限制。
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_target(cls, value):  # 驗證行動目標數值
        return decimal_string(value)  # 回傳驗證行動目標數值的結果

    @field_validator('weekdays')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_days(cls, value):  # 限制星期為不重複的 0 至 6
        if len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value):  # 依目前條件選擇下一步處理分支
            raise ValueError('星期需為不重複的 0～6')  # 中止目前操作並向呼叫端傳遞錯誤
        return sorted(value)  # 回傳限制星期為不重複的 0 至 6的結果


class GoalCreate(Model):  # 建立目標與三項行動的輸入
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    title: str = Field(min_length=1, max_length=160)  # 設定標題的型別、預設值與輸入限制
    outcome: str = Field(min_length=1, max_length=4000)  # 設定目標的終極成果說明的型別、預設值與輸入限制
    deadline: date  # 截止日必須由使用者明確選擇。
    actions: List[Action] = Field(min_length=3, max_length=3)  # 固定三個重要習慣。


class Contribution(Model):  # 一項行動的人工貢獻量
    action_id: str = Field(min_length=1, max_length=128)  # 設定本次貢獻所屬行動識別碼的型別、預設值與輸入限制
    quantity: str  # 設定本次人工確認的貢獻量的型別、預設值與輸入限制

    @field_validator('quantity', mode='before')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_quantity(cls, value):  # 驗證人工貢獻量
        return decimal_string(value)  # 回傳驗證人工貢獻量的結果


class WithContributions(Model):  # 含去重貢獻清單的共用輸入
    contributions: List[Contribution] = Field(default_factory=list, max_length=50)  # 設定本次要累計的行動貢獻清單的型別、預設值與輸入限制

    @model_validator(mode='after')  # 在模型建立後檢查跨欄位限制
    def distinct_actions(self):  # 拒絕在同次貢獻中重複列入同一行動
        ids = [c.action_id for c in self.contributions]  # 保存「ids」供後續驗證或回傳使用
        if len(ids) != len(set(ids)):  # 依目前條件選擇下一步處理分支
            raise ValueError('同一行動在本次貢獻只能出現一次')  # 中止目前操作並向呼叫端傳遞錯誤
        return self  # 回傳拒絕在同次貢獻中重複列入同一行動的結果


class StoryParticipant(Model):  # 明確參與者與直接互動旗標
    person_id: str = Field(min_length=1, max_length=128)  # 使用固定人物 ID，不依名字合併
    interacted: bool = Field(default=False, strict=True)  # 同場預設不算直接互動


class StoryMention(Model):  # 尚未配對或已人工指定的原文提及
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)  # 保留原文字元與空白
    name: str = Field(min_length=1, max_length=100)  # 精確對應來源字串
    start: StrictInt = Field(ge=0)  # 原文 Unicode 起點
    end: StrictInt = Field(gt=0)  # 原文 Unicode 終點，不包含此位置
    person_id: Optional[str] = Field(default=None, min_length=1, max_length=128)  # 只有使用者選定才保存人物身分


class PendingPerson(Model):
    """待確認人物，不在草稿階段建立正式紀錄。"""
    name: str = Field(min_length=1, max_length=100)
    relation: Literal['participant', 'interaction', 'mention']
    start: Optional[StrictInt] = Field(default=None, ge=0, exclude_if=lambda v: v is None)


class PendingTargetPerson(PendingPerson):
    """待建立人物在單次請求中的穩定識別，不依姓名合併。"""
    client_ref: str = Field(min_length=1, max_length=128)


class StoryInput(Model):  # 草稿與正式人物核對共用資料
    pending_person: Optional[PendingPerson] = Field(default=None, exclude_if=lambda v: v is None)  # 只存候選；最終確認才建人
    pending_people: List[PendingTargetPerson] = Field(default_factory=list,max_length=100,exclude_if=lambda v:not v)
    title: str = Field(default='', max_length=160)  # 可另取故事標題
    participants: List[StoryParticipant] = Field(default_factory=list, max_length=100)  # 每筆經歷最多一百位參與者
    mentions: List[StoryMention] = Field(default_factory=list, max_length=100)  # 每個原文位置獨立配對

    @model_validator(mode='after')  # 驗證跨項目的唯一性
    def distinct_links(self):  # 拒絕重複人物與重複提及位置
        ids = [p.person_id for p in self.participants]  # 取得固定人物識別碼
        spans = [(m.start, m.end) for m in self.mentions]  # 取得原文範圍
        if self.pending_person and self.pending_people:
            raise ValueError('單人與多人待建立契約不可混用')
        refs=[p.client_ref for p in self.pending_people]
        if len(refs)!=len(set(refs)):
            raise ValueError('待建立人物代碼不可重複')
        pending_spans=[(p.start,(p.start or 0)+len(p.name)) for p in self.pending_people if p.relation=='mention']
        if len(ids)+sum(p.relation!='mention' for p in self.pending_people)>100 or len(spans)+len(pending_spans)>100:
            raise ValueError('人物參與或提及總數超過上限')
        if len(spans+pending_spans)!=len(set(spans+pending_spans)):
            raise ValueError('待建立人物提及位置重複')
        if self.pending_person:
            pending = self.pending_person
            if pending.relation == 'mention' and ((pending.start, (pending.start or 0) + len(pending.name)) in spans or len(spans) >= 100):
                raise ValueError('新增人物的提及位置不能重複或超過上限')
            if pending.relation != 'mention' and len(ids) >= 100:
                raise ValueError('參與人物已達上限')
        if len(ids) != len(set(ids)) or len(spans) != len(set(spans)):  # 重複輸入不能默默覆寫
            raise ValueError('參與者與提及位置不可重複')  # 讓介面要求人工修正
        return self  # 回傳唯一且合法的角色資料


class DraftCreate(WithContributions):
    request_id: Optional[str] = Field(default=None,min_length=1,max_length=128)  # 可選重送識別；相容舊客戶端。  # 尚未確認的原始經歷輸入
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)  # 設定輸入欄位驗證策略
    raw_text: str = Field(min_length=1, max_length=20000)  # 設定原始經歷文字（保留空白與換行）的型別、預設值與輸入限制
    occurred_at: datetime  # 設定帶時區的實際發生時間的型別、預設值與輸入限制
    goal_id: Optional[str] = Field(default=None, max_length=128)  # 設定關聯目標識別碼的型別、預設值與輸入限制
    person_id: Optional[str] = Field(default=None, max_length=128)  # 設定關聯人物識別碼的型別、預設值與輸入限制
    story: Optional[StoryInput] = None  # 保存未審閱的多人整理，舊用戶端可省略

    @field_validator('raw_text')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def nonblank_raw(cls, value):  # 拒絕純空白原文，同時保留有效原文的空白
        if not value.strip():  # 依目前條件選擇下一步處理分支
            raise ValueError('原始記錄不可為空白')  # 中止目前操作並向呼叫端傳遞錯誤
        return value  # 回傳已通過檢查的值

    @field_validator('occurred_at')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def aware_time(cls, value):  # 要求實際發生時間明確攜帶時區
        if value.tzinfo is None or value.utcoffset() is None:  # 依目前條件選擇下一步處理分支
            raise ValueError('發生時間必須帶時區')  # 中止目前操作並向呼叫端傳遞錯誤
        return value  # 回傳已通過檢查的值


class DraftEdit(DraftCreate):  # 攜帶預期版本的草稿修改輸入
    expected_revision: StrictInt = Field(ge=1)  # 設定修改者已讀取的版本號的型別、預設值與輸入限制


class PersonUpdateCandidate(Model):  # 必須逐項勾選的人物資訊候選
    dimension: Literal['interests', 'food', 'skills', 'habits']  # 設定人物資訊所屬四維度之一的型別、預設值與輸入限制
    value: str = Field(min_length=1, max_length=160)  # 設定人物資訊標籤內容的型別、預設值與輸入限制
    description: str = Field(default='', max_length=2000)  # 設定人物資訊補充說明的型別、預設值與輸入限制
    evidence_type: Literal['stated_by_person', 'observed_by_user', 'documented_source']  # 設定人工確認的證據類型的型別、預設值與輸入限制
    selected: bool = False  # 設定是否明確勾選更新人物資訊的型別、預設值與輸入限制
    conflicts_with: Optional[str] = None  # 設定使用者指定的衝突資訊識別碼的型別、預設值與輸入限制


class BirthdayValue(Model):
    birth_year: Optional[StrictInt] = Field(default=None, ge=1, le=9999)
    birth_month: Optional[StrictInt] = Field(default=None, ge=1, le=12)
    birth_day: Optional[StrictInt] = Field(default=None, ge=1, le=31)

    @model_validator(mode='after')
    def actual_date(self):
        """未知年只用閏年驗月日合法性，絕不把此年寫入生日或推算年齡。"""
        if (self.birth_month is None) != (self.birth_day is None):
            raise ValueError('生日的月與日必須同時存在或同時為空')
        if self.birth_year is not None and self.birth_month is None:
            raise ValueError('不能只保存出生年份而沒有月日')
        if self.birth_month is not None:
            date(self.birth_year if self.birth_year is not None else 2000, self.birth_month, self.birth_day)
        return self


class EmploymentValue(Model):
    company_name: str = Field(default='', max_length=300)
    job_title: str = Field(default='', max_length=300)
    employment_status: Literal['current', 'past', 'unknown'] = 'unknown'
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @model_validator(mode='after')
    def meaningful_entry(self):
        """一筆至少公司或職稱，空日期保持NULL；不自動結束另一筆工作。"""
        if not self.company_name and not self.job_title:
            raise ValueError('公司與職稱至少填寫一項')
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError('任職結束日期不得早於開始日期')
        return self


class PersonDetailSource(Model):
    """輸入管道與得知依據分開；自行記錄可以不知道證據，不假造經歷ID。"""
    source_kind: Literal['manual', 'raw']
    source_experience_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    evidence_type: Optional[Literal['stated_by_person', 'observed_by_user', 'documented_source']] = None
    quote: Optional[str] = Field(default=None, max_length=20000)

    @model_validator(mode='after')
    def explicit_experience_source(self):
        # Confirm中的新經歷尚未產生ID，可由交易在確認後綁定；獨立人物編輯需服務層檢查ID與Owner。
        if self.source_kind == 'raw' and (self.evidence_type is None or not self.quote):
            raise ValueError('經歷來源須有引用與明確得知依據')
        return self


class PersonUpdateTarget(Model):
    person_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    client_ref: Optional[str] = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode='after')
    def exactly_one(self):
        if bool(self.person_id) == bool(self.client_ref):
            raise ValueError('人物目標必須且只能指定person_id或client_ref')
        return self


class TargetedPersonUpdate(PersonUpdateCandidate):
    """每項更新明確攜帶人物、來源版本與得知依據，禁止第一人預設。"""
    target: PersonUpdateTarget
    expected_person_revision: Optional[StrictInt] = Field(default=None, ge=1)
    source_kind: Literal['manual', 'raw']
    source_revision: StrictInt = Field(ge=1)
    quote: Optional[str] = Field(default=None, max_length=20000)


class BirthdayWrite(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=0)
    confirmed: StrictBool
    value: BirthdayValue
    source: PersonDetailSource


class EmploymentPatchValue(Model):
    company_name: Optional[str] = Field(default=None, max_length=300)
    job_title: Optional[str] = Field(default=None, max_length=300)
    employment_status: Optional[Literal['current','past','unknown']] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None

    @model_validator(mode='after')
    def no_null_identity(self):
        if any(getattr(self,k) is None for k in self.model_fields_set if k in ('company_name','job_title','employment_status')):
            raise ValueError('公司、職稱與任職狀態不能傳null；未知日期可用null')
        return self


class EmploymentCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    confirmed: StrictBool
    value: EmploymentValue
    source: PersonDetailSource


class EmploymentPatch(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    confirmed: StrictBool
    value: EmploymentPatchValue
    source: PersonDetailSource


class PersonDetailSourceWithdrawal(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    confirmed: StrictBool


class TargetBirthdayUpdate(Model):
    target: PersonUpdateTarget
    expected_revision: StrictInt = Field(ge=0)
    source_revision: StrictInt = Field(ge=1)
    selected: StrictBool = False
    value: BirthdayValue
    source: PersonDetailSource


class TargetEmploymentUpdate(Model):
    target: PersonUpdateTarget
    employment_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    client_ref: Optional[str] = Field(default=None, min_length=1, max_length=128)
    expected_revision: StrictInt = Field(default=0, ge=0)
    source_revision: StrictInt = Field(ge=1)
    selected: StrictBool = False
    value: EmploymentPatchValue
    source: PersonDetailSource


class DraftDelete(Model):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)


class Confirm(WithContributions):  # 將草稿正式確認為經歷的輸入
    birthday_updates: List[TargetBirthdayUpdate] = Field(default_factory=list, max_length=100, exclude_if=lambda v: not v)
    employment_updates: List[TargetEmploymentUpdate] = Field(default_factory=list, max_length=100, exclude_if=lambda v: not v)
    pending_people: List[PendingTargetPerson] = Field(default_factory=list, max_length=100, exclude_if=lambda v: not v)
    targeted_person_updates: List[TargetedPersonUpdate] = Field(default_factory=list, max_length=100, exclude_if=lambda v: not v)
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    expected_revision: StrictInt = Field(ge=1)  # 設定修改者已讀取的版本號的型別、預設值與輸入限制
    summary: str = Field(min_length=1, max_length=20000)  # 設定使用者核對後的經歷摘要的型別、預設值與輸入限制
    person_id: Optional[str] = Field(default=None, max_length=128)  # 設定關聯人物識別碼的型別、預設值與輸入限制
    tasks: List[str] = Field(default_factory=list, max_length=20)  # 設定由本次經歷建立的下一步的型別、預設值與輸入限制
    interaction_type: Literal['in_person', 'call', 'message', 'other', 'unknown'] = 'unknown'  # 設定真實互動類型（不預設見面）的型別、預設值與輸入限制
    interaction_event_id: Optional[str] = None  # 設定要沿用的既有互動事件識別碼的型別、預設值與輸入限制
    person_updates: List[PersonUpdateCandidate] = Field(default_factory=list, max_length=30)  # 設定逐項確認的人物資訊候選的型別、預設值與輸入限制
    story: Optional[StoryInput] = None  # 正式確認每筆經歷的人物角色
    story_reviewed: bool = Field(default=False, strict=True)  # 核對與配對必須由使用者明確接受

    @field_validator('tasks')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_tasks(cls, values):  # 清理任務首尾空白並限制內容長度
        values = [v.strip() for v in values]  # 準備此步驟驗證或搜尋需要的值清單
        if any(not v or len(v) > 300 for v in values):  # 依目前條件選擇下一步處理分支
            raise ValueError('任務需有內容且不超過 300 字')  # 中止目前操作並向呼叫端傳遞錯誤
        return values  # 回傳已通過檢查的值


class PersonCreate(Model):  # 人物基本資料及多角色分類輸入
    name: str = Field(min_length=1, max_length=100)  # 設定顯示稱呼的型別、預設值與輸入限制
    role: str = Field(default='', max_length=100)  # 設定舊版完整角色文字的型別、預設值與輸入限制
    notes: str = Field(default='', max_length=4000)  # 設定自行記錄的備註（不自動轉成事實）的型別、預設值與輸入限制
    roles: List[str] = Field(default_factory=list, max_length=20)  # 設定明確設定的多角色清單的型別、預設值與輸入限制
    tags: List[str] = Field(default_factory=list, max_length=30)  # 設定人物搜尋用標籤清單的型別、預設值與輸入限制
    category: Literal['business', 'life', 'learning', 'other'] = 'other'  # 設定人物主分類的型別、預設值與輸入限制
    followed: bool = False  # 設定使用者是否關注此人物的型別、預設值與輸入限制
    common_context: str = Field(default='', max_length=1000)  # 設定自行記錄的共同場合與交集的型別、預設值與輸入限制

    @field_validator('roles', 'tags')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_labels(cls, values):  # 檢查角色與標籤的內容、長度與去重
        values = [v.strip() for v in values]  # 準備此步驟驗證或搜尋需要的值清單
        if any(not v or len(v) > 100 for v in values):  # 依目前條件選擇下一步處理分支
            raise ValueError('角色與標籤需有內容且不超過 100 字')  # 中止目前操作並向呼叫端傳遞錯誤
        return list(dict.fromkeys(values))  # 回傳檢查角色與標籤的內容、長度與去重的結果


class PersonEdit(Model):  # 只修改明確送出欄位的人物更新輸入
    expected_revision: StrictInt = Field(ge=1)  # 設定修改者已讀取的版本號的型別、預設值與輸入限制
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)  # 設定顯示稱呼的型別、預設值與輸入限制
    roles: Optional[List[str]] = Field(default=None, max_length=20)  # 設定明確設定的多角色清單的型別、預設值與輸入限制
    tags: Optional[List[str]] = Field(default=None, max_length=30)  # 設定人物搜尋用標籤清單的型別、預設值與輸入限制
    category: Optional[Literal['business', 'life', 'learning', 'other']] = None  # 設定人物主分類的型別、預設值與輸入限制
    followed: Optional[bool] = None  # 設定使用者是否關注此人物的型別、預設值與輸入限制
    notes: Optional[str] = Field(default=None, max_length=4000)  # 設定自行記錄的備註（不自動轉成事實）的型別、預設值與輸入限制
    common_context: Optional[str] = Field(default=None, max_length=1000)  # 設定自行記錄的共同場合與交集的型別、預設值與輸入限制

    @field_validator('roles', 'tags')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def valid_labels(cls, values):  # 檢查角色與標籤的內容、長度與去重
        return PersonCreate.valid_labels(values) if values is not None else values  # 回傳檢查角色與標籤的內容、長度與去重的結果

    @model_validator(mode='after')  # 在模型建立後檢查跨欄位限制
    def no_explicit_null(self):  # 區分未送出欄位與不允許的明確空值
        if any(getattr(self, field) is None for field in self.model_fields_set):  # 依目前條件選擇下一步處理分支
            raise ValueError('更新欄位不可為 null')  # 中止目前操作並向呼叫端傳遞錯誤
        return self  # 回傳區分未送出欄位與不允許的明確空值的結果


class FactCreate(Model):  # 附來源與人工確認的人物資訊輸入
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    dimension: Literal['interests', 'food', 'skills', 'habits']  # 設定人物資訊所屬四維度之一的型別、預設值與輸入限制
    value: str = Field(min_length=1, max_length=160)  # 設定人物資訊標籤內容的型別、預設值與輸入限制
    description: str = Field(default='', max_length=2000)  # 設定人物資訊補充說明的型別、預設值與輸入限制
    evidence_type: Literal['stated_by_person', 'observed_by_user', 'documented_source']  # 設定人工確認的證據類型的型別、預設值與輸入限制
    source_experience_ids: List[str] = Field(min_length=1, max_length=30)  # 設定引用的已確認經歷識別碼清單的型別、預設值與輸入限制
    confirmed: Literal[True]  # 設定必須由使用者明確確認的旗標的型別、預設值與輸入限制
    conflicts_with: Optional[str] = None  # 設定使用者指定的衝突資訊識別碼的型別、預設值與輸入限制

    @field_validator('confirmed', mode='before')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def explicit_true(cls, value):  # 拒絕以數字或字串代替使用者明確確認
        if value is not True:  # 依目前條件選擇下一步處理分支
            raise ValueError('請明確確認人物資訊')  # 中止目前操作並向呼叫端傳遞錯誤
        return value  # 回傳已通過檢查的值


class Revision(Model):  # 共用的樂觀鎖版本輸入
    expected_revision: StrictInt = Field(ge=1)  # 設定修改者已讀取的版本號的型別、預設值與輸入限制


class SourceRevoke(Revision):  # 指定撤回來源與預期版本
    experience_id: str = Field(min_length=1, max_length=128)  # 設定已確認經歷識別碼的型別、預設值與輸入限制


class InteractionEdit(Revision):  # 指定互動分類與預期版本
    kind: Literal['in_person', 'call', 'message', 'other', 'unknown']  # 設定互動或私人筆記的分類的型別、預設值與輸入限制


class InteractionMerge(Revision):  # 合併事件並攜帶去重提交代碼
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    source_event_ids: List[str] = Field(min_length=1, max_length=30)  # 設定要合併到主要事件的來源事件識別碼的型別、預設值與輸入限制


class GoalLink(Model):  # 人物與目標的明確關聯輸入
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    goal_id: str = Field(min_length=1, max_length=128)  # 設定關聯目標識別碼的型別、預設值與輸入限制
    label: str = Field(default='', max_length=300)  # 設定關聯說明的型別、預設值與輸入限制


RelationKind = Literal['family', 'partner', 'friend', 'colleague', 'classmate', 'mentor', 'client', 'business', 'neighbor', 'rival', 'enemy', 'other']


class RelationTypeItem(Model):  # 關係類型（010）：本階段只接受 kind；方向與起迄日期尚未開放，多給的欄位會被拒絕
    kind: RelationKind


def distinct_relation_kinds(values):  # 同一段關係的類型不可重複
    if values is not None and len({item.kind for item in values}) != len(values):
        raise ValueError('關係類型不可重複')
    return values


class ConnectionCreate(Model):  # 兩位人物間的明確關係輸入
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    other_person_id: str = Field(min_length=1, max_length=128)  # 設定關係另一端的人物識別碼的型別、預設值與輸入限制
    # 舊格式（只有 label）必填；新格式（帶 relation_types 或 description）可省略，由伺服器用描述的前 300 字填入。
    label: Optional[str] = Field(default=None, min_length=1, max_length=300)
    source_experience_ids: List[str] = Field(default_factory=list, max_length=30)  # 設定引用的已確認經歷識別碼清單的型別、預設值與輸入限制
    # 010：人物經歷來源（關聯表）。None＝沒有提供，維持原值；[]＝清空。Migration 前只接受 None 或 []。
    source_person_experience_ids: Optional[List[str]] = Field(default=None, max_length=30)
    # 010 新格式：關係類型（選填、可複選、最多 10 種）與雙方共用的關係描述。帶其中之一就是新格式：已有關係時回 409，不覆蓋。
    relation_types: Optional[List[RelationTypeItem]] = Field(default=None, max_length=10)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator('relation_types')
    @classmethod
    def distinct_kinds(cls, values):
        return distinct_relation_kinds(values)

    @model_validator(mode='after')
    def legacy_format_needs_label(self):
        if self.relation_types is None and self.description is None and self.label is None:
            raise ValueError('請填寫關係說明')
        return self


class ConnectionPatch(Model):  # 010：編輯、封存或恢復既有關係（Migration 010 後開放）
    request_id: str = Field(min_length=1, max_length=128)  # 重送去重用的提交代碼
    expected_revision: StrictInt = Field(ge=1)  # 修改者讀到的關係版本；不符回 409 stale_revision
    label: Optional[str] = Field(default=None, min_length=1, max_length=300)  # 舊欄位；未提供就維持原值
    source_experience_ids: Optional[List[str]] = Field(default=None, max_length=30)  # None＝維持；[]＝清空；陣列＝依順序替換
    source_person_experience_ids: Optional[List[str]] = Field(default=None, max_length=30)  # 同上，人物經歷來源
    relation_types: Optional[List[RelationTypeItem]] = Field(default=None, max_length=10)  # None＝維持；陣列＝替換（只處理 kind）
    description: Optional[str] = Field(default=None, max_length=2000)  # 雙方共用的關係描述；None＝維持
    confirmation_status: Optional[Literal['archived', 'confirmed']] = None  # archived＝封存；confirmed＝恢復（或確認）

    @field_validator('relation_types')
    @classmethod
    def distinct_kinds(cls, values):
        return distinct_relation_kinds(values)


class Complete(Model):  # 附佐證與人工確認的目標完成輸入
    expected_revision: Optional[StrictInt] = Field(default=None, ge=1)  # 新版頁面檢查目標版本，舊請求仍可重試。
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    evidence_ids: List[str] = Field(min_length=1, max_length=10)  # 設定完成目標所引用的佐證識別碼的型別、預設值與輸入限制
    confirmed: Literal[True]  # 設定必須由使用者明確確認的旗標的型別、預設值與輸入限制
    reflection: str = Field(default='', max_length=4000)  # 設定目標完成感想的型別、預設值與輸入限制

    @field_validator('confirmed', mode='before')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def explicit_true(cls, value):  # 拒絕以數字或字串代替使用者明確確認
        if value is not True:  # 依目前條件選擇下一步處理分支
            raise ValueError('必須由使用者明確確認成果')  # 中止目前操作並向呼叫端傳遞錯誤
        return value  # 回傳已通過檢查的值

    @field_validator('evidence_ids')  # 將下方驗證函式綁定到指定輸入欄位
    @classmethod  # 以模型類別呼叫欄位驗證
    def distinct_evidence(cls, values):  # 驗證佐證識別碼有效且不重複
        if len(values) != len(set(values)) or any(not v or len(v) > 128 for v in values):  # 依目前條件選擇下一步處理分支
            raise ValueError('佐證 ID 必須有效且不重複')  # 中止目前操作並向呼叫端傳遞錯誤
        return values  # 回傳已通過檢查的值


class NoteCreate(Model):  # 私人筆記與引用來源輸入
    person_id: Optional[str] = None  # 設定關聯人物識別碼的型別、預設值與輸入限制
    kind: Literal['preparation', 'simulation', 'message']  # 設定互動或私人筆記的分類的型別、預設值與輸入限制
    title: str = Field(min_length=1, max_length=160)  # 設定標題的型別、預設值與輸入限制
    content: str = Field(min_length=1, max_length=20000)  # 設定私人筆記內容的型別、預設值與輸入限制
    source_experience_ids: List[str] = Field(default_factory=list, max_length=30)  # 設定引用的已確認經歷識別碼清單的型別、預設值與輸入限制


class TaskEdit(Model):  # 只更新待辦勾選狀態的輸入
    done: bool  # 設定待辦完成狀態（不代表行動貢獻）的型別、預設值與輸入限制


class StoryPeopleEdit(Revision):  # 版本化更正人物，不重新發放經歷積分
    request_id: str = Field(min_length=1, max_length=128)  # 重送去重識別碼
    story: StoryInput  # 使用者核對後的人物清單
    confirmed: Literal[True]  # 明確接受整份整理

    @field_validator('confirmed', mode='before')  # 拒絕數字等模糊確認
    @classmethod  # 由模型呼叫驗證
    def explicit_true(cls, value):  # 必須是 JSON true
        return FactCreate.explicit_true(value)  # 沿用既有明確確認規則


class MentionMatch(Revision):  # 只核對身分，不改參與角色
    request_id: str = Field(min_length=1, max_length=128)  # 配對的重送識別碼
    status: Literal['matched', 'unmatched', 'rejected']  # 允許確認、取消與拒絕
    person_id: Optional[str] = Field(default=None, min_length=1, max_length=128)  # 可留待核對
    confirmed: Literal[True]  # 使用者明確核對身分

    @field_validator('confirmed', mode='before')  # 使用相同的真值限制
    @classmethod  # 由模型呼叫驗證
    def explicit_true(cls, value):  # 不接受隱式型別轉換
        return FactCreate.explicit_true(value)  # 沿用人工確認驗證

    @model_validator(mode='after')  # 檢查配對狀態與人物的一致性
    def matching_person(self):  # 只有已配對狀態需要人物
        if (self.status == 'matched') != (self.person_id is not None):  # 拒絕矛盾的狀態
            raise ValueError('配對狀態與人物不一致')  # 保留原名待核對，不猜測
        return self  # 回傳一致配對內容


class StoryAvailability(Revision):  # 撤回或恢復交會展示
    request_id: str = Field(min_length=1, max_length=128)  # 保存可重送操作
    available: bool = Field(strict=True)  # 不刪除原始經歷


class HabitSchedule(Model):  # 依穩定行動 ID 更新安排，不重建歷史。
    action_id: str = Field(min_length=1, max_length=128)  # 必須屬於同一目標。
    dates: List[date] = Field(min_length=1, max_length=10000)  # 明確檢視的新安排。
    weekdays: List[StrictInt] = Field(default_factory=list, max_length=7)  # 保存星期快選。
    cycle: Literal['month', 'week'] = 'month'  # 保存編輯週期。
    title: Optional[str] = Field(default=None, min_length=1, max_length=160)
    per_occurrence: Optional[str] = None
    expected_effective_from: Optional[date] = None

    @field_validator('per_occurrence', mode='before')
    @classmethod
    def valid_planned_quantity(cls, value):
        """只接受正數；缺省表示保留原標準，不接受明確的 null。"""
        return decimal_string(value)


class GoalReview(Model):  # 延長、結束與設定的明確確認。
    request_id: str = Field(min_length=1, max_length=128)  # 防止重送。
    expected_revision: StrictInt = Field(ge=1)  # 防止舊頁面覆蓋。
    decision: Literal['extend', 'end', 'setup', 'schedule']  # 成果完成仍沿用 complete。
    confirmed: Literal[True]  # 使用者明確確認。
    deadline: Optional[date] = None  # 延長與舊目標設定需提供。
    schedules: Optional[List[HabitSchedule]] = Field(default=None, min_length=3, max_length=3)  # 同時檢視三個習慣。
    reflection: str = Field(default='', max_length=4000)  # 保存回顧感想。

    @field_validator('confirmed', mode='before')  # 拒絕隱式轉型。
    @classmethod  # 使用類別驗證。
    def explicit_confirm(cls, value):  # 只有布林 True 代表確認。
        if value is not True: raise ValueError('請明確確認本次操作')  # 不接受數字代替。
        return value  # 回傳確認旗標。


class PendingAccept(Model):  # 延長後逐筆核對採計。
    request_id: str = Field(min_length=1, max_length=128)  # 避免重複入帳。
    expected_revision: StrictInt = Field(ge=1)  # 使用最新版本。
    quantity: str  # 核對後的實際數量。
    confirmed: Literal[True]  # 明確採計確認。

    @field_validator('quantity', mode='before')  # 沿用精確正數規則。
    @classmethod  # 使用類別驗證。
    def valid_quantity(cls, value):  # 驗證合法數量。
        return decimal_string(value)  # 保留原有精度上限。

    @field_validator('confirmed', mode='before')  # 不允許隱式確認。
    @classmethod  # 使用類別驗證。
    def explicit_confirm(cls, value):  # 只接受布林 True。
        if value is not True: raise ValueError('請明確確認採計')  # 防止數字轉型。
        return value  # 回傳確認旗標。


class GoogleChallenge(Model):
    """登入前明確選擇是否保存Guest；未知欄位拒絕。"""
    mode: Literal['login','upgrade']
    discard_guest: bool = False


class GoogleExchange(Model):
    """ID token僅作交換，不接受前端自報owner/email。"""
    challenge_id: str = Field(pattern=r'^[0-9a-f-]{36}$')
    credential: str = Field(min_length=1,max_length=16384)


class GoogleExchangeStatus(Model):
    """只核對已驗證Session的交換收據，不接收token或自報owner。"""
    challenge_id: str = Field(pattern=r'^[0-9a-f-]{36}$')


# 選取Jerry Schema010資料DTO；不引入新AI/作品入口。
class PersonsCreate(Model):  # 新人物系統的新增輸入：類型與分類全部選填，同名可並存
    request_id: str = Field(min_length=1, max_length=128)  # 重送去重用的提交代碼
    name: str = Field(min_length=1, max_length=100)
    aliases: List[str] = Field(default_factory=list, max_length=20)  # 別名（010 people.aliases，最多 20 個）
    person_type: Optional[Literal['real', 'fictional']] = None  # 未指定時用 Schema 010 預設 real
    person_subtype: Optional[Literal['historical', 'original']] = None  # historical 屬 real；original 屬 fictional
    description: str = Field(default='', max_length=2000)  # 人物簡介（010 people.description）
    roles: List[str] = Field(default_factory=list, max_length=20)
    tags: List[str] = Field(default_factory=list, max_length=30)
    category: Literal['business', 'life', 'learning', 'other'] = 'other'
    # 承接舊人物主檔欄位（2.0 P2）：people.notes 是人物備註，和 notes 資料表（人物設定版本）不同。
    notes: str = Field(default='', max_length=4000)
    common_context: str = Field(default='', max_length=1000)
    followed: bool = False
    profile: Optional['PersonProfileFields'] = None  # 單頁一次儲存：同一交易建立第 1 版人物設定（全部空白則不建立）

    @field_validator('aliases', 'roles', 'tags')
    @classmethod
    def valid_labels(cls, values):  # 去空白、去重、每項 1～100 字
        return PersonCreate.valid_labels(values)


class PersonsEdit(Model):  # 只修改明確送出的欄位；person_subtype 可送 null 清空，其他欄位不可為 null
    expected_revision: StrictInt = Field(ge=1)
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    aliases: Optional[List[str]] = Field(default=None, max_length=20)
    person_type: Optional[Literal['real', 'fictional']] = None
    person_subtype: Optional[Literal['historical', 'original']] = None
    description: Optional[str] = Field(default=None, max_length=2000)
    roles: Optional[List[str]] = Field(default=None, max_length=20)
    tags: Optional[List[str]] = Field(default=None, max_length=30)
    category: Optional[Literal['business', 'life', 'learning', 'other']] = None
    notes: Optional[str] = Field(default=None, max_length=4000)  # 承接舊人物主檔欄位
    common_context: Optional[str] = Field(default=None, max_length=1000)
    followed: Optional[bool] = None

    @field_validator('aliases', 'roles', 'tags')
    @classmethod
    def valid_labels(cls, values):
        return PersonCreate.valid_labels(values) if values is not None else values

    @model_validator(mode='after')
    def no_explicit_null(self):
        if any(getattr(self, field) is None for field in self.model_fields_set if field != 'person_subtype'):
            raise ValueError('更新欄位不可為 null')
        return self


class PersonsStatus(Model):  # 封存或恢復人物（不刪除）
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    status: Literal['active', 'archived']


class PersonProfileFields(Model):  # 人物設定欄位（取代原 AI 角色卡的設定欄位）；未送出的欄位視為空白
    background: str = Field(default='', max_length=3000)  # 背景
    personality: str = Field(default='', max_length=2000)  # 性格
    motivation: str = Field(default='', max_length=1500)  # 動機
    stance: str = Field(default='', max_length=1500)  # 立場
    abilities: str = Field(default='', max_length=1500)  # 能力
    expression: str = Field(default='', max_length=2000)  # 表達方式（2026-11-11 放寬：完整的說話方式加示範台詞約 1500 字）
    behavior: str = Field(default='', max_length=2000)  # 行為
    knowledge_boundary: str = Field(default='', max_length=1000)  # 知識界線
    restrictions: str = Field(default='', max_length=1500)  # 禁止事項及其他限制


class PersonProfileSave(Model):  # 保存一版人物設定（只新增；expected_profile_id 是目前最新版，第一次為 null）
    request_id: str = Field(min_length=1, max_length=128)
    expected_profile_id: Optional[str] = Field(default=None, min_length=1, max_length=128)
    fields: PersonProfileFields
    origin: Literal['manual', 'ai', 'ai_edited'] = 'manual'  # 第三階段：AI 產生或 AI 產生後修改
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)  # origin 為 ai／ai_edited 時必填

    @model_validator(mode='after')
    def generation_matches_origin(self):
        if (self.origin == 'manual') != (self.generation_id is None):
            raise ValueError('AI 產生的設定必須附上生成紀錄；人工填寫不可附生成紀錄')
        return self


class PersonExperienceCreate(Model):  # 人物經歷（人物自己的經歷，使用者不必參與）；建立者就是登入帳號，不另外填
    request_id: str = Field(min_length=1, max_length=128)  # 重送去重用的提交代碼
    subject_person_id: str = Field(min_length=1, max_length=128)  # 經歷主體：這筆經歷主要屬於誰
    participant_ids: List[str] = Field(default_factory=list, max_length=50)  # 其他參與人物（選填，最多 50 位）
    title: str = Field(default='', max_length=200)  # 選填；空白時畫面顯示內容開頭
    content: str = Field(min_length=1, max_length=20000)
    experience_type: Literal['real', 'historical', 'fictional']  # 性質：建立後不能更改（資料庫權限）
    occurred_precision: Literal['unknown', 'year', 'month', 'day'] = 'unknown'  # 發生時間的精度；unknown＝不知道
    occurred_on: Optional[str] = Field(default=None, max_length=10)  # 依精度：'208'、'208-12'、'208-12-01'；格式由服務層檢查
    occurred_label: str = Field(default='', max_length=120)  # 時間描述，例如「建安十三年冬」

    @model_validator(mode='after')
    def distinct_people(self):
        if len(set(self.participant_ids)) != len(self.participant_ids) or self.subject_person_id in self.participant_ids:
            raise ValueError('參與人物不可重複，也不必包含主體人物')
        return self


class PersonExperiencePatch(Model):  # 編輯、封存或恢復人物經歷；未送出（或 null）的欄位維持原值。性質與主體不能改
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)  # 修改者讀到的版本；不符回 409 stale_revision
    title: Optional[str] = Field(default=None, max_length=200)
    content: Optional[str] = Field(default=None, min_length=1, max_length=20000)
    occurred_precision: Optional[Literal['unknown', 'year', 'month', 'day']] = None  # 修改時間時必填；unknown＝改成不知道
    occurred_on: Optional[str] = Field(default=None, max_length=10)
    occurred_label: Optional[str] = Field(default=None, max_length=120)
    participant_ids: Optional[List[str]] = Field(default=None, max_length=50)  # 送出時整份替換；[]＝清空
    status: Optional[Literal['active', 'archived']] = None  # archived＝封存；active＝恢復

    @field_validator('participant_ids')
    @classmethod
    def distinct_participants(cls, values):
        if values is not None and len(set(values)) != len(values):
            raise ValueError('參與人物不可重複')
        return values


PersonsCreate.model_rebuild()
