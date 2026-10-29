# v1.1 控制項、生命週期與既有美術候選核對

範圍：`collaboration/ui-kit/` 本地獨立候選；程式起點 `5dbec8688b3fb850053dcd51bb4b17c4c2f7460b`，文件基準 `ae5a9dc57cc49886427d3cb8ac7cc94bdc00065d`。不代表正式 App 整合或 Boyi／Jerry 驗收。

## 本輪可審查內容

- 按鈕：原生 button 的 type、disabled、ref 與 aria 透傳；鍵盤 Enter／Space、可見焦點、pressed、載入停用、hover／active 在隔離頁面驗證。
- 輸入：文字、長文、密碼、數字、日期時間、搜尋、下拉、checkbox、radio、switch 十種受控展示；空白、填寫、說明、錯誤、停用、載入六狀態。錯誤使用 `aria-invalid` 與文字訊息。這是狀態矩陣，產品資料校驗規則未設定。
- 面板：未保存退出提示、保留編輯或明確捨棄、模擬保存失敗保留文字、重試、Toast、長來源抽屜和 Escape；空搜尋、服務未設定、版本衝突、連線失敗有本地展示退路。保存只在此頁記憶體 fixture，不冒充 IndexedDB 或正式後端。
- 轉場／孵化：重播清除舊播放計時，動畫結束事件缺失時有 700ms 有界完成；卸載中的單次取消、回執切換不遲到完成，Quiet／減少動效立即定格。事件仍需正式宿主接入。
- App 圖與人物：`tools/audit_app_persona_art.py` 讀真 PNG、尺寸、SHA256，輸出 `APP_PERSONA_AUDIT.json`。確認 App icon 原稿 1254²，1024／512／192／180／48／32／16 輸出及 48 favicon、1200×630 分享圖；15 組肖像原稿／256 顯示／圓形預覽、3 組 1600×900／800×450 封面。原稿不修改。三張 4:5 中心手機裁切檢查圖僅用於 QA；目視顯示兩側人物受裁，不能用它們聲稱五人均完整顯示。正式手機群像需美術重新構圖，或 UI 採 contain 並核對版面。

## 實際驗證

- TypeScript：`node node_modules/typescript/bin/tsc --noEmit`，exit 0。
- Vitest：`node node_modules/vitest/vitest.mjs run`，16 files／51 tests 通過。
- Vite：`node node_modules/vite/bin/vite.js build`，exit 0。
- 本地 Chrome／Playwright，390×844 與 1280×800：`node tests/v11-controls-qa.mjs` 通過；`node tests/v11-lifecycle-qa.mjs` 通過；既有 `v11-interaction-qa.mjs` 與 `v11-lumi-qa.mjs` 重新通過。這些只連 localhost 的隔離套件。
- 截圖：`controls-input-mobile-error.png`、`controls-panel-mobile-unsaved.png`，以及三張 `persona-cover-mobile-*.png` 裁切審查圖。輸入截圖為整張卡片，面板截圖為確認對話框；不能當桌面全頁證據。人物裁切圖不是運行時資產。

## 十四類候選狀態

| 類別 | 狀態 | 尚缺的具體事項 |
|---|---|---|
| 1 設計基礎 | 可供審查 | Safari／正式宿主 CSS 隔離與安全區需 Jerry 驗證 |
| 2 按鈕 | 可供審查 | 正式宿主鍵盤與輔助技術驗收 |
| 3 輸入 | 可供審查 | 真資料規則與正式保存能力需宿主注入 |
| 4 導覽、卡片、排程 | 可供審查 | 正式帳本／目標保存與跨組接線 |
| 5 面板與回饋 | 可供審查 | 真錯誤碼、保存與路由離開接線 |
| 6 多模態 | 部分完成 | 真麥克風、上傳配額／格式政策、正式權限／後端與 Jerry 審查 |
| 7 App 圖示 | 可供審查 | 平台實機、Boyi 視覺／尺寸驗收；無原生向量原稿 |
| 8 Lumi 與世界 | 部分完成 | 原生 1920×1440 原畫不足、日／Quiet 未像素級同構、人工美術審查 |
| 9 蛋 | 部分完成 | 左右殼非完整蛋同源切片，裂口閉合／逐格連續需原畫 |
| 10 孵化 | 部分完成 | 正式回執／宿主接入及 Boyi／Jerry 動效驗收 |
| 11 正向回饋 | 可供審查 | 人工亮度、視覺節奏與宿主接入驗收 |
| 12 人物美術 | 部分完成 | 手機五人群像保留問題及 Boyi 美術驗收 |
| 13 轉場 | 部分完成 | 逐格／atlas 素材、正式宿主事件與人工動效驗收 |
| 14 音效 | 部分完成 | Boyi 聽審、Jerry 跨瀏覽器格式與正式觸發驗收 |

上述狀態只描述本地候選可審查程度；51 個測試通過不等於十四類全部正式驗收。無真服務、真回執、Safari／實機或人工聽審的通過宣稱。
