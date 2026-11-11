# Hidden Relationship Intelligence：MVP P0

2026-11-12狀態校正。四類User／Person／Relationship／Context、來源追溯、不確定性及可撤回是既有產品目標；不是顯示在人物卡的技術標籤頁，也不代表已完成或已部署。Jerry進階劇場、人物作品、AI角色演出與完整角色創作未核准，不從資料契約推成下一版承諾。私人筆記、現實情境準備與Lumi互動分開。

## 已有與尚缺

`relationship_memory.py`有有限SQLite特徵骨架、明示摘要偏好、讀取時規則快照及profile_version；離線測試涵蓋偏好跨Session、Owner隔離及部分人物事實來源撤回。`training_opt_in`固定false，不等於訓練功能或授權。

**完整來源失效尚未驗收**：records讀取未有背景來源撤回的統一過濾；人物事實可來自提及，不能據有效source數自動稱confirmed_interaction。背景purpose/Provider/欄位/來源版本同意、事件觸發/排程、衝突/削弱/歷史與快取失效尚需Gate B審查。現有測試不證明user/context不重用撤回來源。人物基本資料011不會自動補此能力。

`GET/PUT/DELETE /api/personalization`依Session Owner及寫入CSRF處理偏好；偏好enabled不能冒充完整背景AI授權。草稿AI的獨立可撤回同意不涵蓋背景分析。未確認草稿、模擬與未授權第三人資料不得進正式特徵或訓練集；模型輸出也不得回寫真人正式事實。

## PostgreSQL與發布

Owner已提供2026-11-11 E2E/Alpha快照，不能再把「未收到Metadata」當阻塞。兩PG快照仍缺relationship_features/preferences；這與011四表是不同審查案。009候選SQL保留ROLLBACK且無正式收據，不可當可執行Migration包；不新增服務/資料庫，不挪用其他表冒充Feature Store。

Runtime旗標保持未開放政策，本輪沒有修改正式設定。用途/資料/最小權限/來源失效及回復Gate未過前不啟用。不能因已保存特徵、三個SQLite測試或simulation API存在，宣稱真Gemini背景標籤、長期記憶或模型訓練已上線。

詳細差異、資料製作者契約、Gold／實際輸出／正式採納分流與待核准輸出envelope，見[v1.1資料契約稽核](integration/2026-11-12_DATA_CONTRACT_AUDIT/README.md)。這份候選規格不自行替代已核准正式規則，也不執行匯入或發布。
