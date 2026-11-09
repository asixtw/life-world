"""由當次已確認來源衍生雙端情境特徵；沒有持久化推論或人格標籤。"""
from typing import Literal
from pydantic import BaseModel,ConfigDict


class Behavior(BaseModel):
    """有限規則輸出，與模型台詞分開；不使用未校準confidence。"""
    model_config=ConfigDict(extra='forbid',strict=True)
    action:Literal['ask_question','share_context','acknowledge']
    tone:Literal['supportive']='supportive'
    reason_codes:list[Literal['question_context','confirmed_context','limited_context']]
    simulation:Literal[True]=True


def build_context(facts, records, message, observed_at):
    """只用本次重新驗證的來源，傳回短期內部提示；無DB寫入副作用。

    facts為已確認人物資訊，records為相同Owner的已確認來源摘要。
    標籤只描述記錄中的議題，不宣稱雙方真正的興趣或人格。
    """
    topics={'reading':('閱讀','讀書','書籍'),'learning':('學習','練習','課程'),'work':('工作','專案','會議')}
    def features(items, side):
        """將記錄議題附上可追溯來源，不推論人格或校準機率。"""
        result=[]
        for topic,words in topics.items():
            refs=sorted({ref for text,sources in items if any(word in text for word in words) for ref in sources})
            if refs:result.append({'tag':side+'.recorded_context.'+topic,'source_refs':refs,'observed_at':observed_at,'uncertainty':'unvalidated_context_hint','method':'keyword_rules_v1','source_times':{ref:next((r.get('occurred_at') for r in records if r['id']==ref),None) for ref in refs}})
        return result
    user=features([(r['summary'],[r['id']]) for r in records],'user')
    person=features([(f['value'],f['source_experience_ids']) for f in facts],'person')
    question=any(word in message for word in ('如何','怎麼','為什麼','？','?'))
    behavior=Behavior(action='ask_question' if question else 'share_context' if facts else 'acknowledge',reason_codes=['question_context' if question else 'confirmed_context' if facts else 'limited_context']).model_dump()
    return {'version':'relationship-context-rules-v1','user_features':user,'person_features':person,
            'relationship_features':{'confirmed_source_count':len({r['id'] for r in records}),'uncertainty':'user_reported_only'},
            'context_features':{'purpose':'private_simulation','observed_at':observed_at},'behavior':behavior}
