import { describe, expect, it } from 'vitest' // 先寫排程行為契約，再補實作。
import { calendarCells, datesForPreset, daysInPeriod, nextCycle, todayInZone, validatePeriod } from '../src/schedule-model' // 驗證實際日期及期間邊界。

describe('v1.1 排程純函式', () => { // 月份只作檢視，不自動產生期限。
  it('跨閏年、短月與年界正確列日期', () => { // 避免固定二十八格。
    expect(calendarCells('2028-02').filter(Boolean)).toHaveLength(29) // 閏年二月二十九日。
    expect(calendarCells('2027-02').filter(Boolean)).toHaveLength(28) // 平年二月二十八日。
    expect(nextCycle('2027-12', 'month', 1)).toBe('2028-01') // 年界向後移動。
  }) // 日曆不預設保存期限。
  it('快捷只改編輯期間內的安排', () => { // 快捷不能越界或標成完成。
    const dates = daysInPeriod('2028-02-27', '2028-03-03') // 六天跨月期間。
    expect(dates).toHaveLength(6) // 起迄包含在內。
    expect(datesForPreset(dates, 'weekdays')).toEqual(['2028-02-28', '2028-02-29', '2028-03-01', '2028-03-02', '2028-03-03']) // 週一不在這段期間。
    expect(datesForPreset(dates, 'clear')).toEqual([]) // 清除安排不清除完成。
  }) // 三個行動各自持有 selectedDates。
  it('拒絕逆向期間且以目標時區決定今天', () => { // 日期字串不靠 UTC 午夜轉換。
    expect(validatePeriod('2028-03-01', '2028-02-29')).toBe(false) // 不允許倒置期間。
    expect(todayInZone('Asia/Taipei', new Date('2027-12-31T17:00:00Z'))).toBe('2028-01-01') // 台北已跨年。
  }) // 目標時區由宿主提供。
}) // 純函式測試不接正式保存。
