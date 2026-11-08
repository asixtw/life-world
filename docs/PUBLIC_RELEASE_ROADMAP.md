# Guest＋測試帳號真Alpha執行結果

|項目|狀態|證據|
|---|---|---|
|Alpha 12A/09/12G/10B|PASS|Owner Studio執行：帳號registered、Argon2、Runtime LOGIN、mismatch0；不重跑|
|Cloud Run→Alpha|PASS|既有VPC/私人IP、lw_alpha_app、限定IAM/專用Secret，真ready與資料讀寫|
|Guest/帳密核心真HTTP與瀏覽器|PASS|Cookie、目標三習慣、經歷確認、任務進度獎勵、刷新/重開/重登、跨Owner拒絕|
|人物基本CRUD/來源拒絕|PASS|真人物卡讀寫、無確認來源422、Guest403；未生成AI台詞|
|真Gemini/人物劇場生成|NOT RUN|本輪0新呼叫，AI未配置；不冒充完整產品|
|Google/Email|NOT RUN|不阻塞本輪Guest與受限帳密|
|公開主流量切換|NOT RUN|新lw-public-alpha-dc471d2為0%，舊entry-6fd3725仍100%；Staging不變|

[實際版本與驗收收據](GUEST_ALPHA_LIVE_ACCEPTANCE.md)。Source Commit dc471d2fd02d2686576fd19b7971fc8a3e5b1c6f，Image sha256:4235181863fe65f0fa99c9a9bac94a583171d1a4290f7ed438d800a055e86396。

## 2026-11-08 MVP P0整合更新

- 原版共用UI已部署lw-public-ui-7907691；主網址Guest與測試帳號Chromium PASS。
- 真AI／語音候選9b02b45發現PG預算sum字串型別錯誤，正在修正；尚未切主流量。
- Google Client ID已核對，27項安全回歸PASS；真Google瀏覽器登入仍NOT RUN。
- [Hidden Relationship Intelligence](RELATIONSHIP_MEMORY_CONTRACT.md)正式列MVP P0。本機已開始持久化、撤回、跨Owner與登入測試；Alpha新表受完整還原Gate阻擋，不標線上PASS。
