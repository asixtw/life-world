# 真Alpha Guest＋專用帳號：0%候選已可操作

網址：https://alpha-guest-review---lw-public-u5py2jttpa-de.a.run.app/

專用帳號lw_synthetic_test已由Owner私密12A建立，工程已驗證真帳密登入、登出、重登及網頁UI登入。初始密碼只依Owner同意在對話交付，不在本包、Git、前端或Build日誌。

|工作|狀態|實際證據|
|---|---|---|
|12A／09／12G／10B|PASS|Owner Studio結果，34表、Marker/owner正確、LOGIN、無管理屬性、mismatch0；未重跑任何Migration或建帳|
|IAM／VPC／Secret|PASS|限定Instance Cloud SQL Client＋公開SA兩個專用Secret version1，既有VPC/subnet；真/ready200與業務讀寫證實連通|
|Guest真Alpha HTTP|PASS|首候選首次建世界等72項檢查實跑；最後候選29項Cookie/隔離/重登/跨Revision回讀重新驗證，詳LIVE_E2E_REPORT|
|Guest真手機瀏覽器|PASS|實際Guest→個介→目標/三習慣→三次孵化→文字經歷→編輯/人工確認→任務/進度/1積分/Lumi→刷新|
|瀏覽器關閉重開|PASS|新Chromium程序/新context攜有效Cookie仍讀同Owner/目標/經歷/獎勵；不是無Cookie跨裝置Guest恢復|
|帳密真登入/回訪|PASS|HTTP登入/登出舊Session401/重登及Desktop UI登入；與Guest跨世界404|
|人物基本功能/來源保護|PASS|測試帳號建立/讀人物卡；未確認來源simulation422，Guest無權讀取403；沒有生成虛構人物事實|
|Username AI身分授權|PASS（資格邊界）|registered帳號停在ai_not_configured503，Guest403；不是因Google Provider限制|
|真Gemini摘要/劇場|NOT RUN|AI未配置/核准新額度，0新呼叫；不以手動摘要或422/503當真AI PASS|
|公開主流量切換|NOT RUN|新候選0%；舊lw-public-entry-6fd3725仍100%；Staging spec不變|

## 精確版本

- Source Commit dc471d2fd02d2686576fd19b7971fc8a3e5b1c6f，包含Guest初始請求singleflight/timeout、安全測試與已開Alpha入口「不用註冊，先開始」。
- Build d1481e66-c018-4112-873a-3a31b6faec58 SUCCESS，21項定點檢查；Alpha UI5項本機Chromium通過。
- Image sha256:4235181863fe65f0fa99c9a9bac94a583171d1a4290f7ed438d800a055e86396。
- Revision lw-public-alpha-dc471d2，Tag alpha-guest-review，0%主要流量。
- Draft PR https://github.com/asixtw/life-world/pull/20 ，非main分支codex/gcp144-public-core，未Merge。

## 可操作範圍與限制

訪客點「不用註冊，先開始」；無註冊即可建立獨立世界。授權帳密入口「登入預建帳號」，本帳號已包含一個合成驗收目標/三習慣、1筆人工確認經歷、任務、1積分與人物卡，可繼續操作。各Guest/帳號資料隔離，沒有刪除舊資料。

Google與Email未啟用；真Gemini/真劇場不能測，該項仍NOT RUN。初始密碼不是一次性用後失效，網站目前沒有自助改密碼；如需輪替，走既有受控Hash更新及Session撤銷，不把功能缺口假稱完成。新Guest有既有world/source/write配額；同Cookie重送恢復同世界，完全無Cookie的獨立首次請求不宣稱全域去重。

真瀏覽器第一次腳本只等確認HTTP201就立即跳頁，觸發尚未完成SPA導航的保護對話框；改為等待核對表單消失/保存導航完成後，同樣斷言已通過。最後HTTP重測沿用有效Cookie卻未先恢復CSRF而正確403；腳本先GET auth/me恢復原Session CSRF後通過，沒有放寬應用安全規則。

## 回滾與最後公開驗收

目前未切主流量，沒有必要回滾舊公開入口。必要時移除/停用alpha-guest-review測試Tag；保留舊Revision和Alpha資料。未經Owner確認不把候選調至主流量100%。Guest/帳密手動核心可進行Owner驗收；真AI/劇場、Google/Email與PR整合仍需另行完成，不能宣稱完整正式Release。

Staging IAP/IAM/配置未修改；本輪沒有新Cloud SQL Instance、自動備份/PITR，也沒有擴大Gemini費用設定。實際雲端帳單未知，cost=null。詳細SQL/IAM/VPC/Secret與測試範圍見EXECUTION_RECEIPT.json，所有證據hash見SHA256.json。

[Git內去敏驗收證據](acceptance/guest-alpha-live-2026-11-08/EXECUTION_RECEIPT.json)；[剩餘Gate](acceptance/guest-alpha-live-2026-11-08/REMAINING_GATES.md)。
