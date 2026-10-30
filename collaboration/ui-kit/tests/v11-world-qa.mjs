import { chromium } from 'playwright' // 真實 Chrome 檢查新世界候選裁切與層級。
import { mkdir } from 'node:fs/promises' // 截圖只寫 ui-kit QA 目錄。
import path from 'node:path' // 不讀其他私人視窗。

const folder = path.join(process.cwd(), 'docs', 'qa', 'v1_1') // 與 P0 證據同一候選批。
await mkdir(folder, { recursive: true }) // 確保可存真實 PNG。
const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }) // 現有 Chrome 隔離 profile。
try { // 任一檢查失敗也關閉瀏覽器。
  for (const viewport of [{ width: 390, height: 844, label: 'mobile' }, { width: 1280, height: 800, label: 'desktop' }]) { // 手機與桌面分開檢查。
    const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height }, deviceScaleFactor: 1 }) // 真 viewport。
    for (const mode of ['day', 'quiet', 'reduced']) { // 同一房間兩主題及減少動效靜態版。
      await page.goto(`http://127.0.0.1:5174/?ui-review=components&flow=world&mode=${mode}`, { waitUntil: 'networkidle' }) // 固定不互動 fixture。
      const result = await page.evaluate(() => { const room = document.querySelector('.world-room'); if (!room) throw new Error('room missing'); const frame = room.getBoundingClientRect(); const lumi = room.querySelector('.world-room__lumi')?.getBoundingClientRect(); const base = room.querySelector('.world-room__base img'); const broken = [...room.querySelectorAll('img')].filter(image => !image.complete || !image.naturalWidth).map(image => image.className); return { overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth, broken, source: base?.currentSrc ?? '', lumiContained: !!lumi && lumi.left >= frame.left && lumi.right <= frame.right && lumi.top >= frame.top && lumi.bottom <= frame.bottom, frame: [Math.round(frame.width), Math.round(frame.height)] } }) // 實際載入及角色邊界。
      if (result.overflow > 0 || result.broken.length || !result.lumiContained) throw new Error(`${viewport.label}/${mode}: ${JSON.stringify(result)}`) // 角色不可裁切、圖不可破。
      if (!result.source.includes(viewport.width < 600 ? '@768x1024' : '@1280x960')) throw new Error(`${viewport.label}/${mode}: wrong image source ${result.source}`) // 手機必用獨立直向顯示版。
      await page.screenshot({ path: path.join(folder, `world-${viewport.label}-${mode}-${viewport.width}x${viewport.height}.png`), fullPage: true }) // 真實畫面含獨立文字卡。
      await page.locator('.world-room').screenshot({ path: path.join(folder, `world-scene-${viewport.label}-${mode}.png`) }) // 場景局部原尺寸檢視錨點與遮擋。
      console.log(`${viewport.label}/${mode}: ${result.frame.join('x')} scene; assets loaded; Lumi contained; no page overflow.`) // 報告可核對觀察。
    } // Quiet 不以日間圖冒充。
    if (viewport.label === 'desktop') { const scoped = await page.evaluate(() => { const outside = document.createElement('button'); outside.className = 'button button--primary'; document.body.append(outside); const inside = document.querySelector('.lw-kit .button--primary'); const colors = [getComputedStyle(outside).backgroundColor, inside ? getComputedStyle(inside).backgroundColor : '']; outside.remove(); return colors }); if (scoped[0] === scoped[1]) throw new Error(`CSS leaked outside kit: ${scoped.join('/')}`) } // 作用域 CSS 不覆蓋宿主同名 class。
    await page.close() // 釋放測試頁。
  } // 六組手機／桌面、日間／Quiet／減少動效。
  const failed = await browser.newPage({ viewport: { width: 390, height: 844 } })
  await failed.route('**/derived-v1_1/world/room-day@768x1024.png', route => route.abort()) // 背景失敗仍有文字退路。
  await failed.goto('http://127.0.0.1:5174/?ui-review=components&flow=world', { waitUntil: 'networkidle' })
  await failed.getByText('房間圖層載入失敗', { exact: false }).waitFor()
  await failed.getByText('仍可使用下方文字操作', { exact: false }).waitFor()
  await failed.close()
} finally { await browser.close() } // 不留下 Chrome 程序。
