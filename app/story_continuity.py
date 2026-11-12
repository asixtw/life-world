"""多章節作品的劇情繼承：把已保存的一章整理成下一章要帶著的內容（檢查點）。

全部取自已保存的規劃與段落，不呼叫模型：
- 各章大綱：規劃時模型寫的標題、前提與每個節拍要推進的事，加上那一章使用者寫的場景與條件（故事裡已經成立的設定）。
- 上一章結尾：最後幾段的說話者、台詞與動作，並記下當時誰在場。
- 每位人物：最後的狀態（情緒、立場、目標）與累積的記憶。

隔離規則和單一章節相同：記憶與狀態只交給那一位人物自己；上一章結尾只給當時在場的人看。
這個模組只有純函式，不讀寫資料庫，也不依賴生成引擎（引擎與多章節作品服務都會用到它）。
"""

MEMORY_LIMIT = 12  # 每位人物帶到下一章的記憶則數（與單一章節內的上限相同）
TAIL_SEGMENTS = 6  # 上一章結尾帶幾段到下一章
SCENE_LIMIT = 1000  # 每一章帶到後面章節的場景描述字數上限（章節多了以後，每次呼叫都會帶著全部的大綱）


def identity(member):
    """人物在整部作品裡的固定代號。陣容代號（c1、c2…）每一章重新編，不能跨章使用。"""
    if member['source'] == 'self':
        return 'self'
    if member['source'] == 'person':
        return 'person:' + member['person_id']
    return 'card:' + member['work_id']


def episode_outline(number, plan, scene=None):
    """一章的大綱：章節編號、規劃時寫下的標題、前提、節拍目標，以及那一章使用者寫的場景與條件。

    scene 是那一章的場景設定（description、conditions）。它是使用者寫的、故事裡已經成立的設定；
    2026-11-12 實測只帶模型寫的前提時，後面的章節會說出和它相反的事實，所以一起帶下去。沒有給 scene 時不放這兩個欄位（舊資料相容）。
    """
    outline = {'no': number, 'title': plan['title'], 'premise': plan.get('premise', ''), 'beats': [beat['goal'] for beat in plan['beats']]}
    description = ((scene or {}).get('description') or '').strip()
    if description:
        outline['scene'] = description[:SCENE_LIMIT]
    conditions = [item for item in ((scene or {}).get('conditions') or []) if item]
    if conditions:
        outline['conditions'] = conditions
    return outline


def checkpoint(cast, turns, previous=None):
    """把一章整理成檢查點。cast 是這一章的陣容，turns 是這一章已保存的段落，previous 是前一個檢查點（第 1 章沒有）。

    人物這一章沒有發言時沿用前一個檢查點的狀態；記憶接在前面各章之後，只留最近 MEMORY_LIMIT 則。
    """
    keys = {member['id']: identity(member) for member in cast}
    names = {member['id']: member['name'] for member in cast}
    before = (previous or {}).get('characters') or {}
    characters = {}
    for member in cast:
        key = keys[member['id']]
        earlier = before.get(key) or {}
        own = [turn for turn in turns if turn['speaker_ref'] == member['id']]
        memories = list(earlier.get('memories') or []) + [item for turn in own for item in turn['output'].get('memory', [])]
        characters[key] = {'name': member['name'], 'state': own[-1]['output']['state'] if own else earlier.get('state'),
                           'memories': memories[-MEMORY_LIMIT:]}
    last_scene = [{'speaker': names[turn['speaker_ref']], 'line': turn['output']['line'], 'action': turn['output']['action'],
                   'witnesses': [keys[item] for item in turn['witnesses'] if item in keys]} for turn in turns[-TAIL_SEGMENTS:]]
    return {'last_scene': last_scene, 'characters': characters}


def story_so_far(continuity, who=None):
    """交給模型的「先前劇情」：各章大綱與上一章結尾。

    who 是發言人物的固定代號：只給他當時在場看到的段落；who 為 None（規劃階段）時給全部。
    這一章不是續寫的（continuity 為空）就回 None，呼叫端不放這個欄位。
    """
    if not continuity:
        return None
    scene = [{'speaker': item['speaker'], 'line': item['line'], 'action': item['action']}
             for item in continuity['last_scene'] if who is None or who in item['witnesses']]
    return {'episodes': continuity['episodes'], 'last_scene': scene}


def carried(continuity, who):
    """這位人物從前面章節帶過來的（記憶, 狀態）；沒有就是（[], None）。"""
    character = ((continuity or {}).get('characters') or {}).get(who) or {}
    return list(character.get('memories') or []), character.get('state')
