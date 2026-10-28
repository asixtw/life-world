import type { TransitionEvent } from './contracts' // 純函式固定轉場回呼語意。

export function planTransitionStart(transitionId: string, still: boolean): TransitionEvent[] { // 靜態模式立即結束。
  return still ? [{ type: 'start', transitionId }, { type: 'complete', transitionId }] : [{ type: 'start', transitionId }] // 動態完成等 animationend。
}
