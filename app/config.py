"""Explicit development policy; these values are not approved product rules."""  # 說明此模組的責任與實作邊界
from dataclasses import dataclass  # 建立不可變的開發設定物件


@dataclass(frozen=True)  # 執行此模組的共用工具操作
class DemoPolicy:  # 本機開發設定；尚非正式產品規則
    points_per_experience: int = 1  # 設定每筆確認經歷的開發用積分的型別、預設值與輸入限制
    max_upload_bytes: int = 5 * 1024 * 1024  # 設定圖片上傳大小上限的型別、預設值與輸入限制
    session_hours: int = 24 * 7  # 設定登入工作階段有效小時數的型別、預設值與輸入限制
    secure_cookies: bool = False  # 設定是否只透過 HTTPS 傳送 Cookie的型別、預設值與輸入限制
    rule_version: str = 'local-demo-v1'  # 設定積分規則的開發版本代號的型別、預設值與輸入限制

    def __post_init__(self):  # 檢查開發設定的數值皆為正數
        if self.points_per_experience <= 0 or self.max_upload_bytes <= 0 or self.session_hours <= 0:  # 依目前條件選擇下一步處理分支
            raise ValueError('Development policy values must be positive')  # 中止目前操作並向呼叫端傳遞錯誤
