# Windows 全量合成回歸分層契約

來源基準：31fce0393027466286fbe46b452814f8605b4f07。本次僅調整測試契約，產品 fail-closed 不變。

## 平台界線

- Windows EvaluationStore 產品停用。10 個原有 POSIX 儲存成功功能案例逐項明示不適用，不能計作 Windows 功能通過；同一候選仍在 POSIX 執行這些原斷言。
- 四個 invalid-case 改直接呼叫 validate_case 並核對 synthetic_case_required，避免誤把平台拒絕當輸入檢查成功。
- 新增7個原生非POSIX拒絕案例：constructor及六個CLI，未修改平台值，Path/sqlite操作以禁止哨兵確認尚未存取。此證據不代表Windows ACL已實作。
- 既有模擬非POSIX案例保留；gateway/Gemini等平台無關測試不整檔跳過。

## 合成 PostgreSQL 分階段

核心 PG catalog 契約固定32表、60FK、207欄位。owner matrix 的兩張合成 memory 表尚非核准產品migration，不能把原catalog斷言改成34表來混同。

專用啟動器建立一個全新可丟棄PG18容器：
1. 原bootstrap建立32表dev及獨立Alpha合成庫。
2. core階段跑 tests，僅將5項owner matrix明確留到下一階段；保留全部原catalog、安全和最低權限斷言。
3. core完成後才安裝兩張memory fixture表，核對schema及最低權限，再跑原5項matrix。
4. 不在加表後重跑32表catalog，不以TRUNCATE假稱刪表。最後只清除此run專屬容器與暫時合成密碼檔，保留報告。

期望收集（本次新增5個fixture回歸後）：core590項、matrix5項；Windows只允許列出的10項POSIX-only排除，其餘skip或缺漏、重複、backend錯誤、17項核心PG或5項matrix失敗均不接受。使用共享app fixture的案例必須有實際postgresql證據；刻意SQLite相容性測試仍明確是SQLite，不能稱全部測試皆PG。

## Node及其他界線

啟動前需要已安裝Node絕對路徑；缺少即停止，不下載、不把JS測試跳過當完整通過。執行Node契約不等於真瀏覽器旅程、人工聽審或UI驗收。

不連Cloud SQL，不讀E2E業務資料，不改使用者原repo，不推送、不部署。使用者尚須明確同意新run後自行啟動；助手不操作曾被拒的Docker pipe。

## 已有證據

- 原31fce0專用Windows PG owner矩陣：run e9177173d3cc44c28af9352e6a3bb947，2026-11-10T03:51:19.495881+08:00，5/5 passed、0skip、exit0、cleanup_confirmed=true；各項postgresql，重建Database實例亦postgresql。不是OS程序重啟。
- 本次測試契約修訂POSIX完整離線回歸：566 passed、24 skipped（17需專用PG、7需原生非POSIX），41.18秒。10項POSIX儲存功能實際執行，Node可用。外部Python socket已阻斷。
- 本次Windows全量及真PG分階段流程尚未執行，不能沿用前輪結果冒稱通過。

## 首輪完整 Windows 實機結果與限流 fixture 修正

23ca1d5 實機 run `b78364a1626749bb8c07d9d6f07b8e93`：core於2026-11-10T05:59:14.915089+08:00開始，573 passed、2 failed、10個具名POSIX skip，105.88秒；17項專用PG通過。matrix 5/5真PG通過、0skip，7.257秒。overall exit1、cleanup_confirmed=true。此結果不是全套通過。

兩個限流案例在測試本體執行前被backend guard拒絕：模組內app fixture覆蓋共用fixture，直接建立SQLite。這是測試環境整合缺口，該兩例沒有執行到401/429斷言，不是已證實產品限流失效。修正為PG模式透過既有pg_support.database建立受marker保護的合成DB，保留PG設定並加上限流設定；PG初始化失敗原樣傳出，不回退SQLite。原backend guard及安全斷言不變。

另修正訪客案例的服務生命週期：原每個visitor退出即關閉整個app，SQLite可重新連檔但PG pool關閉後不能重用。使用單一外層TestClient維持服務lifespan，內層11個獨立cookie訪客依次測試，最後才關閉一次；不改產品pool生命週期。新增受控mock先證明舊行為過早關閉，再驗證11個獨立cookie jar及最後一次close。

新修正仍待使用者新一輪真PG執行，不能把mock或SQLite結果當成真PG限流通過；不重用已清理的上輪容器。

本次fixture修訂完整POSIX離線回歸：571 passed、24 skipped（17需專用PG、7原生非POSIX不適用），37.55秒。未操作Docker，真PG限流兩例仍待執行。
