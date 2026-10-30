import { chromium } from 'playwright' // 只對本機展示做真實 Chrome 截圖。
import { mkdir } from 'node:fs/promises' // 把測試證據保存到交付包。
import path from 'node:path' // 路徑限目前 ui-kit。

const base = 'http://127.0.0.1:5174/' // 固定 localhost，不碰使用者其他分頁。
const folder = path.join(process.cwd(), 'docs', 'qa', 'screenshots') // 交接時可下載的 PNG。
await mkdir(folder, { recursive: true }) // 只建立本套件 QA 目錄。
const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }) // 使用已安裝 Chrome 與隔離暫存 profile。
try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 }) // 指定規格手機尺寸。
  await page.goto(base, { waitUntil: 'networkidle' }) // 等實際資產載入。
  const check = async (label) => { const state = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, broken: [...document.images].filter(image => !image.complete || image.naturalWidth === 0).map(image => image.alt) })); if (state.overflow || state.broken.length) throw new Error(`${label}: ${JSON.stringify(state)}`); return state } // 不把破圖當交付。
  await check('mobile-overview') // 首頁排版。
  await page.screenshot({ path: path.join(folder, 'mobile-overview-390x844.png'), fullPage: true }) // 真實頁面長圖。
  await page.getByRole('button', { name: '劇場', exact: true }).click() // 進入隔離腳本劇場。
  await page.getByRole('combobox', { name: '示範人物' }).selectOption({ label: '柏拉圖' }) // 展示已接入肖像。
  await page.getByRole('combobox', { name: '演練場景' }).selectOption({ label: '承諾、責任與選擇' }) // 展示場景封面。
  await page.getByRole('button', { name: '開始預寫演練' }).click() // 只啟動腳本 fixture。
  await page.getByRole('button', { name: '先檢視承諾的前提是否仍成立' }).click() // 出現人物專屬台詞。
  await check('mobile-theater') // 頭像與封面皆須載入。
  await page.screenshot({ path: path.join(folder, 'mobile-theater-390x844.png'), fullPage: true }) // 劇場證據。
  await page.getByRole('button', { name: '紀錄', exact: true }).click() // 檢查附件 fixture。
  await page.getByRole('button', { name: '圖片', exact: true }).click() // 真實 SVG 圖片預覽。
  await page.getByRole('button', { name: '模擬上傳', exact: true }).first().click() // 不呼叫正式服務。
  for (let index = 0; index < 3; index++) await page.getByRole('button', { name: '推進模擬進度' }).click() // 到 100%。
  await check('mobile-record') // 長內容仍無破圖與橫溢。
  await page.screenshot({ path: path.join(folder, 'mobile-record-390x844.png'), fullPage: true }) // 進度與預覽證據。
  await page.setViewportSize({ width: 1280, height: 800 }) // 回到桌面規格。
  await page.getByRole('button', { name: '總覽', exact: true }).click() // 桌面首頁。
  await check('desktop-overview') // 桌面排版。
  await page.screenshot({ path: path.join(folder, 'desktop-overview-1280x800.png'), fullPage: true }) // 桌面證據。
  console.log('Visual QA passed: 4 real PNG screenshots, no broken images or horizontal overflow.') // 可供交接記錄。
} finally { await browser.close() } // 測試用 Chrome 不留背景程序。
