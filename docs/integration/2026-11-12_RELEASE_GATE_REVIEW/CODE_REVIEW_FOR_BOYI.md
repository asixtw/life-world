# PR #26｜Boyi 獨立人工 Code Review 包

Owner於2026-11-12指定Boyi為人工審查者。**審查結論尚未收到，不代簽、不代寄信。** Gate A只核准UX；不等於Code Review、安全/Schema或發布通過。

## 審查固定版本

- 產品 `a2eb3632037726b93f3bea82b395fa7e5d010aa6`，App tree `c823bdde84ae8ab90c75a45d557cb6cd9e9c0623`。
- Gate A核准當時交付Head `318b4bd18150ac4cc11351d46877720389b9c20e`；其app/static與產品候選完全相同，後續本批僅文件/審查稿，不需重做UX。
- Base main `68102f230aa947a434286ba9260e1ae75f6634b0`。若審查時base/head產品改變，先比對差異，不能把核准套到不同產品。
- 開啟PR #26 Files changed；產品主要Diff可用 `git diff 68102f2..a2eb363 -- app tests deploy scripts`，證據另看README，二進位圖/錄影不當程式碼審查。

## 必看項目與現成證據

| 檢查 | 入口 | 驗收重點 |
|---|---|---|
| Google保存/切換 | external_auth.py、google_identity.py、guest_lifecycle.py | 升級同Owner；舊世界不同Owner、明確同意後才abandon；取消/失敗不清資料；Session/Nonce/CSRF與並發 |
| Confirm一致性 | service.py、draft_review.py、schemas.py、person_basic_details.py | 多人target/client_ref、不依姓名；晚期衝突全部回滾；保存草稿不建人；重送不建雙份/不重複計分 |
| 草稿版本與回復 | service.py::_draft、DraftReview契約 | 舊Story/v2可讀；未知_format拒寫保留；舊Alpha不能無損讀新候選；仍需固定兼容Rollback映像實測 |
| 日期/目標/資料保留 | experience_validation.js、experience_basic.js、experience.js、media.js | input/離欄/加入前日曆驗證、未知年2/29、目標時區與部分完成；不自改原文/日期、不默默丟數量；API拒絕可回第二步 |
| AI與來源 | ai_runtime.py、ai_draft_consent.py、relationship_memory.py、people.py | 明確用途授權/撤回、本人用量、有限預留/未知費用；草稿不擴大資料範圍；舊快照競態修復；四維來源契約/PG Feature Store仍有阻擋 |
| Schema/權限/Purger | 011審查稿、MINIMUM_PRIVILEGES.review.sql、guest_fk.py、guest_maintenance.py | Marker、既有Owner角色、append-only/Owner不可改；不擴網站Runtime；90/61 FK未審即停止，不盲加白名單 |
| 發布與備份 | deploy/release.py、兩Cloud Build YAML、CLOUD_SQL_BACKUP_RESTORE_PLAN.md | main人工核准/正確Build SHA、E2E候選不切100%、真備份恢復/雙映像相容、不把舊export當現行還原保障 |

收據：API_NODE.log（788 PASS/87 SKIP）、MERGED_UI_PG.log（26 PASS）、DRAFT_SOURCE_TESTS.log（28 PASS）、RELEASE_SAFETY_TESTS.log（24 PASS）、DRAFT_COMPAT_LOCAL_PG.json、LOCAL_PG_PERMISSION_AUDIT.json、OWNER_ENTRY_CHECK.json。範圍不同/有重疊；真Google/Gemini/GCP E2E NOT RUN，不用替身代替。

## 必須保留的未通過事項

- 011與正式最小權限未執行，Schema來源仍2026-11-11；正式回復/備份驗收不足。
- 四維source_kind持久契約/PG Feature Store/用途同意與撤回傳播尚未完整通過；不啟背景AI。
- Purger新29 FK與Alpha維護角色/清除契約未放行；不能移除安全檢查。
- 尚無本輪固定Image Digest與受控GCP E2E；不存在可立即聲稱已驗證的Alpha無損Rollback。
- Gate A已Approved不會關閉上述Code Review/Gate B/C/D事項。

## 提交人工審查結果

請綁定上述產品SHA，逐項提出問題/嚴重度/檔案行或回覆結果：

```text
Reviewer: Boyi
Product commit: a2eb3632037726b93f3bea82b395fa7e5d010aa6
Code Review: PENDING / REQUEST_CHANGES / APPROVED
Reviewed scope:
Findings (P0/P1/P2, file/line, expected fix):
Not reviewed / NOT RUN:
Release gates still blocked:
```

不要因Code Review通過便視為授權Merge/DB/GCP操作；發布仍另批。

## GitHub帳號與人工審查分離

唯讀查證PR作者login是`asixtw`。本次只指定人工Reviewer Boyi，聯絡資料不在公開Git重刊，也不以email前綴猜測GitHub帳號。

若Boyi使用`asixtw`，GitHub不允許PR作者批准自己的PR；可保留具名人工審查紀錄，但不能把它冒稱平台上的非作者Approval，也不繞過branch protection。若當時規則要求非作者Approval，需另指定符合權限的非作者帳號。

規則來源：[GitHub官方：Approving a pull request with required reviews](https://docs.github.com/en/pull-requests/how-tos/review-pull-requests/approving-a-pull-request-with-required-reviews)。未代為送出Review或邀請他人，未改branch protection。
