# Public Alpha 工程整合交付｜2026-11-05

本批是提供全團隊協作的工程候選，**合併main不等於網站已上線**。App版本仍v0.4.0；本輪不宣稱完成Docker、GCP或外部匿名驗收。

## 本次納入

- 有界匿名文字世界：共用DB限流、來源驗證、世界／業務寫入配額，維持Session、CSRF及帳號隔離。
- 預建registered帳號登入與跨裝置回讀：LIFEWORLD_ALPHA_LOGIN_ENABLED預設false，Owner核准部署設定後才啟用；claim／自由註冊仍封鎖。
- 目標Dashboard、七日來源、三習慣首頁摘要、唯讀月曆與單日用量；保留建立／調整／回顧流程。
- 獨立合成人物model_eval工具與Gemini adapter；沒有真實模型呼叫或秘密存取，不接入正式人物事實。
- 多模態provider隔離測試與現況說明；ASR／VLM正式服務尚未接上，Alpha不開放辨識。
- 最新產品決定保留積分累積及reward_ledger，無兌換／消費／商店。此決定優先於較舊文件中的「封測不做積分」敘述。

## 實際本機驗證

已測程式整合基準：45f9e112eaea93781828cbd484a80eecad0c28df；本次其後只新增本交付說明及索引，不更動程式。

- Python3.12、SQLite＋JS：375 passed／17 skipped；PG專項在下一模式實跑。
- 隔離合成PG18＋JS：392 passed／0 skipped，1項既有Pydantic alias warning。
- 手機／桌面瀏覽器：Alpha4項、Dashboard／首頁／唯讀月曆26項，共30 passed。
- 合併refresh保留Alpha能力讀取與Dashboard跨帳號快照清除；跨日測試改較長合成Session，不擴張PG runtime權限。

所有資料與帳號皆合成；本機結果不能當GCP、iOS／Android實機或真實模型品質證據。

## 協作入口

|負責範圍|入口|
|---|---|
|Owner／Jerry：隔離Alpha角色、配置與部署候選|[Alpha工程契約](../deploy/README.alpha-candidate.md)、[發布Gate](../deploy/ALPHA_RELEASE_GATE.md)|
|產品／前端：Dashboard、首頁與月曆|[Dashboard](GOAL_DASHBOARD.md)、[首頁三習慣](HOME_HABIT_OVERVIEW.md)、[月曆驗收](HABIT_SCHEDULE_ACCEPTANCE.md)|
|模型評測|[獨立工具](../model_eval/README.md)，付費呼叫仍需另批|
|媒體接續|[Provider現況](MEDIA_PROVIDER_STATUS_20261105.md)，不得把替身回應當真實辨識|

## 未完成與發布界線

Docker image build／smoke與digest尚未驗；隔離雲端Alpha、備份恢復、可信代理、固定HTTPS Host／Origin、Secret／角色有效權限、外部雙瀏覽器與停止／回復仍由Owner工作線依核准程序完成。

API CloudBuild YAML會測試／建映像／push Artifact，不自動部署API；Web YAML會部署React展示站。React展示站不是完整Life World API網站；main更新不會自動完成Alpha發布。GCP Trigger實況及其副作用須Owner另行批准，不從合併推定公開IAM或建庫授權。

不要合併落後的整份舊交接／劇場分支覆蓋本基準。團隊以GitHub main最新commit開工，先核對工作樹，保留個人未完成變更；更新GitHub不會自動更新同仁電腦或雲端。
