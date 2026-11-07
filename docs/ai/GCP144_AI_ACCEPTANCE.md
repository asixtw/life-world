# GCP-144 AI 定點驗收｜2026-11-07

獨立 AI 候選，未部署。延續 [既有 API／安全契約](GCP143_AI_CANDIDATE.md)，不修改 Cloud Run、Secrets、IAM、資料庫 schema 或權限。

| 項目 | 本輪狀態與證據 |
|---|---|
| 真實經歷整理／任務生成 | **BLOCKED**；真實 generateContent 呼叫 0 次。既有模型清單 HTTP 200 不證明免費 tier 或剩餘 quota，免費限定尚無可驗證的該 Key 所屬專案證據。未讀取 Key 值、未試探生成或切換 Key。 |
| 模型候選 | `gemini-2.5-flash-lite`；僅候選，不宣稱已呼叫或已啟用。待免費方案證據後，首批上限為 2 次合成文字請求、每次輸出最多 256 tokens、無自動重試。 |
| 費用／用量 | 本輪生成 0 次；供應商實際費用未知，不能寫為 0 元。成功候選收據現保存供應商回報 input/output tokens；缺失保留 null。cost 未回報同樣保留 null，不以預留額代替實際帳單。 |
| 人工編輯／確認 | 合成傳輸替身 API 驗證：候選/失敗不寫正式經歷、進度、獎勵；使用者可自行編輯摘要確認。確認重送冪等、任務確認0額外獎勵，重建 Service 可從相同持久化 SQLite 測試庫讀回。 |
| 權限／隱私／失敗退路 | 沿用 registered Owner／CSRF／Owner isolation、持久化 attempt/budget 限額；模型失敗回固定錯誤並可人工處理，無自動重試。收據不保存 prompt、原文或模型輸出。 |
| PostgreSQL／Browser | 本輪 **NOT RUN**；歷史隔離 PG18.6 18 項契約結果另見 GCP143 文件，不能當今天線上或真實模型證據。 |

本輪命令：`python -m pytest -q tests/ai tests/test_model_eval.py tests/test_model_eval_gemini.py tests/test_model_eval_cli.py tests/test_media_provider_boundary.py` → **33 passed in 0.57s**。全為明示合成輸入/傳輸替身，不構成真實 AI PASS。新增驗收先紅燈：收據缺 input_tokens；修正後通過。另一新增重建 Service 測試初次因類名誤植失敗，修正為正式 LifeWorld 類，非產品功能紅燈。

下一個最小解除事項：計費管理者確認既有 Key 所屬專案為可用的 Free tier（勿提供 Key 值）；不需先掛載到線上服務。若需要付費呼叫，另取得具體金額上限核准。本輪沒有執行付費服務啟用或正式部署。
