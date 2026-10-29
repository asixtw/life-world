import { HatchArt, stageLabels } from './Hatch' // 使用實際孵化渲染器做固定構圖證據。
import { PositiveFeedback } from './PositiveFeedback' // 與正式展示的回饋共用，不造假的圖片組合。
import { Card } from './components' // 沿用元件與主題。
export function ArtReview() { // 只讀 fixture 入口，不觸發操作或計時器。
  const mode = new URLSearchParams(window.location.search).get('mode') // 以 URL 選擇固定偏好，供靜態驗收重現。
  return <main className={`art-review ${mode === 'quiet' ? 'theme-quiet' : ''} ${mode === 'reduced' ? 'motion-reduced' : ''}`}><p className="eyebrow">靜態審查 fixture · 未連接正式服務</p><h1>孵化與確認回饋 · {mode ?? 'day'}</h1><p>新左右殼與無殼 Lumi 姿勢使用實際元件及原稿；候選錨點尚未正式校準。</p><div className="art-review-grid">{(['open', 'complete'] as const).map(stage => <Card key={stage} title={stageLabels[stage]}><HatchArt stage={stage} still /></Card>)}<Card title="確認後養分到達"><PositiveFeedback confirmedReceiptId="demo-static-review" /><p className="fine-print">虛構已確認回執，未改變進度或積分。</p></Card></div></main> // 當前只有外觀證據，不宣稱完整互動通過。
} // 此入口與主展示共享最終代碼。
