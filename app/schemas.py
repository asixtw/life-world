from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Optional, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator


def decimal_string(value):
    if isinstance(value, bool):
        raise ValueError('請填寫正數')
    try:
        value = Decimal(str(value))
    except InvalidOperation:
        raise ValueError('請填寫有效數字')
    if not value.is_finite() or value <= 0 or value > Decimal('1000000000000'):
        raise ValueError('數值必須大於 0 且不超過 10^12')
    if value.as_tuple().exponent < -6:
        raise ValueError('最多六位小數')
    return format_decimal(value)


def format_decimal(value):
    result = format(value, 'f')
    return result.rstrip('0').rstrip('.') if '.' in result else result


class Model(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Profile(Model):
    name: str = Field(min_length=1, max_length=80)
    bio: str = Field(min_length=1, max_length=2000)
    timezone: str = 'Asia/Taipei'

    @field_validator('timezone')
    @classmethod
    def valid_timezone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError('請使用有效的 IANA 時區')
        return value


class Credentials(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    username: str = Field(pattern=r'^[a-zA-Z0-9_]{3,30}$')
    password: str = Field(min_length=10, max_length=128)

    @field_validator('username')
    @classmethod
    def normalize_username(cls, value):
        return value.lower()


class Login(Model):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=128)
    discard_guest: bool = False


class Action(Model):
    title: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=20)
    target: str
    level: StrictInt = Field(ge=1, le=3)
    weekdays: List[StrictInt] = Field(min_length=1, max_length=7)

    @field_validator('target', mode='before')
    @classmethod
    def valid_target(cls, value):
        return decimal_string(value)

    @field_validator('weekdays')
    @classmethod
    def valid_days(cls, value):
        if len(set(value)) != len(value) or any(d < 0 or d > 6 for d in value):
            raise ValueError('星期需為不重複的 0～6')
        return sorted(value)


class GoalCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=160)
    outcome: str = Field(min_length=1, max_length=4000)
    actions: List[Action] = Field(min_length=3, max_length=3)


class Contribution(Model):
    action_id: str = Field(min_length=1, max_length=128)
    quantity: str

    @field_validator('quantity', mode='before')
    @classmethod
    def valid_quantity(cls, value):
        return decimal_string(value)


class WithContributions(Model):
    contributions: List[Contribution] = Field(default_factory=list, max_length=50)

    @model_validator(mode='after')
    def distinct_actions(self):
        ids = [c.action_id for c in self.contributions]
        if len(ids) != len(set(ids)):
            raise ValueError('同一行動在本次貢獻只能出現一次')
        return self


class DraftCreate(WithContributions):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=False)
    raw_text: str = Field(min_length=1, max_length=20000)
    occurred_at: datetime
    goal_id: Optional[str] = Field(default=None, max_length=128)
    person_id: Optional[str] = Field(default=None, max_length=128)

    @field_validator('raw_text')
    @classmethod
    def nonblank_raw(cls, value):
        if not value.strip():
            raise ValueError('原始記錄不可為空白')
        return value

    @field_validator('occurred_at')
    @classmethod
    def aware_time(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('發生時間必須帶時區')
        return value


class DraftEdit(DraftCreate):
    expected_revision: StrictInt = Field(ge=1)


class Confirm(WithContributions):
    request_id: str = Field(min_length=1, max_length=128)
    expected_revision: StrictInt = Field(ge=1)
    summary: str = Field(min_length=1, max_length=20000)
    person_id: Optional[str] = Field(default=None, max_length=128)
    tasks: List[str] = Field(default_factory=list, max_length=20)

    @field_validator('tasks')
    @classmethod
    def valid_tasks(cls, values):
        values = [v.strip() for v in values]
        if any(not v or len(v) > 300 for v in values):
            raise ValueError('任務需有內容且不超過 300 字')
        return values


class PersonCreate(Model):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(default='', max_length=100)
    notes: str = Field(default='', max_length=4000)


class Complete(Model):
    request_id: str = Field(min_length=1, max_length=128)
    evidence_ids: List[str] = Field(min_length=1, max_length=10)
    confirmed: Literal[True]
    reflection: str = Field(default='', max_length=4000)

    @field_validator('confirmed', mode='before')
    @classmethod
    def explicit_true(cls, value):
        if value is not True:
            raise ValueError('必須由使用者明確確認成果')
        return value

    @field_validator('evidence_ids')
    @classmethod
    def distinct_evidence(cls, values):
        if len(values) != len(set(values)) or any(not v or len(v) > 128 for v in values):
            raise ValueError('佐證 ID 必須有效且不重複')
        return values


class NoteCreate(Model):
    person_id: Optional[str] = None
    kind: Literal['preparation', 'simulation', 'message']
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=20000)


class TaskEdit(Model):
    done: bool
