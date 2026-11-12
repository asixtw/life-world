"""回合制互動作品（game.v1，行程題材）的規則：Python 參考實作的單元測試，以及播放器的純函式和它逐項對照。

1. 參考實作（tests/trip_reference.py）照共同規格算：車程的四捨五入、等開門、來不及與趕不回來、選項的排序、
   到站前的區間決定反應、數值的加減與上下限、結局的判定順序、最後一句話。
2. 播放器（app/export_player/route-1.js）在 Node 裡只匯出規則的純函式（瀏覽器裡同一份程式才接上畫面）：
   把示意資料所有走得到的行程都走一遍，每一步的時間、反應、數值，每一刻的選項，以及結局與最後一句話，都要和參考實作一樣。
這裡不開瀏覽器、不連網；畫面上的數字由 browser_tests/test_export_route_offline.py 再對一次。
"""
import json
import os
import shutil
import subprocess

import pytest

import trip_reference as ref
from app.work_export import route_data


def game(**changes):
    return ref.sample(**changes)


def test_travel_rounds_half_up_and_never_goes_below_five_minutes():
    assert ref.travel({'x': 5, 'y': 5}, {'x': 3, 'y': 6}, 12) == 27  # 距離 2.236 × 12 ＝ 26.83
    assert ref.travel({'x': 6, 'y': 6}, {'x': 10, 'y': 5}, 12) == 49  # 49.48：不到 .5，捨去
    assert ref.travel({'x': 0, 'y': 0}, {'x': 3, 'y': 4}, 2.5) == 13, '剛好 .5 要進位（Python 內建的 round 會得到 12）'
    assert ref.travel({'x': 5, 'y': 5}, {'x': 5, 'y': 5}, 12) == 5, '同一個點也算 5 分鐘'
    assert ref.travel({'x': 0, 'y': 0}, {'x': 0, 'y': 0.2}, 12) == 5, '很近的兩個點最少 5 分鐘'


def test_a_leg_waits_for_opening_and_is_blocked_by_closing_time_or_the_way_home():
    sample = game()
    early = ref.leg(sample, 'home', 480, 'p2')  # 08:27 到，10:00 才開門
    assert (early['travel'], early['arrive'], early['wait'], early['begin'], early['leave'], early['blocked']) == (27, 507, 93, 600, 645, '')
    on_time = ref.leg(sample, 'home', 480, 'p1')
    assert (on_time['arrive'], on_time['wait'], on_time['leave'], on_time['close'], on_time['back'], on_time['blocked']) == (507, 0, 552, 660, 27, '')
    assert ref.leg(sample, 'home', 600, 'p1')['blocked'] == 'closed', '10:27 到、停留 45 分，超過 11:00 打烊'
    assert ref.leg(sample, 'home', 588, 'p1')['blocked'] == '', '剛好在打烊的時間離開，還來得及'
    assert ref.leg(sample, 'home', 589, 'p1')['blocked'] == 'closed'
    # 趕不回起點：18:00 前要回來。先把打烊時間拿掉，只看回程：15:55 出發去舊鐵道步道，16:46 到、18:01 離開，再加回程就超過
    late = ref.leg(game(events=[{**event, 'close': 1440} for event in sample['events']]), 'home', 955, 'p3')
    assert late['blocked'] == 'late' and late['leave'] + late['back'] > ref.deadline(sample)
    edge = game(clock={'start': 480, 'limit': 27 + 45 + 27})  # 剛好趕得回來
    assert ref.leg(edge, 'home', 480, 'p1')['blocked'] == ''
    assert ref.leg(game(clock={'start': 480, 'limit': 27 + 45 + 26}), 'home', 480, 'p1')['blocked'] == 'late'
    both = ref.leg(game(clock={'start': 480, 'limit': 60}), 'home', 600, 'p1')
    assert both['blocked'] == 'closed', '打烊與趕不回來同時成立：說打烊'


def test_replay_walks_the_route_and_applies_reactions_by_the_attitude_before_arrival():
    sample = game()
    state = ref.replay(sample, ['p1', 'p3', 'home'])
    assert [step['node'] for step in state['steps']] == ['home', 'p1', 'p3', 'home'] and state['done'] and state['visited'] == ['p1', 'p3']
    start, market, trail, back = state['steps']
    assert (start['arrive'], start['among'], start['final'], start['reactions']) == (480, None, False, [])
    assert (market['travel'], market['arrive'], market['leave'], market['among']) == (27, 507, 552, 8), '七站都能去，加上回起點'
    # 晨光魚市：兩個人都從 0 開始（普通的那一句）；何以晴 +2、溫若岑 −2
    assert [(item['who'], item['band'], item['before'], item['after'], item['change']) for item in market['reactions']] == [
        ('c1', 'mid', 0, 2, 2), ('c2', 'mid', 0, -2, -2)]
    assert market['reactions'][0]['text'] == sample['events'][0]['reactions']['c1']['mid']
    # 舊鐵道步道：何以晴到站前是 +2（≥ high，用有好感的那一句），溫若岑是 −2（≤ low，用不滿的那一句）
    assert [(item['who'], item['band'], item['before'], item['after']) for item in trail['reactions']] == [('c1', 'high', 2, 3), ('c2', 'low', -2, -4)]
    assert trail['reactions'][1]['text'] == sample['events'][2]['reactions']['c2']['low']
    assert (back['final'], back['reactions'], back['arrive']) == (True, [], trail['leave'] + back['travel'])
    assert state['meters'] == {'c1': 3, 'c2': -4} and state['now'] == back['arrive'] and state['here'] == 'home'
    # 回到起點之後的選擇不算；不能走的那一步直接拒絕
    assert ref.replay(sample, ['home', 'p1'])['visited'] == []
    with pytest.raises(AssertionError):
        ref.replay(sample, ['p1', 'p1'])


def test_values_stay_inside_the_range_and_the_shown_change_is_what_really_changed():
    narrow = game(meter={'label': '滿意', 'min': -3, 'max': 3, 'low': -2, 'high': 2})
    state = ref.replay(narrow, ['p1', 'p3'])  # 溫若岑 −2 再 −2：最低只到 −3
    last = state['steps'][-1]['reactions'][1]
    assert (last['before'], last['after'], last['change']) == (-2, -3, -1) and state['meters']['c2'] == -3
    state = ref.replay(narrow, ['p1', 'p3', 'p5'])  # 何以晴 +2、+1、+1：最高只到 3，最後一站實際沒有變
    assert state['steps'][-1]['reactions'][0]['change'] == 0 and state['meters']['c1'] == 3
    assert [ref.band(narrow, value) for value in (-3, -2, -1, 0, 1, 2, 3)] == ['low', 'low', 'mid', 'mid', 'mid', 'high', 'high']


def test_options_put_reachable_places_first_by_travel_time_and_always_end_with_going_home():
    sample = game()
    first = ref.options(sample, [])
    assert [item['id'] for item in first] == ['p7', 'p1', 'p2', 'p6', 'p3', 'p4', 'p5', 'home'], '由近到遠；同樣遠的照原本的順序（p1 在 p2 前面）'
    assert all(item['enabled'] for item in first) and first[-1] == {'id': 'home', 'enabled': True, 'final': True, 'reason': '', 'travel': 0, 'arrive': 480}
    assert first[0]['wait'] == 840 - 497, '巷口甜點舖下午兩點才開：可以去，但要等'
    later = ref.options(sample, ['p2', 'p5'])  # 12:23 離開燈塔
    assert [(item['id'], item['reason']) for item in later if not item['enabled']] == [('p1', 'closed')], '晨光魚市十一點就收攤'
    assert [item['id'] for item in later if item['enabled']] == ['p3', 'p7', 'p6', 'p4', 'home'], '能去的排前面，依車程由近到遠'
    assert all(item['id'] not in ('p2', 'p5') for item in later), '去過的站不再出現'
    assert ref.options(sample, ['p1', 'home']) == [], '已經回到起點就沒有選項'
    only_home = ref.options(game(clock={'start': 480, 'limit': 20}), [])
    assert [item['enabled'] for item in only_home] == [False] * 7 + [True] and {item['reason'] for item in only_home[:-1]} == {'late'}


def test_endings_follow_the_order_in_the_contract():
    sample = game()
    assert sample['endings']['thresholds'] == {'great': 3, 'poor': 0} and sample['endings']['reachable'] == ['perfect', 'great', 'ok', 'poor']
    assert ref.ending(sample, ['home']) == 'poor', '一站都沒去：一律 poor'
    assert ref.ending(sample, ['p2', 'p5', 'p7', 'home']) == 'perfect', '兩個人都 ≥ 2'
    assert ref.replay(sample, ['p2', 'p5', 'p7', 'home'])['meters'] == {'c1': 2, 'c2': 2}
    assert ref.ending(sample, ['p7', 'home']) == 'great', '總和 3，但溫若岑只有 1：不是 perfect'
    assert ref.ending(sample, ['p2', 'home']) == 'ok', '總和 1：在兩個門檻之間'
    assert ref.ending(sample, ['p1', 'home']) == 'poor', '總和 0 ≤ poor 的門檻'
    assert ref.ending(sample, ['p1', 'p3', 'home']) == 'poor'
    # 門檻的邊界；perfect 的判斷在門檻之前
    meters = lambda first, second: {'c1': first, 'c2': second}
    assert ref.classify(sample, meters(4, -1), 2) == 'great' and ref.classify(sample, meters(3, -1), 2) == 'ok'
    assert ref.classify(sample, meters(1, 0), 2) == 'ok' and ref.classify(sample, meters(1, -1), 2) == 'poor'
    assert ref.classify(sample, meters(2, 2), 1) == 'perfect' and ref.classify(sample, meters(6, 1), 3) == 'great'
    assert ref.classify(sample, meters(6, 6), 0) == 'poor', '沒有去任何一站，數值再高也是 poor'


def test_each_companion_says_goodbye_by_the_final_attitude():
    sample = game()
    lines = ref.farewells(sample, ['p1', 'p3', 'home'])  # 何以晴 +3、溫若岑 −4
    assert [(item['who'], item['value'], item['band']) for item in lines] == [('c1', 3, 'high'), ('c2', -4, 'low')]
    assert lines[0]['text'] == sample['farewells']['c1']['high'] and lines[1]['text'] == sample['farewells']['c2']['low']
    assert [item['band'] for item in ref.farewells(sample, ['home'])] == ['mid', 'mid']


def test_times_durations_and_values_are_written_the_way_the_player_shows_them():
    assert [ref.clock(value) for value in (0, 480, 507, 1439, 1440, 1500)] == ['00:00', '08:00', '08:27', '23:59', '00:00', '01:00']
    assert [ref.span(value) for value in (0, 5, 45, 60, 80, 600)] == ['0 分', '5 分', '45 分', '1 小時', '1 小時 20 分', '10 小時']
    assert [ref.signed(value) for value in (2, 0, -1)] == ['+2', '0', '−1']


def test_the_sample_reaches_every_kind_of_ending_and_calibration_keeps_poor_below_great():
    sample = game()
    kinds = {ref.classify(sample, ref.replay(sample, picks)['meters'], len(picks)) for picks in ref.routes(sample)}
    assert kinds == {'perfect', 'great', 'ok', 'poor'}
    flat = game(events=[{**event, 'reactions': {who: {**reaction, 'delta': 0} for who, reaction in event['reactions'].items()}} for event in sample['events']])
    result = ref.calibrate(flat)  # 每一站都不加不減：分布只有一個數字，門檻仍然要分得開
    assert result['thresholds']['poor'] < result['thresholds']['great'] and result['reachable'] == ['great', 'poor']


# ---- 播放器的純函式和參考實作逐項對照（Node） ----

NODE_SCRIPT = r"""
const rules = require('./app/export_player/route-1.js');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = input.routes.map(picks => {
  const state = rules.replay(input.data, picks);
  return {state: {steps: state.steps, here: state.here, now: state.res.now, visited: state.visited, done: state.done, meters: state.meters},
          options: rules.options(input.data, picks), ending: state.done ? rules.ending(input.data, picks) : null,
          farewells: state.done ? rules.farewells(input.data, picks) : null};
});
const text = {clock: input.clocks.map(rules.clock), span: input.spans.map(rules.span), signed: input.values.map(rules.signed),
              travel: input.pairs.map(([a, b, speed]) => rules.travel(a, b, speed))};
process.stdout.write(JSON.stringify({out, text}));
"""


def run_player(payload):
    node = os.environ.get('LIFEWORLD_NODE') or shutil.which('node')
    if not node:
        pytest.skip('需要 Node 執行播放器的純函式；可設定 LIFEWORLD_NODE')
    result = subprocess.run([node, '-e', NODE_SCRIPT], input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8')
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_the_player_computes_every_reachable_route_exactly_like_the_reference():
    sample = game()
    data = route_data(sample)  # 播放器讀的是匯出檔裡的資料（lw-route.v1），不是資料庫裡的那一份
    routes = [[]] + [picks for picks in ref.routes(sample)]
    routes += [picks + ['home'] for picks in routes]  # 每一條行程：走到一半的樣子，以及回到起點之後
    clocks, spans, values = [0, 480, 507, 1439, 1440, 1500], [0, 5, 45, 60, 80, 600], [2, 0, -1, 6, -6]
    pairs = [[{'x': 0, 'y': 0}, {'x': 3, 'y': 4}, 2.5], [{'x': 5, 'y': 5}, {'x': 5, 'y': 5}, 12], [{'x': 6, 'y': 6}, {'x': 10, 'y': 5}, 12]]
    result = run_player({'data': data, 'routes': routes, 'clocks': clocks, 'spans': spans, 'values': values, 'pairs': pairs})
    assert len(result['out']) == len(routes) > 800
    for picks, got in zip(routes, result['out']):
        assert got['state'] == ref.replay(sample, picks), picks
        assert got['options'] == ref.options(sample, picks), picks
        if picks and picks[-1] == 'home':
            assert got['ending'] == ref.ending(sample, picks), picks
            assert got['farewells'] == ref.farewells(sample, picks), picks
    assert result['text'] == {'clock': [ref.clock(value) for value in clocks], 'span': [ref.span(value) for value in spans],
                              'signed': [ref.signed(value) for value in values], 'travel': [ref.travel(*pair) for pair in pairs]}


def test_the_player_refuses_a_step_that_cannot_be_taken_and_handles_tight_schedules_like_the_reference():
    tight = game(clock={'start': 600, 'limit': 240})  # 10:00 出發、四小時：很多站來不及或趕不回來
    tight['endings'].update(ref.calibrate(tight))
    data = route_data(tight)
    routes = [[]] + [picks for picks in ref.routes(tight)]
    routes += [picks + ['home'] for picks in routes]
    result = run_player({'data': data, 'routes': routes + [['p2', 'p2'], ['p1'], ['nowhere'], ['home', 'p7']], 'clocks': [], 'spans': [], 'values': [], 'pairs': []})
    reasons = set()
    for picks, got in zip(routes, result['out']):
        assert got['state'] == ref.replay(tight, picks) and got['options'] == ref.options(tight, picks), picks
        reasons |= {item['reason'] for item in got['options']}
    assert reasons == {'', 'closed', 'late'}, '兩種不能去的原因都出現過'
    twice, blocked, unknown, after_home = result['out'][-4:]
    assert twice['state']['visited'] == ['p2'] and len(twice['state']['steps']) == 2, '去過的站不能再去：那一步不算'
    assert blocked['state']['visited'] == [] and len(blocked['state']['steps']) == 1, '來不及的站（晨光魚市十一點收攤）不能去'
    assert unknown['state']['visited'] == [] and len(unknown['state']['steps']) == 1, '不認得的代號不算'
    assert after_home['state']['done'] and len(after_home['state']['steps']) == 2, '回到起點之後的選擇不算'
