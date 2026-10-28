import { useEffect, useRef, useState } from 'react' // 轉場播放器可逐一重播。
import { Button, Card } from './components' // 操作沿用共用按鈕。
import type { TransitionEvent } from './contracts' // 宿主可觀察完成與取消。
import { planTransitionStart, planTransitionUnmount } from './transition-machine' // 靜態與卸載事件序列可測。

type TransitionId = 'page' | 'tab' | 'card' | 'drawer' | 'focus' | 'story' | 'upload' | 'process' | 'confirm' | 'return' // 十個指定類型共用動效 token。
const transitions: { id: TransitionId; label: string }[] = [{ id: 'page', label: '頁面切換' }, { id: 'tab', label: '分頁切換' }, { id: 'card', label: '卡片展開' }, { id: 'drawer', label: '抽屜進出' }, { id: 'focus', label: '人物聚焦' }, { id: 'story', label: '故事切換' }, { id: 'upload', label: '上傳' }, { id: 'process', label: '處理' }, { id: 'confirm', label: '確認回饋' }, { id: 'return', label: '返回' }] // 各類提供固定 ID。

export function Transitions({ quiet, reducedMotion, onEvent }: { quiet: boolean; reducedMotion: boolean; onEvent?: (event: TransitionEvent) => void }) { // 偏好切換時自然落到定格。
  const [active, setActive] = useState<TransitionId>('page') // 目前選擇的轉場。
  const [playKey, setPlayKey] = useState(0) // 變更 key 重新播放 CSS 動效。
  const [show, setShow] = useState(true) // 可單獨展示返回狀態。
  const [running, setRunning] = useState(false) // 動畫事件只回報目前播放序列。
  const runningRef = useRef(false) // 卸載時辨識真正未完動畫。
  const activeRef = useRef(active) // 卸載回報當時的轉場 ID。
  const callbackRef = useRef(onEvent) // 宿主更新回呼時不使用舊閉包。
  callbackRef.current = onEvent // 每次 render 同步。
  activeRef.current = active // 每次 render 同步。
  const [osReduced, setOsReduced] = useState(() => typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) // 尊重 OS 設定。
  const still = quiet || reducedMotion || osReduced // 靜態模式不等待 CSS 動畫事件。
  const emit = (type: TransitionEvent['type'], id: TransitionId) => onEvent?.({ type, transitionId: id }) // 回報不含產品資料。
  const replay = (id = active) => { if (runningRef.current) emit('cancel', activeRef.current); activeRef.current = id; setActive(id); setShow(true); setPlayKey(key => key + 1); planTransitionStart(id, still).forEach(event => onEvent?.(event)); runningRef.current = !still; setRunning(!still) } // 重新播放先取消舊序列。
  const cancel = () => { setShow(false); if (runningRef.current) emit('cancel', active); runningRef.current = false; setRunning(false) } // 返回可由宿主觀察。
  useEffect(() => () => { const events = planTransitionUnmount(runningRef.current, activeRef.current); runningRef.current = false; events.forEach(event => callbackRef.current?.(event)) }, []) // 導覽離開只取消未完成動畫。
  useEffect(() => { const query = window.matchMedia?.('(prefers-reduced-motion: reduce)'); if (!query) return; const update = () => setOsReduced(query.matches); query.addEventListener('change', update); return () => query.removeEventListener('change', update) }, []) // OS 變動立即更新。
  useEffect(() => { if (running && still) { runningRef.current = false; setRunning(false); emit('complete', active) } }, [running, still, active]) // 動畫中切換偏好只完成一次。
  return <Card title="轉場播放器"><p>點選任何轉場，再用重播核對。Quiet 與減少動效立即定格，沒有聲音。</p><div className="transition-picker">{transitions.map(item => <Button kind={active === item.id ? 'primary' : 'secondary'} key={item.id} onClick={() => replay(item.id)}>{item.label}</Button>)}</div><div className="transition-stage" aria-live="polite"><div key={`${active}-${playKey}`} onAnimationEnd={() => { if (runningRef.current && !still) { runningRef.current = false; setRunning(false); emit('complete', active) } }} className={`transition-object transition-object--${active} ${still ? 'transition-object--still' : ''}`}>{show ? <><span aria-hidden="true">✦</span><strong>{transitions.find(item => item.id === active)?.label}</strong><small>展示狀態 · 480ms</small></> : <span>已返回</span>}</div></div><div className="action-row"><Button onClick={() => replay()}>重播</Button><Button kind="secondary" onClick={cancel}>返回</Button></div></Card> // 播放器只呈現視覺，不觸發產品交易。
}
