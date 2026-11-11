# 2026-11-10 自 8445（life-world-react-integrated/app/action_guard.py）原樣移植。
"""F05D Action Consistency Guard：把玩家行動解析成有限的明確約束，並在生成後做確定性檢查。

設計界線：
- 只處理可明確判斷的指令：左右、前進後退、靠近遠離、進入離開、接受拒絕、使用／不使用指定物品，
  以及「玩家沒選攻擊卻被寫成攻擊」「被擅自改用其他做法」「玩家被寫成自己改變主意」。其餘一律 unknown，不強迫解讀。
- 問句、假設與條件句不當作實際行動；同一軸出現互相衝突的值（先左後右、又左又右）只記錄、不硬性判定。
- F05D-2：三種結算狀態都檢查「玩家自己做了什麼」。executed 要照原意完成；blocked 不得替玩家執行另一個動作；
  modified 只能是外部因素改變結果，不能是玩家自己反向、改做法或改變主意。外部角色、環境與船隻被外力推動可以不同。
- 不嘗試用關鍵字取代語意理解：詞彙表刻意很小，命中時才拒絕；沒命中就放行。
所有函式都是純函式，不讀資料庫、不呼叫模型，結果可序列化並保存到生成紀錄。
"""
import re
import unicodedata

INTENT_VERSION = 'action-intent-v2'  # 解析結果格式版本，保存在 ai_generations.input_json（v2：攻擊同義詞、說明文字與玩家自述註記）
GUARD_VERSION = 'action-guard-v2'  # 檢查規則版本，違規時保存在 ai_generations.params_json（v2：三種狀態一致檢查）
MAX_CONSTRAINTS, MAX_NOTES = 8, 16

# 正規化：全形轉半形（NFKC）、移除格式控制字元（零寬字元等）與空白；換行視為分句。
# 只轉換本模組詞彙用到的簡體字，避免簡體輸入繞過檢查；不是完整的簡繁轉換。
SIMPLIFIED = str.maketrans('转进后远离绝应驶调击袭开枪剑没别头达迈动边侧弯并经实这们坚扬弃过还让杀斩斗变决',
                           '轉進後遠離絕應駛調擊襲開槍劍沒別頭達邁動邊側彎並經實這們堅揚棄過還讓殺斬鬥變決')


def normalize(text):
    """回傳只用於比對的文字；保存與顯示仍用原文。"""
    text = unicodedata.normalize('NFKC', str(text or '')).translate(SIMPLIFIED)
    text = re.sub(r'[\r\n]+', ',', text)
    return ''.join(ch for ch in text if not ch.isspace() and unicodedata.category(ch) != 'Cf')


# ---- 詞彙表：每個值只列少量明確的動作片語 ----
def _direction(side):
    verbs = '轉|偏|駛|移|拐|划|走|行|閃|避|靠|切|開|飛|游|跑|繞|彎|前進|前行|進|打|擺|扳'
    return [rf'(?:向|往|朝){side}(?:方|側|邊|手邊)?(?:{verbs})', rf'(?:向|往|朝){side}(?:方|側|邊)?(?=[,.!?;:。、]|$)',
            rf'{side}(?:轉|拐|彎)(?!角)', rf'(?:轉|偏|拐|駛|移|閃|靠|切)(?:向|往|到|至){side}', rf'{side}滿?舵', rf'靠{side}']


LEXICON = {
    'direction': {'left': _direction('左'), 'right': _direction('右')},
    'motion': {'forward': [r'前進', r'前行', r'挺進', r'推進', r'(?:向|往)前(?:走|衝|行|推|划|駛|移|跑|邁|進)', r'(?:向|往)前(?=[,.!?;:。、]|$)'],
               'backward': [r'後退', r'倒退', r'退後', r'撤退', r'後撤', r'(?:向|往)後(?:退|走|撤|移|跑|划|駛)', r'(?:向|往)後(?=[,.!?;:。、]|$)']},
    'distance': {'approach': [r'靠近', r'接近', r'走近', r'貼近', r'逼近', r'湊近', r'走向'],
                 'withdraw': [r'遠離', r'離遠', r'拉開距離', r'退開']},
    'passage': {'enter': [r'進入', r'走進', r'踏入', r'進去', r'闖入', r'潛入', r'鑽進', r'進到'],
                'exit': [r'離開', r'走出', r'退出', r'出去', r'撤離', r'逃出']},
    'consent': {'accept': [r'接受', r'答應', r'同意', r'應允', r'收下', r'允諾'],
                'reject': [r'拒絕', r'婉拒', r'回絕', r'謝絕']},
    # 刀劍拳的量詞本身沒有攻擊對象。保留打中、刺穿等動作及既有的對人破甲案例。
    'conduct': {'attack': [r'攻擊', r'襲擊', r'突襲', r'偷襲', r'開火', r'開槍', r'射擊', r'射殺', r'射箭', r'揮(?:劍|刀|拳)', r'拔(?:劍|刀|槍)',
                           r'(?:砍|刺|斬|劈|捅)(?:向|中|傷|殺|死|倒|穿)', r'一拳(?:打|砸)中', r'一[刀劍]斬斷(?:守衛|敵人|對方)',
                           r'(?:刺|砍|斬|擊)殺', r'殺(?:死|了)',
                           r'(?:擊|打)倒', r'毆打', r'痛打', r'揍', r'出拳', r'搏鬥', r'開戰']},
}
COMPILED = {axis: {value: re.compile('|'.join(patterns)) for value, patterns in values.items()} for axis, values in LEXICON.items()}
OPPOSITE = {'left': 'right', 'right': 'left', 'forward': 'backward', 'backward': 'forward', 'approach': 'withdraw',
            'withdraw': 'approach', 'enter': 'exit', 'exit': 'enter', 'accept': 'reject', 'reject': 'accept'}
LABELS = {'left': '向左', 'right': '向右', 'forward': '前進', 'backward': '後退', 'approach': '靠近', 'withdraw': '遠離',
          'enter': '進入', 'exit': '離開', 'accept': '接受', 'reject': '拒絕', 'attack': '攻擊'}
# 使用物品：只認明確的使用動詞；物品名稱取到常見動作字或標點為止，取不到就不建立約束（寧可漏判，不誤判）。
USE_VERB = r'(?:使用|動用|拿出|掏出|取出)'
ITEM_STOP = '來去照點打砍開向對朝往到在從給替幫為和與跟並然再撬劈割切敲推拉扔丟投射刺綁燒擋殺嚇救修,.!?;:。、的'
ITEM = re.compile(USE_VERB + r'([^' + re.escape(ITEM_STOP) + r']{1,6})')
# 玩家沒有選攻擊時，自由輸入出現這些非暴力做法才加上「不要替玩家攻擊」的約束。
NONVIOLENT = re.compile(r'調查|觀察|查看|檢查|搜查|詢問|打聽|談判|協商|說服|交涉|等待|躲藏')
REPLACED = re.compile(r'改用|改成|改為|轉而|改去|改往|改向')  # 敘事明說玩家換了做法
# 玩家自己改變主意：modified／blocked 的原因不能是這些；玩家輸入本身寫了改主意時才可照寫。
MIND = re.compile(r'改變了?(?:心意|主意|決定|想法)|改主意|轉念|反悔|回心轉意|變卦|改口|決定(?:改|放棄|不)|放棄了?(?:原本|原先|原來)?的?(?:計畫|決定|行動|念頭)')

# 否定：只看動作片語前 6 字內（同一子句）。先移除不是否定的慣用語與雙重否定，再以否定詞個數的奇偶判斷。
NOT_NEGATION = ('毫不猶豫', '毫不遲疑', '不假思索', '不顧一切', '不得不', '不能不', '不可不', '不是不', '並非不', '並非沒有', '沒有不', '非得',
                '不顧', '不斷', '不停', '不久', '不過', '不管', '不論', '不僅', '不只', '不但', '不如', '不妨', '不少', '不錯', '不同',
                '不安', '非常', '未來', '未知', '無論', '莫名', '特別', '分別', '區別', '別人', '告別', '個別', '識別', '別處')
NEGATION = re.compile(r'無法|未能|沒能|[不沒別勿未莫甭]')
WINDOW = 6
# 問句、假設、條件：整句不當作實際行動。
HYPOTHETICAL = re.compile(r'如果|假如|假設|假使|(?<![主重需])要是|萬一|倘若|若是|會怎樣|會怎麼樣|會如何|會發生什麼|會不會|能不能|可不可以|要不要|該不該|是否|嗎|呢')
SENTENCE = re.compile(r'[^。.!?]+[。.!?]*')
CLAUSE = re.compile(r'[^,;:、]+')
QUOTED = re.compile(r'「[^」]*」|『[^』]*』|"[^"]*"|“[^”]*”')
PLAYER = re.compile(r'你們|你|您|玩家')
INPUT_PLAYER = re.compile(r'我(?:們)?|你們|你|您|玩家')
CONTROLLED_VESSEL = re.compile(r'(?:你們|你|您)的(?:船|小船|小艇)|(?:船頭|船身|船舵|舵輪|小船|小艇)(?![上旁的])|^船(?=$|並|沒|無|不|仍|開始|慢|緩|在)')
THIRD_PARTY = re.compile(r'敵人|敵船|敵艦|敵軍|追兵|對方|對手|守衛|商人|船商|海鷗|風向|風勢|另一艘|別艘|別人|他們|她們|牠們|(?<!其)[他她牠]')
HEARD_SPEECH = re.compile(rf'(?:聽完|聽見|聽到)(?:{PLAYER.pattern}|{THIRD_PARTY.pattern})說的話')
CONTINUATION = re.compile(r'接著|隨即|然後|再')
NPC_FACT = re.compile(r'既然|看見|看到|目睹|剛才|方才|已經|(?:了|過)(?!解|結|去)')
NPC_ADVICE = re.compile(r'^[「『"“]*(?:請|快|別|不要|建議|務必)|(?:建議|希望|要求)(?:你|您)|(?:你|您)(?:應該|可以|最好|必須|不妨|不要)')
PLAYER_CHOICE = re.compile(rf'(?:{PLAYER.pattern})(?:自己|自行|主動|決定|選擇)')
# 主詞判定：「向你、把你」的你是受詞，「你的」是所有格；「你被…砍中、你遭到拒絕」的玩家是受事者（被迫仍算玩家自己做）。
OBJECT_MARK = '向對朝往把將給替'
PASSIVE_MARK = re.compile(r'被(?!迫)|遭(?:到|受|$)|受到|挨了?|遭(?=一[刀劍拳]|射|砍|刺|攻|襲|擊|殺|拒)')
# 外力造成的位移：modified／blocked 時「浪把你推向右、落石逼你退出」是結果，不是玩家的決定（只用於移動類的軸）。
FORCED = re.compile(r'被迫|(?:逼|迫使|使|令|讓|推|沖|捲|震|拖|拽|甩|擠|吹|颳|撞|帶|把|將)(?:得|著)?(?:你們|你|您|玩家)')
# 用具體證據判斷常見外力。原因句型無法分類時維持保守，不把詞表當成可用外力的白名單。
EXTERNAL_FACTOR = r'(?:風浪|浪頭|橫浪|暗流|海流|水流|潮水|逆流|強風|陣風|落石|岩石|纜繩|浮冰)'
EXTERNAL_FORCE = re.compile(rf'因(?:為)?{EXTERNAL_FACTOR}|{EXTERNAL_FACTOR}.{{0,10}}?(?P<verb>推|卡|纏|擋|撞|逼|迫使|吹|捲|拖|甩|干擾)')
VESSEL_TARGET = re.compile(r'船|舵|航[向線]|[左右]舷')
HELM_ACTION = re.compile(r'(?:向|往|朝)[左右](?:打|扳|轉)舵')
VAGUE_CAUSE = re.compile(r'(?:局勢有變|情況有變|情勢有變|狀況有變|原因不明|沒有具體外力說明|不明原因|未說明原因)[。.!]*')
MOVEMENT = ('direction', 'motion', 'distance', 'passage')
PRESENCE_AXES = ('direction', 'motion', 'distance', 'passage', 'consent', 'item')  # player_action 必須明寫的軸
STATUSES = ('executed', 'blocked', 'modified')


def _negated(prefix):
    window = prefix
    for phrase in NOT_NEGATION:
        window = window.replace(phrase, '·' * len(phrase))  # 等長替換，不改變 6 字窗口的位置
    return len(NEGATION.findall(window[-WINDOW:])) % 2 == 1


def _sentences(text):
    for match in SENTENCE.finditer(text):
        sentence = match.group()
        yield sentence, sentence.rstrip('!.。').endswith('?') or bool(HYPOTHETICAL.search(sentence))


def _agents(prefix, player):
    """主詞位置的玩家稱呼：排除受詞（向你、把你…）與所有格（你的…）。"""
    return [m for m in player.finditer(prefix)
            if (m.start() == 0 or prefix[m.start() - 1] not in OBJECT_MARK) and not prefix.startswith('的', m.end())]


def _not_player(prefix, player, axis):
    """動作片語前最後的主詞是第三方，或玩家是被動句的受事者（只看攻擊與接受拒絕）時回傳 True。"""
    prefix = HEARD_SPEECH.sub('', prefix)  # 「聽完你說的話」中的你不是後面動作的主詞
    agents = _agents(prefix, player)
    third = _agents(prefix, THIRD_PARTY)
    if third and not any(m.start() >= third[-1].end() for m in agents):
        return True
    if axis in ('conduct', 'consent'):
        return bool(PASSIVE_MARK.search(prefix, agents[-1].end() if agents else 0))
    return False


def _has_nonviolent_action(text):
    # 只有確定要做的調查等行動才產生隱含的避免攻擊約束。
    return any(not _negated(clause[:match.start()]) and not _not_player(clause[:match.start()], INPUT_PLAYER, 'other')
               for sentence, hypothetical in _sentences(text) if not hypothetical
               for clause in CLAUSE.findall(sentence) for match in NONVIOLENT.finditer(clause))


def _said_by_player(pattern, text):
    """玩家自己的輸入（非問句）是否寫了改用或改主意；有寫就不把敘事照寫當成擅改。"""
    return any(not _negated(clause[:match.start()]) and not _not_player(clause[:match.start()], INPUT_PLAYER, 'other')
               for sentence, hypothetical in _sentences(text) if not hypothetical
               for clause in CLAUSE.findall(sentence) for match in pattern.finditer(clause))


def _mentions(text, item=None, inherit_player=False):
    """回傳 (axis, value, negated, clause, start, hypothetical) 的動作片語命中清單。"""
    found = []
    item_pattern = ITEM if item is None else re.compile(r'(?:使用|動用|拿出|掏出|取出|用)' + re.escape(item))
    for sentence, hypothetical in _sentences(text):
        previous_player = False
        for clause in CLAUSE.findall(sentence):
            matches = [(axis, value, match) for axis, values in COMPILED.items()
                       for value, pattern in values.items() for match in pattern.finditer(clause)]
            matches += [('item', match.group(1) if item is None else item, match) for match in item_pattern.finditer(clause)]
            for axis, value, match in matches:
                start = match.start()
                prefix = clause[:start]
                # 只延續同一句、連接詞後緊接動作的玩家主詞，避免把下一個明寫的主詞也歸給玩家。
                if previous_player and CONTINUATION.fullmatch(prefix):
                    found.append((axis, value, False, '你' + clause[start:], 1, hypothetical))
                else:
                    found.append((axis, value, _negated(prefix), clause, start, hypothetical))
            if inherit_player:
                previous_player = bool(_agents(clause, PLAYER)) and not _not_player(clause, PLAYER, 'conduct')
    return found


def _constraint(axis, value, polarity, implicit=False):
    if implicit:
        meaning = '玩家沒有選擇攻擊，不要替玩家發動攻擊'
    else:
        label = f'使用「{value}」' if axis == 'item' else LABELS[value]
        meaning = ('玩家要' if polarity == 'do' else '玩家不要') + label
    return {'axis': axis, 'value': value, 'polarity': polarity, 'meaning': meaning}


def parse_intent(action, description=''):
    """把伺服器已確認的行動（resolved_action）轉成約束。

    action: {'kind': 'choice'|'free', 'text': ..., 'strategy': ...}；選項文字來自伺服器保存的上一回合或故事開場，不採信前端。
    description: 選項說明；只補充標籤沒有涵蓋的軸。
    回傳 {'version','source','status','constraints','notes'}；status 只有 explicit／unknown，沒有約束就是 unknown。
    """
    source = action.get('kind', 'free')
    texts = [normalize(action.get('text', ''))] + ([normalize(description)] if source == 'choice' and description else [])
    collected, notes = {}, set()
    for index, text in enumerate(texts):
        seen = {}
        if any(hypothetical for _, hypothetical in _sentences(text)):
            notes.add('hypothetical')
        for axis, value, negated, clause, start, hypothetical in _mentions(text):
            if hypothetical or _not_player(clause[:start], INPUT_PLAYER, axis):
                continue
            seen.setdefault(axis, set()).add((value, 'avoid' if negated else 'do'))
        for axis, pairs in seen.items():
            if not (index and axis in collected):  # 說明文字只補標籤沒有的軸
                collected[axis] = pairs
                if index:
                    notes.add('from_description:' + axis)  # 模型照抄的是選項標籤，這些軸不要求寫進 player_action
    if _said_by_player(REPLACED, texts[0]):
        notes.add('player_text:replaced')
    if _said_by_player(MIND, texts[0]):
        notes.add('player_text:changed_mind')
    constraints = []
    for axis, pairs in collected.items():
        wanted = {value for value, polarity in pairs if polarity == 'do'}
        avoided = {value for value, polarity in pairs if polarity == 'avoid'}
        # 同一軸要兩個值（先左後右、又左又右），或同一值又要又不要：只記錄，不硬性判定。物品可以同時用好幾樣。
        if (axis != 'item' and len(wanted) > 1) or wanted & avoided:
            notes.add('conflict:' + axis)
            continue
        constraints += [_constraint(axis, value, polarity) for value, polarity in sorted(pairs)]
    if len({c['axis'] for c in constraints}) > 1:
        notes.add('sequence')
    # 玩家選了非攻擊的選項，或自由輸入明寫調查、談判等做法：加上「不要替玩家攻擊」，對應「調查被改成攻擊」。
    attack_strategy = source == 'choice' and COMPILED['conduct']['attack'].search(normalize(action.get('strategy', '')))
    implied = source == 'choice' or _has_nonviolent_action(texts[0])
    if implied and not attack_strategy and 'conduct' not in collected:
        constraints.append(_constraint('conduct', 'attack', 'avoid', implicit=True))
        notes.add('implicit:strategy')
    constraints = sorted(constraints, key=lambda c: (c['axis'], c['value'], c['polarity']))[:MAX_CONSTRAINTS]
    return {'version': INTENT_VERSION, 'source': source, 'status': 'explicit' if constraints else 'unknown',
            'constraints': constraints, 'notes': sorted(notes)[:MAX_NOTES]}


def _has_external_force(clause):
    """只把肯定的因果片語當成外力證據。呼叫端已排除假設句。"""
    return any(not _negated(clause[:match.start('verb') if match['verb'] else match.start()])
               for match in EXTERNAL_FORCE.finditer(clause))


def _external_movement(prefix, status, has_cause):
    """把有外力的位移與玩家自己操作區分開。"""
    forced = FORCED.search(prefix)
    if status != 'executed' and forced:
        if PLAYER_CHOICE.search(prefix):
            return False
        if forced.group() == '被迫':
            return has_cause
        return bool(forced.start() and not _agents(prefix[:forced.start()], PLAYER))
    agents = _agents(prefix, PLAYER)
    return _has_external_force(prefix) and (not agents or bool(PASSIVE_MARK.search(prefix, agents[-1].end())))


def _attributed(axis, field, clause, start, status, has_cause=False, v3=False):
    """這個動作片語是否歸給玩家自己。

    - player_action 欄位本身就是玩家的動作，不要求主詞（但排除明確的第三方）。
    - executed：方向可由玩家、玩家的船或行動效果開頭的動作承擔（F05C「船頭向右偏移」）；其他軸要求 6 字內的玩家主詞。
    - blocked／modified：檢查玩家主詞；另由 check 區分具體外力與未交代原因的反向船隻效果。
    """
    prefix = clause[:start]
    if _not_player(prefix, PLAYER, axis):
        return False
    if axis in MOVEMENT:
        external = _external_movement(prefix, status, has_cause) if v3 else status != 'executed' and FORCED.search(prefix)
        if external:
            return False
    prefix = HEARD_SPEECH.sub('', prefix)
    agents = _agents(prefix, PLAYER)
    if field == 'player_action':
        return bool(agents or not CONTROLLED_VESSEL.search(prefix))
    if axis == 'direction':
        if field == 'action_effect' and not prefix and (status == 'executed' or (v3 and HELM_ACTION.match(clause))):
            return True
        if status == 'executed' and field in ('scene', 'action_effect') and CONTROLLED_VESSEL.search(prefix):
            return True
        return bool(agents)
    return any(m.start() >= len(prefix) - WINDOW for m in agents)


def _npc_assertion(clause):
    return bool(NPC_FACT.search(clause) and not NPC_ADVICE.search(clause))


def _player_phrase(pattern, text, field):
    """改用、改主意等片語由玩家主詞發出時回傳 True；問句與第三方除外。"""
    for sentence, hypothetical in _sentences(text):
        if hypothetical:
            continue
        for clause in CLAUSE.findall(sentence):
            if field == 'npc_line' and not _npc_assertion(clause):
                continue
            for match in pattern.finditer(clause):
                prefix = clause[:match.start()]
                if _negated(prefix) or _not_player(prefix, PLAYER, 'other'):
                    continue
                if field == 'player_action' or any(m.start() >= len(prefix) - WINDOW for m in _agents(prefix, PLAYER)):
                    return True
    return False


def check(intent, output):
    """回傳違規代碼清單（axis:kind@field），空清單表示通過。只在意圖為 explicit 時檢查。

    三種狀態都檢查（F05D-2）：
    - reversed：玩家自己做了相反值；violated_avoid：玩家做了不要的事；action:replaced：玩家被寫成改用其他做法；
      action:player_changed：玩家被寫成自己改變主意（含 blocked／modified 的原因）。
    - denied（玩家要 V 卻寫成沒做到）只在 executed 判定；blocked／modified 本來就可能沒做到。
    - unstated：v3 的 player_action 沒有寫出玩家原本的動作（executed／modified 要正向寫出，blocked 寫出嘗試即可）。
    問句與假設句、場景與效果中的引號內話語不算已發生的動作。v2 形狀沒有 player_action，只檢查其他欄位。
    """
    resolution = (output or {}).get('action_resolution') or {}
    status = resolution.get('status')
    if not intent or intent.get('status') != 'explicit' or status not in STATUSES:
        return []
    notes = set(intent.get('notes', []))
    texts = {'reason': QUOTED.sub('', normalize(resolution.get('reason', '')))}
    for field in ('action_effect', 'scene', 'npc_line'):
        text = normalize(output.get(field, ''))
        texts[field] = text if field == 'npc_line' else QUOTED.sub('', text)  # 敘事中的引號內容是某人的話，不是已發生的事
    action_fields = ('action_effect', 'scene')
    v3 = 'player_action' in resolution
    if v3:
        texts['player_action'] = normalize(resolution['player_action'])  # 可引用玩家原話，不移除引號
        action_fields = ('player_action',) + action_fields
    # reason 與事實型台詞要和 v3 玩家行動相符。v2 在途輸出保留原有台詞檢查範圍。
    narrative_fields = action_fields + (('reason', 'npc_line') if v3 else ())
    causal_clauses = []
    named_cause = False
    vague_cause = False
    if v3 and status != 'executed':
        named_cause = bool(re.fullmatch(EXTERNAL_FACTOR + r'[。.!]*', texts['reason']))
        vague_cause = bool(VAGUE_CAUSE.fullmatch(texts['reason']))
        causal_clauses = [clause for field in ('reason', 'action_effect', 'scene')
                          for sentence, hypothetical in _sentences(texts[field]) if not hypothetical
                          for clause in CLAUSE.findall(sentence) if _has_external_force(clause)]
    has_cause = bool(named_cause or causal_clauses)
    has_vessel_cause = named_cause or any(VESSEL_TARGET.search(clause) for clause in causal_clauses)
    unexplained = []
    violations = []
    for constraint in intent['constraints']:
        axis, value, polarity = constraint['axis'], constraint['value'], constraint['polarity']
        fields = narrative_fields + (('npc_line',) if not v3 and axis == 'consent' else ())
        for field in fields:
            hits = _mentions(texts[field], item=value if axis == 'item' else None, inherit_player=v3 and field in ('scene', 'action_effect'))
            for hit_axis, hit_value, negated, clause, start, hypothetical in hits:
                if hypothetical or hit_axis != axis:
                    continue
                if v3 and field == 'npc_line' and not _npc_assertion(clause):
                    continue
                if polarity == 'avoid':
                    kind = 'violated_avoid' if hit_value == value and not negated else None
                else:
                    kind = ('reversed' if hit_value == OPPOSITE.get(value) and not negated else
                            'denied' if hit_value == value and negated and status == 'executed' else None)
                if kind:
                    if _attributed(axis, field, clause, start, status, has_cause, v3):
                        violations.append(f'{axis}:{kind}@{field}')
                    elif (vague_cause and not has_vessel_cause and axis == 'direction' and kind == 'reversed'
                          and field in ('action_effect', 'scene') and CONTROLLED_VESSEL.search(clause[:start])
                          and not _not_player(clause[:start], PLAYER, axis)):
                        unexplained.append(f'direction:unexplained_effect@{field}')
    if v3:  # 動作片語必須屬於玩家，命中第三方動作不足以證明玩家已行動。
        described = {n.split(':', 1)[1] for n in notes if n.startswith('from_description:')}
        for constraint in intent['constraints']:
            axis, value = constraint['axis'], constraint['value']
            if constraint['polarity'] != 'do' or axis not in PRESENCE_AXES or axis in described:
                continue
            hits = _mentions(texts['player_action'], item=value if axis == 'item' else None)
            if not any(a == axis and v == value and not hyp and (status == 'blocked' or not neg)
                       and _attributed(axis, 'player_action', clause, start, status, has_cause, v3)
                       for a, v, neg, clause, start, hyp in hits):
                violations.append(f'{axis}:unstated@player_action')
    if 'player_text:replaced' not in notes:
        violations += [f'action:replaced@{field}' for field in narrative_fields if _player_phrase(REPLACED, texts[field], field)]
    if 'player_text:changed_mind' not in notes:
        mind_fields = narrative_fields if v3 else action_fields + ('reason',)
        violations += [f'action:player_changed@{field}' for field in mind_fields if _player_phrase(MIND, texts[field], field)]
    if not violations and vague_cause:
        violations.extend(unexplained)
        if not violations and not has_cause:
            violations.append('action:unexplained_cause@reason')
    return sorted(set(violations))
