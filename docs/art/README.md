# GCP-144 美術素材與孵化候選

2026-11-07。沿用既有角色，不重新生成或替換正式設計。本次只交付盤點與可審查互動；沒有部署。詳列實際檔案尺寸、格式、alpha 與 SHA256 的 [Asset Inventory](ASSET_INVENTORY.json) 共25筆，從現有 PNG 重新讀取，沒有改寫素材。候選狀態不等於 Owner 核准，來源包及原始相對路徑完整保留。

| 類別 | 現有來源與用途 | 狀態／缺口與 fallback |
|---|---|---|
| Lumi 角色及狀態 | `collaboration/ui-kit/assets/lumi-poses-candidate-20261029/`：idle、listening、confirmed、quiet 等候選，來源1254平方RGBA；`derived-v1_1/poses/` 有128／256／512／1254衍生輸出 | 人體審查與角色組裝 anchor 仍待核准。App 沿用既有 CSS Lumi，不冒稱已整合圖片 |
| 世界房間背景 | `world-candidates-20261029/originals/room-day-base.png`、`room-quiet-base.png`，1448×1086；plant／cabinet／contact shadow 分層 | 原包標示 independent-candidate-not-accepted，1920原生規格不符；世界頁先保留既有版面背景 |
| 目標／任務圖示 | `shared-art/lifeworld-fullkit-shared-art/` 的 egg-rest／app-icon，以及 App 現有導覽符號 | 沒有獨立已核准的 task icon 完整套件；先用原有文字與圖示，不將 app-icon 當任務圖示 |
| 經歷視覺素材 | `collaboration/flow-wireframe/assets/confirmed@256.png`、`listening@256.png`；`derived-v1_1/poses/confirmed@*.png` | 原型／候選，非正式經歷狀態替代；保留文字確認與可讀成功回饋 |
| 孵化蛋三階段 | `shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-initialcrack-v1@512.png`、`lw-egg-deepcrack-v1@512.png`；`shared-art/additions-20261029/originals/lw-egg-shellsplit-v2.png` | paired shell closure 尚未通過來源包驗收；本候選只用 CSS 蛋殼與既有 CSS Lumi 驗證互動，沒有把未核准殼圖直接套用 |
| 獎勵及裝飾 | `shared-art/additions-20261029/originals/lw-effects-nourishment-v2.png`；房間 plant／cabinet 分層 | 候選；特效alpha最大253並非完全不透明。獎勵數量仍由伺服器決定，圖片不代表發放 |

## 統一接入規範

- ID：`lw-{category}-{state}-v{major}`；輸出 `{id}@{width}.png`，保留原始檔不覆寫。清單以 repo 相對路徑、原始 SHA256、核准狀態及替代文字對應。
- Lumi／蛋以512×512為桌面展示來源、256×256手機來源；圖層須維持同一畫布、腳底anchor與視覺比例，禁止單獨裁切造成跳動。UI以contain縮放，不拉伸。
- PNG／WebP透明背景用於角色、蛋殼、裝飾；實測alpha範圍確認透明不是白底。SVG只用既有可審核圖示，避免可執行外部內容。房間背景可不透明，桌面4:3／手機3:4須各自審查裁切，放大衍生輸出不可標原生高解析。
- 世界頁接入順序：Owner核准特定角色版本及anchor → Lumi idle／confirmed對照 → day／quiet房間與手機裁切 → 目標卡與經歷視覺。下一次映像只打包審核過的實際引用資產，不能整包夾帶私人來源或未確認權利素材。
- fallback保留原有CSS Lumi、背景及文字；圖片失敗不隱藏目標／任務內容。動作沒有完成就不得觸發進度或積分變更。

## 三次孵化互動契約

`app/static/birth.js`／`birth.css` 只接管首次建立目標後的 `#birth` 呈現。第一次細裂痕、第二次擴大、第三次蛋殼淡出並揭露現有Lumi。每階段1400ms，動畫中button disabled且程式鎖定，不接受連點跳階；第三階段完成前「進入我的世界」隱藏。原生button支援Enter／Space與觸控，狀態有live region；reduced motion停用變形轉場但仍保留三次明確輸入及400ms防連點。刷新會重置呈現進度，不新增／重複寫入目標、經歷或獎勵；伺服器既有lumi_hatched語意不變。這不是持久化孵化狀態Migration。

## 本輪驗收

隔離Chromium桌面鍵盤／手機觸控 ×一般／reduced-motion：`browser_tests/test_birth_interaction.py` **4 passed**。涵蓋第三下前不可進入、動畫中重送click不跳階及完成後Lumi可見。首次嘗試因沙箱阻擋Chromium啟動；允許隔離瀏覽器執行後，先重現缺少模組失敗，再實作。第一輪實作的4個測試定位失敗，是accessible name按階段變更而locator仍綁舊名稱；改用穩定data locator並保留初始accessible-name斷言，未放寬三階段規則。

既有journey／goal-flow／public-alpha測試已依新互動加入三次點擊；本輪未重跑這些完整後端旅程，不冒稱全部回歸通過。線上Staging及PostgreSQL未測本互動，未部署。
