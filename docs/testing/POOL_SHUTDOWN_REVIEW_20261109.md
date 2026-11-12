# PostgreSQL pool 清理與 shutdown 定點修補

日期：2026-11-09。基底：GitHub main `68102f230aa947a434286ba9260e1ae75f6634b0`。

## 範圍與行為

只修改 `app/postgres.py` 的連線歸還與 `close()`，新增兩個測試檔。未修改 runtime、API、schema、部署設定、資料庫設定或產品規則。

- 連線歸還和 shutdown 摘取 idle 連線共用短鎖，避免 close 返回後才把連線放回池。
- driver／Connector 的 close 保持在鎖外，避免外部清理阻塞 pool 臨界區。
- raw.close 失敗時仍釋放 semaphore 名額；不可重用的連線不放回池。
- shutdown 嘗試清理全部已摘取資源，再重拋第一個原始例外；queue.Empty 清理例外不再誤當作佇列已空。

## 本輪實際驗證

- 最新 main 加上18個合成測試、尚未修程式：522 passed、8 failed、17 skipped，42.14秒。
- 套用修補後完整 API／SQLite 與 Node 契約：530 passed、0 failed、17 skipped，44.28秒。
- 紅綠 JUnit 逐案例比較：總共547項，相同8項從failed變passed，其餘539項狀態不變。
- 獨立審查另外重跑新增18項：18 passed，diff --check通過。
- 13 warnings為既有record_property與JUnit xunit2格式不相容，不是產品失敗；保留未消音。
- 17 skipped全部要求專用PostgreSQL18，未執行的真PG不算通過。
- 以既有requirements.lock與requirements.api.lock建立隔離環境，66個適用套件pin全部相符，pip check通過。初次未補齊Google依賴的collection error另列為環境失敗，不算功能紅燈。

本輪測試使用全新暫存合成資料與最小環境，未繼承帳號、Google或LIFEWORLD設定。pytest程序的socket connect、connect_ex與create_connection均阻斷；Node只執行既有本機契約。這不是OS層完整子程序網路隔離。

可重現定點命令：`python -m pytest tests/test_pool_shutdown.py tests/test_shutdown_support.py -q`；完整回歸：`python -m pytest tests -q`。只能在隔離合成環境執行，不帶正式服務／資料庫設定。

## 保留限制

- 未解決完整connect／_open／Connector初始化與close競態。
- close不等待active borrowers，返回不代表所有連線已關閉。
- repeated／concurrent close的Connector exactly-once未解。
- connect中的raw.close失敗仍可能覆蓋原交易錯誤，為既有行為；本次只保證歸還名額。shutdown重拋首錯，後續清理錯誤沒有新增彙整介面。
- 合成Mock／thread測試不代表真PostgreSQL、Cloud SQL、TLS、瀏覽器或正式部署通過。

本修補只供獨立分支審查。未推main、未部署、未呼叫線上ready、未更改Cloud SQL／IAM／網路。

## 2026-11-09 第二輪隔離生命週期檢查

基於 core/audio 候選 `66fd8d42ad99c8018e933744df6b9b5a7c62b490`，新增四個合成測試先確認全部因行為錯誤失敗，再修補：

- 在 mutex 內摘除 Connector，將清理責任移交給唯一 close 呼叫；重複或並行 close 不再重領同一 Connector。
- Connector factory 前在同一 mutex 下檢查 closed，阻止 shutdown 後重新初始化。
- connector.connect 使用鎖內取得的區域參照，避免共享欄位被 close 摘除後讀到 None。
- raw 開啟後再次在 mutex 下檢查 closed；若 shutdown 已發生，不交出新交易，沿既有 finally 清理 raw 並歸還容量。

新舊定點測試合計 22 passed。active borrower 已交出的交易仍沿既有非等待式 shutdown 語義完成，退出時關閉 raw；close 返回不代表 active raw 全已關閉。交易准入判定在 raw 取得後的 mutex 檢查處，之後 shutdown 不追溯取消已准入交易。

本節修補時尚未處理 Connector.connect 與 Connector.close 重疊；下一節補上責任移交。factory 仍在 mutex 內，慢 factory 可能延遲 close。清理失敗不自動重試（避免重複副作用），connect 的 raw.close 失敗仍可能遮蔽原交易錯誤。只用合成 Mock/thread，沒有真 PG、Cloud SQL 或部署證據。

修後完整離線回歸：536 passed、17 PostgreSQL skipped、13 既有 JUnit warnings，46.51 秒；沒有把 skipped 計為通過。定點紅燈 4 failed，修後 22 passed。原候選完整回歸為 532 passed／17 skipped。測試最小環境及 Python socket 封鎖仍沿用，並非 OS 子程序完整網路隔離。

### Provider 開啟與關閉重疊的責任移交

再新增四個案例（1／2 個受控 opener、provider 與 cleanup 同時失敗、cleanup 失敗時未返回 raw 清理），先確認 4 failed／前輪 4 passed，再以 opener 計數修補至新舊 pool 共 26 passed。

每個 cloud provider.connect 在 mutex 內取得 Connector 參照與 opening 名額，網路呼叫在鎖外。close 對有 opener 的 Connector 只標記關閉，不等待 provider；最後一個 opener 返回或失敗後，在 mutex 內摘除 Connector、鎖外清理。因此 Connector.close 不再與此 pool 的 provider.connect 重疊，重複 close 也不重領資源。若清理失敗導致 _open 無法返回，會嘗試關閉已取得 raw；provider 與 cleanup 都失敗時保留較早的 provider 錯誤，後續清理錯誤不另行彙整。

上述內容取代前文「並行 close exactly-once 未解」及「provider.connect/close 重疊未解」限制，只涵蓋此 pool 管理的 Connector。close 仍不等待 active borrower 或 opener；若 provider 永久不返回，清理也會延後，沒有新增強制取消或 timeout 契約。factory 仍在 mutex 內，慢 factory 可延遲 close；外部私自使用 Connector 不在保證範圍。真實 Cloud SQL driver 行為尚未實測。

責任移交版完整離線回歸：540 passed、17 PostgreSQL skipped、13 既有 JUnit warnings，44.67 秒；定點26 passed。此結果取代前一輪536 passed作為本候選最新回歸，歷史紅綠紀錄保留。

獨立審查重跑26 passed，未見阻擋問題；依其建議補上 closer 例外捕捉與按 opener 身分確認完成事件。測試補強後最終完整回歸仍為540 passed、17 skipped、13 warnings，43.70秒；產品程式與上一輪相同。


### 2026-11-09 整合證據補充（取代上文「最新」的時間性敘述）

完整整合版離線回歸為 **549 passed、17 PG skipped、13 warnings**。上文540屬歷史pool階段結果。OSSANG先前專用PG18執行17必測全通過，但該次整體542 passed、2 failed、13 Node skipped，且早於最後整合；不能當成本head完整Windows回歸。新core在Windows實機記憶體載入的constructor及6個CLI拒絕probe已通過，僅證明fail-closed路徑，不是Windows全功能或ACL驗收。詳見 `CORE_SAFETY_INTEGRATION_20261109.md`（位於 docs/testing）。三線完整驗收仍未完成。
