# TDD 與實際驗收紀錄

## 2026-11-07 GCP-144 孵化互動

隔離Chromium `browser_tests/test_birth_interaction.py -q --tb=short`：4 passed（桌面／觸控，各含reduced motion）。驗證三次點擊、動畫鎖及第三階段揭露。完整後端旅程未重跑；線上與DB驗收不在此證據範圍。詳見[盤點與限制](art/README.md)。

## 首次自動部署已知失敗修復（2026-11-05，合併前檢查）

基準 `1cd3458`：Web 在發布步驟找不到 PATH 上的 python3，API 舊契約讀取已移除的 images。API 單檔先重現 1 failed／2 passed；新增發布容器契約亦先重現舊映像不符，修正後 `.venv\Scripts\python.exe -X utf8 -m pytest --noconftest tests/test_api_build_config.py -q --tb=short -p no:cacheprovider`：3 passed、0 failed、0 skipped。兩份 YAML 解析及發布入口契約通過，`release.py` 與基準逐位元內容（統一換行後）一致，候選／回滾邏輯未修改；未重跑完整 API 測試。

Windows／既有 WSL 無 Docker CLI，本機容器檢查未執行成功；經使用者明確同意，僅提交一次無原始碼、無部署的 Cloud Build `8eab4a4f-ef32-4dd4-8812-f24e854945e9`，結果 SUCCESS。官方 google-cloud-cli:slim（digest `sha256:8a50079dfc4b164aa5e83926bef5f9b305b93e80f82d40fabd836da4830dd08e`）實際 PATH 無 python3，但映像自帶 `/usr/lib/google-cloud-sdk/platform/bundledpythonunix/bin/python3` 可匯入發布器所需標準庫並呼叫 gcloud 592.0.0，日誌為 RELEASE_RUNTIME_CHECK=PASS。兩份 YAML 改用該官方映像與已驗證絕對入口，不另安裝套件。

Web 來源唯讀核對：00004-rmt 於台北時間 2026-11-03 17:45 建立，commit e9f9661；00005-qtk 於 2026-11-05 17:18 建立，commit 4ece786，creator 為 lw-build-main，digest 與既有 Web Trigger 的成功 Build `da542cb1-7aea-4083-a617-13e9c3186266` 結果完全一致，早於本次 CI/CD 啟用失敗。未因此修改流量。本節僅記合併前驗證，不代表修復後的正式發布已通過。

## 自動 CI/CD 最終準備（2026-11-05，續 e368379）

先以虛擬時間新增兩個鎖等待案例，舊版實際 2 failed（180 秒提前結束，無法等到第 240 秒／不足 900 秒），修正後僅重跑直接相關檢查：`.venv\Scripts\python.exe -X utf8 -m pytest deploy/tests/test_release.py -q --tb=short -p no:cacheprovider -k 'lock or cancelled or rollback_cannot or older_rebuild'`：9 passed、15 deselected、0 skipped；Python AST／Web timeout 基本檢查通過。第一次相關檢查為 6 passed、3 failed，三項均因沙箱 TEMP 的 WinError 5 無法 chdir，改以正常 TEMP 執行後上述 9 項通過，未修改案例放寬斷言。Web／API `--preflight` 本輪各通過，未出現 Traffic has no resolved revision。未重跑整套測試、未部署／改流量。IAM 專案直接政策僅 Logging Writer／Run Developer，自身 policy 為空，角色定義不含兩項待查權限；有效權限因 Troubleshooter API 未啟用、組織政策查詢 403 而未能完整確認，不標為通過或確定缺少，也未修改 IAM。安全解除遺留鎖僅有文件程序，未實際執行。

## 自動 CI/CD 發布護欄（2026-11-05）

本輪 `python -X utf8 -m unittest discover -s deploy/tests -p 'test_*.py' -q`：31 passed、0 failed、0 skipped。只測 YAML／Bash、合成發布控制平面及關鍵來源／CAS／回滾邊界；沒有執行 Cloud Build、Artifact Push 或正式流量發布。新增函式先重現 10 項未實作失敗；發布回應遺失先重現錯誤流量保留，再補上回滾與取消後恢復 journal。API 唯讀 `--preflight`、兩服務的 Cloud Run `validateOnly` 請求格式檢查成功，沒有讀 Secret 值或 Cloud SQL 資料。兩個既有 Trigger 只修改 includedFiles 並讀回 Web 19／API 12 項，來源與 SA 未變；首個 PATCH 缺必要 query 欄位遭 400 拒絕，補齊後成功，未啟動建置或修改 IAM／流量。既有 React、SQLite／PG 與容器驗證步驟原樣保留，並未以本輪結果冒充重跑。完整機制、一次性權限及啟用界線見 `deploy/README.web-main.md`、`deploy/README.api-main.md`。

## v0.4.0 單一目標與三個習慣（2026-10-28～29）

本輪實測 **137 項後端、19 項 Chromium 全數通過，0 失敗、0 跳過**。涵蓋分步建立、月／週日期、返回草稿、到期回顧、逐筆採計、歷史與原有完整回歸；27 個既有資料表原欄位遷移前後一致。完整命令、有效紅燈、手機／桌面圖與限制見[單一目標驗收](GOAL_FLOW_ACCEPTANCE.md)。下方數字是各舊版本當時結果。2026-10-29 發布準備另行重跑的命令與結果見[v0.4 發布檢查](GITHUB_PUBLISH_V0_4.md)，不覆寫初次 TDD 證據。

## Windows 環境安裝修正（2026-10-30）

`greenlet` 3.2.5 沒有任何 Windows 預編譯檔，`python scripts/setup.py` 在沒有 C++ 編譯器的 Windows 會失敗。`requirements.lock` 改為 Windows 鎖 3.2.4，其他平台維持 3.2.5，保留其 Python 3.9／3.10 結束時崩潰的修正；並補鎖 Windows 專用的 `colorama` 0.4.6。`scripts/setup.py` 另增加損壞環境重建、移除鎖定外套件與 `--check` 比對。`greenlet` 僅供 Playwright 使用，App 仍為 v0.3.0。

- 環境：Windows 11、Python 3.14.7、Playwright 1.60.0、greenlet 3.2.4。
- 紅燈／綠燈：`tests/test_dependency_lock.py` 先因鎖定 `greenlet==3.2.5` 失敗，改版後通過。Codex 兩輪獨立檢驗指出解析可被行末註解、等價版本寫法及其他 Python 條件繞過，也會誤判安全寫法；補案例確認紅燈後，改以 `packaging` 依版本語意及 Python 3.9～3.14 判斷。
- 測試規格修正：`tests/test_setup_script.py` 原有「直譯器無法啟動就重建」兩項案例已改為「暫時性失敗不得清除環境」。依據是 Codex 注入一次性 `PermissionError` 證實原行為會誤刪可用環境，且探測沒有期限；改為只依 `pyvenv.cfg` 記錄的基礎 Python 判斷損壞，不執行直譯器。
- 安裝：全新環境執行 `python scripts/setup.py` 成功，Windows 生效的 35 項鎖定套件全數安裝，除 pip 外沒有未鎖定套件。基礎 Python 路徑失效的 `.venv`（結束碼 103）可由 `setup.py` 重建，環境完整時不重建。
- 環境同步：`setup.py --check` 直接比對已安裝版本與鎖定檔，取代先前的安裝指紋。實測版本變更、套件遺失、移出鎖定檔的 `tomli` 都能同步；只改換行不會重裝；安裝失敗時環境維持不一致，不會誤報成功。
- 平台：以 `pip install --dry-run --only-binary=:all:` 核對 Python 3.9／3.12／3.14 與 Windows x64／macOS arm64／Linux x86_64 的組合，均有預編譯檔；同一檢查對 3.2.5＋Windows＋Python 3.14 確實失敗。該檢查於鎖定檔分平台前執行，macOS／Linux 的 3.2.5 另由 PyPI 發行檔確認有預編譯檔。實際安裝只在 Windows 執行，macOS／Linux 未執行。Windows ARM64 沒有 3.2.4 預編譯檔。
- 後端：`.venv\Scripts\python.exe -m pytest -q`，**125 passed**。其中 `test_migration_preserves_legacy_rows_and_rewards` 原本在繁體中文 Windows（cp950）失敗，與本次依賴無關：`tests/test_connections.py:185` 的 `read_text()` 未指定編碼，無法讀取 UTF-8 遷移檔。已改為 `encoding='utf-8'`，斷言未變更。
- 瀏覽器：**14 passed**，由 Codex 於鎖定檔分平台後，在獨立複本以內建 Chromium 執行回報。此後 `requirements.lock` 未再變更，後續改動限 `setup.py`、測試與倉庫外的啟動檔，未重跑。此套件會覆寫 `docs/artifacts/connections` 的截圖，須在複本內執行或事後還原。
- 未驗證：真實重新開機未執行，以停止後重新啟動代替。未建立 CI 安裝矩陣，`NO_WINDOWS_WHEELS` 只防護已知版本，不保證未來版本都有預編譯檔。網站執行中更新鎖定檔不會同步，須停止網站後重新啟動。

## v0.3.0 交會與完整體驗（2026-10-28）

最新實際結果為 **100 項後端通過、14 項 Chromium 旅程通過**，含既有目標、草稿、人物及小劇場回歸，並驗證交會取代星圖後的來源、配對、返回與失敗退路。完整紅燈／綠燈、手機／桌面截圖、卡頓量測及 22 表資料升級檢查見[交會整合與體驗報告](CONNECTIONS_ACCEPTANCE.md)。下方是 v0.1／v0.2 歷史，不當成本輪結果。

日期：2026-10-27，Asia/Taipei。測試使用虛構內容與隔離資料，沒有把正式客戶或原交接範例當作真實資料。

## v0.2.0 人物流程還原

本輪最後實際結果為 **81 項後端測試通過、7 項 Chromium 瀏覽器測試通過**，包含原有 63 項後端案例與 3 條瀏覽器旅程。原圖逐張對照、手機／桌面截圖、紅燈與綠燈紀錄、資料升級及保留差異見 [人物流程還原驗收](PEOPLE_RESTORATION.md)。下方保留 v0.1 的歷史驗收紀錄，當中的 63／3 是當時結果。

## v0.1 歷史紀錄

## 測試驅動過程

1. 先建立 `REQUIREMENTS.md`，記錄 U-01～06、正常／異常／邊界，以及尚未正式裁定的開發設定。
2. 先撰寫 pytest 案例；最初沒有 `app.main` 時 import 失敗。加入只有 FastAPI factory 的紅燈殼後，**55 項測試全部失敗**；原始輸出保存在 [TDD_RED.txt](TDD_RED.txt)。
3. 實作 schemas、migration、session、領域交易及 API。第一輪為 54 passed／1 failed（尚未建立前端 JS）；前端檔案加入後 55 passed。
4. 補 8 項回歸測試，抓到原文空白／換行與密碼前後空白被自動裁切。保持測試要求，修改欄位處理後 **63 passed**。
5. 真實 Chromium 測試先抓到「切換到第二目標再升級時，貢獻欄位沒有重建」；修正表單恢復順序，保留所選目標、日期、原文與貢獻。
6. 新增「未保存記錄的導覽保護」紅燈案例，確認當時會直接離開而遺失內容；再實作保存草稿／繼續編輯／明確捨棄流程，維持原測試條件。
7. 真實瀏覽器三條旅程通過，涵蓋功能操作與手機畫面，並檢視桌面／手機截圖。

測試資料修正：一開始引用的 PNG 範例本身有損毀 CRC，改用 Pillow 產生且可驗證的 2×2 PNG 作正常案例；損毀／偽造圖片的拒絕測試仍保留。另將登入按鈕定位限縮到登入表單，避免同文案的背景按鈕造成 Playwright strict-mode 歧義；沒有放寬登入回讀斷言。

## 執行環境與結果

- Python 3.9.6；pytest 8.4.2；FastAPI 0.128.8；SQLite 本機檔案。
- 後端：`.venv/bin/python -m pytest -q`，**63 passed**。
- 瀏覽器：`.venv/bin/python -m pytest browser_tests -q`，**3 passed**。
- 瀏覽器為 Playwright 1.60.0 搭配實際 Chromium；1440×1050 桌面及 390×844 手機尺寸。
- 最後完整輸出見 [TDD_GREEN.txt](TDD_GREEN.txt) 與 [BROWSER_GREEN.txt](BROWSER_GREEN.txt)。

本機 sandbox 最初阻止套件下載、監聽埠號及 Chromium 的 macOS process 啟動；取得執行授權後已實際完成測試，不把被阻止的執行當成通過。

## 需求對照

| 需求 | 測試證據 |
|---|---|
| U-01 首目標與 Lumi 順序 | `test_first_goal_is_mandatory_and_lumi_is_born_after_commit`、瀏覽器 onboarding |
| U-02 人物升級、保留草稿 | `test_guest_person_gate_preserves_draft_and_claim_resumes`、跨目標升級完整旅程 |
| U-03 人工小數累計與去重 | partial／Decimal／revision／相同 key 不同內容／同草稿重送／4 執行緒併發測試 |
| U-04 佐證＋人工確認 | `test_goal_needs_evidence_and_explicit_human_confirmation`、上傳錯誤與跨目標證據、瀏覽器完成成果 |
| U-05 補記與積分 | 真實發生／提交時間分離、2001 年補記、同一請求重送 |
| U-06 人物選填 | guest 無人物確認、無目標經歷、升級後選填人物 |
| 隔離與保存 | 跨 owner 存取、失效 session、登出、資料庫重開、rollback 注入測試 |
| 模擬與真實分開 | 三種私人筆記不改人物統計、經歷、貢獻與積分 |
| 草稿復原 | API revision、瀏覽器刷新、登出登入、導覽前保存 |

## 畫面檢查

- [桌面世界首頁](artifacts/desktop-world.png)
- [手機世界首頁](artifacts/mobile-world.png)

使用真實 browser screenshot 檢查頁面內容、卡片、Lumi 呈現、導覽與表單；手機測試包含 `scrollWidth <= innerWidth`。主流程未捕獲 JavaScript pageerror。

## 驗收界線

以上證明本機 Python MVP 與本輪測試的行為，不代表舊交接包全部 98 案已逐案驗收，也不代表正式雲端認證／PostgreSQL／AI／部署已完成。未做 Safari、實機相機權限、完整無障礙稽核、負載與公開部署測試。

開發用計分、圖片條件、完成後更正等規則詳見 `REQUIREMENTS.md` 與 `ROADMAP.md`。目前不啟用未裁定的負向衰減與主動結束規則。


## Web main部署設定驗收 2026 11 03

本輪獨立工作樹由origin/main 0bf4ce2開工；9項部署契約、Docker內18檔55項React測試、TypeScript／Vite build、nginx -t及9項本機HTTP檢查通過。runtime為UID101，保留私人IAM原則；未執行GCP建置／Push／Deploy或雲端IAM驗證。完整命令與限制見 [Web main交接](../deploy/README.web-main.md)。


## Step 10 4 PG18 與 API 容器驗收 2026 11 03

完整本輪命令、實際通過數與限制見 [工程交接](STEP10_4_PG_API_HANDOFF.md)。新增PG18真實約束／角色／identity、兩個獨立App並行、去重與rollback；容器測試含8080／自訂PORT、health／ready、nonroot及各層秘密排除。既有SQLite歷史資料案例保留。GCP連線、Cloud Build、部署及UI瀏覽器驗收未執行，本輪結果不能作雲端部署成功證據。

## Step 11 API main 整合驗收｜2026-11-03

由最新 main 4b920e8 建立隔離工作樹，保留 Web main 與 Step 10-4 完整工程；本輪 Windows／Linux SQLite 各 231 passed／14 skipped，PG18.6 各 245 passed；API image build、8080／8091 smoke、10,314 layer 檔掃描、3 項 API 建置契約及 9 項 Web main 契約通過。Linux PG 留有 1 個 Pydantic alias warning，未隱藏。完整命令及限制見 [Step 11 交接](STEP11_API_MAIN_INTEGRATION.md)。本輪只建立本機 commit，未發布 GitHub 或操作 GCP；lw_app 正式寫入仍待 DML 審核。

## Step 18 API e2e 準備驗收｜2026-11-03

本輪新工作樹實際 PG18.6＋HTTPS：49 個驗收檢查、9 個退休／main 關閉檢查，以及 SQL 持久化／最小權限／Identity／清理通過；dev 合成指紋不變。完整 SQLite／工具回歸 259 passed／14 skipped，Web 契約 9 tests OK。Google IAM／Cloud Run／Cloud SQL 真實端對端仍待使用者操作，不能用本機 HMAC 模型代替。見 [交付與證據](STEP18_API_E2E_ACCEPTANCE.md)。

## PR #11 快照與 Direct VPC 補正驗收｜2026-11-03

來源批次時間／原始檔 SHA256／Plan 內容指紋及實際 v1 Revision Direct VPC annotations 已加入預檢。功能紅燈34項，修正後工具63 passed、完整回歸294 passed／14 skipped、本機PG18.6 E2E49項、退休清理9項、Web契約9項通過。唯讀匯出文件以本機gcloud替身驗證，未操作GCP；來源新鮮度與外部變更限制見 [補正紀錄](STEP18_API_E2E_ACCEPTANCE.md#pr-11-合併前補正快照來源與-direct-vpc)。

## PR #11 獨立複審修正驗收｜2026-11-03

修正 SQL PASS 誤印、非 superuser DBA 無法執行 dev 探測、權限核對缺口、退休殘留路由、Direct VPC 未知欄位／多容器及 00 接管既有 DB。紅燈 9 failed／65 passed 與 PG18.6 情境紀錄後修正；工具 74 passed、完整回歸 305 passed／14 skipped、PG18.6 模式全套 319 passed、PG18.6＋HTTPS 49 項及退休 9 項、SQL 負向情境、Web 契約 9 tests 通過，未操作 GCP。dev 的 PUBLIC CONNECT／TEMP 是否撤銷待使用者決定。見 [複審紀錄](STEP18_API_E2E_ACCEPTANCE.md#pr-11-獨立複審修正2026-11-03)。

定點修正：03 改為逐表白名單（總數相同的權限互換實測會誤判 PASS），00 分段並以 session 唯讀預設擋住 guard 失敗後的 CREATE DATABASE／標記（實測曾改寫既有未標記 DB）。紅燈 2 failed／74 passed 與 harness 兩處失敗後修正；工具 76 passed、PG18.6＋HTTPS 49 項、退休 9 項、SQL 負向情境通過。

## GCP-143 AI 隔離候選｜2026-11-07

`tests/ai/test_ai_runtime.py` 與既有 `test_model_eval*.py`：30 passed（0.40s）。新案例覆蓋預設停用、registered/CSRF、持久化額度、無效模型 JSON、候選編輯/人工確認、任務重送不重複或發獎勵、來源人物模擬與多模態傳輸契約。使用全新 SQLite＋傳輸替身，真實模型 API／Browser／PostgreSQL 均未驗收；Secret metadata 不等於 key 可用或免費額度。見 [AI 候選與授權條件](ai/GCP143_AI_CANDIDATE.md)。未部署、未修改雲端。

## 2026-11-08｜GCP-144 RC v3（候選，未部署）

修復交付包版本／Patch基準混用，37檔完整Patch與Parent增量各自重建Tree並綁精確Commit。兩次真實Gemini 3.5 Flash-Lite HTTP200（360 input／121 output tokens、費用null），Browser完成編輯／確認／重送／刷新，僅既有合成SQLite；Call2空任務，不將人工任務當AI輸出。完整API424 passed／28 skipped，精確Commit及各類原始日誌以v3 Manifest為準。Owner最新目標為受IAP保護Staging POC，不自行公開或部署。詳見[RC v3驗收](testing/GCP144_RC_ACCEPTANCE.md)。

## 2026-11-08｜公開核心增量（未提交、未部署）

只驗新增變更：API 5 passed（其中1項因收據metadata變更更新）、新Chromium 3 passed（UI2＋API成功hook1）；詳[公開完成矩陣](testing/PUBLIC_RELEASE_MATRIX.md)。Backend／Browser傳輸均明示測試替身，不代表真實劇場AI驗收。RC v3既有測試不重跑、不冒充本輪；新增Gemini呼叫0次，原核准2次已耗盡。圖片及聲音待Owner逐項核准，正式白名單保持空。

### Owner委任採用後的素材整合驗證

對新增整合再做必要驗證，未重跑原RC v3全套：API5 passed、受影響新Chromium3 passed；實際localhost HTTP畫面與8音檔解碼、手機無溢位、三次蛋圖淡入及壞圖fallback通過。3段原創程序BGM已重製並逐檔SHA相符。修正背景被後載CSS覆蓋、訪客按鈕換行及草稿音效應使用`/experiences/drafts`路徑。沒有新真實模型呼叫。

## 2026-11-09 Main 整合 Stage2 隔離回歸

[完整收據與範圍](testing/main-consolidation-stage2-2026-11-09/README.md)：SQLite 512 passed／17 PG-only skipped；隔離PG18.6模式529 passed；Node13 passed；Chromium39案例覆蓋（原跨日skip已補測PASS）；發布政策24 passed；真ffmpeg短／長音訊解碼PASS。僅測試契約／工具／文件變更，沒有更動產品限額或正式流量。Merge仍待CI隔離與Owner明確授權，未Build／部署。

## 2026-11-09｜最新 main 的 pool 清理／shutdown 隔離驗證

基底68102f2；新增18個合成案例，先重現8 failed，再修補為完整530 passed／17 PG skipped。獨立定點重跑18 passed。真PG／Cloud SQL／TLS／瀏覽器未驗。詳見[修補與驗證界線](testing/POOL_SHUTDOWN_REVIEW_20261109.md)。

## 2026-11-09 音訊／孵化生命週期增量

以 main 68102f2 為基準，實際前端 JS 的 Node 22 案：舊版 8 通過／14 失敗，修正後 22 通過；pytest wrapper 2 通過。修復 pending 播放取消、前後景清理、重試／重疊與重複 mount；18 採用素材 hash／FFmpeg 解碼通過。原生瀏覽器與人工聽審未在此版本執行，未部署。[完整範圍與證據](art/AUDIO_LIFECYCLE_20261109.md)。

合流後同版完整回歸：532 passed／17 PG skipped，另24項發布Mock通過；[合流範圍與未驗項](testing/CORE_AUDIO_INTEGRATION_20261109.md)。

## 2026-11-09 隔離 pool 生命週期後續

基於 66fd8d4，4 個新增合成案例先紅後綠；修補 Connector 重複清理、關閉後初始化與開啟後准入檢查。pool 定點 22 passed；完整 pytest 536 passed、17 PG skipped、13 既有 warnings。active borrower 不等待的語義保留，真 PG／Cloud SQL／Windows 未驗。詳見 [pool 審查](testing/POOL_SHUTDOWN_REVIEW_20261109.md)。未推送、部署或修改原工作樹。

同日 provider 責任移交延伸：4 個新增紅燈後，改為最後 opener 接手 Connector 清理，避免 connect/close 重疊且不等待網路。最新 pool 26 passed；完整 540 passed、17 PG skipped、13 既有 warnings（44.67 秒）。前述 536 是中間版本，不是最新候選結果。


### 2026-11-09 整合證據補充（取代上文「最新」的時間性敘述）

完整整合版離線回歸為 **549 passed、17 PG skipped、13 warnings**。上文540屬歷史pool階段結果。OSSANG先前專用PG18執行17必測全通過，但該次整體542 passed、2 failed、13 Node skipped，且早於最後整合；不能當成本head完整Windows回歸。新core在Windows實機記憶體載入的constructor及6個CLI拒絕probe已通過，僅證明fail-closed路徑，不是Windows全功能或ACL驗收。詳見 `CORE_SAFETY_INTEGRATION_20261109.md`（位於 docs/testing）。三線完整驗收仍未完成。

## 2026-11-12 · PR26 Soft Life 視覺候選

見 [視覺候選範圍與本輪結果](SOFTLIFE_VISUAL_CANDIDATE_20261112.md)。初次以 PR26 `804f3f4` 為基準，僅適配視覺與素材。該次 pytest 772 passed／87 skipped；Node 29 passed；CSS／JS 語法檢查通過。瀏覽器因環境 socket 限制未執行，沒有桌面／手機視覺驗收或上線宣稱。後續已獲 PR26 推送授權，接續基準與重跑結果見上方報告；無 merge、deploy、正式 DB 變更。

接續 `846f250d` 保留三個新提交後，Windows 隔離 pytest **779 passed／90 skipped／0 failed**、Node **58 passed**。完整新基準與瀏覽器檢查界線記於上述報告；歷史 772／29 不冒充本輪結果。

接續真實 Chromium 指定防呆 **23 passed**；六頁三寬度及圖片 fallback 共21畫面無水平溢出、pageerrors 0。完整瀏覽器套件、Safari及產品主觀驗收仍未完成。

## 2026-11-12 · main 發布測試 Step 3 修正（1a02a82）與開放人物 AI 模擬

依據：Cloud Build `3be00bba-539c-41fc-ad76-0869e1e64744`（`1a02a82`）Step 3 SQLite 輪 2 failed／785 passed／114 skipped／1 xfailed，PostgreSQL 輪沒有執行。修正內容見 [EVOLUTION](EVOLUTION.md) 同日條目。

本機環境：Python 3.12.15＋`requirements.api-test.lock`（61 套件逐一相同）；Node 24.20.0（本機）；Cloud Build 會用固定的 24.22.2。PostgreSQL 18.6 可攜版、cluster_name 與 Cloud Build 相同、`scripts/pg_test_bootstrap.py` 初始化。對照組是 main `da161c3` 原樣。

| 項目 | 修正後 | main 原樣 |
|---|---|---|
| 兩項原失敗分別執行 | 各 1 passed | 各 1 failed（KeyError `LIFEWORLD_NODE`；422 `simulation_not_released`） |
| Step 1 發布安全測試（`deploy/tests/test_release.py`） | 24 OK | — |
| 建置設定測試（`tests/test_api_build_config.py`＋`deploy/tests/test_web_main.py`） | 14 passed；新增兩項修正前 failed | — |
| 模擬／撤回來源／前端相關（5 個檔） | 32 passed；撤回來源兩項在拿掉過濾後 failed（突變檢查） | — |
| 完整 SQLite（`pytest tests`，有 Node） | **806 passed／0 failed**／99 skipped／1 xfailed | 801 passed／1 failed／99 skipped／1 xfailed |
| 完整 PostgreSQL（`LIFEWORLD_TEST_BACKEND=postgresql`） | 707 passed／**116 failed**／82 skipped／1 xfailed | 702 passed／117 failed／82 skipped／1 xfailed |

PostgreSQL 輪的 116 項失敗在 main 原樣上同樣存在（差異只有已修正的模擬測試），不是本次修改造成；Cloud Build 過去因 SQLite 輪先失敗而沒有跑到。主因是 `scripts/pg_test_bootstrap.py` 只建立 STEP10 核心草稿結構，程式需要的 010／011 資料表（`person_basic_details`、`person_employments`、`data_consents`、`subject_experiences`、`relationship_memory_preferences` 等）不存在。這一輪**沒有修正**，Cloud Build 的測試資料庫要套用哪些 migration 待決定。

NOT RUN：Cloud Build 重新建置（觸發條件只有推到 main）、Cloud Run 發布（唯讀預檢目前回 `RELEASE_BLOCKED: API runtime differs from production`）、真實模型呼叫。

## 2026-11-12 · Step 3 PostgreSQL 測試庫改用 alpha 結構（010＋011）

依《表規格與擬真資料交接》v1.1：e2e／alpha 同一套 010（42 表），011 是生日／任職四表；`relationship_features`、`relationship_memory_preferences` 這一輪 PostgreSQL 不建。Step 3 的合成 PostgreSQL 改由 alpha 010 唯讀結構快照建表，套 011 審查稿（只去掉環境關卡），Runtime 權限鏡像 alpha 的 `lw_alpha_app`，011 四表沿用 e2e 已執行的最小權限，另列一項 alpha 待套用權限（刪除已存草稿）。PostgreSQL 測試使用 `link_table`。

剩下 17 項依 Jerry 核准的建議處理：只能在 SQLite 執行的寫法改成兩種資料庫都能跑（3）、改用欄名讀資料列（4）、目錄檢查改核對 alpha 010＋011（1）、JSON 欄位改比對內容（2）、關係記憶在 PostgreSQL 改驗證功能關閉且不寫入（5）、刪除草稿依 alpha 待套用權限驗證（2）。

| 項目（本機 PostgreSQL 18.6、Python 3.12.15、Node 24.20.0） | 結果 |
|---|---|
| 完整 PostgreSQL | **826 passed／0 failed**／82 skipped／1 xfailed（改前 116 failed） |
| 完整 SQLite | **809 passed／0 failed**／99 skipped／1 xfailed |
| 測試庫結構與權限（`tests/test_pg_test_schema.py`） | 3 passed；實作前 3 failed |

NOT RUN：Cloud Build、Cloud Run 部署、真實 alpha 的 011 與權限套用。
