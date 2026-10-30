import { useState } from 'react' // 草稿退出與來源抽屜只在本頁 fixture。
import { Button, Card, Dialog, Field, StatusMessage } from './components'
import './panel-gallery.css'

export function PanelGallery() { // 退出時保留草稿並讓使用者明確決定。
  const [open, setOpen] = useState(false)
  const [confirm, setConfirm] = useState(false)
  const [drawer, setDrawer] = useState(false)
  const [text, setText] = useState('')
  const [saved, setSaved] = useState('')
  const [error, setError] = useState(false)
  const [toast, setToast] = useState<'saved' | 'discarded' | 'error' | null>(null)
  const dirty = text !== saved
  const requestExit = () => { setOpen(false); if (dirty) setConfirm(true) }
  const returnToDraft = () => { setConfirm(false); setOpen(true) }
  const save = () => { setSaved(text); setError(false); setOpen(false); setToast('saved') }
  const discard = () => { setText(saved); setConfirm(false); setError(false); setToast('discarded') }
  return <Card title="面板、來源與未存退出"><p>所有內容均為本頁 fixture。退出未保存草稿時會要求選擇；保存失敗保留輸入。</p><div className="action-row"><Button onClick={() => setOpen(true)}>開啟草稿面板</Button><Button kind="secondary" onClick={() => setDrawer(true)}>開啟來源抽屜</Button></div>{toast && <div className="toast" role={toast === 'error' ? 'alert' : 'status'}>{toast === 'saved' ? '已保存此頁示範草稿' : toast === 'discarded' ? '已捨棄未存變更' : '示範保存失敗，內容仍在面板'}<button type="button" aria-label="關閉通知" onClick={() => setToast(null)}>×</button></div>}<Dialog title="草稿編輯面板" open={open} onClose={requestExit}><Field label="草稿文字"><textarea className="panel-gallery__draft" rows={5} value={text} onChange={event => setText(event.target.value)} /></Field>{error && <StatusMessage tone="error">示範保存失敗；輸入仍保留，可重試或返回。</StatusMessage>}<div className="action-row"><Button onClick={save}>保存此頁 fixture</Button><Button kind="secondary" onClick={() => { setError(true); setToast('error') }}>模擬保存失敗</Button><Button kind="text" onClick={requestExit}>返回</Button></div></Dialog><Dialog title="未保存變更" open={confirm} onClose={returnToDraft}><p>草稿尚未保存。可以繼續編輯，或明確捨棄本次變更。</p><div className="action-row"><Button onClick={returnToDraft}>繼續編輯</Button><Button kind="danger" onClick={discard}>捨棄變更</Button></div></Dialog><Dialog title="來源抽屜" open={drawer} variant="drawer" onClose={() => setDrawer(false)}><p>以下為虛構來源清單，不連接人物或外部網站。</p>{Array.from({ length: 16 }, (_, index) => <p key={index}>示範來源 {index + 1}：需由宿主核對來源與版本後使用。</p>)}<Button kind="secondary" onClick={() => setDrawer(false)}>關閉來源</Button></Dialog></Card>
} // Dialog 的 Escape、背景與關閉鍵走同一退出守衛。
