# Life World｜App 與原型功能演進

## 2026-11-06 E2E／正式模板隔離提案（待授權）

不再放寬發布器的DB／Secret比對。準備從正式100%Revision完整複製可版本化配置，以etag及固定全部traffic／Tag建立0%正式基準；只驗證validateOnly、不套用。確認人工E2E仍有部署main入口，提出另行核准獨立Cloud Run服務的最小改向方案，沒有新建資源。PR #14 Gateway Origin已設定為核對過的canonical URI，仍Draft、未授IAM或部署。

## 2026-11-06 PR #14 發布政策最小修正（Draft）

以100%正式revision的明確business=true作唯一政策來源，只在比較複本容許latest/e2e的false差異；新候選顯式true，候選完整Runtime比較不排除business，其他DB／Secret／VPC／SA差異維持拒絕。6項相關測試通過；實際環境另有e2e資料庫、使用者與Secret參照不同，故唯讀預檢仍安全阻擋。未執行IAM授權、Gateway啟用、Merge、部署、Migration或GRANT。

## 2026-11-06 Web／API 唯讀串接候選

區分React gallery與真正app/static。既有Web image新增server端metadata IAM gateway，保留gallery根目錄，以/app/與同來源/api回讀；Cookie／CSRF／Origin／CSP及owner驗證保留，不給瀏覽器Google token。所有寫入封鎖，UI明示唯讀；backend origin預設關閉，啟用後健康檢查需驗API可用，沿用既有自動候選發布／回滾。28項直接相關檢查通過，尚未部署或宣稱Cloud SQL業務驗收；IAM、API prestable政策差異與Session/DML仍有明確待決事項，見deploy/README.web-gateway.md。

## 2026-11-05 首次 CI/CD 失敗最小修復

Web／API 發布步驟改用官方 google-cloud-cli:slim 與映像自帶 Python 的絕對路徑；一次獨立容器檢查已證實兩者可執行。API 建置契約改驗證 Test→Build→Container Verification→明確 Push→release.py，禁止恢復 images 後置推送，保留公開存取／SQL／hostfix 安全限制。僅 API 契約 3 項及 YAML 基本檢查，發布器主要邏輯、IAM、資料庫、流量不改；正式重新部署須經本次 PR Merge 授權。

## 2026-11-05 CI/CD 等鎖與事故復原補充（續 e368379）

等鎖由 180 秒延長為 900 秒、輪詢 5 秒，保留 etag、新舊版本護欄及執行中 Build 不可接管；Web 總 timeout 改為 2700 秒。補入以 Build 終止狀態、Cloud Run 收斂、journal／實際流量及新 etag 為前提的最小事故復原程序，禁止覆蓋其他操作者流量。9 項相關檢查及本輪雙 preflight 通過；兩項 IAM 有效權限受組織可見權限限制尚未完整確認，不補 IAM、不改正式流量、不 Push／Merge。

## 2026-11-05 自動 CI/CD（工程交付，未推送 main）

Web／API 共用 `deploy/release.py`：固定 digest 的 0% 候選、IAM 健康檢查、指定 revision 發布、etag 發布鎖、防舊建置覆蓋與失敗回滾；保留 API 正式設定／hostfix 隔離及既有合成測試。不修改 App／DB schema，不執行資料庫 migration；本機 31 項部署檢查與唯讀 API 設定預檢通過，不代表已完成雲端發布。詳見兩份現行部署 README。

建立／最後更新：2026-11-03（Asia/Taipei）。維護原則見[共同研發指引](PRODUCT_GUIDE.md)。這是功能演進的完整紀錄入口；[ROADMAP](ROADMAP.md)保存後續工作，驗收證據仍保留於原文件。

## 版本與證據如何閱讀

| 類別 | 目前版本／狀態 | 意義 |
|---|---|---|
| 可執行 App | v0.3.0，本機 MVP | 以 [pyproject.toml](../pyproject.toml)與 [App 入口](../app/main.py)為據；未代表正式雲端部署 |
| Connections 設計原型 | v0.3，獨立前端示範 | 保留原貌作設計參考，與 App 編號各自管理 |
| Connections 正式整合 | v0.3.0 已完成 | 交會取代星圖，正式資料、來源與配對保存於 SQLite；見[完整驗收](CONNECTIONS_ACCEPTANCE.md) |

App 與原型各自編號。v0.1／v0.2 下方保留歷史結果；v0.3.0 的 100／14 是本輪實際執行，不混用先前測試。

## App 演進

### 環境修正｜Windows 可直接安裝鎖定依賴

- 日期：2026-10-30。`greenlet` 3.2.5 沒有 Windows 預編譯檔，使 `scripts/setup.py` 在沒有 C++ 編譯器的 Windows 失敗；`requirements.lock` 改為 Windows 鎖 3.2.4，其他平台維持 3.2.5，並補鎖 Windows 專用的 `colorama`。
- `scripts/setup.py` 現在讓環境與鎖定檔一致：基礎 Python 被移除時重建 `.venv`，移除鎖定外的套件，並提供 `--check` 比對實際安裝內容。損壞判定只看檔案結構，暫時性錯誤不會清除環境。新增 `tests/test_dependency_lock.py`、`tests/test_setup_script.py`。App 功能、資料與 API 未變，仍為 v0.3.0；驗證結果與已知限制見[驗收紀錄](ACCEPTANCE.md)。

### 具名正式任務｜歐桑模擬人物與完整 UI／美術交付指令

- 日期：2026-10-28；Boyi 確認 Jerry／歐桑已收到具名分工與完整交付要求通知，本次內容為正式任務。Boyi 管產品／體驗，Jerry 管全端整合／審查，歐桑管資料庫／Pro 協作與獨立完整製作。
- 新增[任務總入口](team/PROMPT_OUSANG_START.md)、[LW-SIM-001](team/PROMPT_SIMULATION_001.md)與[十三類完整美術規格](team/ART_DELIVERY_SPEC.md)，重寫 [UI 指令](team/PROMPT_UI_001.md)，更新具名看板／指引，取代小樣等核准與美術另期安排。
- 歐桑需一次交齊三組十五位人物、六場可玩劇場、全部元件狀態／轉場／App 代表縮圖／蛋與破蛋／Lumi、資料與資產清單、原稿／程式、測試及 Jerry 接入說明。這次交付的是正式任務文件，不代表成果已生成或已驗收，App 仍 v0.3.0。
- 十五位／三封面為測試／POC／封測 demo，正式版保留待評估；「人物劇場→情境體驗（示範角色）」為 Boyi 最新討論的待確認入口提案，沒有改正式路由或資料。
- 本次發布範圍限已確認任務與具名指引，先前獨立的變更管理草案仍保留本機，不混入本次發布；驗證為文件／連結／任務完整性、來源指紋與遠端讀回，不以先前產品測試冒充本輪執行。

### 共用草案發布｜變更同步與公告後發布（待正式定案／公告）

- 日期：2026-10-28；原先依使用者要求保留本機，後依 Boyi 最新指示「先把git推上去」先發布共用草案，不表示正式規則已定案或公告。
- 新增[變更同步規則](team/CHANGE_CONTROL.md)，涵蓋成員／職責、任務、產品／技術與存放規則的影響核對，以及定案、公告、發布與成員同步紀錄；兩層 AGENTS、共同指引與協作入口同步連入。
- 本批僅為 Markdown 文件發布，未代發公告；正式共同規則定案與公告紀錄仍待補，App 維持 v0.3.0。先前已發布的具名任務 `26e36c7` 不受影響；本次版本由包含本段的 Git commit 記錄。
- 驗證為相對連結、內容／差異與發布範圍核對；本輪不重跑或沿用歷史產品測試聲稱通過。

### 共同基準發布｜產品規格、存放規則與三人協作

- 日期：2026-10-28；使用者明確要求將目前版本、共同規格與檔案存放規則推送 `asixtw/life-world`，供夥伴協作。現有 App 與先前未提交的交會整合一起納入共同基準，App 維持 v0.3.0。
- 新增[共同規格索引](SPEC_INDEX.md)、[產品基準](PRODUCT_BASELINE.md)、[存放規則](STORAGE_RULES.md)與[分支／審查流程](../CONTRIBUTING.md)；交接入口以發布 commit 為準，保留舊本機快照的歷史記錄。
- 公開內容為程式、共用規格、工作包及虛構測試證據；實際 DB、媒體、秘密、私有備份及工作區外原型不發布。素材留存／刪除、正式計分與 AI 廠商維持待決。
- 本輪重跑 100 項後端與 14 項 Chromium 通過，詳見[發布檢查](GITHUB_PUBLISH.md)。下方未提交／未推送與 100／14 的其他敘述是各次歷史交付，勿誤讀為本次發布狀態。

### 文件與協作交付｜三人工作包（不升 App 版本）

- 日期：2026-10-28；來源為使用者要求實施「三人團隊分工方案」。已建立[協作入口](team/README.md)、角色分工、任務卡、流程／狀態、三份完整指令、交付模板及整合清單。
- 當期人力更正為三人、沒有專職前端；使用者負責產品，全端負責技術整合與審查，資料夥伴負責資料品質／分批 AI 製作。Codex 為工具，不算第四位人力。
- 暫定目標更新為 React＋TypeScript、保留 Python／FastAPI、PostgreSQL、前後端 GCP；第一輪帳密加邀請／復原碼，AI 供應商未定。這是待實作方向，現有程式仍為 v0.3.0／SQLite／原生前端。
- 保存含最新工作目錄的本機來源快照與受保護程式指紋，避免只以 Git HEAD `988c8d8` 交接；來源包不含使用者資料庫、憑證、虛擬環境或 Git 歷史。詳見[基準](team/BASELINE.md)。
- 驗證見[文件驗證](team/VALIDATION.md)：產品程式指紋、文件連結、任務完整性與快照核對。本輪不為文件新增 Python 產品程式或跑無關 TDD；不沿用先前 100／14 冒充本輪實測。
- 尚未製作 React 元件、執行 PG 遷移／GCP 部署、聯絡夥伴或推送 GitHub；工程任務均保留待領取／審查／阻擋狀態。

### v0.3.0｜交會取代星圖與完整體驗驗收

- 日期：2026-10-28。使用者先要求整合，再明確更正「交會取代星圖，整合完再做完整測試」；本輪已實作，未提交或推送 GitHub。
- 變化：故事聚焦、多人參與／直接互動、精確原文提及、人工身分配對與歷史、來源抽屜、來源展示撤回／恢復、焦點分頁、上一段與閱讀位置、收藏冊／人物卡串接。新頁面沿用原技術，不引入 React。
- 相容：舊 API 與去重保留，舊經歷只回填待核對，不猜測參與；事件合併不改逐筆人物來源；配對與更正不發分。實際資料先備份，22 個舊表內容指紋相同、完整性與外鍵通過。
- 體驗修正：核對返回保留摘要／下一步，慢速載入有回饋，來源與清單失敗可重試，未保存更正需明確捨棄，同場但未互動的故事仍可在人物卡查看。
- 本輪實測：**100 項後端、14 項 Chromium 旅程通過**；手機 390×844、桌面 1440×1050。300 人／103 段故事及模擬慢速條件的量測、截圖、紅燈／綠燈及限制見[整合與體驗報告](CONNECTIONS_ACCEPTANCE.md)。
- 邊界：真實 AI、月／週排程、3,000 人／實機負載、跨刷新探索歷史、全站來源元件等仍另項處理。配對持久保存，探索及未正式核對的頁面修改不等於伺服器已保存。

### v0.1.0｜核心本機閉環

- 日期：2026-10-27；Git 提交 `74b1fea`（同日），[提交紀錄](https://github.com/asixtw/life-world/commit/74b1fea87d82ce68a89a0be5d24751041263be6d)。
- 變化：訪客／本機帳號、Bio 與強制首目標、目標蛋後 Lumi 誕生、三項行動及週規律、經歷草稿保存／恢復、選填人物與升級續作、人工摘要／小數貢獻／後續任務／積分的交易保存與重送去重、補記、圖片佐證及人工成果完成。
- 限制：本機手動整理，非真實 AI；帳號未接受管身分，未做雲端部署。開發計分與媒體門檻不等於正式產品決策；當時排程為週規律及 28 日預覽。
- 證據：[U-01～06](context/LATEST_PRODUCT_DECISIONS_2026-10-27.md)、[需求](REQUIREMENTS.md)、[驗收的 v0.1 歷史紀錄](ACCEPTANCE.md)、[後端結果](TDD_GREEN.txt)、[瀏覽器結果](BROWSER_GREEN.txt)。當時結果為 63 項後端、3 條 Chromium 旅程通過。

### v0.2.0｜人物流程還原

- 日期：原還原／驗收文件記載 2026-10-27；Git 提交於 2026-10-28，`988c8d8`，[提交紀錄](https://github.com/asixtw/life-world/commit/988c8d82a21f6d2e83a37ae4a8cdd97f0d272ca4)。兩種日期分列，不改寫原驗收時間。
- 變化：世界／目標／紀錄／關係四導覽，首頁匿名星圖；關係星圖／收藏冊共用搜尋、透明排序與選取；多角色、分類、標籤及關注。
- 人物完整頁：三分頁、興趣／飲食／專長／習慣四維度、尚未了解狀態、人工確認來源、原文／日期／證據類型、同值加來源、衝突處理、撤回與歷史；另有明確人物關係、場合及合作目標。
- 互動事件：實體見面／電話／訊息／其他／未分類，手動分類與合併，同次多筆經歷不重算見面；舊角色與備註保留，舊經歷回填未分類，不重發積分。
- 流程串接：人物／合作目標帶入記錄及返回狀態；小劇場提供見面前準備、情境演練、傳達心意、相遇後回顧，私人筆記不寫正式事實／進度／積分，訊息只保存／複製。
- 限制：目前仍主要以單一 `person_id` 建立／確認經歷，沒有完整的逐經歷參與／提及分類或正式 Connections；真實 AI、小劇場 AI、新月／週排程及雲端另項處理。
- 證據：[原圖逐項還原與差異](PEOPLE_RESTORATION.md)、[17 項初始失敗紀錄](PEOPLE_TDD_RED.txt)、[後端 81 項結果](PEOPLE_TDD_GREEN.txt)、[瀏覽器 7 項結果](PEOPLE_BROWSER_GREEN.txt)。手機 390×844、桌面 1440×1050；未代表 Safari、實機、完整無障礙或負載已驗證。

### v0.2.0 內的維護｜繁體中文註解

- 日期：原導讀記載 2026-10-27；同上 2026-10-28 的 `988c8d8` 一併提交，未單獨升版。
- 變化：34 個自有程式／設定檔補中文註解，涵蓋 Python、JS、CSS、HTML、SQL、測試、腳本及設定；模板與字串不插入會改變內容的註解。
- 證據：[CODE_GUIDE_ZH](CODE_GUIDE_ZH.md)記錄語彙／AST、JS 語法、CSSOM、SQL 結構等相容檢查，以及當時後端 81 passed in 4.47s、Chromium 7 passed in 26.09s。與前一輪 4.76s／25.89s 分屬不同歷史執行。

## Connections 原型演進

### v0.1／v0.2｜提案背景

日期與檔案未獨立核實。使用者先前以 v0.1 描述焦點人物、共同經歷、參與者與相關故事，再提出 v0.2 的「故事起點 → 交會瞬間 → 路徑延伸」。v0.3 交接稿亦說明延續此方向；這裡只記設計脈絡，不宣稱取得並驗收過 v0.1／v0.2 原型。

### v0.3｜故事探索與人物提及

- 日期：2026-10-28；狀態為互動式前端測試原型，非團隊核准的 Figma／PRD／正式工程功能。
- 故事路線 B：海邊故事 → 小安 → 畢業後的小聚會 → 怡君 → 攝影散步；人物經由故事連接，同場不代表彼此熟識。
- 提及路線 A：合作需求確認會議（林先生、陳小姐實際參與）→ 張總待核對提及 → 原文高亮 → 人工配對 → 張總參與的另一段預算評估回顧。配對只確認身分，不改成會議參與者。
- 已有原型互動：中央故事、人物聚焦與其他故事、參與／提及分區、底部 Source Sheet、候選人物核對／略過、提及來源提示、收藏冊搜尋／分類／詳情、分開顯示參與故事及已配對提及、無參與經歷空白狀態、簡單上一步與重設。
- 來源抽屜呈現日期／種類／使用者審閱、來源說明、摘要、引用片段及人物出現方式；信任界線為審閱不等於第三人證實、提及不等於出席、身分配對不等於私人關係。
- 程式證據：`PEOPLE`／`STORIES` 為固定虛構資料，配對只加入記憶體 `confirmedMentions`，刷新／重設不保留；無 DB 或正式核對 API。候選只有預設單人，非完整同名辨識。`save()` 僅存人物／故事且最多 12 步，`render(true)` 重設捲動，未保存完整探索狀態。
- 驗證界線：交接稿自述 UX-01～09 的原型瀏覽器檢查；本輪只讀原型程式、交接與畫面，**未重新執行這些瀏覽器案例**，也無正式權限、儲存重試、撤回索引、300 人效能或完整無障礙驗收證據。

### 原型查證入口（本機工作區外部參考）

- 本機 `LifeWorld_Connections_v0.3/` 的 `DESIGN_HANDOFF.md`、`prototype.html`、`overview.png`。
- 本機 `LifeWorld_Workspace_2026-10-27/01_目前工作區/互動原型_待依最新決策修訂/index.html`、`LifeWorld_Master_Handoff_v1.1_AUTH_DRAFT/person360.html`。

以上是完整本機工作區的參考路徑，不是 GitHub 連結；原型位於 App 儲存庫之外，單獨下載 App 不包含它們。App 內的規格、功能說明與共同指引可獨立閱讀，不以外部原型作啟動前提。

## 後續工作及討論入口

| 工作 | 缺口與下一步 |
|---|---|
| 多人經歷與身分 | 手動整合已完成；後續評估 AI 候選、名片校對與新建人物草稿 |
| 故事探索 | 本頁路徑與返回已完成；收藏故事及跨刷新探索歷史仍可討論 |
| 共用來源與效能 | 評估全站 Evidence Viewer；300 人已量測，3,000 人／首次載入／實機與併發仍待驗證 |
| POC 與產品驗證 | 使用者指定 2026-11-13 為目標，已授權本機交會整合；對外展示範圍與 5～8 人理解驗證仍待團隊安排 |
| 其他 App 工作 | 真實 AI、月預設／週選用排程、正式身分與部署，見 [ROADMAP](ROADMAP.md) |

完整本機工作區另保留 `LifeWorld_Workspace_2026-10-27/04_後續開發/2026-10-28_Connections_v0.3_整合規劃.md` 與 `05_頭腦風暴/00_索引.md`，不隨此儲存庫發布。團隊接續以[共同規格](SPEC_INDEX.md)與[任務看板](team/TASK_BOARD.md)為入口；未定方案不能當作已授權的功能實作。

## 早前文件維護｜2026-10-28

建立本紀錄、完整研發指引及兩層 AGENTS 入口；將頭腦風暴的完成項轉入本頁，保留未整合與待決內容，新增後續規劃並修正入口。只變更 Markdown，未更動產品程式／API／資料庫／原始交接包，未推送 GitHub。


## Web部署來源與名稱統一main 2026 11 03

Build SA改為lw-build-main，部署目標改為lw-web-main，保留lw-web-runtime、lw-containers、唯一tag及digest部署；step、environment label與映像title同步main。現行部署README改名並更新入口，歷史驗證保留。僅本機設定與驗證，不改PG／FastAPI工程，不刪舊服務／分支，未操作GCP。見 [Web main交接](../deploy/README.web-main.md)。


## Step 10 4 原 FastAPI 新增 PG18 模式 2026 11 03

原本業務模組共用 SQLite／PostgreSQL DB介面；新增明確backend、pg8000／Private IP Connector準備、有界pool、owner交易鎖、型別與audit_seq邊界，沒有縮減API。新增非root API Dockerfile及只Build／Push的Cloud Build設定，Cloud Run業務預設關閉。權限審查SQL僅在本機合成PG執行，原工作樹／Web設定保留。實際驗證與未完成事項見 [工程交接](STEP10_4_PG_API_HANDOFF.md)。

## Step 11 FastAPI／PostgreSQL 整合至 main｜2026-11-03

合併 SQLite／PG18 Adapter、依賴鎖定、測試工具與非 root API 容器；API YAML 的 Build SA 改為 lw-build-main，仍只 Build／Test／Push，未加入 deploy。未來 API Trigger／Cloud Run 統一 lw-api-main、來源 ^main$；Web main 部署檔保持不變。原 dirty 工作樹保留，實際重新驗證與發布界線見 [Step 11 交接](STEP11_API_MAIN_INTEGRATION.md)。

## Step 18 受控 Tagged Revision 驗收工具｜2026-11-03

新增離線 plan 防護、只用既有 API 的合成 e2e、Token stdin／安全報告、唯一 canonical schema SQL 產生器、專用 life_world_e2e／lw_e2e_app 最小權限及清理腳本。保留主 Revision 100% 且業務關閉，未修改 App／Cloud Build／Dockerfile 或執行 GCP；工具及本機驗證見 [Step 18 交付](STEP18_API_E2E_ACCEPTANCE.md)。

## PR #11 合併前預檢修正｜2026-11-03

Plan 改為保留匯出時的來源批次／時間／SHA256，不能用建立時間刷新舊來源；執行時再核對 Plan 內容指紋與15分鐘時限。新增實際 Revision annotations 的 Direct VPC／相同設定檢查，保持既有API與基礎建設設定。退休流程也要求四份新來源，在刪除測試Revision前完成核對；驗收期間凍結配置仍屬必要條件。測試與限制見 [補正交接](STEP18_API_E2E_ACCEPTANCE.md)。

## PR #11 獨立複審｜2026-11-03

E2E SQL 的 PASS 列改與檢查同交易，不再依賴 client 的 ON_ERROR_STOP；權限核對補齊 PUBLIC／欄位級／DDL 路徑並改以 OID 支援非 superuser 管理者；00 不再接管既有 DB。預檢另要求測試修訂只有唯一 e2e 路由、單一容器及僅含已審查欄位的 Direct VPC interface；本機 harness 改以非 superuser 管理者執行交付 SQL。API、核心 DDL 與授權矩陣不變，見 [複審紀錄](STEP18_API_E2E_ACCEPTANCE.md)。

定點修正：權限核對由各權限總數改為逐表白名單；00 拆成建角色、建 DB、標記三階段，前段失敗時 session 維持唯讀，不再建立或改寫同名 DB。
