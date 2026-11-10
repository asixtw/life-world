# 2026-11-10｜最新 main 隔離整合候選

本文件記錄交付前的來源與驗證範圍，不代表 GitHub 推送、PR 合併、Cloud Build 核准或部署。既有歷史證據保留原始結果；較早文件中的「最新／待執行」只適用其記錄時間。

## 可追溯來源與修改範圍

- 實際 Git 基底：`68102f230aa947a434286ba9260e1ae75f6634b0`，本輪透過公開 GitHub `main` 取得；原樹有 1,037 個檔案。
- 已驗證 v4 分發候選：646 檔，來源包 SHA256 `57d475d718121e9714d3c73afbba88b2ac363f44aa06c36cdfd5200895655a09`。
- 原分發包宣告基底 `72ea3eed64a509a111afb1687e2f0d978566b375`。公開倉庫 fetch 回覆 `not our ref`，因此它仍是分發包的來源宣告，不宣稱已從 GitHub 驗證該 commit 或重建其歷史。
- 646 檔與實際 main 比對：610 檔相同、13 檔修改、23 檔新增。只把這 36 檔差異套入獨立分支，沒有使用整包替換、沒有刪除 main 檔案。
- main 另有 414 檔不在分發包內，含 collaboration 306 檔與 docs 108 檔；逐一核對原 Git blob 保留。整合後 1,060 檔，加上本交接文件共 1,061 檔。
- 改動涵蓋 PG pool 關閉／歸還與 Connector 清理、音效與孵化生命週期、獨立評測儲存的 Windows fail-closed 邊界、PG fixture／owner matrix、平台與日期穩定性測試及媒體參數化 ID。
- v4 相對原分發基底只增加 `tests/test_media.py` 的 12 個 semantic IDs，兩處新增 `ids` 移除後 AST 相同，原參數與斷言不變。

## 本輪在完整整合工作樹實際執行

- Python 3.12、`requirements.api-test.lock` 的 61 個鎖定依賴相符。
- 完整 Linux／合成 SQLite 與離線測試：**571 passed、24 skipped、0 failed、0 errors，595 案，40.73 秒**。
- 24 個跳過為 17 個 PG 專用案例及 7 個 Windows 原生拒絕案例，不計通過。Windows v4 未執行的 POSIX 成功路徑本輪有執行。
- 595 個唯一 testcase IDs 與 v4 core＋matrix 的集合精確相同，沒有 missing、extra 或 duplicate。
- 音訊／孵化原始 Node 合約：**22 passed、0 failed、0 skipped**。產品 JavaScript 未再修改，保留此前 13 檔語法檢查結果。
- pytest 原樣保留 18 個 `record_property` 與 JUnit xunit2 的格式警告，沒有壓制、刪測試或放寬斷言。這些不是 Pydantic alias 警告。
- 使用新的合成資料及最小環境，pytest 程序阻擋 Python socket connect；這不是 OS 層網路沙箱。未操作 Cloud SQL、真實 AI、瀏覽器或原專案資料。

完整測試需要 `requirements.api-test.lock`。原 README 的 `requirements.lock` 不包含直接被 Google／IAP 測試匯入的 google-auth／cryptography；舊環境首次收集出現 2 個 errors，保留其紀錄，另建正確鎖版環境後完整重跑。本輪不擅改依賴鎖檔或既有環境。

## 保留的歷史 PG 與體驗證據

- Windows PG18 v4 run `6d91bf32633b4b528b70ba6cdfd674af`：core 580 passed／10 個宣告的平台 skips；matrix 5 passed／0 skip。必要 PG 17＋5 項通過，222 個 app fixture 案例均標示 PostgreSQL。
- 本輪只重新核對原結果包、其 19 個證據檔與 JUnit；未把歷史結果改寫成本輪 PG 執行。歷史 1 個 Pydantic alias=`end` 警告保留，未改產品或壓制警告。
- 桌面人工音效／孵化驗收、合成 API→Cloud SQL 讀寫與雙向 owner 隔離，依各自收據與版本記錄成立；不自動證明本候選 commit 已部署或完整端到端驗收。

## 與 Google 登入轉移分支的關係

- 已公開分支 `codex/google-world-transition-20261110` 為 `2f81508c948801b6d4c1f6b3f03bc77b432ac90e`，其直接 parent 也是 `68102f230aa947a434286ba9260e1ae75f6634b0`。
- 該分支修改 27 個路徑，本候選的 36 個來源差異沒有路徑交集。沒有文字層路徑衝突，不代表組合後的登入、guest owner 切換、UI 音訊與持久化已驗收。
- 本候選不含該分支的 Google 帳號轉移功能。若後續整合它，保留其五個產品檔案與專用測試，再對合併後版本重跑完整測試與必要旅程。不能用舊 646 檔整包覆寫該分支。

## 交付與驗收界線

- 只在隔離分支準備，不推 main、不核准 Build、不 merge、不部署。不因測試通過推定部署保護或 IAM 已完成。
- 未讀取或修改使用者桌面未提交檔案，未取代原 worktree。
- 保護 E2E 瀏覽器登入已依使用者明確同意延後至 GitHub 交付後；手機／Safari、正式網站流程及其他尚未完成的重啟／備份恢復檢查仍各自保留。延期不是通過或上線安全豁免。
- GitHub 交付後的新人物 SQL 不屬本候選，未執行。
