# GCP-144 RC v3｜受保護Staging POC候選

日期：2026-11-08。精確Parent：PR17 `4bdc3df61aa9827a12aeee0b20b2af0eb4f4bde4`；Draft PR Base為`codex/gcp143-staging-test`（PR15 `7385150064484de0807aabdd6d23a8d2779acddb`）。PR16 `1ebc79efae0b752e1d876b4692a7498cb4606eff`及PR18 `8a5e50daddc086de9682d0346e56246de233163d`以精確hunks整合，不Merge四個PR、不改main。

## 交付一致性

37檔是相對PR Base的完整候選；Parent已含Core UI的部分檔案，不能要求Parent增量sections也等於完整檔數。完整RELEASE.patch與PARENT_DELTA.patch各自列明base／sections／SHA，實際套用後必須得到同一Tree。v3 Manifest以本檔所在Commit為候選，在Git之外避免自引用雜湊；舊35檔封存不得當v3。

## 測試範圍

| 類別 | 結果／真實範圍 |
|---|---|
| Full API | 424 passed／28 skipped；精確Commit重跑日誌另綁Commit。17項缺合成PG、11項缺Node |
| AI／Security定點 | 60 passed，包含registered／CSRF／跨Owner、失敗人工退路、24h額度／重啟／並發 |
| PostgreSQL Adapter contract | 本輪單獨重跑，結果記v3證據包；不冒稱真實PG SQL驗證 |
| Chromium核心／Fixture | 2 passed，桌面與手機；目標、三習慣、三次孵化、草稿、確認／重送／刷新／Lumi |
| Lumi／Loading隔離 | 本輪另跑，結果記v3證據包，不沿用舊8項冒稱新跑 |
| 真實Gemini Browser | 2次HTTP200，3.5 Flash-Lite；12項Browser操作檢查PASS，既有合成SQLite。Call2 tasks空，人工任務不能冒稱AI輸出 |
| PostgreSQL正式讀回 | NOT RUN；007／008未執行，無受保護Staging部署核准 |
| 真實Google GIS／新瀏覽器回訪 | NOT RUN；不可用本機合成帳密／Fixture取代 |

真實AI詳見[AI驗收與後續ADR](../ai/GCP144_AI_ACCEPTANCE.md)。本輪所有資料均為合成；不再以未來CRM個資方案延遲合成POC。實際Gemini費用null，無自動重試或Billing修改。

## 保留的安全與已修正問題

保留PR15 Google-only、IAP、Guest原地升級／明確衝突選擇、Session／CSRF輪替、放棄Guest14天tombstone及Owner隔離。AI不直接改正式事實／進度／獎勵，Fixture明示替身。

修正永久全域AI次數／費用耗盡為24h窗；增加跨日、重啟、並發。兩份舊Guest能力測試加入Guest403／零Provider斷言，再用註冊者到達原本失敗及跨App隔離驗收，不降低安全標準。

## 最新DB與部署Gate

Owner已完成01／02及04的31表盤點；users=3、sessions=1、requests=7、reward_ledger=3、goals=1、experiences=3、drafts=3、actions=3、contributions=3、experience_stories=3、habit_quantity_versions=3、auth_rate_buckets=4，其餘已查表0。保留全部資料，不TRUNCATE／DROP／重建／清requests或帳本。007／008未執行，external_identities／guest_abandonments缺少；03完整有效權限與DBA收據仍待證據。

備份／PITR／Deletion Protection及列表依本輪重新唯讀結果記錄於包內；未有成功備份前先交按需備份提案，不自行執行。007／008 DDL、SHA、最小GRANT、前後筆數及回復另包審查，不執行SQL／GRANT。

現有Staging仍IAP保護；不得allUsers、不得新服務或DB。本輪只授權RC Commit／非main Push／單一Draft PR，未授權Merge／Build／Deploy或公開切換。受保護Staging部署需備份、DB Gate與精確image／revision計畫另批；回復保留新增表與身分資料，不採DROP式rollback。
