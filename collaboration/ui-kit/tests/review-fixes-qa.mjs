import { chromium } from 'playwright' // 只操作本機隔離套件。

const browser = await chromium.launch({ headless: true, executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe' }) // 使用既有 Chrome，不下載瀏覽器。
try { // 每項反例獨立使用新頁面。
  if (process.argv.includes('--dialog')) { // 驗證逐字輸入不搶焦點。
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } }) // 手機尺寸含面板退路。
    await page.goto('http://127.0.0.1:5174/?ui-review=components', { waitUntil: 'networkidle' }) // 開啟固定元件頁。
    await page.getByRole('button', { name: '開啟草稿面板' }).click() // 進入有狀態對話框。
    if (!await page.getByRole('dialog', { name: '草稿編輯面板' }).getByRole('button', { name: '關閉面板' }).evaluate(node => node === document.activeElement)) throw new Error('dialog opening did not focus close control') // 開啟仍需有初始焦點。
    const input = page.getByRole('dialog', { name: '草稿編輯面板' }).getByRole('textbox', { name: '草稿文字' }) // 找真輸入。
    await input.pressSequentially('逐字輸入測試') // 每字重繪，舊 effect 會搶焦點。
    if (await input.inputValue() !== '逐字輸入測試' || !await input.evaluate(node => node === document.activeElement)) throw new Error('dialog rerender stole typing focus') // 全文與焦點都須維持。
    await page.keyboard.press('Escape') // 離開時須先問未存內容。
    await page.getByRole('dialog', { name: '未保存變更' }).waitFor() // Escape 必須打開確認。
    await page.getByRole('button', { name: '繼續編輯' }).click() // 取消退出。
    if (await input.inputValue() !== '逐字輸入測試') throw new Error('dialog cancel lost text') // 取消不能丟字。
    await page.getByRole('dialog', { name: '草稿編輯面板' }).getByRole('button', { name: '關閉面板' }).click() // 關閉鍵仍須可用。
    await page.getByRole('dialog', { name: '未保存變更' }).waitFor() // 關閉鍵也必須走守衛。
    await page.close() // 不留下測試頁。
  }
  if (process.argv.includes('--theater')) { // 驗證模擬對話確認與同 owner 續作。
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } }) // 以同一頁面檢查 sessionStorage。
    const url = owner => `http://127.0.0.1:5174/?ui-review=theater&demo-owner=${owner}` // owner 是明示 fixture，非正式認證。
    await page.goto(url('review-alpha'), { waitUntil: 'networkidle' }) // 甲 owner 初次進入。
    await page.getByRole('combobox', { name: '示範人物' }).selectOption({ label: '柏拉圖' }) // 選原有內容。
    await page.getByRole('combobox', { name: '演練場景' }).selectOption({ label: '承諾、責任與選擇' }) // 選同組劇場。
    await page.getByRole('button', { name: '開始預寫演練' }).click() // 建立模擬 session。
    await page.locator('.choice-list button').first().click() // 留一輪未匯出對話。
    const before = await page.locator('.dialogue-line').count() // 記下回合數。
    await page.reload({ waitUntil: 'networkidle' }) // 刷新後同 owner 應續作。
    if (await page.locator('.dialogue-line').count() !== before) throw new Error('same owner refresh lost dialogue') // 不可丟回合。
    const scene = page.getByRole('combobox', { name: '演練場景' }) // 換場景需確認。
    const originalScene = await scene.inputValue() // 保存選擇以驗證取消。
    const otherScene = await scene.locator('option:not([value=""])').evaluateAll((nodes, original) => nodes.map(node => node.value).find(value => value !== original), originalScene) // 選同 pack 的真正另一場景。
    await scene.selectOption(otherScene) // 嘗試切換。
    await page.getByRole('dialog', { name: '尚未匯出的演練' }).waitFor() // 必須出現守衛。
    await page.getByRole('button', { name: '保留演練' }).click() // 取消切換。
    if (await scene.inputValue() !== originalScene || await page.locator('.dialogue-line').count() !== before) throw new Error('cancel scene switch lost dialogue') // 選擇與對話都不能變。
    await page.goto(url('review-bravo'), { waitUntil: 'networkidle' }) // 乙 owner 不能讀甲草稿。
    if (await page.locator('.dialogue-line').count()) throw new Error('cross-owner simulation draft leaked') // owner 隔離。
    await page.goto(url('review-alpha'), { waitUntil: 'networkidle' }) // 回甲仍可續作。
    if (await page.locator('.dialogue-line').count() !== before) throw new Error('owner return lost simulation draft') // 草稿只限同 owner。
    await page.getByRole('button', { name: '重設', exact: true }).click() // 重設也必須走確認。
    await page.getByRole('dialog', { name: '尚未匯出的演練' }).getByRole('button', { name: '保留演練' }).click() // 取消重設。
    if (await page.locator('.dialogue-line').count() !== before) throw new Error('cancel reset lost dialogue') // 路徑仍保留。
    await page.getByRole('combobox', { name: '示範人物' }).selectOption({ label: '蘇格拉底' }) // 人物切換需確認。
    await page.getByRole('dialog', { name: '尚未匯出的演練' }).getByRole('button', { name: '確認切換' }).click() // 明確同意捨棄舊路線。
    if (await page.locator('.dialogue-line').count() || await page.getByRole('combobox', { name: '示範人物' }).inputValue() === '') throw new Error('confirmed switch did not replace session') // 切換後不顯舊話。
    await page.close() // 清理測試頁。
  }
  if (process.argv.includes('--begin-guard')) { // 上方開始鍵與下方重設須共用同一保護。
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } }) // 用獨立 owner 避免沿用其他測試草稿。
    await page.goto('http://127.0.0.1:5174/?ui-review=theater&demo-owner=begin-guard', { waitUntil: 'networkidle' }) // 初始 session 為空。
    await page.getByRole('combobox', { name: '示範人物' }).selectOption({ label: '柏拉圖' }) // 選現有角色。
    await page.getByRole('combobox', { name: '演練場景' }).selectOption({ label: '承諾、責任與選擇' }) // 選同 pack 場景。
    await page.getByRole('button', { name: '開始預寫演練' }).click() // 空 session 應直接開始。
    if (await page.getByRole('dialog', { name: '尚未匯出的演練' }).count()) throw new Error('empty session unexpectedly asked for discard') // 第一次開始不能誤阻擋。
    await page.locator('.choice-list button').first().click() // 產生未匯出的回合。
    const oldSession = await page.locator('.fine-print').filter({ hasText: 'session:' }).first().textContent() // 保存舊 session 身份。
    const oldTurns = await page.locator('.dialogue-line').count() // 保存舊路徑。
    await page.getByRole('button', { name: '開始預寫演練' }).click() // 再次按上方入口不能繞過確認。
    await page.getByRole('dialog', { name: '尚未匯出的演練' }).waitFor() // 預期同一守衛。
    await page.getByRole('button', { name: '保留演練' }).click() // 明確取消。
    if (await page.locator('.dialogue-line').count() !== oldTurns || await page.locator('.fine-print').filter({ hasText: 'session:' }).first().textContent() !== oldSession) throw new Error('cancel upper begin lost session') // 取消後身份與回合不變。
    await page.getByRole('button', { name: '開始預寫演練' }).click() // 再次提出重新開始。
    await page.getByRole('dialog', { name: '尚未匯出的演練' }).getByRole('button', { name: '確認切換' }).click() // 明確確認後重啟。
    if (await page.locator('.fine-print').filter({ hasText: 'session:' }).first().textContent() === oldSession || await page.locator('.dialogue-line').count() >= oldTurns) throw new Error('confirmed upper begin did not restart cleanly') // 新 session 與起點須不同。
    await page.close() // 清理瀏覽器頁。
  }
  console.log(`review fixes QA passed: ${process.argv.slice(2).join(', ')}`) // 僅成功後輸出。
} finally { await browser.close() } // 確保 Chrome 關閉。
