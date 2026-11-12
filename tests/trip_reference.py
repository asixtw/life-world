"""回合制互動作品（game.v1，行程題材）的規則：Python 參考實作，以及一份手寫的示意資料（測試與版面樣張共用）。

播放器（app/export_player/route-1.js）自己算時間、數值與結局；這裡用 Python 把同一套規則再寫一次，兩邊互相對照：
tests/test_trip_reference.py 用 Node 執行播放器的純函式、逐步比對；browser_tests/test_export_route_offline.py 比對畫面上的時間與數值。
這份檔案不是測試案例（檔名不是 test_ 開頭），只被測試匯入。規則的出處是共同規格 game.v1。

行程的時間規則（題材層）：
- 兩地車程＝max(5, 四捨五入(直線距離 × speed)) 分鐘。四捨五入一律「.5 進位」：和播放器的寫法（floor(x + 0.5)）相同；
  Python 內建的 round 是「四捨六入五成雙」，剛好 .5 時結果會不一樣，所以不用它。
- 從目前位置去某一站：到達＝現在＋車程；早於開門就等到開門；開始停留＋stay 超過打烊 → 不能去（closed：來不及）；
  離開那一站的時間＋回起點的車程 超過 出發＋總時數 → 不能去（late：去了就趕不回起點）。兩個都成立時說 closed。去過的站不能再去。
- 隨時可以回起點結束行程；沒有站可去時只剩這個選項。

數值與結局的規則（通用層，換題材也不變）：
- 每位同行者的數值從 0 開始。到一站：先依「到站前」的數值決定用哪一句反應（≤ low 用 low、≥ high 用 high、其餘 mid），
  再加上 delta 並夾在 min～max。畫面顯示的升降是夾過之後實際變了多少。
- 結束時：一站都沒去 → poor；每位同行者都 ≥ high → perfect；否則總和 ≥ thresholds.great → great；否則總和 ≤ thresholds.poor → poor；其餘 ok。
- 結局時每個人的最後一句話，依最後的數值區間。
"""
import copy
import math

CLASSES = ('perfect', 'great', 'ok', 'poor')  # 結局種類，由好到壞


# ---- 題材層：行程的時間 ----

def travel(a, b, speed):
    """兩地車程（分鐘）。a、b 是帶 x、y 的地點。"""
    dx, dy = a['x'] - b['x'], a['y'] - b['y']
    return max(5, math.floor(math.sqrt(dx * dx + dy * dy) * speed + 0.5))


def spots(game):
    """{代號: 地點}：起點與每一站。"""
    return {game['home']['id']: game['home'], **{event['id']: event for event in game['events']}}


def deadline(game):
    """最晚幾點要回到起點（從 00:00 起算的分鐘數）。"""
    return game['clock']['start'] + game['clock']['limit']


def leg(game, here, now, event_id):
    """現在（now）人在 here，去 event_id 這一站會怎樣：車程、到達、等開門、開始停留、離開、回起點的車程，以及能不能去。

    blocked：''＝可以去；'closed'＝停留完已經超過打烊；'late'＝去了就趕不回起點。
    """
    where = spots(game)
    place = where[event_id]
    ride = travel(where[here], place, game['speed'])
    arrive = now + ride
    begin = max(arrive, place['open'])
    leave = begin + place['stay']
    back = travel(place, game['home'], game['speed'])
    blocked = 'closed' if leave > place['close'] else 'late' if leave + back > deadline(game) else ''
    return {'to': event_id, 'travel': ride, 'arrive': arrive, 'wait': begin - arrive, 'begin': begin, 'stay': place['stay'],
            'leave': leave, 'close': place['close'], 'back': back, 'blocked': blocked}


# ---- 通用層：數值、反應、結局 ----

def band(game, value):
    """數值落在哪一個區間：'low'（≤ low）、'high'（≥ high）、其餘 'mid'。"""
    meter = game['meter']
    return 'low' if value <= meter['low'] else 'high' if value >= meter['high'] else 'mid'


def react(game, meters, event):
    """到一個事件：每位同行者依到站前的區間說一句話，然後數值加減（夾在 min～max）。meters 會被就地更新。

    回傳 [{'who', 'band', 'text', 'before', 'after', 'change'}]，依同行者的順序；事件裡沒有寫到的人略過。
    """
    meter, result = game['meter'], []
    for member in game['cast']:
        reaction = (event.get('reactions') or {}).get(member['id'])
        if not reaction:
            continue
        before = meters[member['id']]
        which = band(game, before)
        after = max(meter['min'], min(meter['max'], before + reaction['delta']))
        meters[member['id']] = after
        result.append({'who': member['id'], 'band': which, 'text': reaction[which], 'before': before, 'after': after, 'change': after - before})
    return result


def replay(game, picks):
    """照 picks（依序選的站；選起點的代號＝回起點結束）把行程走一遍。

    回傳 {'steps': 每一步, 'here': 現在在哪, 'now': 現在幾點, 'visited': 去過的站, 'done': 是否已經回到起點, 'meters': {同行者: 數值}}。
    每一步：{'node', 'travel', 'arrive', 'wait', 'begin', 'stay', 'leave', 'among', 'final', 'reactions'}；
    among 是選它的當下有幾個選項可以選（能去的站，加上「回起點」那一個；第一步是出發，沒有選擇，among 是 None）；
    final 表示這一步是回到起點；reactions 是到這一站時每個人的反應（react 的結果；出發與回起點沒有）。
    """
    home, start = game['home']['id'], game['clock']['start']
    steps = [{'node': home, 'travel': 0, 'arrive': start, 'wait': 0, 'begin': start, 'stay': 0, 'leave': start, 'among': None, 'final': False, 'reactions': []}]
    here, now, visited, done = home, start, [], False
    meters = {member['id']: 0 for member in game['cast']}
    where = spots(game)
    for pick in picks:
        among = 1 + sum(1 for event in game['events'] if event['id'] not in visited and not leg(game, here, now, event['id'])['blocked'])
        if pick == home:
            ride = 0 if here == home else travel(where[here], game['home'], game['speed'])
            steps.append({'node': home, 'travel': ride, 'arrive': now + ride, 'wait': 0, 'begin': now + ride, 'stay': 0, 'leave': now + ride,
                          'among': among, 'final': True, 'reactions': []})
            here, now, done = home, now + ride, True
            break
        going = leg(game, here, now, pick)
        assert pick not in visited and not going['blocked'], f'{pick} 這一步不能走'
        steps.append({'node': pick, 'travel': going['travel'], 'arrive': going['arrive'], 'wait': going['wait'], 'begin': going['begin'],
                      'stay': going['stay'], 'leave': going['leave'], 'among': among, 'final': False, 'reactions': react(game, meters, where[pick])})
        here, now = pick, going['leave']
        visited.append(pick)
    return {'steps': steps, 'here': here, 'now': now, 'visited': visited, 'done': done, 'meters': meters}


def options(game, picks):
    """現在可以選什麼：每個還沒去過的站一個（能去的在前，各自依車程由近到遠，同樣遠的照原本的順序），最後是「回起點，結束行程」。

    每一個：{'id', 'enabled', 'final', 'reason', 'travel', 'arrive', 'wait', 'begin', 'stay', 'leave', 'close', 'back'}；
    回起點那一個只有 id、enabled、final、reason、travel、arrive。已經回到起點就沒有選項。
    """
    state = replay(game, picks)
    if state['done']:
        return []
    home = game['home']['id']
    legs = [leg(game, state['here'], state['now'], event['id']) for event in game['events'] if event['id'] not in state['visited']]
    legs.sort(key=lambda item: (bool(item['blocked']), item['travel']))  # Python 的排序是穩定的：同樣遠的維持原本的順序
    items = [{'id': item['to'], 'enabled': not item['blocked'], 'final': False, 'reason': item['blocked'], 'travel': item['travel'],
              'arrive': item['arrive'], 'wait': item['wait'], 'begin': item['begin'], 'stay': item['stay'], 'leave': item['leave'],
              'close': item['close'], 'back': item['back']} for item in legs]
    ride = 0 if state['here'] == home else travel(spots(game)[state['here']], game['home'], game['speed'])
    return items + [{'id': home, 'enabled': True, 'final': True, 'reason': '', 'travel': ride, 'arrive': state['now'] + ride}]


def classify(game, meters, visited_count, thresholds=None):
    """結局種類。thresholds 不給就用作品裡保存的（endings.thresholds）。"""
    thresholds = thresholds or game['endings']['thresholds']
    values = [meters[member['id']] for member in game['cast']]
    total = sum(values)
    if not visited_count:
        return 'poor'
    if values and all(value >= game['meter']['high'] for value in values):
        return 'perfect'
    if total >= thresholds['great']:
        return 'great'
    if total <= thresholds['poor']:
        return 'poor'
    return 'ok'


def ending(game, picks):
    """照 picks 走完之後的結局種類（picks 的最後一步應該是回起點）。"""
    state = replay(game, picks)
    return classify(game, state['meters'], len(state['visited']))


def farewells(game, picks):
    """結局時每位同行者的最後一句話：[{'who', 'value', 'band', 'text'}]，依最後的數值區間。"""
    meters = replay(game, picks)['meters']
    result = []
    for member in game['cast']:
        which = band(game, meters[member['id']])
        result.append({'who': member['id'], 'value': meters[member['id']], 'band': which, 'text': game['farewells'][member['id']][which]})
    return result


def clock(minutes):
    """分鐘數 → 'HH:MM'（和播放器顯示的寫法相同）。"""
    return f'{minutes // 60 % 24:02d}:{minutes % 60:02d}'


def span(minutes):
    """一段時間 → '45 分'、'2 小時'、'1 小時 20 分'（和播放器顯示的寫法相同）。"""
    hours, rest = divmod(minutes, 60)
    return f'{rest} 分' if not hours else f'{hours} 小時' if not rest else f'{hours} 小時 {rest} 分'


def signed(value):
    """數值的寫法：正數帶加號、負數用全形減號、零就是 0（和播放器顯示的寫法相同）。"""
    return f'+{value}' if value > 0 else f'−{-value}' if value < 0 else '0'


def routes(game):
    """列舉所有走得到的行程（至少去一站）：每一條是依序去過的站。隨時可以回起點，所以每一段走得到的開頭都是一條完整的行程。"""
    def walk(picks):
        for option in options(game, picks):
            if option['enabled'] and not option['final']:
                yield picks + [option['id']]
                yield from walk(picks + [option['id']])
    return walk([])


def calibrate(game):
    """算門檻與走得到的結局（規格裡這件事由後端做；這裡只為了替手寫的示意資料填上合理的數字）。

    取每條行程的總和：great 是第 75 百分位、poor 是第 25 百分位（最近名次法），並確保 poor < great。
    reachable：實際出現過的結局種類，由好到壞；一站都沒去一律是 poor，所以 poor 一定走得到。
    """
    finals = []
    for picks in routes(game):
        state = replay(game, picks)
        finals.append((state['meters'], len(state['visited'])))
    totals = sorted(sum(meters.values()) for meters, _ in finals)
    rank = lambda share: totals[min(len(totals) - 1, max(0, math.ceil(share * len(totals)) - 1))]
    thresholds = {'great': rank(0.75), 'poor': rank(0.25)}
    if thresholds['poor'] >= thresholds['great']:
        thresholds['poor'] = thresholds['great'] - 1
    seen = {classify(game, meters, count, thresholds) for meters, count in finals} | {'poor'}
    return {'thresholds': thresholds, 'reachable': [name for name in CLASSES if name in seen]}


# ---- 手寫的示意資料 ----
# 兩位同行者加上使用者、起點加七站、各站營業時間不同、每一站對兩個人的影響不同；08:00 從車站出發，10 小時內（18:00 前）要回來。
# 這不是模型生成的內容：地點、營業時間、每個人的反應與結局都是為了檢查版面與規則手寫的。
SAMPLE_TITLE = '版面樣張，示意資料｜海線小鎮一日行'


def _event(event_id, name, text, x, y, stay, open_at, close_at, tags, first, second):
    """一站。first、second 是兩位同行者的 (delta, 不滿時, 普通時, 有好感時)。"""
    reactions = {who: {'delta': delta, 'low': low, 'mid': mid, 'high': high} for who, (delta, low, mid, high) in zip(('c1', 'c2'), (first, second))}
    return {'id': event_id, 'name': name, 'text': text, 'x': x, 'y': y, 'stay': stay, 'open': open_at, 'close': close_at, 'tags': tags, 'reactions': reactions}


SAMPLE = {
    'schema': 'game.v1', 'skin': 'trip', 'generation_id': 'gen-game-sample',
    'build': {'status': 'ready', 'done': ['plan', 'c1', 'c2'], 'pending': []},
    'setup': {'description': '〔SETUP〕示意：海線小鎮一日行，候選地點與營業時間是手寫的。', 'start_place': '車站', 'hours': 10, 'start_time': '08:00',
              'participants': [{'person_id': 'person-c1', 'profile_id': 'profile-c1', 'version': 2, 'content_sha256': 'sha-c1'},
                               {'person_id': 'person-c2', 'profile_id': 'profile-c2', 'version': 1, 'content_sha256': 'sha-c2'}],
              'player': {'name': '你', 'person_id': None}},
    'cast': [{'id': 'c1', 'name': '何以晴', 'person_id': 'person-c1', 'public_profile': '〔PUBLIC-c1〕愛吃、行動派。'},
             {'id': 'c2', 'name': '溫若岑', 'person_id': 'person-c2', 'public_profile': '〔PUBLIC-c2〕喜歡安靜的地方。'}],
    'player': {'name': '你', 'public_profile': '〔PUBLIC-player〕'},
    'title': SAMPLE_TITLE, 'genre': '行程',
    'premise': '（示意）難得大家都有空。早上八點在車站集合，傍晚六點前要回到這裡搭車——想去的地方比時間多，每個人心裡都有一個沒說出口的期待。',
    'meter': {'label': '滿意', 'min': -6, 'max': 6, 'low': -2, 'high': 2},
    'clock': {'start': 480, 'limit': 600}, 'speed': 12,
    'home': {'id': 'home', 'name': '車站', 'x': 5, 'y': 5, 'text': '（示意）小鎮唯一的車站。寄物櫃在出口右手邊，回程的車是傍晚六點。'},
    'events': [
        _event('p1', '晨光魚市', '（示意）天亮就開的漁港市場，現撈的海鮮當場料理，十一點就收攤。', 3, 6, 45, 360, 660, ['吃', '市場'],
               (2, '「……至少這裡的東西是新鮮的。」她悶悶地排進隊伍。', '「這個時間來才有剛上岸的！」她已經在看哪一攤排最長。', '「你果然懂我！」她拉著你直奔最裡面那一攤。'),
               (-2, '她站在市場口沒有進來，低頭滑手機。', '「人好多、地上好濕……我在外面等你們。」', '「味道有點重，不過你們開心就好。」她退到通風的地方。')),
        _event('p2', '山城咖啡', '（示意）半山腰的老屋咖啡館，靠窗的位子看得到整個港口。十點才開門。', 7, 4, 45, 600, 1020, ['咖啡', '休息'],
               (-1, '「又要坐著？」她看了一眼手錶，沒有再說話。', '「坐一下也好，但不要坐太久喔。」她一直在看時間。', '「好吧，陪她坐一下。」她小聲問你下一站吃什麼。'),
               (2, '她挑了離你們最遠的靠窗位子，總算鬆了一口氣。', '她挑了靠窗的位子，把手機收了起來。', '「這裡真好。」她替每個人都點了一杯。')),
        _event('p3', '舊鐵道步道', '（示意）沿著廢棄鐵道走的海邊步道，來回要走一個多小時，沿路沒有遮蔭。', 8, 8, 75, 360, 1080, ['散步', '拍照'],
               (1, '「走就走。」她一個人走在最前面。', '「走！流點汗等一下吃更香。」', '「來比賽誰先到隧道口！」她已經跑起來了。'),
               (-2, '「……你是故意的嗎？」她在入口的長椅坐下，不走了。', '「……還要走多久？」她看了看自己的鞋。', '「好吧，陪你們走一段。」她走得很慢，但沒有抱怨。')),
        _event('p4', '玻璃工坊', '（示意）可以自己吹一個玻璃杯帶回家的體驗工坊。下午一點到四點，體驗一場九十分鐘。', 2, 2, 90, 780, 960, ['手作'],
               (-2, '「九十分鐘？」她的臉整個垮下來。', '「九十分鐘都在同一個地方？」她偷偷看了一下時間。', '「好啦，陪你們做一個。」但她的腳一直在抖。'),
               (1, '「至少可以安靜地坐著。」她淡淡地說。', '「慢慢做也不錯。」她仔細挑了顏色。', '「我想做一對，一個送你。」她難得主動開口。')),
        _event('p5', '海角燈塔', '（示意）岬角盡頭的白色燈塔，可以爬到塔頂。下午四點半關門，路程不近。', 10, 5, 60, 540, 990, ['風景', '拍照'],
               (1, '「風好大。」她抓著欄杆，總算笑了一下。', '「風好大！不過上面看得到整片海。」', '「快上來！這裡看得到我們早上去過的地方！」'),
               (-1, '「我在下面等。」她沒有要爬的意思。', '「這麼多階……」她抬頭看了看，嘆了一口氣。', '「我慢慢爬，你們先上去。」')),
        _event('p6', '百年書店', '（示意）木地板會嘎吱響的老書店，二樓有一排可以坐著看書的窗台。十一點開門。', 5, 8, 45, 660, 1140, ['逛街', '書'],
               (-2, '「我在門口等你們。」她連門都沒有進。', '「裡面好安靜，我會想睡……」她在門口踱步。', '「你們慢慢看。」她翻了兩頁食譜就開始打呵欠。'),
               (2, '她一個人上了二樓，坐在窗台邊，臉色總算好了一點。', '她在二樓的窗台坐下來，翻開一本就沒有再抬頭。', '「這本你一定喜歡。」她抽出一本書塞到你手裡。')),
        _event('p7', '巷口甜點舖', '（示意）下午兩點才開的小店，招牌是現烤的檸檬塔，賣完就收。', 6, 6, 30, 840, 1080, ['吃', '甜點'],
               (2, '「……檸檬塔？」她的眼睛總算亮了一下。', '「我要兩個！」她眼睛都亮了。', '「今天太完美了，我請客！」'),
               (1, '「分我一口就好。」她的語氣軟了一些。', '「分我一口就好。」結果她吃掉了半個。', '「我也要一個，內用。」她難得不想走。'))],
    'wishes': {'c1': '（示意）想吃到剛上岸的海鮮，最後再配一份甜的；最怕整個下午困在同一個地方。',
               'c2': '（示意）想找個安靜的地方坐下來，喝杯咖啡、翻幾頁書；不想走太多路。'},
    'farewells': {'c1': {'low': '「下次……我自己排行程好了。」她頭也不回地進了月台。', 'mid': '「還不錯啦，下次多排一點吃的。」',
                         'high': '「下個月再來一次！我已經想好要吃什麼了。」'},
                  'c2': {'low': '「我先回去了。」她沒有等你們一起走。', 'mid': '「謝謝你排的行程，辛苦了。」',
                         'high': '「今天很好。下次，換我帶你去一個地方。」'}},
    'endings': {'classes': {'perfect': {'title': '兩個人都捨不得回家', 'text': '（示意）回程的車上沒有人滑手機，都在看今天拍的照片，還約好了下一次。'},
                            'great': {'title': '大家都說下次還要來', 'text': '（示意）雖然不是每一站都合每個人的意，回程的車上還是笑聲不斷。'},
                            'ok': {'title': '有人盡興，有人還好', 'text': '（示意）回程的車上，有人在回味，有人已經睡著了。'},
                            'poor': {'title': '好像哪裡不太對', 'text': '（示意）回程的車上很安靜。也許下次該先問問大家想去哪裡。'}}}}
SAMPLE['endings'].update(calibrate(SAMPLE))  # 門檻與走得到的結局：照規格的算法從這份資料算出來


def sample(title=SAMPLE_TITLE, **changes):
    """示意資料的一份複本（可以改標題與其他欄位），不會動到原本那一份。"""
    game = copy.deepcopy(SAMPLE)
    game.update(title=title, **changes)
    return game
