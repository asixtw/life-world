import { describe, expect, it } from 'vitest' // 先定義三行動單位與改名邊界。
import { nextEffectiveDay, renameHabit } from '../src/habits-model' // 日期依目標時區隔天生效。

describe('v1.1 三行動候選', () => { // 不動正式目標或帳本。
  it('名稱修正不改固定單位與身份', () => { // 編輯期間不能偷偷改計量契約。
    const habit = { id: 'reading', name: '閱讀', unit: '頁', level: 1 as const } // 虛構習慣。
    expect(renameHabit(habit, '閱讀研究')).toEqual({ id: 'reading', name: '閱讀研究', unit: '頁', level: 1 }) // 單位及 ID 不變。
    expect(habit.name).toBe('閱讀') // 原物件不變。
  }) // 正式變更由宿主另行審查。
  it('新用量從目標時區隔日生效', () => { // UTC 日期不能代替目標當地日期。
    expect(nextEffectiveDay('Asia/Taipei', new Date('2027-12-31T17:00:00Z'))).toBe('2028-01-02') // 台北已跨到一月一日。
  }) // 只計算生效日，不自行寫正式用量。
}) // 純函式候選測試。
