# 2026-11-10 自 8445 的 app/schemas.py 原樣移植，供生成模組使用；B 原有的 app/schemas.py 不變。
from datetime import date, datetime  # 處理 UTC、實際日期與期限。
from decimal import Decimal, InvalidOperation  # 以精確十進位處理貢獻量，避免浮點誤差
from typing import List, Optional, Literal  # 宣告可選欄位、清單與受限字串型別
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # 使用 IANA 時區轉換日期與時間

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_serializer, model_validator  # 定義輸入模型、型別、長度與跨欄位驗證


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


# ---- S1：AI 角色卡與私人作品（只接受玩家明確輸入的虛構／職務角色設定，不讀取真人資料） ----
from typing import Annotated, Union  # 為清單元素設定長度限制；依模組／作品種類選擇內容結構
import unicodedata  # F04 字面重複檢查：統一字寬／組合字，不讓格式控制字元偽裝成不同策略

CardLine = Annotated[str, Field(min_length=1, max_length=120)]  # 單項限制或禁止事項
SampleLine = Annotated[str, Field(min_length=1, max_length=200)]  # 單句示範台詞


class CharacterCardInput(Model):  # 角色卡生成輸入；historical 延後，不在本批開放
    name: str = Field(min_length=1, max_length=60)  # 角色名稱
    kind: Literal['fictional', 'role']  # 原創虛構角色或職務角色
    background: str = Field(default='', max_length=1500)  # 背景
    personality: str = Field(default='', max_length=600)  # 個性
    motivation: str = Field(default='', max_length=600)  # 動機
    stance: str = Field(default='', max_length=600)  # 立場
    voice: str = Field(default='', max_length=400)  # 語氣
    knowledge_boundary: str = Field(default='', max_length=600)  # 知識界線
    restrictions: str = Field(default='', max_length=600)  # 禁止事項或其他明確限制


class CharacterCardDraft(Model):  # AI 角色卡候選：維持 character-card-v1 的 11 個欄位與上限（Prompt 與結構雜湊不變）
    name: str = Field(min_length=1, max_length=60)
    kind: Literal['fictional', 'role']
    tagline: str = Field(default='', max_length=120)  # 一句話概念
    background: str = Field(default='', max_length=1500)
    personality: str = Field(default='', max_length=600)
    motivation: str = Field(default='', max_length=600)
    stance: str = Field(default='', max_length=600)
    voice: str = Field(default='', max_length=400)
    knowledge_boundary: str = Field(default='', max_length=600)
    restrictions: List[CardLine] = Field(default_factory=list, max_length=8)
    sample_lines: List[SampleLine] = Field(default_factory=list, max_length=3)


# 角色管理中心（2026-11-08）：角色卡是使用者主觀設定的「演員設定」，不是人物百科；忠於設定，不要求貼近真實。
# 11 個舊欄位全部保留（舊版本照常可讀）；新增欄位都是選填。來源參照與肖像由伺服器設定，編輯時不能更換。
CARD_INSPIRATIONS = ('original', 'anime', 'wuxia', 'history', 'real_person', 'role', 'mixed')  # 靈感來源（可複選，供篩選）
CardSampleLine = Annotated[str, Field(min_length=1, max_length=400)]  # 範例台詞（人物演繹轉入時含情境，放寬長度避免截斷）
CardTag = Annotated[str, Field(min_length=1, max_length=20)]


class CardSourceRef(Model):  # 角色卡的來源參照；只由伺服器在複製／轉入時寫入
    kind: Literal['system_character', 'character_card', 'person_portrayal']
    id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=20)  # 系統角色為目錄版本（如 1.0.0）；作品為版本號字串
    name: str = Field(min_length=1, max_length=60)  # 當時名稱
    ai_inferred: bool = False  # 人物演繹轉入：內容來自 AI 推論，不是真人事實
    snapshot_sha256: Optional[str] = Field(default=None, max_length=64)  # 人物演繹的來源快照雜湊
    generation_id: Optional[str] = Field(default=None, max_length=128)  # 人物演繹的原始生成紀錄
    acknowledged_at: Optional[str] = Field(default=None, max_length=40)  # 使用者確認本次轉入用途的時間
    note: str = Field(default='', max_length=200)


class CharacterCardContent(Model):  # 角色卡作品內容（AI 候選與人工稿共用同一結構）
    name: str = Field(min_length=1, max_length=60)
    kind: Literal['fictional', 'role']  # 相容舊資料；分類改由 inspirations 與來源參照表達
    tagline: str = Field(default='', max_length=400)  # 一句話設定／角色摘要
    background: str = Field(default='', max_length=3000)
    personality: str = Field(default='', max_length=2000)
    motivation: str = Field(default='', max_length=1500)
    stance: str = Field(default='', max_length=1500)  # 立場（與價值觀不同，保留原欄位）
    voice: str = Field(default='', max_length=600)  # 說話方式
    knowledge_boundary: str = Field(default='', max_length=1000)
    restrictions: List[CardLine] = Field(default_factory=list, max_length=8)
    sample_lines: List[CardSampleLine] = Field(default_factory=list, max_length=3)
    values: str = Field(default='', max_length=1500)  # 價值觀（選填）
    behavior: str = Field(default='', max_length=2000)  # 行為模式與情緒反應（選填）
    appearance: str = Field(default='', max_length=1000)  # 外觀（選填）
    inspirations: List[Literal[CARD_INSPIRATIONS]] = Field(default_factory=list, max_length=7)
    tags: List[CardTag] = Field(default_factory=list, max_length=12)
    image_ref: Optional[str] = Field(default=None, max_length=80)  # 系統肖像 ID；使用者角色目前沒有上傳圖片
    source_references: List[CardSourceRef] = Field(default_factory=list, max_length=6)

    @model_validator(mode='after')
    def distinct_labels(self):  # 標籤與靈感不重複，避免篩選結果重複計數
        if len(set(self.inspirations)) != len(self.inspirations) or len(set(self.tags)) != len(self.tags):
            raise ValueError('標籤不可重複')
        return self


# ---- 角色管理中心：複製、刪除、人物演繹轉入 ----
class CharacterCopy(Model):  # 複製系統範例或自己的角色卡版本，建立獨立的新角色卡
    request_id: str = Field(min_length=1, max_length=128)
    source_kind: Literal['system', 'card']
    source_id: str = Field(min_length=1, max_length=128)
    source_version: str = Field(min_length=1, max_length=20)


class CharacterDelete(Model):  # 真正刪除；有任何引用時拒絕
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)


PORTRAYAL_SECTIONS = ('summary', 'traits', 'motivations', 'values', 'speaking_style', 'behaviors', 'emotional_reactions',
                      'knowledge_boundary', 'sample_dialogues')


class PortrayalToCard(Model):  # F06A 人物演繹結果轉為角色卡；只轉入使用者勾選的段落
    request_id: str = Field(min_length=1, max_length=128)
    portrayal_work_id: str = Field(min_length=1, max_length=128)
    version_no: StrictInt = Field(ge=1)
    sections: List[Literal[PORTRAYAL_SECTIONS]] = Field(min_length=1, max_length=9)
    acknowledged: Literal[True]  # 使用者確認本次轉入的資料用途；不代表真人本人同意


# ---- 人物劇場：選角設定（固定版本）與多角色演出 ----
THEATER_POSITIONS = ('protagonist', 'opponent', 'advisor', 'supporting')


class TheaterCastMember(Model):
    source: Literal['system', 'card']
    id: str = Field(min_length=1, max_length=128)  # 系統角色 ID 或角色卡作品 ID
    version: str = Field(min_length=1, max_length=20)  # 固定版本：系統目錄版本或角色卡版本號
    name: str = Field(min_length=1, max_length=60)
    position: Literal[THEATER_POSITIONS]


class TheaterScenario(Model):
    text: str = Field(min_length=1, max_length=800)  # 情境（可自由輸入，或由系統範例場景帶入後修改）
    preset_id: Optional[str] = Field(default=None, max_length=80)


class TheaterCastContent(Model):  # 演出設定：場景、陣容、固定版本、演出位置與演出要求
    title: str = Field(min_length=1, max_length=60)
    scenario: TheaterScenario
    mode: Literal['faithful', 'free']  # 貼近我的設定／自由改編
    direction: str = Field(default='', max_length=600)  # 演出要求
    cast: List[TheaterCastMember] = Field(min_length=2, max_length=4)

    @model_validator(mode='after')
    def distinct_cast(self):
        keys = [(member.source, member.id) for member in self.cast]
        if len(set(keys)) != len(keys):
            raise ValueError('同一個角色不能重複上場')
        return self


class CastRef(Model):
    work_id: str = Field(min_length=1, max_length=128)
    version_no: StrictInt = Field(ge=1)


class PerformanceLine(Model):
    cast_index: Optional[StrictInt] = Field(default=None, ge=0, le=3)  # None 為旁白
    speaker: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=300)


class TheaterPerformanceContent(Model):  # 多角色演出成果；只能原樣保存一次成功生成的結果
    title: str = Field(min_length=1, max_length=60)
    cast_ref: CastRef
    cast: List[TheaterCastMember] = Field(min_length=2, max_length=4)
    scenario: TheaterScenario
    mode: Literal['faithful', 'free']
    direction: str = Field(default='', max_length=600)
    lines: List[PerformanceLine] = Field(min_length=6, max_length=12)
    notes: str = Field(default='', max_length=200)


class TheaterPerformanceInput(Model):  # 生成輸入只帶演出設定的作品與版本；角色內容由伺服器讀取
    cast_work_id: str = Field(min_length=1, max_length=128)
    cast_version: StrictInt = Field(ge=1)


# ---- F04：故事開場（只接受玩家輸入的虛構情境；角色卡由伺服器依 owner 讀取指定版本） ----
class StoryOpeningInput(Model):  # 生成故事開場的輸入；角色卡內容不由前端提供
    character_work_id: str = Field(min_length=1, max_length=128)  # 已保存的角色卡作品
    character_version: StrictInt = Field(ge=1)  # 固定版本，生成期間不換成最新版
    genre: str = Field(min_length=1, max_length=40)  # 故事類型
    setting: str = Field(min_length=1, max_length=800)  # 場景描述
    conflict: str = Field(min_length=1, max_length=800)  # 當前衝突
    player_goal: str = Field(min_length=1, max_length=600)  # 玩家目標
    constraints: str = Field(default='', max_length=600)  # 其他限制（選填）


class StoryChoice(Model):  # 一個起始行動；三個選項必須是不同策略
    label: str = Field(min_length=1, max_length=40)
    strategy: str = Field(min_length=1, max_length=20)  # 例如談判、調查、冒險
    description: str = Field(min_length=1, max_length=300)


class StorySource(Model):  # 故事開場引用的角色卡版本（同一作品固定不變）
    character_work_id: str = Field(min_length=1, max_length=128)
    character_version: StrictInt = Field(ge=1)
    character_name: str = Field(min_length=1, max_length=60)


class StoryBrief(Model):  # 當次生成使用的故事設定，供追溯與重新生成
    genre: str = Field(min_length=1, max_length=40)
    setting: str = Field(min_length=1, max_length=800)
    conflict: str = Field(min_length=1, max_length=800)
    player_goal: str = Field(min_length=1, max_length=600)
    constraints: str = Field(default='', max_length=600)


class StoryOpeningContent(Model):  # 故事開場作品內容（AI 候選與人工稿共用同一結構）
    title: str = Field(min_length=1, max_length=80)
    opening: str = Field(min_length=1, max_length=2000)
    objective: str = Field(min_length=1, max_length=400)
    conflict: str = Field(min_length=1, max_length=600)
    choices: List[StoryChoice] = Field(min_length=3, max_length=3)
    narrative_notes: str = Field(default='', max_length=600)
    source: StorySource
    brief: StoryBrief

    @model_validator(mode='after')
    def distinct_choices(self):  # 只拒絕正規化後的字面重複；不宣稱能辨識同義策略
        def key(value):
            normalized = unicodedata.normalize('NFKC', value).casefold()
            return ''.join(ch for ch in normalized if not ch.isspace() and unicodedata.category(ch) != 'Cf')
        strategies = {key(c.strategy) for c in self.choices}
        labels = {key(c.label) for c in self.choices}
        if '' in strategies or '' in labels or len(strategies) != 3 or len(labels) != 3:
            raise ValueError('三個選項必須是不同策略與不同行動')
        return self


# ---- F05-A：短篇文字互動（每回合 module=character_reply；互動紀錄是私人作品 kind=story_session） ----
SESSION_MAX_TURNS = 5  # 首版短篇：最多 5 個玩家決策回合


def literal_choice_key(value):  # 與 F04 distinct_choices 相同的字面正規化；只拒絕字面重複，不判斷同義策略
    normalized = unicodedata.normalize('NFKC', value).casefold()
    return ''.join(ch for ch in normalized if not ch.isspace() and unicodedata.category(ch) != 'Cf')


def require_distinct_choices(choices):  # 三個下一步行動必須是不同策略、不同名稱
    strategies = {literal_choice_key(c.strategy) for c in choices}
    labels = {literal_choice_key(c.label) for c in choices}
    if '' in strategies or '' in labels or len(strategies) != len(choices) or len(labels) != len(choices):
        raise ValueError('三個選項必須是不同策略與不同行動')


class ActionInput(Model):  # 玩家本回合行動：選項只送編號（名稱由伺服器依上一回合帶入），自由輸入送原文
    kind: Literal['choice', 'free']
    choice_index: Optional[StrictInt] = Field(default=None, ge=0, le=2)
    text: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def action_shape(self):  # 兩種行動的欄位互斥，避免以選項夾帶任意文字
        if self.kind == 'choice' and (self.choice_index is None or self.text):
            raise ValueError('選擇預設行動時只送選項編號')
        if self.kind == 'free' and (self.choice_index is not None or not self.text):
            raise ValueError('自由行動需要輸入文字')
        return self


class CharacterReplyInput(Model):  # 生成一回合角色回應；故事、角色卡與劇情歷史都由伺服器依 owner 讀取
    session_work_id: str = Field(min_length=1, max_length=128)
    session_version: StrictInt = Field(ge=1)  # 本回合依據的互動紀錄版本，必須是目前版本
    turn_no: StrictInt = Field(ge=1, le=SESSION_MAX_TURNS)
    action: ActionInput


class ReplyContent(Model):  # Provider 輸出：角色台詞、場景變化與下一步三個選項
    npc_line: str = Field(min_length=1, max_length=400)
    scene: str = Field(min_length=1, max_length=600)
    choices: List[StoryChoice] = Field(min_length=3, max_length=3)
    narrative_notes: str = Field(default='', max_length=300)  # 虛構／推測／史實提示

    @model_validator(mode='after')
    def distinct_choices(self):
        require_distinct_choices(self.choices)
        return self


# ---- F05D：character-reply-v2 行動結算（Action Contract） ----
def _has_action_text(value):
    """格式控制字、其他控制字及空白不能單獨充當原因或效果。"""
    return any(ch.isprintable() and not ch.isspace() for ch in value)


class ActionResolution(Model):  # 模型對玩家本回合行動的結算；受阻或改變時必須說明原因
    status: Literal['executed', 'blocked', 'modified']
    reason: str = Field(max_length=200)  # Provider Schema 要求欄位存在，executed 可為空字串。

    @model_validator(mode='after')
    def reason_required(self):  # 不允許無理由地讓玩家行動失敗或變形
        if self.status != 'executed' and not _has_action_text(self.reason):
            raise ValueError('行動受阻或改變時必須說明原因')
        return self


class ReplyContentV2(ReplyContent):  # character-reply-v2 的 Provider 輸出：v1 欄位＋行動結算與實際效果
    action_resolution: ActionResolution
    action_effect: str = Field(min_length=1, max_length=300)  # 玩家行動實際造成的結果

    @field_validator('action_effect')
    @classmethod
    def visible_action_effect(cls, value):
        if not _has_action_text(value):
            raise ValueError('行動效果必須包含可見文字')
        return value


class ActionResolutionV3(ActionResolution):  # F05D-2 v3：另外明寫玩家自己的動作；reason 是外部原因
    player_action: str = Field(min_length=1, max_length=200)

    @field_validator('player_action')
    @classmethod
    def visible_player_action(cls, value):
        if not _has_action_text(value):
            raise ValueError('玩家行動必須包含可見文字')
        return value


class ReplyContentV3(ReplyContentV2):  # character-reply-v3 的 Provider 輸出：玩家動作、外部原因與世界效果分開
    action_resolution: ActionResolutionV3


class TurnAction(Model):  # 保存在回合中的行動（選項已帶入名稱與策略）
    kind: Literal['choice', 'free']
    choice_index: Optional[StrictInt] = Field(default=None, ge=0, le=2)
    text: str = Field(min_length=1, max_length=300)
    strategy: str = Field(default='', max_length=20)


class SessionTurn(ReplyContent):  # 一個已確認的回合：玩家行動＋原樣保存的角色回應＋生成紀錄
    turn_no: StrictInt = Field(ge=1, le=SESSION_MAX_TURNS)
    action: TurnAction
    generation_id: str = Field(min_length=1, max_length=128)
    provider_kind: Literal['fake', 'live']  # fake 即測試用假回應，畫面必須標示
    # F05D：character-reply-v2 的回合才有行動結算；v1 回合沒有這兩個欄位，序列化時也不得補上 null。
    action_resolution: Optional[Union[ActionResolutionV3, ActionResolution]] = None  # v3 有 player_action；v2 沒有
    action_effect: Optional[str] = Field(default=None, min_length=1, max_length=300)

    @model_serializer(mode='wrap')
    def omit_absent_v2_fields(self, handler) -> dict:  # 舊回合輸出必須與保存的 JSON 完全相同，逐回合比對才不會失敗
        data = handler(self)
        for key in ('action_resolution', 'action_effect'):
            if data.get(key) is None:
                data.pop(key, None)
        return data


class SessionStory(Model):  # 開始冒險時固定的故事開場版本
    work_id: str = Field(min_length=1, max_length=128)
    version_no: StrictInt = Field(ge=1)
    title: str = Field(min_length=1, max_length=80)


class SessionCharacter(Model):  # 該故事版本引用的角色卡版本
    work_id: str = Field(min_length=1, max_length=128)
    version_no: StrictInt = Field(ge=1)
    name: str = Field(min_length=1, max_length=60)


class StorySessionContent(Model):  # 互動紀錄內容；每個版本都是完整快照，伺服器只允許逐回合追加或由玩家結束
    title: str = Field(min_length=1, max_length=80)
    story: SessionStory
    character: SessionCharacter
    objective: str = Field(min_length=1, max_length=400)  # 故事原本的目標，全程顯示
    status: Literal['active', 'ended']
    ending: Optional[Literal['player_ended', 'turn_limit']] = None
    turns: List[SessionTurn] = Field(default_factory=list, max_length=SESSION_MAX_TURNS)

    @model_validator(mode='after')
    def consistent_turns(self):  # 回合連續編號；結束狀態與原因一致（其餘轉換規則由服務層依目前版本判斷）
        if [turn.turn_no for turn in self.turns] != list(range(1, len(self.turns) + 1)):
            raise ValueError('回合編號必須從 1 連續遞增')
        if (self.status == 'ended') != (self.ending is not None):
            raise ValueError('結束狀態與結束原因不一致')
        return self


# ---- F06A：AI 真人角色演繹（person_portrayal）與互動試演（portrayal_reply） ----
# 真實人物資料只由伺服器依 owner 讀取；前端只送 ID。AI 輸出是「推演」，與來源資料分開保存。
PORTRAYAL_FIELDS = ('roles', 'tags', 'category', 'common_context', 'notes')  # 可選取的人物主檔欄位（使用者自己記錄的描述）
PortrayalRef = Annotated[str, Field(pattern=r'^[fnp][0-9]{1,2}$')]  # 送給模型的短代號：f＝已確認事實、n＝人物筆記、p＝主檔欄位
PortrayalId = Annotated[str, Field(min_length=1, max_length=128)]
PORTRAYAL_MAX_TURNS = 6  # 互動試演最多 6 個來回（至少 3 個）
PORTRAYAL_SCENARIOS = ('advice', 'conflict', 'business', 'daily', 'memory', 'custom')


def _unique(values):
    if len(set(values)) != len(values):
        raise ValueError('選取的項目不可重複')
    return values


class PortrayalSelection(Model):  # 使用者明確選取、要送給 AI 的人物資料
    fact_ids: List[PortrayalId] = Field(default_factory=list, max_length=30)
    note_ids: List[PortrayalId] = Field(default_factory=list, max_length=30)
    fields: List[Literal['roles', 'tags', 'category', 'common_context', 'notes']] = Field(default_factory=list, max_length=5)

    @field_validator('fact_ids', 'note_ids', 'fields')
    @classmethod
    def no_duplicates(cls, values):
        return _unique(values)


class PersonPortrayalInput(Model):  # person_portrayal 生成輸入：只有人物 ID 與選取的資料 ID，內容由伺服器讀取
    person_id: PortrayalId
    selection: PortrayalSelection
    dataset: Literal['compact', 'full', 'custom'] = 'custom'  # 精簡／完整資料組，用於比較
    consent: Literal[True]  # 使用者已確認選取的資料會送往 AI Provider（前端一次性確認後每次帶上）

    @field_validator('consent', mode='before')
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError('請先確認人物資料會送往 AI 服務')
        return value


class PortrayalItem(Model):  # 一項 AI 推論與它依據的來源代號（空陣列＝沒有直接依據的推測）
    text: str = Field(min_length=1, max_length=200)
    basis: List[PortrayalRef] = Field(default_factory=list, max_length=6)


class PortrayalDialogue(Model):  # 依特徵推演的示範對話，不是本人說過的話
    situation: str = Field(min_length=1, max_length=80)
    line: str = Field(min_length=1, max_length=240)


class PortrayalProfile(Model):  # AI 人物詮釋（Provider 輸出）
    summary: str = Field(min_length=1, max_length=400)
    traits: List[PortrayalItem] = Field(min_length=1, max_length=6)
    motivations: List[PortrayalItem] = Field(min_length=1, max_length=4)
    values: List[PortrayalItem] = Field(default_factory=list, max_length=4)
    speaking_style: PortrayalItem
    behaviors: List[PortrayalItem] = Field(default_factory=list, max_length=5)
    emotional_reactions: List[PortrayalItem] = Field(default_factory=list, max_length=4)
    knowledge_boundary: str = Field(min_length=1, max_length=300)
    uncertainties: List[Annotated[str, Field(min_length=1, max_length=160)]] = Field(default_factory=list, max_length=6)
    sample_dialogues: List[PortrayalDialogue] = Field(min_length=1, max_length=3)

    def refs(self):  # 所有推論引用的代號
        items = self.traits + self.motivations + self.values + [self.speaking_style] + self.behaviors + self.emotional_reactions
        return {ref for item in items for ref in item.basis}


class PortrayalRefTarget(Model):  # 代號對應的來源（只有 ID，原文保存在生成紀錄的來源快照）
    kind: Literal['fact', 'note', 'field']
    id: PortrayalId


class PortrayalSource(Model):  # 作品引用的來源：固定人物、選取的資料與快照雜湊
    person_id: PortrayalId
    person_name: str = Field(min_length=1, max_length=100)
    fact_ids: List[PortrayalId] = Field(default_factory=list, max_length=30)
    note_ids: List[PortrayalId] = Field(default_factory=list, max_length=30)
    fields: List[Literal['roles', 'tags', 'category', 'common_context', 'notes']] = Field(default_factory=list, max_length=5)
    dataset: Literal['compact', 'full', 'custom']
    snapshot_sha256: str = Field(pattern=r'^[0-9a-f]{64}$')
    refs: dict[PortrayalRef, PortrayalRefTarget] = Field(default_factory=dict, max_length=65)


class PersonPortrayalContent(Model):  # 人物演繹作品：AI 詮釋（可人工修改）＋來源參照；圖片欄位保留給 F06B
    profile: PortrayalProfile
    source: PortrayalSource
    image: None = None  # F06B 人物立繪預留；本批一律為 null

    @model_validator(mode='after')
    def basis_in_source(self):  # 推論只能引用這份作品來源中的代號（人工修改也不能指到不存在的資料）
        if not self.profile.refs() <= set(self.source.refs):
            raise ValueError('推論引用了不在來源中的資料')
        return self


class PortrayalReplyInput(Model):  # portrayal_reply：互動試演的一句話；人物詮釋與來源由伺服器依 owner 讀取
    session_work_id: PortrayalId
    session_version: StrictInt = Field(ge=1)
    turn_no: StrictInt = Field(ge=1, le=PORTRAYAL_MAX_TURNS)
    message: str = Field(min_length=1, max_length=300)


class PortrayalReply(Model):  # Provider 輸出：人物可能的回應
    line: str = Field(min_length=1, max_length=400)
    tone: str = Field(default='', max_length=80)
    basis: List[PortrayalRef] = Field(default_factory=list, max_length=6)
    notes: str = Field(default='', max_length=200)


class PortrayalTurn(Model):  # 已確認的一個來回：使用者訊息＋原樣保存的 AI 回應＋生成紀錄
    turn_no: StrictInt = Field(ge=1, le=PORTRAYAL_MAX_TURNS)
    message: str = Field(min_length=1, max_length=300)
    reply: PortrayalReply
    generation_id: PortrayalId
    provider_kind: Literal['fake', 'live']


class PortrayalSessionRef(Model):  # 互動試演固定引用的人物演繹作品版本
    work_id: PortrayalId
    version_no: StrictInt = Field(ge=1)
    person_name: str = Field(min_length=1, max_length=100)


class PortrayalScenario(Model):  # 互動情境；自訂情境需要描述
    kind: Literal['advice', 'conflict', 'business', 'daily', 'memory', 'custom']
    detail: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def custom_needs_detail(self):
        if self.kind == 'custom' and not self.detail:
            raise ValueError('自訂情境需要描述')
        return self


class PortrayalSessionContent(Model):  # 互動試演紀錄：每個版本都是完整快照，只能逐來回追加或由使用者結束
    title: str = Field(min_length=1, max_length=80)
    portrayal: PortrayalSessionRef
    scenario: PortrayalScenario
    status: Literal['active', 'ended']
    ending: Optional[Literal['player_ended', 'turn_limit']] = None
    turns: List[PortrayalTurn] = Field(default_factory=list, max_length=PORTRAYAL_MAX_TURNS)

    @model_validator(mode='after')
    def consistent_turns(self):
        if [turn.turn_no for turn in self.turns] != list(range(1, len(self.turns) + 1)):
            raise ValueError('回合編號必須從 1 連續遞增')
        if (self.status == 'ended') != (self.ending is not None):
            raise ValueError('結束狀態與結束原因不一致')
        return self


class PersonProfileGenerateInput(Model):  # person_profile 生成輸入：只有人物 ID；上下文由伺服器依帳號讀取
    person_id: str = Field(min_length=1, max_length=128)
    guidance: str = Field(default='', max_length=500)  # 使用者對這次產生的偏好（選填）
    target_fields: List[Literal['background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior',
                                'knowledge_boundary', 'restrictions']] = Field(default_factory=list, max_length=9)  # 空＝全部欄位
    mode: Literal['generate', 'improve'] = 'generate'  # generate＝產生（空白或重寫）；improve＝改善已儲存的內容
    consent: Literal[True]  # 沿用既有 AI 使用同意：使用者確認人物資料會送往 AI 服務

    @field_validator('consent', mode='before')
    @classmethod
    def explicit_consent(cls, value):
        if value is not True:
            raise ValueError('請先確認人物資料會送往 AI 服務')
        return value


class PersonProfileDraft(Model):  # person_profile 的 Provider 輸出：九個人物設定欄位（上限與人物設定保存一致）
    background: str = Field(max_length=3000)
    personality: str = Field(max_length=2000)
    motivation: str = Field(max_length=1500)
    stance: str = Field(max_length=1500)
    abilities: str = Field(max_length=1500)
    expression: str = Field(max_length=1000)
    behavior: str = Field(max_length=2000)
    knowledge_boundary: str = Field(max_length=1000)
    restrictions: str = Field(max_length=1500)


class GenerateRequest(Model):  # 共用生成端點；module 決定輸入格式
    request_id: str = Field(min_length=1, max_length=128)  # 同一提交代碼只呼叫一次 Provider
    module: Literal['character_card', 'story_opening', 'character_reply', 'person_portrayal', 'portrayal_reply', 'theater_performance',
                    'person_profile']
    input: Union[CharacterCardInput, StoryOpeningInput, CharacterReplyInput, PersonPortrayalInput, PortrayalReplyInput, TheaterPerformanceInput,
                 PersonProfileGenerateInput]

    @model_validator(mode='after')
    def input_matches_module(self):  # 不允許以 A 模組名稱夾帶 B 模組的輸入
        expected = {'character_card': CharacterCardInput, 'story_opening': StoryOpeningInput, 'character_reply': CharacterReplyInput,
                    'person_portrayal': PersonPortrayalInput, 'portrayal_reply': PortrayalReplyInput,
                    'theater_performance': TheaterPerformanceInput, 'person_profile': PersonProfileGenerateInput}[self.module]
        if not isinstance(self.input, expected):
            raise ValueError('輸入格式與生成模組不符')
        return self


class WorkCreate(Model):  # 使用者明確保存作品；generation_id 指向 AI 原稿（選填）
    request_id: str = Field(min_length=1, max_length=128)
    kind: Literal['character_card', 'story_opening', 'story_session', 'person_portrayal', 'portrayal_session', 'theater_cast', 'theater_performance']
    content: Union[CharacterCardContent, StoryOpeningContent, StorySessionContent, PersonPortrayalContent, PortrayalSessionContent,
                   TheaterCastContent, TheaterPerformanceContent]
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode='after')
    def content_matches_kind(self):
        expected = {'character_card': CharacterCardContent, 'story_opening': StoryOpeningContent, 'story_session': StorySessionContent,
                    'person_portrayal': PersonPortrayalContent, 'portrayal_session': PortrayalSessionContent,
                    'theater_cast': TheaterCastContent, 'theater_performance': TheaterPerformanceContent}[self.kind]
        if not isinstance(self.content, expected):
            raise ValueError('作品內容與種類不符')
        return self


class WorkVersionCreate(Model):  # 新增版本；不改寫既有版本
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    base_version: StrictInt = Field(ge=1)  # 本次修改依據的版本
    content: Union[CharacterCardContent, StoryOpeningContent, StorySessionContent, PersonPortrayalContent, PortrayalSessionContent,
                   TheaterCastContent, TheaterPerformanceContent]  # 種類由伺服器依作品比對
    generation_id: Optional[str] = Field(default=None, min_length=1, max_length=128)


class WorkStatus(Model):  # 封存或恢復；本批不提供刪除
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    status: Literal['active', 'archived']
