# LW-SIM-001／LW-UI-001／LW-ASSET-001 交接

| 欄位 | 狀態 |
|---|---|
| 主責／審查 | 歐桑主責；Boyi 產品與內容、Jerry 整合審查均待進行 |
| 共同來源 | `1c9d502f32688bcc3c73e4b99a2cc3724c179047` |
| 工作分支 | `work/ousang-full-kit`，僅 `collaboration/ui-kit/` |
| 名單決議 | 使用者選 A；本包依任務文件十五人，沈知衡另屬原創長版卡 |
| 狀態 | 部分交付，非最終驗收 |

## 接入與驗證

React＋TypeScript／Vite 專案、鎖定檔與啟動方法見 [README](../README.md)。`content/` 放十五人、六場、45 示例與來源；`evaluation/inputs.v1.json` 和 `reference.v1.json` 分離 30 題的模型輸入與參考；`assets/manifest.json` 指到已驗證的共用原稿與輸出。十五頭像與三封面已接入，映射見 `assets/persona-art-map.v1.json`。

最近一次 `tsc -b`、`vite build`、`vitest run` 通過，61 模組與 12 案例。Chrome 已操作選角、來源、分支結尾、返回與手動匯出；匯出 JSON 已在 `Downloads` 讀回並核對 `demo` 隔離欄位。390×844 新劇場與美術頁無水平溢位、小按鈕或破圖；先前五頁及 1280×800 桌面基本檢查通過。未測實機、Safari、真實 AI 或正式服務；沒有可寫入套件的瀏覽器截圖檔。

## Jerry 接入要點

1. 保留 `usageScope=demo`、`exportKind=life-world-simulation` 與 `importToRealExperience=false`；不得直接寫正式人物、經歷、積分或收藏。
2. 對 `Persona`、`Scenario`、`SourceRef`、`AssetRef`、`SimulationSession` 與 `LiveAdapter` 審查型別、版本、來源和檔案存在性。`reviewed=false` 的來源需人工核對；評估參考答案不得注入模型輸入。
3. 即時端點由宿主注入 adapter，處理權限、取消、重試與祕密金鑰；前端無供應商或 key。未設定時保留預寫腳本退路。
4. 孵化只接後端唯一 `confirmedReceiptId` 顯示，不因重播、跳過、關閉再計分。Lumi 是每位使用者一個常駐陪伴者。
5. 人物入口、圖像及來源由 Boyi／Jerry 審查後才考慮正式 App；本包無正式路由變更。

## 剩餘缺件

分離蛋殼、完成定格、獨立養分光效、世界基底；Boyi／Jerry 審查與實際截圖檔。共用美術原料依使用者指定本地 ZIP 取得，兩份 Library ID 與 SHA256 見 [進度](PROGRESS.md)。Windows 官方 Library helper 的 xattr 步驟失敗，本地檔案沒有 Library metadata；未修改 helper。十三類逐項見 [盤點](13_CATEGORY_AUDIT.md)。
