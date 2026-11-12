(function () {
  // Life World 離線播放器 route-1：回合制互動作品的路線播放器。
  // 玩法：使用者在自己的回合選下一步；選之前只看得到代價（時間），選了之後才看到每位同行者的反應與數值升降；最後依數值走到不同的結局。
  // 反應全部預先生成、寫在檔案的內嵌資料（lw-route.v1）裡：這段程式不連線、不呼叫模型，只是照資料與規則把遊戲演出來。
  //
  // 程式分兩層，之後加別的題材（登山、採購、劇情多結局……）只換第二層：
  // ・通用層：規則——數值的區間、到一個節點時每個人的反應與升降、把走過的選擇重放一遍、結局判定、最後一句話；
  //           畫面——同行者的數值列、左欄走過的路（可以點回去重選）、右欄目前的節點與反應、選項卡、結局演出（片尾字幕、特效、音樂）、
  //           重來、看過幾種結局、字級與深淺色、列印。
  // ・題材層（SKINS，現在只有「行程」）：資源怎麼算（時間：車程、等開門、打烊、趕不趕得回起點）、現在有哪些選項與不能選的原因、
  //           這些東西在畫面上怎麼寫（選項卡上的幾行、現在幾點還剩多久、行程表），以及題材自己的圖（示意地圖）。
  // 通用層不知道「時間」是什麼：它只把題材層給的資源狀態（res）原樣帶著走，要顯示時再交回題材層。
  //
  // 唯一的狀態是 picks（依序選了哪些節點）。畫面每次都從 picks 重放一遍算出來，所以「回到某一站重選」就是把 picks 截短——
  // 之後的選擇、時間與數值自然都回到當時，不需要另外記錄與還原。
  //
  // 規則的部分是純函式；在 Node 裡載入這個檔案時只匯出它們（給自動測試和 Python 的參考實作逐項對照），不碰畫面。
  // 沒有程式時頁面是靜態的清單（開場白、同行的人、所有站；反應、願望與結局收合）。看過的結局與閱讀偏好存在這個瀏覽器；
  // 存不了（直接點開的檔案被限制、放在站內的沙箱 iframe 裡）也照常可以玩，只是不會記得。

  // ======== 共用的寫法（純函式） ========
  function clock(minutes) { // 從 00:00 起算的分鐘數 → 'HH:MM'
    var hours = Math.floor(minutes / 60) % 24;
    var rest = minutes % 60;
    return (hours < 10 ? '0' : '') + hours + ':' + (rest < 10 ? '0' : '') + rest;
  }
  function span(minutes) { // 一段時間 → '45 分'、'2 小時'、'1 小時 20 分'
    var hours = Math.floor(minutes / 60);
    var rest = minutes % 60;
    return !hours ? rest + ' 分' : !rest ? hours + ' 小時' : hours + ' 小時 ' + rest + ' 分';
  }
  function signed(value) { // 數值：正數帶加號、負數用全形減號
    return value > 0 ? '+' + value : value < 0 ? '−' + (-value) : '0';
  }

  // ======== 通用層：規則 ========
  var CLASSES = ['perfect', 'great', 'ok', 'poor']; // 結局種類，由好到壞
  var CLASS_LABELS = {perfect: '完美結局', great: '好結局', ok: '普通結局', poor: '遺憾結局'};

  // 數值落在哪一個區間：決定用哪一句反應、最後說哪一句話
  function band(meter, value) { return value <= meter.low ? 'low' : value >= meter.high ? 'high' : 'mid'; }

  // 到一個事件：每位同行者先依「到之前」的區間說一句話，然後數值加減、夾在上下限之內。meters 會被就地更新。
  // change 是夾過之後實際變了多少——畫面標的升降用它，已經到頂再加也不會謊報。事件裡沒有寫到的人略過。
  function react(data, meters, event) {
    var result = [];
    data.cast.forEach(function (member) {
      var reaction = (event.reactions || {})[member.id];
      if (!reaction) return;
      var before = meters[member.id];
      var which = band(data.meter, before);
      var after = Math.max(data.meter.min, Math.min(data.meter.max, before + reaction.delta));
      meters[member.id] = after;
      result.push({who: member.id, band: which, text: reaction[which], before: before, after: after, change: after - before});
    });
    return result;
  }

  // 把 picks（依序選的節點；選起點＝結束）重放一遍。題材層（skin）負責資源與「現在能選什麼」，這裡負責順序、反應與數值。
  // 回傳 {steps, here, res, visited, done, meters}。每一步是題材層給的欄位，加上 node、among（選它的當下有幾個選項可以選；
  // 第一步是出發，沒有選擇，是 null）、final（這一步是不是結束）與 reactions。
  // 不能走的那一步（不認得、去過了、被擋住）不算，後面的也不看——畫面上本來就按不到，這是擋住不合理的輸入。
  function replay(data, skin, picks) {
    var meters = {};
    data.cast.forEach(function (member) { meters[member.id] = 0; });
    var events = {};
    data.events.forEach(function (event) { events[event.id] = event; });
    var first = skin.begin();
    first.step.node = data.home.id;
    first.step.among = null;
    first.step.final = false;
    first.step.reactions = [];
    var state = {steps: [first.step], here: data.home.id, res: first.res, visited: [], done: false, meters: meters};
    for (var index = 0; index < picks.length && !state.done; index += 1) {
      var open = skin.choices(state);
      var choice = null;
      var among = 0;
      open.forEach(function (item) {
        if (item.enabled) among += 1;
        if (item.enabled && item.id === picks[index] && !choice) choice = item;
      });
      if (!choice) break;
      var moved = choice.final ? skin.finish(state, choice) : skin.visit(state, choice);
      moved.step.node = choice.id;
      moved.step.among = among;
      moved.step.final = choice.final;
      moved.step.reactions = choice.final ? [] : react(data, meters, events[choice.id]);
      state.steps.push(moved.step);
      state.here = choice.id;
      state.res = moved.res;
      if (choice.final) state.done = true; else state.visited.push(choice.id);
    }
    return state;
  }

  // 結局種類。判斷的順序是規格定的：什麼都沒做 → poor；每個人都在 high 以上 → perfect；總和過了 great 的門檻 → great；
  // 總和在 poor 的門檻以下 → poor；其餘 ok。門檻是匯出前由伺服器依所有走得到的路線算好、寫在資料裡的。
  function classify(data, state) {
    if (!state.visited.length) return 'poor';
    var total = 0;
    var all = data.cast.length > 0;
    data.cast.forEach(function (member) {
      total += state.meters[member.id];
      if (state.meters[member.id] < data.meter.high) all = false;
    });
    var thresholds = data.endings.thresholds || {};
    if (all) return 'perfect';
    if (total >= thresholds.great) return 'great';
    if (total <= thresholds.poor) return 'poor';
    return 'ok';
  }

  // 結局時每位同行者的最後一句話：依最後的數值區間
  function farewells(data, state) {
    return data.cast.map(function (member) {
      var value = state.meters[member.id];
      var which = band(data.meter, value);
      return {who: member.id, value: value, band: which, text: ((data.farewells || {})[member.id] || {})[which] || ''};
    });
  }

  // ======== 題材層：行程 ========
  // 兩地車程（分鐘）＝max(5, 四捨五入(直線距離 × speed))；.5 進位（floor(x + 0.5)），和 Python 的參考實作同一種寫法
  function travel(a, b, speed) {
    var dx = a.x - b.x;
    var dy = a.y - b.y;
    return Math.max(5, Math.floor(Math.sqrt(dx * dx + dy * dy) * speed + 0.5));
  }

  function tripSkin(data) {
    var home = data.home;
    var deadline = data.clock.start + data.clock.limit; // 最晚幾點要回到起點
    var spots = {};
    spots[home.id] = home;
    data.events.forEach(function (event) { spots[event.id] = event; });

    // 現在（now）人在 here，去 event 這一站會怎樣。blocked：''＝可以去；'closed'＝停留完已經超過打烊；'late'＝去了就趕不回起點。
    // 早到就等開門；兩個原因同時成立時說打烊（那是這一站自己的限制，比較具體）。
    function leg(here, now, event) {
      var ride = travel(spots[here], event, data.speed);
      var arrive = now + ride;
      var begin = Math.max(arrive, event.open);
      var leave = begin + event.stay;
      var back = travel(event, home, data.speed);
      return {id: event.id, enabled: true, final: false, reason: leave > event.close ? 'closed' : leave + back > deadline ? 'late' : '',
              travel: ride, arrive: arrive, wait: begin - arrive, begin: begin, stay: event.stay, leave: leave, close: event.close, back: back};
    }

    var skin = {
      // ---- 規則（純函式） ----
      // 出發：資源狀態只有「現在幾點」
      begin: function () {
        var start = data.clock.start;
        return {step: {travel: 0, arrive: start, wait: 0, begin: start, stay: 0, leave: start}, res: {now: start}};
      },
      // 現在可以選什麼：每個還沒去過的站一個（能去的在前，各自依車程由近到遠，同樣遠的照原本的順序），最後是「回起點，結束」。
      // 已經回到起點就沒有選項。
      choices: function (state) {
        if (state.done) return [];
        var items = [];
        data.events.forEach(function (event, order) {
          if (state.visited.indexOf(event.id) >= 0) return;
          var item = leg(state.here, state.res.now, event);
          item.enabled = !item.reason;
          item.order = order;
          items.push(item);
        });
        items.sort(function (a, b) { return (a.enabled ? 0 : 1) - (b.enabled ? 0 : 1) || a.travel - b.travel || a.order - b.order; });
        items.forEach(function (item) { delete item.order; });
        var ride = state.here === home.id ? 0 : travel(spots[state.here], home, data.speed);
        items.push({id: home.id, enabled: true, final: true, reason: '', travel: ride, arrive: state.res.now + ride});
        return items;
      },
      // 去一站：時間走到離開那一站的時候
      visit: function (state, choice) {
        return {step: {travel: choice.travel, arrive: choice.arrive, wait: choice.wait, begin: choice.begin, stay: choice.stay, leave: choice.leave},
                res: {now: choice.leave}};
      },
      // 回起點：時間走到回到起點的時候
      finish: function (state, choice) {
        return {step: {travel: choice.travel, arrive: choice.arrive, wait: 0, begin: choice.arrive, stay: 0, leave: choice.arrive}, res: {now: choice.arrive}};
      },

      // ---- 畫面上的寫法 ----
      words: {trail: '走過的路', start: '準備出發', go: '出發', next: '接下來去哪？', finish: '回起點，結束行程', depart: '出發', back: '回到起點',
              again: '再走一次', none: '已經沒有來得及去的地方了，只能回起點。', table: '這一局的行程', used: '總共用了'},
      // 開始畫面的幾行說明
      intro: function () {
        return [clock(data.clock.start) + ' 從' + home.name + '出發', span(data.clock.limit) + '內要回到' + home.name + '（' + clock(deadline) + ' 前）',
                '可以去的地方有 ' + data.events.length + ' 站，時間不夠全部去——每一步都要選。'];
      },
      // 左欄每一步前面的時間
      when: function (step) { return clock(step.arrive); },
      // 右欄節點上方的一行：這一步花了多少時間
      detail: function (step, index) {
        if (index === 0) return clock(step.arrive) + ' 出發';
        var ride = '車程 ' + span(step.travel) + '・';
        if (step.final) return (step.travel ? ride : '') + clock(step.arrive) + ' 回到' + home.name;
        return ride + clock(step.arrive) + ' 到' + (step.wait ? '（等 ' + span(step.wait) + '開門）' : '') + '・停留 ' + span(step.stay) + '・' + clock(step.leave) + ' 離開';
      },
      // 現在幾點、還剩多少時間
      status: function (state) {
        return '現在 ' + clock(state.res.now) + '・還剩 ' + span(Math.max(0, deadline - state.res.now)) + '（' + clock(deadline) + ' 前要回到' + home.name + '）';
      },
      // 選項卡上的幾行：只有代價，沒有任何「會讓誰的數值升降」的東西
      rows: function (choice) {
        if (choice.final) return [['車程', choice.travel ? span(choice.travel) : '就在這裡'], ['回到' + home.name, clock(choice.arrive)]];
        var event = spots[choice.id];
        return [['車程', span(choice.travel)], ['到達', clock(choice.arrive) + (choice.wait ? '（等 ' + span(choice.wait) + '開門）' : '')],
                ['停留', span(choice.stay) + '，' + clock(choice.leave) + ' 離開'],
                ['打烊', event.open <= 0 && event.close >= 1440 ? '整天開放' : clock(choice.close)]];
      },
      // 不能選的原因
      why: function (choice) {
        return choice.reason === 'closed' ? '來不及：' + clock(choice.close) + ' 打烊' : choice.reason === 'late' ? '去了就趕不回起點' : '';
      },
      // 行程表（片尾字幕與列印共用）：{head, rows, total}；total 是已經用掉的時間
      table: function (state) {
        var rows = state.steps.map(function (step, index) {
          var name = spots[step.node].name;
          if (index === 0) return [clock(step.arrive), name + '（出發）', '—', '—'];
          if (step.final) return [clock(step.arrive), name + '（回到起點）', '—', step.travel ? span(step.travel) : '—'];
          return [clock(step.arrive), name, span(step.stay) + (step.wait ? '（先等 ' + span(step.wait) + '）' : ''), span(step.travel)];
        });
        return {head: ['時間', '地點', '停留', '車程'], rows: rows, total: span(state.res.now - data.clock.start)};
      },
      // 示意地圖：用 x、y 畫出起點與各站；走過的路線連起來，去過的站實心，現在的位置多一圈
      picture: function (state) {
        var SCALE = 10;
        var map = svg('svg', 'lw-map');
        map.setAttribute('viewBox', '-14 -12 128 124');
        map.setAttribute('role', 'img');
        map.setAttribute('aria-label', '示意地圖：起點與各站的相對位置，以及走過的路線');
        var path = state.steps.map(function (step) { return spots[step.node].x * SCALE + ',' + spots[step.node].y * SCALE; });
        if (path.length > 1) {
          var line = svg('polyline', 'lw-map-route');
          line.setAttribute('points', path.join(' '));
          map.appendChild(line);
        }
        function label(spot, been) {
          var text = svg('text', 'lw-map-label' + (been ? ' lw-been' : ''));
          // 起點的名字放在上面；比起點低的站把名字放在點的下面、其餘放在上面：起點附近的名字不會疊在一起。靠邊的點把字往內靠，不會跑出地圖
          // 字和點之間留下「現在的位置」那一圈的空間
          var below = spot !== home && (spot.y > home.y || spot.y <= 1);
          var anchor = spot.x <= 2 ? 'start' : spot.x >= 8 ? 'end' : 'middle';
          text.setAttribute('x', spot.x * SCALE + (anchor === 'start' ? -4 : anchor === 'end' ? 4 : 0));
          text.setAttribute('y', spot.y * SCALE + (below ? 10.5 : spot === home ? -7.5 : -6.5));
          text.setAttribute('text-anchor', anchor);
          text.textContent = spot.name;
          map.appendChild(text);
        }
        data.events.forEach(function (event) {
          var been = state.visited.indexOf(event.id) >= 0;
          var dot = svg('circle', 'lw-map-dot' + (been ? ' lw-been' : ''));
          dot.setAttribute('cx', event.x * SCALE);
          dot.setAttribute('cy', event.y * SCALE);
          dot.setAttribute('r', 2.4);
          map.appendChild(dot);
          label(event, been);
        });
        var base = svg('rect', 'lw-map-home');
        base.setAttribute('x', home.x * SCALE - 2.8);
        base.setAttribute('y', home.y * SCALE - 2.8);
        base.setAttribute('width', 5.6);
        base.setAttribute('height', 5.6);
        map.appendChild(base);
        label(home, true);
        var here = svg('circle', 'lw-map-here');
        here.setAttribute('cx', spots[state.here].x * SCALE);
        here.setAttribute('cy', spots[state.here].y * SCALE);
        here.setAttribute('r', 5);
        map.appendChild(here);
        return map;
      }
    };
    return skin;
  }

  var SKINS = {trip: tripSkin};

  // 在 Node 裡（自動測試）只匯出規則，不往下碰畫面
  if (typeof module === 'object' && module && module.exports) {
    var ruled = function (data, picks) { return replay(data, SKINS[data.skin](data), picks); };
    module.exports = {
      clock: clock, span: span, signed: signed, travel: travel, replay: ruled,
      options: function (data, picks) { return SKINS[data.skin](data).choices(ruled(data, picks)); },
      ending: function (data, picks) { return classify(data, ruled(data, picks)); },
      farewells: function (data, picks) { return farewells(data, ruled(data, picks)); }
    };
    return;
  }

  // ======== 通用層：畫面 ========
  var root = document.documentElement;
  var tools = document.querySelector('.lw-tools');
  var stage = document.querySelector('.lw-game');
  var source = document.getElementById('lw-story');
  if (!tools || !stage || !source) return;
  var data = null;
  try { data = JSON.parse(source.textContent); } catch (error) { data = null; }
  // 讀不懂的資料、不認得的題材：什麼都不動，頁面維持靜態的清單
  if (!data || data.format !== 'lw-route.v1' || !SKINS[data.skin] || !data.cast || !data.events || !data.home || !data.meter || !data.clock || !data.endings) return;
  var skin = SKINS[data.skin](data);
  var words = skin.words;

  function list(selector, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(selector)); }
  function hit(event, selector) { return event.target && event.target.closest ? event.target.closest(selector) : null; }
  // 沙箱裡（站內的 iframe、某些直接點開檔案的情況）連碰 localStorage 都會丟例外：讀寫一律包起來，存不了就當成沒有
  function read(key) { try { return window.localStorage.getItem(key); } catch (error) { return null; } }
  function write(key, value) { try { window.localStorage.setItem(key, value); } catch (error) { /* 存不了不影響遊戲 */ } }
  function readObject(key) {
    try {
      var value = JSON.parse(read(key) || 'null');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (error) { return {}; }
  }
  // 程式新增的元素一律用 textContent 放文字：資料裡的內容不會被當成標籤解析
  function make(tag, name, text) {
    var element = document.createElement(tag);
    if (name) element.className = name;
    if (text !== undefined && text !== null && text !== '') element.textContent = text;
    if (tag === 'button') element.type = 'button';
    return element;
  }
  function svg(tag, name) {
    var element = document.createElementNS('http://www.w3.org/2000/svg', tag);
    if (name) element.setAttribute('class', name);
    return element;
  }
  function empty(element) { while (element.firstChild) element.removeChild(element.firstChild); }
  function add(parent) { // add(parent, child, child…)：略過空的
    for (var index = 1; index < arguments.length; index += 1) if (arguments[index]) parent.appendChild(arguments[index]);
    return parent;
  }
  // 系統的「減少動態效果」：這時不放動畫特效、數值直接到位、字幕直接顯示全文。每次要用時才問，使用者中途改設定也算數
  function calm() { return Boolean(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }

  // ---- 閱讀偏好 ----
  // 字級與深淺色和閱讀版、互動版共用同一個鍵：同一個瀏覽器裡三種檔案的設定一致。這裡不認得的欄位（例如場景提示）原樣留著。
  var KEY = 'lw-reader-prefs';
  var SIZES = ['s', 'm', 'l', 'xl'];
  var saved = readObject(KEY);
  var prefs = {theme: typeof saved.theme === 'string' ? saved.theme : '', size: typeof saved.size === 'string' ? saved.size : 'm'};

  function isDark() {
    var theme = root.getAttribute('data-theme');
    if (theme) return theme === 'dark';
    return Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function apply() {
    if (prefs.theme === 'dark' || prefs.theme === 'light') root.setAttribute('data-theme', prefs.theme);
    else root.removeAttribute('data-theme');
    root.setAttribute('data-size', SIZES.indexOf(prefs.size) < 0 ? 'm' : prefs.size);
    var theme = tools.querySelector('[data-tool=theme]');
    if (theme) theme.textContent = isDark() ? '淺色' : '深色';
    saved.theme = prefs.theme;
    saved.size = prefs.size;
    write(KEY, JSON.stringify(saved));
  }

  // ---- 狀態 ----
  var picks = []; // 依序選了哪些節點：唯一的遊戲狀態
  var phase = 'start'; // start：還沒出發；play：進行中；end：結局
  var trailOpen = false; // 手機寬度時，「走過的路」有沒有展開
  var pending = null; // 等著讓數值動起來的計時器（到站後先看反應，再看升降）
  var MOVE_AFTER = 700; // 反應出現之後多久，數值才開始動（毫秒）
  var nodes = {};
  nodes[data.home.id] = data.home;
  data.events.forEach(function (event) { nodes[event.id] = event; });
  var people = {};
  data.cast.forEach(function (member) { people[member.id] = member; });

  // 看過的結局記在這個瀏覽器；鍵帶著作品標題，不同作品不會互相覆蓋。存不了時只記在這一次開啟裡。
  var ENDINGS_KEY = 'lw-route-endings:' + data.title;
  var endingsSeen = readObject(ENDINGS_KEY);

  function seenText() {
    // 分母用資料裡「實際走得到的結局種類」；萬一走出了不在裡面的種類，也算進去（不會出現 5／4）
    var all = (data.endings.reachable || []).filter(function (name) { return CLASSES.indexOf(name) >= 0; });
    CLASSES.forEach(function (name) { if (endingsSeen[name] && all.indexOf(name) < 0) all.push(name); });
    var have = all.filter(function (name) { return endingsSeen[name]; }).length;
    return '已看過 ' + have + '／' + all.length + ' 種結局';
  }

  // ---- 固定的骨架：數值列、左欄、右欄、列印用的行程表、給報讀器的一句話 ----
  var castBar = make('section', 'lw-cast');
  castBar.setAttribute('aria-label', '同行的人與' + data.meter.label);
  var meters = data.cast.map(function (member) {
    var box = make('div', 'lw-meter');
    box.setAttribute('data-c', member.color);
    box.setAttribute('data-who', member.id);
    var bar = make('span', 'lw-bar');
    bar.setAttribute('aria-hidden', 'true');
    var zero = make('span', 'lw-bar-zero');
    var fill = make('span', 'lw-bar-fill');
    add(bar, fill, zero);
    var value = make('span', 'lw-meter-value', '0');
    var delta = make('span', 'lw-delta');
    add(box, make('span', 'lw-name', member.name), make('span', 'lw-meter-label', data.meter.label), bar, value, delta);
    castBar.appendChild(box);
    return {id: member.id, zero: zero, fill: fill, value: value, delta: delta};
  });
  var cols = make('div', 'lw-cols');
  var trail = make('aside', 'lw-trail');
  trail.setAttribute('aria-label', words.trail);
  var trailToggle = make('button', 'lw-trail-toggle');
  trailToggle.setAttribute('data-play', 'trail');
  var trailBody = make('div', 'lw-trail-body');
  var trailList = make('ol', 'lw-trail-list');
  var trailHint = make('p', 'lw-trail-hint', '點任何一步，回到當時重新選（之後的選擇會作廢）。');
  var mapSlot = make('div', 'lw-picture');
  add(trailBody, make('h2', 'lw-trail-title', words.trail), trailHint, trailList);
  add(trail, trailToggle, trailBody);
  var now = make('section', 'lw-now');
  add(cols, trail, now);
  var spoken = make('p', 'lw-sr');
  spoken.setAttribute('role', 'status');
  add(stage, castBar, cols, spoken);
  var printout = make('section', 'lw-print');
  stage.parentNode.insertBefore(printout, stage.nextSibling);

  // ---- 數值列 ----
  // 條狀圖：中間偏左或偏右的那條線是 0，往右是正、往左是負；寬度由程式直接設在元素上（頁面的 CSP 不放行行內樣式屬性，但允許程式這樣設）。
  function showMeter(view, value, change) {
    var range = data.meter.max - data.meter.min || 1;
    var zero = (0 - data.meter.min) / range * 100;
    var at = (Math.max(data.meter.min, Math.min(data.meter.max, value)) - data.meter.min) / range * 100;
    view.zero.style.left = zero + '%';
    view.fill.style.left = Math.min(zero, at) + '%';
    view.fill.style.width = Math.abs(at - zero) + '%';
    view.value.textContent = signed(value);
    showDelta(view.delta, change);
  }

  // 升降的標示：▲ +2、▼ −1；沒有變就不標
  function showDelta(element, change) {
    element.className = 'lw-delta' + (change > 0 ? ' lw-up' : change < 0 ? ' lw-down' : '');
    element.textContent = change > 0 ? '▲ ' + signed(change) : change < 0 ? '▼ ' + signed(change) : '';
    element.hidden = !change;
  }

  function settle() { // 還在等的升降直接到位（使用者已經按了下一步，或畫面要重畫）
    if (pending) {
      window.clearTimeout(pending.timer);
      pending.finish();
      pending = null;
    }
  }

  // arrived：剛剛才走到這一步（不是回頭看）。這時先讓反應出現、數值停在到站前，過一會兒才動起來並標出升降；
  // 回頭看某一步、或系統要求減少動態效果時，直接顯示到站後的數值與升降。
  function drawMeters(state, arrived) {
    var last = state.steps[state.steps.length - 1];
    var changes = {};
    var befores = {};
    last.reactions.forEach(function (item) {
      changes[item.who] = item.change;
      befores[item.who] = item.before;
    });
    var deltas = list('.lw-reaction .lw-delta', now);
    function finish() {
      meters.forEach(function (view) { showMeter(view, state.meters[view.id], phase === 'play' ? changes[view.id] || 0 : 0); });
      deltas.forEach(function (element) { element.hidden = !element.textContent; });
      stage.setAttribute('data-settled', '1');
    }
    if (!arrived || calm() || !last.reactions.length) { finish(); return; }
    stage.removeAttribute('data-settled');
    meters.forEach(function (view) { showMeter(view, befores[view.id] === undefined ? state.meters[view.id] : befores[view.id], 0); });
    deltas.forEach(function (element) { element.hidden = true; });
    pending = {finish: finish, timer: window.setTimeout(function () { pending = null; finish(); }, MOVE_AFTER)};
  }

  // ---- 左欄：走過的路 ----
  // 每一步是一顆按鈕（錨點）：到達時間、名稱、當時是幾選一。按了回到那一步當時的狀態；現在所在的那一步標成目前位置、按了沒有作用。
  function drawTrail(state) {
    empty(trailList);
    var current = state.steps.length - 1;
    state.steps.forEach(function (step, index) {
      var button = make('button', 'lw-step');
      button.setAttribute('data-step', index);
      if (index === current) button.setAttribute('aria-current', 'step');
      var among = index === 0 ? words.depart : step.among > 1 ? step.among + ' 選 1' : '沒有別的選擇';
      add(button, make('span', 'lw-step-time', skin.when(step)), make('span', 'lw-step-name', nodes[step.node].name),
          make('span', 'lw-step-among', (step.final ? words.back + '・' : '') + among));
      trailList.appendChild(add(make('li'), button));
    });
    trailHint.hidden = state.steps.length < 2;
    trail.hidden = phase === 'start';
    trail.setAttribute('data-open', trailOpen ? '1' : '0');
    trailToggle.setAttribute('aria-expanded', trailOpen ? 'true' : 'false');
    empty(trailToggle);
    add(trailToggle, make('span', '', words.trail + '（' + (state.visited.length ? '去過 ' + state.visited.length + ' 站' : '剛出發') + '）'),
        make('span', '', trailOpen ? '收起 ▴' : '展開 ▾'));
  }

  // ---- 題材的圖（行程：示意地圖）----
  // 還沒出發時放在開始畫面裡；出發之後放在左欄、走過的路下面
  function drawPicture(state, where) {
    empty(mapSlot);
    var picture = skin.picture ? skin.picture(state) : null;
    if (picture) mapSlot.appendChild(picture);
    where.appendChild(mapSlot);
  }

  // ---- 右欄：開始畫面 ----
  function drawStart(state) {
    var box = make('section', 'lw-start');
    var intro = make('ul', 'lw-intro');
    skin.intro().forEach(function (line) { intro.appendChild(make('li', '', line)); });
    var go = make('button', 'lw-go', words.go);
    go.setAttribute('data-play', 'start');
    add(box, make('h2', 'lw-start-title', words.start), intro,
        make('p', 'lw-start-note', '同行的人各有各的期待，但不會先說。到了每一站，他們的反應與「' + data.meter.label + '」的升降會告訴你。'));
    drawPicture(state, box);
    add(box, add(make('p', 'lw-start-go'), go));
    now.appendChild(box);
  }

  // ---- 右欄：目前的節點、每個人的反應、接下來的選項 ----
  function drawNode(state, arrived) {
    var index = state.steps.length - 1;
    var step = state.steps[index];
    var node = nodes[step.node];
    var card = make('article', 'lw-node' + (arrived ? ' lw-arrive' : ''));
    var name = make('h2', 'lw-node-name', node.name);
    name.setAttribute('tabindex', '-1'); // 走到新的一步時把焦點放在這裡：報讀器念出站名，鍵盤再按 Tab 就是第一張選項卡
    add(card, make('p', 'lw-node-when', skin.detail(step, index)), name, make('p', 'lw-node-text', node.text));
    if (step.reactions.length) {
      var reactions = make('ul', 'lw-reactions');
      step.reactions.forEach(function (item) {
        var member = people[item.who];
        var row = make('li', 'lw-reaction');
        row.setAttribute('data-c', member.color);
        row.setAttribute('data-who', item.who);
        var delta = make('span', 'lw-delta');
        showDelta(delta, item.change);
        if (item.change) delta.textContent += ' ' + data.meter.label; // ▲ +2 滿意
        add(row, add(make('p', 'lw-reaction-head'), make('span', 'lw-name', member.name), delta), make('p', 'lw-reaction-text', item.text));
        reactions.appendChild(row);
      });
      card.appendChild(reactions);
    }
    card.appendChild(make('p', 'lw-clock', skin.status(state)));
    now.appendChild(card);

    var open = skin.choices(state);
    var section = make('section', 'lw-options');
    section.setAttribute('aria-label', words.next);
    section.appendChild(make('h2', 'lw-options-title', words.next));
    if (!open.some(function (choice) { return choice.enabled && !choice.final; })) section.appendChild(make('p', 'lw-options-note', words.none));
    var cards = make('ul', 'lw-option-list');
    open.forEach(function (choice) {
      var target = nodes[choice.id];
      var button = make('button', 'lw-option' + (choice.final ? ' lw-option-home' : ''));
      button.setAttribute('data-go', choice.id);
      // 不能去的只標成不能按（不用 disabled）：鍵盤與報讀器仍然走得到、讀得到原因
      if (!choice.enabled) button.setAttribute('aria-disabled', 'true');
      var title = make('span', 'lw-option-name', choice.final ? words.finish : target.name);
      if (!choice.final) (target.tags || []).forEach(function (tag) { title.appendChild(make('span', 'lw-tag', tag)); });
      var rows = make('span', 'lw-option-rows');
      skin.rows(choice).forEach(function (row) { add(rows, make('span', 'lw-key', row[0]), make('span', 'lw-val', row[1])); });
      add(button, title, choice.final ? null : make('span', 'lw-option-text', target.text), rows);
      if (!choice.enabled) button.appendChild(make('span', 'lw-option-why', skin.why(choice)));
      cards.appendChild(add(make('li'), button));
    });
    section.appendChild(cards);
    now.appendChild(section);

    var said = step.reactions.map(function (item) { return people[item.who].name + ' ' + data.meter.label + ' ' + signed(item.change); });
    spoken.textContent = (index === 0 ? '' : '到了' + node.name + '。' + (said.length ? said.join('；') + '。' : '')) + skin.status(state);
  }

  // ---- 行程表（片尾字幕與列印共用）----
  function tableOf(info) {
    var table = make('table', 'lw-table');
    var head = make('tr');
    info.head.forEach(function (cell) { head.appendChild(make('th', '', cell)); });
    table.appendChild(add(make('thead'), head));
    var body = make('tbody');
    info.rows.forEach(function (cells) {
      var row = make('tr');
      cells.forEach(function (cell) { row.appendChild(make('td', '', cell)); });
      body.appendChild(row);
    });
    table.appendChild(body);
    return table;
  }

  // 列印：只印目前走出來的行程表（螢幕上不顯示這一塊）。走到一半印就是到目前為止的；走完了多一行結局。
  function drawPrint(state, kind) {
    empty(printout);
    if (phase === 'start') return;
    var info = skin.table(state);
    add(printout, make('h2', 'lw-print-title', words.table), tableOf(info), make('p', 'lw-print-total', words.used + ' ' + info.total));
    if (kind) printout.appendChild(make('p', 'lw-print-ending', '結局：' + ((data.endings.classes[kind] || {}).title || CLASS_LABELS[kind])));
  }

  // ---- 結局演出 ----
  var fx = null; // 進行中的特效：{canvas, frame, dusk}
  var music = null; // 播放中的音樂：{context, timer}

  // 特效都是自己畫的（canvas），沒有外部素材。kind：fireworks（煙火）、confetti（紙花）、rain（下雨）。
  // 畫布固定在視窗上、不擋滑鼠；離開結局畫面就移除。系統要求減少動態效果時根本不建立。
  function fxOn(kind) {
    fxOff();
    if (calm() || !kind) return;
    var canvas = make('canvas', 'lw-fx');
    canvas.setAttribute('data-fx', kind);
    canvas.setAttribute('aria-hidden', 'true');
    document.body.appendChild(canvas);
    var pen = canvas.getContext && canvas.getContext('2d');
    fx = {canvas: canvas, frame: 0, dusk: null};
    if (kind === 'rain') { // 不好的結局：畫面慢慢暗下來
      fx.dusk = make('div', 'lw-dusk');
      fx.dusk.setAttribute('aria-hidden', 'true');
      document.body.appendChild(fx.dusk);
      window.setTimeout(function () { if (fx && fx.dusk) fx.dusk.classList.add('lw-on'); }, 50);
    }
    if (!pen) return;
    var COLORS = ['#ffcf5c', '#ff7a7a', '#7cc0ff', '#8fd0ae', '#c9a0ff', '#ffffff'];
    var bits = [];
    var began = Date.now();
    var last = began;
    var nextBurst = 0;
    var mine = fx;
    function size() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    size();
    window.addEventListener('resize', size);
    mine.stop = function () { window.removeEventListener('resize', size); };
    function pick(items) { return items[Math.floor(Math.random() * items.length)]; }
    function spawn(elapsed) {
      var width = canvas.width;
      var height = canvas.height;
      if (kind === 'fireworks' && elapsed < 9000 && elapsed >= nextBurst) { // 每隔半秒多在上半部炸開一朵
        nextBurst = elapsed + 450 + Math.random() * 500;
        var x = width * (0.15 + Math.random() * 0.7);
        var y = height * (0.12 + Math.random() * 0.38);
        var color = pick(COLORS);
        for (var index = 0; index < 46; index += 1) {
          var angle = Math.PI * 2 * index / 46;
          var speed = 90 + Math.random() * 150;
          bits.push({x: x, y: y, vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed, life: 1.3 + Math.random() * 0.5, age: 0, color: color});
        }
      }
      if (kind === 'confetti' && elapsed < 7000 && bits.length < 160) { // 紙花從上面飄下來
        for (var count = 0; count < 3; count += 1) {
          bits.push({x: Math.random() * width, y: -10, vx: -30 + Math.random() * 60, vy: 70 + Math.random() * 90, life: 9, age: 0, color: pick(COLORS),
                     spin: Math.random() * 6, size: 6 + Math.random() * 6});
        }
      }
      if (kind === 'rain' && elapsed < 40000 && bits.length < 140) {
        for (var drop = 0; drop < 4; drop += 1) {
          bits.push({x: Math.random() * (width + 80), y: -20, vx: -60, vy: 620 + Math.random() * 260, life: 3, age: 0, size: 10 + Math.random() * 14});
        }
      }
    }
    function tick() {
      if (fx !== mine) return;
      var nowAt = Date.now();
      var dt = Math.min(0.05, (nowAt - last) / 1000);
      last = nowAt;
      spawn(nowAt - began);
      pen.clearRect(0, 0, canvas.width, canvas.height);
      bits = bits.filter(function (bit) {
        bit.age += dt;
        bit.x += bit.vx * dt;
        bit.y += bit.vy * dt;
        if (kind === 'fireworks') bit.vy += 120 * dt; // 火花往下掉
        var left = 1 - bit.age / bit.life;
        if (left <= 0 || bit.y > canvas.height + 30) return false;
        if (kind === 'rain') {
          pen.strokeStyle = 'rgba(150,170,190,0.45)';
          pen.lineWidth = 1;
          pen.beginPath();
          pen.moveTo(bit.x, bit.y);
          pen.lineTo(bit.x + bit.vx * 0.02, bit.y + bit.size);
          pen.stroke();
        } else if (kind === 'confetti') {
          pen.save();
          pen.translate(bit.x, bit.y);
          pen.rotate(bit.spin + bit.age * 3);
          pen.globalAlpha = Math.min(1, left * 3);
          pen.fillStyle = bit.color;
          pen.fillRect(-bit.size / 2, -bit.size / 4, bit.size, bit.size / 2);
          pen.restore();
        } else {
          pen.globalAlpha = Math.max(0, left);
          pen.fillStyle = bit.color;
          pen.beginPath();
          pen.arc(bit.x, bit.y, 2.2, 0, Math.PI * 2);
          pen.fill();
          pen.globalAlpha = 1;
        }
        return true;
      });
      mine.frame = window.requestAnimationFrame(tick);
    }
    mine.frame = window.requestAnimationFrame(tick);
  }

  function fxOff() {
    if (!fx) return;
    if (fx.frame) window.cancelAnimationFrame(fx.frame);
    if (fx.stop) fx.stop();
    if (fx.canvas.parentNode) fx.canvas.parentNode.removeChild(fx.canvas);
    if (fx.dusk && fx.dusk.parentNode) fx.dusk.parentNode.removeChild(fx.dusk);
    fx = null;
  }

  // 音樂：用 Web Audio 即時合成的簡單旋律，沒有音檔。預設不播——使用者按了「開啟音樂」才建立音訊，可以再關掉。
  // 好結局明亮（大調、快）、普通的結局平靜、不好的結局低沉緩慢（小調、慢）。音符是相對於 A4（440Hz）的半音數，null 是休止。
  var TUNES = {
    bright: {wave: 'triangle', beat: 0.26, volume: 0.16, notes: [3, 7, 10, 7, 12, 10, 7, 10, 15, 10, 7, 3, 5, 7, 3, null]},
    calm: {wave: 'sine', beat: 0.62, volume: 0.14, notes: [-5, -2, 0, -2, -5, -7, -9, null]},
    dark: {wave: 'sine', beat: 0.95, volume: 0.18, notes: [-12, -9, -5, -9, -10, -12, -13, null]}
  };

  function musicOn(kind) {
    musicOff();
    var Synth = window.AudioContext || window.webkitAudioContext;
    if (!Synth) return false;
    var context;
    try { context = new Synth(); } catch (error) { return false; }
    var tune = TUNES[kind] || TUNES.calm;
    var master = context.createGain();
    master.gain.value = tune.volume;
    master.connect(context.destination);
    var next = context.currentTime + 0.08;
    var index = 0;
    function schedule() { // 一次只排接下來不到一秒的音符：關掉時不會留下一長串還沒播的
      while (next < context.currentTime + 0.8) {
        var note = tune.notes[index % tune.notes.length];
        if (note !== null) {
          var voice = context.createOscillator();
          var envelope = context.createGain();
          voice.type = tune.wave;
          voice.frequency.value = 440 * Math.pow(2, note / 12);
          envelope.gain.setValueAtTime(0.0001, next);
          envelope.gain.linearRampToValueAtTime(1, next + 0.03);
          envelope.gain.exponentialRampToValueAtTime(0.0001, next + tune.beat * 0.95);
          voice.connect(envelope);
          envelope.connect(master);
          voice.start(next);
          voice.stop(next + tune.beat);
        }
        next += tune.beat;
        index += 1;
      }
    }
    schedule();
    music = {context: context, timer: window.setInterval(schedule, 250)};
    root.setAttribute('data-music', 'on');
    try { // 有些瀏覽器建立時是暫停的：使用者剛按了按鈕，可以直接繼續。繼續不了就是沒有聲音，不影響其他東西
      var resumed = context.resume && context.resume();
      if (resumed && resumed.catch) resumed.catch(function () { /* 沒有聲音 */ });
    } catch (error) { /* 沒有聲音 */ }
    return true;
  }

  function musicOff() {
    root.setAttribute('data-music', 'off'); // 頁面上的標記跟著實際的狀態：不管是按了關閉，還是離開結局畫面時一起關掉
    if (!music) return;
    window.clearInterval(music.timer);
    try {
      var closed = music.context.close();
      if (closed && closed.catch) closed.catch(function () { /* 已經關了 */ });
    } catch (error) { /* 已經關了 */ }
    music = null;
  }

  function drawMusic(button) {
    button.setAttribute('aria-pressed', music ? 'true' : 'false');
    button.textContent = music ? '關閉音樂' : '開啟音樂';
  }

  var MOODS = {perfect: {fx: 'fireworks', tune: 'bright'}, great: {fx: 'confetti', tune: 'bright'}, ok: {fx: '', tune: 'calm'}, poor: {fx: 'rain', tune: 'dark'}};

  // 結局畫面：結局卡（種類、標題、文字）→ 每位同行者最後的數值、最後一句話，以及這時才揭曉的願望 → 音樂、再走一次、看過幾種結局 → 片尾字幕。
  function drawFinale(state, kind) {
    var ending = data.endings.classes[kind] || {title: CLASS_LABELS[kind], text: ''};
    var info = skin.table(state);
    var finale = make('section', 'lw-finale');
    finale.setAttribute('data-ending', kind);
    finale.setAttribute('aria-label', '結局');
    var title = make('h2', 'lw-ending-title', ending.title);
    title.setAttribute('tabindex', '-1');
    var lastStep = state.steps[state.steps.length - 1];
    finale.appendChild(add(make('div', 'lw-ending'), make('p', 'lw-ending-kind', CLASS_LABELS[kind]), title, make('p', 'lw-ending-text', ending.text),
                           make('p', 'lw-ending-when', skin.detail(lastStep, state.steps.length - 1) + '・' + words.used + ' ' + info.total)));

    var lines = make('ul', 'lw-farewells');
    farewells(data, state).forEach(function (item) {
      var member = people[item.who];
      var row = make('li', 'lw-farewell');
      row.setAttribute('data-c', member.color);
      row.setAttribute('data-who', item.who);
      add(row, add(make('p', 'lw-farewell-head'), make('span', 'lw-name', member.name), make('span', 'lw-farewell-value', data.meter.label + ' ' + signed(item.value))),
          make('p', 'lw-farewell-text', item.text));
      var wish = (data.wishes || {})[item.who];
      if (wish) row.appendChild(add(make('p', 'lw-wish'), make('span', 'lw-label', '沒說出口的願望'), document.createTextNode(wish)));
      lines.appendChild(row);
    });
    finale.appendChild(lines);

    var bar = make('div', 'lw-finale-tools');
    var again = make('button', 'lw-go', words.again);
    again.setAttribute('data-play', 'again');
    var sound = make('button', 'lw-music');
    sound.setAttribute('data-play', 'music');
    sound.hidden = !(window.AudioContext || window.webkitAudioContext); // 這個瀏覽器不能合成聲音就不放這顆按鈕
    drawMusic(sound);
    add(bar, again, sound, make('p', 'lw-endings-seen', seenText()));
    finale.appendChild(bar);

    // 片尾字幕：由下往上捲一次，捲完停在全文；可以略過。系統要求減少動態效果時直接顯示全文、沒有捲動。
    var credits = make('div', 'lw-credits');
    credits.setAttribute('aria-label', '片尾字幕');
    var roll = make('div', 'lw-credits-roll');
    add(roll, make('p', 'lw-credits-title', data.title), make('p', 'lw-credits-head', '同行'),
        make('p', 'lw-credits-line', data.cast.map(function (member) { return member.name; }).join('　')),
        make('p', 'lw-credits-head', '你扮演'), make('p', 'lw-credits-line', data.player && data.player.name ? data.player.name : '你'),
        make('p', 'lw-credits-head', words.table), tableOf(info), make('p', 'lw-credits-head', words.used), make('p', 'lw-credits-line', info.total),
        make('p', 'lw-credits-head', '結局'), make('p', 'lw-credits-line', ending.title), make('p', 'lw-credits-end', 'Life World'));
    credits.appendChild(roll);
    if (calm()) {
      credits.classList.add('lw-still');
    } else {
      var skip = make('button', 'lw-credits-skip', '略過字幕');
      skip.setAttribute('data-play', 'skip');
      credits.appendChild(skip);
      roll.style.animationDuration = Math.max(18, 10 + info.rows.length * 4) + 's'; // 行程越長捲得越久，讀得完
      roll.addEventListener('animationend', function () { stillCredits(credits); });
    }
    finale.appendChild(credits);
    now.appendChild(finale);

    spoken.textContent = CLASS_LABELS[kind] + '：' + ending.title + '。' + seenText();
  }

  function stillCredits(credits) {
    credits.classList.add('lw-still');
    var skip = credits.querySelector('.lw-credits-skip');
    if (skip) skip.parentNode.removeChild(skip);
  }

  // ---- 重畫 ----
  // arrived：這次重畫是因為剛走了一步（要演出反應與升降、把焦點帶到新的節點）；回頭看、重來、切換時是 false。
  function render(arrived) {
    settle();
    var state = replay(data, skin, picks);
    var kind = phase === 'end' ? classify(data, state) : '';
    root.setAttribute('data-phase', phase);
    if (kind === 'poor') root.setAttribute('data-mood', 'poor'); else root.removeAttribute('data-mood');
    empty(now);
    drawTrail(state);
    if (phase === 'start') {
      spoken.textContent = '';
      drawStart(state);
    } else {
      drawPicture(state, trailBody);
      if (phase === 'end') drawFinale(state, kind); else drawNode(state, arrived);
    }
    drawMeters(state, arrived && phase === 'play');
    drawPrint(state, kind);
    return state;
  }

  function show(element) { // 把新的內容帶進畫面，焦點放上去
    if (!element) return;
    // 捲到左右兩欄的開頭：手機寬度時「走過的路」那一列也在畫面裡。上面留下數值列的高度（它固定在畫面頂端，同行者多時會排成好幾列）
    cols.style.scrollMarginTop = (castBar.offsetHeight + 12) + 'px';
    if (cols.scrollIntoView) cols.scrollIntoView({block: 'start'});
    if (element.focus) element.focus({preventScroll: true});
  }

  function leaveFinale() {
    fxOff();
    musicOff();
  }

  function start() {
    phase = 'play';
    picks = [];
    render(true);
    show(now.querySelector('.lw-node-name'));
  }

  // 選了一張選項卡：往下走一步。選的是「回起點」就進結局。
  function go(id) {
    if (phase !== 'play') return;
    var before = replay(data, skin, picks);
    var allowed = skin.choices(before).some(function (choice) { return choice.id === id && choice.enabled; });
    if (!allowed) return;
    picks.push(id);
    if (id === data.home.id) {
      phase = 'end';
      var kind = classify(data, replay(data, skin, picks));
      if (!endingsSeen[kind]) { // 先記下這個結局，結局畫面上的「已看過 n／N 種」才包含這一次
        endingsSeen[kind] = 1;
        write(ENDINGS_KEY, JSON.stringify(endingsSeen));
      }
      render(true);
      fxOn(MOODS[kind].fx);
      show(now.querySelector('.lw-ending-title'));
    } else {
      render(true);
      show(now.querySelector('.lw-node-name'));
    }
  }

  // 回到第 index 步當時的狀態：之後的選擇作廢（picks 截短），時間與數值自然回到當時。按的是現在這一步就沒有作用。
  function rewind(index) {
    if (phase === 'start' || !(index >= 0) || index >= picks.length) return; // 最後一步（index 等於 picks 的長度）就是現在的位置
    leaveFinale();
    picks = picks.slice(0, index);
    phase = 'play';
    render(false);
    show(now.querySelector('.lw-node-name'));
  }

  // 再走一次：回到出發之前。看過哪些結局留著。
  function again() {
    leaveFinale();
    picks = [];
    phase = 'start';
    trailOpen = false;
    render(false);
    window.scrollTo(0, 0);
    var first = now.querySelector('[data-play=start]');
    if (first) first.focus({preventScroll: true});
  }

  document.addEventListener('click', function (event) {
    var step = hit(event, '.lw-step');
    if (step) {
      rewind(Number(step.getAttribute('data-step')));
      return;
    }
    var option = hit(event, '.lw-option');
    if (option) {
      if (option.getAttribute('aria-disabled') !== 'true') go(option.getAttribute('data-go'));
      return;
    }
    var button = hit(event, 'button[data-play]');
    if (!button) return;
    var what = button.getAttribute('data-play');
    if (what === 'start') {
      start();
    } else if (what === 'again') {
      again();
    } else if (what === 'trail') {
      trailOpen = !trailOpen;
      trail.setAttribute('data-open', trailOpen ? '1' : '0');
      trailToggle.setAttribute('aria-expanded', trailOpen ? 'true' : 'false');
      trailToggle.lastChild.textContent = trailOpen ? '收起 ▴' : '展開 ▾';
    } else if (what === 'music') {
      if (music) {
        musicOff();
      } else {
        var kind = (now.querySelector('.lw-finale') || button).getAttribute('data-ending');
        musicOn((MOODS[kind] || MOODS.ok).tune);
      }
      drawMusic(button);
    } else if (what === 'skip') {
      stillCredits(button.parentNode);
    }
  });

  tools.addEventListener('click', function (event) {
    var button = hit(event, 'button[data-tool]');
    if (!button) return;
    var tool = button.getAttribute('data-tool');
    if (tool === 'smaller' || tool === 'larger') {
      var index = SIZES.indexOf(prefs.size);
      if (index < 0) index = 1;
      prefs.size = SIZES[Math.max(0, Math.min(SIZES.length - 1, index + (tool === 'larger' ? 1 : -1)))];
    } else if (tool === 'theme') {
      prefs.theme = isDark() ? 'light' : 'dark';
    }
    apply();
  });

  apply();
  render(false);
  root.setAttribute('data-play', '1'); // 程式啟動了：靜態的清單藏起來（樣式照這個標記），換成遊戲畫面
  root.setAttribute('data-music', 'off');
  stage.hidden = false;
  tools.hidden = false;
})();
