# 目前開發快照｜同仁審查入口

> 2026-11-02 後續修正及資料庫交接請讀[本輪審查入口](RELEASE_REVIEW_2026-11-02.md)。下文保留 11/1 的歷史狀態，不代表後續缺陷仍全數未修。

日期：2026-11-01（Asia/Taipei）。本分支供程式、資料與體驗審查；不是正式發布或部署，也未合併 main。請用虛構測試資料操作。

本次依 Boyi 指示保留 `docs/EVOLUTION.md` 的本機新版，不納入這次推送；分支內該檔維持 main 已有版本。請以本入口、實際程式及各功能驗收紀錄判讀本次快照。

## 先確認你正在看哪個版本

| 入口 | 實際範圍 |
|---|---|
| [Python App](../README.md#啟動) | App v0.4.0，FastAPI／SQLite／原生前端；包含單一目標、三習慣、到期回顧、未來用量版本、人物與交會，以及本機素材流程。 |
| [完整流程 Wireframe](../collaboration/flow-wireframe/index.html)／[操作說明](../collaboration/flow-wireframe/README.md) | 較新的劇場 v0.5、7×4 月循環、人物草稿、活動關聯與點擊孵化；對話、辨識及額度是本機模擬。這些互動尚未全部接入 Python App。 |
| [UI kit](../collaboration/ui-kit/README.md) | 歐桑的獨立 React／TypeScript 元件與美術候選，沿用 main 已合併內容；不是 App 已全面採用的畫面。 |
| [資料字典](DATABASE_SCHEMA.md)／[PostgreSQL 接續規劃](database/POSTGRESQL_HANDOFF.md) | SQLite 001–005 的結構與候選遷移方向；只有結構 metadata，不含資料庫檔、帳號、客戶資料列、實際媒體或憑證。PostgreSQL／GCP 尚未部署。 |

本快照以 GitHub main `8513b55` 為基底，納入本機目前的公開程式、原型、測試與交接內容；也包含先前尚未發布之三筆本機提交的內容。原始本機分支、index 與工作檔保留。

## 取得與啟動

```bash
git clone --single-branch --branch review/current-state-2026-11-01 https://github.com/asixtw/life-world.git life-world-review
cd life-world-review
python3 scripts/setup.py
.venv/bin/python -m app
```

App 開啟 `http://127.0.0.1:8000`。沒有內建帳密，請用虛構資料完成首次引導；一般安裝不會接上分享者的資料庫。

另開終端機，在 Repository 根目錄提供靜態原型：

```bash
python3 -m http.server 8011 --bind 127.0.0.1
```

開啟 `http://127.0.0.1:8011/collaboration/flow-wireframe/`。可按「載入虛構示例」，或從首次設定走流程。原型只使用這個瀏覽器的 localStorage；不同連接埠或瀏覽器不共享原型紀錄。

## 請優先審查

1. **人物劇場的場次生命週期**：草稿、目前場次與歷史必須分開；先重現下方缺陷，再提出修正與回歸案例。
2. **目標與經歷資料**：單一目標、三習慣、日期／時區、關聯與實際投入分離、待回顧貢獻及重送去重。
3. **人物與故事**：多人關聯、新人物先留草稿、實際參與／僅被提及的區分、來源、跨帳號及私人模擬的界線。
4. **操作體驗**：手機與桌面的日期選取、返回／刷新、錄音權限、附件與校對、版本衝突與失敗重試。
5. **工程接續**：素材提供者介面、實際手機格式、雲端留存與刪除、PostgreSQL 遷移及 GCP 部署；待決事項不要當成已落地能力。

回報請附「所在入口／頁面、前置資料、重現步驟、預期、實際結果、裝置／瀏覽器、證據、優先度」。回報缺陷不需要真實客戶內容或 API Key。

## 已知問題與交付界線

以下六項在 localhost 的隔離 Chromium 已重現，仍未修復，不能因既有測試通過就視為劇場可封測：

| ID | 已知問題 |
|---|---|
| LW-01 | 改動另一份草稿的人物會影響目前場次的顯示及回應依據。 |
| LW-02 | 建立新情境可能直接回到上一份草稿的預覽步驟。 |
| LW-03 | 開始新場會靜默覆蓋尚在進行的場次。 |
| LW-04 | 查看歷史會覆寫目前場次，無法繼續原場。 |
| LW-05 | 清除主原型沒有清除劇場命名空間的全部紀錄。 |
| LW-06 | 服務錯誤重試成功後，玩家行動數可能仍為 0。 |

LW-09 舊多人歷史及 LW-10 載入示例的覆寫處理仍待接續。LW-07 未選目標仍關聯、LW-08 期間外直接採計，已在**新版原型**修正並加測；不能直接推論正式後端也完成相同修正。詳見[劇場與原型驗收](team/theater/ACCEPTANCE.md)。

其他限制：

- 外部 STT／VLM 尚未設定，App 預設辨識回覆 503；原型的成功畫面是明示模擬。
- 真實手機 Safari、軟鍵盤、多裝置、負載及部署沒有因這份快照而完成驗收。
- 原型封測不提供積分；App 仍有既有積分閉環，規則與介面尚待整體對齊。
- 歷史文件內「尚未發布」等字句是當時狀態；這份入口記錄本次審查快照，不修改那些歷史測試結果或將它們當成本次測試。

## 本次驗證

- 後端：`.venv/bin/python -m pytest -q --tb=short` → **176 passed，0 failed，0 skipped，9.65 秒**。
- 瀏覽器：完整 `browser_tests` → **89 passed，0 failed，0 skipped，143.43 秒**；使用隔離資料、明確的測試時鐘，截圖輸出改放測試暫存目錄，未修改測試斷言。可重現啟動方式見[目標驗收](GOAL_FLOW_ACCEPTANCE.md#可重現命令)。
- 結構檔核對為 DDL／metadata，沒有資料列；本機私人文件、金鑰、SQLite、錄音與上傳素材不在分享範圍。
- 測試通過代表涵蓋案例通過，不取代上述已知缺陷、實機或人工 UX 驗收。

需要接續的共同規格與分工，見[規格索引](SPEC_INDEX.md)、[協作入口](team/README.md)、[素材契約](team/MEDIA_COMPONENT_CONTRACT.md)。
