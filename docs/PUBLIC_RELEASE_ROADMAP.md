# 公開候選統一進度

更新：2026-11-08。一般工程持續進行；不把未完成真實PostgreSQL E2E的候選稱為完整Beta。

|工作|狀態|證據／下一步|
|---|---|---|
|Product邏輯備份實際還原|PASS|Build 6d320f67-a5cb-4022-91b1-642c3500f516；32表/2收據/筆數一致，臨時IAM撤銷|
|Alpha 01/01B／空庫|PASS（Owner回傳）|非superuser但CREATEROLE/CREATEDB與有效授權通過；核心Schema/角色不存在、表0、counts={}，不重跑|
|公開OAuth Origin|PASS（Owner已儲存）|不重做、不改IAP Client；真實Google登入未驗收|
|02探針／ROLLBACK／正式COMMIT|NOT RUN|[單一交易執行包](database/alpha-02-rehearsal-2026-11-08/02_EXECUTION_GUIDE.md)；只能Owner在原Studio操作|
|Alpha 03–12|BLOCKED|02正式結果確認後，按既有實際SQL逐檔推進，勿混用Product Migration|
|公開登入／訪客入口|PARTIAL|現有封閉入口須補可見方法選擇、安全降級及重試，不假稱資料保存|
|Provider獨立產品能力|PASS（工程測試）|註冊狀態Owner共用AI/劇場/額度；線上PG仍待接通|
|公開Runtime／真PG E2E|BLOCKED|私有Gate仍關閉，無DB/AI Secret；不可用容器SQLite代替保存|
|AI／劇場|PARTIAL|真Adapter歷史測試、最新提示與Fixture契約；本輪不得新增真模型呼叫，網站E2E未完成|
|Lumi／房間／音效|PARTIAL|素材與程式已接入；公開畫面與獨立開關可測，登入世界內旅程待DB|
|PR／正式Release|PARTIAL|PR20維持Draft／未Merge；以精確Commit/Build/Digest/Revision逐次保存，未宣告完整Beta|

Owner只需使用同一Studio進行新02包，不重跑Product Restore、Alpha01/01B、空庫檢查或OAuth設定。若出現回滾殘留或非預期public物件，停止實際變更並回報，不擅改原始02。
