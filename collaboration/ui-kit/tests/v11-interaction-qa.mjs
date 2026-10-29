import { chromium } from 'playwright' // 只操作本機獨立候選，保留真實瀏覽器證據。
import { mkdir } from 'node:fs/promises' // 圖片留在本套件 QA 目錄。
import path from 'node:path' // 不讀取其他網站或個人視窗。

const folder = path.join(process.cwd(), 'docs', 'qa', 'v1_1') // 新版證據與舊版分開。
await mkdir(folder, { recursive: true }) // 建立證據資料夾。
const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }) // 使用既有 Chrome 隔離 profile。
const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1, acceptDownloads: true }) // 先檢查手機規格。
try { // 確保測試失敗也會關閉瀏覽器。
  await page.goto('http://127.0.0.1:5174/', { waitUntil: 'networkidle' }) // 僅連本機 Vite。
  await page.getByRole('button', { name: '元件', exact: true }).click() // 進入 P0 展示。
  await page.getByRole('button', { name: '次要／開啟面板' }).click() // 焦點應進入 Dialog。
  if (await page.evaluate(() => document.activeElement?.getAttribute('aria-label')) !== '關閉面板') throw new Error('Dialog focus did not enter') // 真正焦點檢查。
  await page.keyboard.press('Escape') // Escape 應關閉面板。
  if (await page.getByRole('dialog').count()) throw new Error('Dialog Escape failed') // 不只看靜態畫面。
  const schedule = page.getByRole('region', { name: '行動排程' }) // v1.1 新月／週元件。
  await schedule.getByLabel('結束日期').fill('2026-11-10') // 使用者明確設定期間。
  await schedule.getByRole('button', { name: '週一至週五' }).click() // 套用期間內快捷。
  const reading = await schedule.locator('[aria-pressed="true"]').count() // 讀第一項行動安排。
  if (reading < 1) throw new Error('Schedule preset did not apply') // 不能只有視覺按鈕。
  await page.getByRole('button', { name: '整理', exact: true }).click() // 第二項應獨立。
  if (await schedule.locator('[aria-pressed="true"]').count()) throw new Error('Habit plans leaked') // 不串三項安排。
  await schedule.getByLabel('檢視').selectOption('week') // 真正切換週檢視。
  await page.screenshot({ path: path.join(folder, 'mobile-p0-schedule-390x844.png'), fullPage: true }) // 新畫面真實 PNG。
  if (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)) throw new Error('mobile schedule overflow') // 手機七欄不可橫溢。
  await page.getByRole('navigation', { name: '手機展示導覽' }).getByRole('button', { name: '紀錄', exact: true }).click() // 進入媒體候選。
  await page.getByRole('button', { name: '開始', exact: true }).click() // 只進入權限 fixture。
  await page.getByRole('button', { name: '模擬拒絕' }).click() // 權限拒絕仍可文字或選檔。
  await page.getByRole('button', { name: '選圖片 fixture' }).click() // 只選素材，不上傳。
  if (!await page.getByText('上傳回執：無', { exact: false }).count()) throw new Error('Selecting file auto-uploaded') // 明確檢查上傳邊界。
  await page.getByRole('button', { name: '明確上傳 fixture' }).click() // 使用者觸發 mock。
  await page.getByText('fixture-material-receipt').first().waitFor() // 等待 mock 回執。
  await page.getByRole('button', { name: '辨識 fixture' }).click() // 原文另行取得。
  await page.getByText('這是虛構辨識原文，請人工核對。').first().waitFor() // 原文可見。
  await page.getByRole('textbox', { name: '人工校對文字' }).fill('人工修正內容') // 修改校對文字。
  await page.getByRole('button', { name: '標記人工核對' }).click() // 標記後再改應重置。
  await page.getByRole('textbox', { name: '人工校對文字' }).fill('再修改') // 修改重置核對。
  if (!await page.getByText('人工核對：待核對').count()) throw new Error('Review did not reset') // 防止舊核對滲入。
  await page.screenshot({ path: path.join(folder, 'mobile-p0-media-390x844.png'), fullPage: true }) // 真實媒體狀態截圖。
  if (await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)) throw new Error('mobile media overflow') // 長文字不遮操作。
  await page.getByRole('button', { name: '劇場', exact: true }).click() // 既有劇場回歸。
  await page.getByRole('combobox', { name: '示範人物' }).selectOption({ label: '柏拉圖' }) // 選定示範角色。
  await page.getByRole('combobox', { name: '演練場景' }).selectOption({ label: '承諾、責任與選擇' }) // 選定同組場景。
  await page.getByRole('button', { name: '查看人物與來源' }).click() // 來源面板可用。
  await page.keyboard.press('Escape') // 來源面板關閉。
  await page.getByRole('button', { name: '開始預寫演練' }).click() // 只進腳本模式。
  for (let route = 0; route < 3; route++) { // 同場景三條實際分支都要走到結尾。
    await page.locator('.choice-list button').nth(route).click() // 選不同起始策略。
    await page.getByRole('button', { name: '返回上一步' }).click() // 回到上一節點。
    await page.locator('.choice-list button').nth(route).click() // 重走選定路線。
    while (await page.locator('.choice-list button').count()) await page.locator('.choice-list button').first().click() // 走到可回顧終點。
    if (!await page.getByText('回顧：', { exact: false }).count()) throw new Error(`theater route ${route} did not end`) // 每路線應有結尾。
    await page.getByRole('button', { name: '重設', exact: true }).click() // 重設後下一路線獨立。
  } // 不將三條路徑當同一條重複。
  const download = page.waitForEvent('download') // 真正檢查匯出事件。
  await page.getByRole('button', { name: '匯出模擬紀錄' }).click() // 匯出 demo JSON。
  if (!(await download).suggestedFilename().endsWith('.json')) throw new Error('Export was not JSON') // 不讀取私人資料。
  await page.getByRole('button', { name: '孵化', exact: true }).click() // 回執切換與 Quiet 路徑。
  await page.getByRole('checkbox', { name: 'Quiet' }).check() // 安靜模式即時靜態完成。
  await page.getByRole('button', { name: '開始孵化' }).click() // 不等待動畫。
  await page.getByRole('img', { name: 'Lumi 孵化完成' }).waitFor() // 完成資產可見。
  await page.getByRole('button', { name: '重播孵化' }).click() // 重播同回執不改正式成果。
  await page.getByRole('button', { name: '取消／返回' }).click() // 回 idle。
  await page.getByRole('checkbox', { name: 'Quiet' }).uncheck() // 動態模式測跳過。
  await page.getByRole('button', { name: '開始孵化' }).click() // 進入計時階段。
  await page.getByRole('button', { name: '跳過' }).click() // 直接到完成靜態結果。
  await page.getByRole('checkbox', { name: '提供虛構已確認回執' }).uncheck() // 回執變更重新掛載孵化。
  if (await page.getByRole('button', { name: '開始孵化' }).isEnabled()) throw new Error('hatch started without receipt') // 無回執不能孵化。
  await page.setViewportSize({ width: 1280, height: 800 }) // 桌面驗證同一版。
  await page.getByRole('button', { name: '元件', exact: true }).click() // 查看桌面排程布局。
  const layout = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, broken: [...document.images].filter(image => !image.complete || !image.naturalWidth).length })) // 實際 DOM 幾何與載圖檢查。
  if (layout.overflow > 0 || layout.broken) throw new Error(`desktop layout: ${JSON.stringify(layout)}`) // 不冒稱無破圖。
  await page.screenshot({ path: path.join(folder, 'desktop-p0-schedule-1280x800.png'), fullPage: true }) // 桌面真實 PNG。
  console.log('v1.1 local interaction QA passed: Dialog focus/Escape, schedule independence/week, media permission/upload/review, theater source/branch/back/reset/export, Quiet hatch/replay/cancel, desktop layout.') // 精確列覆蓋範圍。
} finally { await browser.close() } // 不留 Chrome 程序。
