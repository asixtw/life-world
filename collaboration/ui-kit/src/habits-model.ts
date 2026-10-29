import { todayInZone } from './schedule-model' // 目標時區是唯一的日期基準。

export type HabitDraft = { id: string; name: string; unit: string; level: 1 | 2 | 3 } // 三行動身份及單位由宿主固定。
export function renameHabit<T extends HabitDraft>(habit: T, name: string): T { // 名稱修正不能改計量單位。
  const trimmed = name.trim() // 防止空白假名稱。
  return { ...habit, name: trimmed } // 草稿允許暫時空白，由表單阻擋保存；保留 id、unit、level。
} // 不在元件內重算正式獎勵。
export function nextEffectiveDay(timeZone: string, now = new Date()): string { // 新用量按目標時區隔天生效。
  const today = todayInZone(timeZone, now) // 先取得民用日期。
  const day = new Date(`${today}T12:00:00Z`) // UTC 正午僅供純日期遞增。
  day.setUTCDate(day.getUTCDate() + 1) // 跨月底與跨年仍正確。
  return day.toISOString().slice(0, 10) // 回傳宿主可版本化保存的日期。
} // 不自行執行正式儲存。
