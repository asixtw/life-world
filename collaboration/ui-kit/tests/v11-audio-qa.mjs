import { chromium } from 'playwright' // 真 Chrome 驗證 WAV 載入與無聲退路。
import { mkdir } from 'node:fs/promises' // 截圖保留於 ui-kit QA。
import path from 'node:path' // 不寫其他目錄。

const folder = path.join(process.cwd(), 'docs', 'qa', 'v1_1') // P2 部分候選證據。
await mkdir(folder, { recursive: true }) // 確保目錄存在。

const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }) // 隔離 profile 不碰使用者頁面。
try { // 保證測試後關閉瀏覽器。
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } }) // 手機畫面下檢查播放控制。
  await page.goto('http://127.0.0.1:5174/?ui-review=components', { waitUntil: 'networkidle' }) // 只連本機候選。
  const sample = page.getByRole('button', { name: '試聽 ui-tap-01' }) // 第一個真 WAV。
  if (await sample.isEnabled()) throw new Error('audio enabled by default') // 預設不得發聲。
  if (await page.evaluate(() => document.querySelectorAll('audio').length)) throw new Error('audio element created on page load') // 頁面不自動播放。
  await page.getByRole('checkbox', { name: '明確開啟試聽' }).check() // 使用者手動開啟。
  const transfers = [] // 記錄三格式真檔回應。
  page.on('response', response => { if (response.url().includes('ui-tap-01')) transfers.push({ url: response.url(), status: response.status() }) }) // 只監聽本機候選檔。
  for (const format of ['wav', 'm4a', 'ogg']) { // 每個格式都要實際從 Chrome 播放。
    await page.getByLabel('試聽格式').selectOption(format)
    await sample.click()
    await page.waitForTimeout(350)
    const found = transfers.some(item => item.url.includes(`ui-tap-01.${format}`) && (item.status === 200 || item.status === 206))
    const status = await page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'v1.1 音效候選' }) }).locator('[role=status]').last().innerText()
    if (!found || status.includes('播放失敗')) throw new Error(`${format} failed: ${status}; transfers=${JSON.stringify(transfers)}`)
  }
  await page.getByRole('button', { name: '播放確認事件 fixture' }).click() // 同回執第一回。
  await page.getByRole('button', { name: '播放確認事件 fixture' }).click() // 第二回應去重。
  await page.getByText('同回執已略過、缺回執或聲音已關閉。').waitFor() // 不重播同一確認。
  await page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'v1.1 音效候選' }) }).screenshot({ path: path.join(folder, 'audio-three-format-day-390x844.png') }) // 真列表與開啟狀態截圖。
  await page.getByRole('checkbox', { name: 'Quiet' }).check() // Quiet 即時靜音。
  if (await sample.isEnabled()) throw new Error('Quiet still allows sound') // 安靜模式禁止試聽。
  await page.locator('section.card').filter({ has: page.getByRole('heading', { name: 'v1.1 音效候選' }) }).screenshot({ path: path.join(folder, 'audio-three-format-quiet-390x844.png') }) // Quiet 無聲狀態截圖。
  console.log('Audio QA passed: default off, no page autoplay, real WAV/M4A/Ogg playback and HTTP 200/206, receipt dedupe, Quiet mute.') // 技術操作證據，不代表 Boyi 聽審。
} finally { await browser.close() } // 清理音軌與瀏覽器。
