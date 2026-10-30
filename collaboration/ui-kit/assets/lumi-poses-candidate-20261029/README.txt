Life World Lumi 姿勢與獨立蛋殼 — 2026-10-29 候選包

內容：6 種 Lumi（idle/quiet 沿用，其餘4種新生成）與左、右獨立蛋殼原稿；idle/quiet既有512/256顯示版。每件為獨立真RGBA PNG，非sprite atlas。
狀態：product_candidate，未推GitHub、未宣告完成驗收。

目視：四款新姿勢均維持暖白蛋身、兩葉芽、綠眼、金嘴、mint翅；confirmed向下開翅微喜、celebrate向上開翅慶祝。一般回饋沒有蛋殼或特效。獨立兩殼維持cream/gold/sage並有鋸齒裂口，可各自載入。

必須注意：所有原稿同為1254x1254，但同畫布≠同尺度/同底線。manifest記錄alpha>127的實際bbox及建議bottom-center錨點，並非正式校準結果。工程可把每件的實測錨點對到場景地面，但這只是顯示裝配，不能取代規格輸出。新殼是左右分片重繪，不是把原shellsplit-v2上蓋/下碗切開；未驗證能重組封閉蛋、裂口逐像素吻合或完整孵化動態。

缺項：新資產512/256/128輸出、idle/quiet128；共同角色尺度及錨點精確校準；手機小尺寸及深淺背景邊緣檢驗；完整孵化裝配；產品/美術人工確認。原稿深色底可見少量亮邊，先候選審查，不宣稱乾淨邊緣驗收。welcome與原idle都為單側抬翅，差異較保守，需要確認是否足夠。

工具：built-in image_gen，transparent_background=true；未用Python改圖、裁切、縮放或合成。Python僅讀像素檢查alpha/bbox、原樣複製、產manifest/ZIP。Prompt統一：保留原識別與材質，改指定姿勢；無殼無背景無文字，要求1254畫布、底線1030與葉頂240。生成未精確遵守位置，因此記錄實際結果。詳見PROMPTS.txt。
