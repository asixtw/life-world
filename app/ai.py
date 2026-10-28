"""Provider boundary: no external AI requests or automatic factual writes."""  # 說明此模組的責任與實作邊界
from typing import Protocol  # 宣告可選欄位、清單與受限字串型別


class DraftAssistant(Protocol):  # 整理候選提供者的介面契約
    def suggest(self, raw_text: str) -> dict:  # 建立可手動審閱的整理候選，不寫入正式事實
        ...  # 此處僅宣告介面，實際行為由提供者實作


class ManualAssistant:  # 保留原文的手動整理替身，不連接外部 AI
    def suggest(self, raw_text):  # 建立可手動審閱的整理候選，不寫入正式事實
        return {'provider': 'local-manual', 'summary': raw_text, 'applied': False,
                'notice': '未連接外部 AI。已保留原文，請自行編輯摘要並確認。'}  # 回傳建立可手動審閱的整理候選，不寫入正式事實的結果
