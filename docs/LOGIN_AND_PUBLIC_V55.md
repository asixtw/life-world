# v5.5 身分與公開邊界

產品能力由內部Owner/status=registered、資源歸屬、方案與額度決定；Google不是功能通行證。Google、受邀測試帳密與未來已驗證帳密使用同一AIRuntime、劇場、進度及獎勵；不按Email自動合併。

LIFEWORLD_PASSWORD_LOGIN_ENABLED控制一般既有帳密登入；LIFEWORLD_TEST_LOGIN_USERNAMES是受限名單，無論Google是否設定皆可啟用指定registered帳密。兩者皆未開放即拒絕帳密登入。LIFEWORLD_REGISTRATION_ENABLED獨立控制註冊，Cloud Run預設false；公開Alpha仍禁止公開註冊。一般帳密／Apple正式開放仍需驗證與恢復機制，不在此輪冒稱完成。

LIFEWORLD_TEST_ACCOUNT_SEED只從固定版本Secret取得指定Owner/username/Argon2 hash；啟動只新增一個registered合成Owner，同設定重啟不重建，不覆寫既有Owner。沒有新HTTP建帳號／重設入口。密碼本身不進Git或Runtime環境。

公開source=shared只允許public_alpha、關閉註冊、共享rate Secret及全域容量/寫入限制。不信任XFF或假設Cloud Run peer固定；所有訪客共享來源桶（10新世界/小時、30登入/15分鐘、200來源寫入/小時），並有Owner/全域容量及AI24小時額度。尖峰會保守429，不是每IP公平額度。未來改善可信Proxy不改Owner授權。

登出先撤銷Session（8秒逾時可重試），dirty先選保存草稿/捨棄/繼續；本機清理最多2.5秒、AbortSignal阻止延後清理新資料。清理失敗明示已登出但本機草稿尚留，不刪伺服器資料。

55 API定點通過、1 PG環境跳過；3登出瀏覽器案例與2核心閉環通過。真模型、真PG、外部雲端HTTP各自以本輪實測更新，不能互代。公開切換先保留IAM限制實測API，失敗恢復IAP與原Revision；再依Owner授權開匿名首頁。Google仍受007/008及備份Gate限制。

AI新增測試期累計預留總額（LIFEWORLD_AI_TOTAL_BUDGET_MICROUSD），與滾動24小時額度分開。跨日不重置總額，失敗及費用未知仍占最壞預留，不把預留當實際帳單。
