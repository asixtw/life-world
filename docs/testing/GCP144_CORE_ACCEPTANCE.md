# GCP-144 核心流程與介面修正候選

## 本輪結果

- API：`python -m pytest -q tests/test_staging_ui_copy.py tests/test_core_readback.py tests/test_experiences.py`，23 passed（0.73s）。
- Chromium：`python -m pytest -q browser_tests/test_guest_save_copy.py`，4 passed（3.41s）。
- 全為隔離合成測試；API 使用 SQLite，瀏覽器僅替代頁面查詢以驗證正式 render/finally 和保存提示，不是 PostgreSQL、真實 AI 或 OAuth 驗收。
- 本機標籤測試先失敗後修正；訪客保存提示兩種 capability 分支先失敗後修正。

## 功能證據與限制

經歷案例涵蓋：草稿／整理候選不累計正式進度、人工確認一次保存經歷／任務／貢獻／獎勵、同 key 重送、不同 key 再確認、修改 payload 衝突、DB 失敗全回滾及併發去重。新增跨 App 實例讀回與再次重送，確認不是只讀前端快取。ManualAssistant 為原文候選，沒有呼叫真實 AI。

「本機開發版」原為 HTML 固定文字，改為環境中立的「Life World 測試版」。保存成功提示依 google_login_available 宣告 Google 功能是否開放；Session 失效不等同資料刪除，也不承諾訪客可自行恢復。

Loading 不是常駐文字；超過200ms才顯示，成功／失敗 finally 隱藏。Chromium驗證兩條路徑均回復 hidden 與 aria-busy=false；本輪線上觀察未見殘留。不為沒有重現的問題修改載入邏輯。

## 尚未完成的線上 Gate

- 既有私人 PostgreSQL DBA 通道尚未取得：Stage40/50、007/008、有效權限及資料筆數均 NOT VERIFIED。
- 線上畫面已觀察到測試閱讀目標及三習慣；當時有另一使用者同時填寫紀錄，未覆寫或重複提交其內容。線上刷新／重新進入／確認後進度與Lumi回饋仍須獨立實測。
- Google GIS 真實登入 NOT RUN；需先取得唯讀DB證據、既有Client HTTPS Origin及啟用核准。
- AI 真實生成不在本分支；相關整合保持獨立審查。

本候選未部署，線上仍是上一個已核准版本；未執行 Migration、GRANT、IAM、Secrets 或雲端服務變更。
