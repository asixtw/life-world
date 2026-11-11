# 精簡人物選擇｜整合候選，未核准UX

2026-11-11。只改四步第三步的選擇視圖，不改正式資料庫、帳號、StoryInput或Confirm交易。

## 視圖與資料

experience_people.js提供editor/collect/hydrate；ConnectionsUI在record模式委派，review/manage仍保留舊編輯器。所有保存均投影到原StoryInput：participants、mentions、pending_people、title。人物卡的UI row key不當作person_id；待建client_ref仍沿用既有草稿契約。未選人物可直接前往第四步；主動選擇有關人物後需選取/新增或明確取消。

新增的已有人物卡沒有預設角色。共同參與不自動等於直接互動；提及需人工選來源位置。虛構/歷史人物的新增卡只提供提及選項，後端仍獨立拒絕不合格參與。舊同人參與與提及、重複原文名字的精確位置分別保留，不自動合併或推斷。

搜尋只用目前Session Owner的world.people，無跨帳號建議。挑選或移除不呼叫資料庫寫入；個人化/AI不因開啟選擇器自動呼叫。新增人物仍pending，最後人工確認才正式建立。進階原文稱呼及故事標題預設收合。

## 本機恢復與回復

workflow_existing_people保存Owner、有限卡片清單、穩定row key、角色與來源位置，使用既有Owner/draft Media IndexedDB。復原驗型別/數量/鍵唯一；原始素材不因錯誤被覆蓋或清除。是否關聯人物由原表單狀態保持，不因身分升級改變。

伺服器格式沒改，但9b0592c舊前端不懂這個新增本機欄位，不能宣稱UI回退自動恢復所有未保存選擇。正式發布前須相容reader或匯出策略；目前只有隔離合成資料，Alpha未套用。此風險不以測試PASS消除。

## 測試與Gate

browser_tests/test_experience_people_picker.py驗證型別、來源不代選、同人雙角色、Owner、未完成恢復及320/390/1440鍵盤/空白搜尋；原工作流測試改用新控制項但保留資料斷言。API/Node、整合Chromium收據與限制見INTEGRATION_RELEASE_REPORT.md。沒有真Google、真AI、GCP新Revision或Safari驗收，不代表Owner UX Approved。
