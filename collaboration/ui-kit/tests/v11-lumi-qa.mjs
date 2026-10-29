import { chromium } from 'playwright' // 真實 Chrome 固定畫面檢查，不讀其他視窗。
import { mkdir } from 'node:fs/promises' // 證據限定 ui-kit 內。
import path from 'node:path'

const folder = path.join(process.cwd(), 'docs', 'qa', 'v1_1')
await mkdir(folder, { recursive: true })
const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' })
try {
  for (const size of [{ width: 390, height: 844, name: 'mobile' }, { width: 1280, height: 800, name: 'desktop' }]) {
    const page = await browser.newPage({ viewport: size, deviceScaleFactor: 1 })
    for (const mode of ['day', 'quiet', 'reduced']) {
      await page.goto(`http://127.0.0.1:5174/?art-review=1&mode=${mode}`, { waitUntil: 'networkidle' })
      const result = await page.evaluate(() => {
        const images = [...document.querySelectorAll('img')]
        const broken = images.filter(img => !img.complete || !img.naturalWidth).map(img => img.currentSrc)
        const composites = [...document.querySelectorAll('.hatch-composite')]
        const nested = composites.every(node => { const outer = node.closest('.hatch-art')?.getBoundingClientRect(); const rect = node.getBoundingClientRect(); return outer && rect.left >= outer.left && rect.right <= outer.right && rect.top >= outer.top && rect.bottom <= outer.bottom })
        return { broken, count: composites.length, left: document.querySelectorAll('.hatch-composite__left').length, right: document.querySelectorAll('.hatch-composite__right').length, feedback: document.querySelector('.feedback-lumi')?.getAttribute('src') ?? '', overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, nested }
      })
      if (result.broken.length || result.count !== 2 || result.left !== 2 || result.right !== 2 || !result.feedback.includes('lw-lumi-confirmed-candidate-v1') || result.overflow > 0 || !result.nested) throw new Error(`${size.name}/${mode}: ${JSON.stringify(result)}`)
      await page.screenshot({ path: path.join(folder, `lumi-assembly-${size.name}-${mode}.png`), fullPage: true })
      console.log(`${size.name}/${mode}: two independent shell pairs, no-shell feedback, loaded and contained.`)
    }
    await page.goto('http://127.0.0.1:5174/?ui-review=hatch', { waitUntil: 'networkidle' })
    if (await page.locator('.lumi-poses figure').count() !== 6) throw new Error(`${size.name}: missing six-pose gallery`)
    await page.locator('.lumi-poses').screenshot({ path: path.join(folder, `lumi-six-poses-${size.name}.png`) })
    await page.close()
  }
} finally { await browser.close() }
