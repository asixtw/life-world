# 人物補充最小修正｜A1／A2

2026-11-11。基準 `23f8972`。**Gate A / Changes Requested / NOT APPROVED**。四步不變，不接正式API或DB。

## A1：不讓未保存看起來是稍後自動累積

- 第三步在輸入前揭露：公司／職稱／生日，以及多人、提及及尚無完整原子交易的新人物補充，只供設計展示，此次完成後不會保留到人物檔案。
- 第四步未保存區改標「此次完成後不會保留到人物檔案」；未核對或來源失效也在此區。不是已排程、待同步或稍後自動寫入。
- 示意完成頁列出未保存項目與所屬人物，明示只留本次記憶體、不會稍後自動保存、沒有偷偷塞進經歷原文／notes／tags／skills。重置或關閉Demo會失去記憶體資料。
- 正式發布阻擋：在多人定向、新人物原子交易或相應欄位契約未完成前，**不得對一般使用者開放無法保存的補充輸入**。不能僅掛警告後當成可發布產品。若正式版決定支援，須先完成Gate B保存契約與交易。
- 保留現行保守 `writableChange`；本輪不嘗試用「只有一位互動者」推定 target。新人物事實也保守列為不保存，避免未完成交易被假稱可用。

## A2：輸入來源與得知依據分開

| 欄位 | UI／意義 | 映射規則 |
|---|---|---|
| `source_kind`（Demo內部 `sourceKind`） | 輸入來源：我手動提供／本次原文片段 | 只描述輸入管道，不能推出證據類型；raw必須提供有效引用 |
| `evidence_type` | 這項資訊從何得知？人物本人告知／我觀察到／文件記載 | 無預設答案，未選擇不能加入候選；逐人逐項保存明確選擇 |
| `selected`（Demo `accepted`） | 第四步逐項核對 | 不等於獨立向人物本人查證；不能因選證據類型就自動勾選 |

UI值依序映射 `stated_by_person`／`observed_by_user`／`documented_source`，與現有PersonUpdateCandidate DTO一致。手動輸入不預設觀察、原文不預設本人告知、AI不決定證據類型。只有已有經使用者明確確認、仍有效且屬於同一候選的來源證據，未來才可沿用；來源改變必須重核對。本Demo不分析文字推定答案。

這是資訊依據，不是再次AI授權；不新增模型呼叫或同意勾選。編輯同一候選保留證據；新增另一候選不盲沿用上一項的證據。既有示意AI候選的「本人告知」由固定劇本明確記載，不是模型判定。未記錄證據的歷史資料正式串接前須補齊，不自行補值。

Gate B提案例（**非現行可送API**）：

```json
{"target":{"person_id":"owned-person"},"expected_person_revision":2,
 "dimension":"interests","value":"登山","evidence_type":"stated_by_person","selected":true,
 "source":{"source_kind":"manual","draft_id":"owned-draft","revision":3,"quote":null}}
```

`evidence_type`進現有候選DTO；`source_kind`、target／client_ref／來源版本屬新增契約，不能塞進description後假稱完成。API必須驗證Owner、目標、來源、版本與request_id；一個Confirm交易內提交經歷、新人物、事實、來源、任務、進度及獎勵。失敗全回滾、重送不重建、不把多人的事實套給第一人。

## 仍未解鎖

B1多人定向／pending_person多筆與原子交易：BLOCKED。正式草稿刪除、來源撤回、PR #22聯合驗收：未完成。公司／職稱／生日schema／API：NOT APPROVED / NOT IMPLEMENTED；生日正式輸入必須做真日期及年可空驗證，不能沿用Demo格式正則。真Google／Alpha／Gemini／手機Safari：NOT RUN。UX核准不代表API、安全或部署核准。

## 實際設計驗收

- 新增證據必填案例先實跑紅燈：1 FAIL，原本未選證據仍可加入候選。
- 完整本機Chromium套件：90 PASS、0 FAIL、0 SKIP（96.26s）。
- 隨後新增兩種source_kind × 三種evidence_type × 390/1440映射及草稿保留測試：12 PASS（32 deselected，非skip）。共102個不同設計案例分兩次通過。
- 完成頁2項再執行產生截圖，兩項皆PASS，不重複計數。
- 320/390/1440原有30張補充畫面已更新；另加390/1440未保存完成頁2張。固定底部操作、返回／草稿、取消／失敗／重複確認及訪客升級保留等回歸通過。
- 0 JS pageerror、0 API／模型請求由fixture監控；不代表正式服務交易通過。
- [完整日誌](evidence/PERSON_A1_A2_FULL.log) · [映射日誌](evidence/PERSON_A1_A2_MAPPING.log) · [收據／source hash](evidence/PERSON_A1_A2_RECEIPT.json)。
- [390未保存完成頁](screenshots-supplement/390/completion-unretained.png) · [1440未保存完成頁](screenshots-supplement/1440/completion-unretained.png) · [更新畫面集](supplement-gallery.html)。

執行指令：`python -m pytest docs/experience/ux-v03-candidate/tests -q --tb=short`，追加 `tests/test_supplement.py -k input_channel_never_implies_evidence`，完成頁重跑 `-k completion_discloses`。實機／正式API／Google／Alpha未執行。
