import { chromium } from 'playwright' // 只擷取固定 fixture，不點擊互動流程。
import { mkdir, writeFile } from 'node:fs/promises' // 保存當輪可公開的虛構證據。
const folder = 'docs/qa/20261029' // 日期區隔舊截圖。
await mkdir(folder, { recursive: true }) // 不覆蓋歷史證據。
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || (process.platform === 'win32' ? 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' : '/usr/bin/chromium'), args: ['--no-sandbox'] }) // 隔離 Chromium，不操作使用者分頁。
const results = [] // 記錄每個主題和尺寸。
try { // 確保測試程序會清理。
  for (const width of [390, 1280]) { // 手機與桌面靜態版面。
    for (const mode of ['day', 'quiet', 'reduced']) { // 三種既有偏好。
      const page = await browser.newPage({ viewport: { width, height: width === 390 ? 844 : 800 }, reducedMotion: mode === 'reduced' ? 'reduce' : 'no-preference' }) // 減少動效同時覆蓋 OS 偏好。
      await page.goto(`http://127.0.0.1:5174/?art-review&mode=${mode}`, { waitUntil: 'networkidle' }) // 直接載入固定狀態，不執行旅程。
      const result = await page.evaluate(() => ({ overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, images: [...document.images].map(img => ({ src: img.currentSrc.split('/').pop(), loaded: img.complete && img.naturalWidth > 0, naturalWidth: img.naturalWidth, width: img.getBoundingClientRect().width, height: img.getBoundingClientRect().height })), animations: document.getAnimations().length })) // 量測原稿尺寸、破圖、橫溢與靜態保證。
      if (result.overflow || result.images.some(img => !img.loaded) || result.images.length !== 4 || result.animations) throw new Error(JSON.stringify({ mode, width, ...result })) // 不以成功截圖掩蓋缺圖。
      await page.screenshot({ path: `${folder}/art-${mode}-${width}.png`, fullPage: true }) // 真實瀏覽器渲染證據。
      results.push({ mode, width, ...result }) // 保留通過量測。
      await page.close() // 每種狀態獨立。
    } // 三主題結束。
  } // 兩尺寸結束。
  await writeFile(`${folder}/static-layout.json`, JSON.stringify({ browser: browser.version(), scope: 'static fixtures only; interactive testing deferred', results }, null, 2)) // 明示驗證邊界。
  console.log(`PASS: ${results.length} static layouts; no overflow, broken images or animations`) // 供交接引用。
} finally { await browser.close() } // 不留瀏覽器背景程序。
