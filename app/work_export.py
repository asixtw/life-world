"""作品匯出：把已完成的作品組成可以離線開啟的單一 HTML 檔（純文字；單一作品或多章節作品的合集）。

所有作品之後都以「可下載的 HTML」交付，這個模組是共用的主幹：
    已保存的劇情（資料庫）＋ 固定的播放器（app/export_player）→ 打包 → 存進物件儲存 → 留下匯出紀錄 → 下載。

設計原則：
- 匯出不呼叫模型。內容全部來自已保存的作品與段落；播放器是固定程式，不是每次生成。
- 可重現：同一個作品版本配同一個播放器版本，產出的檔案逐位元相同（檔案裡不寫匯出時間）。
  物件名稱用內容雜湊，相同內容只存一份、只記一筆。
- 離線可用：不引用任何外部資源；內嵌的樣式與程式以 CSP 雜湊鎖定，其餘一律不允許載入或執行。
  內容直接寫成 HTML（不靠程式繪製），所以不能執行程式的預覽工具也讀得到；程式只處理閱讀偏好。
- 檔案裡只有作品本身：標題、各章的類型、前提與場景、人物名稱與角色定位、每一幕的幕名、逐段內容、下集預告。
  不放人物設定、我的設定、公開簡介、演出要求、場景條件、人物的記憶，或任何識別碼；
  規劃裡給生成用的內容（每一幕誰在場、發言順序）也不放。
- 兩種播放器，同一件作品可以各匯出一份（請求的 player 決定；不給就是閱讀版）：
  閱讀版（reader-3，劇情資料 lw-story.v3）是整篇文章；人物的狀態與只給單一人物的筆記（底牌）會劇透，閱讀版從頭到尾不讀、不輸出。
  互動版（play-2，劇情資料 lw-play.v2）一次看一段，多帶已經保存、原本沒有給讀者看的東西：每一段之後那位人物的狀態
  （真心話：選一個人的視角入局，他的直接看得到，別人的只能偷看幾次）、每位人物的底牌（預設收合），以及作品的互動層
  （content['interactive']，另一個模組生成、可能不存在）：關鍵抉擇與另外兩個結局、藏在原文裡的線索詞、各陣營的番外、給讀者的一句提問。
  內容一樣完整寫在頁面裡；逐段揭開、偷看、找線索、抉擇由內嵌的程式處理。沒有互動層的作品照樣有視角與限次偷看，只是沒有抉擇與線索。
  互動版是另外加上去的：閱讀版的輸出不因為有互動版、有互動層而多出任何東西（位元組不變）。
  （play-1 是前一版：真心話是整頁的總開關、沒有抉擇，選邊只顯示一行字；已經匯出的檔案不受影響。）
- 人物眾多時要分得出個人、團體與關鍵情節（reader-3）：每位人物一個顏色（跨章不變）、陣營分組與標籤、
  每一幕的幕名與起承轉合（轉折特別標示）。這些都直接寫成 HTML 與樣式；舊作品的規劃沒有這些欄位，照原本的樣子匯出。
- 多章節作品只匯出已採納的章節（依主線順序），有目錄；還沒採納的草稿不在裡面。
- 匯出紀錄不改資料表：每個作品對應一個 kind='work_export' 的 works 列（識別碼由作品識別碼推導），
  每次內容不同的匯出新增一個版本；版本只增不改。
- 下載時核對擁有者，並比對檔案雜湊與紀錄；以附件送出並加上 sandbox，不會在本站的網域裡被當成頁面執行。
- 第三種播放器：路線播放器（route-1，內嵌資料 lw-route.v1），給回合制互動作品（works.kind='turn_game'、內容 game.v1）用。
  使用者在自己的回合選下一步，同行的角色各自反應、數值升降，最後依數值走到不同的結局。反應全部預先生成、寫在檔案裡，播放時不呼叫模型。
  這種作品只有這一種播放器（請求的 player 給什麼都是它）；生成完成（build.status='ready'）之後才能匯出。
  和前兩種不同，遊戲畫面由內嵌的程式依資料畫出來；沒有程式時頁面仍然列出開場白、同行的人與所有站，反應、願望與結局收在預設不展開的區塊。
- 站內直接看（GET …/exports/{版本}/view）：同一份檔案、不是附件，給本站的頁面放進 <iframe sandbox="allow-scripts">。
  只有這一條回應允許被同源的頁面框住，而且回應自己也帶 sandbox：就算被直接打開，裡面的程式也拿不到本站的登入狀態。
"""
import base64  # CSP 雜湊
import hashlib  # 檔案與 CSP 雜湊
import html  # 作品文字一律跳脫
import json  # 內嵌劇情資料、匯出紀錄
from pathlib import Path  # 固定播放器的檔案
import re  # 檔名清理
from typing import Literal
from urllib.parse import quote  # Content-Disposition 的 UTF-8 檔名
import uuid  # 匯出紀錄的固定識別碼

from fastapi import Request
from fastapi.responses import Response
from pydantic import Field

from .errors import DomainError, require
from .generation import encoded  # 與既有服務一致的穩定 JSON
from .object_storage import StorageError
from .roleplay import POSITION_LABELS, ROLEPLAY_KINDS, run_view
from .schemas import Model
from .story_continuity import identity  # 人物在整部作品裡的固定代號（跨章不變）
from .story_series import SERIES_KIND

# 播放器版本：內容或樣式有變就換新名稱，舊的匯出檔不受影響
# （reader-2：加上目錄與多章節；reader-3：人物顏色、陣營、幕名與轉折、下集預告）
PLAYER = 'reader-3'
_PLAYER_DIR = Path(__file__).parent / 'export_player'
READER_CSS = (_PLAYER_DIR / 'reader-3.css').read_text(encoding='utf-8').strip()
READER_JS = (_PLAYER_DIR / 'reader-3.js').read_text(encoding='utf-8').strip()
EXPORT_KIND, EXPORT_SCHEMA, STORY_FORMAT = 'work_export', 'work_export.v1', 'lw-story.v3'
EXPORT_NAMESPACE = uuid.UUID('5d0d7b0e-3f6a-4c56-9a43-6f1c2f7b9e10')  # 固定命名空間：由作品識別碼推導匯出紀錄的識別碼
HTML_MIME = 'text/html; charset=utf-8'
FALLBACK_FILENAME = 'life-world-work.html'
DISCLAIMER = '這是 AI 依人物設定生成的虛構演出，不代表真實人物或事實。'
PERSON_COLORS = 6  # 閱讀器準備了幾個人物顏色（reader-3.css 的 --c1 到 --c6）；人物比這個多就從頭循環
KIND_LABELS = {'setup': '起', 'rise': '承', 'turn': '轉', 'payoff': '合'}  # 這一幕在故事裡的作用 → 標題列上的小標籤

# 互動版播放器：和閱讀版並存，各自是完整的一份樣式與程式；版本規則相同（有變就換新名稱）
# （play-1：一次看一段、真心話總開關、讀完看底牌；play-2：選視角入局、限次偷看、線索、關鍵抉擇與三個結局、番外）
PLAY_PLAYER, PLAY_FORMAT = 'play-2', 'lw-play.v2'
PLAY_CSS = (_PLAYER_DIR / 'play-2.css').read_text(encoding='utf-8').strip()
PLAY_JS = (_PLAYER_DIR / 'play-2.js').read_text(encoding='utf-8').strip()
PLAY_SUFFIX = '（互動版）'  # 互動版的檔名接在標題後面，和閱讀版一起下載時分得出來
STATE_LABELS = (('emotion', '情緒'), ('stance', '立場'), ('goal', '目標'))  # 人物狀態的欄位 → 「真心話」上的標示（依這個順序）
ENDING_LABELS = {'true': '真結局', 'plain': '另一種結局', 'bad': '壞結局'}  # 抉擇選項的種類 → 那個結局的標示；不認得的種類不收
CLUE_FIELDS = ('line', 'action')  # 線索詞只會藏在台詞或動作裡
PEEKS_FOR_TWO, PEEKS_FOR_MORE = 2, 3  # 可以偷看別人真心話幾次：兩位人物以內 2 次，三位以上 3 次

# 路線播放器：回合制互動作品（第 1 期只有「行程」這一種題材）。和前兩種一樣是完整的一份樣式與程式，有變就換新名稱。
GAME_KIND, GAME_SCHEMA = 'turn_game', 'game.v1'  # 作品種類與內容格式（生成由另一個模組負責；這裡只讀已保存的內容）
ROUTE_PLAYER, ROUTE_FORMAT = 'route-1', 'lw-route.v1'
ROUTE_CSS = (_PLAYER_DIR / 'route-1.css').read_text(encoding='utf-8').strip()
ROUTE_JS = (_PLAYER_DIR / 'route-1.js').read_text(encoding='utf-8').strip()
ROUTE_SUFFIX = '（互動遊戲）'  # 檔名接在標題後面
BAND_LABELS = (('low', '不滿時'), ('mid', '普通時'), ('high', '有好感時'))  # 到站前的態度 → 用哪一句反應
ENDING_CLASS_LABELS = (('perfect', '完美結局'), ('great', '好結局'), ('ok', '普通結局'), ('poor', '遺憾結局'))  # 結局種類，由好到壞
# 站內直接看的路由（見 install）。app/main.py 的安全標頭中介層用它認出「唯一可以被同源頁面框住」的那一條回應。
VIEW_PATH = re.compile(r'/api/works/[^/]+/exports/\d+/view')


class WorkExportCreate(Model):
    request_id: str = Field(min_length=1, max_length=128)
    format: Literal['html'] = 'html'  # 目前只有單一 HTML 檔
    player: Literal['reader', 'play'] = 'reader'  # 閱讀版（預設；加入互動版之前的前端不送這個欄位）或互動版


def export_work_id(work_id):
    """作品的匯出紀錄放在哪一列：由作品識別碼推導，不需要另外的對照欄位或資料表。"""
    return str(uuid.uuid5(EXPORT_NAMESPACE, 'work_export:' + work_id))


def export_filename(title, suffix=''):
    """下載時的檔名：去掉作業系統不接受的字元與控制字元；清到沒有內容就用固定名稱。suffix 接在名稱後面（互動版用）。"""
    name = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]+', ' ', title or '')
    name = re.sub(r'\s+', ' ', name).strip(' .')[:80].strip(' .')
    return (name or FALLBACK_FILENAME[:-len('.html')]) + suffix + '.html'


def player_kind(name):
    """匯出紀錄裡的播放器版本名稱（reader-1、reader-3、play-1、play-2、route-1…）是哪一種：
    'play'（互動版）、'route'（互動遊戲的路線播放器）或 'reader'（閱讀版）。"""
    return 'play' if str(name).startswith('play-') else 'route' if str(name).startswith('route-') else 'reader'


def cast_key(member):
    """人物在整部作品裡的固定代號：顏色與陣營都跟著它，不跟著陣容代號。

    陣容代號（c1、c2…）每一章重新編，同一個代號在下一章可能是另一個人。多章節作品保存的陣容已經帶著固定代號（key）；
    單一作品的陣容由來源推導。很舊的資料推導不出來時退回用名稱（同一件作品裡名稱不會重複）。
    """
    if member.get('key'):
        return member['key']
    try:
        return identity(member)
    except KeyError:
        return 'name:' + member['name']


def cast_colors(cast):
    """每位人物的色號（1 到 PERSON_COLORS）：依整部作品的陣容順序，超過就循環。回傳 {固定代號: 色號}。"""
    return {cast_key(member): index % PERSON_COLORS + 1 for index, member in enumerate(cast)}


def chapter_sides(content):
    """這一章的陣營：{固定代號: 陣營名稱}。規劃裡沒有陣營（舊作品）就是空的。

    規劃用陣容代號列出每個陣營的成員，這裡換成固定代號。一個人只算第一個列到他的陣營；不在陣容裡的代號略過。
    規劃裡只給單一人物的筆記（private_notes）不在這裡讀：閱讀版從頭到尾不碰那個欄位，只有互動版的 chapter_secrets 會讀。
    """
    keys = {member['id']: cast_key(member) for member in run_view(content)['cast']}
    sides = {}
    for side in (content.get('plan') or {}).get('sides') or []:
        name = str(side.get('name') or '').strip()
        for cast_id in side.get('members') or []:
            if name and cast_id in keys:
                sides.setdefault(keys[cast_id], name)
    return sides


def cast_data(cast, colors, sides):
    """讀者看得到的陣容：名稱、角色定位、色號與陣營（沒有陣營是 None）。"""
    return [{'name': member['name'], 'role': POSITION_LABELS.get(member.get('position')),
             'color': colors[cast_key(member)], 'side': sides.get(cast_key(member))} for member in cast]


def segment_state(turn):
    """這一段之後那位人物的狀態（互動版的「真心話」）：{'emotion': 情緒, 'stance': 立場, 'goal': 目前目標}。

    生成每一段時模型一併回報、和段落一起保存的內容；這裡只是讀出來，不另外呼叫模型。
    三個欄位都是空的，或舊資料沒有這個欄位，回 None（頁面上那一段就沒有真心話）。
    """
    state = turn['output'].get('state')
    if not isinstance(state, dict):
        return None
    values = {key: str(state.get(key) or '').strip() for key, _ in STATE_LABELS}
    return values if any(values.values()) else None


def chapter_secrets(content, colors):
    """這一章每位人物的底牌（互動版讀完才看）：[{'who': 第幾位人物, 'name': 名稱, 'color': 色號, 'secret': 文字}]，依這一章的陣容順序。

    來源是規劃裡只給單一人物的筆記（private_notes）：生成時只交給本人，別的人物與讀者都看不到。
    只有互動版讀它，而且頁面上預設收合；閱讀版不呼叫這個函式。規劃用陣容代號指人，這裡換成整部作品的人物序號與色號。
    一位人物只取第一則；空白的、指到不在陣容裡的代號的都略過。舊作品沒有這個欄位就是空清單。
    """
    notes = {}
    for item in (content.get('plan') or {}).get('private_notes') or []:
        note = str(item.get('note') or '').strip()
        if note:
            notes.setdefault(item.get('id'), note)
    secrets = []
    for member in run_view(content)['cast']:
        if member['id'] in notes:
            key = cast_key(member)
            color = colors.setdefault(key, len(colors) % PERSON_COLORS + 1)  # 和段落一樣：萬一不在整部作品的陣容裡，接著往下編
            secrets.append({'who': list(colors).index(key) + 1, 'name': member['name'], 'color': color, 'secret': notes[member['id']]})
    return secrets


def _clean(value):
    """互動層裡的一段文字：不是字串就當成沒有；去掉前後的空白。"""
    return value.strip() if isinstance(value, str) else ''


def _records(value):
    """互動層裡的一個清單：只留字典形狀的項目。形狀不對的項目（或整個不是清單）略過，不讓匯出失敗。"""
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _decision_options(value):
    """抉擇的選項。規格是恰好三個、恰好一個真結局；回傳整理過的三個選項，不符合就回 None（整個抉擇不放，故事照原本的樣子讀到最後）。

    每個選項都要有代號（不重複）與文字；真結局以外的兩個要有結局的旁白——選了卻沒有內容可看，比沒有抉擇更糟。
    真結局就是原本生成的後續節拍，不需要旁白，資料裡有也不帶。
    """
    if not isinstance(value, list) or len(value) != 3 or not all(isinstance(item, dict) for item in value):
        return None
    options = [{'id': _clean(item.get('id')), 'label': _clean(item.get('label')), 'kind': _clean(item.get('kind')),
                'needs_clue': bool(item.get('needs_clue')), 'ending': _clean(item.get('ending'))} for item in value]
    kinds = [option['kind'] for option in options]
    if (kinds.count('true') != 1 or any(kind not in ENDING_LABELS for kind in kinds) or len({option['id'] for option in options}) != 3
            or not all(option['id'] and option['label'] for option in options)
            or not all(option['ending'] for option in options if option['kind'] != 'true')):
        return None
    for option in options:
        if option['kind'] == 'true':
            option['ending'] = ''
    return options


def chapter_interactive(content, beats, secrets, colors):
    """這一章的互動層（只有互動版讀）：關鍵抉擇、線索、番外、給讀者的提問。回傳整理過的資料；沒有或整理完是空的，回 None。

    來源是作品內容的 interactive（另一個模組在作品完成之後生成、寫進去；舊作品與還沒生成的作品沒有這個欄位）。
    那一份是模型產生的，這裡不假設它完整：每一項各自檢查，不能用的略過，其餘照常——互動層再怎麼不對，原本的故事都要讀得完。
    beats 是這一章已經整理好的節拍與段落（chapter_data 的結果），secrets 是這一章的底牌，colors 是整部作品的色號。
    回傳的形狀：
      decision：None，或 {'after_beat': 節拍號碼, 'after': 抉擇出現在哪一段之後（那個節拍最後一段的段號）,
                'actor': 做決定的人 {'who', 'name', 'color'} 或 None, 'question': 題目, 'options': 三個選項}。
      clues：[{'id', 'no': 段號, 'field': 'line' 或 'action', 'phrase': 原文裡的短詞, 'hint': 提示, 'who'／'name': 指向誰的底牌}]。
      epilogues：[{'side': 陣營名稱, 'text': 番外}]；question：給讀者的一句提問（沒有是空字串）。
    互動層自己的識別碼（schema、generation_id）不帶：檔案裡只有作品本身。規劃用陣容代號指人，這裡換成整部作品的人物序號。
    """
    layer = content.get('interactive')
    if not isinstance(layer, dict):
        return None
    people = {}  # 這一章的陣容代號 → 整部作品的人物序號、名稱與色號（和 chapter_secrets 同一套算法）
    for member in run_view(content)['cast']:
        key = cast_key(member)
        color = colors.setdefault(key, len(colors) % PERSON_COLORS + 1)
        people[member['id']] = {'who': list(colors).index(key) + 1, 'name': member['name'], 'color': color}
    segments = {segment['no']: segment for beat in beats for segment in beat['segments']}
    order = list(segments)  # 段號，依出場順序
    holders = {item['who'] for item in secrets}  # 這一章有底牌的人（人物序號）

    # 線索：短詞要在指定那一段的台詞或動作裡找得到，而且指向一位有底牌的人——線索的用處是拼出那個人的底牌。
    # 找不到、指錯人、沒有提示、代號重複的都略過；同一個欄位裡兩則線索的位置互相重疊時，後面那一則略過（包不出不交錯的標籤）。
    clues, taken, spans = [], set(), {}
    for item in _records(layer.get('clues')):
        clue_id, phrase, hint, field, number = _clean(item.get('id')), _clean(item.get('phrase')), _clean(item.get('hint')), item.get('field'), item.get('turn_no')
        owner = people.get(item['secret_of']) if isinstance(item.get('secret_of'), str) else None
        segment = segments.get(number) if type(number) is int else None
        if not (clue_id and phrase and hint) or clue_id in taken or field not in CLUE_FIELDS or segment is None or owner is None or owner['who'] not in holders:
            continue
        begin = str(segment[field] or '').find(phrase)  # 只認第一次出現的位置
        used = spans.setdefault((number, field), [])
        if begin < 0 or any(begin < last and first < begin + len(phrase) for first, last in used):
            continue
        used.append((begin, begin + len(phrase)))
        taken.add(clue_id)
        clues.append({'id': clue_id, 'no': number, 'field': field, 'phrase': phrase, 'hint': hint, 'who': owner['who'], 'name': owner['name']})

    # 抉擇：指定的節拍要在這一章裡、而且有段落（抉擇出現在它的最後一段之後）
    decision, raw = None, layer.get('decision')
    if isinstance(raw, dict):
        beat = next((item for item in beats if type(raw.get('after_beat')) is int and item['no'] == raw['after_beat']), None)
        options = _decision_options(raw.get('options'))
        if beat is not None and options:
            after = beat['segments'][-1]['no']
            # 「要先找到線索才能選」只有在抉擇之前真的有線索可以找時才算數。線索全部對不到原文、或都藏在抉擇之後的段落時，
            # 讀者永遠解不開，真結局（也就是原本的故事）會被鎖死——這種時候改成直接可以選。
            reachable = any(order.index(clue['no']) <= order.index(after) for clue in clues)
            for option in options:
                option['needs_clue'] = option['needs_clue'] and reachable
            actor = people.get(raw['actor']) if isinstance(raw.get('actor'), str) else None
            decision = {'after_beat': beat['no'], 'after': after, 'actor': dict(actor) if actor else None,
                        'question': _clean(raw.get('question')), 'options': options}

    # 番外：一個陣營一則（重複的只取第一則）；沒有陣營名稱或沒有內容的略過
    epilogues = []
    for item in _records(layer.get('epilogues')):
        side, text = _clean(item.get('side')), _clean(item.get('text'))
        if side and text and all(side != kept['side'] for kept in epilogues):
            epilogues.append({'side': side, 'text': text})
    question = _clean(layer.get('question'))
    if decision is None and not clues and not epilogues and not question:
        return None
    return {'decision': decision, 'clues': clues, 'epilogues': epilogues, 'question': question}


def chapter_data(number, title, content, turns, colors, play=False):
    """一章的劇情資料：只取讀者看得到的內容，依節拍分組。

    content 與 turns 是那件生成作品已保存的內容與段落；colors 是整部作品的色號（{固定代號: 色號}）。
    規劃裡的欄位只挑讀者該看到的：類型、前提、每一幕的幕名與起承轉合、下集預告；
    每一幕誰在場、發言順序都不輸出。每一段帶著說話者的色號與這一章的陣營，頁面照著畫。
    play＝互動版：每一段多帶 who（說話者是整部作品陣容的第幾位，視角與人物篩選用；不靠名稱比對）與 state（這一段之後他的狀態），
    這一章多帶 secrets（每位人物的底牌）與 interactive（這一章的互動層：抉擇、線索、番外、提問；沒有是 None）。
    閱讀版（預設）不帶這些，也不讀它們的來源。
    """
    view = run_view(content)
    plan = content.get('plan') or {}
    sides = chapter_sides(content)
    people = {member['id']: (member['name'], cast_key(member)) for member in view['cast']}
    by_beat = {}
    for turn in turns:
        by_beat.setdefault(turn['input'].get('beat_no'), []).append(turn)
    beats = []
    for beat in plan.get('beats') or []:
        segments = []
        for turn in by_beat.get(beat['beat_no'], []):
            name, key = people[turn['speaker_ref']]
            # 正常情況每一章的人物都在整部作品的陣容裡；萬一不在，接著往下編一個色號，不讓那一段沒有顏色
            color = colors.setdefault(key, len(colors) % PERSON_COLORS + 1)
            segment = {'no': turn['turn_no'], 'speaker': name, 'color': color, 'side': sides.get(key), 'line': turn['output']['line'],
                       'action': turn['output']['action'], 'stage': turn['output']['stage_direction']}
            if play:  # colors 的順序就是整部作品的陣容順序，所以序號和開頭人物清單裡的位置一致
                segment.update(who=list(colors).index(key) + 1, state=segment_state(turn))
            segments.append(segment)
        if segments:
            beat_title = str(beat.get('title') or '').strip()
            kind = beat.get('kind') if beat.get('kind') in KIND_LABELS else None
            # goal 是規劃時寫給模型看的「這一幕要推進什麼」，可能先說破後面的發展：有幕名就只給幕名，檔案裡不留 goal。
            # 舊作品沒有幕名，照舊用 goal 當這一幕的說明。
            beats.append({'no': beat['beat_no'], 'title': beat_title, 'kind': kind, 'goal': '' if beat_title else beat['goal'], 'segments': segments})
    chapter = {'no': number, 'title': title, 'genre': str(plan.get('genre') or '').strip(), 'premise': plan.get('premise', ''),
               'scene': view['scene']['description'], 'form': view['form'], 'beats': beats, 'teaser': str(plan.get('teaser') or '').strip()}
    if play:
        chapter['secrets'] = chapter_secrets(content, colors)
        chapter['interactive'] = chapter_interactive(content, beats, chapter['secrets'], colors)
    return chapter


def story_data(title, cast, chapters, play=False):
    """播放器使用的劇情資料（lw-story.v3）：整部作品的標題、陣容與各章。單一作品就是只有一章。

    cast 是整部作品的陣容；chapters 是 [(章號, 章名, 已保存的內容, 段落)]，依主線順序。
    色號依整部作品的陣容順序決定一次，每一章都用同一份：同一位人物從頭到尾是同一個顏色。
    開頭人物清單的陣營，用每位人物「第一次被分到」的那一個：後面的章節如果換了陣營，各段的標籤照那一章的規劃，開頭不先透露。
    play＝互動版的劇情資料（lw-play.v2，見 play_data）；預設是閱讀版，內容和加入互動版之前完全一樣。
    """
    colors = cast_colors(cast)
    sides, items = {}, []
    for number, chapter_title, content, turns in chapters:
        items.append(chapter_data(number, chapter_title, content, turns, colors, play))
        for key, side in chapter_sides(content).items():
            sides.setdefault(key, side)
    people = cast_data(cast, colors, sides)
    if play:
        # 開頭人物的 secret：只有一章時就是那一章的底牌。多章節時同一個人每一章各有各的底牌，放在各章的 secrets，這裡不帶（None）。
        own = {item['who']: item['secret'] for item in items[0]['secrets']} if len(items) == 1 else {}
        for number, member in enumerate(people, start=1):
            member['secret'] = own.get(number)
    return {'format': PLAY_FORMAT if play else STORY_FORMAT, 'title': title, 'cast': people, 'chapters': items}


def play_data(title, cast, chapters):
    """互動版使用的劇情資料（lw-play.v2）：lw-story.v3 的超集，參數和 story_data 相同。

    多出來的欄位：每一段的 who（說話者是陣容的第幾位，從 1 起）與 state（這一段之後他的情緒、立場、目標；沒有是 None）、
    每一章的 secrets（這一章每位人物的底牌）與 interactive（這一章的互動層，見 chapter_interactive；沒有是 None）、
    開頭每位人物的 secret（只有一章時是他的底牌；沒有或多章節時是 None）。
    拿掉這些欄位、把格式名稱換回來，就是同一件作品的閱讀版資料。（v1 → v2：每一章多了 interactive。）
    """
    return story_data(title, cast, chapters, play=True)


def _e(value):
    return html.escape(str(value or ''), quote=True)


def _csp_hash(text):
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode('utf-8')).digest()).decode() + "'"


def _embed_json(value):
    """放進 <script type="application/json"> 的資料。< > & 改寫成跳脫碼，內容裡的任何文字都不能提早結束這個區塊。"""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    for char, code in (('<', '\\u003c'), ('>', '\\u003e'), ('&', '\\u0026'), (' ', '\\u2028'), (' ', '\\u2029')):
        text = text.replace(char, code)
    return text


def _color_attr(item):
    """人物顏色寫成 data-c（色號 1 到 6）；樣式表把色號對到淺色、深色各一組顏色。資料裡沒有色號就不加。"""
    return f' data-c="{int(item["color"])}"' if item.get('color') else ''


def _who_html(segment):
    """說話者：名稱，後面接陣營的小標籤。沒有陣營，或陣營名稱就是他自己的名字（一個人一方）時不加。"""
    who, side = segment['speaker'], segment.get('side')
    return _e(who) + (f'<span class="lw-side">{_e(side)}</span>' if side and side != who else '')


def _xray_html(segment):
    """互動版的「真心話」：這一段之後那位人物的情緒、立場、目標，接在段落的最後。空的欄位不列；三個都空就沒有這一塊。

    樣式預設不顯示，所以不能執行程式的環境裡不會先看到。內嵌的程式只打開兩種：讀者選的那個視角的人物自己的段落，
    以及讀者花掉一次「偷看」的那一段（偷看的按鈕由程式加在這一塊前面）。
    """
    state = segment.get('state') or {}
    items = ''.join(f'<span class="lw-xray-item"><span class="lw-xray-key">{label}</span>{_e(state[key])}</span>'
                    for key, label in STATE_LABELS if state.get(key))
    return f'<div class="lw-xray"><span class="lw-xray-label">真心話</span>{items}</div>' if items else ''


def _clue_marks(segment, clues):
    """互動版：把這一段的線索詞包起來。回傳（台詞的 HTML, 動作的 HTML, 線索提示的 HTML）。

    clues 是指到這一段的線索（chapter_interactive 整理過的形狀）。每一則只包第一次出現的位置，包成
    <span class="lw-clue" data-clue="代號">…</span>；內嵌的程式把它變成可以點的線索，沒有程式時它就是一般文字。
    先在原文裡找位置，再把前、中、後各段分別跳脫：跳脫是逐字進行的，結果和「在已跳脫的文字裡找已跳脫的詞」相同，
    但不會把「&」變成的 &amp; 這種跳脫碼從中間切開。找不到或和前一則重疊的不包（資料整理時已經排除，這裡再擋一次）。
    提示寫在段落裡、先加上 hidden：點了線索詞才由程式打開；data-who 是這則線索指向第幾位人物的底牌。只替包得到的線索輸出提示。
    """
    marked, wrapped = {}, []
    for field in CLUE_FIELDS:
        text, spans = str(segment[field] or ''), []
        for clue in clues:
            phrase = str(clue.get('phrase') or '')
            begin = text.find(phrase) if phrase and clue.get('field') == field else -1
            if begin >= 0 and all(begin >= last or begin + len(phrase) <= first for first, last, _ in spans):
                spans.append((begin, begin + len(phrase), clue))
        parts, at = [], 0
        for first, last, clue in sorted(spans, key=lambda item: item[0]):
            parts.append(_e(text[at:first]) + f'<span class="lw-clue" data-clue="{_e(clue["id"])}">{_e(text[first:last])}</span>')
            at = last
        marked[field] = ''.join(parts) + _e(text[at:])
        wrapped += [id(clue) for _, _, clue in spans]
    notes = ''.join(f'<p class="lw-clue-note" data-clue="{_e(clue["id"])}" data-who="{int(clue["who"])}" hidden>'
                    f'<span class="lw-label">線索</span>{_e(clue["hint"])}</p>' for clue in clues if id(clue) in wrapped)
    return marked['line'], marked['action'], notes


def _segment_html(segment, narrative, who_tag, play=False, clues=()):
    """一段內容。劇本：人物名稱在上，場景提示加括號；小說：敘述在前，台詞加引號並標出說話的人。

    整段帶著說話者的色號：名稱用那個顏色，左邊有同色的細線，人物一多也看得出每一段是誰的。
    play＝互動版：多一個 data-p（說話者是第幾位人物，視角與人物篩選用）；台詞與動作裡的線索詞包起來（clues 是指到這一段的線索）；
    段落最後接線索的提示（先藏著）與真心話。閱讀版（預設）不走這些，輸出不變。
    """
    stage, who = _e(segment['stage']), _who_html(segment)
    if play:
        line, action, notes = _clue_marks(segment, clues)
    else:
        line, action, notes = _e(segment['line']), _e(segment['action']), ''
    if narrative:
        parts = [f'<p class="lw-stage">{stage}</p>' if stage else '', f'<p class="lw-action">{action}</p>' if action else '',
                 f'<p class="lw-line"><span class="lw-who">{who}</span>「{line}」</p>' if line else '']
        if not line:  # 只有動作沒有台詞：仍然標出是誰
            parts.insert(0, f'<p class="lw-who">{who}</p>')
    else:
        parts = [f'<{who_tag} class="lw-who">{who}</{who_tag}>', f'<p class="lw-stage">（{stage}）</p>' if stage else '',
                 f'<p class="lw-action">{action}</p>' if action else '', f'<p class="lw-line">{line}</p>' if line else '']
    if play:
        return (f'<article class="lw-seg"{_color_attr(segment)} data-p="{int(segment["who"])}">' + ''.join(parts)
                + notes + _xray_html(segment) + '</article>')
    return f'<article class="lw-seg"{_color_attr(segment)}>' + ''.join(parts) + '</article>'


def _beat_html(beat, narrative, beat_tag, who_tag, play=False, clues=None):
    """一幕。

    有幕名（新作品）：標題列是「第 N 幕」＋起承轉合的小標籤＋幕名，不顯示規劃用的目標。
    轉折那一幕另外加 class（樣式給強調色的底線與實心標籤）與「轉折」兩個字，讓讀者一眼看到故事在這裡轉彎。
    沒有幕名（舊作品）：照舊顯示第幾幕與這一幕的目標，不加任何新元素。
    play 與 clues（互動版：{段號: [線索]}）只往下傳給每一段；幕本身兩種播放器畫得一樣。
    """
    number, title = f'第 {int(beat["no"])} 幕', beat.get('title')
    kind = beat.get('kind') if title else None
    if title:
        label = KIND_LABELS.get(kind)
        head = (f'<{beat_tag} class="lw-beat-title"><span class="lw-beat-no">{number}</span>'
                + (f'<span class="lw-kind">{label}</span>' if label else '') + f'<span class="lw-beat-name">{_e(title)}</span>'
                + ('<span class="lw-turn-mark">轉折</span>' if kind == 'turn' else '') + f'</{beat_tag}>')
    else:
        head = f'<{beat_tag} class="lw-beat-title">{number}</{beat_tag}><p class="lw-goal">{_e(beat["goal"])}</p>'
    return (f'<section class="lw-beat{" lw-beat-turn" if kind == "turn" else ""}">' + head
            + ''.join(_segment_html(segment, narrative, who_tag, play, (clues or {}).get(segment['no'], ())) for segment in beat['segments'])
            + '</section>')


def _premise_html(premise):
    """開場白：規劃時寫的前提，前面標「開場」，讀者知道這是進入故事前的一段話，不是劇情的一部分。"""
    return f'<p class="lw-premise"><span class="lw-label">開場</span>{_e(premise)}</p>' if premise else ''


def _genre_html(chapter):
    return f'<span class="lw-genre">{_e(chapter["genre"])}</span>' if chapter.get('genre') else ''


def _teaser_html(teaser):
    """下集預告：故事沒有完全了結時，規劃寫的一句話。沒有就不輸出。"""
    return (f'<aside class="lw-teaser"><p class="lw-teaser-label">敬請期待下集</p><p class="lw-teaser-text">{_e(teaser)}</p></aside>'
            if teaser else '')


def _chapter_decision(chapter):
    """互動版：這一章畫得出來的關鍵抉擇——資料裡有抉擇，而且它指定的節拍在這一章裡。沒有就是 None。

    畫抉擇的地方（_chapter_html）與結尾卡上跟抉擇有關的部分（真結局的標示、結局計數）都用這個判斷，兩邊才會一致。
    """
    decision = (chapter.get('interactive') or {}).get('decision')
    if decision and any(beat['no'] == decision.get('after_beat') for beat in chapter['beats']):
        return decision
    return None


def _choice_html(decision):
    """互動版的關鍵抉擇：題目、三個選項、另外兩個結局。直接寫成靜態的區塊，排在指定節拍的最後一段之後。

    沒有程式（或「全部顯示」）時它就是文章裡的一段：題目、三個選項照資料的順序列出來，另外兩個結局收在預設不展開的區塊
    （原生的 details），真結局就是接下來原本的故事。內嵌的程式啟動後才把選項變成按鈕：選了真結局繼續往下，
    選了另外兩個就在這裡顯示那個結局的旁白（從收合的區塊複製出來），可以回到這裡重選。
    選項帶著種類（data-kind）；要先找到線索才能選的多一個 data-needs-clue。這裡沒有按鈕：不會出現按了沒反應的東西。
    """
    actor, options = decision.get('actor'), decision['options']
    items = ''.join(f'<li data-option="{_e(option["id"])}" data-kind="{_e(option["kind"])}"' + (' data-needs-clue="1"' if option.get('needs_clue') else '')
                    + f'>{_e(option["label"])}</li>' for option in options)
    endings = ''.join(f'<div class="lw-ending" data-option="{_e(option["id"])}" data-kind="{_e(option["kind"])}">'
                      f'<p class="lw-ending-kind">{ENDING_LABELS.get(option["kind"], "")}</p><p class="lw-ending-pick">{_e(option["label"])}</p>'
                      f'<p class="lw-ending-text">{_e(option["ending"])}</p></div>' for option in options if option['kind'] != 'true')
    return ('<aside class="lw-choice" aria-label="關鍵抉擇"><p class="lw-choice-kicker">關鍵抉擇</p>'
            + (f'<p class="lw-choice-actor">由 <span class="lw-name"{_color_attr(actor)}>{_e(actor["name"])}</span> 做決定</p>' if actor else '')
            + (f'<p class="lw-choice-question">{_e(decision["question"])}</p>' if decision.get('question') else '')
            + f'<ol class="lw-choice-list">{items}</ol>'
            '<p class="lw-choice-static">故事接下來走的是其中一條路；另外兩條路的結局收在下面。</p>'
            f'<details class="lw-endings"><summary>看另外兩個結局</summary>{endings}</details></aside>')


def _chapter_html(chapter, multi, last, play=False):
    """一章。多章節時有章名、類型、前提與場景；單一作品這些已經在頁首，這裡只放內容。標題層級跟著調整。

    last：是不是整份檔案的最後一章。下集預告只放在最後一章的結尾——合集裡前面幾章的「下一集」已經在檔案裡，不需要再預告。
    play＝互動版：下集預告不放在章節裡，改放在整份檔案最後的結尾卡（讀完才出現）；段落照互動版的方式畫；
    這一章有互動層時，線索詞在段落裡包起來，關鍵抉擇接在它指定的那一幕之後（合集裡每一章各用各的互動層）。
    """
    narrative = chapter['form'] == 'narrative'
    beat_tag, who_tag = ('h3', 'h4') if multi else ('h2', 'h3')
    head = ''
    if multi:
        head = (f'<h2 class="lw-chapter-title">第 {int(chapter["no"])} 章　{_e(chapter["title"])}</h2>'
                + (f'<p class="lw-tags">{_genre_html(chapter)}</p>' if chapter.get('genre') else '')
                + _premise_html(chapter['premise'])
                + (f'<p class="lw-scene">場景：{_e(chapter["scene"])}</p>' if chapter['scene'] else ''))
    decision, clues = None, {}
    if play:
        decision = _chapter_decision(chapter)
        for clue in (chapter.get('interactive') or {}).get('clues') or []:
            clues.setdefault(clue['no'], []).append(clue)  # 每一段要包哪些線索詞
    beats = ''.join(_beat_html(beat, narrative, beat_tag, who_tag, play, clues)
                    + (_choice_html(decision) if decision and beat['no'] == decision['after_beat'] else '') for beat in chapter['beats'])
    tail = _teaser_html(chapter.get('teaser') if last and not play else '')
    return (f'<section class="lw-chapter" id="ch-{int(chapter["no"])}" data-form="{"narrative" if narrative else "script"}">'
            + head + beats + tail + '</section>')


def _cast_html(cast, play=False):
    """開頭的人物清單。每個名字用那位人物的顏色（和段落裡同一個），讀者可以對照。

    有陣營時依陣營分組、一組一行，例如「沈氏集團：沈知衡（對手）、蘇映舟（配角）」；自己一個人一方（陣營名稱就是他的名字）只寫名字；
    沒有被分到陣營的人排在最後一行。完全沒有陣營（舊作品）就是原本的一行。組的順序是陣營在陣容裡第一次出現的順序。
    play＝互動版：名字多一個 data-p（他是陣容的第幾位，和段落上的號碼對應），內嵌的程式據此把名字變成可以點的篩選按鈕。
    """
    def person(number, member):
        who = f' data-p="{number}"' if play else ''
        return f'<span class="lw-name"{_color_attr(member)}{who}>{_e(member["name"])}</span>' + (f'（{_e(member["role"])}）' if member['role'] else '')

    groups = {}
    for number, member in enumerate(cast, start=1):  # 序號照陣容原本的順序編，分組之後也不會變
        groups.setdefault(member.get('side') or '', []).append((number, member))
    loose = groups.pop('', [])
    if not groups:
        return '、'.join(person(number, member) for number, member in loose)
    rows = []
    for side, members in groups.items():
        alone = len(members) == 1 and members[0][1]['name'] == side
        rows.append(('' if alone else f'<span class="lw-group-name">{_e(side)}</span>：') + '、'.join(person(number, member) for number, member in members))
    if loose:
        rows.append('、'.join(person(number, member) for number, member in loose))
    return ''.join(f'<div class="lw-group">{row}</div>' for row in rows)


# ---- 兩種播放器共用的頁面片段 ----
# 字級、深淺色、場景提示：閱讀版與互動版都有的工具（按鈕本身；外層與各自多出來的按鈕由各自的頁面加）
_TOOL_BUTTONS = ('<button type="button" data-tool="smaller" aria-label="字級縮小">A−</button>'
                 '<button type="button" data-tool="larger" aria-label="字級放大">A＋</button>'
                 '<button type="button" data-tool="theme">深色</button>'
                 '<button type="button" data-tool="stage" aria-pressed="true">場景提示</button>')


def _head_html(title, player, css, js):
    """文件開頭到 </head>。CSP 只放行這一份內嵌的樣式與程式（以雜湊鎖定），其餘一律不允許載入或執行。"""
    csp = (f"default-src 'none'; style-src {_csp_hash(css)}; script-src {_csp_hash(js)}; img-src data:; "
           "base-uri 'none'; form-action 'none'")
    return ('<!doctype html>\n<html lang="zh-Hant">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f'<meta http-equiv="Content-Security-Policy" content="{csp}">\n'
            '<meta name="referrer" content="no-referrer">\n'
            f'<meta name="generator" content="Life World {player}">\n'
            f'<title>{_e(title)}</title>\n<style>{css}</style>\n</head>\n')


def _meta_html(story, finished_on, play=False):
    """頁首的作品資訊：人物、場景（單一作品）或章數（多章節）、完成日期。"""
    chapters = story['chapters']
    meta = [('人物', _cast_html(story['cast'], play))]
    if len(chapters) > 1:
        meta.append(('章節', f'共 {len(chapters)} 章'))
    elif chapters and chapters[0]['scene']:
        meta.append(('場景', _e(chapters[0]['scene'])))
    if finished_on:
        meta.append(('完成', _e(finished_on)))
    return '<dl class="lw-meta">' + ''.join(f'<dt>{label}</dt><dd>{value}</dd>' for label, value in meta) + '</dl>\n'


def _toc_html(chapters):
    """多章節作品的目錄；只有一章時沒有。"""
    if len(chapters) < 2:
        return ''
    return ('<nav class="lw-toc" aria-label="目錄"><h2>目錄</h2><ol>'
            + ''.join(f'<li><a href="#ch-{int(chapter["no"])}">第 {int(chapter["no"])} 章　{_e(chapter["title"])}</a></li>' for chapter in chapters)
            + '</ol></nav>\n')


def _data_and_script_html(story, js):
    """文件結尾：內嵌的劇情資料（給之後的工具讀；頁面本身不靠它繪製）與播放器程式。"""
    return f'<script type="application/json" id="lw-story">{_embed_json(story)}</script>\n<script>{js}</script>\n</body>\n</html>\n'


def render_html(story, finished_on=''):
    """把劇情資料組成單一 HTML 檔（位元組）。輸入相同，輸出就相同。

    v3 新增的欄位（色號、陣營、幕名、類別、類型、預告）都用「有才畫」的方式讀取：資料裡沒有，頁面就和前一版一樣。
    """
    chapters = story['chapters']
    multi = len(chapters) > 1
    # 單一作品：前提與類型放在頁首（標題旁）；多章節時各章自己的放在章名下面
    premise = chapters[0]['premise'] if chapters and not multi else ''
    genre = _genre_html(chapters[0]) if chapters and not multi else ''
    document = (
        _head_html(story['title'], PLAYER, READER_CSS, READER_JS)
        + f'<body>\n<header class="lw-head">\n<p class="lw-kicker">Life World 作品{genre}</p>\n'
        f'<h1>{_e(story["title"])}</h1>\n' + (_premise_html(premise) + '\n' if premise else '')
        + _meta_html(story, finished_on)
        + '<div class="lw-tools" hidden>' + _TOOL_BUTTONS + '</div>' + '\n</header>\n' + _toc_html(chapters) + '<main>\n'
        + '\n'.join(_chapter_html(chapter, multi, number == len(chapters)) for number, chapter in enumerate(chapters, start=1)) + '\n</main>\n'
        f'<footer class="lw-foot"><p>{DISCLAIMER}</p><p>由 Life World 匯出・閱讀器 {PLAYER}</p></footer>\n'
        + _data_and_script_html(story, READER_JS))
    return document.encode('utf-8')


def _side_names(story):
    """整部作品出現過的陣營名稱（互動版「你站哪一邊」的選項）：先照開頭人物清單的順序，再補上後面章節才出現的。

    最後補上番外寫到、但人物身上沒有的陣營名稱：選邊之後顯示那一邊的番外，選項裡沒有它，那一則番外就永遠選不到。
    """
    names = [member.get('side') for member in story['cast']]
    names += [segment.get('side') for chapter in story['chapters'] for beat in chapter['beats'] for segment in beat['segments']]
    names += [item.get('side') for chapter in story['chapters'] for item in (chapter.get('interactive') or {}).get('epilogues') or []]
    return list(dict.fromkeys(name for name in names if name))


def _secrets_html(chapters):
    """互動版的「看底牌」：每位人物只有自己知道的事。沒有任何底牌就不輸出。

    用瀏覽器原生的收合區塊（details，沒有 open）：打開檔案時是收合的，文字不會顯示，按了「看底牌」才展開；不需要程式，
    所以不能執行程式的環境也不會先露出來。逐段模式下整張結尾卡在讀完之前是藏起來的，連這顆按鈕都看不到（由內嵌的程式處理）。
    多章節時依章分開列、標明第幾章（同一個人每一章的底牌可能不同）；人物名稱用他的顏色。
    每一則帶著是第幾位人物（data-p），清單帶著第幾章（data-ch）：讀者靠線索看穿某個人的底牌時，內嵌的程式據此找到那一則，
    直接顯示出來（不用再按「看底牌」）。底牌的文字只寫在這裡一份。
    """
    multi = len(chapters) > 1
    groups = []
    for chapter in chapters:
        items = ''.join(f'<li class="lw-secret"{_color_attr(item)} data-p="{int(item["who"])}"><span class="lw-name">{_e(item["name"])}</span>'
                        f'<span class="lw-secret-text">{_e(item["secret"])}</span></li>' for item in chapter.get('secrets') or [])
        if items:
            head = f'<h3 class="lw-secrets-chapter">第 {int(chapter["no"])} 章　{_e(chapter["title"])}</h3>' if multi else ''
            groups.append(head + f'<ul class="lw-secret-list" data-ch="{int(chapter["no"])}">{items}</ul>')
    if not groups:
        return ''
    return ('<details class="lw-secrets"><summary>看底牌</summary>'
            '<p class="lw-secrets-note">每個人只有自己知道的事。會透露劇情，建議讀完再看。</p>' + ''.join(groups) + '</details>')


def _epilogues_html(chapters, sides):
    """互動版的番外：各陣營在故事之後的一小段。沒有就不輸出。

    和底牌一樣收在預設不展開的區塊（沒有程式也不會先露出來）。每一則的 data-side 是它在「你站哪一邊」選項裡的號碼：
    內嵌的程式啟動後把這個區塊藏起來，讀者選了哪一邊，就把那一邊的番外複製到選邊的下方。
    多章節時各章的番外都列在這裡、標明是第幾章的。
    """
    multi = len(chapters) > 1
    items = []
    for chapter in chapters:
        head = f'<p class="lw-epilogue-chapter">第 {int(chapter["no"])} 章　{_e(chapter["title"])}</p>' if multi else ''
        for item in (chapter.get('interactive') or {}).get('epilogues') or []:
            if item.get('side') in sides:
                items.append(f'<div class="lw-epilogue" data-side="{sides.index(item["side"]) + 1}">' + head
                             + f'<p class="lw-epilogue-side">{_e(item["side"])}</p><p class="lw-epilogue-text">{_e(item["text"])}</p></div>')
    return f'<details class="lw-epilogues"><summary>看番外</summary>{"".join(items)}</details>' if items else ''


def _end_html(story):
    """互動版的結尾卡，放在整份檔案最後一章之後。有才有，依序是：
    「真結局」的標示（有抉擇的作品）、下集預告（最後一章的）、看底牌、你站哪一邊、番外、給讀者的一句提問（最後一章的）、
    已看過幾個結局與「回到轉折點重選」（有抉擇的作品）、從頭再看。

    逐段模式下，走完真結局、全部揭開後才出現；「全部顯示」時直接在最後。沒有程式時它就是文章的結尾：預告與提問看得到、
    底牌與番外收合；要靠程式才有意義的幾塊（真結局的標示、選邊、結局計數、從頭再看）先加上 hidden，由程式打開——
    預覽工具裡不會出現按了沒反應的按鈕，也不會對沒有做過選擇的讀者說「真結局」。
    「你站哪一邊」要有兩個以上的陣營才問；選了之後由程式顯示那一邊的番外與提問。
    """
    chapters = story['chapters']
    sides = _side_names(story)
    pick = ''
    if len(sides) >= 2:
        pick = ('<div class="lw-pick" hidden><h2 class="lw-pick-title">你站哪一邊？</h2><div class="lw-pick-options">'
                + ''.join(f'<button type="button" data-side="{number}">{_e(name)}</button>' for number, name in enumerate(sides, start=1))
                + '</div><p class="lw-pick-result" role="status" hidden></p></div>')
    decided = any(_chapter_decision(chapter) for chapter in chapters)
    question = ((chapters[-1].get('interactive') or {}).get('question') or '') if chapters else ''
    return ('<section class="lw-end" aria-label="讀完之後">' + ('<p class="lw-end-kind" hidden>真結局</p>' if decided else '')
            + _teaser_html(chapters[-1].get('teaser') if chapters else '') + _secrets_html(chapters) + pick + _epilogues_html(chapters, sides)
            + (f'<p class="lw-ask"><span class="lw-label">想一想</span>{_e(question)}</p>' if question else '')
            + ('<div class="lw-end-seen" hidden><p class="lw-endings-seen"></p>'
               '<button type="button" data-play="rechoose">回到轉折點重選</button></div>' if decided else '')
            + '<div class="lw-again" hidden><button type="button" data-play="restart">從頭再看</button></div></section>')


def render_play_html(story, finished_on=''):
    """把互動版的劇情資料（lw-play.v2）組成單一 HTML 檔（位元組）。輸入相同，輸出就相同。

    漸進增強：每一段、每一幕都直接寫在頁面裡，和閱讀版一樣讀得到；「一次看一段」是內嵌的程式啟動後才把還沒讀到的藏起來。
    關鍵抉擇是文章裡的一個靜態區塊（題目、三個選項、另外兩個結局收合），底牌與番外也收合：沒有程式時整篇照樣讀得完。
    要靠程式的部分（工具列、選視角、逐段的按鈕列、操作提示、選邊、結局計數、從頭再看）在頁面裡都先加上 hidden，程式啟動後才打開。
    和閱讀版不同的地方：段落與人物名字帶人物序號（data-p）、段落最後有真心話（樣式預設不顯示）、線索詞包起來、
    指定的節拍之後有關鍵抉擇、下集預告移到最後的結尾卡、結尾卡裡有收合的底牌與番外、多了選視角的區塊與逐段的按鈕列。
    人物顏色、陣營、幕名與起承轉合的畫法和閱讀版相同。

    入局（選視角）與「開始」二選一：只要有任何一段帶著人物狀態，就先問「你要以誰的視角入局」——選了才開始，
    他的真心話直接看得到，別人的只能偷看幾次（次數寫在 data-peeks，內嵌的程式照這個數字算）。
    完全沒有人物狀態的舊作品，選視角沒有任何差別，所以不問，照舊給一顆「開始」。
    """
    chapters = story['chapters']
    multi = len(chapters) > 1
    premise = chapters[0]['premise'] if chapters and not multi else ''
    genre = _genre_html(chapters[0]) if chapters and not multi else ''
    has_state = any(segment.get('state') for chapter in chapters for beat in chapter['beats'] for segment in beat['segments'])
    has_clue = any((chapter.get('interactive') or {}).get('clues') for chapter in chapters)
    decided = any(_chapter_decision(chapter) for chapter in chapters)
    peeks = PEEKS_FOR_TWO if len(story['cast']) <= 2 else PEEKS_FOR_MORE
    tools = '<div class="lw-tools" hidden>' + _TOOL_BUTTONS + '<button type="button" data-tool="mode">全部顯示</button></div>'
    entry = ''
    if has_state:
        entry = (f'\n<section class="lw-entry" data-peeks="{peeks}" hidden><h2 class="lw-entry-title">你要以誰的視角入局？</h2>'
                 f'<p class="lw-entry-note">你會直接看到這個人每一段的真心話；其他人的只能偷看 {peeks} 次，用完就沒有了。選「旁觀」就每個人的都要偷看。</p>'
                 '<div class="lw-entry-options">'
                 + ''.join(f'<button type="button" data-view="{number}"{_color_attr(member)}>{_e(member["name"])}</button>'
                           for number, member in enumerate(story['cast'], start=1))
                 + '<button type="button" data-view="0">旁觀</button></div></section>')
    # 操作提示只提這份檔案裡真的有的東西：沒有人物狀態就不提視角與偷看，沒有線索、沒有抉擇也不提
    hint = ('<p class="lw-hint" hidden>' + ('先選一個人的視角入局。' if has_state else '')
            + '一次看一段：按「下一段」、空白鍵或 → 往下，← 回上一段。'
            + (f'自己視角的真心話直接看得到，別人的只能偷看 {peeks} 次。' if has_state else '')
            + ('文字裡藏著線索，點到才算找到；找齊一個人的線索，就能看穿他的底牌。' if has_clue else '')
            + ('故事走到轉折會停下來等你做決定，不同的選擇通往不同的結局。' if decided else '')
            + '點人物的名字，其他人的段落會變淡；再點一次取消。</p>')
    nav = ('<nav class="lw-nav" aria-label="逐段閱讀" hidden>'
           + ('' if has_state else '<button type="button" class="lw-go" data-play="start">開始</button>')
           + '<button type="button" data-play="prev">上一段</button>'
           '<div class="lw-nav-mid"><p class="lw-progress"></p><p class="lw-status" hidden></p></div>'
           '<button type="button" class="lw-go" data-play="next">下一段</button></nav>')
    document = (
        _head_html(story['title'], PLAY_PLAYER, PLAY_CSS, PLAY_JS)
        + f'<body>\n<header class="lw-head">\n<p class="lw-kicker">Life World 作品・互動版{genre}</p>\n'
        f'<h1>{_e(story["title"])}</h1>\n' + (_premise_html(premise) + '\n' if premise else '')
        + _meta_html(story, finished_on, play=True) + hint + '\n' + tools + entry + '\n</header>\n' + _toc_html(chapters) + '<main>\n'
        + ''.join(_chapter_html(chapter, multi, False, play=True) + '\n' for chapter in chapters) + _end_html(story) + '\n</main>\n'
        + nav + '\n'
        f'<footer class="lw-foot"><p>{DISCLAIMER}</p><p>由 Life World 匯出・互動版 {PLAY_PLAYER}</p></footer>\n'
        + _data_and_script_html(story, PLAY_JS))
    return document.encode('utf-8')


# ---- 路線播放器（route-1）：回合制互動作品 ----

def route_data(content, title=None):
    """路線播放器使用的資料（lw-route.v1）：從已保存的 game.v1 內容挑出玩的人需要的部分。title 不給就用內容裡的標題。

    逐欄挑選（不是整份照抄再刪）：內容之後多了別的欄位，也不會跟著進到檔案裡。
    不帶的東西：建立時的說明與人物設定參照（setup）、生成進度（build）、生成的識別碼、人物的識別碼與公開簡介。
    多帶的東西：每位同行者的色號（1 到 PERSON_COLORS，依陣容順序，超過就循環），畫面用它分辨每個人。
    反應、願望、最後一句話只留陣容裡的人；數值的範圍、時間、門檻照原樣帶——播放器照這些數字算，不另外寫死。
    """
    cast = [{'id': member['id'], 'name': member['name'], 'color': index % PERSON_COLORS + 1} for index, member in enumerate(content.get('cast') or [])]
    ids = [member['id'] for member in cast]
    lines = lambda item: {key: item[key] for key, _ in BAND_LABELS}  # 依態度分的三句話
    events = []
    for event in content.get('events') or []:
        reactions = event.get('reactions') or {}
        events.append({'id': event['id'], 'name': event['name'], 'text': event['text'], 'x': event['x'], 'y': event['y'], 'stay': event['stay'],
                       'open': event['open'], 'close': event['close'], 'tags': list(event.get('tags') or []),
                       'reactions': {who: {'delta': reactions[who]['delta'], **lines(reactions[who])} for who in ids if who in reactions}})
    home, meter, clock, endings = content['home'], content['meter'], content['clock'], content.get('endings') or {}
    classes = endings.get('classes') or {}
    thresholds = endings.get('thresholds') or {}
    return {'format': ROUTE_FORMAT, 'skin': content.get('skin'), 'title': content.get('title', '') if title is None else title,
            'genre': content.get('genre', ''), 'premise': content.get('premise', ''), 'cast': cast,
            'player': {'name': (content.get('player') or {}).get('name') or '你'},
            'meter': {key: meter[key] for key in ('label', 'min', 'max', 'low', 'high')},
            'clock': {'start': clock['start'], 'limit': clock['limit']}, 'speed': content['speed'],
            'home': {key: home[key] for key in ('id', 'name', 'x', 'y', 'text')}, 'events': events,
            'wishes': {who: (content.get('wishes') or {})[who] for who in ids if who in (content.get('wishes') or {})},
            'farewells': {who: lines((content.get('farewells') or {})[who]) for who in ids if who in (content.get('farewells') or {})},
            'endings': {'classes': {name: {'title': classes[name]['title'], 'text': classes[name]['text']} for name, _ in ENDING_CLASS_LABELS if name in classes},
                        'thresholds': {key: thresholds[key] for key in ('great', 'poor') if key in thresholds},
                        'reachable': [name for name in endings.get('reachable') or [] if name in dict(ENDING_CLASS_LABELS)]}}


def _clock_text(minutes):
    """從 00:00 起算的分鐘數 → 'HH:MM'（和播放器顯示的寫法相同）。"""
    minutes = int(minutes)
    return f'{minutes // 60 % 24:02d}:{minutes % 60:02d}'


def _span_text(minutes):
    """一段時間 → '45 分'、'2 小時'、'1 小時 20 分'（和播放器顯示的寫法相同）。"""
    hours, rest = divmod(int(minutes), 60)
    return f'{rest} 分' if not hours else f'{hours} 小時' if not rest else f'{hours} 小時 {rest} 分'


def _signed_text(value):
    """數值的加減：正數帶加號、負數用全形減號（和播放器顯示的寫法相同）。"""
    value = int(value)
    return f'+{value}' if value > 0 else f'−{-value}' if value < 0 else '0'


def _route_places_html(data):
    """沒有程式時也讀得到的清單：起點與每一站的名稱、描述、營業時間、停留與標籤。不放任何會透露反應的東西。"""
    def facts(event):
        hours = '整天開放' if int(event['open']) <= 0 and int(event['close']) >= 1440 else f'營業 {_clock_text(event["open"])}–{_clock_text(event["close"])}'
        tags = ''.join(f'<span class="lw-tag">{_e(tag)}</span>' for tag in event.get('tags') or [])
        return f'<p class="lw-place-facts">{hours}・停留 {_span_text(event["stay"])}{tags}</p>'

    home = data['home']
    places = ''.join(f'<li class="lw-place"><h3 class="lw-place-name">{_e(event["name"])}</h3><p class="lw-place-text">{_e(event["text"])}</p>{facts(event)}</li>'
                     for event in data['events'])
    return (f'<h2 class="lw-static-title">起點</h2><div class="lw-place"><h3 class="lw-place-name">{_e(home["name"])}</h3>'
            f'<p class="lw-place-text">{_e(home["text"])}</p></div>'
            f'<h2 class="lw-static-title">可以去的地方（{len(data["events"])} 站）</h2><ol class="lw-places">{places}</ol>')


def _route_spoilers_html(data):
    """沒有程式時的「劇透區」：每一站每個人的反應與數值加減、每個人的願望、最後一句話、各種結局。

    用瀏覽器原生的收合區塊（details，沒有 open）：不能執行程式的環境裡不會先露出來，想看的人自己展開。
    內嵌的程式啟動後整個靜態區塊都藏起來——玩的時候這些要等選了才知道。
    """
    label = _e(data['meter']['label'])
    people = [(member, f'<span class="lw-name"{_color_attr(member)}>{_e(member["name"])}</span>') for member in data['cast']]

    def three(item):
        return '<ul class="lw-lines">' + ''.join(f'<li><span class="lw-line-key">{name}</span>{_e(item[key])}</li>' for key, name in BAND_LABELS) + '</ul>'

    stops = ''
    for event in data['events']:
        rows = ''.join(f'<li class="lw-spoiler-who">{name}<span class="lw-change">{label} {_signed_text(event["reactions"][member["id"]]["delta"])}</span>'
                       f'{three(event["reactions"][member["id"]])}</li>' for member, name in people if member['id'] in event['reactions'])
        stops += f'<h4 class="lw-spoiler-stop">{_e(event["name"])}</h4><ul class="lw-spoiler-list">{rows}</ul>'
    wishes = ''.join(f'<li class="lw-spoiler-who">{name}<span class="lw-wish-text">{_e(data["wishes"][member["id"]])}</span></li>'
                     for member, name in people if member['id'] in data['wishes'])
    farewells = ''.join(f'<li class="lw-spoiler-who">{name}{three(data["farewells"][member["id"]])}</li>'
                        for member, name in people if member['id'] in data['farewells'])
    classes = data['endings']['classes']
    endings = ''.join(f'<li><span class="lw-line-key">{name}</span><strong>{_e(classes[key]["title"])}</strong>　{_e(classes[key]["text"])}</li>'
                      for key, name in ENDING_CLASS_LABELS if key in classes)
    return ('<details class="lw-spoilers"><summary>每一站的反應、每個人的願望與結局（會透露內容，建議玩過再看）</summary>'
            f'<h3 class="lw-spoiler-title">每一站的反應</h3>{stops}'
            + (f'<h3 class="lw-spoiler-title">沒說出口的願望</h3><ul class="lw-spoiler-list">{wishes}</ul>' if wishes else '')
            + (f'<h3 class="lw-spoiler-title">最後一句話</h3><ul class="lw-spoiler-list">{farewells}</ul>' if farewells else '')
            + (f'<h3 class="lw-spoiler-title">結局</h3><ul class="lw-lines">{endings}</ul>' if endings else '') + '</details>')


def render_route_html(data):
    """把路線播放器的資料（lw-route.v1，見 route_data）組成單一 HTML 檔（位元組）。輸入相同，輸出就相同（檔案裡不寫時間）。

    頁面分兩部分：
    - 靜態的（.lw-static）：需要執行程式的說明、起點與所有站的清單、收合的劇透區。沒有程式時讀者看到的就是這些，加上頁首的開場白與同行的人。
    - 遊戲畫面（.lw-game，先加上 hidden、裡面是空的）：內嵌的程式啟動後依資料畫出來，並把靜態的部分藏起來。
      這裡不先寫任何按鈕：不能執行程式的預覽工具裡不會出現按了沒反應的東西。
    頁面裡沒有行內樣式（CSP 不放行）；工具列只有字級與深淺色（沒有場景提示，這種作品沒有那個東西）。
    """
    clock, home = data['clock'], data['home']
    start, limit = int(clock['start']), int(clock['limit'])
    companions = '、'.join(f'<span class="lw-name"{_color_attr(member)}>{_e(member["name"])}</span>' for member in data['cast'])
    plan = f'{_clock_text(start)} 從{_e(home["name"])}出發，{_span_text(limit)}內要回到{_e(home["name"])}（{_clock_text(start + limit)} 前）'
    meta = [('同行', companions), ('你扮演', _e(data['player']['name'])), ('行程', plan)]
    tools = ('<div class="lw-tools" hidden><button type="button" data-tool="smaller" aria-label="字級縮小">A−</button>'
             '<button type="button" data-tool="larger" aria-label="字級放大">A＋</button><button type="button" data-tool="theme">深色</button></div>')
    document = (
        _head_html(data['title'], ROUTE_PLAYER, ROUTE_CSS, ROUTE_JS)
        + f'<body>\n<header class="lw-head">\n<p class="lw-kicker">Life World 作品・互動遊戲{_genre_html(data)}</p>\n'
        f'<h1>{_e(data["title"])}</h1>\n' + (_premise_html(data['premise']) + '\n' if data.get('premise') else '')
        + '<dl class="lw-meta">' + ''.join(f'<dt>{label}</dt><dd>{value}</dd>' for label, value in meta) + '</dl>\n'
        + tools + '\n</header>\n<main>\n<section class="lw-static">\n'
        '<p class="lw-need">這個互動遊戲需要執行程式才能玩：你每一步選要去哪裡，同行的人各自反應，最後走到不同的結局。'
        '請用瀏覽器直接打開這個檔案。下面是這趟行程的內容。</p>\n'
        + _route_places_html(data) + '\n' + _route_spoilers_html(data) + '\n</section>\n'
        '<div class="lw-game" hidden></div>\n</main>\n'
        f'<footer class="lw-foot"><p>{DISCLAIMER}</p><p>由 Life World 匯出・互動遊戲 {ROUTE_PLAYER}</p></footer>\n'
        + _data_and_script_html(data, ROUTE_JS))
    return document.encode('utf-8')


def view_csp(payload):
    """站內直接看時，這一條回應的 CSP：和檔案自己寫的那一份同樣嚴格，另外加上「只允許同源的頁面框住」與 sandbox。

    程式與樣式的雜湊從檔案本身算出來（檔案裡 <style> 與沒有屬性的 <script> 的內容）：任何版本的播放器匯出的檔案都適用，
    不用記住每個版本的雜湊。檔案在送出之前已經和匯出紀錄的雜湊比對過，內容就是當初組出來的那一份；
    作品文字都跳脫過、內嵌資料的 < > 也改寫過，所以這兩種標籤只會是播放器自己的。
    sandbox allow-scripts：就算有人不經過 iframe、直接在分頁打開這個網址，頁面也是在獨立的來源裡執行，拿不到本站的登入狀態與儲存空間。
    """
    text = payload.decode('utf-8', errors='replace')
    styles = ' '.join(dict.fromkeys(_csp_hash(item) for item in re.findall(r'<style>(.*?)</style>', text, re.S))) or "'none'"
    scripts = ' '.join(dict.fromkeys(_csp_hash(item) for item in re.findall(r'<script>(.*?)</script>', text, re.S))) or "'none'"
    return (f"default-src 'none'; style-src {styles}; script-src {scripts}; img-src data:; base-uri 'none'; form-action 'none'; "
            "frame-ancestors 'self'; sandbox allow-scripts")


def export_dto(work_id, version_no, manifest, created_at):
    """匯出紀錄的回應：畫面只需要這些；物件路徑與 bucket 不回傳。"""
    return {'version_no': version_no, 'created_at': created_at, 'format': manifest['format'], 'player': manifest['player'],
            'filename': manifest['file']['filename'], 'size': manifest['file']['size'], 'sha256': manifest['file']['sha256'],
            'source_version': manifest['source']['version_no'], 'download_path': f'/api/works/{work_id}/exports/{version_no}/download'}


class WorkExportMixin:
    """擴充 LifeWorld；所有查詢都以 owner 過濾。儲存物件由路由層傳入（None＝這個環境沒有開放）。"""

    def _export_source(self, c, owner, work_id):
        """只有本人的生成作品、多章節作品與互動遊戲可以匯出；別人的、不存在的、其他種類的作品一律 404。"""
        self._ai_user(c, owner)
        work = self._work_row(c, owner, work_id)
        require(work['kind'] in ROLEPLAY_KINDS or work['kind'] in (SERIES_KIND, GAME_KIND), 404, 'not_found', '找不到可存取的作品。')
        return work

    def _export_game(self, c, owner, work):
        """讀出互動遊戲要匯出的資料（lw-route.v1）。生成完成之後才能匯出：還缺某位同行者的反應、還沒算門檻的遊戲玩不完。

        沒有生成進度的內容（不該出現）也當成還沒好，不拿不完整的內容去組檔。
        """
        row = c.execute('SELECT content_json FROM work_versions WHERE work_id=? AND owner_id=? AND version_no=?',
                        (work['id'], owner, work['current_version'])).fetchone()
        content = json.loads(row['content_json'])
        require((content.get('build') or {}).get('status') == 'ready', 409, 'game_not_ready', '互動遊戲還在準備中；每位同行者的反應都想好之後才能玩與下載。')
        return route_data(content, work['title'])

    def _export_story(self, c, owner, work, play=False):
        """讀出要匯出的內容：回傳（劇情資料, 完成日期, 段落總數）。

        生成作品：完成之後才能匯出，整件就是一章。多章節作品：只取已採納的章節，依主線順序。
        人物的顏色由整部作品的陣容決定（多章節作品用它保存的陣容，裡面有跨章不變的固定代號），所以每一章同一個人同一個顏色。
        play＝互動版的劇情資料（多帶人物狀態與底牌）；兩種讀的是同一批已保存的內容與段落，能不能匯出的規則相同。
        """
        if work['kind'] == SERIES_KIND:
            _, series = self._series_row(c, owner, work['id'])
            chapters, total = [], 0
            for episode in series['episodes']:
                source = self._roleplay_work(c, owner, episode['work_id'])
                turns = self._roleplay_turns(c, owner, source['id'])
                chapters.append((episode['no'], episode['title'], self._roleplay_content(c, owner, source), turns))
                total += len(turns)
            return story_data(work['title'], series['cast'], chapters, play), series['episodes'][-1]['adopted_at'][:10], total
        content = self._roleplay_content(c, owner, work)
        require(content['run']['status'] == 'completed', 409, 'work_not_completed', '作品完成之後才能下載；生成中或暫停的作品請先完成。')
        turns = self._roleplay_turns(c, owner, work['id'])
        story = story_data(work['title'], run_view(content)['cast'], [(1, work['title'], content, turns)], play)
        return story, (content['run'].get('finished_at') or '')[:10], len(turns)

    @staticmethod
    def _export_rows(c, owner, work_id):
        """這個作品的全部匯出版本（舊到新）；還沒匯出過就是空清單。"""
        return c.execute('SELECT v.version_no,v.content_json,v.created_at FROM work_versions v JOIN works w ON w.id=v.work_id AND w.owner_id=v.owner_id '
                         'WHERE v.work_id=? AND v.owner_id=? AND w.kind=? ORDER BY v.version_no', (export_work_id(work_id), owner, EXPORT_KIND)).fetchall()

    def work_exports(self, owner, work_id, storage):
        """這個作品匯出過的檔案，新的在前；available 表示這個環境能不能匯出與下載。"""
        with self.db.connect() as c:
            self._export_source(c, owner, work_id)
            rows = self._export_rows(c, owner, work_id) if storage is not None else []
        items = [export_dto(work_id, row['version_no'], json.loads(row['content_json']), row['created_at']) for row in rows]
        return {'available': storage is not None, 'items': items[::-1]}

    def create_work_export(self, owner, work_id, data, storage):
        """匯出一次。順序：讀作品 → 組檔 → 存進物件儲存（交易外）→ 寫匯出紀錄。

        先存檔再記錄：紀錄存在就代表檔案已經寫入過。內容和最新一筆相同時不新增版本，直接回那一筆
        （檔案若已不在，這次會補寫）。同一個提交代碼重送回原結果，不重新組檔。

        data.player 決定匯出閱讀版還是互動版；兩種走同一條路，差別只有劇情資料多帶什麼、用哪個播放器組檔、檔名與紀錄上的播放器名稱。
        兩種的匯出紀錄放在同一列的版本裡（版本號共用、只增不改），「內容有沒有變」各自和自己那一種最新的一筆比：
        下載過互動版之後再下載閱讀版，回的是原來那一筆閱讀版，不會因為中間隔了一筆互動版就多出重複的版本。

        互動遊戲（turn_game）只有路線播放器一種：data.player 給什麼都匯出它，「內容有沒有變」和最新的一筆路線播放器紀錄比。
        """
        require(storage is not None, 503, 'export_storage_unavailable', '這個環境還沒有開放下載作品。')
        operation = 'work:export:' + work_id
        play = data.player == 'play'
        # 提交代碼的指紋：閱讀版不含 player，和加入互動版之前送出的請求是同一個指紋（升級前後重送同一個請求不會被當成內容不同）；
        # 互動版多這一欄，同一個提交代碼不能先後用在兩種播放器上。
        request = data.model_dump(mode='json', exclude=None if play else {'player'})
        with self.db.connect() as c:
            work = self._export_source(c, owner, work_id)
            cached, _ = self._cached(c, owner, operation, data.request_id, request)
            if cached:
                return cached
            game = work['kind'] == GAME_KIND
            if game:
                story = self._export_game(c, owner, work)
                finished_on, segments, chapters = '', len(story['events']), 1  # 紀錄上的「段落數」記的是站數
            else:
                story, finished_on, segments = self._export_story(c, owner, work, play)
                chapters = len(story['chapters'])
        if game:
            payload, player, suffix, kind = render_route_html(story), ROUTE_PLAYER, ROUTE_SUFFIX, 'route'
        else:
            payload = render_play_html(story, finished_on) if play else render_html(story, finished_on)
            player, suffix, kind = (PLAY_PLAYER, PLAY_SUFFIX, 'play') if play else (PLAYER, '', 'reader')
        digest = hashlib.sha256(payload).hexdigest()
        object_name = f'works/{owner}/{work_id}/{digest}.html'
        try:
            storage.put_new(object_name, payload, HTML_MIME)  # 已存在就略過；名稱含內容雜湊，不會覆寫別的內容
        except StorageError:
            raise DomainError(503, 'export_storage_failed', '檔案暫時存不進去，請稍後再試一次。') from None
        manifest = {'schema': EXPORT_SCHEMA, 'format': data.format, 'player': player,
                    'source': {'work_id': work_id, 'kind': work['kind'], 'version_no': work['current_version'], 'segments': segments,
                               'chapters': chapters},
                    'file': {'object': object_name, 'sha256': digest, 'size': len(payload), 'mime': HTML_MIME,
                             'filename': export_filename(work['title'], suffix)},
                    'storage': {'kind': storage.kind, 'bucket': storage.bucket}}
        export_id = export_work_id(work_id)
        with self.db.connect(write=True, owner=owner) as c:
            cached, fingerprint = self._cached(c, owner, operation, data.request_id, request)
            if cached:
                return cached
            rows = self._export_rows(c, owner, work_id)
            # 同一種播放器最新的一筆（另一種的紀錄跳過）；還沒有過就是 None
            same = [(row['version_no'], json.loads(row['content_json'])) for row in rows]
            latest = next(((number, item) for number, item in reversed(same) if player_kind(item['player']) == kind), None)
            if latest is not None and latest[1]['file']['sha256'] == digest:
                version_no, manifest = latest  # 內容沒有變：沿用這一種最新的一筆，不新增版本
            else:
                now = self.now().isoformat()
                version_no = rows[-1]['version_no'] + 1 if rows else 1
                if not rows:
                    c.execute("INSERT INTO works(id,owner_id,kind,title,status,current_version,revision,created_at,updated_at) VALUES (?,?,?,?,'active',1,1,?,?)",
                              (export_id, owner, EXPORT_KIND, work['title'], now, now))
                c.execute('INSERT INTO work_versions(work_id,owner_id,version_no,parent_version,origin,content_schema,content_json,generation_id,created_at) '
                          "VALUES (?,?,?,?,'human',?,?,NULL,?)", (export_id, owner, version_no, version_no - 1 if rows else None, EXPORT_SCHEMA, encoded(manifest), now))
                if rows:
                    c.execute('UPDATE works SET current_version=?,revision=revision+1,title=?,updated_at=? WHERE id=? AND owner_id=?',
                              (version_no, work['title'], now, export_id, owner))
            created_at = self._export_rows(c, owner, work_id)[version_no - 1]['created_at']  # 與之後讀取時同一種表示法
            result = {'export': export_dto(work_id, version_no, manifest, created_at)}
            self._remember(c, owner, operation, data.request_id, fingerprint, result)
            return result

    def work_export_file(self, owner, work_id, version_no, storage):
        """讀出某一次匯出的檔案（下載與站內直接看共用）：核對擁有者，再比對檔案雜湊與紀錄。回傳（內容, 檔名）。"""
        require(storage is not None, 503, 'export_storage_unavailable', '這個環境還沒有開放下載作品。')
        with self.db.connect() as c:
            self._export_source(c, owner, work_id)
            row = next((item for item in self._export_rows(c, owner, work_id) if item['version_no'] == version_no), None)
            require(row is not None, 404, 'not_found', '找不到這一次匯出。')
            manifest = json.loads(row['content_json'])
        try:
            data = storage.get(manifest['file']['object'])
        except StorageError:
            raise DomainError(503, 'export_storage_failed', '檔案暫時讀不到，請稍後再試一次。') from None
        require(data is not None, 404, 'export_file_missing', '找不到匯出的檔案；請再按一次下載重新產生。')
        require(hashlib.sha256(data).hexdigest() == manifest['file']['sha256'], 409, 'export_file_mismatch', '匯出的檔案和紀錄不一致，已停止下載。')
        return data, manifest['file']['filename']


def install(app, service, current):
    """註冊匯出與下載的路由；儲存物件在 app.state.work_storage（None＝不開放）。"""

    @app.get('/api/works/{work_id}/exports', tags=['Works'])
    def list_work_exports(request: Request, work_id: str):
        return service.work_exports(current(request)['id'], work_id, app.state.work_storage)

    @app.post('/api/works/{work_id}/exports', status_code=201, tags=['Works'])
    def create_work_export(request: Request, work_id: str, data: WorkExportCreate):
        return service.create_work_export(current(request, True)['id'], work_id, data, app.state.work_storage)

    @app.get('/api/works/{work_id}/exports/{version_no}/download', tags=['Works'])
    def download_work_export(request: Request, work_id: str, version_no: int):
        data, filename = service.work_export_file(current(request)['id'], work_id, version_no, app.state.work_storage)
        # 以附件送出，並加上 sandbox：即使瀏覽器直接顯示，也不會以本站的身分執行裡面的程式或讀到登入狀態。
        disposition = f'attachment; filename="{FALLBACK_FILENAME}"; filename*=UTF-8\'\'{quote(filename, safe="")}'
        return Response(data, media_type=HTML_MIME, headers={'Content-Disposition': disposition, 'Cache-Control': 'private, no-store',
                                                             'Content-Security-Policy': "default-src 'none'; sandbox"})

    @app.get('/api/works/{work_id}/exports/{version_no}/view', tags=['Works'])
    def view_work_export(request: Request, work_id: str, version_no: int):
        """站內直接看（玩）某一次匯出：和下載同一份檔案、同樣只有本人讀得到、同樣比對雜湊，但不是附件。

        本站的頁面把它放進 <iframe sandbox="allow-scripts">。這一條回應的 CSP 見 view_csp（檔案本身的雜湊、只允許同源框住、自帶 sandbox）；
        X-Frame-Options 由 app/main.py 的安全標頭中介層設定——只有這一條路由成功的回應是 SAMEORIGIN，其他一律 DENY。
        """
        data, _ = service.work_export_file(current(request)['id'], work_id, version_no, app.state.work_storage)
        return Response(data, media_type=HTML_MIME, headers={'Cache-Control': 'private, no-store', 'Content-Security-Policy': view_csp(data)})
