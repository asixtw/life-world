# Core／Audio 最新 main 合流驗證

日期：2026-11-09。基底main：`68102f230aa947a434286ba9260e1ae75f6634b0`。

## 本輪交付

- 連線池清理／shutdown修補與18個合成案例，先在此基底重現8個失敗，再修至全數通過。詳見[pool驗證](POOL_SHUTDOWN_REVIEW_20261109.md)。
- 正式產品audio／birth生命週期修補與22個Node案例，基底8 passed／14 failed，修後22 passed；另有2個pytest wrapper。詳見[前端驗證](../art/AUDIO_LIFECYCLE_20261109.md)。
- 合流保留兩份ACCEPTANCE與EVOLUTION尾端紀錄，沒有覆寫較新AI、Google、訪客或權限功能。
- 相對main產品變更只有app/postgres.py、app/static/audio.js、app/static/birth.js。沒有新增／改寫素材、SQL、runtime設定、套件鎖檔或部署設定。

## 同一合流版本實跑

- 完整pytest：532 passed、17 skipped、0 failed、0 errors，42.03秒。22個Node子案例由2個pytest wrapper執行，不能再加22說成554個pytest。
- 17 skipped是需要專用PostgreSQL18的案例，沒有環境而未執行；13 warnings是既有record_property／JUnit xunit2報告格式警告。
- 發布政策Mock測試：24 passed；非main的API／Web發布入口各自以隔離程序實跑，均在任何雲端呼叫前拒絕。
- 66個適用requirements.lock／requirements.api.lock pin核對相符；pip check通過。pytest程序阻斷socket connect／connect_ex／create_connection、使用最小環境與暫存合成資料。
- 產品檔與新增測試已經各自獨立審查；合流後重新執行完整回歸。原始前端紅燈TAP僅裁除行尾空白，不改測試結果與內容。

## 素材來源補核

最新main中的30個UI-kit直接圖像引用全部與先前原始清單SHA256吻合，包括先前雲端去敏副本中缺少原始bytes的12張。這是隔離副本的完整性補齊，不表示原GitHub曾缺圖，也不是新採用批准。

正式app採用的10 PNG與8 WAV亦已逐檔核對與FFmpeg解碼，三段程序合成BGM重製hash相同；沒有把未批准重建圖冒充原檔。

## 尚未完成

本輪未跑原生瀏覽器、人工聽審、真PG／Cloud SQL／TLS／Windows、線上ready或任何部署。既有較舊去敏候選中的Origin／E2E profile、Windows儲存保護等差異未整包移植，不能說全部第一線已完成。

此工作只在獨立非main分支。已確認repo內沒有GitHub Actions、保存的API trigger證據與Web文件只匹配main；本環境不能即時讀回控制平面全部trigger／webhook，亦沒有GitHub寫入認證。只做push dry-run且因無認證失敗，未建立遠端分支、沒有實際push或部署。正式發布仍須另行通過其授權與驗收。
