# 2026-11-10 實測收據

Base main 68102f230aa947a434286ba9260e1ae75f6634b0；獨立分支 codex/people-connections-fixes-20261110。
Python 3.14.10（正式 Python3.12 映像未 Build）、Node22.15、PG18.6、Headless Chromium。本輪所有資料為合成、本機隔離，不連正式 Alpha，不呼叫 Google／Gemini Provider。

| 驗收 | 結果 | 證據 |
|---|---|---|
| Bug A 真紅燈 | PASS：舊表單沒有角色候選 checkbox | A_RED.log |
| Bug B 真紅燈 | PASS：舊查詢普通日記 total=1；分頁／提及混入 | B_RED.log |
| 待新增人物真紅燈 | PASS：舊 API 拒絕新契約 | PENDING_RED.log |
| 完整 SQLite API＋Node | PASS：524 passed，17 skipped | API_NODE.log |
| 隔離 PG18 人物／交會／確認 | PASS：48 passed（其中2項是既有 SQLite 遷移相容測試，46項使用 PG） | PG18.log |
| Chromium 人物、交會、四步 | PASS：16 passed，手機390／桌面1440 | CHROMIUM.log |
| PR #22 臨時副本合併 API＋Node | PASS：534 passed，27 skipped | PR22_COMBINED_API.log |
| PR #22 五個共同檔案三方文字檢查 | PASS：0 衝突；沒有修改 #22 分支 | PR22_COMPATIBILITY.json |
| 真 Google／Gemini／Alpha／實機Safari | NOT RUN：本輪禁止部署與正式環境操作 | 不以合成結果代替 |

17 skip 是需專用 PG 設定的既有案例（另外的48項專項驗證不代表這17項全部跑過）；合併副本多10項 Google 專用 PG 測試未設該專項環境而 skip。沒有隱藏跳過或宣稱全環境全綠。PR #22 瀏覽器套件／真人 OAuth 未於合併副本重跑；正式整合後仍需 auth UI 回歸。

## 命令

- `LIFEWORLD_NODE=<node22> <python> -m pytest tests -q --tb=short`
- `LIFEWORLD_TEST_BACKEND=postgresql LIFEWORLD_TEST_PG_HOST=127.0.0.1 LIFEWORLD_TEST_PG_PORT=57484 ... <python> -m pytest tests/test_pending_person.py tests/test_people_connections_visibility.py tests/test_people.py tests/test_connections.py -q --tb=short`
- `LIFEWORLD_TEST_URL=http://127.0.0.1:8012 <browser-python> -m pytest browser_tests/test_experience_four_steps.py browser_tests/test_connections.py browser_tests/test_people.py -q --tb=short`
- 合併副本：將本輪 source patch 套在 PR22 `2f81508c948801b6d4c1f6b3f03bc77b432ac90e` 的獨立檔案副本，新增測試後跑完整 tests；沒有 merge、rebase 或改寫任一既有分支。

PG marker `lifeworld-step10-4-synthetic`＋`STEP10_LOCAL_SYNTHETIC_ONLY` 防止連錯；測後停止。第一次測試因本機啟動埠未顯式指定而連線拒絕，修正57484後重跑成功，沒有將環境錯誤當功能紅燈。瀏覽器舊案例按核准四步更新導覽；目標 progress 欄位測試曾誤用 completed，依現有契約修正，保留活動量與獎勵斷言。

## 覆蓋與審查

- 普通日記／目標活動留在紀錄，未核對舊人物線索有入口；正式參與、直接互動、提及分流。總數、分頁、焦點、來源撤回、原文與獎勵不變。
- 人物選項空白、去重、特殊字元、舊標籤完整字串、自由輸入、Owner及過期重送拒絕。
- 待新增人物草稿不建檔、最終確認才建立、失敗原子回滾、重送同收據、跨Owner拒絕、提及位置／上限驗證。
- 四步前後返回、Guest限制、取消無孤立人物、503手動重試、文字＋合成影像留存、0.5活動量最終入帳。
- JS syntax／Git diff whitespace檢查；高可信 Secret掃描的唯一既有命中是未修改 `tests/test_container_safety.py` 的假PrivateKey測試標記。修改程式／新文件沒有金鑰或真帳密。

## 來源

v0.2 ZIP SHA256 `4424cb88e391f7b26a9709dfab9047a5d54329810b1ad64482943deeea5bdcdd`。
確認修復交接 MD SHA256 `23e3f6dba51961eb7beee60906f89c2d8e5b94d863ae284b4f6be2125910d32a`。
