export type SoundEvent = 'ui-tap' | 'draft-saved' | 'experience-confirmed' | 'first-hatch' | 'goal-completed' // 五種事件由規格固定。
const receiptEvents = new Set<SoundEvent>(['experience-confirmed', 'first-hatch', 'goal-completed']) // 確認類事件必須帶來源回執。
export class SoundPolicy { // 可供正式容器注入播放器的純事件門檻。
  private enabled = false // 候選預設關閉。
  private quiet = false // Quiet 無聲優先於使用者一般開關。
  private played = new Set<string>() // 同一事件／回執不重播。
  setEnabled(value: boolean) { this.enabled = value } // 僅明示操作改開關。
  setQuiet(value: boolean) { this.quiet = value } // Quiet 切換即時生效。
  request(event: SoundEvent, receiptId?: string): boolean { // 只有宿主呼叫此方法才可播放，載入頁面無副作用。
    if (!this.enabled || this.quiet) return false // 關閉或 Quiet 一律無聲。
    if (receiptEvents.has(event) && !receiptId) return false // 無正式回執不可播確認音。
    if (receiptId) { const key = `${event}:${receiptId}`; if (this.played.has(key)) return false; this.played.add(key) } // 去重與 UI 動畫重播解耦。
    return true // 實際播放失敗由宿主捕捉，不阻斷原操作。
  } // 不修改進度或分數。
} // 真音效素材另列 WAV 與待編碼版本。
