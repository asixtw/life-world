import { useEffect, useState } from 'react' // 控制孵化階段與計時器。
import type { HatchEvent, HatchStage } from './contracts' // 對外只回報展示事件。
import { Button, Card, StatusMessage } from './components' // 沿用可鍵盤操作的元件。

const stages: HatchStage[] = ['idle', 'glow', 'crack', 'open', 'complete'] // 固定狀態對應資產圖層。
const stageLabels: Record<HatchStage, string> = { idle: '目標蛋待開始', glow: '蛋殼微光', crack: '裂紋逐漸清晰', open: '深裂紋；分離蛋殼插畫待補', complete: 'Lumi 已出現；完成定格插畫待補' } // 不把缺件稱為已交付。
const artByStage: Record<HatchStage, string> = { idle: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-rest-v1@512.png', import.meta.url).href, glow: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-softglow-v1@512.png', import.meta.url).href, crack: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-initialcrack-v1@512.png', import.meta.url).href, open: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-deepcrack-v1@512.png', import.meta.url).href, complete: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-lumi-companion-v1@512.png', import.meta.url).href } // 靜態路徑讓 Vite 打包真實圖片；open／complete 專用原稿仍待補。

export function Hatch({ confirmedReceiptId, quiet, reducedMotion, onEvent }: { confirmedReceiptId?: string; quiet: boolean; reducedMotion: boolean; onEvent?: (event: HatchEvent) => void }) { // 回執由宿主傳入，元件不確認目標。
  const [stage, setStage] = useState<HatchStage>('idle') // 僅保存展示狀態。
  const [playing, setPlaying] = useState(false) // 動畫失敗時仍可跳過。
  const instant = quiet || reducedMotion // Quiet 與減少動效立即顯示靜態結果。
  const emit = (type: HatchEvent['type'], next: HatchStage) => onEvent?.({ type, stage: next, receiptId: confirmedReceiptId }) // 事件無計分欄位。
  const start = () => { if (!confirmedReceiptId) return; setStage(instant ? 'complete' : 'glow'); setPlaying(!instant); emit('start', instant ? 'complete' : 'glow'); if (instant) emit('complete', 'complete') } // 只有確認回執才可開始。
  useEffect(() => { if (!playing) return; const timer = window.setTimeout(() => { const next = stages[stages.indexOf(stage) + 1] ?? 'complete'; setStage(next); emit(next === 'complete' ? 'complete' : 'advance', next); if (next === 'complete') setPlaying(false) }, 1100); return () => window.clearTimeout(timer) }, [playing, stage, confirmedReceiptId]) // 切換、取消與離開均清除計時器。
  useEffect(() => { if (playing && instant) { setPlaying(false); setStage('complete'); emit('complete', 'complete') } }, [instant, playing]) // 偏好切換立即停止動畫。
  return <Card title="首次目標 · 孵化展示"><p className="eyebrow">產品候選資產 · 獨立 fixture</p><p>目標經後端確認後才允許首次孵化；此展示回執只用於畫面。</p><div className={`hatch-art hatch-art--${stage} ${instant ? 'hatch-art--still' : ''}`} role="img" aria-label={stageLabels[stage]}><img className="hatch-asset" src={artByStage[stage]} alt="" /></div><StatusMessage tone={confirmedReceiptId ? 'info' : 'warning'}>{confirmedReceiptId ? stageLabels[stage] : '尚無確認回執；無法開始孵化。'}</StatusMessage><div className="action-row"><Button onClick={start} disabled={!confirmedReceiptId || playing}>{stage === 'complete' ? '重播孵化' : '開始孵化'}</Button><Button kind="secondary" disabled={!playing} onClick={() => { setPlaying(false); setStage('complete'); emit('skip', 'complete') }}>跳過</Button><Button kind="text" disabled={stage === 'idle'} onClick={() => { setPlaying(false); setStage('idle'); emit('cancel', 'idle') }}>取消／返回</Button></div><p className="fine-print">跳過、重播與取消只改變畫面，沒有進度或積分寫入。</p></Card> // 可操作完整生命週期與靜態退路。
}
