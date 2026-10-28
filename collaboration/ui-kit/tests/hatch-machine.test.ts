import { describe, expect, it } from 'vitest' // 孵化事件契約需獨立於瀏覽器計時。
import { planHatchSkip, planHatchStart, planHatchUnmount } from '../src/hatch-machine' // 檢查完整回執與靜態退路。

describe('孵化事件契約', () => { // 跳過與重播不可新增產品回執。
  it('requires a confirmed receipt and labels replay separately', () => { // 未確認目標不能觸發。
    expect(planHatchStart('idle', undefined, false).events).toEqual([]) // 空回執無事件。
    expect(planHatchStart('complete', 'fixture-receipt', false)).toMatchObject({ stage: 'glow', playing: true, events: [{ type: 'replay', receiptId: 'fixture-receipt' }] }) // 重播不是 start。
  }) // 回執只在展示事件中傳遞。
  it('finishes once when reduced motion or Quiet asks for a still result', () => { // 不等待計時器。
    const plan = planHatchStart('idle', 'fixture-receipt', true) // OS 與 UI 偏好共用此路徑。
    expect(plan).toMatchObject({ stage: 'complete', playing: false }) // 立即定格。
    expect(plan.events.map(item => item.type)).toEqual(['start', 'complete']) // 只有一次完成通知。
    expect(planHatchSkip(false, 'fixture-receipt')).toEqual([]) // 已停止後不能重複通知。
    expect(planHatchSkip(true, 'fixture-receipt').map(item => item.type)).toEqual(['skip', 'complete']) // 跳過保留完成語意。
  }) // 不涉及帳本或計分。
  it('cancels on unmount only while an animation remains active', () => { // 離開畫面不遺留未終止序列。
    expect(planHatchUnmount(true, 'fixture-receipt')).toEqual([{ type: 'cancel', stage: 'idle', receiptId: 'fixture-receipt' }]) // 宿主取得終止事件。
    expect(planHatchUnmount(false, 'fixture-receipt')).toEqual([]) // 完成後不再取消。
  }) // 清理事件單次。
}) // 契約測試。
