# TDD 與實際驗收紀錄

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
