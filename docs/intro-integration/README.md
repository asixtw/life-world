# 公開互動介紹接入｜部署批次

2026-11-13（Asia/Taipei）。Owner採用獨立公開介紹、產品初次可選、完成／跳過後不再提示及選單重看；指定結尾進入`https://lw-public-162310640466.asia-east1.run.app/#welcome`。本機以相同來源`/#welcome`驗證，部署後即為指定網址。Owner隨後明確指示「ok 幫我做到部署」，本批已獲Commit／Push／Build／Deploy及同服務切流授權。

## 接入契約

- 固定GET／HEAD `/intro`與`/intro/`提供獨立頁，靜態素材放`/static/intro/`；保留三次獨立點擊、4.8秒第三擊及位置修正。介紹不讀寫產品API，CSP禁止連線。
- 未登入且目前瀏覽器未處理介紹時，`#welcome`提供「先認識Life World」與「直接開始」。直接開始只關閉介紹選擇，接續原本訪客／登入入口，不自動建立世界。
- 介紹看完、跳過演出或明確直接進入產品，記錄`completed`／`skipped`。單純進入／離開介紹不記錄，重播不清除。已登入世界沿用原路由，不插入介紹。
- 偏好只保存版本與結果；localStorage優先、sessionStorage退路，再退為當前頁記憶體。不保存帳號、私人資料或跨裝置狀態；瀏覽器清除資料後會再提示。
- 結尾「開始我的故事」為固定`/#welcome`，不接受網址參數改變跳轉目的。登入者回到此入口後仍依既有產品路由回自己的世界或尚未完成的設定。
- 常駐「關於」選單提供「認識Life World（另開分頁）」；不帶私人草稿，維持原分頁輸入。
- 正式Bio、目標／三習慣、孵化、Session、AI、積分、DB Schema及資料保存規則不變。

## 來源與邊界

初版本機基底`02cab305`，發布前發現現役已更新，因此本次發布改以`421e9b95`及其不可變映像`c3ec8b6a`為基底；介紹來源為`LifeWorld_Design_Language_v1/collaboration/onboarding-preview`的錨點修正版。以同步腳本明確複製必要資源及產出雜湊清單，不把設計工作樹其他未發布修改帶入產品。原始獨立原型繼續維持零保存；瀏覽偏好由產品接入層處理。

本批不改現行服務、DB、IAM、Secrets或解除任何發布Gate。`/intro`只增加安全公開讀取入口，不能藉此開啟私人API。工程驗收與Owner目視／陌生訪客理解度／原生手機驗收分開。

## 本機檢查方式

- [產品首次入口](http://127.0.0.1:8215/#welcome)／[直接介紹](http://127.0.0.1:8215/intro)。本機僅監聽127.0.0.1，使用獨立合成SQLite資料；不代表正式PostgreSQL已驗收。
- 已選擇後可從「關於」選單重看。瀏覽器沒有跨裝置偏好同步；單純重開介紹不清除既有已看狀態。
- 四尺寸畫面：[390首次](screenshots/390-first-choice.png)／[320首次](screenshots/320-first-choice.png)／[768介紹](screenshots/768-intro.png)／[1440摘要](screenshots/1440-summary.png)。
- 同步指令：`python scripts/sync_product_intro.py --source /實際路徑/collaboration/onboarding-preview`。預設為本工作區相鄰設計工作樹，其他機器須提供來源路徑；執行時不會接觸網路。產物已保存在`app/static/intro`，執行產品不依賴設計工作樹。
- [必要素材雜湊](../../app/static/intro/asset-manifest.json)／[來源採用紀錄快照](SOURCE_ASSETS.json)。此功能採用現有候選作介紹展示，不把它當成全站美術或92項聲音都已完成。

## 發布邊界

發布分支為`release/public-intro-20261113`，基底為線上逐byte核對的`421e9b95`；只Push此分支，不Merge／Push main。本批Dockerfile在現役映像上疊加1份路由模組與29個靜態檔。保留既有服務／DB／權限設定，精確操作與結果見[部署紀錄](RELEASE.md)。

## 初版本機驗收（02cab305歷史）

- [後端與安全回歸](BACKEND_FINAL.xml)：**55 PASS／0 FAIL／0 SKIP，1.40秒**。包含新公開路由、逐檔HTTP／雜湊、Gate、既有Guest／身分／目標與圖示。
- [接入瀏覽器與正式流程回歸](BROWSER_FINAL.xml)：**18 PASS／0 FAIL／0 SKIP，22.58秒**。新增接入13項，另回歸Guest防重送1項及原正式孵化4項。
- [原型回歸](SOURCE_REGRESSION.xml)：**22 PASS／0 FAIL／0 SKIP，71.95秒**。確認新增完成事件未使原型寫入偏好；原聲音、圖片失敗、鍵盤、200%文字、離頁／重播及接入網址檢查仍通過。
- Node語法檢查、`git diff --check`與本頁連結檢查通過；Chromium四尺寸截圖已目視檢查。[精確範圍與雜湊收據](RECEIPT.json)。

原本圖示批次的head「完全不新增腳本」測試，依本次需求改為只允許兩個介紹腳本與一份樣式，原腳本及樣式的順序／屬性仍逐項嚴格比對，沒有刪案例或放寬任意變更。放大字體測試曾因注入style被既有CSP拒絕，改用先讀取各元素原字級再透過CSSOM放大；不放寬產品CSP。其後抓到主要按鈕繼承nowrap造成窄螢幕溢出，已局部修正為自然換行。初次與中途XML保留，不作最終通過證據。

Owner主觀視覺／節奏採用、5位陌生訪客理解度、原生Safari／Android及正式雲端驗收均尚未執行。本機SQLite結果不代表PostgreSQL發布Gate已通過。
