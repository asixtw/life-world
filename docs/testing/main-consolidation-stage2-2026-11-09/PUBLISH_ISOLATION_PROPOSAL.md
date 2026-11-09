# main Merge的API發布隔離提案（未執行）

唯一建議變更：既有API Trigger `6ffa2066-8edd-4406-9f3f-31f967da57dc` 的 `approvalConfig.approvalRequired` 從未設／false改為true。保留repository、^main$、includedFiles、Build SA、YAML及disabled原值；不改發布器、IAM、Web Trigger、Cloud Run、DB或Secrets。

Google官方說明：需要核准的Trigger只建立待核准Build，核准後才開始執行；這能阻止「合併Git就自動執行發布步驟」。[Cloud Build人工核准](https://docs.cloud.google.com/build/docs/securing-builds/gate-builds-on-approval)。這是待Owner另批核准的方案，不是本輪已完成的雲端設定。

## 最小可審查差異

```diff
 approvalConfig:
-  approvalRequired: false  # 現況未設，等價false
+  approvalRequired: true
```

1. Owner核准此**具體Trigger變更**，以及之後精確SHA的main Merge；不要把一般PR審查或Push授權當作上述兩項授權。
2. 執行前保存整份Trigger設定與雜湊，唯讀查核當前所有該Trigger的QUEUED／WORKING Build。新gate不會暫停已開始的Build；若有既有工作，停止Merge流程，另外確認處置，不擅自取消他人的Build。
3. 使用現有管理權限只變更approvalConfig，讀回完整設定，除該欄位外須零差異。不新增IAM；缺cloudbuild.triggers.update時才交Owner一次操作。
4. 再讀main／候選SHA，完成Review與必要檢查後，由Owner明確授權Merge。Web includedFiles不被本整合Diff命中；lw-public無main自動發布目標，現役100%保持。
5. Merge後唯讀確認新API Build是待核准、沒有步驟執行；**不自動批准Build**。若出現WORKING或任何意外執行，即停止後續操作、回報Owner；Git revert不能保證已排程Build停下，也不是Cloud Run回滾。

Console入口：https://console.cloud.google.com/cloud-build/triggers?project=life-world-513506 （asia-east1 → lw-api-main → Edit → Require approval before build executes）。這只是未執行操作入口，本輪不需Owner現在點擊。

## 復原

- 比對Trigger當前設定仍屬於此次變更，沒有他人並行修改後，只把approvalRequired恢復為原false語意，其餘欄位保持。不使用整份舊Trigger覆蓋新設定。
- 待核准Build必須逐筆確認；改Trigger不等於批准、拒絕或取消既有Build，不假設自動處理。任何核准／拒絕待核准Build需要另行授權。
- **不要在Merge後立刻無條件移除gate**：下次main相關Push仍可能發布至lw-api-main。只有Owner已接受恢復自動API發布、發布器模板相容與API回歸通過後，才能還原false。
- 若Owner不希望建立任何待核准Build，備選為同一Trigger暫停disabled=true；也需要單獨核准，且不會取消已在執行的Build。不得同時擴大修改兩個Trigger或刪除Trigger。

本輪不提供自動執行的Cloud Patch腳本、不修改發布器、不新增第三服務、不更改lw-public的發布管線。main整合完成不等於新public Release。
