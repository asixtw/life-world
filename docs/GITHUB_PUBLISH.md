# GitHub 共同基準｜發布前檢查

日期：2026-10-28。使用者明確要求將目前 App、共同產品規格、協作及檔案存放規則發布至 `asixtw/life-world` 的 `main`。這份文件隨發布 commit 保存，實際 GitHub commit 由發布後核對並提供給團隊；不以文件存在聲稱遠端更新成功。

## 範圍

- 現有 v0.3.0 App、交會／人物流程、測試及虛構畫面證據；這些變更先前留在本機工作目錄。
- [共同規格](SPEC_INDEX.md)、[產品基準](PRODUCT_BASELINE.md)、[存放規則](STORAGE_RULES.md)、[協作流程](../CONTRIBUTING.md)及[三人工作包](team/README.md)。
- 原有父提交為 `988c8d82a21f6d2e83a37ae4a8cdd97f0d272ca4`；上傳前核對遠端父版本，不強制覆蓋其他人新提交。
- 不包含使用者資料、DB、實際憑證、私有備份、虛擬環境、外部歷史原型。公開測試截圖沿用使用者先前明確同意的虛構素材範圍。

## 本輪實際測試

| 驗證 | 命令／隔離條件 | 結果 |
|---|---|---|
| 後端 | `.venv/bin/python -m pytest -q` | **100 passed in 6.20s**，見[後端紀錄](GITHUB_PUBLISH_BACKEND.txt) |
| Chromium | `LIFEWORLD_TEST_URL=http://127.0.0.1:8012 .venv/bin/python -m pytest browser_tests -q -x --tb=short` | **14 passed in 36.67s**，見[瀏覽器紀錄](GITHUB_PUBLISH_BROWSER.txt) |

測試服務只監聽 `127.0.0.1:8012`，使用 `/tmp/lifeworld-github-publish-20261028` 的隔離虛構資料，沒有讀取或遷移真實使用者 DB。沙箱初次禁止 bind，改用獲准的本機測試服務及 Chromium 後完成；不是產品功能失敗，也沒有降低斷言。

GitHub 外連在一般 shell 沙箱無法解析，使用已連結且核對有寫入權限的 GitHub 工具發布；不是因此改傳未授權帳號或儲存庫。

## 文件與來源核對

發布前檢查所有可交付 Markdown 的本機連結均在儲存庫內可解析；原先離開儲存庫的七個原型／工作區連結改為明示本機參考文字。檢查候選檔案不含 DB、秘密、安裝目錄及私有備份，並比對既有產品指紋、差異格式與實際 Git tree。

發布採遠端父版本核對與非強制更新；發布後再次讀取遠端 commit／關鍵文件與來源樹，確認後才回報成功。任務狀態仍未代替夥伴領取／審查，不自行配置分支保護或建立雲端資源。

## 驗證界線

本輪沒有完成 React／PostgreSQL 遷移、錄音／影像辨識、Quiet UI 或 GCP 部署，沒有真實 AI／Safari／手機硬體或新一輪負載驗證。100／14 為現有 App 回歸，不替未實作能力背書。App 版本維持 v0.3.0。
