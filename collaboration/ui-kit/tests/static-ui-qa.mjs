import { chromium } from 'playwright' // 只讀取固定的本機展示入口，不點選互動流程。
import { mkdir, writeFile } from 'node:fs/promises' // 將本輪全 UI 靜態證據保存於套件。

const folder = 'docs/qa/20261029/ui' // 與三張新圖的獨立 art-review 證據分開。
await mkdir(folder, { recursive: true }) // 只建立本套件的 QA 目錄。
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : '/usr/bin/chromium'), args: ['--no-sandbox'] }) // 使用隔離 Chrome profile。
const base = 'http://127.0.0.1:5174/?ui-review=' // 僅連到本機 Vite fixture。
const cases = [ // 五個展示入口的手機與桌面，以及關鍵構圖與異常狀態的固定手機畫面。
  ...['overview', 'components', 'hatch', 'record', 'theater'].flatMap(page => [390, 1280].map(width => ({ name: `${page}-${width}`, page, width }))), // 全體主頁。
  ...['goal', 'world', 'record', 'relations', 'feedback'].map(flow => ({ name: `flow-${flow}-390`, page: 'components', width: 390, flow })), // 四主分頁樣板與回饋。
  ...['loading', 'error', 'permission', 'success'].map(state => ({ name: `state-${state}-390`, page: 'components', width: 390, state })), // 空白狀態已含於主畫面。
  { name: 'components-quiet-390', page: 'components', width: 390, mode: 'quiet' }, // 共用元件 Quiet 對比。
  { name: 'components-reduced-390', page: 'components', width: 390, mode: 'reduced' }, // 共用元件減少動效定格。
] // 全部是直接載入，不觸發任何操作或正式服務。
const results = [] // 保留每張畫面的可機讀量測。
try { // 即使失敗也關閉測試瀏覽器。
  for (const item of cases) { // 順序擷取，避免同時載入大量原稿。
    const viewport = { width: item.width, height: item.width === 390 ? 844 : 800 } // 固定手機與桌面尺寸。
    const page = await browser.newPage({ viewport, reducedMotion: item.mode === 'reduced' ? 'reduce' : 'no-preference' }) // OS 偏好與 fixture 一致。
    const params = new URLSearchParams({ ...(item.flow ? { flow: item.flow } : {}), ...(item.state ? { state: item.state } : {}), ...(item.mode ? { mode: item.mode } : {}) }) // 無私密輸入。
    await page.goto(`${base}${item.page}&${params}`, { waitUntil: 'networkidle' }) // 直接固定狀態而非按鍵流程。
    await page.evaluate(() => document.fonts.ready) // 等字型排版穩定。
    const result = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, broken: [...document.images].filter(image => !image.complete || image.naturalWidth === 0).map(image => image.alt), imageCount: document.images.length, mainText: document.querySelector('main')?.textContent?.length ?? 0 })) // 核對破圖、溢出與非空畫面。
    if (result.overflow !== 0 || result.broken.length || result.mainText < 60 || (['components', 'hatch', 'theater'].includes(item.page) && result.imageCount === 0)) throw new Error(`${item.name}: ${JSON.stringify(result)}`) // 失敗時不能產生虛假通過報告。
    await page.screenshot({ path: `${folder}/${item.name}.png`, fullPage: true }) // 留真實瀏覽器長圖供目視檢查。
    results.push({ ...item, ...result }) // 記錄固定入口與量測。
    await page.close() // 釋放每頁資源。
  } // 所有固定畫面均逐頁驗證。
  await writeFile(`${folder}/static-ui-layout.json`, JSON.stringify({ browser: browser.version(), scope: 'static gallery fixtures only; interactive, cross-team, real-device and Safari tests deferred', results }, null, 2)) // 不把靜態檢查當完整驗收。
  console.log(`PASS: ${results.length} static UI layouts; no broken images or horizontal overflow`) // 供交接引用。
} finally { await browser.close() } // 不留 Chrome 背景程序。
