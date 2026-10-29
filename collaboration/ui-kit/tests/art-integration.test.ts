import { describe, expect, it } from 'vitest' // 檢查最終資產綁定與回執門檻。
import { renderToStaticMarkup } from 'react-dom/server' // 純靜態渲染，不執行延後的互動測試。
import { createElement } from 'react' // 使用真正元件的 props。
import { artByStage, HatchArt, stages } from '../src/Hatch' // 同一實作供展示與檢查。
import { PositiveFeedback, nourishmentArt } from '../src/PositiveFeedback' // 養分組合與門檻。
import manifest from '../assets/manifest.json' // 清單與渲染保持一致。
import { poseArt, shellArt } from '../src/LumiPoses' // 新姿勢與左右殼必須是獨立真檔。
describe('新美術接入', () => { // 不把 fixture 當正式服務測試。
  it('六階段保留深裂並使用新增原稿', () => { // 避免回退到深裂／陪伴替代圖。
    expect(stages).toEqual(['idle', 'glow', 'crack', 'deepcrack', 'open', 'complete']) // 固定順序。
    expect(artByStage.open).toContain('lw-lumi-confirmed-candidate-v1.png') // 開殼需無殼 Lumi。
    expect(artByStage.complete).toContain('lw-lumi-celebrate-candidate-v1.png') // 完成使用新慶祝姿勢。
    expect(artByStage.deepcrack).toContain('lw-egg-deepcrack-v1') // 舊深裂仍可達。
  }) // 階段檢查結束。
  it('靜態孵化保留可讀標籤及透明圖片', () => { // 無計時器的外觀契約。
    const html = renderToStaticMarkup(createElement(HatchArt, { stage: 'open', still: true })) // 真正元件輸出。
    expect(html).toContain('hatch-art--still') // 靜態模式可立即顯示。
    expect(html).toContain('蛋殼已分離') // 可讀標籤。
    expect(html).not.toContain('待補') // 不留舊缺件標示。
  }) // 靜態畫面檢查結束。
  it('無回執不顯示 Lumi，確認後使用兩個獨立圖層', () => { // 防止未確認就出現完成回饋。
    expect(renderToStaticMarkup(createElement(PositiveFeedback, {}))).toBe('') // 無回執不渲染。
    const html = renderToStaticMarkup(createElement(PositiveFeedback, { confirmedReceiptId: 'fixture' })) // 僅虛構回執。
    expect(html).toContain(nourishmentArt) // 光效實際接回。
    expect(html).toContain(poseArt.confirmed) // 一般確認為無殼角色。
  }) // 回饋門檻檢查結束。
  it('三張圖均列產品候選而非正式核准', () => { // 清單記錄實際來源及範圍。
    for (const id of ['lw-egg-shellsplit-v2', 'lw-lumi-completion-v2', 'lw-effects-nourishment-v2']) { // 遍歷本次新增。
      const asset = manifest.assets.find(item => item.id === id) // 對應穩定 ID。
      expect(asset?.usageScope).toBe('product_candidate') // 不擅自升格正式版。
      expect(asset?.originalPath).toContain('additions-20261029/originals/') // 原稿實體路徑。
    } // 三張皆須通過。
  }) // 清單檢查結束。
  it('新六姿勢及左右殼真實接入孵化與一般回饋', () => { // 不再以單一合殼圖冒充獨立圖層。
    expect(Object.keys(poseArt)).toEqual(['idle', 'quiet', 'welcome', 'listening', 'confirmed', 'celebrate'])
    const open = renderToStaticMarkup(createElement(HatchArt, { stage: 'open', still: true }))
    expect(open).toContain(shellArt.left)
    expect(open).toContain(shellArt.right)
    expect(open).toContain(poseArt.confirmed)
    const complete = renderToStaticMarkup(createElement(HatchArt, { stage: 'complete', still: true }))
    expect(complete).toContain(poseArt.celebrate)
    const feedback = renderToStaticMarkup(createElement(PositiveFeedback, { confirmedReceiptId: 'fixture' }))
    expect(feedback).toContain(poseArt.confirmed)
    expect(feedback).not.toContain('lw-lumi-completion-v2.png')
  })
}) // 測試組結束。
