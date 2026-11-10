# 訪客與Google世界轉換修復（待Code Review，未部署）

日期：2026-11-10。基準：main `68102f230aa947a434286ba9260e1ae75f6634b0`。分支：`codex/google-world-transition-20261110`。

## 根因與修復

1. external_auth的login分支在Google映射不存在時新增registered User，導致「登入以前的世界」建立另一個空世界。改為404 google_world_not_found，不建帳、不放棄。新Google使用者明確以upgrade保存訪客原Owner。
2. 舊同意檢查只保護有Goal／Draft的Guest。現在切換至不同Owner的所有Guest均需明確discard_guest；同Owner永不呼叫abandon。
3. 前端交換後總是重設世界並navigate，丟失未保存表單。upgrade成功只更新Session／資料與導覽，不重繪表單、不改hash、不清原Owner媒體。
4. 網路失敗時只refresh無法區分已提交／未提交。新增Session-bound交換狀態查詢；先GET auth/me再核對收據，不自動重送exchange。未知狀態阻擋其他寫入，保留表單；確認舊交換已失敗或到期後才可重新開始。交換在驗簽及鎖等待後再檢查Challenge期限，拒絕晚到提交。
5. 登入既有不同世界必須經已提交收據確認guest_abandoned，才清來源Owner的IndexedDB及goal草稿；失敗保留可重試清理紀錄，不觸及目標及第三Owner。
6. 清除器只需檢查SQL媒體路徑存在，將SELECT content LIMIT0改SELECT1，避免維護角色被迫取得媒體內容讀權限。Beta CLI的目標限制未放寬，Alpha尚未啟用。

## 交易／資料邊界

- upgrade更新同一User.status並建立映射，Profile／Goals／Drafts／Experiences／Rewards保持不變；不建立abandonment。
- login只接既有Google映射；無映射、衝突、驗簽／CSRF／期限錯誤與交換提交失敗，不建立待清除工作。
- 新Session、撤銷來源Session、abandonment及交換收據在同一DB交易。Google映射沿用唯一鍵與PG advisory lock；不以Email自動合併。
- 成功放棄沿用abandon()：pending、purge_after=abandoned_at+14days。前端明示不合併、至少14天後才符合永久清除條件，**不承諾恢復功能**。
- POST /api/auth/external/status只核對當前Session與CSRF，讀既有requests收據並以owner交易鎖序列化；不改Schema或Runtime ACL。
- 維持現有Session HttpOnly／Secure／SameSite、Origin、Nonce、CSRF輪替與registered能力授權。

## 本輪驗收

原始日誌與SHA256見[evidence](evidence/)。正式Google與隔離測試分開，不用Fixture冒充OAuth。

|情境|範圍／結果|
|---|---|
|原Owner綁定Google、Profile／草稿／進度／獎勵保留|SQLite API及真PG18合成DB PASS|
|原操作位置／未保存表單|Chromium 390px、1440px PASS|
|登入既有Google、14天pending|SQLite API與真PG18 PASS|
|空訪客或有資料訪客未同意|拒絕切換、不產生工作 PASS|
|未知Google映射|404、不新增User、不清Guest PASS|
|取消／驗簽失敗／到期／驗簽期間到期／衝突|API及取消瀏覽器 PASS|
|相同Owner／交換重送／兩裝置同Google|無自身放棄、無額外正式User；兩個來源Guest各一筆待清理 PASS|
|網路回應中斷|Cookie已到達但JSON損壞，核對收據；exchange僅一次 PASS|
|跨Owner本機清理|來源工作區移除，目標／第三Owner保留 PASS|
|未到14天／到期／completed後重送|真PG18維護角色 not_due／completed／noop PASS|
|正式帳號拒刪、跨Owner FK異常|拒刪並留retry錯誤收據 PASS|
|媒體失敗／5次耗盡／中斷後重試|真PG18持久狀態與run_batch PASS|
|清除不改正式Owner資料／Session／獎勵|真PG18資料雜湊逐表前後一致 PASS|
|真實Google OAuth／公開網站修復驗收|NOT RUN，修復版未部署，未控制Owner瀏覽器|
|Alpha Maintenance正式角色／Job／Scheduler|NOT ENABLED；僅審查稿|

本機PG只綁127.0.0.1:57484、固定合成cluster marker，使用lw_alpha_app測試網站DML及獨立lw_alpha_maintenance最小欄位SELECT／限定DELETE角色。實際life_world_alpha Cloud SQL未連線／未變更。SQL清理範圍仍由既有34表／FK契約檢查；新增Hidden Feature Store或其他表會fail-closed，需另外審查契約。

## 修改範圍

- app/external_auth.py：既有登入限制、同意、提交前到期重驗與Session-bound收據查核。
- app/main.py、app/schemas.py：受同源／CSRF保護的交換狀態契約。
- app/static/app.js：雙選項、14天告知、保留表單、取消／未知狀態護欄與owner本機清理。
- app/guest_lifecycle.py：避免無需的媒體內容SELECT權限；未開啟Alpha worker。
- tests/product/與browser_tests/：合成API、真PG及真瀏覽器驗證；明示Google替身。
- 本目錄：最小權限審查稿、Alpha適配、Code Review與正式部署前檢查。

## 部署前檢查

1. 由人工Reviewer審查本Draft PR；main／現役版本若變更需重做差異與必要回歸。
2. 另獲Build／候選Deploy授權；不得批准目前main的待核准API Build來替代公開產品發布。
3. 重新讀Alpha目標／34表／007、008收據／Runtime最小權限，無Schema或ACL變更，不重跑Migration。
4. 在核准的受控候選驗證真Google：新Google以upgrade保留世界；已綁Google以login切換；取消／衝突不清；兩裝置同世界。只有本人可完成的驗證一次集中交Owner。
5. 驗收通過後再獨立核准lw-public流量；保留應用回滾Revision，不刪Alpha資料。
6. Alpha Maintenance仍不隨網站發布啟用。備份／精確FK／獨立角色／SA／Job／秘密與排程需另批授權，見[設計](ALPHA_MAINTENANCE_REVIEW.md)。

## 精確測試數與限制

- 完整SQLite+Node：522 passed／27 skipped；17項為既有一般PG案例本輪未重跑，10項為本輪專用PG案例已另跑全數PASS。
- 真PG18轉換／清除：10 passed／0 skipped。
- Chromium：5 passed（390／1440保存返回、取消／未知帳號、正常既有切換及回應遺失清理隔離）。
- API測試工具為Python3.14.10（鎖定依賴）；正式容器仍Python3.12，容器Build／部署驗收本輪NOT RUN，需另授權。
- 初始紅燈包含一項測試錯把合法guest→registered狀態變更當成資料遺失，已改成比對全部業務內容與Profile欄位；不把該項當產品缺陷。另4項有效紅燈為未知Google仍建帳、空Guest無同意切換及缺少兩種Session收據查核。
- SQL審查稿未執行；維護角色僅在本機合成PG建立。沒有真Google、正式Guest永久刪除或正式排程PASS宣稱。
