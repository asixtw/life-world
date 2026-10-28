# 交付進度（2026-10-28 16:47 UTC）

## 已實作與已驗證

- 來源共同 commit `1c9d502f32688bcc3c73e4b99a2cc3724c179047`；本地分支 `work/ousang-full-kit`。只新增 `collaboration/ui-kit/`，正式 App／DB 未修改。
- `package.json`、`pnpm-lock.yaml`、Vite／React／TypeScript 專案可建置。Node 24.22.1、pnpm 12.16.1、Vite 7.1.12、TypeScript 5.9.3。
- `src/contracts.ts`：Persona、Scenario、DialogueTurn、SimulationSession、SourceRef、AssetRef、LiveAdapter、HatchEvent 型別；`src/engine.ts`：腳本分支、session 隔離、匯出與即時模式未設定錯誤。
- `src/components.tsx`、`src/Hatch.tsx`、`src/FlowSamples.tsx`、`src/App.tsx`、`src/styles.css`：獨立 gallery 的按鈕、表單、排程、Dialog、Quiet／減少動效、孵化、登入／目標／世界／關係／回饋構圖、附件與錄音狀態展示；`src/Theater.tsx` 為待內容注入的劇場元件。
- 本機執行 `tsc -b`、`vite build`、`vitest run`：build 通過；2 個測試檔、8 個案例通過。
- Chrome 本機展示實際開啟；桌面總覽、元件、紀錄和 Quiet，以及 390×844 手機孵化頁已檢視。孵化開始→跳過→完成、減少動效切換已操作；Dialog 初始焦點與 Escape 返回已操作；錄音失敗後文字仍保留。可見按鈕均 ≥44 CSS px，手機無水平溢位。完整逐頁手機視覺與鍵盤巡檢尚未執行。

## 卡點與未完成

- 人物名單：規格文件列三國歷史人物／職務代表／哲學家；使用者已核准的長版測試卡則為原創沈知衡。Boyi 正在決定採哪一套。`content/catalog.ts` 暫留空，不把任一名單擅自視為定案。十五位肖像、三封面、六場景、45 段例子和 30 個保留情境均待名單決議。
- 共用插畫由父任務製作。`Hatch.tsx` 目前用程式圖層供狀態測試，實際生成圖未接入；manifest、原稿與尺寸輸出未完成，不應標資產驗收通過。
- 協作圖像工作流回報八張共用插畫原稿已生成；`shellsplit`、`completion`、獨立養分光效、`world-base` 四項生成遭工具阻擋，沒有輸出。目前不得標完成或以占位圖充數；需另取得可行且獲准的資產途徑後再驗收。
- 八張原稿與衍生檔的兩份 Library ZIP 已定位，並取得可驗證傳輸資訊；在本機 Windows 使用官方傳輸 helper 時因 `os.setxattr` 不存在而失敗，目標目錄沒有建立 ZIP。因此尚無任何原稿本地接入。傳輸資訊暫存已清理。此動作是環境不支援而失敗，不是使用者拒絕；結果已確定未安裝。
- 即時 AI 端點未指定，`LiveAdapter` 可替換但未驗真實服務。

## 共用插畫接入檔名與錨點

請提供透明背景的 `assets/originals/lumi.png`（Lumi 正面全身）、`assets/originals/egg-idle.png`、`assets/originals/egg-glow.png`、`assets/originals/egg-crack.png`、`assets/originals/egg-open.png`（分離蛋殼）、`assets/originals/hatch-complete.png`（Lumi／蛋殼定格）及 `assets/originals/app-icon.png`（1024 方形）。若原稿為整張分層 sheet，請同時附狀態區域與錨點座標；可由本地裁切。孵化主畫面使用約 300×300 CSS px 容器，視覺中心錨點 `(0.5, 0.5)`，蛋底部約在容器 80% 高；手機約 270px 高。原稿最好 ≥1024×1024，便於產生 512／192／180／48 等縮圖。共用角色維持暖奶白圓蛋身、雙葉芽、深綠直橢圓眼、金黃小喙及薄荷翅膀。每份原稿請附生成工具、提示詞摘要與日期，供 manifest 紀錄。

尚待的分享圖 1200×630、方形縮圖、房間／世界基底、正向回饋插畫可合併於共用批次，路徑建議放 `assets/originals/`，本地會產生 `assets/display/` 與 `assets/manifest.json`。

## 階段性打包

本地 WIP 原始碼壓縮包：`C:\Users\t6vmp\Documents\Codex\2026-10-29\task\life-world-ui-kit-wip.zip`。它只包含已提交的程式、契約、鎖定檔與文件，**不包含**未取得的插畫、十五位人物或六場劇情，不能當最終交付。瀏覽器畫面已實際目視檢查，但因目前工具沒有可寫入套件的截圖儲存路徑，尚無檔案化截圖證據。
