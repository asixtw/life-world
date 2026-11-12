# 2026-11-10 自 8445（life-world-react-integrated/app/ai_providers.py）原樣移植；只改 import 路徑。
"""S1 Provider 實作：測試用假回應與 Gemini Developer API 轉接器。

Gemini 格式與回應解析移植自 model_eval/gemini.py、model_eval/gateway.py（離線評測庫不進正式服務）。
在使用者核准模型、金鑰與預算前，build_provider 不會建立真實 Provider，因此不會產生付費呼叫。
"""
import json  # 解析請求與回應本文
import os  # 呼叫當下才讀取金鑰環境變數
import re  # 驗證模型名稱，避免拼入任意 URL 片段
import socket  # 辨識傳輸逾時
import sys  # 診斷紀錄寫到 stdout，由 Cloud Run 解析成結構化日誌
import time  # 假回應延遲與 Provider 延遲量測
from urllib.error import HTTPError, URLError  # 辨識 HTTP 錯誤與 urllib 包裝的傳輸逾時
from urllib.request import HTTPRedirectHandler, Request, build_opener  # 單次 HTTPS 呼叫，不跟隨轉址

from .ai_text import ProviderFailure, TextRequest, TextResult  # Provider 中立介面

FAKE_MARK = '（測試用假回應）'  # 假內容本身也帶標示，避免被複製後誤認為真 AI


class FakeProvider:
    """本機與自動化測試用；不連網、不計費，輸出明確標示為測試用假回應。

    名稱含 #fake-fail／#fake-refuse／#fake-slow 時，模擬故障、拒絕與逾時，供畫面驗證錯誤處理。
    F05 互動回合則看玩家自由輸入的文字（另有 #fake-invalid 模擬格式錯誤）。
    """
    name, model, kind = 'fake', 'fake-character-card-v1', 'fake'

    def __init__(self, delay_ms=0, slow_seconds=45.0):
        self.delay_ms, self.slow_seconds = delay_ms, slow_seconds

    def generate(self, request: TextRequest) -> TextResult:
        payload = json.loads(request.user)
        if payload.get('module') == 'story_opening':
            return self._story(payload)
        if payload.get('module') == 'character_reply':
            return self._reply(payload, request)
        if payload.get('module') == 'person_portrayal':
            return self._portrayal(payload)
        if payload.get('module') == 'portrayal_reply':
            return self._portrayal_reply(payload)
        if payload.get('module') == 'theater_performance':
            return self._performance(payload)
        if payload.get('module') == 'person_profile':
            return self._person_profile(payload)
        if payload.get('module') == 'roleplay_plan':
            return self._roleplay_plan(payload)
        if payload.get('module') == 'roleplay_segment':
            return self._roleplay_segment(payload)
        if payload.get('module') == 'interactive_layer':
            return self._interactive_layer(payload)
        if payload.get('module') == 'game_plan':
            return self._game_plan(payload)
        if payload.get('module') == 'game_reaction':
            return self._game_reaction(payload)
        data = payload.get('input', {})
        name = str(data.get('name', '')).strip() or '未命名角色'
        if '#fake-slow' in name:
            time.sleep(self.slow_seconds)  # 刻意超過總時限，驗證逾時與晚到結果捨棄
        elif self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        if '#fake-fail' in name:
            raise ProviderFailure('provider_error')
        if '#fake-refuse' in name:
            raise ProviderFailure('provider_refused')

        def filled(field, fallback):  # 保留玩家原文，空白欄位以標示過的範例補上
            value = str(data.get(field, '')).strip()
            return value[:500] if value else FAKE_MARK + fallback

        restrictions = [part.strip() for part in re.split(r'[\n；;]+', str(data.get('restrictions', ''))) if part.strip()][:8]
        card = {'name': name[:60], 'kind': data.get('kind') if data.get('kind') in ('fictional', 'role') else 'fictional',
                'tagline': FAKE_MARK + name[:40] + '的角色概念',
                'background': filled('background', '尚未提供背景，請自行補充。'),
                'personality': filled('personality', '個性待補充。'),
                'motivation': filled('motivation', '動機待補充。'),
                'stance': filled('stance', '立場待補充。'),
                'voice': filled('voice', '語氣待補充。'),
                'knowledge_boundary': filled('knowledge_boundary', '只知道設定中明確寫出的內容。'),
                'restrictions': [item[:120] for item in restrictions] or [FAKE_MARK + '不冒充真實人物或其原話'],
                'sample_lines': [FAKE_MARK + '我是' + name[:40] + '。這句台詞只用於測試畫面。']}
        text = json.dumps(card, ensure_ascii=False)
        return TextResult(text=text, input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)


    def _performance(self, payload):
        """多角色演出假回應：陣容輪流發言、首句為旁白；演出要求含標記時模擬故障、拒絕或格式錯誤（台詞說話者不在陣容中）。"""
        direction = str(payload.get('direction', ''))
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        if '#fake-fail' in direction:
            raise ProviderFailure('provider_error')
        if '#fake-refuse' in direction:
            raise ProviderFailure('provider_refused')
        names = [str(member.get('name')) for member in payload.get('cast', [])]
        lines = [{'speaker': '旁白', 'text': FAKE_MARK + str(payload.get('scenario', ''))[:80]}]
        for index in range(7):
            name = names[index % len(names)]
            lines.append({'speaker': name, 'text': FAKE_MARK + f'{name}依照自己的設定回應（第 {index + 1} 句）。'})
        if '#fake-invalid' in direction:
            lines[1]['speaker'] = '不在陣容中的角色'
        performance = {'title': FAKE_MARK[:8] + '多角色演出', 'lines': lines, 'notes': FAKE_MARK + '測試畫面用，不是 AI 生成。'}
        return TextResult(text=json.dumps(performance, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _roleplay_plan(self, payload):
        """自動演出規劃假回應：兩個節拍，陣容依序輪流發言到目標段數；場景含 #fake-fail／#fake-bad-plan 時模擬故障或格式錯誤。"""
        scene = str(payload.get('scene', {}).get('description', ''))
        if '#fake-fail' in scene:
            raise ProviderFailure('provider_error')
        ids = [member['id'] for member in payload.get('cast', [])]
        target = max(len(ids), int(payload.get('target_segments') or len(ids)))
        order = [ids[index % len(ids)] for index in range(target)]
        half = max(1, target // 2)
        beats = [{'goal': FAKE_MARK + '開場：人物登場並說明立場。', 'present': ids, 'speaker_order': order[:half]},
                 {'goal': FAKE_MARK + '推進：人物互相回應並收尾。', 'present': ids, 'speaker_order': order[half:]}]
        beats = [beat for beat in beats if beat['speaker_order']]
        if '#fake-bad-plan' in scene:
            beats[0]['speaker_order'] = ['不在陣容中的人物']
        plan = {'title': FAKE_MARK[:8] + '自動演出', 'premise': FAKE_MARK + scene[:100], 'beats': beats}
        return TextResult(text=json.dumps(plan, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _roleplay_segment(self, payload):
        """自動演出一段假回應：只替指定發言人物說話，台詞引用他的說話方式，證明使用的是他的人格；#fake-bad-speaker 讓第 1 段發言歸屬錯誤。"""
        scene = str(payload.get('scene', {}).get('description', ''))
        if '#fake-fail' in scene:
            raise ProviderFailure('provider_error')
        speaker = payload.get('turn', {}).get('speaker', {})
        persona = speaker.get('persona', {})
        name = str(persona.get('name') or persona.get('display_name') or speaker.get('id'))[:40]
        style = str(persona.get('voice') or persona.get('speaking_style') or '')[:30]
        turn_no = payload.get('turn', {}).get('turn_no')
        segment = {'speaker_id': speaker.get('id'),
                   'line': FAKE_MARK + f'{name}（第 {turn_no} 段，{style or "依設定"}）：我看到了 {len(payload.get("visible_history") or [])} 段經過。',
                   'action': FAKE_MARK + f'{name}向前一步。', 'stage_direction': '',
                   'state': {'emotion': '平靜', 'stance': '觀察', 'goal': FAKE_MARK[:8] + '推進節拍'},
                   'memory': [FAKE_MARK + f'第 {turn_no} 段我說過話。']}
        if '#fake-bad-speaker' in scene and turn_no == 1:
            segment['speaker_id'] = 'someone-else'  # 發言歸屬錯誤，驗證伺服器拒絕並重新生成同一段
        return TextResult(text=json.dumps(segment, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _interactive_layer(self, payload):
        """互動層假回應：只依送來的故事組出確定性的結果，文字都標示測試用。

        - 抉擇：做決定的人是抉擇點之前最後一位說話的人；三個選項（真結局、行得通但比較差、弄巧成拙各一），另外兩個各有一段結局。
        - 線索：每一個底牌，從抉擇點（含）以前、那位人物自己的第一段取開頭的幾個字——一定是原文裡真的有的詞。
        - 番外：每個陣營一則。提問：一句。
        開場白含 #fake-layer-fail／#fake-layer-invalid 時模擬故障或格式錯誤（場景描述會被假規劃寫進開場白）。
        """
        premise = str(payload.get('story', {}).get('premise', ''))
        if '#fake-layer-fail' in premise:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        after = payload.get('decision_after_beat')
        segments = payload.get('segments') or []
        before = [item for item in segments if after is None or (item.get('beat_no') is not None and item['beat_no'] <= after)]
        ids = {str(member.get('name')): member.get('id') for member in payload.get('cast', [])}
        decision = {'actor': '', 'question': '', 'options': []}  # 沒有抉擇點（只有一幕）：不給抉擇
        if after is not None and before:
            actor = str(before[-1].get('speaker'))
            decision = {'actor': ids.get(actor, ''), 'question': FAKE_MARK + f'第 {after} 幕之後，{actor[:20]}該怎麼做？',
                        'options': [{'label': FAKE_MARK + '照原本的打算', 'kind': 'true', 'ending': ''},
                                    {'label': FAKE_MARK + '先退一步', 'kind': 'plain', 'ending': FAKE_MARK + f'{actor[:20]}先退一步，事情勉強過關，卻少了原本的收穫。'},
                                    {'label': FAKE_MARK + '硬碰硬', 'kind': 'bad', 'ending': FAKE_MARK + f'{actor[:20]}硬碰硬，結果事與願違。'}]}
        clues = []
        for secret in payload.get('secrets') or []:
            own = next((item for item in before if item.get('speaker') == secret.get('name') and (item.get('line') or item.get('action'))), None)
            if own is None:
                continue
            field = 'line' if own.get('line') else 'action'
            text = str(own[field])
            phrase = (text[len(FAKE_MARK):] if text.startswith(FAKE_MARK) else text).strip()[:6].strip()  # 原文裡連續的一小段
            if len(phrase) >= 2:
                clues.append({'turn_no': own.get('turn_no'), 'field': field, 'phrase': phrase, 'hint': FAKE_MARK + '這裡有點不對勁？',
                              'secret_of': secret.get('id')})
        layer = {'decision': decision, 'clues': clues[:3],
                 'epilogues': [{'side': side.get('name'), 'text': FAKE_MARK + f'{str(side.get("name"))[:20]}這一方在事情結束後私下碰面。'}
                               for side in payload.get('sides') or []],
                 'question': FAKE_MARK + '換作是你，會怎麼選？'}
        text = '{"decision":' if '#fake-layer-invalid' in premise else json.dumps(layer, ensure_ascii=False)  # 截斷的 JSON：驗證伺服器拒絕
        return TextResult(text=text, input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    # 回合制互動作品（行程）的假規劃：(名稱, 描述, x, y, 停留, 開門與打烊（相對於出發時間的分鐘數；None 是整天開放）, 標籤)。
    # 位置分散、營業時間有早有晚、停留長短不同：時限內走得完三站以上，但走不完全部。
    GAME_PLACES = (('早市', '天亮就開的市場，接近中午收攤。', 3, 6, 45, (-120, 180), ['吃', '市場']),
                   ('半山茶屋', '半山腰的老屋，出發兩小時後才開門。', 7, 4, 45, (120, 540), ['休息']),
                   ('舊鐵道步道', '沿著舊鐵道走的步道，沒有遮蔭。', 8, 8, 75, None, ['散步', '拍照']),
                   ('玻璃工坊', '可以自己動手做的工坊，只開下午三個小時。', 2, 2, 90, (300, 480), ['手作']),
                   ('岬角瞭望台', '路程不近的瞭望台，傍晚前關門。', 10, 5, 60, (60, 510), ['風景', '拍照']),
                   ('老書店', '木地板會響的書店，接近中午才開。', 5, 8, 45, (180, 660), ['逛街', '書']))
    GAME_DELTAS = (2, -1, 1, 0, -2, 1, 2, -1)  # 假的喜好：依「第幾位同行者、第幾站」取用，每個人有高有低、彼此不同

    def _game_plan(self, payload):
        """回合制互動作品的規劃假回應：固定六站（GAME_PLACES），營業時間跟著出發時間移動；文字都標示測試用。

        使用者寫的說明會寫進開場白（之後角色反應的假回應看得到）。說明含 #fake-fail／#fake-plan-invalid 時模擬故障或格式錯誤。
        """
        request = payload.get('request', {})
        description = str(request.get('description', ''))
        if '#fake-fail' in description:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        hour, minute = (int(part) for part in str(request.get('start_time') or '08:00').split(':'))
        start = hour * 60 + minute

        def clock(offset):  # 相對於出發時間的分鐘數 → 'HH:MM'，夾在同一天之內
            minutes = max(0, min(1440, start + offset))
            return f'{minutes // 60:02d}:{minutes % 60:02d}'

        places = [{'name': name, 'text': FAKE_MARK + text, 'x': x, 'y': y, 'stay': stay,
                   'open': clock(hours[0]) if hours else '00:00', 'close': clock(hours[1]) if hours else '24:00', 'tags': tags}
                  for name, text, x, y, stay, hours, tags in self.GAME_PLACES]
        plan = {'title': FAKE_MARK + '一日行程', 'premise': FAKE_MARK + description[:100], 'meter_label': '滿意',
                'home_text': FAKE_MARK + f'從{str(request.get("start_place", ""))[:20]}出發，時間到之前要回到這裡。',
                'places': places,
                'endings': {key: {'title': FAKE_MARK + title, 'text': FAKE_MARK + text} for key, title, text in (
                    ('perfect', '完美', '每個人都盡興，回程的路上沒有人想說再見。'), ('great', '開心', '這一天過得很開心，大家約好下次再來。'),
                    ('ok', '普通', '有人盡興，有人還好，回程的路上各自看著窗外。'), ('poor', '可惜', '氣氛不太對，回程的路上很安靜。'))}}
        text = '{"title":' if '#fake-plan-invalid' in description else json.dumps(plan, ensure_ascii=False)  # 截斷的 JSON：驗證伺服器拒絕
        return TextResult(text=text, input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _game_reaction(self, payload):
        """回合制互動作品的角色反應假回應：每一站一個喜好（GAME_DELTAS）與三種態度下的反應，另有願望與最後一句話；文字都標示測試用。

        只用送來的名稱組句，不引用人物設定的內容。開場白含 #fake-reaction-fail／#fake-reaction-invalid 時模擬故障或格式錯誤
        （使用者寫的說明會被假規劃寫進開場白）。
        """
        premise = str(payload.get('game', {}).get('premise', ''))
        if '#fake-reaction-fail' in premise:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        you = payload.get('you', {})
        name = str((you.get('persona') or {}).get('name') or you.get('id'))[:10]
        digits = re.sub(r'\D', '', str(you.get('id')))
        shift = (int(digits) - 1) * 3 if digits else 0  # 每位同行者從不同的位置開始取用，喜好才會不一樣
        places = []
        for index, place in enumerate(payload.get('places') or []):
            spot = str(place.get('name'))[:8]
            places.append({'id': place.get('id'), 'delta': self.GAME_DELTAS[(index + shift) % len(self.GAME_DELTAS)],
                           'low': FAKE_MARK + f'{name}在{spot}不太說話。', 'mid': FAKE_MARK + f'{name}在{spot}四處看看。',
                           'high': FAKE_MARK + f'{name}在{spot}主動帶路。'})
        reaction = {'places': places, 'wish': FAKE_MARK + f'{name}想找個地方坐下來。',
                    'farewell': {'low': FAKE_MARK + f'{name}：「我先走了。」', 'mid': FAKE_MARK + f'{name}：「今天謝謝你。」',
                                 'high': FAKE_MARK + f'{name}：「下次再一起來！」'}}
        text = '{"places":' if '#fake-reaction-invalid' in premise else json.dumps(reaction, ensure_ascii=False)  # 截斷的 JSON
        return TextResult(text=text, input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _story(self, payload):
        """故事開場假回應：沿用玩家設定，三個選項固定為談判／調查／冒險；設定含標記時模擬故障、拒絕、逾時或格式錯誤。"""
        brief = payload.get('input', {})
        character = payload.get('character', {})
        text = ' '.join(str(brief.get(key, '')) for key in ('genre', 'setting', 'conflict', 'player_goal', 'constraints'))
        if '#fake-slow' in text:
            time.sleep(self.slow_seconds)
        elif self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        if '#fake-fail' in text:
            raise ProviderFailure('provider_error')
        if '#fake-refuse' in text:
            raise ProviderFailure('provider_refused')
        name = str(character.get('name') or '主角')[:40]
        choices = [{'label': FAKE_MARK[:8] + '先談判', 'strategy': '談判', 'description': FAKE_MARK + f'由{name}出面，讓相關的人各自說明立場。'},
                   {'label': FAKE_MARK[:8] + '先調查', 'strategy': '調查', 'description': FAKE_MARK + '先收集線索與紀錄，再決定下一步。'},
                   {'label': FAKE_MARK[:8] + '先冒險', 'strategy': '冒險', 'description': FAKE_MARK + '直接前往危險的現場，親眼確認情況。'}]
        if '#fake-invalid' in text:
            choices = choices[:2]  # 刻意少一個選項，驗證伺服器拒絕不完整輸出
        story = {'title': FAKE_MARK + name + '的' + str(brief.get('genre', '故事'))[:12] + '開場',
                 'opening': FAKE_MARK + f'{name}來到「{str(brief.get("setting", ""))[:200]}」。這段開場只用於測試畫面，不是 AI 生成。',
                 'objective': FAKE_MARK + str(brief.get('player_goal', ''))[:300],
                 'conflict': FAKE_MARK + str(brief.get('conflict', ''))[:500],
                 'choices': choices,
                 'narrative_notes': FAKE_MARK + '本故事為虛構情境，不代表真實人物、事件或歷史結論。'}
        return TextResult(text=json.dumps(story, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    # F05-A 互動回合的確定性分支：(角色台詞, 場景變化, 下一步三個選項)。只用於驗證「不同行動得到不同結果」。
    REPLY_BRANCHES = {
        'talk': ('「好，我願意聽你說完。不過你也得告訴我，打算怎麼保證大家的安全。」', '原本緊繃的人群安靜下來，有人放下了手中的燈。',
                 [('提出交換條件', '談判', '用一個小讓步換取對方的信任。'), ('核對對方說法', '調查', '把剛才聽到的內容與現場紀錄比對。'),
                  ('趁機前往現場', '冒險', '在大家注意力被引開時行動。')]),
        'investigate': ('「這裡的痕跡不對勁，我們先別下結論，把線索一條一條排出來。」', '你注意到地上有一道新的拖痕，延伸到黑暗的角落。',
                        [('詢問目擊者', '談判', '找剛才在場的人問清楚經過。'), ('追查拖痕', '調查', '沿著痕跡找出它通往哪裡。'),
                         ('闖進暗處', '冒險', '不等支援，直接進入角落查看。')]),
        'risk': ('「太危險了！但既然你已經往前，我會替你看著後方。」', '腳下的木板發出斷裂聲，風勢突然變強，四周的光線忽明忽暗。',
                 [('呼叫同伴支援', '談判', '請其他人一起幫忙穩住局面。'), ('檢查周圍環境', '調查', '先確認哪裡還能安全落腳。'),
                  ('繼續向前推進', '冒險', '冒著風險直接接近目標。')]),
        'free': ('「你這個做法我沒想過……好吧，我們就照你的方式試試看。」', '你的行動讓局勢出現新的變化，周圍的人開始重新評估你。',
                 [('說服旁觀者', '談判', '讓旁觀的人站到你這一邊。'), ('觀察新的變化', '調查', '看看剛才的行動帶來哪些影響。'),
                  ('乘勝追擊', '冒險', '趁局勢改變時更進一步。')]),
    }
    BRANCH_WORDS = (('talk', ('談判', '協商', '說服', '交涉')), ('investigate', ('調查', '查', '觀察', '線索')), ('risk', ('冒險', '闖', '潛', '衝', '探')))

    @classmethod
    def _branch(cls, strategy, text):
        """先看策略、再看行動文字的關鍵字；都沒有時視為自由行動分支。"""
        for value in (strategy, text):
            for branch, words in cls.BRANCH_WORDS:
                if value and any(word in value for word in words):
                    return branch
        return 'free'

    # F05D：#fake-reverse 依伺服器解析的第一個明確約束寫出相反結果，用來在畫面驗證 Action Guard 會拒絕。
    REVERSED = {'left': '船頭向右偏移。', 'right': '船頭向左偏移。', 'forward': '你向後退了幾步。', 'backward': '你向前衝了出去。',
                'approach': '你遠離了對方。', 'withdraw': '你靠近了對方。', 'enter': '你轉身離開了這裡。', 'exit': '你走進了更深處。',
                'accept': '你拒絕了這個提議。', 'reject': '你接受了這個提議。'}

    def _reply(self, payload, request):
        """互動回合假回應：依玩家行動走確定性分支並引用上一回合；自由輸入含標記時模擬故障、拒絕、逾時或格式錯誤。

        Schema 含 action_resolution（character-reply-v2）時另回行動結算；#fake-blocked 模擬受阻、#fake-reverse 模擬方向反轉。
        F05D-2：Schema 的 action_resolution 含 player_action（v3）時一併回填玩家動作；#fake-modified 模擬外力改變結果。
        """
        turn = payload.get('turn', {})
        action = turn.get('player_action', {})
        text = str(action.get('text', ''))
        if '#fake-slow' in text:
            time.sleep(self.slow_seconds)
        elif self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        if '#fake-fail' in text:
            raise ProviderFailure('provider_error')
        if '#fake-refuse' in text:
            raise ProviderFailure('provider_refused')
        name = str(payload.get('character', {}).get('name') or '角色')[:20]
        line, scene, options = self.REPLY_BRANCHES[self._branch(str(action.get('strategy', '')), text)]
        history = payload.get('history') or []
        previous = f'延續上一回合「{str(history[-1].get("action", ""))[:20]}」的結果，' if history else ''
        closing = '故事來到最後一個回合。' if turn.get('remaining') == 0 else ''
        choices = [{'label': FAKE_MARK + label, 'strategy': strategy, 'description': FAKE_MARK + description} for label, strategy, description in options]
        if '#fake-invalid' in text:
            choices = choices[:2]  # 刻意少一個選項，驗證伺服器拒絕不完整輸出
        reply = {'npc_line': FAKE_MARK + f'{name}回應你的行動「{text[:30]}」：{line}',
                 'scene': FAKE_MARK + f'第 {turn.get("turn_no", 1)} 回合：{previous}{scene}{closing}',
                 'choices': choices,
                 'narrative_notes': FAKE_MARK + '虛構情境；角色的推測不代表真實人物、事件或史實。'}
        properties = request.response_schema.get('properties', {})
        if 'action_resolution' in properties:
            resolution, effect = {'status': 'executed', 'reason': ''}, FAKE_MARK + f'你依照「{text[:30]}」行動，局勢跟著改變。'
            player_action = FAKE_MARK + f'你照「{text[:150]}」行動。'
            if '#fake-blocked' in text:
                resolution = {'status': 'blocked', 'reason': FAKE_MARK + '舵輪被纜繩纏住，這個行動暫時無法完成。'}
                effect = FAKE_MARK + '你的行動沒有完成，局勢暫時停在原地。'
                player_action = FAKE_MARK + f'你試著照「{text[:150]}」行動。'
            elif '#fake-modified' in text:
                resolution = {'status': 'modified', 'reason': FAKE_MARK + '橫浪突然打來，把船推離原本的航線。'}
                effect = FAKE_MARK + '你照原本的決定行動，但橫浪讓結果和預期不同。'
            elif '#fake-reverse' in text:
                wanted = [c['value'] for c in action.get('intent', {}).get('constraints', []) if c.get('polarity') == 'do' and c.get('value') in self.REVERSED]
                effect = FAKE_MARK + (self.REVERSED[wanted[0]] if wanted else '你的行動帶來意料之外的結果。')
            if 'player_action' in properties['action_resolution'].get('properties', {}):
                resolution = {'player_action': player_action, **resolution}
            reply = {'action_resolution': resolution, 'action_effect': effect, **reply}
        return TextResult(text=json.dumps(reply, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)


    # ---- F06A：人物演繹假回應。只依送來的資料組出確定性結果，資料越多、引用越多、不確定項目越少；全部標示測試用。 ----
    PORTRAYAL_TOPICS = (('性格', 'traits'), ('經歷', 'motivations'), ('行為習慣', 'behaviors'), ('說話方式', 'speaking_style'),
                        ('互動細節', 'values'))

    def _person_profile(self, payload):
        """人物設定：保留既有設定、空白欄位以標示過的範例補上。guidance 含 #fake-fail／#fake-invalid 時模擬失敗。"""
        guidance = str(payload.get('guidance') or '')
        if '#fake-fail' in guidance:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        name = str(payload.get('person', {}).get('name') or '這位人物')[:40]
        current = payload.get('current_profile') or {}
        keys = ('background', 'personality', 'motivation', 'stance', 'abilities', 'expression', 'behavior', 'knowledge_boundary', 'restrictions')
        profile = {key: str(current.get(key) or FAKE_MARK + name + '的' + key + '候選')[:500] for key in keys}
        if '#fake-invalid' in guidance:
            profile.pop('stance')
        return TextResult(text=json.dumps(profile, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _portrayal(self, payload):
        """依 materials 的分類填入對應欄位並引用代號；缺少的分類寫進 uncertainties。人物名稱含 #fake-fail／#fake-invalid 時模擬失敗。"""
        name = str(payload.get('person', {}).get('name') or '這位人物')[:40]
        if '#fake-fail' in name:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        materials = payload.get('materials') or []

        def item(entry):
            return {'text': FAKE_MARK + str(entry.get('text', ''))[:50], 'basis': [entry['ref']]}

        grouped = {field: [] for _, field in self.PORTRAYAL_TOPICS}
        others = []
        for entry in materials:
            label = str(entry.get('label', ''))
            field = next((target for topic, target in self.PORTRAYAL_TOPICS if topic in label), None)
            if entry.get('kind') == 'fact':
                field = 'behaviors' if '習慣' in label else 'traits'
            (grouped[field] if field else others).append(entry)
        guess = lambda text: {'text': FAKE_MARK + text, 'basis': []}  # 沒有依據的推測
        style = grouped['speaking_style']
        profile = {
            'summary': FAKE_MARK + f'{name}：依 {len(materials)} 項選取資料推演的人物詮釋（不是本人）。',
            'traits': [item(e) for e in grouped['traits'][:5]] or [guess('資料不足，只能推測個性偏穩重。')],
            'motivations': [item(e) for e in grouped['motivations'][:3]] or [guess('資料不足，推測重視把事情做好。')],
            'values': [item(e) for e in grouped['values'][:3]],
            'speaking_style': item(style[0]) if style else guess('缺少說話方式資料，暫以平穩語氣推測。'),
            'behaviors': [item(e) for e in grouped['behaviors'][:4]],
            'emotional_reactions': [item(e) for e in others[:3]],
            'knowledge_boundary': FAKE_MARK + f'只依使用者選取的 {len(materials)} 項資料；資料以外的經歷一律不知道。',
            'uncertainties': [f'缺少{topic}資料' for topic, field in self.PORTRAYAL_TOPICS if not grouped[field]][:5],
            'sample_dialogues': [{'situation': '日常聊天', 'line': FAKE_MARK + (f'（依{style[0]["ref"]}）' + str(style[0].get('text', ''))[:30] if style else '嗯，我想一下再回你。')}],
        }
        if '#fake-invalid' in name:
            profile['traits'] = [{'text': FAKE_MARK + '引用不存在的資料', 'basis': ['f99']}]  # 驗證伺服器拒絕不存在的依據
        return TextResult(text=json.dumps(profile, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)

    def _portrayal_reply(self, payload):
        """互動試演假回應：依情境與使用者訊息組句，引用人物詮釋中第一個有依據的代號；訊息含 #fake-fail 時模擬故障。"""
        turn = payload.get('turn', {})
        message = str(turn.get('message', ''))
        if '#fake-fail' in message:
            raise ProviderFailure('provider_error')
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000)
        person = payload.get('person', {})
        profile = person.get('profile', {})
        refs = [entry['ref'] for entry in payload.get('materials') or []]
        style = str(profile.get('speaking_style', {}).get('text', ''))[:30]
        scenario = payload.get('scenario', {}).get('kind', '')
        reply = {'line': FAKE_MARK + f'（{scenario}）關於「{message[:30]}」——{style or "我想想再說。"}',
                 'tone': '測試用：語氣平穩',
                 'basis': refs[:2],
                 'notes': FAKE_MARK + f'第 {turn.get("turn_no", 1)} 個來回；依人物詮釋推演，不是本人。'}
        return TextResult(text=json.dumps(reply, ensure_ascii=False), input_tokens=None, output_tokens=None, cost_microusd=None,
                          provider_request_id=None, model_version=self.model)


class NoRedirect(HTTPRedirectHandler):
    """不把金鑰標頭轉送到未核准的目的地。"""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def https_transport(endpoint, body, headers, timeout):
    """單次 POST；回應上限 128KB，超過視為不合格輸出。"""
    request = Request(endpoint, data=body, headers=headers, method='POST')
    with build_opener(NoRedirect).open(request, timeout=timeout) as response:
        payload = response.read(128001)
        if len(payload) > 128000:
            raise ProviderFailure('invalid_output', http_status=response.status)
        try:
            return json.loads(payload)
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ProviderFailure('invalid_output', http_status=response.status) from None


def emit_diagnostics(record):
    """一行 ASCII JSON 寫到 stdout；Cloud Run 會把 severity／message 與其他欄位解析成結構化日誌。"""
    sys.stdout.write(json.dumps(record, ensure_ascii=True, separators=(',', ':')) + '\n')
    sys.stdout.flush()


def _code(value):
    """finishReason／blockReason 只接受列舉格式，避免把回應中的任意文字寫進日誌。"""
    return value if isinstance(value, str) and re.fullmatch(r'[A-Z][A-Z_]{0,39}', value) else None


def _ident(value):
    return value if isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9._\-]{1,128}', value) else None


def _count(value):
    return value if type(value) is int and value >= 0 else None


def _error_info(exc):
    """HTTP 錯誤本文只取列舉代碼與訊息分類：status、ErrorInfo.reason，以及 api_key／schema／context_length。

    Gemini 對無效金鑰與請求格式錯誤都回 400，只看狀態碼無法分辨；訊息原文可能含使用者內容，一律不保存。
    """
    try:
        data = json.loads(exc.read(65536))
        error = data.get('error') if isinstance(data, dict) else None
        if not isinstance(error, dict):
            return None, None, None
    except Exception:
        return None, None, None
    reasons = [_code(item.get('reason')) for item in error.get('details') or [] if isinstance(item, dict)]
    reason = next((item for item in reasons if item), None)
    message = str(error.get('message') or '').lower()
    if reason == 'API_KEY_INVALID' or 'api key' in message or 'api_key' in message:
        hint = 'api_key'
    elif 'schema' in message or 'invalid json payload' in message:
        hint = 'schema'
    elif 'token' in message and any(word in message for word in ('exceed', 'limit', 'too long', 'maximum')):
        hint = 'context_length'
    else:
        hint = None
    return _code(error.get('status')), reason, hint


def _output_usage(candidates, thoughts):
    """記下已知的輸出與思考用量，兩者皆未回報時維持未知。"""
    return thoughts if candidates is None else candidates + (thoughts or 0)


class GeminiProvider:
    """Gemini Developer API generateContent；金鑰只放 x-goog-api-key 標頭，不放 URL、Log 或回應。

    真實模型相容性（responseJsonSchema、思考 Token 與輸出上限）以使用者核准的小樣本測試確認。
    F05C：每次 generate 留下一行診斷（是否送出、HTTP 狀態、finishReason、分項 Token、Provider 延遲、型號版本），
    不含金鑰、URL、Prompt、玩家輸入或模型輸出；用來核對實際呼叫次數與截斷原因。
    """
    name, kind = 'gemini', 'live'

    def __init__(self, model, *, key_supplier, transport=None, timeout_seconds=30, diagnostics=None, retry_delay_seconds=2.0):
        if not re.fullmatch(r'gemini-[a-z0-9][a-z0-9.\-]{0,100}', model):
            raise ValueError('Invalid Gemini model name')
        self.model = model
        self.endpoint = f'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
        self._key_supplier = key_supplier
        self._transport = transport or https_transport
        self._timeout = timeout_seconds
        self._diagnostics = diagnostics or emit_diagnostics
        self._retry_delay = retry_delay_seconds  # 503 重試前的等待秒數（測試設 0）

    def generate(self, request: TextRequest) -> TextResult:
        record = {'severity': 'INFO', 'message': 'lw_ai_provider_call', 'provider': self.name, 'model': self.model,
                  'max_output_tokens': request.max_output_tokens, 'sent': False, 'http_status': None, 'outcome': 'ok',
                  'provider_latency_ms': None, 'finish_reason': None, 'block_reason': None, 'candidates': None,
                  'prompt_tokens': None, 'candidates_tokens': None, 'thoughts_tokens': None, 'total_tokens': None,
                  'model_version': None, 'response_id': None, 'output_chars': None,
                  'error_status': None, 'error_reason': None, 'error_hint': None, 'retried_after': None}
        try:
            return self._generate(request, record)
        except ProviderFailure as exc:
            record['severity'], record['outcome'] = 'WARNING', exc.code
            if record['http_status'] is None:
                record['http_status'] = exc.http_status
            if record['http_status'] == 200:
                # 即使文字不合格，已回報的用量仍需保存，含僅回傳思考 Token 的截斷。
                exc.result = TextResult(text='', input_tokens=record['prompt_tokens'],
                                        output_tokens=_output_usage(record['candidates_tokens'], record['thoughts_tokens']),
                                        provider_request_id=record['response_id'], model_version=record['model_version'])
            raise
        finally:
            try:
                self._diagnostics(record)
            except Exception:
                pass  # 日誌失敗不影響生成結果

    @staticmethod
    def _observe(record, data, request, key):
        """只擷取列舉代碼、識別碼與整數用量；任何非預期結構都留空，不影響既有解析。"""
        def safe_metadata(value):
            # 識別碼格式也容許 ASCII 金鑰或玩家文字，不能把回顯當作診斷欄位。
            if value is None or key in value or value in request.system or value in request.user:
                return None
            return value

        try:
            candidates = data.get('candidates')
            record['candidates'] = len(candidates) if isinstance(candidates, list) else None
            first = candidates[0] if isinstance(candidates, list) and len(candidates) == 1 and isinstance(candidates[0], dict) else {}
            record['finish_reason'] = safe_metadata(_code(first.get('finishReason')))
            feedback = data.get('promptFeedback')
            record['block_reason'] = safe_metadata(_code(feedback.get('blockReason'))) if isinstance(feedback, dict) else None
            usage = data.get('usageMetadata') if isinstance(data.get('usageMetadata'), dict) else {}
            for field, usage_key in (('prompt_tokens', 'promptTokenCount'), ('candidates_tokens', 'candidatesTokenCount'),
                                     ('thoughts_tokens', 'thoughtsTokenCount'), ('total_tokens', 'totalTokenCount')):
                record[field] = _count(usage.get(usage_key))
            record['model_version'] = safe_metadata(_ident(data.get('modelVersion')))
            record['response_id'] = safe_metadata(_ident(data.get('responseId')))
        except Exception:
            pass

    def _generate(self, request, record):
        if not 1 <= request.max_output_tokens <= 2000:
            raise ProviderFailure('provider_unavailable')
        key = self._key_supplier()  # 通過 owner、registered 與額度檢查後才讀取
        if not isinstance(key, str) or not key.strip() or '\n' in key or '\r' in key:
            raise ProviderFailure('provider_unavailable')
        payload = {'systemInstruction': {'parts': [{'text': request.system}]},
                   'contents': [{'role': 'user', 'parts': [{'text': request.user}]}],
                   'generationConfig': {'maxOutputTokens': request.max_output_tokens, 'candidateCount': 1,
                                        'responseMimeType': 'application/json',
                                        'responseJsonSchema': request.response_schema}}  # 現行文件以 JSON Schema 指定結構化輸出
        record['sent'], started = True, time.monotonic()
        try:
            body, headers = json.dumps(payload, ensure_ascii=False).encode(), {'Content-Type': 'application/json', 'x-goog-api-key': key}
            try:
                data = self._transport(self.endpoint, body, headers, self._timeout)
            except HTTPError as first:
                # 2026-11-11：Gemini 回 503（UNAVAILABLE，服務暫時過載）時，同一次生成內等一下再試一次。
                # 503 不產生 Token，金額預留仍只有一次；只重試一次，其他狀態（429、400、401／403、500…）照原規則不重試。
                if first.code != 503:
                    raise
                record['retried_after'] = 503
                time.sleep(self._retry_delay)
                data = self._transport(self.endpoint, body, headers, self._timeout)
            record['http_status'] = 200  # 傳輸層只對 2xx 回傳本文
        except ProviderFailure:
            raise
        except HTTPError as exc:
            record['http_status'] = exc.code if type(exc.code) is int else None
            # 401／403 多為金鑰或權限設定問題；其餘狀態一律視為供應商故障。原文不回顯。
            # http_status 讓排程生成分辨 429（額度／速率）、401／403（Key）、404（模型）與 400；400 再依錯誤原因分辨金鑰、格式或長度。
            record['error_status'], record['error_reason'], record['error_hint'] = _error_info(exc)
            raise ProviderFailure('provider_unavailable' if exc.code in (401, 403) else 'provider_error',
                                  http_status=record['http_status'], reason=record['error_reason'] or record['error_hint']) from None
        except (socket.timeout, TimeoutError):
            raise ProviderFailure('provider_timeout') from None
        except URLError as exc:
            raise ProviderFailure('provider_timeout' if isinstance(exc.reason, TimeoutError) else 'provider_error') from None
        except Exception:
            raise ProviderFailure('provider_error') from None  # 不讓 URL、標頭或回應細節流入例外鏈
        finally:
            record['provider_latency_ms'] = int((time.monotonic() - started) * 1000)
        if isinstance(data, dict):
            self._observe(record, data, request, key)
        try:
            candidates = data.get('candidates') or []
            if len(candidates) != 1 or (data.get('promptFeedback') or {}).get('blockReason'):
                raise ProviderFailure('provider_refused')
            candidate = candidates[0]
            if candidate.get('finishReason') not in ('STOP', 'MAX_TOKENS'):
                raise ProviderFailure('provider_refused')  # SAFETY 等政策結束不重試
            text = ''.join(p['text'] for p in (candidate.get('content') or {}).get('parts', [])
                           if isinstance(p.get('text'), str) and not p.get('thought'))
            record['output_chars'] = len(text)  # 只記長度，不記內容
            if not text.strip() or len(text) > 20000:
                raise ProviderFailure('invalid_output')
            usage = data.get('usageMetadata') or {}

            def token(name):
                value = usage.get(name)
                if value is not None and (type(value) is not int or value < 0):
                    raise ProviderFailure('invalid_output')
                return value

            prompt_tokens, output_tokens, thoughts = token('promptTokenCount'), token('candidatesTokenCount'), token('thoughtsTokenCount')
            output_tokens = _output_usage(output_tokens, thoughts)
            # API 沒有直接回傳帳單金額，不捏造 0；成本狀態由服務層記為 unknown。
            return TextResult(text=text, input_tokens=prompt_tokens, output_tokens=output_tokens, cost_microusd=None,
                              provider_request_id=record['response_id'], model_version=record['model_version'])
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('invalid_output') from None


def build_provider(settings):
    """依設定建立 Provider；真實 Gemini 需同時具備型號與 LIFEWORLD_AI_LIVE_APPROVED=true。"""
    if settings.provider == 'fake':
        return FakeProvider(delay_ms=settings.fake_delay_ms, slow_seconds=settings.timeout_seconds + 15)
    if settings.provider == 'gemini' and settings.live_approved and settings.model:
        # Secret Manager 版本可能以換行結尾（本機啟動器會 Trim，Cloud Run 注入的環境變數不會）；只去首尾空白，內含換行仍拒絕。
        return GeminiProvider(settings.model, key_supplier=lambda: os.environ.get('LIFEWORLD_AI_API_KEY', '').strip(),
                              timeout_seconds=settings.timeout_seconds)
    return None  # 未設定或未授權：capabilities 回報 ai_available=false，生成端點回 503
