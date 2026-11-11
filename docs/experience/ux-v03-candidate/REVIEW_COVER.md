[最新 A1/A2：未保存去向、輸入來源與證據類型](PERSON_SUPPLEMENT_A1_A2.md)；本補修取代先前含糊的「暫不寫入」說明，Gate B/C仍阻擋。

[2026-11-11 人物補充延伸 Candidate：契約差異與 Gate B 待辦](PERSON_SUPPLEMENT_REVIEW.md)。整體 UX 尚未核准，不以設計補充解鎖工程 Gate。

# Owner 設計審核封面｜UX v0.3 Candidate R2

- 整體狀態：**Changes Requested／NOT APPROVED**。本次五項修改方向已同意，尚未收到「UX v0.3 核准」。
- PR：[#24](https://github.com/asixtw/life-world/pull/24)，維持Draft。
- 對照版本：`8d9357959b46718b51059b0f4bc9dfde5c69840a`。本輪只有設計／測試／文件，app與API保持`7013894`，完整設計Commit／Tree見交付收據。
- [可點擊 Demo](index.html)｜[R2畫面索引](gallery.html)｜[逐項差異](R2_CHANGES.md)｜[圖片對照](comparison.html)。解壓整包後雙擊index.html即可。
- 新圖：**99張R2畫面與補圖**，涵蓋390／1440、320窄屏、大字／縮放／短可視窗；R1原76張保留原位，不混用。
- A-01：人物抽屜固定頭與底部完成操作，中間獨立捲動；來源按需開啟，關閉不取消候選。
- A-02：可保存與目前不寫入分區，未核對及能力缺口不冒稱將保存；工作／公司合併說明。多人定向契約未接通仍列不寫入區。
- A-03：改原文保留摘要與手動內容，清楚要求重核對；舊AI候選不變成新來源結果，有效無關手動資料盡量保留。未改原文的返回不清狀態。
- A-04：手機四步專注模式暫藏全域導覽，完成、保存草稿或明確離開後恢復；離開選項與刪除草稿分開。
- AI：單一手動／AI選擇，預設手動；首次提供者／範圍授權，有效範圍不重問，背景AI不涵蓋未確認草稿。未選AI不啟動示意整理；沒有任何真模型呼叫。
- 實測：獨立Chromium **56 passed**。先重現8個設計失敗，再修復；實際API／外部網路請求均0。詳見evidence/CHROMIUM_R2.log與DESIGN_RECEIPT_R2.json。
- 窄屏／大字／縮放／鍵盤空間為Chromium與CSS模擬，**實機Safari／Android鍵盤仍NOT RUN**，不是無障礙認證或人工設計核准。
- Gate B/C：正式草稿刪除API、多人定向原子提交、工作／公司正式契約、PR22×24真Google升級與Alpha／Provider／實機回歸仍獨立待驗收，未以Demo通過結案。

請審查新版畫面與互動；只有明確回覆「UX v0.3 核准」後才進入產品串接。本輪不Merge、不Deploy、不修改正式資料。
