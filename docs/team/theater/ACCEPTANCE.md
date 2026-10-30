# 人物劇場 v0.5 Wireframe｜驗收紀錄

更新：2026-10-30。本文件只驗收獨立 HTML／CSS／JavaScript 線框，不代表正式 App、API、資料庫、真實 AI／ASR／圖片辨識已整合。

## 本輪驗收

- TDD 紅燈：新增劇場測試先因缺少「建立我的情境」入口失敗；實作後重跑。
- `.venv/bin/python -m pytest browser_tests/test_flow_wireframe.py browser_tests/test_theater_wireframe.py -q --tb=short`：**28 passed，0 failed，0 skipped**（本機 Chromium；包含七種預寫行為、返回／刷新接續）。
- 390×844 與 1440×1050 的單人／多人、停止／介入、沉默／故障、Lumi 隔離、額度收尾、刷新、刪除及舊完整流程回歸均已用瀏覽器案例操作。
- 畫面截圖已於本機檢視；本輪不公開測試時產生的截圖。房間與 Lumi 是 PR #2 候選資產；三組封面、十五張示範人物頭像保持原比例，獨立於真實人物資料。
- 外部 API 請求及正式虛構示例的目標／人物／紀錄／積分變更：瀏覽器案例檢查為零。

## 明示未驗證

- 未做 iOS／Safari、實機麥克風、真實轉錄、真實人物 AI、自主 C1 調度或實際費用量測。
- 1v1 8 次、多人 6 次、每段最多 3 則、Lumi 2 次與技術重試 1 次只是線框測試配置，正式上限待工程提案及產品核准。
- 線框資料僅在瀏覽器 localStorage；清除瀏覽器資料會消失，沒有後端權限或私密儲存保證。
