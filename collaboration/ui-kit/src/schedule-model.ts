export type Cycle = 'month' | 'week' // 月與週只是檢視週期。
export type SchedulePreset = 'weekdays' | 'tue-thu-sat' | 'daily' | 'clear' // 快捷是安排規則，不代表完成。
const isoDay = (date: Date) => date.toISOString().slice(0, 10) // 在純日期運算中固定輸出 YYYY-MM-DD。
const civil = (day: string) => new Date(`${day}T12:00:00Z`) // 使用 UTC 正午避免午夜與夏令時間漂移。
const validDay = (day: string) => /^\d{4}-\d{2}-\d{2}$/.test(day) && isoDay(civil(day)) === day // 阻擋不存在的日期。
export function validatePeriod(startDate: string, endDate: string): boolean { return validDay(startDate) && validDay(endDate) && startDate <= endDate } // 期間由使用者明確設定。
export function todayInZone(timeZone: string, now = new Date()): string { // 目標時區由宿主提供，無法用裝置時區代替。
  const parts = new Intl.DateTimeFormat('en-US', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now) // 讀目標時區的民用日期。
  const get = (type: string) => parts.find(part => part.type === type)?.value ?? '' // 取得年月日欄位。
  return `${get('year')}-${get('month')}-${get('day')}` // 不將 UTC 午夜誤認為使用者當天。
} // 未知 IANA 時區由 Intl 明確拋錯給宿主。
export function daysInPeriod(startDate: string, endDate: string): string[] { // 只回傳可編輯期間的民用日期。
  if (!validatePeriod(startDate, endDate)) return [] // 無效期間不產生安排。
  const result: string[] = [] // 結果不附帶任何完成資訊。
  for (let date = civil(startDate); isoDay(date) <= endDate; date.setUTCDate(date.getUTCDate() + 1)) result.push(isoDay(date)) // UTC 日遞增避免 DST 跳日。
  return result // 包含起日及迄日。
} // 期間由 props 控制，元件不自行預設期限。
export function datesForPreset(days: string[], preset: SchedulePreset): string[] { // 快捷只篩選傳入的期間日期。
  if (preset === 'clear') return [] // 清除僅針對安排集合。
  return days.filter(day => { const week = civil(day).getUTCDay(); return preset === 'daily' || (preset === 'weekdays' && week >= 1 && week <= 5) || (preset === 'tue-thu-sat' && [2, 4, 6].includes(week)) }) // 保留三種明示規則。
} // 不寫回積分或完成狀態。
export function calendarCells(cursor: string): (string | null)[] { // 依實際月份生成 28–31 日及週一起始空格。
  if (!/^\d{4}-\d{2}$/.test(cursor) || !validDay(`${cursor}-01`)) return [] // 無效月份不產出假日期。
  const first = civil(`${cursor}-01`) // 月首作定位。
  const pad = (first.getUTCDay() + 6) % 7 // 星期一是第一欄。
  const count = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate() // 當月真實天數。
  return [...Array<string | null>(pad).fill(null), ...Array.from({ length: count }, (_, index) => `${cursor}-${String(index + 1).padStart(2, '0')}`)] // 不補虛構可選日。
} // 格子不是固定四列。
export function weekStart(cursor: string): string { // 任何民用日期都對齊該週星期一。
  if (!validDay(cursor)) return '' // 無效日期不產生假週。
  const date = civil(cursor) // UTC 正午避免時區的午夜切換。
  date.setUTCDate(date.getUTCDate() - (date.getUTCDay() + 6) % 7) // 星期日向前六日。
  return isoDay(date)
}
export function weekCells(cursor: string): string[] { // 欄頭一至日必須對應真實星期。
  const first = weekStart(cursor)
  if (!first) return []
  const last = civil(first)
  last.setUTCDate(last.getUTCDate() + 6)
  return daysInPeriod(first, isoDay(last))
}
export function nextCycle(cursor: string, cycle: Cycle, amount: number): string { // 導覽不修改保存期間。
  if (cycle === 'month') { const date = civil(`${cursor}-01`); date.setUTCMonth(date.getUTCMonth() + amount); return isoDay(date).slice(0, 7) } // 月份保持月首錨點。
  const first = weekStart(cursor); if (!first) return ''; const date = civil(first); date.setUTCDate(date.getUTCDate() + amount * 7); return isoDay(date) // 週視圖先對齊週一再移動七日。
} // 週跨月、跨年仍可用。
