class DomainError(Exception):  # 攜帶 HTTP 狀態、錯誤代碼與可閱讀訊息的領域例外
    def __init__(self, status, code, message):  # 保存可供 API 回應的錯誤資訊
        self.status = status  # 保存「self.status」供後續驗證或回傳使用
        self.code = code  # 保存「self.code」供後續驗證或回傳使用
        self.message = message  # 保存「self.message」供後續驗證或回傳使用
        super().__init__(message)  # 執行此模組的共用工具操作


def require(condition, status, code, message):  # 將不符合領域條件的操作轉為可辨識錯誤
    if not condition:  # 依目前條件選擇下一步處理分支
        raise DomainError(status, code, message)  # 中止目前操作並向呼叫端傳遞錯誤
