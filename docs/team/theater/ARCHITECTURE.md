# 人物劇場 v0.5｜架構對照與候選介面

更新：2026-10-30。依[產品決策](DECISIONS_v1.1_2026-10-30.md)與[UX／行為規格](UX_BEHAVIOR_v0.5_2026-10-30.md)整理。下述介面是**工程候選**，不是已存在的正式 API、資料表或服務供應商承諾。可操作線框見[完整流程](../../../collaboration/flow-wireframe/README.md)；舊版保留為[快照](../../../collaboration/flow-wireframe-v1.1-archive/README.md)。

## 現況與缺口

| 領域 | 現有能力 | 封測前仍需完成 |
|---|---|---|
| Builder | 本機線框可輸入情境、已建立人物、目的與來源選取；正式 App 有人物卡及既有私人筆記 | 與正式人物權限、來源版本及人物刪除狀態串接；正式建場交易 |
| Session | 線框的本機場次、歷史與回顧 | 伺服器所有者、版本、去重、過期／刪除與跨裝置恢復 |
| Behavior | 七種預寫狀態及錯誤分流 | 可信人物模型、受約束的結構化輸出及行為驗收 |
| Director | 線框每輪有限兩則角色交流，可介入、旁聽與停止 | 真正 C1 調度、停止生成及晚到結果去重；C2/C3 未承諾 |
| Gateway／Usage | 線框配置 1v1 八次／多人六次玩家行動、每段至多三則、Lumi 兩次、技術重試一次 | 供應商未定；後端費用、呼叫、輸出、總額與併發硬限制，並由 Boyi 核准數值 |
| ASR | 權限、停止、校對及失敗退路的**模擬操作** | 真實收音、轉錄、大小／時長、儲存與刪除政策；不可把線框當真實辨識 |
| Lumi／Recap | 本機私人建議和已展示事件回顧 | 服務端私人上下文隔離、總額共用、結束失敗保底及歷史管理 |

封測另需真實圖片辨識，屬既有素材整合契約的待完成能力，不由劇場線框冒充。該契約未包含在此獨立文件分支；正式整合時需一併審查。人物模擬與示範角色分資料域，任何預寫回應都不回寫正式人物、目標、經歷或積分。

## 候選事件與不變條件

```text
ScenarioDraft { scenario_text, purpose, participant_ids[], source_refs[] }
SourceRef { person_id, source_id, source_version, selected_by_user }
Session { id, owner_id, scenario_snapshot, participant_snapshots[], status,
          revision, limits_snapshot, usage, ending_reason }
TurnRequest { session_id, client_request_id, expected_revision, speaker_id,
              recipient_ids[], text, input_kind }
BehaviorEvent { event_id, request_id, speaker_id, recipient_ids[], behavior,
                text, visibility: queued|displayed|discarded, displayed_at? }
SessionEnd { session_id, expected_revision, reason, displayed_event_ids[] }
```

- `source_refs` 明確記錄人物／來源版本；沒有被選取的資料只可作標示假設，來源撤回後不可再次注入模型。
- 伺服器以 `owner_id` 及不可猜測場次識別驗權；`client_request_id` 防重送，`expected_revision` 防舊頁面覆蓋，限額檢查在產生成本前完成。
- 前端確認**實際展示**後才標記 `displayed`；停止或介入清除待展示序列，晚到結果不得使 `discarded` 復活。已發生的供應商成本不能宣稱撤回。
- 沉默 `CHARACTER_SILENCE` 與 `PROVIDER_REFUSAL`、`PROVIDER_ERROR`、`BUDGET_EXHAUSTED` 分開；技術失敗保留玩家草稿，不能假裝人物沉默。
- Lumi 只能讀本場需要的已展示內容及使用者私訊；Lumi 建議不進角色上下文。回顧只使用已展示事件，不推論真人心智或使用者長期人格。

## 整合順序

1. Boyi 以線框核對第一次使用、來源／假設、多人介入和回顧；Jerry 審查資料權限、刪除、儲存與資源限制。
2. 定義上述候選契約的正式型別、錯誤碼與交易邊界，再測試建場、行動、停止、重送及回讀。
3. 接入供應商 adapter／ASR／圖片辨識，與正式人物及來源串接；禁用假成功路徑。
4. 以真實裝置與封測者驗證操作直覺、非預測標示及成本護欄；達標前線框仍只是一份模擬樣本。
