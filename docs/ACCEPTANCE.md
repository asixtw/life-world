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

## 2026-11-09 MVP M0：部署設定檔 core-e2e（未提交、未部署）

命令：`python -m pytest -q -p no:cacheprovider tests --ignore=tests/product/test_google_verifier.py --ignore=tests/product/test_staging_iap_config.py`（本機沿用的 Python 環境缺 `google-auth`、`cryptography`，這兩個檔案無法收集）。修改前：476 passed、12 failed、17 skipped、12 errors；修改後：548 passed（新增72）、12 failed、17 skipped、12 errors，失敗與錯誤清單與修改前逐項相同（皆為既有環境問題，與本變更無關）。新增測試以替身連線驗證拒絕條件，另在暫存副本把 `app/main.py` 換回原版，確認13項 `create_app` 案例會失敗。沒有連任何真實資料庫、沒有建置映像、沒有部署；E2E 連線**尚未驗證**。

## 2026-11-09 MVP M0：Codex 審查後的最小修正（未提交、未部署）

同一命令與排除條件：修改後 604 passed（M0 新增測試共128項）、12 failed、17 skipped、12 errors；失敗與錯誤清單與修改前基線逐項相同（google 18、cp950 5、chmod 1）。M0 測試另含以本機 Git Bash 模擬 Cloud Build 替換值的負向案例（命令替換、引號、換行、空白、非法名稱、重複 tag），沒有執行 Cloud Build。8030 本機腳本另有42項替身程序與合成資料測試（工作樹外）。E2E 連線、Docker 建置與 Cloud Run 啟動仍**尚未驗證**。

## 2026-11-09 MVP M0：Codex 第二輪審查後的最小修正 V3（未提交、未部署）

同一命令與排除條件：修改後 644 passed（M0 測試共168項：設定檔128、建置設定36、來源白名單4）、12 failed、17 skipped、12 errors；失敗與錯誤清單與修改前基線逐項相同（google 18、cp950 5、chmod 1）。新增的負向案例：autocommit 設定靜默無效或拋錯時身分查詢次數為 0（啟動與重新連線）；任何大小寫的 HTTP／HTTPS／ALL／NO_PROXY 與空值 ADC 覆寫都拒絕；Cloud Build 以本機 Git Bash 與替身 gcloud／docker 模擬：同一秒相同來源的兩次建置 tag 不同、認證錯誤含 not found 不被當成成功、權限不足、讀取來源物件失敗（即使替換值是空輸入的 SHA-256）、封裝被修改、來源 bucket 不符、provenance 使用這次 push 的 digest。設定審查環境常見的 `CLOUDSDK_CONFIG` 與代理變數時，M0 測試同樣全數通過。沒有執行 Cloud Build、沒有建置映像。8030 本機腳本另有123項替身程序與合成資料測試（工作樹外）。E2E 連線、Docker 建置與 Cloud Run 啟動仍**尚未驗證**。

## 2026-11-10 MVP M0：Codex 第三輪審查後的最小修正 V4（未提交、未部署）

同一命令與排除條件：修改後 658 passed（M0 測試共183項：設定檔134、建置設定45、來源白名單4）、13 failed、17 skipped、12 errors。其中 24 項與修改前基線逐項相同（google 18、cp950 5、chmod 1）；多出的 1 項 `tests/test_public_release_acceptance.py::test_public_password_core_journey_and_owner_isolation` 是時段相依：執行時是台北時間 00 點多，測試建立「今天 09:00（+08:00）」的經歷被判為未來（`future_event`，422）。只把服務時鐘固定在同日台北 10:00 重跑即通過，該測試只使用 SQLite，與本次修改無關。新增的負向案例：基底 `_open` 第一次設定 autocommit 靜默無效時不送出任何 SQL（啟動與 pool 用盡後重連）；`docker inspect` 印出正確 digest 但以 42 結束、沒有輸出、錯誤 digest、多個 digest 都不輸出 provenance；`find`／`sort` 失敗時 validate-target 停止。設定審查環境常見的 `CLOUDSDK_CONFIG` 與代理變數時，M0 測試同樣全數通過。8030 本機腳本另有182項替身程序與合成資料測試（工作樹外）。沒有執行 Cloud Build；E2E 連線、Docker 建置與 Cloud Run 啟動仍**尚未驗證**。

## 2026-11-10 MVP M0：Codex 第四輪審查後的最小修正 V5（未提交、未部署）

同一命令與排除條件：修改後 675 passed（M0 測試共200項：設定檔151、建置設定45、來源白名單4）、13 failed、17 skipped、12 errors。扣除已知的時段相依案例 `tests/test_public_release_acceptance.py::test_public_password_core_journey_and_owner_isolation`（執行時台北時間 01:36，建立「今天 09:00」的經歷被判為未來；只固定服務時鐘在同日 10:00 重跑即通過，與 M0 無關）之後，其餘 24 項與修改前基線逐項相同（排序清單 SHA-256 `145753f8b53e018b73a470987b3626242b939edbe0803e34cfe73330e5361a59`）。新增的負向案例：交易狀態屬性缺少、讀取失敗、None、0、空字串、字串 False、1 時，啟動與 pool 用盡後重連都在第一個 SQL 之前關閉；鎖定的 pg8000 1.31.6 對 I／T／E 狀態回報 bool False／True／True。設定審查環境常見的 `CLOUDSDK_CONFIG` 與代理變數時，M0 測試同樣全數通過。8030 本機腳本另有202項替身程序與合成資料測試（工作樹外）。沒有執行 Cloud Build、沒有上傳；E2E 連線、Docker 建置與 Cloud Run 啟動仍**尚未驗證**。

## 2026-11-10 MVP M0：Codex 第五輪審查後的最小修正 V6（未提交、未部署）

本輪 B 的程式與測試都沒有修改。同一命令與排除條件：675 passed（M0 測試 200 項）、13 failed、17 skipped、12 errors；扣除已知的時段相依案例（執行時台北時間 02:06；固定服務時鐘在同日 10:00 重跑即通過）之後，其餘 24 項與修改前基線逐項相同（排序清單 SHA-256 `145753f8b53e018b73a470987b3626242b939edbe0803e34cfe73330e5361a59`）。8030 本機腳本有 231 項替身程序與合成資料測試（工作樹外）。沒有執行 Cloud Build；E2E 連線、Docker 建置與 Cloud Run 啟動仍**尚未驗證**。

## 2026-11-11 Unified Person 階段

正式驗收（PostgreSQL）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11111143`）→ Cloud SQL `life_world_e2e`，全部使用 `persons_ui_` 開頭的合成帳號。API：`tests/test_persons_cloudsql_e2e.py`、`test_person_relations_cloudsql_e2e.py`、`test_relation_sources_cloudsql_e2e.py`、`test_person_experiences_cloudsql_e2e.py`、`test_person_experiences_records_cloudsql_e2e.py` 共 7 passed、1 skipped（略過的是關係來源的舊正向案例，已由人物經歷與紀錄頁兩個測試涵蓋），共 428 個 HTTP 請求。Chrome：`browser_tests/test_persons_ui.py`、`test_persons_relations_ui.py`、`test_persons_navigation_ui.py`、`test_persons_experiences_ui.py`、`test_records_page_ui.py` 共 5 passed。這一輪沒有重跑 `test_person_profile_ai_cloudsql_e2e.py`（會呼叫付費的 AI 服務；AI 模組在這一輪沒有修改）。

本機輔助檢查（SQLite，不算驗收）：`python -m pytest -q -p no:cacheprovider tests --ignore=tests/product/test_google_verifier.py --ignore=tests/product/test_staging_iap_config.py`，901 passed、7 failed、26 skipped、12 errors。失敗與錯誤清單和這個階段開始前相同，都不在人物功能內：`tests/product/test_google_exchange.py` 11 項與 `tests/product/test_gcp139_return.py` 1 項（errors，本機環境缺 Google 驗證套件）、`tests/test_provider_independent_login.py` 3 項、`tests/test_staging_tag_origin.py` 3 項、`tests/test_model_eval.py` 1 項。執行全套請用 `PYTHONUTF8=1`，不要用 `PYTHONIOENCODING`。

## 2026-11-11 Unified Person 第二輪

正式驗收（PostgreSQL）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11111215`）→ Cloud SQL `life_world_e2e`，全部使用 `persons_ui_` 開頭的合成帳號。API：上一節的五個檔案加上新增的 `tests/test_self_persona_cloudsql_e2e.py`（我的人設的建立、讀回、改版保留舊版、Revision 檢查、重送、同意與撤回、Owner 隔離），共 8 passed、1 skipped（略過的仍是關係來源的舊正向案例），455 個 HTTP 請求。Chrome：上一節的五個檔案加上新增的 `browser_tests/test_self_persona_entry_ui.py`（導覽只有五項、我的紀錄上方的人設卡片、建立、再編輯成第 2 版、同意、重新整理後仍在），共 6 passed。沒有重跑 `test_person_profile_ai_cloudsql_e2e.py`（會呼叫付費的 AI 服務；這一輪沒有修改後端）。沒有執行舊的瀏覽器測試 `test_character_cards_ui.py`、`test_connections.py`、`test_people.py`（它們靠點擊導覽的「關係」「角色」進入，在人物系統啟用的環境要先改成由網址進入）。

使用者的 E2E 帳號：SQL 批次 `orig15-v2-20261111` 執行後，以該帳號經 API 逐位讀回，15 位人物都是第 2 版人物設定、9／9 欄，原有的備註保留，人物經歷 16 筆。之後以同帳號經 API 新增 4 筆多人參與的範例人物經歷與 6 筆範例關係（都回 201），並在 App 內瀏覽器確認人物頁的關係與經歷頁籤、紀錄頁的人物經歷（20 筆）、我的紀錄上方的人設卡片與人設頁都正確顯示。

本機輔助檢查（SQLite，不算驗收）：`python -m pytest -q -p no:cacheprovider tests --ignore=tests/product/test_google_verifier.py --ignore=tests/product/test_staging_iap_config.py`，903 passed、7 failed、27 skipped、12 errors；失敗與錯誤清單和上一節逐項相同。上一節的命令漏寫了這兩個排除參數（本機缺 Google 驗證套件，這兩個檔案無法收集），已補上。

## 2026-11-11 Unified Person 第三輪

正式驗收（PostgreSQL）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11111349`）→ Cloud SQL `life_world_e2e`，全部使用 `persons_ui_` 開頭的合成帳號。API：和第二輪相同的六個檔案，共 8 passed、1 skipped（略過的仍是關係來源的舊正向案例），455 個 HTTP 請求。Chrome：六個檔案，共 6 passed；其中 `browser_tests/test_self_persona_entry_ui.py` 依新流程重寫（導覽五項 → 人物首頁最上方的我的設定 → 建立 → 回人物首頁看到摘要 → 從帳號視窗再進去存成第 2 版並同意 → 紀錄的第一個頁籤是我的經歷、上面沒有我的設定 → 記下經歷時「關聯人物」與「整理這段故事的人物」只列真實人物 → 重新整理後仍在）。沒有重跑 AI 的雲端測試，也沒有執行舊的瀏覽器測試（原因同第二輪）。

使用者的 E2E 帳號（在 App 內瀏覽器實際操作）：從人物首頁的「建立我的設定」填寫十二欄並保存成第 1 版；從右上角帳號視窗的「我的設定」可以進到同一頁；從「紀錄 → 我的經歷 → ＋ 新的經歷」記下一筆，經過核對頁確認保存，回到我的經歷看到這一筆，積分加 1、目標的每日閱讀變成 1／1。之後以同帳號經 API 新增 1 位範例真實人物與 2 筆範例經歷（都回 201）。

本機輔助檢查（SQLite，不算驗收）：同第二輪的命令，906 passed、7 failed、27 skipped、12 errors；失敗與錯誤清單和第二輪逐項相同。

## 2026-11-11 Unified Person 第四輪（依獨立驗收修正）

正式驗收（PostgreSQL）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11111459`）→ Cloud SQL `life_world_e2e`，全部使用 `persons_ui_` 開頭的合成帳號。

API：七個檔案共 10 passed、1 skipped（略過的仍是關係來源的舊正向案例），530 個 HTTP 請求。新增 `tests/test_integrity_guards_cloudsql_e2e.py` 兩項：
- 我的經歷只接受使用中的真實人物：歷史人物、虛構人物在草稿建立被拒（直接打 API）；名單混入一位虛構人物整筆拒絕；草稿不能改成歷史人物；確認時改送虛構人物、名單混入虛構人物、人物在草稿之後被封存都被拒；以上都不產生草稿、經歷、積分或目標進度。真實人物與沒有關聯人物的照常確認並得到積分；同一請求重送回原結果。
- 關係來源不會失效：移除非必要的參與者照常；移除最後一位相關的人回 409，經歷、關係、來源都不變，重送結果相同；換成不相關的人也回 409；Revision 與 Owner 隔離維持；主體不能改；先調整關係來源再修改就成功，成功的請求重送回原結果；仍被引用時不能封存，移除來源後可以；我的經歷當來源時，更正故事參與人物同樣被擋下。

Chrome：六個檔案共 6 passed。這一輪新增的步驟：記下經歷時繞過選擇器直接打 API，歷史人物與虛構人物都被後端拒絕，沒有草稿、積分不變；被關係引用的人物經歷按「封存」會顯示原因，經歷仍在。因為我的經歷不能再關聯歷史人物，原本把我的經歷關聯到歷史人物「周瑜」的測試資料改成真實人物。

本機輔助檢查（SQLite，不算驗收）：同第二輪的命令，915 passed、7 failed、29 skipped、12 errors；失敗與錯誤清單和第二輪逐項相同。新增 `tests/test_integrity_guards.py` 9 項；把後端還原成修正前的版本時，其中 7 項失敗，確認測試確實在驗這兩項修正。

使用者的 E2E 帳號 15 位人物的第 3 版在 SQL 批次執行後另外核對，見下一節。沒有重跑 AI 的雲端測試，也沒有執行舊的瀏覽器測試（原因同第二輪）。

## 2026-11-11 Unified Person 第四輪：第 3 版人物設定執行後核對

SQL 批次由 Jerry 在 Cloud SQL Studio 執行後，以使用者的 E2E 帳號登入 8030，用正式 API（`GET /api/persons`、`GET /api/persons/{id}`）逐位讀回 15 位人物：最新版都是第 3 版、9／9 欄，版本識別碼與交付的第 3 版資料逐位相同，九欄內容的 SHA-256 逐位相同；原有人物備註的雜湊與匯入前備份相同（沒有變動），人物版本號仍是 2。在 App 內瀏覽器逐位開啟 15 位的人物設定頁籤，都顯示「第 3 版」與 A～E 五個區塊，畫面文字裡找不到本場、初始狀態、可變狀態、關係進程、Lumi、快取、生成前、交付前、本卡、每輪、跨場、回寫等用語；另抽查三位人物（三個組別各一位）的性格與行為欄內容。

## 2026-11-11 作品開發前的資料檢查（使用者的 E2E 帳號）

不是功能驗收，沒有改程式、沒有部署、沒有呼叫模型。用使用者的 E2E 帳號登入 8030，以正式 API 讀回人物、人物設定、我的設定、角色卡、人物經歷、作品中心與生成狀態，再透過同一組 API 補了三處資料：我的設定另存第 2 版（拿掉每欄開頭的範例標記，其他內容不變）；範例真實人物補上身分、共同場合與人物設定第 1 版；四筆範例人物經歷的標題補上「（範例）」。補完後重新讀回：16 位人物都有正式人物設定且九欄都有內容，我的設定第 2 版十二欄都有內容、沒有標記，人物關係 6 筆與來源都還在；在畫面上看過我的設定頁（顯示第 2 版）與建立作品頁（人物清單仍只列角色卡）。結果表與沒有處理的項目寫在 `docs/UNIFIED_PERSON_HANDOVER.md` 第 7 節。

## 2026-11-11 作品可以選人物

正式驗收（PostgreSQL）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11111823`）→ Cloud SQL `life_world_e2e`，全部使用 `persons_ui_` 開頭的合成帳號。這個環境的生成服務是真實模型，這一輪沒有呼叫模型，也沒有建立任何作品。

API（`LW_E2E_PERSONS=1 python -m pytest -q tests/test_person_source_cloudsql_e2e.py`）：新測試 1 passed、1 skipped（略過的是會呼叫真實模型的案例）；連同既有七個檔案一起重跑共 11 passed、2 skipped。驗收內容：可選人物清單只列本人使用中的人物，有正式人物設定的附識別碼與版號，沒有回執的同格式筆記不算，另一個帳號看不到；沒有人物設定、已封存、別人的人物、畫面讀到的不是最新版、同一位重複、名單混入一位不合規，都在建立前被拒絕；人物合格但「包含我」沒有我的設定時也被拒絕（這一步讓人物來源的讀取與鎖定在 PostgreSQL 上完整執行）；以上都沒有建立作品，人物與人物設定沒有變動。會真的開始生成的案例（`LW_E2E_LIVE_GENERATION=1`）沒有執行。

Chrome（`LW_E2E_PERSONS_UI=1 python -m pytest -q browser_tests/test_creation_people_ui.py`）：新測試 1 passed；連同既有五個不呼叫模型的畫面測試一起重跑共 6 passed（會用 AI 產生人物設定的 test_persons_ui.py 這一輪沒有跑）。驗收內容：作品 → ＋ 建立新作品；① 人物先列人物，標出類型與人物設定版本；沒有人物設定的人物不能勾並指向人物頁；搜尋人物；勾選兩位並取消「包含我」後顯示多人文字；人物可以設角色定位；填場景後「開始生成」可以按（沒有按）；重新整理後草稿還在；繞過畫面直接送出沒有人物設定的人物，後端回 409，沒有建立作品。

送給模型的內容在這個環境看不到，由程式自帶的自動測試驗證（擷取型假模型，不連網、不計費；`tests/test_person_source_generation.py` 7 項、`tests/test_creation_people_picker_view.py` 4 項）：規劃只有公開簡介；人物發言時送出鎖定版本的九欄；我發言時送我的設定；雙方私有內容互不可見；同名舊角色卡與無回執筆記沒有混入；開始後才存的新版本不被進行中的作品使用；鎖定的版本被改動或失去回執就停止並保留已生成的段落；封存人物不停止進行中的作品但不能再加入新作品；人物與角色卡可以混用；生成前後人物、人物設定、我的設定、同意、我的經歷與積分都不變。後端的 7 項裡有 6 項是先寫的，在修改前的後端上執行過，全部失敗；封存人物那一項是實作後補的。

整套自動測試（同第二輪的命令）：926 passed、7 failed、31 skipped、12 errors（比上一輪多 2 項略過，是新的 Cloud SQL 測試檔，沒有開啟時不執行）；失敗與錯誤清單和修改前逐項相同（比修改前多通過的 11 項就是上面兩個檔案）。

還沒有驗收的部分：沒有用真實模型生成過任何引用人物的作品，所以「鎖定版本逐段讀取」在 PostgreSQL 上、背景排程、作品頁逐段顯示與完成狀態，都還沒有實際跑過。

## 2026-11-11 作品下載成離線 HTML（第 1 級：純文字）

正式驗收（PostgreSQL 與 Cloud Storage）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11112328`）→ Cloud SQL `life_world_e2e`、bucket `lw-works-e2e-513506`，使用 `persons_ui_` 開頭的合成帳號。

API（`LW_E2E_PERSONS=1 python -m pytest -q tests/test_work_export_cloudsql_e2e.py`）：1 passed、1 skipped（略過的是會真的生成作品的案例）。確認匯出功能在 e2e 已開放（部署的 bucket 設定和環境白名單一致）；不存在的作品與角色卡都被拒絕，沒有留下匯出紀錄。連同既有的八個檔案一起重跑共 12 passed、3 skipped。真正的匯出與下載需要一件已完成的作品，也就是一次真實模型生成；使用者同意後另外執行，結果見下一節。另外以本機登入者的身分（不是服務帳號）對 bucket 實測過程式的呼叫方式：寫入、重複寫入（回已存在、不覆寫）、讀回、讀不存在的物件，結果都符合設計；測試物件已刪除。

Chrome：`browser_tests/test_work_export_ui.py`（生成一件作品、下載、離線開啟）需要真實模型，使用者同意後另外執行，結果見下一節。既有六個不呼叫模型的畫面測試加上離線開啟的兩項一起重跑，共 8 passed、1 skipped。

程式自帶的自動測試（假模型與記憶體儲存，不連網、不計費）：`tests/test_work_export.py` 7 項、`tests/test_object_storage.py` 12 項、`tests/test_run_export_view.py` 3 項。驗證內容：已完成的作品匯出成單一 HTML，存放的、下載的逐位元相同；不引用外部資源，內嵌樣式與程式由 CSP 雜湊鎖定；標題與場景裡的標籤符號被跳脫，嵌入的劇情資料不會提早結束區塊；檔案裡沒有人物設定、我的設定、公開簡介、演出要求與場景條件；相同內容只存一份、只記一筆，同一提交代碼重送回原結果；未完成的作品、角色卡、別人的作品、不存在的版本都被拒絕；檔案遺失或被改動時拒絕下載，重新匯出會補寫；沒有設定儲存時功能關閉；匯出前後作品、段落、生成紀錄與作品列表都不變。儲存模組：寫入帶「不存在才建立」的條件、已存在視為已寫入、物件名稱只接受安全路徑、bucket 必須是環境白名單登記的那一個。這些測試都是先寫的，在功能實作前執行過並失敗。

離線開啟（`python -m pytest -q browser_tests/test_export_reader_offline.py`，本機 Chrome、完全離線、不需要 8030）：2 passed。劇本對白與小說敘事各一次：內容直接顯示、閱讀器程式有執行、沒有任何連線與主控台錯誤、標籤符號照原樣顯示成文字、字級／深淺色／場景提示可以切換而且重新開啟後記得。

整套自動測試（同第二輪的命令）：948 passed、7 failed、31 skipped、12 errors；失敗與錯誤清單和修改前逐項相同（多通過的 22 項就是上面三個檔案）。

## 2026-11-11 作品下載成離線 HTML：真實模型驗收

使用者同意後，以 `persons_ui_` 開頭的合成帳號各生成一件作品（一位人物、單人文字、短篇），模型是 `gemini-3.5-flash-lite`。對象同上一節（revision `lw-api-main-b8030-11112328`）。這是第一次在雲端實際跑完「選人物 → 背景逐段生成 → 完成 → 匯出 → 下載」。

API（`LW_E2E_PERSONS=1 LW_E2E_LIVE_GENERATION=1 python -m pytest -q tests/test_work_export_cloudsql_e2e.py`）：2 passed，約 8 分 20 秒。生成中匯出被拒絕（409）；完成後匯出成功，從 Cloud Storage 讀回的檔案大小與雜湊和紀錄一致，以附件回傳並帶 sandbox；檔案不引用外部資源，包含每一段的台詞、動作與場景提示，不含人物設定；再匯出一次與同一提交代碼重送都回同一筆；另一個帳號讀不到清單也下載不到；匯出前後作品詳情相同；作品中心仍是 1 件。

Chrome（`LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 python -m pytest -q browser_tests/test_work_export_ui.py`）：1 passed，約 5 分鐘。在畫面上建立作品並開始生成，生成中沒有下載按鈕；完成後出現「下載 HTML」；按下後瀏覽器收到以作品標題命名的 .html 檔；用完全離線的瀏覽環境開啟，看得到標題、人物與每一段，閱讀器工具列出現，沒有任何連線與主控台錯誤；作品頁顯示上次匯出；重新整理後再下載一次，檔案內容相同。

佐證：bucket `lw-works-e2e-513506` 裡有 2 個物件（15,091 與 16,507 位元組），都是服務帳號寫入的，路徑是 `works/{擁有者}/{作品}/{內容雜湊}.html`；Chrome 那件下載了兩次，只存了一份。畫面與實際下載到的檔案在倉庫外的 `alpha-unification-20261110/works_html_export_evidence/`。

用量（取自 Cloud Run 的診斷紀錄，不含內容）：兩件作品共 29 次模型呼叫，18 次成功（每件 1 次規劃＋8 段），11 次失敗後自動重試（8 次是 Gemini 回 503、3 次逾時）。成功的呼叫共輸入 25,022 tokens、輸出（含思考）4,319 tokens，依部署設定的費率估計約 US$0.018；失敗的呼叫沒有回報用量。

觀察到但沒有處理的事：

- Gemini 在這段時間頻繁回 503。引擎延後重試後都完成了，沒有人工介入，但一件 8 段的作品因此花了 5 到 8 分鐘。
- 生成的台詞幾乎每一段都重複人物設定裡的口頭禪。驗收用的人物設定只有四欄、很短；內容品質這一輪沒有評估。

還沒有驗收的部分：含「我」的多人作品、使用者的 E2E 帳號的第一個作品、生成失敗後的恢復、中篇與長篇。

## 2026-11-12 多章節作品（第 2 級）

正式驗收（PostgreSQL 與 Cloud Storage）：Local 8030 → Cloud Run `lw-api-main` e2e 標籤（revision `lw-api-main-b8030-11120013`）→ Cloud SQL `life_world_e2e`，使用 `persons_ui_` 開頭的合成帳號。

API（`LW_E2E_PERSONS=1 python -m pytest -q tests/test_story_series_cloudsql_e2e.py`）：1 passed、1 skipped（略過的是會真的生成兩章的案例）。端點已上線；不存在的作品、角色卡、不存在的多章節作品都被拒絕，沒有留下任何作品。連同既有的九個檔案一起重跑共 13 passed、4 skipped。真正的續寫、採納與合集匯出需要已完成的作品，也就是真實模型生成，這一輪還沒有做。

Chrome：`browser_tests/test_story_series_ui.py`（生成兩章、採納、下載整部作品、離線開啟）沒有執行，因為需要真實模型。既有六個不呼叫模型的畫面測試加上離線開啟的三項一起重跑，共 9 passed、2 skipped。

程式自帶的自動測試（擷取型假模型與記憶體儲存，不連網、不計費）：`tests/test_story_series.py` 5 項、`tests/test_series_view.py` 4 項，另外更新了 `tests/test_work_export.py` 與離線開啟的測試以配合閱讀器升版。驗證內容：已完成的作品成為第 1 章，未完成的、角色卡、別人的作品都被拒絕，同一件作品只會開出一部；續寫時規劃收到前面各章的大綱與上一章最後 6 段，人物發言時收到自己前一章的記憶與最後的狀態，收不到別人的記憶，人物設定照常鎖定並送出；不是續寫的一般作品沒有這些內容；生成紀錄的提示詞版本是 v4；草稿不影響主線，未完成的草稿不能採納，採納後主線往前、接在舊進度上的草稿回 409，捨棄的草稿不再列出，第三章看得到前兩章的大綱且記憶逐章累積；合集匯出有目錄、只包含已採納的章節，未採納草稿的內容不在檔案裡，單一作品沒有目錄；擁有者隔離；續寫前後人物、人物設定、我的設定、同意、我的經歷與積分都不變。後端 5 項是先寫的，在功能實作前執行過並失敗。

離線開啟（`python -m pytest -q browser_tests/test_export_reader_offline.py`，本機 Chrome、完全離線）：3 passed。新增的一項確認三章的合集有目錄，點章名會跳到那一章。

整套自動測試（同第二輪的命令）：956 passed、8 failed、33 skipped、12 errors。失敗的 8 項裡 7 項和修改前相同；另一項 `tests/test_public_release_acceptance.py::test_public_password_core_journey_and_owner_isolation` 會在台北時間 0 點到 9 點之間失敗（它送出「今天 09:00」的經歷，被當成未來時間），這次剛好在凌晨執行；用上一次推送的版本 `39ad50a` 在同一時間單獨執行同樣失敗，和這一輪無關。

## 2026-11-12 多章節作品：真實模型驗收（API 通過；Chrome 發現並修正一個頁面問題，尚未重跑）

使用者同意後，以 `persons_ui_` 開頭的合成帳號執行，模型是 `gemini-3.5-flash-lite`。

API（`LW_E2E_PERSONS=1 LW_E2E_LIVE_GENERATION=1 python -m pytest -q tests/test_story_series_cloudsql_e2e.py`，revision `lw-api-main-b8030-11120013`）：2 passed，約 6 分鐘。生成第 1 章 → 開成多章節作品 → 續寫第 2 章 → 草稿不影響主線、未完成不能採納 → 草稿開始時鎖定的繼承內容和第 1 章實際保存的內容一致（大綱、最後 6 段、人物的狀態與記憶）→ 完成後採納，主線成為兩章 → 再採納一次回 409 → 合集匯出有目錄、段數等於兩章相加、不含人物設定，從 Cloud Storage 讀回的檔案和紀錄一致 → 另一個帳號讀不到 → 人物與人物設定沒有變動 → 作品中心是兩章加一部多章節作品。

Chrome（`browser_tests/test_story_series_ui.py`）：1 failed，停在第 1 步。後端沒有問題，那件作品 6 分鐘內完整生成（8 段）；失敗的是作品頁：讀取進度時有一次請求拿到空白回應，頁面顯示「Failed to execute 'json' on 'Response'」之後就不再更新，一直停在「5/8 段」。這是既有的頁面行為（讀不到一次就停止），被較長的真實生成暴露出來。已修正並部署（revision `lw-api-main-b8030-11120046`）：背景生成時讀不到進度會說明「暫時讀不到進度，稍後自動重試」並繼續讀，間隔逐次拉長；回應不是 JSON 時顯示「伺服器暫時沒有回應」而不是解析錯誤。新增 `tests/test_run_polling_view.py` 2 項（修正前第 1 項失敗）。**Chrome 的續寫、採納、整部下載在雲端還沒有跑過**，要等重跑。

用量（取自 Cloud Run 的診斷紀錄）：API 驗收 18 次呼叫（13 成功、5 失敗），估計 US$0.015；Chrome 那次 15 次呼叫（9 成功、6 失敗），估計 US$0.009。

觀察到但沒有處理的事：每日金額上限是用預留計算的，失敗而沒有回報用量的呼叫（Gemini 503、逾時）每次佔住 US$0.50、24 小時後才釋放。這一晚每成功一次約有 0.55 次失敗；過去 24 小時實際費用約 US$0.07，佔住的預留卻有 US$12，上限 US$19 只剩約 13 次失敗的空間。照這個失敗率，一天大約生成 4 到 5 件短篇就會被暫停。要不要讓「供應商明確拒絕、沒有用量」的呼叫不佔預留，需要使用者決定。

整套自動測試（修正後重跑）：958 passed、8 failed、35 skipped、12 errors；失敗與錯誤清單和修正前那一次相同（7 項既有的，加上凌晨會失敗的 `test_public_release_acceptance` 那一項）。

## 2026-11-12 預留規則調整、人物個性的表現（提示詞 v5）、多章節作品 Chrome 驗收重跑

使用者的兩項指示：先調整每日金額上限的預留規則再重跑驗收；生成的作品看不出人物的個性與差異。

**預留規則。** 供應商明確拒絕（HTTP 429、503）而且沒有回報用量的呼叫，預留全數退回、生成紀錄的費用記為 0；逾時、連線中斷與其他錯誤（含 500）維持原樣，預留保留 24 小時。新增 `tests/test_budget_release_on_rejection.py` 6 項：429／503 退回且重送不重複退回、500 與沒有狀態碼的失敗照舊保留、排程生成連續 6 次 503 之後仍然完成（每日上限只夠 3 次預留）、429 被分類成額度不足時一樣退回。實作前執行：4 failed, 2 passed（兩項「照舊保留」本來就成立）。

**人物個性的表現。** 檢視 2026-11-11 真實模型生成的那件作品，找到三個原因：規劃把「誰做什麼」寫進節拍，人物只能照做；逐段的提示只說「依照人格演出」；設定裡的口頭禪每一段都出現、每一段都描寫光線。提示詞升到 `roleplay-plan-v5`／`roleplay-segment-v5`（規則見 `docs/UNIFIED_PERSON_HANDOVER.md` 第 4 節「人物個性的表現」），v2 到 v4 原封保留。新增 `tests/test_persona_expression_prompt.py` 5 項：新作品用 v5、舊版本的雜湊不變、規劃仍然只看公開簡介、發言的人看不到別人的九欄、三種來源（人物、角色卡、我）送出的每一個人物欄位在提示裡都有說明、關鍵規則確實在送出的提示裡。實作前執行：5 failed。提示詞寫得好不好，自動測試判斷不了，只能看真實模型的結果（見下）。

整套自動測試：971 passed、8 failed、35 skipped、12 errors（207 秒）。失敗與錯誤的清單和修改前相同：7 項既有失敗、12 項缺少 Google 驗證套件的錯誤，以及 `tests/test_public_release_acceptance.py::test_public_password_core_journey_and_owner_isolation`（台北時間 0 到 9 點會失敗，未修改的基準也一樣）。比上一輪多 13 項通過，都是這一輪新增的測試。

**Chrome 真實模型驗收（重跑）。** `LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 python -m pytest -q browser_tests/test_story_series_ui.py`，revision `lw-api-main-b8030-11120112`，`persons_ui_` 開頭的合成帳號，模型 `gemini-3.5-flash-lite`。這次改用兩位九欄都填、個性相反的合成人物（慢而仔細的模型製作者、急而果斷的展覽統籌），場景是兩人必須一起做決定的情況，呈現形式選小說敘事。

結果：1 passed（6 分 38 秒）。第 1 章生成 → 續寫 → 草稿不影響主線 → 採納 → 整部下載並離線開啟（兩章、有目錄）→ 作品列表出現多章節作品，全部走完；上一次失敗的那一步（作品頁停在 5/8 段）沒有再發生。畫面與下載到的檔案在 `C:\LifeWorld_project\alpha-unification-20261110\works_html_export_evidence\`（`series-01` 到 `series-04` 的 PNG、`series-downloaded.html`）。

用量：32 次模型呼叫：26 次成功（2 次規劃、24 段）、6 次被 Gemini 以 503 拒絕後自動重試。依診斷紀錄的 Token 數估計實際費用約 US$0.04。那 6 次 503 走的是新的退回規則，這個 revision 沒有任何錯誤層級的紀錄或 5xx 回應。帳本的資料列沒有直接讀取的管道，所以「雲端帳上確實退回」是由程式自帶的測試加上雲端沒有錯誤推定的，不是直接看到。

人物表現（人工閱讀下載到的檔案，不是自動判定）：比 2026-11-11 那件明顯改善。展覽統籌說話快、一直報時間、丟選項要對方選、直接拿別人的東西、談不下去就提折衷；模型製作者句子短、手不離開模型、被催時動作更慢、在「不能寫沒根據的話」上不退讓，被逼急時手會發顫。兩人互相回應，口頭禪沒有重複，24 段裡只有 7 段寫了場景提示。還有三個問題：規劃的節拍有時仍然寫出人物的態度；第 2 章有一段和第 1 章矛盾（第 1 章說紋樣沒有依據，第 2 章模型製作者卻說是照榫頭位置推敲的）；第 1 章最後一個節拍，模型製作者先回應了下一段才出現的電話。另外第 2 章因為續寫表單的預設值變成劇本對白（已修正）。

**驗收時發現並修正：續寫表單的預設值。** 第 1 章選小說敘事，續寫表單的呈現形式卻固定預設「劇本對白」，第 2 章就換了形式。修正：`GET /api/series/{id}` 多回 `output`（這部作品的長度與呈現形式），表單用它當預設。先寫的測試：`tests/test_story_series.py` 與 `tests/test_series_view.py` 各加 1 項（修正前都失敗）；Chrome 驗收也加了這一項檢查。修正後部署 revision `lw-api-main-b8030-11120129`。這個修正只用程式自帶的自動測試確認，**沒有在雲端實際操作過**（要先有一件生成完成的作品，等下一次真實模型驗收一起確認）。

## 2026-11-12 跨章一致性補強（提示詞 v6）、Chrome 驗收第二次、使用者的 E2E 帳號的第一件作品

使用者看過第一次重跑的結果後指示「補強並再跑一次」。

**修改。** 各章大綱除了模型寫的標題、前提、節拍，另外帶上那一章使用者寫的場景描述（最多 1000 字）與場景條件（`story_continuity.episode_outline`）。提示詞升到 `roleplay-plan-v6`／`roleplay-segment-v6`：v5 的規則全部保留，加上「已經成立的事實不能改變、不能替沒有依據的事補上依據」、「依 `beat.position` 決定是把情況帶出來還是接著往下寫」、「節拍不寫人物的想法、態度或立場」。v2 到 v5 原封保留。

先寫的測試：`tests/test_story_series.py` 加 1 項、改 1 項（大綱帶場景與條件、第三章看得到前兩章的場景、沒有場景時和原本一樣、超過 1000 字截斷）；`tests/test_persona_expression_prompt.py` 加 1 項、改 2 項（新作品用 v6、v5 的雜湊固定、新規則有送出、提示提到的欄位確實有送出）。實作前執行：5 failed。

整套自動測試：973 passed、8 failed、35 skipped、12 errors（221 秒）；失敗與錯誤的清單和修改前相同。

**Chrome 真實模型驗收（第二次）。** `LW_E2E_PERSONS_UI=1 LW_E2E_LIVE_GENERATION=1 python -m pytest -q browser_tests/test_story_series_ui.py`，revision `lw-api-main-b8030-11120143`，`persons_ui_` 開頭的合成帳號，同樣的兩位人物與場景。結果：1 passed（4 分 29 秒）。這次同時確認了續寫表單的修正：表單的呈現形式預設是小說敘事，第 2 章也是小說敘事。用量：23 次呼叫（21 次成功、2 次 503 後重試），估計約 US$0.03；這個 revision 沒有錯誤層級的紀錄或 5xx 回應。下載到的檔案是 `C:\LifeWorld_project\alpha-unification-20261110\works_html_export_evidence\series-downloaded.html`；第一次（v5）的檔案另存在同一個資料夾的 `run1-v5`。

人工閱讀的結果：第 2 章沒有再出現和第 1 章相反的說法（人物說「確實沒有文獻」「是猜的，沒有原件」「沒有根據的字眼不能寫在標籤上」）；每個節拍由第一個發言的人把情況帶出來，沒有再出現先回應後發生。兩位人物的差異仍然清楚。還看得到的問題：規劃的節拍有時仍然寫出人物的態度（例如「某人強調……拒絕……」）；時間細節前後不一致（場景寫八點、半小時後截稿，生成內容變成八點半、九點半截稿）；人物轉述紙條內容時換了說法。只跑了一次，不能當成問題已經解決的證明。

**使用者的 E2E 帳號的第一件作品。** 使用者在自己的帳號看到作品數是 0（測試都在合成帳號，作品只有擁有者看得到），要我在 App 內的瀏覽器面板用使用者的 E2E 帳號操作一次。建立頁：選兩位人物（各自的人物設定第 3 版），不勾「包含我」，場景是一個虛構的工作情境，填了起始事件、主角目標與四項場景條件，輸出選短篇、小說敘事，自己填了標題。結果：已完成，10 段，11 次呼叫（1 次規劃＋10 段，沒有失敗），估計約 US$0.03；作品列表顯示 1 件。

人工閱讀的結果：有行為描寫，其中一位分清楚「看得到的」與「推測的」的習慣與乾幽默看得出來。但兩人在第 2 段就達成共識、第 4 段就把問題解決，後面 6 段都在收拾與離場，沒有新的情況；另一位不願讓人看見半成品的那一面沒有出現，兩人的差異比合成帳號那一組不明顯。原因判斷：這兩位人物都偏謹慎、講依據，場景也沒有利害衝突或時間壓力；逐段提示要求「把事情往前推一步」，模型就提早把問題解決了。這一點還沒有處理。

## 2026-11-12 破題、名場面藍本與節奏（提示詞 v7）；使用者的 E2E 帳號的第二件作品

使用者看了自己帳號的第一件作品後的意見（原話）：「劇情過於生硬，且沒有激發人期待過程的設定」「要嘛，用一個歷史名場面來表演；或者，將名場面改編現代化、商戰、生活化、科幻化」「就跟寫文章需要主旨破題，才讓人有先入為主的觀念，以及對接下來的表演有期待」「演出劇情需要有熟悉的事物（好處是可以省略很多解釋，而改編則可以帶出創意的驚喜）」。並要我加規則後重生一件。

**修改。**

- 提示詞升到 `roleplay-plan-v7`／`roleplay-segment-v7`（前面各版的規則全部保留，v2 到 v6 原封不動）：`premise` 是開演前給觀眾看的開場白（破題）；場景提到觀眾熟悉的名場面時當作藍本，依它最為人熟知的橋段安排節拍，每個節拍用「對應〈橋段名稱〉：」開頭，人物保留自己的名字與個性；主要的懸念到最後一個節拍才有結果，同意之前先說保留或代價。逐段多收到 `beat.total`（節拍總數）。
- 作品頁在第一段之前顯示「開場」（規劃時寫的 `premise`）；匯出的 HTML 本來就有。
- 範例場景（`app/catalog/scene_presets.v1.json`，版本 1.1.0）加 5 個名場面：鴻門宴（照原樣演）、鴻門宴・商戰版、煮酒論英雄・職場版、空城計・生活版、三顧茅廬・科幻版。描述用「哪一方」來寫，不寫人名；選了之後由使用者補上誰站在哪一方。原有 12 個不變。

先寫的測試：`tests/test_persona_expression_prompt.py` 加 1 項、改 2 項；新檔 `tests/test_scene_presets_catalog.py` 2 項；`tests/test_run_export_view.py` 加 1 項（開場白在第一段之前、內容跳脫、規劃中或沒有前提時不顯示）；`tests/test_story_series.py` 改成檢查「續寫用現行版本」。實作前執行：7 failed（其中 1 項是測試自己寫錯的字眼，已修正）。

整套自動測試：977 passed、8 failed、35 skipped、12 errors（214 秒）；失敗與錯誤的清單和修改前相同。部署 revision `lw-api-main-b8030-11120211`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

**在使用者的 E2E 帳號重生一件（使用者要求，由我在 App 內的瀏覽器面板操作）。** 人物：三位（主角、對手、軍師），各用人物設定第 3 版，不勾「包含我」；場景從範例場景選「名場面｜鴻門宴・商戰版」，再補上三人各站在哪一方；輸出選中篇、小說敘事；標題留白。結果：已完成，17 段，22 次呼叫（18 次成功、4 次 503 後自動重試），估計約 US$0.05。AI 自己定了標題。作品頁在第一段之前顯示了開場白；下拉選單裡看得到 5 個名場面。

規劃的四個節拍：對應〈項王見沛公〉、對應〈范增舉璧〉（模型把「玦」寫成「璧」）、對應〈項莊舞劍〉、對應〈沛公逃走〉。

人工閱讀的結果（不是自動判定）：

- 有改善的：開場白交代了誰和誰、為了什麼、要守住什麼；衝突一路維持到最後，沒有人提早同意；三個人的位置分得出來（軍師冷、盯著條文，三次把筆推到合約上；對手三次把筆推開、不肯趁火打劫；主角用玩笑擋、不碰合約）；熟悉鴻門宴的人認得出「三次示意、主事者不應」。
- 還有問題的：結局沒有收住，最後一段主角站起來卻沒有離開，開場白的問題沒有答案，「借故離席、留下禮物、謀士最後那句話」都沒有演出來；三個人都用同一套比喻說話，台詞抽象，很少講具體的條款、數字或人；人物名字被寫錯（多次把主角和軍師兩個相近的名字混在一起）；17 段裡有 10 段寫了場景提示，多半是燈光與氣氛；第 13、14 段連續是同一個人說話。

只生成了一件，不能當成規則有效的證明。

## 2026-11-12 通用的故事原則（提示詞 v8）、個人／團體／關鍵情節的區別（reader-3）；使用者的 E2E 帳號的第三件作品

使用者的指示：追加規則可以，但必須是通用型，不是為了某一種戲劇張力而加（下次可能是狼人殺、童話冒險、科幻盜賊、名人的青年經歷、校園戀愛、旅遊規劃、生活懸疑）；故事沒有收尾時可以留懸念並補上「敬請期待下集」；人物多時用 HTML＋CSS 分出個人、團體與關鍵情節；指令要優化。主要需求是純文字、圖＋文、網頁互動各有 1 到 2 件代表作，並注意推進度。

**修改。**

- 指令整份重寫成 `roleplay-plan-v8`／`roleplay-segment-v8`（v2 到 v7 原封保留）。規劃依不分題材都成立的原則安排：類型與承諾、一個問題、起承轉合、轉折要意料之外情理之中、只有他知道的事、具體、自己解決、結尾或下集預告；v5 到 v7 的人物個性、事實一致、開場白與藍本都保留在裡面。
- 規劃多了欄位（`PLAN_SCHEMA_V8`，舊 Schema 不動）：`genre`、`sides`（陣營）、`private_notes`（只有那位人物知道的事）、每個節拍的 `title`（幕名）與 `kind`（起承轉合）、`teaser`（下集預告）。這些是輔助資料，模型寫錯時由 `_tidy_plan` 整理掉，不讓作品重新規劃。
- `private_notes` 只放進本人發言的那一段；作品頁讀到的規劃不含它（`public_plan`），匯出檔也不含。下集預告只在最後一個節拍才交給發言的人。
- 作品頁（`generation.js` 的 `panel`、`characters.css`）：人物依陣容順序有顏色、名稱旁有陣營標籤、每一幕開頭有幕名與起承轉合（轉折另有樣式）、開場白旁有類型、完成後在最後顯示「敬請期待下集」。
- 匯出檔升到 `reader-3`、`lw-story.v3`（`app/work_export.py`、`app/export_player/reader-3.*`）：同樣的區別，加上敘事、台詞、場景提示三種字體；人物顏色在多章節合集裡各章一致。版面樣張：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/版面樣張-reader3.html`。

先寫的測試：`tests/test_persona_expression_prompt.py` 重寫成 7 項（版本與舊版雜湊、規劃只看公開簡介、人物欄位說明、通用原則且不含特定題材的字眼、新 Schema、底牌只到本人與公開欄位的去向、寫錯的輔助資料被整理）；`tests/test_run_export_view.py` 加 1 項；`tests/test_work_export.py` 增為 24 項、`browser_tests/test_export_reader_offline.py` 增為 5 項。實作前執行：這一輪新增與改寫的案例共 29 項失敗。

整套自動測試：995 passed、8 failed、35 skipped、12 errors（227 秒）；失敗與錯誤的清單和修改前相同。離線閱讀器 5 passed。部署 revision `lw-api-main-b8030-11120414`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

**在使用者的 E2E 帳號生成純文字代表作（使用者要求各類型要有代表作；由我在 App 內的瀏覽器面板操作）。** 設定與上一件相同：同樣三位人物（主角、對手、軍師），範例場景「名場面｜鴻門宴・商戰版」，中篇、小說敘事。結果：已完成，17 段，19 次呼叫（18 次成功、1 次 429 後自動繼續），估計約 US$0.05。AI 定了標題、類型與兩個陣營，四幕依序是起、承、轉、合，有下集預告。新的規劃 Schema 被 Gemini 接受，沒有被拒絕。

人工閱讀的結果（不是自動判定）：

- 比上一件好的：有明確的轉折（主角亮出他的底牌）；有具體的物件與數字；結局回答了開場白的問題並留下下集預告；人名沒有再寫錯；三個人不再共用同一套比喻。
- 還有問題的：第 12 段對手說的是主角的立場，是一段演錯人的台詞；第 2 段軍師替對方說話，和他後面的立場不一致；小動作仍然重複（茶杯出現 7 次、「推半寸」4 次、手指敲兩下 4 次）；17 段裡 9 段有場景提示，多半是空調與燈光；鴻門宴的橋段比上一件不容易認出來（節拍沒有用「對應〈橋段〉」標出來）；規劃的節拍仍然寫了人物的動作與結果；結局來得偏容易。
- 判斷：結構性的要求（起承轉合、底牌、結尾、陣營、幕名）模型做得到；細緻的要求（不重複小動作、少寫場景提示、不演錯人）這個模型（`gemini-3.5-flash-lite`）遵守得不穩定，再加規則的效果有限。

只生成了一件。互動版與圖文版還沒有做。

## 2026-11-12 互動版匯出（play-1）；使用者的 E2E 帳號的第四件作品與兩件互動版

使用者要純文字、圖＋文、網頁互動各有 1 到 2 件代表作，並選擇先做互動版。這一版只用已經保存的資料，不多呼叫模型。

**修改。** `POST /api/works/{id}/exports` 多一個可選欄位 `player`（`reader` 或 `play`；不帶就是閱讀版，其他值 422）。互動版的播放器是 `play-1`、內嵌資料 `lw-play.v1`（`lw-story.v3` 的超集：每段多 `state`，每章多 `secrets`）。播放器的行為：一次揭開一段（按鈕、空白鍵、方向鍵；可回退；有進度；可切換全部顯示）、「真心話」開關（顯示每段之後這位人物保存的情緒、立場、目標）、點人物名稱只強調他的段落、讀完才出現的結尾卡（下集預告、看底牌、你站哪一邊、從頭再看）。沒有 JS 時內容全部可讀，底牌收合。作品頁與多章節總覽各多一顆「下載互動版」。閱讀版的輸出逐位元不變。

測試：`tests/test_work_export.py` 增為 35 項、`tests/test_run_export_view.py` 6 項、`tests/test_series_view.py` 6 項、新檔 `browser_tests/test_export_play_offline.py` 6 項（系統 Chrome、完全離線：逐段揭開、幕名跟著第一段出現、回退、真心話、人物篩選、讀完才看得到底牌、選陣營、沒有對外請求、console 沒有錯誤）。實作前新測試都失敗（19 項），兩項防護性檢查本來就成立。

整套自動測試：1008 passed、8 failed、35 skipped、12 errors（232 秒）；失敗與錯誤的清單和修改前相同。離線播放器兩個檔 11 passed。部署 revision `lw-api-main-b8030-11120503`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped（部署完成當下第一次執行有 1 failed、1 error，立刻重跑全過，是新版本切換時的暫時現象）。

**使用者的 E2E 帳號的第四件作品（純文字第二件代表作，換一種類型；由我在瀏覽器面板操作）。** 兩位人物，範例場景「名場面｜空城計・生活版」並補上誰站哪一方，短篇、小說敘事。結果：已完成，12 段，13 次呼叫（沒有失敗），估計約 US$0.04。AI 定了標題、類型與兩個陣營，四幕起承轉合，有下集預告。人工閱讀：空城計的橋段對得上（虛張聲勢、轉折時被識破、最後亮出底牌讓雙方各退一步），結構比商戰那一件順；問題是有一位人物的一句台詞說錯了自己在這場戲裡的身分、12 段裡 5 段有場景提示、節拍仍然寫了人物的動作。

**在使用者的 E2E 帳號匯出互動版（瀏覽器面板，按作品頁的「下載互動版」）。**

| 作品 | 檔名 | 大小 | 檢查（在頁面裡讀回下載端點的內容） |
|---|---|---|---|
| 第四件（空城計・生活版） | `〔標題〕（互動版）.html` | 53,794 bytes | `lw-play.v1`；12 段、12 段都有真心話；有轉折幕、看底牌、下集預告、選陣營；雜湊與匯出紀錄一致；沒有外部資源；不含人物設定欄位 |
| 第三件（鴻門宴・商戰版） | `〔標題〕（互動版）.html` | 59,689 bytes | `lw-play.v1`；17 段、17 段都有真心話；有看底牌、下集預告、選陣營；雜湊一致；沒有外部資源 |

下載回應是 200、附件、`Content-Security-Policy: default-src 'none'; sandbox`。
沒有做到的：App 內的瀏覽器面板沒有把檔案存到下載資料夾，所以**這兩個真實的互動版檔案我沒有在瀏覽器裡實際點過**；播放器的操作是用同一份程式產生的樣張與離線 Chrome 測試確認的。樣張：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/版面樣張-互動版.html`。

## 2026-11-12 互動層與 play-2：視角、限次讀心、線索、關鍵抉擇與三個結局

外部審閱與使用者的意見：play-1 是閱讀輔助，不是遊戲——真心話一開就全部攤開，沒有東西可猜；怎麼點結局都一樣。使用者同意升級，每件作品多呼叫一次模型。

**修改。**

- 互動層（`app/interactive_layer.py`，提示詞 `interactive-layer-v1`）：作品完成後多呼叫一次模型，產生關鍵抉擇（三個選項：故事實際的做法、行得通但較差的、會弄巧成拙的；後兩個各有一段旁白結局）、線索、各陣營的番外、給讀者的一句提問。送給模型的只有作品本身（標題、開場白、各幕、每一段的台詞與動作、底牌），不含人物設定。輸出由程式整理：線索的詞必須是原文裡一字不差的子字串，寫錯的丟掉。存進作品內容的 `interactive`（新增一個作品版本）。
- `POST /api/works/{id}/interactive`：只接受本人已完成的生成作品；已經有就不再呼叫模型；回應只有數量，不含內容（避免劇透）。沿用每日金額上限的預留與結算。
- 播放器升到 `play-2`、資料 `lw-play.v2`：開始前選一位人物的視角（或旁觀）；自己的真心話直接看，別人的要消耗次數偷看（兩位人物 2 次、三位以上 3 次）；線索詞可以點，同一位人物的線索集滿就看穿他的底牌；到抉擇點停下來選，真結局接回原本的故事，另外兩個顯示旁白並可回到轉折點重選；記錄看過幾個結局；選邊之後出現那一方的番外與提問。沒有互動層的作品只有視角與限次讀心。多章節合集每一章用自己的互動層。沒有 JS 時整篇可讀，抉擇以靜態區塊呈現。閱讀版輸出不變。
- 作品頁按「下載互動版」會先準備互動層再匯出；準備失敗時改匯出沒有抉擇的版本並說明原因。

測試：新檔 `tests/test_interactive_layer.py` 19 項；`tests/test_work_export.py` 46 項、`tests/test_run_export_view.py` 8 項、`tests/test_series_view.py` 6 項、`browser_tests/test_export_play_offline.py` 9 項（系統 Chrome、完全離線：選視角、限次偷看、收集線索看穿底牌、抉擇卡、沒找到線索時真結局不能選、壞結局與重選、真結局、結局計數、番外與提問、沒有互動層的檔案）。兩位實作者各自在實作前確認新測試失敗；其中 7 項是實作後才補的（回報裡有列）。

整套自動測試：1040 passed、8 failed、35 skipped、12 errors（320 秒）；失敗與錯誤的清單和修改前相同。離線播放器兩個檔 14 passed。部署 revision `lw-api-main-b8030-11120651`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

**在使用者的 E2E 帳號為兩件作品產生互動層並匯出（瀏覽器面板，按作品頁的「下載互動版」；真實模型）。**

| 作品 | 互動層 | 匯出 |
|---|---|---|
| 第四件（空城計・生活版） | 抉擇在第 3 幕之後，做決定的是對手；三個選項與兩段旁白結局；番外 2 則；提問 1 句；**線索 0 則** | `play-2`，84,947 bytes，雜湊與紀錄一致，沒有外部資源 |
| 第三件（鴻門宴・商戰版） | 抉擇在第 3 幕之後，做決定的是主角；三個選項與兩段旁白結局；番外 2 則；提問 1 句；**線索 0 則** | `play-2`，90,746 bytes |

兩次呼叫都成功，各約 3 秒；輸入約 3,500 到 3,800 Token、輸出約 660 Token，每次估計約 US$0.003。這個 revision 沒有錯誤層級的紀錄或 5xx 回應。

人工閱讀互動層內容的結果：

- 做到的：兩件都有合理的三個選項與兩段不同的旁白結局；番外貼合人物（對手那一則和他的底牌一致）；提問是對讀者說的。
- 沒做到的：**兩件的線索都是 0 則**。指令寫了「沒有合適的詞就不要硬給」，模型兩次都沒給，所以「找線索才能選真結局」這個玩法在真實作品上沒有出現（真結局直接可選）。
- 抉擇點的位置：程式固定放在轉折那一幕結束之後。鴻門宴那一件的轉折就是主角亮出底牌，所以真結局的選項讀者已經看過，沒有懸念；空城計那一件選到的決定者是對手而不是主角。
- **沒有實際點過真實的互動版檔案**：App 內的瀏覽器面板按下載不會存檔。播放器的操作是用同一份程式產生的樣張與離線 Chrome 測試確認的。樣張：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/版面樣張-互動版2.html`。

## 2026-11-12 回合制互動作品第 1 期：使用者選擇、角色依個性反應、數值決定結局（行程題材）

使用者定案的方向：核心是 AI 角色扮演——使用者在自己的回合做選擇，其他角色各自依個性反應；每位角色有一個數值，每個選項讓不同角色的數值各自升降，數值決定多結局；結局像遊戲結局（字幕、音樂、特效）；引擎要通用（旅遊、登山、購物、採購、劇情……只換節點與資源）；版面是左欄走過的路、右欄內容與選項。第 1 期做通用引擎與行程題材。

**修改。**

- 後端 `app/turn_game.py`（新作品種類 `turn_game`、內容 `game.v1`，沒有改資料表）：規劃一次（`game-plan-v1`：5～8 站、開場白、數值名稱、四種結局；只看同行者的公開簡介），每位同行者各自一次（`game-reaction-v1`：只看自己的完整人物設定，寫出到每一站時三種態度下的反應、數值加減、沒說出口的願望、結局時的最後一句話）。時間由程式計算；程式檢查可玩性（時限內至少走得完 3 站），並把所有走得到的行程列舉一遍，取數值總和的第 25、75 百分位當結局門檻。通用規則與行程規則分成兩組函式。
- API：`POST /api/games`（規劃）、`POST /api/games/{id}/advance`（下一位同行者）、`GET /api/games/{id}`（不含反應、願望與結局的文字）。
- 播放器 `route-1`（`lw-route.v1`）：左欄走過的每一站（可點回去，時間與數值都回到當時）與示意地圖；右欄這一站的內容、每個人的反應與數值升降、接下來的選項卡（只顯示車程、到達、停留、打烊，不顯示對誰有影響）；結局演出（片尾字幕、煙火或紙花、下雨與褪色、Web Audio 合成的音樂，預設不播）；沒有 JS 時顯示站的清單。通用層與題材層分開。
- 站內直接玩：`GET /api/works/{id}/exports/{version}/view`（只有這一條回應允許被同源框住）；頁面 `#game-new`、`#game/{id}`（`app/static/game.js`），作品頁多「＋ 互動遊戲」。

測試：`tests/test_turn_game.py` 31 項、`tests/test_route_export.py` 14 項、`tests/test_trip_reference.py` 11 項、`tests/test_game_view.py` 12 項、`browser_tests/test_export_route_offline.py` 12 項。後端與播放器各自實作同一套時間、數值、結局規則，用示意資料所有走得到的行程逐步對照，結果一致。兩位實作者各自在實作前確認新測試失敗；播放器畫面層與建立頁的迴圈有一部分是先有初稿才補測試（回報裡有列）。

整套自動測試：1109 passed、7 failed、35 skipped、12 errors（273 秒）。失敗比先前少 1 項：`test_public_password_core_journey_and_owner_isolation` 只在台北時間 0 到 9 點失敗，這次在白天執行所以通過；其餘清單相同。離線播放器三個檔 26 passed。部署 revision `lw-api-main-b8030-11121105`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

**在使用者的 E2E 帳號生成並實際玩（瀏覽器面板；真實模型）。** `#game-new`：三位同行者（各用人物設定第 3 版），說明是虛構的海邊小鎮一日遊，起點車站、10 小時、08:00 出發。結果：約 50 秒內完成，4 次呼叫全部成功（規劃 1 次、同行者 3 次），輸入共約 18,500 Token、輸出共約 3,400 Token，估計約 US$0.014。作品有 6 站，數值名稱「心情」。

實際玩了一輪（走三站後回車站）：

| 站 | 同行者甲 | 同行者乙 | 同行者丙 |
|---|---|---|---|
| 第 1 站 | +2 | +1 | +1 |
| 第 2 站 | −1 | −1 | +2 |
| 第 3 站 | −2 | −2 | +1 |

時間、可去的站與等開門的分鐘數都由播放器算出；回車站後是遺憾結局（poor），有下雨與褪色的效果，顯示每個人最後的數值、最後一句話與這時才揭曉的願望、片尾的行程表，以及「已看過 1／4 種結局」。

人工閱讀的結果：三個人的反應分得出來（一位愛咬文嚼字、一位務實話少、一位用牌局的說法）；同一站對不同人有升有降，確實要取捨。問題：有一位的願望指向六站裡沒有的地方，這個願望無從滿足；數值總和 +1 仍被判成遺憾結局（門檻是相對的，取所有走法的第 25 百分位）；只玩了一輪，另外三種結局沒有實際走到。

**沒有做到或沒有驗證的。**

- App 內的瀏覽器面板會擋掉頁面內嵌的框架（`ERR_BLOCKED_BY_CLIENT`），所以「在這裡玩」在面板裡是空白的；改用頁面上的「在新分頁開啟」可以玩。一般的 Chrome 裡內嵌框架只在測試環境驗過，沒有在 8030 上看過。
- 音樂只確認按了才建立音訊，沒有實際聽過。
- 互動版（play-2）的「在這裡玩」沒有在 8030 上操作過。

## 2026-11-12 統一建立入口：建立時選玩法（看的故事／玩的遊戲）

使用者的意見（原話）：「＋新作品 跟 ＋互動遊戲一定要分開嗎？難道以選擇模組的方式，做為區隔？之後還有互動式＋滾動視差視覺 HTML，理論上都是 HTML，為什麼要多入口」。定案：只留一個入口，建立頁第一步選玩法；呈現方式（閱讀版、互動閱讀版、互動遊戲，之後的多格漫畫、捲動視差）到作品頁再選。

**修改（只改前端）。**

- 建立頁（`app/static/creation.js`）最上面加「玩法」：看的故事（預設，AI 把整個劇情演完）與玩的遊戲（你每回合做選擇，角色依個性反應，數值決定結局）。選玩的遊戲時同一頁只顯示它需要的東西：人物 1～3 位（只列有人物設定的人物）、你的稱呼、行程說明、題材（目前只有行程）、起點、時數、出發時間、標題；送 `POST /api/games` 後到 `#game/{id}`。兩種玩法已填的內容切換時都保留。預設玩法下，去掉玩法那一塊之後，建立頁六個階段的畫面與送出的請求和改動前逐字相同。
- 作品頁只剩「＋ 建立新作品」；舊網址 `#game-new` 就地改寫成 `#create?mode=game`（預選玩的遊戲）。`#game/{id}` 不再有建立表單。
- 作品清單的種類標籤：生成作品「看的故事」、多章節作品「看的故事・多章節」、互動遊戲「玩的遊戲」；其他舊種類不變。
- 看的故事的作品頁：區塊標題「看或玩」，多一顆「在這裡看」（閱讀版放進頁面內的框架）；原本的下載與「在這裡玩」不變。

測試：新檔 `tests/test_creation_mode_view.py` 11 項；`tests/test_game_view.py`（建立表單的案例搬到新檔，檢查點相同）、`tests/test_run_export_view.py` 跟著改。實作前 16 項失敗。`browser_tests/test_story_series_ui.py` 的清單標籤斷言改成「看的故事・多章節」（這一輪沒有執行）。

整套自動測試：1120 passed、7 failed、35 skipped、12 errors（268 秒），失敗清單和上一輪相同。離線播放器三個檔 26 passed。部署 revision `lw-api-main-b8030-11121206`；不呼叫模型的雲端 API 回歸 3 passed／3 skipped。

面板確認（使用者的 E2E 帳號，沒有送出建立、沒有呼叫模型）：作品頁只剩「＋ 建立新作品」，沒有連到 `#game-new` 的連結；清單上 4 件生成作品標成「看的故事」、互動遊戲標成「玩的遊戲」。打開舊網址 `#game-new` 會變成 `#create` 並預選「玩的遊戲」，只顯示 ① 人物、② 場景；② 場景裡有行程用的說明提示、題材（行程）、起點、時數（8／10／12）、出發時間；開始生成的面板寫「會呼叫模型 2 次：規劃 1 次，加上 1 位同行者各 1 次」（勾了一位人物時），沒寫說明時說明不能開始的原因。切到「看的故事」時 ①～④ 與「包含我」都在，面板是原本的「自動判斷：單人文字（1 位）」。看的故事作品頁的區塊標題是「看或玩」，按鈕依序是下載 HTML、下載互動版、在這裡看、在這裡玩。確認完按「清除重來」清掉測試用的草稿。沒有實際送出建立，所以從新入口建立遊戲到完成的整條流程，只有自動測試與離線 Chrome 檢查，沒有在 8030 上跑過；「在這裡看」在面板裡會被擋（和「在這裡玩」相同）。

## 2026-11-12 外部檢驗後的修正（互動遊戲上 GitHub 前）

Codex 依 `docs/INTERACTIVE_GAME_REVIEW_20261112.md` 做了獨立檢驗，建議先修正再提交（報告在工作樹外：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_INDEPENDENT_REVIEW_20261112.md`）。五項發現都修正了：

| 發現（Codex 的優先序） | 修正 | 測試 |
|---|---|---|
| P1 同一位同行者可以重複生成及結算（第一個請求結算後、存進作品前的空窗） | `GameReactionModule.resolve` 在同一個交易內也找「已成功、還沒存進作品」的那一筆；有的話不預留、不呼叫模型，`/advance` 直接 `game_apply` 那一筆。互動層（`POST /api/works/{id}/interactive`）有同樣的空窗，用同樣的做法修正 | `tests/test_turn_game.py`、`tests/test_interactive_layer.py`：模型沒有再被呼叫、帳本只有一筆預留、作品只多一個版本 |
| P2 規劃失敗後，原表單重按只拿到舊錯誤 | 建立頁與遊戲頁依結果決定提交代碼：伺服器明確回了失敗（有狀態碼，且不是 409 `generation_in_progress`）→ 下一次是新的嘗試；連線中斷或還在進行 → 沿用原代碼（若其實已完成，重送只會找回那一次的結果）。建立頁失敗時另外說明再按會發生什麼（重新規劃並再呼叫一次模型，或只是找回結果） | `tests/test_creation_mode_view.py`、`tests/test_game_view.py`（原本「每次重試都換新代碼」的斷言依這條規則改寫） |
| P2 模型回超大整數時 500、紀錄留在 `running` | `number()` 先檢查範圍（絕對值超過 10^9 當作沒有給），任何輸入都不拋例外；兩個模組的 `parse` 把整理時意外的例外轉成 `invalid_output`；共用的 `ai_finish` 也兜底：`parse` 拋出非預期的例外時記一行只有類型的日誌，當作 `invalid_output`，紀錄一定離開 `running`、用量照常結算 | `tests/test_turn_game.py`（規劃與反應各一）、`tests/test_generation_8030.py`（共用層） |
| P2 匯出文字的隱私承諾超出程式保證 | 作品頁、多章節總覽、遊戲頁的說明改成實際能保證的範圍：檔案裡不含人物設定的欄位與我的設定；台詞與反應是 AI 依人物設定寫的，可能用到設定裡的說法，分享前可以先看過。沒有加自動比對原文的檢查 | 前端測試照舊檢查說明存在 |
| P2 通用作品 API 讓本人讀到劇透與內部參照 | `GET /api/works/{id}`、`GET /api/works/{id}/versions/{n}`、`POST /api/works/{id}/status` 依種類投影：`turn_game` 只回和 `GET /api/games/{id}` 同等級的欄位；`generated_work` 拿掉 `content.interactive` 與 `plan.private_notes`（`meta` 不變）。另外 `GET /api/ai/generations/{id}` 對 `game_plan`、`game_reaction`、`interactive_layer` 不回原稿，`roleplay_plan` 的原稿拿掉 `private_notes` | `tests/test_turn_game.py`、`tests/test_interactive_layer.py` |

先寫的測試在修正前都失敗（後端 8 項加上互動層與生成紀錄的新測試，前端 3 項）。

整套自動測試：1134 passed、7 failed、35 skipped、12 errors（278 秒），失敗與錯誤的清單和修改前相同。離線播放器三個檔：26 passed。部署 revision `lw-api-main-b8030-11121327`；不呼叫模型的雲端 API 回歸：3 passed／3 skipped。這一輪沒有呼叫真實模型，修正後的流程沒有在 8030 上實際建立遊戲。

維持原樣、記在交接的已知限制：修正前保存的封存／恢復回執重送時仍是未投影的舊內容；舊種類 `roleplay_session` 沒有投影；沒有設定 Provider 時，「有結果還沒存」的 `/advance` 仍回 503；過深的 JSON 由共用層兜底成 `invalid_output`。

## 2026-11-12 第二次外部檢驗後的修正

Codex 複驗（報告在工作樹外：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_RECHECK_20261112.md`）確認第一次的五項都已修正，另外找到三項程式問題與一項文件問題，結論是仍需修正。這一輪的修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| P1 接手別的請求已結算的結果後，同一個提交代碼重送會替下一位同行者生成並再計費 | 接手時在存入作品的同一個交易裡替這個提交代碼記回執（`game:advance`，綁定作品與那一筆結果）；`/advance` 挑下一位之前先查回執，有就只回目前的進度。同一個代碼拿去推進另一件作品是 409 `idempotency_conflict` | `tests/test_turn_game.py`：重送不再呼叫模型、帳本不變、完成後重送也不生成、跨作品 409 |
| P2 修正之前保存的封存／恢復回執重送仍回完整內容 | 讀回執時也套用公開規則（`works_center.public_detail`）；`turn_game.game_public` 對已經公開的內容只挑公開欄位，投影兩次結果相同 | `tests/test_turn_game.py`：把回執改成修正前的格式後重送，只有公開欄位 |
| P2 舊種類 `roleplay_session` 恢復生成後，通用 API 讀得到底牌 | `public_content` 對 `roleplay_session` 套用和 `generated_work` 相同的規則；沒有這些欄位的舊內容原樣回傳 | `tests/test_turn_game.py` |
| 提交文件含連結實際帳號的驗收紀錄 | 四份文件（`ACCEPTANCE.md`、`EVOLUTION.md`、`UNIFIED_PERSON_HANDOVER.md`、`INTERACTIVE_GAME_REVIEW_20261112.md`）把帳號名稱改成「使用者的 E2E 帳號」，拿掉該帳號五件作品的識別碼，以及帳號本人在我的設定做過哪些操作的描述。原始紀錄另存在工作樹外：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/acceptance_raw_20261112/` | 掃描四份文件沒有帳號名稱與那五個識別碼 |

先寫的三項測試在修正前都失敗（重送會往下生成到 ready；已公開的內容再投影時拋出 `KeyError`；舊種類的底牌沒有拿掉）。

整套自動測試：1137 passed、7 failed、35 skipped、12 errors（298.50 秒），失敗與錯誤的清單和修改前相同。離線播放器三個檔：26 passed。部署 revision `lw-api-main-b8030-11121419`；不呼叫模型的雲端 API 回歸：3 passed／3 skipped。這一輪沒有呼叫真實模型。

Codex 評估可以接受、維持原樣的兩項：沒有設定 Provider 時「有結果還沒存」的 `/advance` 回 503（恢復設定後同一個代碼會接回原結果）；沒有自動比對生成文字是否照抄人物設定（說明已提醒分享前檢視）。另外，本人可以從生成紀錄 API 讀到這幾個模組的輸入參照（人物、設定版本與雜湊，沒有設定正文），Codex 列為可選的後續收斂。

## 2026-11-12 第三次外部檢驗後的修正

Codex 第三次複驗（報告在工作樹外：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_THIRD_REVIEW_20261112.md`）確認上一輪的三個重現案例都已通過，另外找到一個並行次序的問題與文件問題，結論是仍需修正。這一輪的修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| P1 同一個提交代碼的兩個請求並行：一個在路由查過「沒有回執」後停住，另一個接手已結算的結果、記回執、存好（2/3）；前一個再走進預留，就替下一位同行者生成並多結算一次（3/3） | 查回執、接手已結算的結果並記回執、決定是否預留下一位，放進同一個寫入交易。共用預留 `ai_reserve` 多一個 `shortcut`：在同代碼的生成紀錄查過之後、`resolve` 之前執行，回傳值就是這次的結果（不預留、不占額度，交易照常提交）。回合制作品的捷徑是 `TurnGameMixin._game_pickup`；下一位的檢查抽成 `GameReactionModule.target`，捷徑與 `resolve` 共用同一套檢查。回執在預留的交易裡就記好，`game_apply` 不再寫回執：存作品失敗時，同一個代碼重送照回執再存，不往下生成。路由的快速查詢保留（不需要 Provider），查到「沒有」不算數 | `tests/test_turn_game.py::test_two_requests_with_the_same_id_picking_up_a_settled_result_never_start_another_companion`：三種次序（兩個都到存作品那一步、一個早查晚預留、存作品失敗後重送），都要一筆回執、兩個回應都是 2/3、只替第一位呼叫過模型、帳本不變、作品只多一個版本；「早查晚預留」在修正前失敗 |
| 文件仍有帳號的同意狀態，以及實際作品的標題與陣容 | 四份文件拿掉帳號的同意狀態（含交接第 7 節表格的 `consent`）；作品標題、人物名稱與生成內容的細節改成通用描述（第幾件、名場面藍本、幾位人物、主角／對手／軍師），路徑、呼叫次數、費用、段數與人工閱讀的結論保留。上一輪替換帳號名稱時弄壞的匯入資料夾路徑改成文字描述。這一輪改之前的版本另存在工作樹外：`C:/LifeWorld_project/alpha-unification-20261110/works_html_export_evidence/acceptance_raw_20261112/*_before_third.md` | 第三次檢驗的掃描程式（在暫存資料夾的複本）重跑：帳號名稱、五個識別碼、四個作品標題都是 0；`consent_near_anonymous_account` 只剩 `EVOLUTION.md:242`（那一行寫的是產品的同意文字仍用「我的人設」，不是帳號的狀態） |

範圍說明：`tests/`、`browser_tests/` 用的虛構人物名稱與公開簡介，是既有的合成測試資料（已提交的 `39ad50a` 裡就有），沒有人物設定欄位的內容，也不連到任何帳號；這一輪沒有改。

先寫的測試在修正前：3 項裡「早查晚預留」失敗（兩個回應是 2/3 與 3/3），另兩種次序本來就通過（留作回歸）。Codex 的第三次重現程式（`third_review_probes.py`、`third_review_limits.py`）在本機 SQLite 重跑：14 passed（修正前 13 passed、1 failed）。

整套自動測試：1140 passed、7 failed、35 skipped、12 errors（292 秒；失敗、錯誤與跳過的清單和第三次檢驗的基線逐項相同，多的 3 項是新測試）。離線播放器三個檔：26 passed。部署 revision `lw-api-main-b8030-11121452`；不呼叫模型的雲端 API 回歸：3 passed／3 skipped。這一輪沒有呼叫真實模型。隔離 PostgreSQL 的重現沒有在本機跑（本機沒有 PostgreSQL 工具）；PostgreSQL 同帳號的寫入交易先取 advisory lock，READ COMMITTED 每個 statement 用新快照，後到的交易看得到先到的回執。

## 2026-11-12 第四次外部檢驗後的修正

Codex 第四次複驗（報告在工作樹外：`C:/LifeWorld_project/codex-review-turn-game-20261112/INTERACTIVE_GAME_FOURTH_REVIEW_20261112.md`）確認第三次的並行問題已修正、文件去識別化通過、回歸通過；唯一沒通過的是跨作品提交代碼在目標已完成時的回應。這一輪的修正：

| 複驗發現 | 修正 | 測試 |
|---|---|---|
| 已綁在遊戲 A 的提交代碼送到遊戲 B：B 還在生成時是 409 `idempotency_conflict`，B 已完成時卻先回 200（路由看到 ready 就回傳，沒有檢查代碼綁在哪一件） | `/advance` 先呼叫快速查詢 `game_advance_receipt` 再判斷 ready。快速查詢是唯讀交易、不需要 Provider，同時檢查代碼的兩種綁定：接手的回執（`requests` 的 `game:advance`）與這個代碼自己生成過的角色反應（`ai_generations`，指紋用和 `ai_reserve` 相同的 `ai_fingerprint`）；綁在別件作品就是 409。同一件作品自己的代碼重送、全新的代碼，在 ready 時照常回 200。預留交易裡的查核（`_game_pickup`）保留 | `tests/test_turn_game.py::test_a_code_bound_to_one_game_is_refused_on_another_game_even_when_that_game_is_ready`（兩種綁定來源；B 生成中與已完成；沒有設定 Provider；同作品重送與新代碼 200；不呼叫模型、帳本與作品不變），修正前兩種來源都失敗 |

Codex 的重現程式（`third_review_probes.py`、`third_review_limits.py`、`fourth_review_cases.py`）在本機 SQLite 重跑：19 passed（修正前第四次的補充案例是 3 passed、2 failed）。

整套自動測試：1142 passed、7 failed、35 skipped、12 errors（267 秒；失敗、錯誤與跳過的清單和第四次檢驗的基線逐項相同，多的 2 項是新測試）。離線播放器三個檔：26 passed。部署 revision `lw-api-main-b8030-11121515`；不呼叫模型的雲端 API 回歸：3 passed／3 skipped。這一輪沒有呼叫真實模型。
