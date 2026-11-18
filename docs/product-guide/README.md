# 產品新手導覽與 PWA 整合候選｜2026-11-18

## 結果

本批是**產品導覽**，不是 onboarding 重做。`ProductGuideUI` 與既有個人設定／第一目標／三習慣／孵化流程分開；看完、跳過、重播導覽不代表完成 onboarding，不建立示例資料、不發教學獎勵。工程驗證通過，Owner 視覺／真機驗收仍待決。

- 正常根入口：未登入、此裝置未看過新版介紹時顯示三幕；`/intro`／`#intro` 可主動重播。三幕以「努力容易被忘記的生活困擾 → 一句話的簡報紀錄示例 → 逐步累積的回報」為主。第一幕不談 AI、目標管理或 Lumi；第二幕約六秒顯示固定示範，不呼叫模型；第三幕才以 Lumi 與房間變化回應成長，不虛構使用者已獲成果。
- 三次主要點擊即可看完。只有主動點「開始我的世界」才進入既有歡迎／首次設定；已完成設定的登入使用者不會每次被送回介紹。
- 右上「關於」提供**認識 Life World／使用教學／加到手機主畫面**。桌面保留側欄，手機仍是世界／目標／紀錄／關係四主分頁，不增加第五頁。
- `#tutorial` 是可重看的完整教學；實際目標、記錄、最後核對、世界頁只加入可收起／暫停的簡短提示。未保存表單經由既有離開保護，不被教學重繪。已點「知道了」的提示不持續重複；「稍後繼續」後由教學入口續看。
- 介紹偏好是裝置層級 `lifeworld:intro:v2`；操作提示為**後端 Session Owner + 此瀏覽器**的 `lifeworld:guide:v1:<owner>`，不參與權限判定、不宣稱跨裝置同步。localStorage 不可寫時使用 sessionStorage／記憶體，且不讓較舊偏好蓋過新值。
- PWA 沿用 PR27 的 Manifest、圖示、裝置模型與安裝程式；首次真實經歷 Confirm 成功後只在世界頁提供可忽略的安裝提示，或由使用者主動開啟。未保存訪客世界有明確提醒，不承諾 Session 轉移，不宣稱離線可用。
- iOS 提供 Safari 分享／加入主畫面說明；Android 有真實瀏覽器事件才可呼叫 prompt，沒有則顯示選單教學；IG／FB 提供外部瀏覽器說明與複製網址，不強制跳轉。取消／稍後可重開；接受 prompt 不等於完成安裝，只有 appinstalled 回報才顯示完成。
- v05 的 **23 個現役執行資產**（包含動畫、圖片、音效）已逐位元保存，舊版完整介紹保留在 `/intro/v05/`，可從教學頁下方重播。沒有改 v05 狀態機、音效、Lumi 圖；新三幕只重用圖片與既有 App 音效系統，預設靜音並尊重 reduced-motion。

### 本機實際產品入口

- 導覽獨立候選：<http://127.0.0.1:8211/>；直接重看 <http://127.0.0.1:8211/intro>，教學 <http://127.0.0.1:8211/#tutorial>。
- 導覽 + **未發布**手機佐證修復的相容性驗證版：<http://127.0.0.1:8212/>。
- 不需 Google。用既有「不用註冊，先開始」→ 輸入合成稱呼與 Bio → 建立目標與三習慣 → 孵化 → 記錄新經歷 → 四步核對 → 最後保存。測試用本機 SQLite，真 AI 關閉；沒有公開測試登入後門。
- 兩個服務只綁 127.0.0.1，資料分別在 `/private/tmp/lw-guide-review-data-20261118` 與 `/private/tmp/lw-guide-mobile-review-data-20261118`，不連 GCP 或正式 PG。

## 證據

基準：main `75f2a79c281db4f7e880f3ae44135b0a28152849`；[PR27](https://github.com/asixtw/life-world/pull/27) 已合併（來源 `396f2c0`）。本批 [來源檔案指紋](SOURCE.json)：`cb90fd7638a8181cc79f11a8b878151c3f0723b7307ff085cb2b226720d44867`。功能分支 `feat/product-guide-integration-20261118`；正式 Merge／Build／Deploy 不在本批。

|實際執行|結果與範圍|
|---|---|
|[API／安全回歸](evidence/API.log)|52 passed / 0 failed；介紹路由、v05 指紋、PWA 模型、Session、Owner、草稿與 AI 授權|
|[瀏覽器](evidence/BROWSER.log)|19 passed / 0 failed；正常入口、四尺寸、跳過重播、無／部分儲存權限、雙帳號、正常登入、完整 onboarding → 四步 Confirm、進度／任務／原規則獎勵、教學暫停／返回與 PWA|
|[固定示例動畫](evidence/ANIMATION.log)|1 passed；另行實測六秒逐步呈現、不中斷下一步、無 AI／資料寫入；與上列合計 20 個不同瀏覽器案例|
|[Node](evidence/NODE.log)|48 passed / 0 failed；精度、經歷輸入與音效生命週期|
|[佐證相容 API](evidence/MOBILE_COMPAT_API.log)|21 passed / 0 failed；獨立疊合工作區，沒有修改原佐證候選|
|[佐證相容瀏覽器](evidence/MOBILE_COMPAT_BROWSER.log)|5 passed；320／390／1440px JPEG 成敗、輸入保留、私有縮圖、人工完成、回應遺失只讀核對及完整新使用者旅程|
|JS syntax／git diff --check|PASS|
|真實 iPhone Safari、Android Chrome、IG／FB、原生安裝、實際虛擬鍵盤、Safari/WebKit|NOT RUN；UA／安裝事件／剪貼簿權限以 Chromium 合成環境驗證，不冒充真機|
|PostgreSQL、正式 Google／Gemini、GCP 上新版 UX|NOT RUN；本批只做本機 Chrome／SQLite，Python3.14.10，Pillow11.3.0|

各列是不同執行收據，部分驗收範圍重疊，不能把所有數字當作不重複案例總數。沒有 FAIL／SKIP／XFAIL 的本批最終套件；未跑項目沒有記 PASS。既有 TestClient/httpx 棄用警告保留。

執行指令（隔離候選根目錄）：
```sh
export LIFEWORLD_DB_BACKEND=sqlite LIFEWORLD_AUTH_SOURCE_MODE=direct LIFEWORLD_AI_CALLS_APPROVED=false
export PLAYWRIGHT_BROWSERS_PATH=/private/tmp/lw-guide-video-tools
# 首次重現錄影時只安裝測試工具，不修改正式依賴。
/private/tmp/lw-operations-venv/bin/python -m playwright install ffmpeg
export LIFEWORLD_NODE=/private/tmp/lw-operations-venv/lib/python3.14/site-packages/playwright/driver/node
export PYTHONPATH="/private/tmp/lw-evidence-pillow113:$PWD:$PWD/tests"
/private/tmp/lw-operations-venv/bin/python -m pytest tests/test_product_guide_integration.py tests/test_pwa_install.py tests/test_identity_goals.py tests/test_draft_review.py tests/test_owner_boundary_matrix.py tests/ai/test_draft_ai_consent.py -q --tb=short
/private/tmp/lw-operations-venv/bin/python -m pytest browser_tests/test_product_guide_integration.py -q --tb=short
$LIFEWORLD_NODE --test tests/frontend_quantity.cjs tests/frontend_experience_validation.cjs tests/frontend_audio_lifecycle.cjs
```
錄影：`/private/tmp/lw-onboarding-evidence-20261118/product-guide-example.webm`，只有固定示例，不含私人輸入。

相容性工作區 `/private/tmp/lw-guide-mobile-compat-20261118`：疊合本批 patch 與原 `fix/mobile-evidence-20261118` 的九檔 patch，均先 `git apply --check`，無人工覆寫 Hunk。該工作區執行 `tests/test_mobile_evidence.py tests/test_product_guide_integration.py`，及 `browser_tests/test_mobile_evidence_ui.py browser_tests/test_product_guide_integration.py -k 'failure_is_local or unknown_result or full_new_user'`。手機測試僅改 Artifact 輸出目錄，原佐證九檔 SHA256 全部維持，並未把修復混入本批提交。

### 畫面與差異

[手機：為何誕生](evidence/390-intro-1.png)／[一句話的整理示例](evidence/390-intro-benefits.png)／[第三幕](evidence/390-intro-world.png)／[使用教學](evidence/390-tutorial.png)／[iPhone 安裝說明](evidence/390-install-ios.png)／[桌面介紹](evidence/1440-intro-1.png)／[桌面教學](evidence/1440-tutorial.png)。全部 320／390／768／1440 畫面與 IG／FB／Android 分流在 `/private/tmp/lw-onboarding-evidence-20261118`。

主要差異：原 main 只有歡迎與 PWA 安裝選單；現在補上價值導向的三幕介紹、可重看教學與操作提示。**既有 onboarding 表單、三習慣、孵化、四步經歷、AI 授權與 Confirm 交易不改寫**。新後端僅三類靜態路由（App 介紹外殼與 v05 保留），不增加資料表／DTO／正式 API 寫入。

## 待決事項

1. Owner 審查最新生活情境文案與視覺；「努力被遺忘、感覺不到進步」是待使用者測試的假設，不是已證實的市場事實。工程 PASS 不代表 UX 或市場驗證通過。導覽與 onboarding 持續分離。
2. 正式 `lw-public` 仍是 `lw-public-intro-v05-423f9be`，100% 流量，映像 `sha256:4340dd7b800f40983e3bd539b971c6889321ff08cecab3db14ec5f65ae4e15ee`；main 的 `lw-api-main` 則為 `lw-api-main-c-f8791ada2ce846b781ed93693aa67665`，100%，映像 `sha256:ac8d7ed334d17c7fb944d0e4e4103d564fd3588623820d21d88cea67c848d095`。本次沒有部署或切流，不能把本機入口當成正式公開版。
3. 唯讀 Trigger 查核：asia-east1 的 `lw-api-main`、`lw-web-main` 均監聽 `^main$`；global 無 Trigger。功能分支不符合這兩個部署觸發條件；**Merge main 可能同時觸發兩者**，仍須 Owner 發布授權。
4. 手機佐證仍為獨立未發布候選。若正式整合兩者，應沿本次已驗證疊合範圍再固定 SHA；原生 HEIC 沒有因新增教學而獲得支援。真機／PG／Python3.12 Linux 與正式版本差異須在發布前安排。
5. 不新增 Service Worker，不做旋轉／橫向、不改 Manifest／手機圖示、資料庫、IAM、Secrets、AI 額度或獎勵。停止功能擴充，等待 Owner 對候選與發布的決策。
