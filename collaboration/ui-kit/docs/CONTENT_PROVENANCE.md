# 內容生成與來源核對紀錄

共同工程基準：`1c9d502f32688bcc3c73e4b99a2cc3724c179047`。資料版本：`content/*.v1.json`、`evaluation/*.v1.json`。輸入規格為 `docs/team/PROMPT_OUSANG_START.md`、`PROMPT_SIMULATION_001.md`、`PROMPT_UI_001.md` 與美術交付規格；人物名單選 A。生成提示為：依三組指定十五人物製作 demo 角色的動機、視角、語氣、邊界；每人三段獨立多輪示例、兩個事件不重疊的保留題；六場各三條主線並有不同後果。反覆編輯要求：不得將虛構台詞冒充原話、不得以已知歷史結果倒推角色、國際職務不得暗示真人秘密動機、保留題參考答案不得進模型輸入。

工具：本地 PowerShell、TypeScript／Vitest／Vite、Chrome UI 驗證及公開來源網頁檢索。內容由 Codex 輔助撰寫、人工使用者尚未驗收；精確執行模型版本未知，不填造版本號。`script-voices.v1.json` 為預寫回應資料，不是即時模型輸出。前端只 import `evaluation/inputs.v1.json` 供契約測試，正式 UI 不載入保留題或 `evaluation/reference.v1.json`；即時模型端點未提供，因此沒有模型看到保留題或參考答案的實際請求。本地測試載入兩檔只用於資料隔離檢查。

## 公開來源機器查核與人工待審

以下為 2026-10-28 的資料定位查核，不是 Boyi 人工史料審閱，所有 `reviewed` 維持 `false`。

- [Perseus《Apology》作品記錄](https://catalog.perseus.org/catalog/urn:cts:greekLit:tlg0059.tlg002)：確認作品 CTS URN `tlg0059.tlg002`、英譯版本與 17a 起始定位；引用欄位指向作品記錄，不聲稱逐句文本已核對。
- [Perseus《Republic》作品記錄](https://catalog.perseus.org/catalog/urn:cts:greekLit:tlg0059.tlg030)：確認作品 CTS URN `tlg0059.tlg030`、英譯版本；第七卷 514a–517a 仍待逐段人工核對。
- [IAEA GOV/2024/61 PDF](https://www.iaea.org/sites/default/files/24/11/gov2024-61.pdf)：封面載 2024-11-19、文件號與題名，於 2024-11-21 解密公開；只用作 2024 截止的公開背景，不推斷虛構代表的心理或私下立場。
- [IMO 2024-05-24 新聞稿](https://www.imo.org/en/mediacentre/pressbriefings/pages/imo-msc-resolution-red-sea.aspx)：頁面行 18–38 有日期、MSC 108 對商船與船員安全的決議背景及航運風險表述；替換會持續更新至 2026 的無日期熱點頁，不把新聞稿當虛構航運代表的本人立場。

其餘十一筆來源的精確篇章與逐項主張仍標為 `unverified`，不能作已查核主張。角色卡中的 `fieldEvidence` 對每項摘要、動機、視角、語氣、行為邊界和時間界線標示 `interpretation` 或 `design_assumption`；來源 ID 只定位參考材料，不能把整段心理創作升格為史實。國際職務角色的內在設定全部為 `design_assumption`。
