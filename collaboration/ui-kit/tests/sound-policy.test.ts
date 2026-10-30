import { describe, expect, it } from 'vitest' // 音效事件邊界先定測試。
import { SoundPolicy } from '../src/sound-policy' // 不需真音軌即可測 Quiet 與去重。

describe('v1.1 音效播放政策', () => { // 音效失敗不可阻擋產品操作。
  it('預設關閉、Quiet 無聲且不在頁面載入時播放', () => { // 使用者明確啟用才可試聽。
    const policy = new SoundPolicy() // 新候選預設關閉。
    expect(policy.request('ui-tap')).toBe(false) // 未啟用不可播放。
    policy.setEnabled(true) // 使用者明確開啟。
    policy.setQuiet(true) // Quiet 優先。
    expect(policy.request('ui-tap')).toBe(false) // 安靜世界無聲。
  }) // UI 頁載入不呼叫 request。
  it('同一確認回執只播一次，換回執才可再播', () => { // 動畫重播不重播獎勵音。
    const policy = new SoundPolicy() // 未設定時無聲。
    policy.setEnabled(true) // 明確啟用。
    expect(policy.request('experience-confirmed', 'receipt-1')).toBe(true) // 首次確認。
    expect(policy.request('experience-confirmed', 'receipt-1')).toBe(false) // 同一回執去重。
    expect(policy.request('experience-confirmed', 'receipt-2')).toBe(true) // 新回執。
    expect(policy.request('experience-confirmed')).toBe(false) // 確認事件缺回執不可假播。
  }) // 聲音不改帳本。
}) // 真 WAV 試聽與 Boyi 聽審另列。
