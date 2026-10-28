import { describe, expect, it } from 'vitest' // 轉場完成事件不能只靠 CSS 假設。
import { planTransitionStart } from '../src/transition-machine' // 靜態與動態流程使用同一契約。

describe('轉場回呼契約', () => { // 供宿主串接等待或取消。
  it('completes immediately for still mode, otherwise waits for the visual end', () => { // Quiet／OS 減少動效不等待。
    expect(planTransitionStart('page', true).map(item => item.type)).toEqual(['start', 'complete']) // 立即定格。
    expect(planTransitionStart('page', false).map(item => item.type)).toEqual(['start']) // 動態完成由 animationend 回報。
  }) // 不會把開始等同完成。
}) // 契約測試。
