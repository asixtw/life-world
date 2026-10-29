# LW-SIM-001／LW-UI-001／LW-ASSET-001 更新交接

## 任務卡

| 欄位 | 狀態 |
|---|---|
| 主責／審查 | 歐桑；Boyi 產品／內容、Jerry 技術／正式接入 |
| 目前狀態 | 接入實作、單元／型別／建置及本輪六張靜態畫面核對完成；待審查，不等於 Boyi／Jerry 驗收 |
| 共同規格 | `1c9d502f32688bcc3c73e4b99a2cc3724c179047` |
| 恢復來源 | `LifeWorld_ui-kit_full_b3a715c.zip`，SHA-256 `0683792faff60acb7d3adf01f0a7a5c854e9ee49853d8669ea872123fe9a5cf0` |
| Git 邊界 | 本地工作樹以 b3a715c 為上一提交；本輪新增內容與驗證證據另成提交 |
| 目錄／分支 | 僅 collaboration/ui-kit；work/ousang-full-kit 待審查分支，不改 main |
| 最新使用者範圍 | 三張新圖接回 UI 後再上傳；世界基底先延後；人物以創作合理性／角色一致性為主；互動測試延後 |

## 本次變更

- Hatch 將 open／complete 接回專用分離蛋殼與完成定格；保留 deepcrack 獨立階段，回執、重播、跳過、取消仍不改帳本。
- PositiveFeedback 在人工確認 fixture 與流程回饋中組合獨立養分／Lumi；無回執不顯示。無聲定格，Quiet 降低光效亮度。
- 三張 1254 RGBA 原稿、生成來源及 SHA 保持原檔，清單新增實際狀態、尺寸、錨點、限制；AssetGallery 與舊缺件文案更新。
- FlowSamples 補四主分頁樣板、麵包屑、目標／故事卡；不改正式導覽。
- content/original-enthusiasts 追加十五原創 TXT、索引及重算摘要。HS01 exact hash 保持；不替換原三國／職務／哲學十五人。
- ArtReview 為共享實際元件的只讀固定 fixture；新測試／靜態截圖腳本與本交接可供接續。

## 實際驗證與限制

本輪 `pnpm test` 6 檔／22 案例通過；`pnpm build`（tsc -b + Vite）通過。日誌在 `docs/qa/20261029/`。新圖原像素與 alpha 實測通過，所有 top-level 清單路徑存在。15 份追加卡的 60 段各 1000 漢字與 HS01 雜湊通過。

**本輪靜態版面 gate 已通過，仍非完整產品驗收。** 在受核准的本機 Windows Chrome 環境，以暫時 Vite localhost 服務執行 `tests/static-art-qa.mjs`，六個 day／quiet／reduced × 390／1280 固定畫面全數載入；無破圖、水平溢位或仍運行的動畫。六張真實 PNG 已目視檢查分離蛋殼、完成 Lumi、養分層級、留白與 Quiet 呈現，見 `docs/qa/20261029/art-*.png` 與 `static-layout.json`。舊 `static-layout.txt` 僅記先前失敗，不代表最終狀態。

`pnpm dev --port 5174` 保持運行，另一終端 `node tests/static-art-qa.mjs` 可重現固定 fixture；只讀取 `?art-review&mode=day|quiet|reduced`，390×844／1280×800。可設定 `CHROME_PATH`。本輪沒有執行 qa:visual 舊互動腳本；新互動、Safari、實機延後。

## 美術與接入契約

Hatch 容器維持 300px（手機270px）高；新增圖以 contain、最大276px／12px安全留白呈現，錨點 (0.5,0.88)。回饋為最大300px正方形、光效全幅在後、Lumi 84%居中在前，Quiet opacity .38、日間 .65。所有模式無聲且定格，不依賴動畫完成才可繼續。

PNG 是平面原稿：蛋殼兩半仍同一檔，完成 Lumi 與殼亦非獨立圖層；獨立蛋／分離殼／完成／養分檔可組合，無 PSD 或原生向量宣稱。新圖細 alpha 斑點及完成圖窄側邊保留；六張固定合成畫面已目視核對，仍待產品美術審查。未重採樣導出另尺寸；原稿兼 runtime 來源，CSS 控制顯示。

## 不變內容與後續

規定 15 人、6 場、18 主路徑、90 人物專屬首輪回應、45 多輪示例（每例至少4輪）、30 保留評估題及參考隔離仍保持。資料 reviewed=false 不改成通過；先前機器來源定位紀錄只屬歷史，不把創作任務變事實考核。即時 AI 端點／金鑰／正式 App、DB、部署與 Summit 不在範圍。

世界基底及新互動測試明確延後；其餘十三類與最終靜態 gate 見 [13_CATEGORY_AUDIT](13_CATEGORY_AUDIT.md)。Boyi／Jerry 尚未審查；只有真實對應檢查與審查後才可更新為已驗收。
