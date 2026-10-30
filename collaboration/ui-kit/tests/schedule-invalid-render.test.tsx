import { describe, expect, it } from 'vitest' // 以 SSR 驗證無效 props 不炸毀元件。
import { renderToStaticMarkup } from 'react-dom/server' // 不需要正式瀏覽器或資料庫。
import { MonthSchedule } from '../src/MonthSchedule' // 直接對受控排程輸入壞日期。

describe('無效日期的排程退路', () => { // 非法值須顯示可理解訊息。
  it('非法月份與期間保留今天恢復入口', () => { // 壞值不應觸發 Invalid time value。
    const html = renderToStaticMarkup(<MonthSchedule startDate="2026-13-01" endDate="2026-13-31" selectedDates={[]} cycle="month" cursor="2026-13" timeZone="Asia/Taipei" onToggleDate={() => {}} onSelectWeekday={() => {}} onApplyPreset={() => {}} onClear={() => {}} onChangeCycle={() => {}} onChangePeriod={() => {}} onChangeCursor={() => {}} />) // 事件只用空 fixture。
    expect(html).toContain('請設定有效的開始與結束日期') // 明確指出期間錯誤。
    expect(html).toContain('檢視日期無效') // 明確指出月份錯誤。
    expect(html).toContain('今天') // 保留復原控制。
  })
})
