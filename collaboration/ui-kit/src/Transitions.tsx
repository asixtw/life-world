import { useState } from 'react' // 轉場播放器可逐一重播。
import { Button, Card } from './components' // 操作沿用共用按鈕。

type TransitionId = 'page' | 'tab' | 'card' | 'drawer' | 'focus' | 'story' | 'upload' | 'process' | 'confirm' | 'return' // 十個指定類型共用動效 token。
const transitions: { id: TransitionId; label: string }[] = [{ id: 'page', label: '頁面切換' }, { id: 'tab', label: '分頁切換' }, { id: 'card', label: '卡片展開' }, { id: 'drawer', label: '抽屜進出' }, { id: 'focus', label: '人物聚焦' }, { id: 'story', label: '故事切換' }, { id: 'upload', label: '上傳' }, { id: 'process', label: '處理' }, { id: 'confirm', label: '確認回饋' }, { id: 'return', label: '返回' }] // 各類提供固定 ID。

export function Transitions({ quiet, reducedMotion }: { quiet: boolean; reducedMotion: boolean }) { // 偏好切換時自然落到定格。
  const [active, setActive] = useState<TransitionId>('page') // 目前選擇的轉場。
  const [playKey, setPlayKey] = useState(0) // 變更 key 重新播放 CSS 動效。
  const [show, setShow] = useState(true) // 可單獨展示返回狀態。
  const still = quiet || reducedMotion // Quiet 與減少動效不需要等待。
  const replay = (id = active) => { setActive(id); setShow(true); setPlayKey(key => key + 1) } // 每次重播產生新動畫節點。
  return <Card title="轉場播放器"><p>點選任何轉場，再用重播核對。Quiet 與減少動效立即定格，沒有聲音。</p><div className="transition-picker">{transitions.map(item => <Button kind={active === item.id ? 'primary' : 'secondary'} key={item.id} onClick={() => replay(item.id)}>{item.label}</Button>)}</div><div className="transition-stage" aria-live="polite"><div key={`${active}-${playKey}`} className={`transition-object transition-object--${active} ${still ? 'transition-object--still' : ''}`}>{show ? <><span aria-hidden="true">✦</span><strong>{transitions.find(item => item.id === active)?.label}</strong><small>展示狀態 · 480ms</small></> : <span>已返回</span>}</div></div><div className="action-row"><Button onClick={() => replay()}>重播</Button><Button kind="secondary" onClick={() => setShow(false)}>返回</Button></div></Card> // 播放器只呈現視覺，不觸發產品交易。
}
