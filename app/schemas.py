from datetime import datetime  # 處理 UTC、發生時間與期限
from decimal import Decimal, InvalidOperation  # 以精確十進位處理貢獻量，避免浮點誤差
from typing import List, Optional, Literal  # 宣告可選欄位、清單與受限字串型別
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # 使用 IANA 時區轉換日期與時間

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator  # 定義輸入模型、型別、長度與跨欄位驗證


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
    unit: str = Field(min_length=1, max_length=20)  # 設定行動計量單位的型別、預設值與輸入限制
    target: str  # 設定行動預期累計值的型別、預設值與輸入限制
    level: StrictInt = Field(ge=1, le=3)  # 設定建立時的養分等級的型別、預設值與輸入限制
    weekdays: List[StrictInt] = Field(min_length=1, max_length=7)  # 設定每週預計執行日（週一為 0）的型別、預設值與輸入限制

    @field_validator('target', mode='before')  # 將下方驗證函式綁定到指定輸入欄位
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
    actions: List[Action] = Field(min_length=3, max_length=3)  # 設定三項可自主完成的目標行動的型別、預設值與輸入限制


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


class StoryInput(Model):  # 草稿與正式人物核對共用資料
    title: str = Field(default='', max_length=160)  # 可另取故事標題
    participants: List[StoryParticipant] = Field(default_factory=list, max_length=100)  # 每筆經歷最多一百位參與者
    mentions: List[StoryMention] = Field(default_factory=list, max_length=100)  # 每個原文位置獨立配對

    @model_validator(mode='after')  # 驗證跨項目的唯一性
    def distinct_links(self):  # 拒絕重複人物與重複提及位置
        ids = [p.person_id for p in self.participants]  # 取得固定人物識別碼
        spans = [(m.start, m.end) for m in self.mentions]  # 取得原文範圍
        if len(ids) != len(set(ids)) or len(spans) != len(set(spans)):  # 重複輸入不能默默覆寫
            raise ValueError('參與者與提及位置不可重複')  # 讓介面要求人工修正
        return self  # 回傳唯一且合法的角色資料


class DraftCreate(WithContributions):  # 尚未確認的原始經歷輸入
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


class Confirm(WithContributions):  # 將草稿正式確認為經歷的輸入
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


class ConnectionCreate(Model):  # 兩位人物間的明確關係輸入
    request_id: str = Field(min_length=1, max_length=128)  # 設定重送去重用的提交代碼的型別、預設值與輸入限制
    other_person_id: str = Field(min_length=1, max_length=128)  # 設定關係另一端的人物識別碼的型別、預設值與輸入限制
    label: str = Field(min_length=1, max_length=300)  # 設定關聯說明的型別、預設值與輸入限制
    source_experience_ids: List[str] = Field(default_factory=list, max_length=30)  # 設定引用的已確認經歷識別碼清單的型別、預設值與輸入限制


class Complete(Model):  # 附佐證與人工確認的目標完成輸入
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
