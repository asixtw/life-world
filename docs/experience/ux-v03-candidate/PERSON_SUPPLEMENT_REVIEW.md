# 人物補充 Candidate｜2026-11-11

狀態：**Gate A Candidate / NOT APPROVED**。延續 `68fdd0f`，不是新的記錄流程。PR #24 維持 Draft。本輪未串 API、DB、Google 或模型。

## 與 R2 差異／取捨

- 四步不變。第三步每位人物下方新增「＋ 補充這次了解的人物資訊（選填）」，預設收起；類別單選後只輸入一項，不展開人物履歷。
- 興趣、飲食、專長、互動習慣沿用四維度。公司、職稱、生日可保留展示候選，但明示尚未支援正式寫入，不放 notes/tags/skills。
- 補充先為待核對候選，第四步逐項採納／排除；既有人物列原值加本次值，屬新增事實而非偷偷覆寫舊值。
- 多人物獨立 key、候選、核對狀態與編輯暫存。現有 Confirm 不支援多人物定向，因此多人／僅提及的資訊仍顯示在「目前不寫入」區；保留分人核對能力，但不冒稱完成後端。
- 來源可選「我手動提供」或「本次原文片段」。前者不是 AI 推斷、與原文修改無關時保留；後者片段需存在，變更後取消核對。每項保留 target、ownerId、dimension、value、quote、sourceRaw、sourceKind、accepted、supported、needsReview。
- 第四步沿用固定頭尾抽屜，不重放編輯表單。返回修改會打開該人物補充區。關閉預覽不取消勾選。
- 未加入候選的編輯值保留在人物暫存；前往第四步前需保留或明確清空，以免看似保存卻沒有進預覽。
- 不增加 AI。手動仍預設；任何既有 AI 情境皆明示示意，無對外呼叫。

## 正式契約檢查及 Gate B 提案（待核准，未實作）

| 現有介面／資料 | 已有能力 | 缺口 |
|---|---|---|
| PersonCreate / PersonEdit，`app/schemas.py` | name、role(s)、notes、tags、category、common_context 等 | 無公司、職稱、生日獨立欄；不能混塞到既有欄位 |
| PersonUpdateCandidate | interests / food / skills / habits、value、description、evidence_type、selected、conflicts_with | 無 target、client_ref、候選版本及逐項來源 ID |
| Confirm | request_id、expected_revision、person_id、person_updates、story | 更新由 `app/people.py::_apply_person_updates` 全套用單一 person_id；不能把第二人套給第一人 |
| people / person_facts / fact_sources | 人物 Owner、四維事實、經歷來源、revision／撤回 | 新人物與多目標更新需整體原子提交；手動輸入仍需明確 evidence_type，不等於第三人證實 |

建議增量 Payload（**不是現行可送 API**）：

```json
{"request_id":"stable-id","expected_revision":3,
 "people_candidates":[{"client_ref":"new-1","create":{"name":"小安"}}],
 "person_updates":[{"target":{"client_ref":"new-1"},"candidate_ref":"fact-1","dimension":"interests","value":"水彩","selected":true,"source":{"draft_id":"draft-id","revision":3,"kind":"manual","evidence_type":"observed_by_user"}}]}
```

既有人物 target 改 person_id，附 expected_person_revision；每項需明確 target，拒絕跨 Owner、失效來源與重複 client_ref。Confirm 同交易解析新人物、寫經歷／來源／事實／任務／進度／獎勵，再留下 request_id 去重收據；任一步失敗全回滾。取消／存草稿不建正式人物。同名不自動合併。

公司／職稱／生日需獨立 schema/API 審查：可提 `person_profile_candidates` 及來源關聯，或經核准後擴充事實維度；不得當下實作。生日建議拆 month/day/year(nullable)，DB CHECK 合法月日（含 2/29）與 API 日期驗證，年不由系統猜測；公司與職稱應保留有效時間與來源，避免覆蓋歷史。正式方案及 Migration **NOT APPROVED / NOT IMPLEMENTED**。

Gate B 必測：多人 client_ref 映射、錯 Owner、版本衝突、來源修改／撤回、交易中途失敗、並行同 request_id／不同 payload、草稿取消不建人、不重複獎勵。PR #22 另做同 Owner 升級保留人物編輯暫存及第三步 DOM；不同 Owner 切換清除原 Owner 暫存。**真 Google、Alpha、正式 API／模型／實機 Safari NOT RUN**。不啟用維護排程。

## 設計驗收

自動化測試與畫面位於 `tests/test_supplement.py`、`screenshots-supplement/320|390|1440/`。實際結果見本輪收據，不能以設計測試通過代表 Gate B/C 或 Owner UX 核准。

[人物補充手機／桌面畫面集](supplement-gallery.html) · [互動入口](index.html?scene=existing)

## 本輪實測收據

- 完整設計套件：84 PASS、0 FAIL、0 SKIP，88.44 秒。
- 最後新增重複確認按鈕案例：2 PASS，26 個非本次指定案例 deselected；不是 skip。合計86個設計案例通過，分兩次執行。
- 指令：`python -m pytest docs/experience/ux-v03-candidate/tests -q --tb=short`；追加 `tests/test_supplement.py -k repeated_confirmation`。
- 新入口紅燈先行：因原先沒有補充入口，重現1 FAIL。開發期間另有4項回歸失敗：2項仍檢查舊版不支援欄位文案；2項存草稿後測試誤以為回到第三步（現有恢復為第一步）。依實際契約修正測試導航及文案，未放寬來源或資料斷言。
- 新截圖30張（每個寬度10張），320／390／1440；檢查無橫向溢位、抽屜底部操作在可視區。原有手機大字／縮放測試也通過，非實機鍵盤驗收。
- Fixture監控0個API／外部服務請求及0個JS pageerror；新人物、保存草稿、確認與網路失敗都是示意記憶體操作。
- [完整日誌](evidence/PERSON_SUPPLEMENT_FULL.log)／[重複確認](evidence/PERSON_SUPPLEMENT_REPEAT.log)／[收據及Source SHA256](evidence/PERSON_SUPPLEMENT_RECEIPT.json)。

Gate A仍待Owner設計核准，Gate B/C未完成，不Merge、不Deploy、不修改正式DB。
