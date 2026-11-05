"""Gemini3.5Flash-Lite使用官方generateContent契約；僅合成transport，不呼叫API。"""
import json
import pytest
from model_eval.gemini import GeminiProvider
from model_eval.core import EvalError


def test_gemini_model_payload_and_usage_without_key_in_url():
    seen=[]
    def transport(url,body,headers,timeout):
        seen.append((url,json.loads(body),headers,timeout))
        return {'candidates':[{'content':{'parts':[{'text':'我想先確認這次的目標。'}]},'finishReason':'STOP'}],
                'usageMetadata':{'promptTokenCount':20,'candidatesTokenCount':8,'thoughtsTokenCount':2},'responseId':'synthetic-id'}
    provider=GeminiProvider('gemini-3.5-flash-lite',key_supplier=lambda:'SYNTHETIC-KEY',transport=transport)
    result=provider.generate({'system':'只用合成來源','case':{'synthetic_only':True}},120)
    assert result.text=='我想先確認這次的目標。'
    assert result.input_tokens==20 and result.output_tokens==10 and result.cost_microusd is None
    url,body,headers,timeout=seen[0]
    assert url=='https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'
    assert 'SYNTHETIC-KEY' not in url and headers['x-goog-api-key']=='SYNTHETIC-KEY'
    assert body['generationConfig']['maxOutputTokens']==120
    assert body['systemInstruction']['parts'][0]['text']=='只用合成來源'


def test_gemini_refusal_error_and_invalid_model_never_leak_key():
    calls=[]
    def refused(*args):calls.append(1);return {'promptFeedback':{'blockReason':'SAFETY'}}
    p=GeminiProvider('gemini-3.5-flash-lite',key_supplier=lambda:'SYNTHETIC-KEY',transport=refused)
    with pytest.raises(EvalError):p.generate({'system':'合成','case':{}},100)
    assert calls==[1]
    with pytest.raises(EvalError):GeminiProvider('../wrong',key_supplier=lambda:None)
