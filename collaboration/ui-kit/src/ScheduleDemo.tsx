import { useState } from 'react' // 示範宿主保存三個獨立行動。
import { Button, Card } from './components' // 沿用共用語意元件。
import { MonthSchedule, datesForPreset } from './MonthSchedule' // 排程本身保持受控。
import { daysInPeriod, todayInZone } from './schedule-model' // 快捷僅套用編輯期間。

export function ScheduleDemo() { // 虛構三行動各自持有安排，不寫正式目標。
  const today = todayInZone('Asia/Taipei') // 展示時區固定且明示。
  const [startDate, setStartDate] = useState(today) // 期限由使用者填寫，未預填一月。
  const [endDate, setEndDate] = useState('') // 未選期限不得自動安排。
  const [cycle, setCycle] = useState<'month' | 'week'>('month') // 初始只決定檢視。
  const [cursor, setCursor] = useState(today.slice(0, 7)) // 月視圖不等於目標期限。
  const [habit, setHabit] = useState(0) // 三行動互相獨立。
  const [plans, setPlans] = useState<string[][]>([[], [], []]) // 只保存安排，不保存完成或分數。
  const update = (days: string[]) => setPlans(previous => previous.map((plan, index) => index === habit ? days : plan)) // 切換行動不串資料。
  const period = daysInPeriod(startDate, endDate) // 快捷不超出使用者設定期間。
  return <Card title="v1.1 月／週排程候選"><p>虛構三項行動；月份只是檢視，結束日期須自行設定。此展示沒有正式保存。</p><div className="action-row">{['閱讀', '整理', '寫作'].map((label, index) => <Button key={label} kind={index === habit ? 'primary' : 'secondary'} aria-pressed={index === habit} onClick={() => setHabit(index)}>{label}</Button>)}</div><MonthSchedule startDate={startDate} endDate={endDate} selectedDates={plans[habit]} cycle={cycle} cursor={cursor} timeZone="Asia/Taipei" onToggleDate={day => update(plans[habit].includes(day) ? plans[habit].filter(item => item !== day) : [...plans[habit], day].sort())} onSelectWeekday={weekday => update([...new Set([...plans[habit], ...period.filter(day => new Date(`${day}T12:00:00Z`).getUTCDay() === weekday)])].sort())} onApplyPreset={preset => update(datesForPreset(period, preset))} onClear={() => update([])} onChangeCycle={value => { setCycle(value); setCursor(value === 'month' ? today.slice(0, 7) : today) }} onChangePeriod={(start, end) => { setStartDate(start); setEndDate(end); setPlans(previous => previous.map(plan => plan.filter(day => day >= start && day <= end))) }} onChangeCursor={setCursor} /></Card> // 受控事件可供宿主連接版本化保存。
} // 未設定正式儲存或完成回執。
