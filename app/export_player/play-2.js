(function () {
  // Life World 離線播放器 play-2（互動版）。內容已經完整寫在頁面裡；這段程式把它變成有東西可猜、選擇會改變結局的版本：
  // 1. 入局：開始之前先選一個人的視角（或旁觀）。他的每一段真心話直接看得到；別人的要「偷看」，次數有限，用完就沒有了。
  // 2. 逐段模式（預設）：先藏起還沒讀到的段落，按「下一段」、空白鍵或 → 一次揭開一段，← 收回。
  //    章名、幕名跟著那一章（幕）的第一段出現；「全部顯示」可以切到整篇閱讀，再按回到逐段。
  // 3. 線索：原文裡有些詞可以點。點到會顯示提示並記入計數；同一個人的線索都找到，就直接看穿他的底牌。
  // 4. 關鍵抉擇：揭開到指定那一幕的最後一段，「下一段」停住，出現抉擇。選真結局才繼續揭開原本的後續；
  //    選另外兩個會在原地顯示那個結局的旁白，可以回到轉折點重選。真結局可能要先找到線索才能選。看過哪些結局記在這個瀏覽器。
  // 5. 結尾卡（走完真結局才出現）：下集預告、底牌（看穿的直接顯示，其餘按「看底牌」）、你站哪一邊（選了顯示那一邊的番外與提問）、從頭再看。
  // 6. 人物篩選：點開頭的人物名字，其他人的段落變淡（不隱藏，上下文還在）。
  // 所有文字（選項、結局、提示、底牌、番外）都已經在頁面裡，這裡只決定什麼時候顯示、把靜態的清單換成按鈕；不從別處取得內容。
  // 這段程式沒有執行時（預覽工具、被停用），頁面就是整篇可讀的文章：抉擇是一個靜態區塊，底牌、番外、另外兩個結局仍然收合。
  // 所以「藏起來」都由這裡動手，不寫死在頁面裡。沒有任何連線；偏好與看過的結局存在這個瀏覽器，存不了（例如直接點開的檔案被限制）也照常使用。
  var root = document.documentElement;
  var tools = document.querySelector('.lw-tools');
  if (!tools) return;

  function list(selector, scope) { return Array.prototype.slice.call((scope || document).querySelectorAll(selector)); }
  function hit(event, selector) { return event.target && event.target.closest ? event.target.closest(selector) : null; }
  function read(key) { try { return window.localStorage.getItem(key); } catch (error) { return null; } }
  function write(key, value) { try { window.localStorage.setItem(key, value); } catch (error) { /* 存不了不影響閱讀 */ } }
  function readObject(key) {
    try {
      var value = JSON.parse(read(key) || 'null');
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
    } catch (error) { return {}; }
  }
  // 程式新增的元素一律用 textContent 放文字：頁面裡的內容不會被當成標籤再解析一次
  function make(tag, name, text) {
    var element = document.createElement(tag);
    if (name) element.className = name;
    if (text) element.textContent = text;
    if (tag === 'button') element.type = 'button';
    return element;
  }
  function empty(element) { while (element.firstChild) element.removeChild(element.firstChild); }
  function digits(value) { return /^\d+$/.test(value || '') ? value : ''; }
  function press(event) { return event.key === 'Enter' || event.key === ' ' || event.key === 'Spacebar'; }

  // ---- 閱讀偏好 ----
  // 字級、深淺色、場景提示和閱讀版共用同一個鍵：同一個瀏覽器裡兩種檔案的設定一致。
  var KEY = 'lw-reader-prefs';
  var SIZES = ['s', 'm', 'l', 'xl'];
  var prefs = {theme: '', size: 'm', stage: 'on'};
  var saved = readObject(KEY);
  Object.keys(prefs).forEach(function (key) { if (typeof saved[key] === 'string') prefs[key] = saved[key]; });

  function isDark() {
    var theme = root.getAttribute('data-theme');
    if (theme) return theme === 'dark';
    return Boolean(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
  }

  function apply() {
    if (prefs.theme === 'dark' || prefs.theme === 'light') root.setAttribute('data-theme', prefs.theme);
    else root.removeAttribute('data-theme');
    root.setAttribute('data-size', SIZES.indexOf(prefs.size) < 0 ? 'm' : prefs.size);
    root.setAttribute('data-stage', prefs.stage === 'off' ? 'off' : 'on');
    var stage = tools.querySelector('[data-tool=stage]');
    if (stage) stage.setAttribute('aria-pressed', prefs.stage === 'off' ? 'false' : 'true');
    var theme = tools.querySelector('[data-tool=theme]');
    if (theme) theme.textContent = isDark() ? '淺色' : '深色';
    write(KEY, JSON.stringify(prefs));
  }

  // ---- 頁面上的東西 ----
  var main = document.querySelector('main');
  var segs = list('main .lw-seg');
  var total = segs.length;
  var nav = document.querySelector('.lw-nav');
  var end = document.querySelector('.lw-end');
  var secrets = document.querySelector('.lw-secrets');
  var entry = document.querySelector('.lw-entry'); // 選視角；沒有任何人物狀態的舊作品沒有這一塊，改用「開始」
  var endKind = document.querySelector('.lw-end-kind');
  var endSeen = document.querySelector('.lw-end-seen');
  var modeButton = tools.querySelector('[data-tool=mode]');
  var startButton = nav && nav.querySelector('[data-play=start]');
  var prevButton = nav && nav.querySelector('[data-play=prev]');
  var nextButton = nav && nav.querySelector('[data-play=next]');
  var progress = nav && nav.querySelector('.lw-progress');
  var status = nav && nav.querySelector('.lw-status');
  // 沒有段落（或頁面不完整）就不進入逐段模式：整篇照常顯示
  var stepping = Boolean(total && prevButton && nextButton && progress && (entry || startButton));
  var mode = stepping ? 'step' : 'all';
  var shown = 0; // 已經揭開幾段

  // 每一章、每一幕從第幾段開始（依頁面順序，章排在它的幕前面）。章名、幕名跟著自己的第一段出現；
  // 沒有段落的章跟著它後面的第一段出現（後面沒有段落就跟著最後一段）。
  var heads = list('main .lw-chapter, main .lw-beat').map(function (element) {
    var first = segs.indexOf(element.querySelector('.lw-seg'));
    if (first < 0) {
      first = total - 1;
      for (var index = 0; index < total; index += 1) {
        if (element.compareDocumentPosition(segs[index]) & 4) { first = index; break; } // 4＝這一段排在它後面
      }
    }
    return {element: element, first: first};
  });

  function wait(element, on) { if (element) element.classList.toggle('lw-wait', on); }

  // ---- 視角與偷看 ----
  // view：null＝還沒選、0＝旁觀、n＝第 n 位人物（和段落上的 data-p 同一套號碼）。
  // 自己視角的真心話直接打開；別人的每一段前面加一顆「偷看」，按一次少一次。次數寫在頁面裡（兩位人物 2 次、三位以上 3 次）。
  var view = null;
  var viewButtons = entry ? list('button[data-view]', entry) : [];
  var peeksTotal = entry ? Number(entry.getAttribute('data-peeks')) || 0 : 0;
  var peeksLeft = peeksTotal;
  var xrays = [];
  segs.forEach(function (seg) {
    var box = seg.querySelector('.lw-xray');
    if (!box) return;
    var button = make('button', 'lw-peek');
    button.setAttribute('data-play', 'peek');
    seg.insertBefore(button, box);
    xrays.push({seg: seg, button: button, peeked: false});
  });

  function drawXray() {
    xrays.forEach(function (item) {
      var open = item.peeked || (view > 0 && item.seg.getAttribute('data-p') === String(view));
      item.seg.classList.toggle('lw-open', open);
      item.button.hidden = open;
      item.button.textContent = peeksLeft > 0 ? '偷看他此刻在想什麼（剩 ' + peeksLeft + ' 次）' : '偷看的次數用完了';
      // 用完只標成不能按（不用 disabled）：和「下一段」一樣，焦點留在上面時鍵盤照常可以翻頁
      item.button.setAttribute('aria-disabled', peeksLeft > 0 ? 'false' : 'true');
    });
  }

  // ---- 線索 ----
  // 線索詞在頁面裡是一般文字（.lw-clue）；有這段程式才變成可以點的。它的提示寫在同一段裡（.lw-clue-note，先藏著），
  // data-who 是這則線索指向第幾位人物的底牌。沒有對應提示的詞不算線索。
  var clues = [];
  var seen = []; // 已經看穿的底牌：{item: 結尾卡裡那一則底牌, card: 段落裡「你看穿了…」的那張卡}
  list('main .lw-clue').forEach(function (span) {
    var seg = span.closest('.lw-seg');
    var id = span.getAttribute('data-clue');
    var note = null;
    list('.lw-clue-note', seg || span).forEach(function (item) { if (!note && item.getAttribute('data-clue') === id) note = item; });
    if (!seg || !note) return;
    var clue = {span: span, seg: seg, chapter: span.closest('.lw-chapter'), note: note, who: note.getAttribute('data-who'), found: false};
    span.setAttribute('role', 'button');
    span.setAttribute('tabindex', '0');
    span.setAttribute('aria-pressed', 'false');
    span.addEventListener('keydown', function (event) {
      if (!press(event)) return;
      event.preventDefault(); // 焦點在線索詞上：空白鍵是「點它」，不是下一段
      findClue(clue);
    });
    clues.push(clue);
  });

  function clueFound(chapter) { return clues.some(function (clue) { return clue.found && clue.chapter === chapter; }); }

  // 這則線索指向的那一張底牌（結尾卡裡收合的清單，依章分開）。章號與人物號碼只接受數字，才拿去組選擇器。
  function secretOf(clue) {
    var chapter = digits(clue.chapter ? clue.chapter.id.replace('ch-', '') : '');
    var who = digits(clue.who);
    if (!secrets || !chapter || !who) return null;
    return secrets.querySelector('.lw-secret-list[data-ch="' + chapter + '"] .lw-secret[data-p="' + who + '"]');
  }

  function findClue(clue) {
    if (clue.found) return;
    clue.found = true;
    clue.span.classList.add('lw-found');
    clue.span.setAttribute('aria-pressed', 'true');
    clue.note.hidden = false;
    // 同一章裡指向同一個人的線索都找到了：看穿他的底牌，直接顯示在剛點的這一段下面
    var all = clues.every(function (other) { return other.found || other.chapter !== clue.chapter || other.who !== clue.who; });
    var item = all ? secretOf(clue) : null;
    if (item) {
      var name = item.querySelector('.lw-name');
      var text = item.querySelector('.lw-secret-text');
      var card = make('aside', 'lw-seen');
      if (item.getAttribute('data-c')) card.setAttribute('data-c', item.getAttribute('data-c'));
      card.appendChild(make('p', 'lw-seen-title', '你看穿了 ' + (name ? name.textContent : '') + ' 的底牌'));
      card.appendChild(make('p', 'lw-seen-text', text ? text.textContent : ''));
      clue.note.parentNode.insertBefore(card, clue.note.nextSibling);
      seen.push({item: item, card: card});
    }
    draw();
  }

  // 結尾卡的底牌：已經看穿的直接列在「看底牌」上面（從收合的清單複製出來，原本那一則先藏起來，不重複出現），其餘照舊要按了才看得到。
  var known = null;
  var knownList = null;
  var knownCount = -1;
  if (secrets) {
    known = make('div', 'lw-known');
    known.hidden = true;
    known.appendChild(make('p', 'lw-known-title', '你已經看穿的底牌'));
    knownList = make('ul', 'lw-secret-list');
    known.appendChild(knownList);
    secrets.parentNode.insertBefore(known, secrets);
  }

  function drawKnown() {
    if (!secrets || knownCount === seen.length) return; // 沒有變就不重畫
    knownCount = seen.length;
    empty(knownList);
    var items = list('.lw-secret', secrets);
    items.forEach(function (item) { item.hidden = false; });
    seen.forEach(function (one) {
      var copy = one.item.cloneNode(true);
      var head = one.item.parentNode.previousElementSibling; // 多章節：標明是哪一章的底牌
      if (head && head.classList.contains('lw-secrets-chapter')) copy.insertBefore(make('span', 'lw-known-chapter', head.textContent), copy.firstChild);
      knownList.appendChild(copy);
      one.item.hidden = true;
    });
    known.hidden = !seen.length;
    // 某一章的底牌都看穿了，那一章的小標題一起收掉；全部都看穿了，「看底牌」整個不用了
    list('.lw-secret-list', secrets).forEach(function (group) {
      var left = list('.lw-secret', group).some(function (item) { return !item.hidden; });
      var head = group.previousElementSibling;
      group.hidden = !left;
      if (head && head.classList.contains('lw-secrets-chapter')) head.hidden = !left;
    });
    secrets.hidden = !items.some(function (item) { return !item.hidden; });
  }

  // ---- 關鍵抉擇 ----
  // 頁面裡的抉擇是靜態的：題目、選項清單（li 帶著代號、種類、要不要先找到線索）、另外兩個結局收在 details。
  // 這裡替每個抉擇做一組可以按的（.lw-choice-play）：選項按鈕、少線索時的說明、選了另外兩個時的結局卡、回到轉折點重選、已看過幾個結局。
  // 逐段模式顯示可以按的那一組、藏起靜態的；「全部顯示」相反（和沒有程式時一樣）。
  // after：抉擇出現時已經揭開幾段（它前面那一幕的最後一段）；chapterEnd：它所在那一章的最後一段——走到那裡才算看過那一章的真結局。
  // 多章節時每一章可以各有一個抉擇，依頁面順序一個一個來。
  var ENDINGS_KEY = 'lw-play-endings:' + document.title; // 看過的結局記在這個瀏覽器；鍵帶著作品標題，不同作品不會互相覆蓋
  var endingsSeen = readObject(ENDINGS_KEY);
  var choices = list('main .lw-choice').map(function (element) {
    var chapter = element.closest('.lw-chapter');
    var choice = {element: element, chapter: chapter, after: 0, chapterEnd: total, picked: null, shownEnding: null, options: [],
                  statics: list('.lw-choice-list, .lw-choice-static, .lw-endings', element)};
    segs.forEach(function (seg, index) {
      if (seg.compareDocumentPosition(element) & 4) choice.after = index + 1; // 4＝抉擇排在這一段後面
      if (chapter && chapter.contains(seg)) choice.chapterEnd = index + 1;
    });
    var buttons = make('div', 'lw-choice-options');
    list('.lw-choice-list li', element).forEach(function (item) {
      var id = item.getAttribute('data-option');
      var option = {id: id, kind: item.getAttribute('data-kind'), needsClue: item.hasAttribute('data-needs-clue'), ending: null,
                    key: (chapter ? chapter.id : '') + ':' + id, button: make('button', 'lw-option', item.textContent)};
      list('.lw-ending', element).forEach(function (one) { if (one.getAttribute('data-option') === id) option.ending = one; });
      option.button.addEventListener('click', function () { choose(choice, option); });
      buttons.appendChild(option.button);
      choice.options.push(option);
    });
    choice.lock = make('p', 'lw-choice-lock', '還少一條線索——回頭找找');
    choice.card = make('div', 'lw-ending-card');
    choice.back = make('div', 'lw-choice-back');
    var again = make('button', '', '回到轉折點重選');
    again.setAttribute('data-play', 'rechoose');
    choice.back.appendChild(again);
    choice.count = make('p', 'lw-endings-seen');
    choice.play = make('div', 'lw-choice-play');
    [buttons, choice.lock, choice.card, choice.back, choice.count].forEach(function (part) { choice.play.appendChild(part); });
    element.appendChild(choice.play);
    element.setAttribute('tabindex', '-1'); // 可以用程式把焦點放上來（見 arrive），本身不在 Tab 的順序裡
    return choice;
  });

  // 走到轉折點時把焦點放在抉擇卡上：鍵盤再按 Tab 就是第一個選項。不直接放在選項上——連按空白鍵翻頁的讀者會不小心按下去。
  function arrive(choice) {
    if (choice && choice.element.focus) choice.element.focus({preventScroll: true});
  }

  // 擋在目前進度上的抉擇（還沒選真結局的第一個，而且剛好揭開到它前面）；沒有就是 null
  function waitingChoice() {
    for (var index = 0; index < choices.length; index += 1) {
      if (!isTrue(choices[index])) return choices[index].after === shown ? choices[index] : null;
    }
    return null;
  }

  function isTrue(choice) { return Boolean(choice.picked) && choice.picked.kind === 'true'; }
  function resolved() { return choices.every(isTrue); }

  // 逐段模式最多能揭開到第幾段：第一個還沒選真結局的抉擇擋在那裡（還沒選，或選了另外兩個結局）
  function limit() {
    for (var index = 0; index < choices.length; index += 1) {
      if (!isTrue(choices[index])) return choices[index].after;
    }
    return total;
  }

  function waitingView() { return Boolean(entry) && view === null; } // 有視角可選卻還沒選：不能開始
  function canAdvance() { return mode === 'step' && !waitingView() && shown < limit(); }

  function seenText() {
    var all = 0;
    var have = 0;
    choices.forEach(function (choice) {
      choice.options.forEach(function (option) {
        all += 1;
        if (endingsSeen[option.key]) have += 1; // 只數這份檔案裡真的有的結局
      });
    });
    return '已看過 ' + have + '／' + all + ' 個結局';
  }

  function markSeen(option) {
    if (endingsSeen[option.key]) return;
    endingsSeen[option.key] = 1;
    write(ENDINGS_KEY, JSON.stringify(endingsSeen));
  }

  function drawChoice(choice, everything, counted) {
    wait(choice.element, !everything && shown < choice.after);
    choice.statics.forEach(function (part) { wait(part, !everything); });
    choice.play.hidden = everything;
    var here = !everything && shown === choice.after; // 讀者正站在轉折點上：可以選，也可以改選
    var open = clueFound(choice.chapter);
    var locked = false;
    choice.options.forEach(function (option) {
      var blocked = option.needsClue && !open; // 要先找到線索的選項：這一章一條線索都還沒找到就不能選
      locked = locked || blocked;
      option.button.setAttribute('aria-pressed', choice.picked === option ? 'true' : 'false');
      option.button.setAttribute('aria-disabled', here && !blocked ? 'false' : 'true');
      option.button.classList.toggle('lw-locked', blocked);
    });
    choice.lock.hidden = !locked;
    var ending = choice.picked && !isTrue(choice) ? choice.picked.ending : null;
    if (choice.shownEnding !== ending) { // 結局卡：把收合區塊裡那個結局複製出來；換了選擇才重做
      empty(choice.card);
      if (ending) choice.card.appendChild(ending.cloneNode(true));
      choice.shownEnding = ending;
    }
    choice.card.hidden = !ending;
    choice.back.hidden = !choice.picked || isTrue(choice);
    choice.count.textContent = counted;
  }

  function viewName() {
    var name = '';
    viewButtons.forEach(function (button) { if (button.getAttribute('data-view') === String(view)) name = button.textContent; });
    return name;
  }

  function drawStatus(done) {
    if (!status) return;
    var parts = [];
    if (entry && view !== null) parts.push('視角：' + viewName());
    if (xrays.length) parts.push('偷看剩 ' + peeksLeft + ' 次');
    if (clues.length) parts.push('線索 ' + clues.filter(function (clue) { return clue.found; }).length + '／' + clues.length);
    var stuck = done ? null : waitingChoice();
    if (stuck) parts.push(stuck.picked ? '這條路到這裡結束' : '等你做決定'); // 停在轉折點：說明為什麼「下一段」按不動
    status.textContent = parts.join('・');
    status.hidden = !parts.length;
  }

  function draw() {
    var everything = mode === 'all';
    var done = everything || (shown >= total && resolved()); // 讀完＝全部揭開，而且每個抉擇都走了真結局
    if (main && everything) main.removeAttribute('aria-live'); // 整篇一次出現時不要全部念一遍
    segs.forEach(function (seg, index) { wait(seg, !everything && index >= shown); });
    heads.forEach(function (head) { wait(head.element, !everything && head.first >= shown); });
    // 真結局要真的走完那一章才算看過（另外兩個結局在選的當下就算）；「全部顯示」不算
    if (!everything) choices.forEach(function (choice) { if (isTrue(choice) && shown >= choice.chapterEnd) markSeen(choice.picked); });
    var counted = seenText();
    choices.forEach(function (choice) { drawChoice(choice, everything, counted); });
    wait(end, !done); // 結尾卡：讀完才出現
    if (!done && secrets) secrets.open = false; // 結尾卡收起來時底牌也收合：再讀到最後要重新按才看得到
    if (endKind) endKind.hidden = everything; // 「真結局」只對一路選過來的讀者說
    if (endSeen) {
      endSeen.hidden = everything;
      endSeen.querySelector('.lw-endings-seen').textContent = counted;
    }
    drawXray();
    drawKnown();
    root.setAttribute('data-mode', mode);
    if (modeButton) modeButton.textContent = everything ? '逐段閱讀' : '全部顯示'; // 按鈕寫的是按下去會變成什麼
    if (!stepping) return;
    nav.hidden = everything;
    if (entry) entry.hidden = everything || shown > 0; // 選視角只在還沒開始的時候
    viewButtons.forEach(function (button) {
      button.setAttribute('aria-pressed', view !== null && button.getAttribute('data-view') === String(view) ? 'true' : 'false');
    });
    if (startButton) startButton.hidden = shown > 0;
    prevButton.hidden = nextButton.hidden = shown === 0;
    // 走不下去時「下一段」只標成不能按，不用 disabled：焦點留在被停用的按鈕上時，瀏覽器不會送出鍵盤事件，← 會失效
    nextButton.setAttribute('aria-disabled', canAdvance() ? 'false' : 'true');
    progress.textContent = shown === 0 ? '共 ' + total + ' 段' : '第 ' + shown + '／' + total + ' 段';
    drawStatus(done);
    if (main && !everything) main.setAttribute('aria-live', 'polite'); // 新揭開的段落讓螢幕報讀器念出來
  }

  function bring(element, top) {
    if (!element || !element.scrollIntoView) return;
    // 一般的段落放在畫面中間；新的一章（幕）或比畫面高的段落從開頭對齊，標題與第一行不會被切掉
    var tall = element.getBoundingClientRect().height > window.innerHeight * 0.6;
    element.scrollIntoView({block: top || tall ? 'start' : 'center'});
  }

  function advance() {
    if (!canAdvance()) return false;
    var index = shown;
    shown += 1;
    draw();
    var target = segs[index];
    for (var number = 0; number < heads.length; number += 1) {
      if (heads[number].first === index) { target = heads[number].element; break; } // 這一段是某一章（幕）的第一段：章名、幕名一起進到畫面
    }
    list('.lw-new').forEach(function (item) { item.classList.remove('lw-new'); });
    target.classList.add('lw-new');
    // 走到停下來的地方（抉擇，或最後的結尾卡）也從開頭對齊：接在這一段下面的那張卡一起進到畫面
    bring(target, target !== segs[index] || shown >= limit());
    arrive(waitingChoice());
    return true;
  }

  function focusStart() {
    var first = entry ? viewButtons[0] : startButton;
    if (first) first.focus({preventScroll: true});
  }

  function back() {
    if (mode !== 'step' || shown <= 0) return false;
    var inNav = nav.contains(document.activeElement);
    shown -= 1;
    // 退到抉擇之前：那個選擇不算了，再走到轉折點要重新選
    choices.forEach(function (choice) { if (choice.after > shown) choice.picked = null; });
    draw();
    if (shown > 0) {
      bring(segs[shown - 1]);
    } else {
      window.scrollTo(0, 0);
      if (inNav) focusStart(); // 「上一段」收起來了，焦點交給開始的地方
    }
    return true;
  }

  // 從頭再看：回到選視角之前，偷看的次數與找到的線索都重來；看過哪些結局留著。
  function restart() {
    if (!stepping) return;
    shown = 0;
    mode = 'step';
    view = null;
    peeksLeft = peeksTotal;
    xrays.forEach(function (item) { item.peeked = false; });
    clues.forEach(function (clue) {
      clue.found = false;
      clue.span.classList.remove('lw-found');
      clue.span.setAttribute('aria-pressed', 'false');
      clue.note.hidden = true;
    });
    seen.forEach(function (one) { if (one.card.parentNode) one.card.parentNode.removeChild(one.card); });
    seen = [];
    choices.forEach(function (choice) { choice.picked = null; });
    draw();
    window.scrollTo(0, 0);
    focusStart();
  }

  // 選視角：選了就開始（揭開第一段）。還沒往下讀之前可以改選。
  function enter(next) {
    view = next;
    if (shown === 0 && advance()) nextButton.focus({preventScroll: true}); // 選視角的區塊收起來了，焦點交給「下一段」：鍵盤可以接著按
    else draw();
  }

  function choose(choice, option) {
    // 只有站在轉折點上才能選；要先找到線索的選項，還沒找到時按了沒有作用（下面那行字說明原因）
    if (mode !== 'step' || shown !== choice.after) return;
    if (option.needsClue && !clueFound(choice.chapter)) return;
    choice.picked = option;
    choices.forEach(function (other) { if (other.after > choice.after) other.picked = null; });
    if (option.kind === 'true') {
      draw();
      if (!advance()) bring(end, true); // 真結局沒有後續段落：接下來就是結尾卡
      nextButton.focus({preventScroll: true}); // 焦點交給「下一段」：空白鍵可以接著往下，不會又按到選項
    } else {
      markSeen(option);
      draw();
      bring(choice.card);
    }
  }

  // 回到轉折點重選。抉擇卡上的那一顆回到它自己；結尾卡上的那一顆回到最後一個抉擇。偷看的次數與線索不重來。
  function rechoose(button) {
    var element = button.closest('.lw-choice');
    var target = null;
    choices.forEach(function (choice) { if (!element || choice.element === element) target = choice; });
    if (!target || !stepping) return;
    mode = 'step';
    shown = target.after;
    choices.forEach(function (choice) { if (choice.after >= target.after) choice.picked = null; });
    draw();
    bring(target.element, true);
    arrive(target); // 剛才按的那一顆收起來了，焦點交給抉擇卡
  }

  document.addEventListener('click', function (event) {
    var word = hit(event, '.lw-clue[role=button]');
    if (word) {
      clues.forEach(function (clue) { if (clue.span === word) findClue(clue); });
      return;
    }
    var person = hit(event, 'button[data-view]');
    if (person) {
      enter(Number(person.getAttribute('data-view')) || 0);
      return;
    }
    var button = hit(event, 'button[data-play]');
    if (!button) return;
    var what = button.getAttribute('data-play');
    if (what === 'start') {
      if (advance()) nextButton.focus({preventScroll: true}); // 「開始」收起來了，焦點交給「下一段」：鍵盤可以接著按
    } else if (what === 'next') {
      advance();
    } else if (what === 'prev') {
      back();
    } else if (what === 'restart') {
      restart();
    } else if (what === 'rechoose') {
      rechoose(button);
    } else if (what === 'peek') {
      xrays.forEach(function (item) {
        if (item.button !== button || item.peeked || peeksLeft <= 0) return; // 次數用完就不能再看
        item.peeked = true;
        peeksLeft -= 1;
      });
      draw();
    }
  });

  document.addEventListener('keydown', function (event) {
    // 只在逐段模式接手：整篇閱讀時空白鍵照常捲動頁面
    if (mode !== 'step' || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return;
    var space = event.key === ' ' || event.key === 'Spacebar';
    if (!space && event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return;
    // 焦點在按鈕、連結、收合區塊上時，空白鍵是「按下它」：交給瀏覽器，不要同時又翻一段
    if (space && hit(event, 'button,a,summary,input,select,textarea,[role=button]')) return;
    var left = event.key === 'ArrowLeft';
    // 沒有得翻了（還沒選視角、停在抉擇、已經讀完）：交還給瀏覽器，空白鍵照常捲動頁面
    if (left ? shown <= 0 : !canAdvance()) return;
    event.preventDefault();
    if (event.repeat) return; // 按住不放不連翻，免得一口氣把後面都揭開
    if (left) back(); else advance();
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
    } else if (tool === 'stage') {
      prefs.stage = prefs.stage === 'off' ? 'on' : 'off';
    } else if (tool === 'mode' && stepping) {
      mode = mode === 'all' ? 'step' : 'all'; // 進度與做過的選擇都留著：切回逐段時回到剛才讀到的地方
      draw();
      if (mode === 'step' && shown > 0) bring(segs[shown - 1]);
    }
    apply();
  });

  // ---- 人物篩選 ----
  // 名字在頁面裡是一般文字；有這段程式才變成可以按的按鈕（滑鼠、Enter、空白鍵）。再按一次同一個名字取消。
  var names = list('.lw-meta .lw-name[data-p]');
  var chosen = '';

  function focusOn(who) {
    chosen = chosen === who ? '' : who;
    names.forEach(function (name) { name.setAttribute('aria-pressed', name.getAttribute('data-p') === chosen ? 'true' : 'false'); });
    segs.forEach(function (seg) { seg.classList.toggle('lw-dim', Boolean(chosen) && seg.getAttribute('data-p') !== chosen); });
  }

  names.forEach(function (name) {
    name.setAttribute('role', 'button');
    name.setAttribute('tabindex', '0');
    name.setAttribute('aria-pressed', 'false');
    name.addEventListener('click', function () { focusOn(name.getAttribute('data-p')); });
    name.addEventListener('keydown', function (event) {
      if (!press(event)) return;
      event.preventDefault();
      focusOn(name.getAttribute('data-p'));
    });
  });

  // ---- 你站哪一邊 ----
  // 選了之後顯示那一邊的番外（從收合的番外區塊複製出來）與給讀者的那句提問。選擇記在這個瀏覽器；鍵帶著作品標題，不同作品不會互相覆蓋。
  // 沒有這一塊的作品（不到兩個陣營）：番外維持收合的區塊、提問直接在文章最後，和沒有程式時一樣。
  var pick = document.querySelector('.lw-pick');
  if (pick) {
    var PICK_KEY = 'lw-play-pick:' + document.title;
    var epilogues = document.querySelector('.lw-epilogues');
    var ask = document.querySelector('.lw-ask');
    var options = list('button[data-side]', pick);
    var result = pick.querySelector('.lw-pick-result');
    var more = make('div', 'lw-pick-more');
    more.hidden = true;
    pick.appendChild(more);
    var side = function (name) {
      var picked = null;
      options.forEach(function (option) {
        var on = option.textContent === name;
        if (on) picked = option;
        option.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      if (result) {
        result.textContent = picked ? '你選了：' + name : '';
        result.hidden = !picked;
      }
      empty(more);
      if (picked && epilogues) {
        list('.lw-epilogue', epilogues).forEach(function (item) {
          if (item.getAttribute('data-side') !== picked.getAttribute('data-side')) return;
          if (!more.firstChild) more.appendChild(make('p', 'lw-pick-more-title', '番外'));
          more.appendChild(item.cloneNode(true));
        });
      }
      more.hidden = !more.firstChild;
      if (ask) ask.hidden = !picked;
    };
    side(read(PICK_KEY) || ''); // 上次選的陣營還在才顯示
    pick.addEventListener('click', function (event) {
      var option = hit(event, 'button[data-side]');
      if (!option) return;
      side(option.textContent);
      write(PICK_KEY, option.textContent);
    });
    if (epilogues) epilogues.hidden = true; // 番外改由選邊帶出來
    pick.hidden = false;
  }

  // ---- 目錄（多章節） ----
  // 逐段模式下還沒揭開的章是藏起來的，連結跳不過去：先把到那一章第一段為止的內容揭開，瀏覽器再照常捲到那一章。
  // 中間有還沒走真結局的抉擇就不能跳過去：揭開到那個轉折點、停在那裡。還沒選視角就跳章，當成旁觀。
  var toc = document.querySelector('.lw-toc');
  if (toc) {
    toc.addEventListener('click', function (event) {
      var link = hit(event, 'a[href^="#"]');
      if (!link || mode !== 'step') return;
      var chapter = document.getElementById(link.getAttribute('href').slice(1));
      heads.forEach(function (head) {
        if (head.element !== chapter || head.first < shown) return;
        if (waitingView()) view = 0;
        var stop = limit();
        if (stop <= head.first) {
          event.preventDefault();
          shown = stop;
          draw();
          var blocked = waitingChoice();
          if (blocked) {
            bring(blocked.element, true);
            arrive(blocked);
          }
        } else {
          shown = head.first + 1;
          draw();
        }
      });
    });
  }

  apply();
  draw();
  tools.hidden = false;
  if (modeButton && !stepping) modeButton.hidden = true;
  list('.lw-again, .lw-hint').forEach(function (element) { element.hidden = !stepping; });
})();
