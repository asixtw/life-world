# Owner 設計審核封面

- 設計版本：**UX v0.3 Candidate / NOT APPROVED**。
- Owner 決定：**Changes Requested（預設）**。尚未收到「UX v0.3 核准」。
- PR：[#24](https://github.com/asixtw/life-world/pull/24)，維持 Draft。
- 程式基準：7013894；本輪提交只有設計檔、證據與文件，app／API 沒有異動。完整設計 Commit／Tree 在本機交付收據與 PR。
- 390px／1440px：[畫面索引](gallery.html)（74個狀態畫面＋可捲動抽屜補圖）。
- Demo：[index.html](index.html)。解壓整包後雙擊，無須終端機或帳號；重新載入重置資料。
- 對照：[v0.2／舊 PR24／v0.3](comparison.html)。
- 新的合併前關卡：[MERGE_GATES](MERGE_GATES.md)。
- 暫無保存契約：獨立工作／公司、逐人物定向異動、多人待建人物與通用來源DTO；見[能力表](FIELD_CAPABILITIES.md)。
- 草稿刪除 API：**NOT IMPLEMENTED**，只有可點的確認、失敗、衝突、重試設計；不會刪真實資料。
- 帳號：沒有產品身分切換頁籤；UI 設計依 Session 狀態。Demo Session 為標明來源的合成 Fixture，不是真 Google 交換。
- 同 Owner upgrade：示意停在第三步並只解鎖人物區，保留原文／數量及既有內容；login 切另一Owner，明確同意、不帶入表單。
- 測試：獨立 Chromium **26 passed**，各互動在390與1440執行；程式監測 API／外部網路請求皆0。這不是人工 UX 核准，也不是真 Alpha 或帳號聯合驗收。
- 未驗收：真 Google、真 Session／CSRF輪替、正式 Alpha、AI／媒體Provider、產品草稿刪除／多人原子交易、實機 iPhone／Android、正式畫面人工簽核。

請先審查畫面、操作與手機文末導覽位置。只有明確回覆「UX v0.3 核准」後，才按核准設計繼續產品串接與回歸；Merge／Deploy仍不得自行執行。
