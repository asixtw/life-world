# 互動遊戲（玩的遊戲）說明與檢驗清單

2026-11-12。給 Codex 做上 GitHub 前的專案檢驗用。前半是這個功能的說明，後半是請你檢驗的項目。

## 0. 先讀：環境與限制

- 專案：`C:\LifeWorld_project\codex-public-core-compare-20261109`，分支 `jerry_unified_person`。本機與遠端都在 `39ad50a`；**這份說明涵蓋的內容全部是尚未提交的本機修改**（20 個修改檔、39 個新檔；新檔含這份說明，其中一份不要提交，見第 12 節）。
- Python：`C:\LifeWorld_project\life-world-react-integrated\.venv\Scripts\python.exe`。執行時加 `PYTHONUTF8=1 PYTHONDONTWRITEBYTECODE=1`；不要用 `PYTHONIOENCODING`（會讓既有測試假紅燈）。
- 整套測試：`python -m pytest -q -p no:cacheprovider --ignore=tests/product/test_google_verifier.py --ignore=tests/product/test_staging_iap_config.py --tb=line --show-capture=no`
- **不要做的事**：
  - 不要 commit、push、merge，也不要開 PR（等 Jerry 看過檢驗結果再決定）。
  - 不要寫入或遷移 `life_world_dev`；不要改資料表（這一版沒有 migration）。
  - **不要呼叫真實模型**：在 8030 上建立互動遊戲、`POST /api/games`、`POST /api/games/{id}/advance`、以及任何帶 `LW_E2E_LIVE_GENERATION=1` 的測試都會呼叫 Gemini 並計費，需要 Jerry 先同意。
  - 雲端測試只用自動註冊的 `persons_ui_` 合成帳號；不要寫入使用者的 E2E 帳號。
  - 不要部署。e2e 目前的版本是 `lw-api-main-b8030-11121515`（第 16 節的修正之後）（0% 流量的 e2e 標籤），已經包含這份說明的全部內容。
- 檢驗報告建議放在工作樹外，例如 `C:\LifeWorld_project\codex-review-turn-game-20261112\`，附上實際執行的命令與結果（JUnit XML 或輸出）。

## 1. 這是什麼

使用者（Jerry）定案的方向，原話摘錄：

- 「這個作品功能最重要仍是 AI 角色扮演。互動式＋視差視覺效果是為了提高趣味性的加分項。」
- 「在使用者的回合進行選項，使用者選擇之後，其他角色依照個性反應，才是醍醐味。」
- 非使用者的角色有一個數值（心情、好感等，擇一顯示），「每一個選項都會影響不同角色反應的數值，就是遊戲性，並且因此影響多結局」。
- 結局「像是遊戲結局一樣，跳出字幕或者音樂伴奏或是煙花效果（悲劇結局則是另一種效果）」。
- 題材不限：旅遊、登山、商城購物、食材採購、劇情多結局……
- 版面：「左邊會有過往每一站的選擇（主要目的是錨點），右邊則是詳細內容，以及接下來的選擇」。
- 「理論上都是 HTML，為什麼要多入口」→ 只有一個建立入口，建立時選玩法。

第 1 期只做一種題材：**一日行程**。從起點（車站）出發，8～12 小時內要回來；每一步選下一站，車程、停留與營業時間由程式計算；同行的 1～3 位角色到每一站各自有反應，數值升降；回到起點時依數值決定結局。

## 2. 使用者流程

1. 作品頁 →「＋ 建立新作品」→ 建立頁第一步選玩法「玩的遊戲」（`#create?mode=game`；舊網址 `#game-new` 會轉過來）。
2. 填：同行的人物 1～3 位（必須有正式人物設定）、你的稱呼（選填）、行程說明（可貼候選地點與營業時間；沒寫就用虛構的地方）、題材（目前只有行程）、起點、可用時數（8／10／12）、出發時間、標題（選填）。
3. 開始生成 → `POST /api/games`（規劃，1 次模型呼叫）→ 前往 `#game/{id}`。
4. 遊戲頁反覆呼叫 `POST /api/games/{id}/advance`，每次生成一位同行者的反應（每位 1 次模型呼叫），直到 `build.status='ready'`。連續失敗時自動重試 5 次（等 5、10、20、40、60 秒），之後只留「再試一次」；401／403／404 不重試。
5. ready 後：「在這裡玩」（站內框架）或「下載互動遊戲」（單一離線 HTML，可傳給沒有帳號的人）。
6. 玩：左欄走過的路（點任一步回到當時，時間與數值都回去）；右欄這一站的內容、每位同行者的反應與數值升降；下面是接下來的選項卡（只顯示車程、到達、停留、打烊，**不顯示**對誰有影響）。隨時可以「回起點，結束行程」。
7. 結局：結局標題與文字、每人最後的數值與最後一句話、這時才揭曉的願望、片尾字幕（行程表）、特效（perfect 煙火、great 紙花、ok 無、poor 下雨與褪色）、Web Audio 合成的音樂（預設不播）、「已看過 n／N 種結局」、「再走一次」。

## 3. 架構與檔案

| 層 | 檔案 | 說明 |
|---|---|---|
| 後端 | `app/turn_game.py`（新，1009 行） | 兩個生成模組、輸出整理、通用規則、行程規則、`TurnGameMixin`、三條 `/api/games` 路由 |
| 後端接線 | `app/service.py`、`app/generation_routes.py`、`app/works_center.py`、`app/ai_providers.py`（`FakeProvider` 的假輸出） | |
| 匯出 | `app/work_export.py`（`route_data`、`render_route_html`、`view_csp`、`/view` 路由） | 播放器 `route-1`，資料 `lw-route.v1` |
| 播放器 | `app/export_player/route-1.js`（993 行）、`route-1.css` | 單一檔案、離線、CSP 以雜湊放行內嵌程式 |
| 安全標頭 | `app/main.py` | 只有 `/view` 成功的回應可被同源框住 |
| 前端 | `app/static/creation.js`（玩法選擇與遊戲的建立）、`app/static/game.js`（`#game/{id}`）、`app/static/works.js`、`app/static/app.js`、`app/static/generation.js`（「在這裡看」）、`app/static/characters.css` | |
| 建置清單 | `deploy/core-e2e-build-sources.txt` | 新檔都已列入 |

程式分兩層，之後加題材只換題材層：

- **通用**（`turn_game.py`）：`tone_of`、`bump`、`play`、`classify`、`ending_of`、`nearest_rank`、`ending_thresholds`、`outcomes`、`endings_summary`、`new_game`、`with_reaction`、`build_view`、`tidy_plan`、`tidy_reaction`。
- **行程題材**（`trip_` 開頭）：`trip_timing`、`trip_leg`、`trip_replay`、`trip_options`、`trip_rules`、`trip_routes`、`trip_playable`、`trip_fit`、`trip_spread`、`trip_settle` 等；`SKINS['trip']` 把它們接到通用層。
- 播放器同樣分成通用層與 `SKINS.trip = tripSkin(data)`；唯一的狀態是 `picks`（走過的站），每次重畫都從頭重放。

沒有改資料表：作品存在既有的 `works`（`kind='turn_game'`）與 `work_versions`（`content_schema='game.v1'`）；模型呼叫沿用 `ai_generations` 與 `requests`（每日金額預留）。

## 4. 資料

### 4.1 作品內容 `game.v1`（節錄）

```python
{
  'schema': 'game.v1', 'skin': 'trip',
  'build': {'status': 'building' | 'ready', 'done': ['plan', 'c1'], 'pending': ['c2']},
  'setup': {'description', 'start_place', 'hours', 'start_time',
            'participants': [{'person_id', 'profile_id', 'version', 'content_sha256'}],   # 鎖定的人物設定版本
            'player': {'name', 'person_id': None}},
  'cast': [{'id': 'c1', 'name', 'person_id', 'public_profile'}],                          # 同行者 1～3 位
  'player': {'name': '你', 'public_profile': ''},                                         # 使用者扮演的人，沒有數值
  'title', 'genre', 'premise',
  'meter': {'label': '心情', 'min': -6, 'max': 6, 'low': -2, 'high': 2},
  'clock': {'start': 480, 'limit': 600}, 'speed': 12,
  'home': {'id': 'home', 'name', 'x', 'y', 'text'},
  'events': [{'id': 'p1', 'name', 'text', 'x', 'y', 'stay', 'open', 'close', 'tags',
              'reactions': {'c1': {'delta': -2..2, 'low', 'mid', 'high'}}}],              # 5～8 站
  'wishes': {'c1': '…'}, 'farewells': {'c1': {'low', 'mid', 'high'}},
  'endings': {'classes': {'perfect', 'great', 'ok', 'poor'}, 'thresholds': {'great', 'poor'}, 'reachable': [...]}
}
```

### 4.2 匯出資料 `lw-route.v1`

`game.v1` 去掉 `setup`、`build`、`generation_id`、`person_id`、`public_profile`，人物加上顏色序號。放在匯出檔的 `<script type="application/json" id="lw-story">`。

## 5. 規則（全部由程式計算，不交給模型）

**時間（行程題材；後端 `trip_timing` 與播放器 `tripSkin` 各一份，必須一致）**

- 車程＝`max(5, round(直線距離 × speed))` 分鐘；距離用 x、y 算；`round` 四捨五入（.5 進位）。
- 去 P 站：`arrive = now + 車程`；`begin = max(arrive, P.open)`；`leave = begin + P.stay`。
  - `leave > P.close` → 不能去（來不及）。
  - `leave + 回起點車程 > clock.start + clock.limit` → 不能去（趕不回起點）。
  - 去過的站不能再去。
- 隨時可以回起點；沒有站可去時只剩這一個。

**數值與結局**

- 每位同行者從 0 開始。到站時先依到站前的數值選一句反應（`≤ low` 用 low、`≥ high` 用 high、其餘 mid），再加 `delta` 並夾在 min～max。
- 結束：每位都 `≥ high` → perfect；否則總和 `≥ thresholds.great` → great；總和 `≤ thresholds.poor` → poor；其餘 ok；一站都沒去 → poor。
- 門檻：後端列舉所有走得到的行程（最多 8 站，直接窮舉），只算「至少去一站」的走法，以最近名次法取總和的第 75、25 百分位；兩者相等時 `poor = great - 1`；`reachable` 記下實際出現的結局種類。

**可玩性與整理**

- 規劃：`id` 由程式給；文字截斷；座標夾在 0～10，重疊就挪一格；停留夾在 30～150 並取 15 的倍數；`open ≥ close` 改整天開放；少於 4 站不合格。
- 可玩性：時限內至少走得完 3 站並回到起點。不成立時依序放寬：只把到不了的站改整天開放 → 全部整天開放 → 停留上限 60 分 → 全部 30 分；還不行才不合格。
- 角色反應：缺站補中性反應；`delta` 夾在 −2～+2；一位同行者的 `delta` 全部 ≤ 0 或全部相同 → 不合格（遊戲會是平的）；沒有任何反應 → 不合格。
- 出發時間加時數超過 24:00 → 422 `trip_past_midnight`（營業時間只能表示同一天）。

## 6. 模型呼叫與資料隔離

| 模組 | 版本 | 次數 | 送給模型的內容 | 輸出 |
|---|---|---|---|---|
| `game_plan` | `game-plan-v1` | 1 | 同行者的代號、名稱、公開簡介；使用者的稱呼；行程說明、起點、出發時間、時數；地圖大小 | 標題、開場白、數值名稱（固定清單擇一）、起點描述、5～8 站、四種結局 |
| `game_reaction` | `game-reaction-v1` | 每位同行者 1 | **只有這一位**的完整人物設定（鎖定版本）；使用者與其他同行者只有名稱與公開簡介；開場白；每一站 | 每站的 `delta` 與三種態度的反應、願望、三種最後一句話 |

- 規劃看不到任何人的人物設定；每位同行者看不到別人的設定。
- 兩個模組都是 `background = True`（不會被同帳號其他生成擋住）；同一件作品同時兩個 `advance` 時，第二個回 409 `generation_in_progress`。
- 每次呼叫沿用每日金額上限的預留與結算；失敗時作品不變。
- 輸出上限 2000 Token；實作者估計 8 站的反應約 1,200～1,550 Token（沒有用真實模型量過最壞情況）。
- 實測（2026-11-12，`gemini-3.5-flash-lite`，3 位同行者、6 站）：4 次呼叫全部成功，模型時間共約 16 秒，輸入約 18,500、輸出約 3,400 Token，估計約 US$0.014。

## 7. API

| 方法與路徑 | 說明 | 主要錯誤 |
|---|---|---|
| `POST /api/games` | body：`request_id`、`skin:'trip'`、`participants:[{person_id, profile_id?}]`（1～3）、`player:{name?}`、`description`、`start_place`、`hours`（8｜10｜12，預設 10）、`start_time`、`title?`。成功 201 `{id, title, build}` | 422 `participants_required`／`too_many_participants`／`duplicate_cast_name`／`trip_past_midnight`；404 `not_found`；409 `person_archived`／`person_profile_required`／`unified_people_not_enabled`；429 `ai_budget_reached`；模型錯誤 |
| `POST /api/games/{id}/advance` | body `{request_id}`。生成下一位；全部完成時算門檻、設 ready。已 ready 再呼叫回 200、不呼叫模型（提交代碼綁在別件作品時仍是 409） | 409 `generation_in_progress`／`work_archived`／`source_unavailable`／`idempotency_conflict`；模型錯誤時作品維持 building |
| `GET /api/games/{id}` | 只有本人。標題、開場白、同行者名稱、數值名稱、時鐘、站數、時數、`build`。**不含反應、願望、最後一句話、結局文字** | 404 |
| `POST /api/works/{id}/exports` | 既有路由。`turn_game` 只有 `route-1` 一種播放器；未 ready 回 409 `game_not_ready` | |
| `GET /api/works/{id}/exports/{v}/view` | 新。回同一份 HTML（不是附件），給同源的 `<iframe sandbox="allow-scripts">` 用；只有本人。reader-3、play-2 的匯出也適用 | 404 |

## 8. 站內框架的安全設計

- `/view` 回應的 CSP：`default-src 'none'; style-src <雜湊>; script-src <雜湊>; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'self'; sandbox allow-scripts`。
- `X-Frame-Options`：`app/main.py` 只在「GET、狀態 200、路徑完全符合 `VIEW_PATH`」時給 `SAMEORIGIN`，其他回應（含這條路由的錯誤回應）照舊 `DENY`。
- 首頁在有 Google 登入時的 CSP 原本只有 `frame-src https://accounts.google.com/gsi/`，會擋同源框架；這一版改成 `frame-src 'self' https://accounts.google.com/gsi/`。**這是這一版唯一放寬的既有安全標頭**，請評估。
- 沙箱裡沒有 localStorage；播放器的儲存都包在 try/catch。播放器寫入畫面一律用 `textContent`（`route-1.js` 沒有 `innerHTML`）。

## 9. 測試與目前的結果

| 測試檔 | 項目 | 內容 |
|---|---|---|
| `tests/test_turn_game.py` | 31 | 建立、逐位 advance、ready；重送；人物來源的拒絕；隔離（規劃不含設定、每位只含自己的）；整理；可玩性與放寬；時間、數值、結局、門檻；`GET` 不含劇透；作品中心；金額預留與結算；不改人物資料 |
| `tests/test_trip_reference.py` ＋ `tests/trip_reference.py` | 11 | Python 參考實作；用示意資料所有走得到的行程（898 條，含走到一半）逐步對照播放器的 JS。`tests/test_turn_game.py` 另有一則用同一份參考實作對照後端（448 條走法，時間、數值、結局與門檻都一致） |
| `tests/test_route_export.py` | 14 | 匯出、內部欄位不外流、跳脫、可重現、未 ready 409、`/view` 的標頭與權限、其他路由標頭不變、既有匯出逐位元不變 |
| `tests/test_game_view.py`、`tests/test_creation_mode_view.py` | 11、11 | Node 執行前端：玩法切換、送出內容、等待與失敗、advance 迴圈與重試、作品頁單一入口與標籤、「在這裡看」 |
| `browser_tests/test_export_route_offline.py` | 12 | 系統 Chrome 完全離線：開始、選站、反應與數值、不能去的原因、回溯、結局與特效、音樂預設不播、減少動態效果、手機寬度、沒有對外請求與 console 錯誤、沒有 JS 時的清單 |

最近一次整套結果：**1120 passed、7 failed、35 skipped、12 errors**。7 個失敗與 12 個錯誤在這一輪修改之前就存在，和這一版無關：

- 12 個 errors：`tests/product/test_google_exchange.py`（11）、`tests/product/test_gcp139_return.py`（1）——這個 venv 沒有 `google`／`cryptography` 套件。
- `tests/test_provider_independent_login.py`（3）、`tests/test_staging_tag_origin.py`（3）——同上，缺 Google 驗證套件。
- `tests/test_model_eval.py::test_records_snapshot_unknown_cost_human_score_and_no_product_tables`——Windows 的檔案權限位元。
- 另外 `tests/test_public_release_acceptance.py::test_public_password_core_journey_and_owner_isolation` 只在台北時間 0～9 點失敗（未修改的基準也一樣），白天執行會通過。

離線播放器三個檔（reader、play、route）26 passed。不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

真實環境的實測：在 8030 → Cloud SQL `life_world_e2e` 用使用者的 E2E 帳號建了一件海邊小鎮一日遊的作品，並在瀏覽器實際玩完一輪到 poor 結局。版面樣張（示意資料）：`C:\LifeWorld_project\alpha-unification-20261110\works_html_export_evidence\版面樣張-互動遊戲.html`。

**沒有自動化的雲端測試涵蓋 `/api/games`**：建立需要呼叫模型，雲端環境沒有假模型。

## 10. 已知問題（已記錄，請評估嚴重度，不必當成新發現）

1. ~~`GET /api/works/{id}`（既有的通用路由）回整份作品內容~~：已在第 13 節修正（依種類投影）。
2. 願望可能指到不存在的站（實測一例），無從滿足。
3. 結局門檻是相對的：實測數值總和 +1 被判成 poor。
4. 反應只看「這一站」與「到站前的態度」，不知道先前去過哪裡（預先生成的限制）。
5. 生成要遊戲頁開著（由頁面呼叫 `advance`）；沒有背景排程。
6. 列舉所有行程算門檻在保存的交易裡做；最壞情況（8 站、任意順序都走得完，約 11 萬條）約 0.36 秒。
7. App 內的瀏覽器面板會擋頁面內的框架（`ERR_BLOCKED_BY_CLIENT`），「在這裡玩／看」要用「在新分頁開啟」；一般 Chrome 只在測試環境驗過。
8. 建立遊戲成功後整份建立草稿清空，包含看的故事那一側的欄位。
9. 音樂只確認按了才建立音訊，沒有人實際聽過。

## 11. 請 Codex 檢驗的項目

**正確性**

- [ ] 後端 `trip_*` 與播放器 `tripSkin` 的時間規則完全一致（含邊界：剛好打烊、剛好趕回、等開門、.5 的四捨五入）。
- [ ] 數值區間的判定（`≤ low`／`≥ high` 的等號）與結局判定兩邊一致。
- [ ] 門檻與 `reachable` 的算法符合第 5 節；`reachable` 裡的每一種結局真的走得到。
- [ ] 可玩性放寬的順序與結果；放寬後仍不合格時不會存半成品。
- [ ] `tidy_plan`／`tidy_reaction` 對各種錯誤輸出（缺欄位、型別錯、超長、重複、指到不存在的代號）都不會拋例外。

**隔離與隱私**

- [ ] 規劃收到的內容不含任何人物設定欄位；每位同行者只收到自己的設定。
- [ ] `GET /api/games/{id}`、作品中心、匯出檔都不含 `person_id`、`public_profile`、`setup.participants`、`generation_id`。
- [ ] 第 10 節第 1 項的嚴重度，以及建議怎麼收斂（例如通用路由依種類過濾）。
- [ ] 匯出檔與站內頁面不含「我的設定」或人物設定的任何內容。

**安全**

- [ ] `/view` 的 CSP、`X-Frame-Options`、`sandbox` 是否足夠；`VIEW_PATH` 的比對是否可能被其他路徑繞過。
- [ ] 第 8 節首頁 `frame-src 'self'` 的放寬是否可接受。
- [ ] 播放器與前端的跳脫（`route-1.js`、`game.js`、`creation.js`）：模型輸出的任何文字都不能成為 HTML 或程式。
- [ ] 匯出檔沒有任何對外請求。

**冪等、並行與費用**

- [ ] `request_id` 重送不重複呼叫模型；同一件作品並行 `advance` 不會讓同一位被生成兩次。
- [ ] 每次呼叫都有金額預留與結算；模型失敗、逾時、輸出不合格時作品不變、預留依規則處理。
- [ ] 前端自動重試的上限與每次換新 `request_id` 的行為。

**相容與部署**

- [ ] PostgreSQL 相容（本機測試是 SQLite；8030 上的真實建立只有一次）。
- [ ] 新檔都在 `deploy/core-e2e-build-sources.txt`；沒有遺漏的靜態檔。
- [ ] 既有的閱讀版（reader-3）與互動版（play-2）匯出逐位元不變。
- [ ] 預設玩法（看的故事）下，建立頁的畫面與送出的請求和改動前相同。

**文件**

- [ ] `docs/UNIFIED_PERSON_HANDOVER.md` 第 4 節「回合制互動作品」「統一建立入口」與程式一致；`docs/ACCEPTANCE.md` 的數字與實際執行相符。

## 12. 這一版上 GitHub 的範圍（不只互動遊戲）

上次推送是 `39ad50a`（11-11）。之後的本機修改依時間順序包含：

1. 作品匯出成 HTML 第 1 級（`app/object_storage.py`、`app/work_export.py`，Cloud Storage bucket `lw-works-e2e-513506`）。
2. 多章節作品（第 2 級：`app/story_series.py`、`app/story_continuity.py`、`app/static/series.js`）。
3. 作品頁讀不到進度時自動重試（`generation.js` 的 `advance`）。
4. 每日金額預留：供應商明確拒絕（429、503）且沒有用量的呼叫退回預留（`app/generation.py`）。
5. 生成提示詞 v5～v8（人物個性、跨章一致、破題與名場面、通用故事原則；`app/roleplay.py`），以及名場面範例場景（`app/catalog/scene_presets.v1.json`）。
6. 閱讀器 `reader-3`（人物顏色、陣營、起承轉合、下集預告）。
7. 互動層與互動版 `play-2`（`app/interactive_layer.py`、`POST /api/works/{id}/interactive`）。
8. 互動遊戲第 1 期（本文件）。
9. 統一建立入口。

每一項的規則都在 `docs/UNIFIED_PERSON_HANDOVER.md` 第 4 節，驗收紀錄在 `docs/ACCEPTANCE.md`。請以互動遊戲為重點，其餘做一致性與回歸的檢查。

**不要提交的檔案**

- `docs/FIRST_WORK_GENERATION_READINESS_20261111.md`：先前的盤查報告，含 15 位人物設定的全文。

**工作樹外的相關修改**（不在這個倉庫）

- `C:\LifeWorld_project\LifeWorld-STARTUP\core-e2e-8030\Deploy-8030-E2E.ps1`：e2e 部署多設定一個環境變數 `LIFEWORLD_WORKS_BUCKET`。

**換行**：工作區部分檔案是 CRLF；`.gitattributes` 把 `.py`／`.js`／`.css`／`.html`／`.md` 正規化成 LF，提交時 git 會提示轉換，屬正常現象。

## 13. 外部檢驗後的修正（2026-11-12，請複驗）

第一次檢驗報告：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_INDEPENDENT_REVIEW_20261112.md`。五項發現的修正：

| 發現（Codex 的優先序） | 修正 | 測試 |
|---|---|---|
| P1 同一位同行者可以重複生成及結算（第一個請求結算後、存進作品前的空窗） | `GameReactionModule.resolve` 在同一個交易內也找「已成功、還沒存進作品」的那一筆；有的話不預留、不呼叫模型，`/advance` 直接 `game_apply` 那一筆。互動層（`POST /api/works/{id}/interactive`）有同樣的空窗，用同樣的做法修正 | `tests/test_turn_game.py`、`tests/test_interactive_layer.py`：模型沒有再被呼叫、帳本只有一筆預留、作品只多一個版本 |
| P2 規劃失敗後，原表單重按只拿到舊錯誤 | 建立頁與遊戲頁依結果決定提交代碼：伺服器明確回了失敗（有狀態碼，且不是 409 `generation_in_progress`）→ 下一次是新的嘗試；連線中斷或還在進行 → 沿用原代碼（若其實已完成，重送只會找回那一次的結果）。建立頁失敗時另外說明再按會發生什麼（重新規劃並再呼叫一次模型，或只是找回結果） | `tests/test_creation_mode_view.py`、`tests/test_game_view.py`（原本「每次重試都換新代碼」的斷言依這條規則改寫） |
| P2 模型回超大整數時 500、紀錄留在 `running` | `number()` 先檢查範圍（絕對值超過 10^9 當作沒有給），任何輸入都不拋例外；兩個模組的 `parse` 把整理時意外的例外轉成 `invalid_output`；共用的 `ai_finish` 也兜底：`parse` 拋出非預期的例外時記一行只有類型的日誌，當作 `invalid_output`，紀錄一定離開 `running`、用量照常結算 | `tests/test_turn_game.py`（規劃與反應各一）、`tests/test_generation_8030.py`（共用層） |
| P2 匯出文字的隱私承諾超出程式保證 | 作品頁、多章節總覽、遊戲頁的說明改成實際能保證的範圍：檔案裡不含人物設定的欄位與我的設定；台詞與反應是 AI 依人物設定寫的，可能用到設定裡的說法，分享前可以先看過。沒有加自動比對原文的檢查 | 前端測試照舊檢查說明存在 |
| P2 通用作品 API 讓本人讀到劇透與內部參照 | `GET /api/works/{id}`、`GET /api/works/{id}/versions/{n}`、`POST /api/works/{id}/status` 依種類投影：`turn_game` 只回和 `GET /api/games/{id}` 同等級的欄位；`generated_work` 拿掉 `content.interactive` 與 `plan.private_notes`（`meta` 不變）。另外 `GET /api/ai/generations/{id}` 對 `game_plan`、`game_reaction`、`interactive_layer` 不回原稿，`roleplay_plan` 的原稿拿掉 `private_notes` | `tests/test_turn_game.py`、`tests/test_interactive_layer.py` |

請複驗：

- [ ] 報告裡的重現案例（`review_probes.py`）在修正後的行為。注意：`test_export_preserves_model_generated_strings_including_source_echoes` 原本斷言通用詳情裡有 `setup.participants[0].person_id`、版本 1 有 `endings.classes`，這是修正前的行為，修正後應改成斷言這些欄位不存在。
- [ ] 互動層（`POST /api/works/{id}/interactive`）的同一個空窗也已修正。
- [ ] `GET /api/ai/generations/{id}` 的投影沒有影響角色卡草稿（前端只讀角色卡草稿的 output；`app/static` 沒有讀這幾個模組的生成紀錄）。
- [ ] 前端提交代碼的規則：伺服器明確失敗才換新；連線中斷、409 `generation_in_progress` 沿用。
- [ ] 已知限制（交接第 4 節「外部檢驗後的修正」）是否可以接受。

最新結果：整套 1134 passed、7 failed、35 skipped、12 errors（278 秒），失敗與錯誤的清單和修改前相同；離線播放器 26 passed；雲端回歸 3 passed／3 skipped。

## 14. 第二次外部檢驗後的修正（2026-11-12，請再複驗）

第二次檢驗報告：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_RECHECK_20261112.md`。修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| P1 接手別的請求已結算的結果後，同一個提交代碼重送會替下一位同行者生成並再計費 | 接手時在存入作品的同一個交易裡替這個提交代碼記回執（`game:advance`，綁定作品與那一筆結果）；`/advance` 挑下一位之前先查回執，有就只回目前的進度。同一個代碼拿去推進另一件作品是 409 `idempotency_conflict` | `tests/test_turn_game.py`：重送不再呼叫模型、帳本不變、完成後重送也不生成、跨作品 409 |
| P2 修正之前保存的封存／恢復回執重送仍回完整內容 | 讀回執時也套用公開規則（`works_center.public_detail`）；`turn_game.game_public` 對已經公開的內容只挑公開欄位，投影兩次結果相同 | `tests/test_turn_game.py`：把回執改成修正前的格式後重送，只有公開欄位 |
| P2 舊種類 `roleplay_session` 恢復生成後，通用 API 讀得到底牌 | `public_content` 對 `roleplay_session` 套用和 `generated_work` 相同的規則；沒有這些欄位的舊內容原樣回傳 | `tests/test_turn_game.py` |
| 提交文件含連結實際帳號的驗收紀錄 | 四份文件（`ACCEPTANCE.md`、`EVOLUTION.md`、`UNIFIED_PERSON_HANDOVER.md`、`INTERACTIVE_GAME_REVIEW_20261112.md`）把帳號名稱改成「使用者的 E2E 帳號」，拿掉該帳號五件作品的識別碼，以及帳號本人在我的設定做過哪些操作的描述。原始紀錄另存在工作樹外：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/acceptance_raw_20261112/` | 掃描四份文件沒有帳號名稱與那五個識別碼 |

請再複驗：

- [ ] 報告第二節三個程式問題的重現案例（`recheck_probes.py`、`recheck_limits.py`），SQLite 與隔離 PostgreSQL。注意 `recheck_limits.py` 斷言的是修正前的現況，修正後應改成斷言劇透欄位不存在。
- [ ] 兩個同代碼的 `/advance` 同時接手同一筆結果時只記一筆回執、不出錯（同帳號的寫入依序進行）。
- [ ] 四份文件的去識別化，以及提交候選清單裡沒有其他連結實際帳號的內容。
- [ ] 回歸：整套、離線播放器、既有匯出逐位元不變、預設建立頁不變。

最新結果：整套 1137 passed、7 failed、35 skipped、12 errors（298.50 秒），失敗與錯誤的清單和修改前相同；離線播放器 26 passed；雲端回歸 3 passed／3 skipped。

## 15. 第三次外部檢驗後的修正（2026-11-12，請再複驗）

第三次檢驗報告：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_THIRD_REVIEW_20261112.md`。修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| P1 同一個提交代碼的兩個請求並行：一個在路由查過「沒有回執」後停住，另一個接手已結算的結果、記回執、存好（2/3）；前一個再走進預留，就替下一位同行者生成並多結算一次（3/3） | 查回執、接手已結算的結果並記回執、決定是否預留下一位，放進同一個寫入交易。共用預留 `ai_reserve` 多一個 `shortcut`：在同代碼的生成紀錄查過之後、`resolve` 之前執行，回傳值就是這次的結果（不預留、不占額度，交易照常提交）。回合制作品的捷徑是 `TurnGameMixin._game_pickup`；下一位的檢查抽成 `GameReactionModule.target`，捷徑與 `resolve` 共用同一套檢查。回執在預留的交易裡就記好，`game_apply` 不再寫回執：存作品失敗時，同一個代碼重送照回執再存，不往下生成。路由的快速查詢保留（不需要 Provider），查到「沒有」不算數 | `tests/test_turn_game.py::test_two_requests_with_the_same_id_picking_up_a_settled_result_never_start_another_companion`：三種次序（兩個都到存作品那一步、一個早查晚預留、存作品失敗後重送），都要一筆回執、兩個回應都是 2/3、只替第一位呼叫過模型、帳本不變、作品只多一個版本；「早查晚預留」在修正前失敗 |
| 文件仍有帳號的同意狀態，以及實際作品的標題與陣容 | 四份文件拿掉帳號的同意狀態（含交接第 7 節表格的 `consent`）；作品標題、人物名稱與生成內容的細節改成通用描述（第幾件、名場面藍本、幾位人物、主角／對手／軍師），路徑、呼叫次數、費用、段數與人工閱讀的結論保留。上一輪替換帳號名稱時弄壞的匯入資料夾路徑改成文字描述。這一輪改之前的版本另存在工作樹外：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/acceptance_raw_20261112/*_before_third.md` | 第三次檢驗的掃描程式（在暫存資料夾的複本）重跑：帳號名稱、五個識別碼、四個作品標題都是 0；`consent_near_anonymous_account` 只剩 `EVOLUTION.md:242`（那一行寫的是產品的同意文字仍用「我的人設」，不是帳號的狀態） |

範圍說明：`tests/`、`browser_tests/` 用的虛構人物名稱與公開簡介，是既有的合成測試資料（已提交的 `39ad50a` 裡就有），沒有人物設定欄位的內容，也不連到任何帳號；這一輪沒有改。

請再複驗：

- [ ] 第三次報告第二節的並行次序（`third_review_probes.py` 的 `second_reads_before_commit_reserves_after`）與 `both_reach_apply`，SQLite 與隔離 PostgreSQL。
- [ ] 存作品失敗後，同一個代碼重送照回執存好、不往下生成；同一個代碼用在另一件作品仍是 409 `idempotency_conflict`；已有回執的重送在沒有設定 Provider 時也能回進度（路由的快速查詢）。
- [ ] `ai_reserve` 的 `shortcut` 不影響其他模組（只有回合制作品的角色反應傳入）。
- [ ] 四份文件與其餘候選檔案沒有帳號的同意狀態、作品標題與陣容；`EVOLUTION.md:242` 是產品文字，請確認可以接受。
- [ ] 回歸：整套、離線播放器、既有匯出逐位元不變、預設建立頁不變。

最新結果：整套 1140 passed、7 failed、35 skipped、12 errors（292 秒；失敗、錯誤與跳過的清單和第三次檢驗的基線逐項相同，多的 3 項是新測試）；離線播放器 26 passed；雲端回歸 3 passed／3 skipped；Codex 的第三次重現程式（`third_review_probes.py`、`third_review_limits.py`）在本機 SQLite 重跑：14 passed（修正前 13 passed、1 failed）。

## 16. 第四次外部檢驗後的修正（2026-11-12，請再複驗）

第四次檢驗報告：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_FOURTH_REVIEW_20261112.md`。修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| 已綁在遊戲 A 的提交代碼送到遊戲 B：B 還在生成時是 409 `idempotency_conflict`，B 已完成時卻先回 200（路由看到 ready 就回傳，沒有檢查代碼綁在哪一件） | `/advance` 先呼叫快速查詢 `game_advance_receipt` 再判斷 ready。快速查詢是唯讀交易、不需要 Provider，同時檢查代碼的兩種綁定：接手的回執（`requests` 的 `game:advance`）與這個代碼自己生成過的角色反應（`ai_generations`，指紋用和 `ai_reserve` 相同的 `ai_fingerprint`）；綁在別件作品就是 409。同一件作品自己的代碼重送、全新的代碼，在 ready 時照常回 200。預留交易裡的查核（`_game_pickup`）保留 | `tests/test_turn_game.py::test_a_code_bound_to_one_game_is_refused_on_another_game_even_when_that_game_is_ready`（兩種綁定來源；B 生成中與已完成；沒有設定 Provider；同作品重送與新代碼 200；不呼叫模型、帳本與作品不變），修正前兩種來源都失敗 |

第 7 節 API 表的 `/advance` 一列已補上：已完成時回 200，但提交代碼綁在別件作品仍是 409 `idempotency_conflict`。

請再複驗：

- [ ] 第四次報告第二節的案例（`fourth_review_cases.py` 的 `test_bound_code_conflicts_on_another_game_that_is_already_ready`，兩種代碼來源），SQLite 與隔離 PostgreSQL。
- [ ] ready 時同一件作品自己的代碼重送、全新的代碼都回 200，沒有設定 Provider 也一樣；別件作品的代碼在沒有設定 Provider 時也是 409。
- [ ] 第三次的並行案例與第四次的其他補充案例仍通過（`third_review_probes.py`、`third_review_limits.py`、`fourth_review_cases.py`）。
- [ ] 回歸：整套、離線播放器、既有匯出逐位元不變、預設建立頁不變；提交範圍與第 12 節相同（這一輪沒有新增檔案）。

最新結果：整套 1142 passed、7 failed、35 skipped、12 errors（267 秒；失敗、錯誤與跳過的清單和第四次檢驗的基線逐項相同，多的 2 項是新測試）；離線播放器 26 passed；雲端回歸 3 passed／3 skipped；Codex 的重現程式（`third_review_probes.py`、`third_review_limits.py`、`fourth_review_cases.py`）在本機 SQLite 重跑：19 passed（修正前第四次的補充案例是 3 passed、2 failed）。
