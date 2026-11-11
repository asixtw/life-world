# 音訊與孵化生命週期增量驗收

本輪以遠端 main `68102f230aa947a434286ba9260e1ae75f6634b0` 為基準。既有 10 張採用圖、5 個音效、3 首程序 BGM、三次孵化已存在，不重做、替換或把舊素材找回缺口當成目前缺口。本次只修正前端生命週期，沒有部署、正式資料庫或雲端變更。

## 本次修正

- 音樂與音效仍各自預設關閉。關閉任一類立即停止／釋放該類所有音軌，不影響另一類。
- `play()` 尚未完成時停用、切換路由、撤銷素材或離頁，晚到的成功不會重新啟動聲音。
- 被拒絕的 BGM 清理後可由下次手勢重試。重複手勢、路由或回前景事件不會疊播。
- 背景頁與 pagehide 停止所有音軌；回前景只按目前場景與已啟用偏好恢復 BGM，不重播過去音效。新場景無核准 BGM 時保持無聲。
- 自然結束／媒體錯誤釋放來源。音效最多八條並行，快速連點先釋放最舊者。
- 同一孵化 DOM 的 mount 只綁定一次，避免重複完成聲或焦點跳轉。原三次明確輸入、1400 ms／減少動態 400 ms 的鎖定規則不變。
- 白名單、成功回執去重、偏好只存布林值的既有邊界保留。沒有新增第三方素材、依賴或外部服務。

## 本輪實跑

`node --test --test-reporter=tap tests/frontend_audio_lifecycle.cjs tests/frontend_birth_lifecycle.cjs`

- 最終相同 22 案在舊基準：8 通過／14 失敗；修正後 22 通過／0 失敗／0 跳過。
- pytest 入口 `python -m pytest -q tests/test_frontend_audio_birth_lifecycle.py`：2 個 wrapper 通過。執行使用最小環境，socket 連線被阻斷；wrapper 呼叫相同兩個 Node 測試檔，不是額外 22 個獨立功能。
- `node --check app/static/*.js` 逐檔語法檢查通過；`git diff --check` 通過。
- 採用清單的 18 檔逐檔 SHA-256 相符，15 個既有來源的 bytes 與採用檔一致。10 PNG／8 WAV 的 FFmpeg 解碼皆通過；三首 BGM 在隔離輸出目錄重製，與既有檔完全同 hash。

逐項輸出及程式 hash 見 [驗收回執](audio-lifecycle-20261109/RECEIPT.json)、[最終測試](audio-lifecycle-20261109/frontend-green.tap)、[基準紅測試](audio-lifecycle-20261109/final-baseline-red.tap)、[採用素材驗證](audio-lifecycle-20261109/adopted-media-check.json)。

## 驗收界線

Node 直接執行實際產品 JavaScript，DOM、計時器與 Audio 是明示替身。這能驗證競態與清理契約，不能代替原生瀏覽器／行動 Safari 自動播放、真正 BFCache、畫面響應、螢幕閱讀器或人工聽審。上述原生驗收在本修正版本未執行，既有歷史 Chromium 成果不能自動移作本次通過證據。本輪不因測試啟動既有受限瀏覽器，也不改安全設定。

完整後端回歸由共同合流版本另跑；本文件不宣稱 92 項素材或全部產品驗收完成。
