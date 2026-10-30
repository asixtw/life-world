import type { HatchEvent, HatchStage } from './contracts' // 純函式供 UI 與契約測試共用。

export function planHatchStart(current: HatchStage, receiptId: string | undefined, instant: boolean) { // 只有有效回執才啟動。
  if (!receiptId) return { stage: current, playing: false, events: [] as HatchEvent[] } // 無回執不生成事件。
  const stage: HatchStage = instant ? 'complete' : 'glow' // 靜態偏好直接到達結果。
  const type: HatchEvent['type'] = current === 'complete' ? 'replay' : 'start' // 重播不冒充首次開始。
  const events: HatchEvent[] = [{ type, stage, receiptId }] // 每次操作只有一個起始事件。
  if (instant) events.push({ type: 'complete', stage: 'complete', receiptId }) // 靜態完成只通知一次。
  return { stage, playing: !instant, events } // 由 UI 承接計時或定格。
}

export function planHatchSkip(playing: boolean, receiptId: string | undefined): HatchEvent[] { // 跳過與完成各有語意。
  return playing ? [{ type: 'skip', stage: 'complete', receiptId }, { type: 'complete', stage: 'complete', receiptId }] : [] // 非播放中不重複完成。
}

export function planHatchUnmount(playing: boolean, receiptId: string | undefined): HatchEvent[] { // 離開畫面須終止未完序列。
  return playing ? [{ type: 'cancel', stage: 'idle', receiptId }] : [] // 已完成或取消不重複通知。
}
