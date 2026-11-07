# GCP-144 AI｜RC v3 合成資料POC驗收

日期：2026-11-08。Owner本輪核准受IAP保護Staging POC及最多兩次真實Gemini合成生成；未來CRM個資政策不阻塞本次合成POC。這不是公開上線、付費、Secret掛載或部署授權。

## 本輪真實結果

| 測試 | Provider／Model | HTTP | Input／Output tokens | 實際候選 |
|---|---|---|---|---|
| Call 1：經歷摘要＋任務 | Gemini／gemini-3.5-flash-lite | 200 | 171／80 | 摘要依合成原文；提出明天重讀第2段並寫一句心得 |
| Call 2：已確認經歷任務 | Gemini／gemini-3.5-flash-lite | 200 | 189／41 | 摘要依確認內容；tasks=[]，不宣稱產生具體任務 |

每次上限256 output tokens、無重試；共2次，360 input＋121 output＝481 tokens。實際成本null，沒有啟用Billing。gemini-2.5-flash-lite與gemini-3.5-flash-lite的模型metadata均HTTP200；僅3.5本輪實際generateContent成功，不能把2.5列表可見當生成通過。Provider Request ID、應用request_id與原始生成文字保存在私有v3證據包。

## 產品操作驗收與限制

真實Browser → registered測試Owner → 正式Gemini Adapter → 可編輯摘要與任務候選 → 測試者操作確認UI → 正式後端交易 → 重送 → 刷新，已在**既有合成SQLite**完成；不是Product PostgreSQL或Google真登入。

實際檢查12項通過：registered gate、未確認不改狀態、真實模型標籤、編輯、確認保存、確認重送、第二次候選不改狀態、後續任務確認冪等、刷新讀回、固定規則只給一次獎勵、原文保存、兩個正式生成端點。確認動作由自動化瀏覽器驗收者操作，不冒稱Owner本人已逐字審稿。第二次任務是空候選，後續人工建立的任務不能算成模型輸出。

摘要未發現新增原文以外的人物／地點／事實；Call1任務有具體動作／產出，但「預定時間」偏泛。Call2空候選符合資訊不足可不猜測的契約，並非具體任務品質的第二個成功案例。兩次呼叫已用完，不為補品質結果自動再呼叫。

失敗回人工流程、Guest拒絕、CSRF、跨Owner及超額／並發保護使用獨立Fixture／安全測試；沒有假稱實際Provider本輪曾失敗。Product PostgreSQL回讀、IAP Staging真實GIS／AI E2E仍NOT RUN，等待備份／007／008／最小權限及精確部署另批。

## 額度修正

Runtime沿用既有requests收據，Owner／全域次數與保守預留費用改滾動24小時；失敗不釋放窗內預留、重啟不繞過、跨worker交易鎖防超額。新DAILY環境變數優先；相容舊GLOBAL_CALLS／BUDGET_MICROUSD但語意也改為日窗，不可把舊一次性預算未經批准直接部署。本次POC預留哨兵不代表實際金額，費用仍null。

## ADR-GCP144-AI-001｜後續GCP AI配額方案（Proposed）

決策：POC繼續現有Gemini Developer API Adapter及Provider抽象，不重寫。正式方案待Owner決定，未啟用任何付費或新GCP專案。

| 候選 | 認證與配置 | 配額／成本設計 | 待決 |
|---|---|---|---|
| Gemini Developer API Paid Tier | 後端Secret中的API Key／指定Project | 專案RPM/TPM/RPD、每Owner額度、Token usage、日／月預算及告警 | Billing與資料方案／金額需Owner批准 |
| Gemini Enterprise Agent Platform（原Vertex AI演進平台） | ADC／既有Service Account、Project／Location、最小IAM | Provider-specific quota、區域可用性、Token usage與Cloud Billing監控 | 不假設可沿用API Key或同一模型ID，不先開API／改IAM |

Provider介面仍回ModelResult、實際input/output tokens、provider_request_id與可為null的成本。未來由獨立Adapter處理認證、端點與配額；不更動領域確認／冪等／Owner隔離契約。沒有新微服務。

官方來源：[Agent Platform概覽](https://docs.cloud.google.com/gemini-enterprise-agent-platform/overview)、[Gemini API配額](https://ai.google.dev/gemini-api/docs/rate-limits)、[API Billing](https://ai.google.dev/gemini-api/docs/billing/)。Provider數值與費率須在採用時重查，不把本次合成測試升格為正式商用核准。

## 歷史結果

11/07的33項Fixture測試及兩次獨立合成API證據是舊輪結果。本輪新增兩次真實生成另計，不再沿用舊「本輪0次」或「免費尚未可測」作目前POC結論。原始舊文件由v3交付包保存，正式資料及備份不重置。
