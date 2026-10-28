import { useState } from 'react' // 可操作的正常、異常與邊界狀態。
import { Button, Card, Dialog, Field, StatusMessage } from './components' // 與正式元件樣式一致。

type ViewState = 'loading' | 'empty' | 'error' | 'permission' | 'success' // 每個狀態可單獨預覽。
const states: { id: ViewState; label: string }[] = [{ id: 'loading', label: '載入' }, { id: 'empty', label: '空白' }, { id: 'error', label: '錯誤' }, { id: 'permission', label: '權限' }, { id: 'success', label: '成功' }] // 不需要改程式即可切換。

export function StateGallery() { // 展示表單、面板、Toast、權限與回執。
  const [state, setState] = useState<ViewState>('empty') // 目前系統訊息。
  const [sheet, setSheet] = useState(false) // 手機底部面板。
  const [toast, setToast] = useState(false) // 短暫回饋由使用者關閉。
  return <Card title="系統狀態與退路"><p>切換載入、空白、失敗、權限與成功。資料均為虛構展示，重試不呼叫網路。</p><div className="action-row">{states.map(item => <Button key={item.id} kind={state === item.id ? 'primary' : 'secondary'} onClick={() => setState(item.id)}>{item.label}</Button>)}</div>{state === 'loading' && <StatusMessage tone="info">正在處理示範資料…可返回或取消。</StatusMessage>}{state === 'empty' && <StatusMessage tone="info">目前沒有項目。可開始新增或回到上一頁。</StatusMessage>}{state === 'error' && <StatusMessage tone="error">示範請求失敗，草稿仍保留。請重試或手動繼續。</StatusMessage>}{state === 'permission' && <StatusMessage tone="warning">麥克風權限未取得。可改用文字或音檔入口。</StatusMessage>}{state === 'success' && <StatusMessage tone="success">示範回執已顯示；正式交易仍待後端確認。</StatusMessage>}<div className="action-row"><Button kind="secondary" onClick={() => setState('success')}>重試（fixture）</Button><Button kind="text" onClick={() => setState('empty')}>返回</Button><Button onClick={() => setSheet(true)}>開啟 BottomSheet</Button><Button kind="secondary" onClick={() => setToast(true)}>顯示 Toast</Button></div><div className="form-grid demo-state-inputs"><Field label="停用輸入" help="尚不可編輯"><input disabled defaultValue="停用狀態" /></Field><Field label="載入中輸入" help="aria-busy 已標示"><input readOnly aria-busy="true" defaultValue="處理中…" /></Field></div>{toast && <div role="status" className="toast">展示通知已顯示。<button type="button" onClick={() => setToast(false)} aria-label="關閉通知">×</button></div>}<Dialog title="底部面板示範" open={sheet} variant="sheet" onClose={() => setSheet(false)}><p>可以按 Escape、背景或關閉鍵退出，並回到原控制。</p><Button kind="secondary" onClick={() => setSheet(false)}>完成</Button></Dialog></Card> // 錯誤、重試及焦點退路均可點選。
}
