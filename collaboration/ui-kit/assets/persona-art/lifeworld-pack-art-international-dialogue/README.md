# Life World — 國際協調示範人物美術 v1

**已製作並檢查 5 位虛構角色頭像 + 1 張五人協商封面。** 全部由 OpenAI built-in `image_gen.imagegen` 實際生成；不是提示詞或占位圖。用途限 `demo`（測試／POC／封測），**正式版未核准**，產品／內容驗收仍由 Boyi、整合審查由 Jerry 負責。

## 檔案與固定 ID

| 角色／封面 | Asset ID |
|---|---|
| 美方代表 | `portrait-international-dialogue-us-representative` |
| 伊方代表 | `portrait-international-dialogue-iran-representative` |
| 中立調停者 | `portrait-international-dialogue-neutral-mediator` |
| 國際組織觀察員 | `portrait-international-dialogue-international-observer` |
| 航運方代表 | `portrait-international-dialogue-shipping-representative` |
| 國際協調封面 | `cover-international-dialogue` |

- `originals/`：6 份工具輸出的原始 PNG，原始 bytes 保留。5 份頭像為 **1254×1254**；封面為 **1672×941**。不把它們誤稱為原生 1024／1600×900。
- `masters/`：5 份 **1024×1024** 頭像規格化原稿；1 份 **1600×900** 封面。這些是從生成原稿衍生的標準尺寸 master。
- `exports/`：5 份 **256×256** 頭像顯示輸出；1 份 **800×450** 封面。
- `previews/`：5 份 **256×256 透明圓形裁切預覽**，以及方形／日間／Quiet 背景裁切總覽。總覽上的技術標籤位於圖像外，不是烤入美術。
- `assets/manifest.json`：每個 ID、實際路徑、尺寸、bytes、SHA-256、中文 alt、版本、工具、來源、使用依據與正式版未核准狀態。
- `provenance/`：精確提示詞、來源規格固定 commit／blob SHA、原始產物來源路徑、可重跑技術輸出程式和驗證記錄。工具未公開確切模型版本，照實標示未知。

## 角色與使用界線

這是五個**完全虛構的職務角色形象**，沒有使用真人政治人物照片、私人資料或現任官員肖像作參考；不能當作任何實際人士的官方頭像。國籍角色名不是對人物個性、立場或能力的推論。服裝為非制服的商務服飾，五位保持同等尊重的表現方式。

封面是**想像中的平和協商場景**，不是新聞、真實談判紀錄或官方宣傳。圖中恰好五位角色，無文字、旗幟、國徽、機構徽章、聯合國品牌或真實公司標誌。公開立場資料、模擬對話與日期由內容模組另外提供，本包不主張任何實際政治立場。

建議在頭像旁由 UI 顯示 **「示範角色・虛構形象」**，場景旁顯示假設模擬標示；角色名稱、對話及來源等必要文字不要烤入圖片。沒有宣稱可任意商用、完成法律審核或獲機構背書。未使用或重新生成任何既有受阻 Lumi 資產，也未使用《空山問獅會》資產。

## 整合

在 `collaboration/ui-kit/` 下以獨立 `assets/international-dialogue/` 子目錄整包接入，或由整合者明確更新 manifest 基準路徑；**所有 manifest 路徑相對本包根目錄**。上表只固定 asset ID；內容模組 persona ID 若不同，請作明確一對一 AssetRef，不默默更名。

頭像通常使用 `exports/...@256.png`，以 CSS `border-radius:50%` 裁切；不要用透明圓形預覽替代唯一 master。保持正方形比例；放大顯示改用 1024 master。封面使用 `@800x450` 或 `@1600x900`，保持 16:9，不任意裁掉左右角色。背景色不替代文字對比或焦點狀態的工程驗證。

這些是扁平 PNG，不是 PSD／可編輯向量／分層人物。技術處理只做等比例縮放、封面極小置中裁切、圓形 alpha mask 和預覽排版，沒有重繪、修臉、改色或新增生成內容。原稿自帶的來源資訊保留在原始檔；衍生檔另外以 hash／manifest 追溯。

## 驗證與交接

已逐一查看 6 份生成圖及標準封面，並以裁切總覽檢查 5 位頭像的 256 輸出、圓形裁切、日間與 Quiet 背景。面部與主要髮型可辨識；封面五人無重複、無遺漏。實際檔案的 dimensions／hash／path 另由驗證程式核對。

重跑技術輸出（需要 Python + Pillow）：

```bash
python provenance/export_assets.py
python provenance/verify_assets.py
```

本包完成的是**圖像層級 QA**；不宣稱已測手機瀏覽器、Safari、正式頁面、可操作劇場、即時 API 或部署。本代理未上傳、發布或修改桌面 repository；主代理負責轉交與整合。

`packages/` 是每份不超過 8,000,000 bytes 的自然分組運輸 ZIP，不是單一 ZIP 的二進位切片；依 `packages/INDEX.json` 解開到同一位置即可。不要把重複 ZIP 再提交進 repository。
