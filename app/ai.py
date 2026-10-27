"""Provider boundary: no external AI requests or automatic factual writes."""
from typing import Protocol


class DraftAssistant(Protocol):
    def suggest(self, raw_text: str) -> dict:
        ...


class ManualAssistant:
    def suggest(self, raw_text):
        return {'provider': 'local-manual', 'summary': raw_text, 'applied': False,
                'notice': '未連接外部 AI。已保留原文，請自行編輯摘要並確認。'}
