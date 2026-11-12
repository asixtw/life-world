# A／B／C 提交收據與 Gate B 剩餘阻擋

2026-11-12。Owner明確核准本輪三批Commit及普通Push；未授權Merge main／正式Migration／GRANT／Build／Deploy／切流。

## Git基準與逐批驗證

- 起點本機／遠端整合分支均 `f3f4c9f5a9a0833d5966e427d9c9a33c85b45731`；main `68102f230aa947a434286ba9260e1ae75f6634b0`。無待處理並行變更。
- 原分支：`integration/pr24-first-unified-schema010-20261111`；工作目錄 `/private/tmp/lw-integration-20261111`。無新分支、force、rebase或Merge main。
- 本機未配置作者身分；沿用歷史已使用的 `Codex` Agent作者，不代署Owner、不改全域Git設定。

| 批次 | Commit | 實際內容／獨立驗證 |
|---|---|---|
| A | `fe1b68416844d01b75f420d6e072e2f1fa9361a8` | F1/F2/F4及測試；A執行時B程式還原為起點，不依賴B。API **34 PASS**、本機PG **4 PASS**；[A_TESTS](evidence/A_TESTS.log)、[A_PG](evidence/A_PG.log) |
| B | `eae607c32980d2a2d31b9bdbde35eda34254b1c1` | 媒體父工作／逐段成本／冪等；建立在A上可獨立測試。API **80 PASS／15 SKIP**、本機PG **5 PASS**、Node **53 PASS**；[B_TESTS](evidence/B_TESTS.log)、[B_PG](evidence/B_PG.log)、[B_NODE](evidence/B_NODE.log) |
| C | **收錄本檔的Commit**，用下列唯讀命令解析 | 只加入原AI審查、修復證據／契約補充／整合報告與F5獨立測試，不改app。**2 PASS／2 strict XFAIL**；[C_TESTS](evidence/C_TESTS.log) |

```sh
git log -1 --format=%H -- docs/integration/2026-11-12_SECURITY_FIX/SUBMISSION_RECORD.md
```

C的完整SHA以Git記錄與當次交付回覆為準，不在Commit內容捏造其自參照SHA。上述測試有交集，不相加冒稱完整套件。原四紅燈探針在A+B再跑 **4 PASS**，[收據](evidence/COMMIT_AB_ORIGINAL_PROBES.log)；原檔與紅燈收據未改。

15 SKIP是需要原專用PG fixture的測試，其fixture會TRUNCATE／GRANT，因此未在Owner共用本機庫啟用；另用無DDL／GRANT／清庫的5件PG測試。這是本機PG，不是GCP E2E。真Google／Gemini、實機Safari／Android、整套PG、備份還原與GCP發布仍NOT RUN。

## F5條件核准如何落實

[契約補充](FACT_PROVENANCE_CONTRACT.review.md#owner有條件核准後的四項補充2026-11-12尚未正式凍結)完整記錄：

1. manual只表示輸入方式；四維正式fact仍需已確認經歷，不推論evidence_type，生日／任職可無經歷的011規則不外推。
2. source_revision是已核對的草稿版號；無草稿API為null，正式來源revision獨立遞增，fact revision也不混用。原文用實際SHA256核對，不造不存在的experiences revision。
3. 一般create/upsert不得清空revoked_at。明確恢復需獨立動作、確認／版本／去重／重驗來源與append-only History；用途可用投影不等於恢復記錄狀態或AI授權。
4. 同fact多來源各自保存／撤回／更正；舊資料未知留null/legacy_incomplete。盤點legacy Confirm、targeted/DraftReview、FactCreate、resolve、revoke、來源恢復、story availability、讀取DTO及未開放匯入，不留舊API繞過路徑。

**原 strict XFAIL 保留**：正式來源DTO缺source_kind/source_revision/quote。**追加 strict XFAIL**：普通FactCreate upsert會清空已撤回來源revoked_at。後者用 `--runxfail` 證明實際在revoked_at被清空的斷言失敗，不是setup失敗：[C_REVOKE_GAP](evidence/C_REVOKE_GAP.log)。本輪不修改F5正式寫入程式，兩項皆不當PASS、不改SKIP。

## 正式凍結／Gate B仍需決定

- 確認manual必須經歷、無草稿版號null、逐來源sources[]與舊寫入相容／拒絕策略。
- 凍結明確更正／恢復DTO、來源與fact雙版本、錯誤碼；修復upsert的非預期恢復。
- 核實來源複合FK／一張append-only History／最小權限／舊列處理，之後才提精確Migration審查稿。這輪沒有新DDL／正式Migration或GRANT。
- 檢查GuestPurger新增FK、011及Alpha/E2E最新Schema／ACL差異、DraftReview混版本及相容Rollback映像、用途授權與派送競態、備份／隔離還原及受控真Provider E2E。未以本機測試替代。
- Gate A保持Approved；四步設計未改，僅錯誤提示／來源有效狀態的既列影響範圍待人工抽查。AI-Assisted Review不冒稱獨立人工Approval。

WORKTREE.patch為F1–F4修復核准前的差異；本輪C新增契約測試以Git的B..C差異為準，未改寫原紅燈收據。

Diff檢查補註：來源/測試檔的`git diff --check`通過；保存的WORKTREE.patch含標準unified diff空白context行，因此檢查該證據檔本身會提示trailing whitespace，保留以避免破壞Patch格式，非產品新增尾端空白。

產品Diff與證據已檢查：原文／人物正式歷史／經歷／目標與獎勵交易程式未擴充；新測試資料皆合成、PG只新增自有合成Owner。報告／Patch無Access Token、API Key、真密碼、Cookie或正式業務資料；公開基礎設施識別碼僅沿用儲存庫已有範圍，不公開Runtime env／Secrets。

**狀態：Gate B BLOCKED／GCP E2E NOT RUN／Merge、Alpha NO-GO。** 完成普通Push並讀回後停止，不進行其他產品開發或雲端操作。


## F5 最小防護提交（2026-11-12，Owner加速授權）

基準HEAD與遠端均為a7a21af6e9635ab9b31e6024dc13dc10bf08b6dd。提交範圍僅app/people.py、test_fact_provenance_contract.py、test_fact_source_safety.py、test_pg_fact_source_safety.py及本收據；其他Audit/發布準備草稿保持未提交，不混入本次功能修復。

完整產品Diff：一般fact寫入先檢查既有來源，撤回來源回409 source_restore_required，證據類型不符回409 source_correction_required；source衝突INSERT改DO NOTHING，不能清空revoked_at。沿用Owner交易鎖、來源關聯與冪等收據；未新增恢復API，未改UX、Schema或權限。

本輪命令：`/private/tmp/lw-integration-venv/bin/python -m pytest tests/test_fact_provenance_contract.py tests/test_fact_source_safety.py tests/test_people.py tests/test_relation_sources.py tests/test_people_connections_visibility.py -q --tb=short`：47 PASS、1 strict XFAIL、0 FAIL、0 SKIP。`LIFEWORLD_INTEGRATION_PG_CONFIG=/private/tmp/lw-integration-pg18-config.json /private/tmp/lw-integration-venv/bin/python -m pytest tests/test_pg_fact_source_safety.py -q --tb=short`：4 PASS。兩集合環境不同，不冒充GCP測試。正式source_kind/source_revision/quote缺口仍strict XFAIL，不宣稱F5全部完成。

差異審查：測試使用合成資料；固定字串為測試帳密，不含真實憑證或個資。重送、跨Owner、CSRF、版本、混合來源原子回滾及證據不覆寫已驗證。沒有正式恢復功能；Provider派送與完整持久化不是本次已通過項目。

Alpha Export控制面前置重查：Project/Instance/DB匹配、RUNNABLE、無未完成作業、精確物件404、服務帳號既有objectCreator。但本機無可用私網DBA連線證明當下Marker/Schema/Owner/ACL/Sequence仍與Studio基準一致；Q4僅沿用Owner結果且未重跑，不能替代結構驗證。Export BLOCKED／NOT RUN，無Operation ID、Generation、Checksum。需Owner透過既有Studio提供基準延續確認／新結構唯讀結果，無需重複Q4；未發出Export、不另換目標。

Gate A維持Approved；B BLOCKED、C NOT RUN、D NO-GO。沒有Migration、GRANT、Build、Deploy、Merge或切流。
