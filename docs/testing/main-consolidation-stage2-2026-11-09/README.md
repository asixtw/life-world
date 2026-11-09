# Main 整合第二階段：限流契約與隔離回歸

日期：2026-11-09（Asia/Taipei）。分支：`codex/main-consolidation-stage2-20261109`，PR Base為main `82d0925597aeb23b95023f102b1ca98c46666fe9`。內容完整沿用public-core `611e8398508a9fba440aa9c941d4d20b83190fef`（main的線性後代），不重複Merge PR15–19、不納入PR14、不以PR3原型替代產品。

**狀態：隔離回歸PASS；main Merge仍等待明確授權與CI隔離。** 未Build、Deploy、切流、改Trigger／發布器、執行雲端SQL、修改IAM／Secrets。現役仍為 `lw-public-camera-8f377fa`，100%。

## 本輪修改與契約

產品 `app/`、模型、UI、音效、Dockerfile、DB SQL及發布器均沒有相對611e839變動。

- 舊測試「所有Guest共用10次」改為11名正常訪客成功、偽造XFF仍只命中同一HMAC桶。
- 新增8項Guest配額測試：實際Guest總量、累積建立收據、每日額度與視窗重開、shared每小時1000次、偽造XFF、有效Session重送、並行匿名容量不超額、並行Session不重複建世界、可信direct peer每小時10次。每日與累積容量採測試設定，沒有降低產品門檻。
- 無有效Session的並行匿名請求視為獨立訪客，僅保證硬容量不超額；既有前端按鈕去重與有效Session重送不重建世界仍有測試，未發明跨匿名請求的身分合併規則。
- 精確驗證Retry-After倒數與scope；拒絕不延長視窗，且不留下額外User／Session。配額邊界測試只在合成DB預置999次計數，仍走真正API交易驗證第1000／1001次。
- PG測試客戶端共用一個服務生命週期，避免每關閉一個測試瀏覽器便關閉整個PG pool。這是fixture修正，不改應用生命週期。
- PG核心006的32表／207欄／60 FK契約繼續完整比對。SQLite額外009的兩張記憶契約表明確列出，不將其當作已部署PG或忽略未知表。
- 歡迎頁已核准共用Lumi插畫；Chromium改驗證該插畫存在，仍保留建立第一目標前沒有「個人已孵化寵物」及三段孵化的原驗收。
- 新增僅本機的 `browser_tests/rc_fixture_server.py`：固定日期、明示模型替身、只允許/private/tmp與SQLite，解決RC流程依賴未記錄的舊測試服務。它不進API runtime映像，也不呼叫Gemini。

## 實際結果

|驗證|結果|證據|
|---|---|---|
|舊限流斷言紅燈|1 failed，預期重現舊契約衝突|evidence/RATE_CONTRACT_RED.log|
|限流／公平性／公開身分定點|12 passed|evidence/RATE_CONTRACT_GREEN.log|
|完整SQLite API，已提供Node|512 passed／17 skipped|evidence/SQLITE_FINAL.log|
|隔離PostgreSQL模式完整API|529 passed／0 skipped，2 warnings|evidence/POSTGRES_FULL.log|
|Node日期／習慣／前端邏輯|13 passed，亦包含於完整suite|evidence/NODE_FRONTEND.log|
|Chromium一般核心|36 passed／1 skipped|evidence/CHROMIUM_CORE_GREEN.log|
|上列跨日時鐘補測|1 passed，補齊唯一skip|evidence/CHROMIUM_CLOCK.log|
|Chromium AI草稿／確認／冪等／進度／Lumi|2 passed，390／1440px|evidence/CHROMIUM_AI_FIXTURE.log|
|發布政策（mock，無雲端寫入）|24 passed|evidence/RELEASE_POLICY.log|
|真ffmpeg解碼／串流分段|2秒／61秒11,712,044 bytes均PASS|evidence/FFMPEG_REAL_DECODE.json|

Chromium合計39個不同案例已覆蓋；一般核心首次skip因缺時鐘控制檔，已以專用時鐘服務實跑，沒有用刪除案例或調低標準消除skip。SQLite的17個PG專用skip由完整PG模式實際覆蓋，不把SQLite log寫成0 skip。

PG是本機從官方18.6原始碼編譯，只綁127.0.0.1:57483、固定cluster marker `lifeworld-step10-4-synthetic`；bootstrap僅初始化本輪合成life_world_dev／Alpha fixture，絕不連Cloud SQL。原本55432被既有程序占用，改用57483，未停止或修改原程序。PG模式內通用app fixture接真PG，明確SQLite專用測試仍維持SQLite，不宣稱529項全都只使用PG。PG收據有2個warning，未列為失敗；未因警告刪除或跳過案例。

ffmpeg 9.0是本機測試binary，驗證真解碼為16kHz單聲道、每段最多30秒，61秒分30／30／1秒，原始素材保持、輸出仍為候選。模型是明示替身；沒有新增真Gemini呼叫，亦未重建／重驗正式容器的OS套件版本。Dockerfile既有ffmpeg安裝行未改。

## 可重現執行

Python為暫存Python3.12環境；Node22.15.0官方Darwin arm64包已比對官方SHA256。測試套件／鎖檔沒有為安裝工具新增產品依賴。

```sh
LIFEWORLD_NODE=/path/to/node python -m pytest tests -q
# 專用PG18先由scripts/pg_test_bootstrap.py初始化一次；只有marker與127.0.0.1符合才可執行。
# LIFEWORLD_TEST_PG_PASSWORD由私密環境注入，不寫入Repo、命令列或日誌。
LIFEWORLD_TEST_PG_HOST=127.0.0.1 LIFEWORLD_TEST_PG_PORT=57483 LIFEWORLD_TEST_BACKEND=postgresql LIFEWORLD_NODE=/path/to/node python -m pytest tests -q
python -m unittest discover -s deploy/tests -p test_release.py -q
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8002
# 上一步需明確設定LIFEWORLD_DATA_DIR=/private/tmp/isolated與LIFEWORLD_DB_BACKEND=sqlite。
LIFEWORLD_TEST_URL=http://127.0.0.1:8002 python -m pytest browser_tests/test_journey.py browser_tests/test_goal_flow.py browser_tests/test_birth_interaction.py browser_tests/test_media_flow.py browser_tests/test_mobile_photo_normalization.py browser_tests/test_person_hint_review.py browser_tests/test_theater_dispatch.py browser_tests/test_logout_recovery.py browser_tests/test_guest_start_guard.py -q
python -m browser_tests.rc_fixture_server --data-dir=/private/tmp/rc-isolated --port=8003
LIFEWORLD_TEST_URL=http://127.0.0.1:8003 python -m pytest browser_tests/test_rc_browser_flow.py -q
# 跨日補測必須另以clock_server提供相同LIFEWORLD_TEST_CLOCK_FILE，不能對正式服務改時間。
```

原始收據及SHA256見evidence/。測試生成的截圖另外保存在本機交付包，沒有覆蓋歷史截圖或將日期造成的二進位差異混入PR。

## 已知剩餘項與授權

- 新分支以main為Base的Draft PR供審查，不代表Merge授權，也未更新PR20或關閉其他PR。
- main的API Trigger仍會命中產品Diff，目前沒有人工approval gate；發布器現有模板／正式Revision不一致尚未修復。本輪不依賴其失敗作隔離保障。
- 推薦下一批只針對API Trigger開啟人工核准，正式Merge前讀回並確認沒有已執行的舊Build；詳見[隔離提案](PUBLISH_ISOLATION_PROPOSAL.md)。本輪未執行。
- 現役app來源仍8f377fa；本分支app內容完全相同，但Git整合候選尚未Build或部署。
- Safari無痕Google redirect、Email恢復、正式Hidden Feature Store及完整Alpha備份Gate等既有產品工作不因本輪隔離測試通過而變成PASS。真實Google／AI／公開Alpha寫入本輪NOT RUN。
