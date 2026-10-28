import { useEffect, useRef, useState } from 'react' // 控制孵化階段與計時器。
import type { HatchEvent, HatchStage } from './contracts' // 對外只回報展示事件。
import { Button, Card, StatusMessage } from './components' // 沿用可鍵盤操作的元件。
import { planHatchSkip, planHatchStart, planHatchUnmount } from './hatch-machine' // 純函式固定回執與事件順序。

const stages: HatchStage[] = ['idle', 'glow', 'crack', 'open', 'complete'] // 固定狀態對應資產圖層。
const stageLabels: Record<HatchStage, string> = { idle: '目標蛋待開始', glow: '蛋殼微光', crack: '裂紋逐漸清晰', open: '深裂紋；分離蛋殼插畫待補', complete: 'Lumi 已出現；完成定格插畫待補' } // 不把缺件稱為已交付。
const artByStage: Record<HatchStage, string> = { idle: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-rest-v1@512.png', import.meta.url).href, glow: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-softglow-v1@512.png', import.meta.url).href, crack: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-initialcrack-v1@512.png', import.meta.url).href, open: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-deepcrack-v1@512.png', import.meta.url).href, complete: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-lumi-companion-v1@512.png', import.meta.url).href } // 靜態路徑讓 Vite 打包真實圖片；open／complete 專用原稿仍待補。

export function Hatch({ confirmedReceiptId, quiet, reducedMotion, onEvent }: { confirmedReceiptId?: string; quiet: boolean; reducedMotion: boolean; onEvent?: (event: HatchEvent) => void }) { // 回執由宿主傳入，元件不確認目標。
  const [stage, setStage] = useState<HatchStage>('idle') // 僅保存展示狀態。
  const [playing, setPlaying] = useState(false) // 動畫失敗時仍可跳過。
  const playingRef = useRef(false) // 卸載清理讀取最新執行狀態。
  const callbackRef = useRef(onEvent) // 卸載時不捕捉過期回呼。
  const receiptRef = useRef(confirmedReceiptId) // 卸載取消仍指向本次回執。
  callbackRef.current = onEvent // 每次 render 同步宿主回呼。
  receiptRef.current = confirmedReceiptId // 回執變更時同步清理依據。
  const [osReduced, setOsReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) // OS 偏好也決定流程節奏。
  const instant = quiet || reducedMotion || osReduced // 三種偏好都直接顯示靜態結果。
  const emit = (type: HatchEvent['type'], next: HatchStage) => onEvent?.({ type, stage: next, receiptId: confirmedReceiptId }) // 事件無計分欄位。
  const start = () => { const plan = planHatchStart(stage, confirmedReceiptId, instant); if (!plan.events.length) return; setStage(plan.stage); playingRef.current = plan.playing; setPlaying(plan.playing); plan.events.forEach(event => onEvent?.(event)) } // 重播與靜態完成由同一契約計畫。
  useEffect(() => () => { const events = planHatchUnmount(playingRef.current, receiptRef.current); playingRef.current = false; events.forEach(event => callbackRef.current?.(event)) }, []) // 導航離開時只取消仍在播放的序列。
  useEffect(() => { const query = window.matchMedia?.('(prefers-reduced-motion: reduce)'); if (!query) return; const update = () => setOsReduced(query.matches); query.addEventListener('change', update); return () => query.removeEventListener('change', update) }, []) // OS 偏好變動立即生效。
  useEffect(() => { if (!playing || instant) return; const timer = window.setTimeout(() => { const next = stages[stages.indexOf(stage) + 1] ?? 'complete'; setStage(next); emit(next === 'complete' ? 'complete' : 'advance', next); if (next === 'complete') { playingRef.current = false; setPlaying(false) } }, 1100); return () => window.clearTimeout(timer) }, [playing, stage, confirmedReceiptId, instant]) // 偏好變更時同步取消計時器。
  useEffect(() => { if (playing && instant) { playingRef.current = false; setPlaying(false); setStage('complete'); emit('complete', 'complete') } }, [instant, playing]) // 偏好切換立即停止動畫。
  return <Card title="首次目標 · 孵化展示"><p className="eyebrow">產品候選資產 · 獨立 fixture</p><p>目標經後端確認後才允許首次孵化；此展示回執只用於畫面。</p><div className={`hatch-art hatch-art--${stage} ${instant ? 'hatch-art--still' : ''}`} role="img" aria-label={stageLabels[stage]}><img className="hatch-asset" src={artByStage[stage]} alt="" /></div><StatusMessage tone={confirmedReceiptId ? 'info' : 'warning'}>{confirmedReceiptId ? stageLabels[stage] : '尚無確認回執；無法開始孵化。'}</StatusMessage><div className="action-row"><Button onClick={start} disabled={!confirmedReceiptId || playing}>{stage === 'complete' ? '重播孵化' : '開始孵化'}</Button><Button kind="secondary" disabled={!playing} onClick={() => { playingRef.current = false; setPlaying(false); setStage('complete'); planHatchSkip(playing, confirmedReceiptId).forEach(event => onEvent?.(event)) }}>跳過</Button><Button kind="text" disabled={stage === 'idle'} onClick={() => { if (playingRef.current) emit('cancel', 'idle'); playingRef.current = false; setPlaying(false); setStage('idle') }}>取消／返回</Button></div><p className="fine-print">跳過、重播與取消只改變畫面，沒有進度或積分寫入。</p></Card> // 可操作完整生命週期與靜態退路。
}
