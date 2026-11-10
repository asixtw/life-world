# Code Review（自我審查；人工Review尚待完成）

已檢查：
- login不存在映射時不INSERT users；upgrade始終來源Owner，不執行Email合併。
- 無同意、相同Owner、來源變registered、到期或衝突，不呼叫abandon；放棄與新Session／收據同一交易。
- 交換收據只保存credential/session的hash；查核API僅信任當前Session與CSRF，不接受前端自報Owner。
- 未知結果不重送exchange；Cookie輪替但JSON損壞時先讀Session並核對收據。未決交易期間阻擋其他寫入與假取消。
- 同Owner保存成功不重繪或navigate，保留未保存表單；不同Owner切換清除前端快取且僅清理來源workspace。
- Purger不讀evidence.content，其他安全邊界不變，維護CLI仍拒絕Alpha。
- 未修改Schema、Migration、website權限、owner、模型額度、Cloud Build或任何部署設定。

剩餘風險：真Google／Safari／行動裝置OAuth尚未驗收；只有修復版部署後才能標正式PASS。視窗關閉與SDK阻擋可能無callback，保留原Session／資料並顯示未完成狀態；不推測驗證成功。外部儲存刪除需新租約／並發審查。SQLite009增加兩表會令Purger fail-closed，不能刪除此表／FK檢查來趕進度。

本輪沒有獨立Reviewer核准，不自行Merge或Deploy。
