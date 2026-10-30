import { describe, expect, it } from 'vitest' // 先寫排程行為契約，再補實作。
import { calendarCells, datesForPreset, daysInPeriod, nextCycle, todayInZone, validatePeriod, weekStart, weekCells } from '../src/schedule-model' // 驗證實際日期及期間邊界。

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
  it('任意游標在週檢視都對齊週一並能跨月年', () => { // 不能把週四畫在週一欄。
    expect(weekStart('2026-10-29')).toBe('2026-10-26')
    expect(weekCells('2026-10-29')).toEqual(['2026-10-26','2026-10-27','2026-10-28','2026-10-29','2026-10-30','2026-10-31','2026-11-01'])
    expect(weekCells('2028-01-01')).toEqual(['2027-12-27','2027-12-28','2027-12-29','2027-12-30','2027-12-31','2028-01-01','2028-01-02'])
    expect(nextCycle('2026-10-29', 'week', 1)).toBe('2026-11-02')
  })
  it('非法月份、日數、閏年與格式只回傳可處理的失敗', () => { // 壞日期不得以 Invalid time value 中斷元件。
    for (const day of ['2026-13-01', '2026-00-01', '2026-04-31', '2027-02-29', '2026-1-01', '2026-01-1']) { // 覆蓋月份、日數與格式。
      expect(validatePeriod(day, '2026-12-31')).toBe(false) // 無效期間交由畫面提示。
      expect(weekStart(day)).toBe('') // 無效週游標不得拋例外。
      expect(weekCells(day)).toEqual([]) // 週格不顯示虛構日期。
    }
    expect(calendarCells('2026-13')).toEqual([]) // 非法月份只回空格集合。
    expect(calendarCells('2026-00')).toEqual([]) // 零月不可進入 Date 計算。
    expect(nextCycle('2026-13', 'month', 1)).toBe('') // 無效月導覽不拋例外。
    expect(validatePeriod('2028-02-29', '2028-02-29')).toBe(true) // 真閏日維持可用。
  })
}) // 純函式測試不接正式保存。
