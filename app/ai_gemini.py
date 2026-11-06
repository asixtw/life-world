"""Gemini generateContent adapter；來源https://ai.google.dev/api/generate-content。

本模組不讀Secret Manager、不自動重送或輪替key，只有通過評測庫批准檢查才會被CLI呼叫。
"""
import json
import re
from .ai_provider_http import https_transport
from .ai_provider_base import EvalError,ModelResult


class GeminiProvider:
    live=True
    name='gemini'

    def __init__(self,model,*,key_supplier,transport=None):
        if not re.fullmatch(r'gemini-[a-z0-9][a-z0-9.\-]{0,100}',model):raise EvalError('invalid_model')
        self.model=model
        self.endpoint=f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        self._key_supplier=key_supplier
        self._transport=transport or https_transport

    @property
    def metadata(self):return {'endpoint':self.endpoint,'protocol':'gemini-generateContent-v1beta','pricing':'unknown'}

    def generate(self,prompt,max_output_tokens):
        if not 1<=max_output_tokens<=2000:raise EvalError('invalid_output_limit')
        key=self._key_supplier()
        if not isinstance(key,str) or not key:raise EvalError('key_unavailable')
        payload={'systemInstruction':{'parts':[{'text':prompt['system']}]},
                 'contents':[{'role':'user','parts':[{'text':json.dumps(prompt['case'],ensure_ascii=False)}]}],
                 'generationConfig':{'maxOutputTokens':max_output_tokens,'candidateCount':1}}
        if prompt.get('json_output'):payload['generationConfig']['responseMimeType']='application/json'
        if prompt.get('inline_media'):
            media=prompt['inline_media']
            if media.get('mime_type') not in ('image/png','image/jpeg','audio/wav','audio/x-wav','audio/webm','audio/ogg','audio/mp4','audio/mpeg'):raise EvalError('invalid_media')
            payload['contents'][0]['parts'].append({'inlineData':{'mimeType':media['mime_type'],'data':media['data']}})
        try:
            data=self._transport(self.endpoint,json.dumps(payload).encode(),{'Content-Type':'application/json','x-goog-api-key':key},30)
            candidates=data.get('candidates',[])
            if len(candidates)!=1 or data.get('promptFeedback',{}).get('blockReason'):raise EvalError('provider_refused')
            candidate=candidates[0]
            if candidate.get('finishReason') not in ('STOP','MAX_TOKENS'):raise EvalError('provider_refused')
            text=''.join(p['text'] for p in candidate.get('content',{}).get('parts',[]) if 'text' in p and not p.get('thought'))
            if not text.strip() or len(text)>20000:raise EvalError('invalid_output')
            usage=data.get('usageMetadata',{})
            def token(name):
                n=usage.get(name)
                if n is not None and (type(n) is not int or n<0):raise EvalError('invalid_usage')
                return n
            prompt_tokens=token('promptTokenCount');out=token('candidatesTokenCount');thoughts=token('thoughtsTokenCount')
            if out is not None:out+=thoughts or 0
            # API未直接提供帳單金額，不能捏造0；評測庫持續占用核准的預留額。
            return ModelResult(text,prompt_tokens,out,None,data.get('responseId'))
        except EvalError:raise
        except Exception:raise EvalError('provider_failed') from None
