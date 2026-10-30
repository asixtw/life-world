import { useEffect, useRef, useState } from 'react' // owner 切換與非同步儲存需防止晚回應串畫面。
import { Button, Card, Field, StatusMessage } from './components' // 原生按鈕與可讀狀態。
import { IndexedDbDraftRepository, retryMaterialLink, saveTextThenLink, VersionConflictError } from './draft-persistence' // 真 IndexedDB 與部分成功退路。
import type { DraftRecord, DraftRepository, StoredSource } from './draft-persistence' // 型別化草稿版本。
import type { MediaDraftImport } from './MediaDemo' // 只接本機套用，不接正式人物或經歷。

const draftId = 'v11-record-fixture' // 同名草稿用來檢查 owner 隔離。
const empty = (ownerId: string): DraftRecord => ({ ownerId, draftId, revision: 0, text: '', materials: [], source: null, originalTranscript: '', reviewed: false }) // 不預設已存成果。
const pendingLink = (record: DraftRecord) => record.source && !record.materials.includes(record.source.id) ? '素材待連結' : null // 重整後仍可重試已保存 Blob 的連結。
async function readWithDemoDelay(repository: DraftRepository, ownerId: string): Promise<DraftRecord | null> { // QA fixture 可重現慢回讀，不改正式儲存語意。
  const found = await repository.load(ownerId, draftId)
  const delay = Number(new URLSearchParams(window.location.search).get('qa-draft-delay') ?? 0)
  if (delay > 0 && delay <= 1000) await new Promise(resolve => window.setTimeout(resolve, delay))
  return found
}
export function PersistentDraftDemo({ imported, onImportApplied }: { imported?: MediaDraftImport | null; onImportApplied?: () => void }) { // 僅在獨立 ui-kit 的 IndexedDB 命名空間保存虛構 fixture。
  const repository = useRef(new IndexedDbDraftRepository()).current // 真瀏覽器儲存，沒有正式後端。
  const [ownerId, setOwnerId] = useState('demo-owner-a') // 兩個固定 fixture owner，不是正式登入。
  const [draft, setDraft] = useState<DraftRecord>(empty(ownerId)) // 已回讀版本與本地輸入分開。
  const [text, setText] = useState('') // 未保存編輯即使失敗仍保留。
  const [localSource, setLocalSource] = useState<StoredSource | null>(null) // 真選檔 Blob 與校對文字同一 owner 草稿。
  const [originalTranscript, setOriginalTranscript] = useState('') // 辨識原文與人工文字分開。
  const [reviewed, setReviewed] = useState(false) // 校對標記只屬本機草稿。
  const [preview, setPreview] = useState('') // 本機 Blob 預覽 URL 在卸載時釋放。
  const [mode, setMode] = useState<'normal' | 'save-failure' | 'link-failure'>('normal') // 可重現儲存與連結故障。
  const [linkError, setLinkError] = useState<string | null>(null) // 文字成功後的獨立素材錯誤。
  const [message, setMessage] = useState('正在回讀本機草稿…') // 不把記憶體誤稱持久化。
  const [remote, setRemote] = useState<DraftRecord | null>(null) // 版本衝突時供使用者核對。
  const [loading, setLoading] = useState(true) // 尚未知道 revision 時禁止保存，以免誤蓋舊版。
  const operation = useRef(0) // owner 或重整變更使舊 UI 回應失效。
  const editGeneration = useRef(0) // 載入期間的人工輸入不可被回讀覆蓋。
  const sourceGeneration = useRef(0) // 文字編輯不阻止已存 Blob／原文回讀；素材匯入另計世代。
  useEffect(() => { if (!imported) return; editGeneration.current++; sourceGeneration.current++; setText(imported.editedTranscript); setLocalSource(imported.source); setOriginalTranscript(imported.originalTranscript); setReviewed(imported.reviewed); setMessage('已套用 MediaDemo 的本機素材與校對文字；尚未保存'); onImportApplied?.() }, [imported, onImportApplied]) // 明確複製，不能自動造正式人物。
  useEffect(() => { if (!localSource?.blob) { setPreview(''); return }; const url = URL.createObjectURL(localSource.blob); setPreview(url); return () => URL.revokeObjectURL(url) }, [localSource]) // 重新載入的 Blob 也可再次預覽。
  useEffect(() => { const token = ++operation.current; const editAtStart = editGeneration.current; const sourceAtStart = sourceGeneration.current; setDraft(empty(ownerId)); setLoading(true); setRemote(null); setLinkError(null); setMessage('正在回讀本機草稿…'); void readWithDemoDelay(repository, ownerId).then(found => { if (operation.current !== token) return; const result = found ?? empty(ownerId); setDraft(result); setLinkError(pendingLink(result)); if (editGeneration.current === editAtStart) setText(result.text); if (sourceGeneration.current === sourceAtStart) { setLocalSource(result.source ?? null); setOriginalTranscript(result.originalTranscript ?? '') }; setReviewed(editGeneration.current === editAtStart && sourceGeneration.current === sourceAtStart ? result.reviewed ?? false : false); setLoading(false); setMessage(editGeneration.current === editAtStart ? found ? `已回讀本機草稿 v${result.revision}` : '此 owner 尚無本機草稿' : '回讀完成；載入期間的新輸入已保留，請明確保存') }).catch(error => { if (operation.current === token) { setLoading(false); setMessage(`回讀失敗：${error instanceof Error ? error.message : 'unknown'}`) } }); return () => { operation.current++ } }, [ownerId, repository]) // 重整與切換 owner 均從 IndexedDB 回讀。
  const save = async () => { // 文字、原文及真 Blob 綁在同一 owner/draft/version 交易。
    const token = operation.current
    const editAtStart = editGeneration.current
    const payload: DraftRecord = { ...draft, text, source: localSource, originalTranscript, reviewed }
    setMessage('保存中…')
    try {
      if (mode === 'save-failure') throw new Error('模擬保存失敗')
      const materialId = localSource?.id ?? 'fixture-material-1'
      const next = localSource || mode === 'link-failure' ? await saveTextThenLink(repository, payload, draft.revision, materialId, async () => { if (mode === 'link-failure') throw new Error('模擬素材連結失敗') }) : { draft: await repository.save(payload, draft.revision), linkError: null }
      if (operation.current !== token) return
      setDraft(next.draft); setLinkError(next.linkError); setRemote(null)
      setMessage(editGeneration.current !== editAtStart ? `舊版已存 v${next.draft.revision}；新輸入仍待保存` : next.linkError ? `文字已存 v${next.draft.revision}；素材連結失敗，可重試` : `已存本機草稿 v${next.draft.revision}`)
    } catch (error) {
      if (operation.current !== token) return
      if (error instanceof VersionConflictError) { const current = await repository.load(ownerId, draftId); if (operation.current === token) { setRemote(current); setMessage('版本衝突：本機未存文字仍保留，請核對新版再重試') } }
      else setMessage(`保存失敗：${error instanceof Error ? error.message : 'unknown'}；未存文字與素材仍保留`)
    }
  } // 配額、權限或版本失敗都不清空本頁文字和 Blob。
  const retryLink = async () => { const token = operation.current; const result = await retryMaterialLink(repository, draft, draft.source?.id ?? 'fixture-material-1', async () => {}); if (operation.current !== token) return; setDraft(result.draft); setLinkError(result.linkError); setMessage(result.linkError ? `連結仍失敗：${result.linkError}` : `同一草稿 ${draft.draftId} 的素材已連結`) } // 真選檔使用其穩定 ID。
  const simulateParallelUpdate = async () => { try { const current = await repository.load(ownerId, draftId) ?? empty(ownerId); await repository.save({ ...current, text: `${current.text}（另一頁更新）` }, current.revision); setMessage('模擬別頁已更新；本頁版本未變') } catch (error) { setMessage(`模擬別頁更新失敗：${error instanceof Error ? error.message : 'unknown'}`) } } // 只改 demo IndexedDB。
  return <Card title="v1.1 本機草稿持久化"><p>這是虛構 fixture，使用獨立 IndexedDB 命名空間；不代表已保存到帳號或正式 App。重新整理頁面可回讀本機草稿。</p><label className="field"><span className="field__label">示範 owner</span><select value={ownerId} onChange={event => { operation.current++; editGeneration.current++; sourceGeneration.current++; setText(''); setLocalSource(null); setOriginalTranscript(''); setReviewed(false); setOwnerId(event.target.value) }}><option value="demo-owner-a">示範 A</option><option value="demo-owner-b">示範 B</option></select></label><p className="fine-print">草稿 ID：{draftId} · owner：{ownerId} · 已讀版本：{draft.revision} · 素材連結：{draft.materials.join('、') || '無'}</p><p>本機素材：{localSource?.name ?? '無'}；{localSource?.blob ? `真 Blob ${localSource.sizeBytes ?? localSource.blob.size} bytes` : '無真檔或僅 fixture'}。辨識原文（唯讀）：{originalTranscript || '無'}；人工核對：{reviewed ? '已核對' : '待核對'}。</p>{preview && localSource?.blob && (localSource.mimeType?.startsWith('image/') ? <img className="fixture-local-preview" src={preview} alt="本機草稿圖片預覽" /> : localSource.mimeType?.startsWith('audio/') ? <audio controls src={preview} aria-label="已保存本機音訊試聽" /> : <a href={preview} target="_blank" rel="noreferrer">開啟已保存本機素材</a>)}<Field label="本機草稿文字"><textarea rows={3} value={text} onChange={event => { editGeneration.current++; setText(event.target.value); setReviewed(false) }} placeholder="輸入虛構內容後明確保存" /></Field><label className="field"><span className="field__label">故障 fixture</span><select value={mode} onChange={event => setMode(event.target.value as typeof mode)}><option value="normal">正常</option><option value="save-failure">保存失敗</option><option value="link-failure">文字成功／素材連結失敗</option></select></label><div className="action-row"><Button disabled={loading} onClick={() => void save()}>保存本機草稿</Button><Button kind="secondary" onClick={() => void simulateParallelUpdate()}>模擬別頁更新</Button><Button kind="text" disabled={loading} onClick={() => { const token = ++operation.current; const editAtStart = editGeneration.current; const sourceAtStart = sourceGeneration.current; setLoading(true); void readWithDemoDelay(repository, ownerId).then(found => { if (operation.current === token) { const result = found ?? empty(ownerId); setDraft(result); setLinkError(pendingLink(result)); if (editGeneration.current === editAtStart) setText(result.text); if (sourceGeneration.current === sourceAtStart) { setLocalSource(result.source ?? null); setOriginalTranscript(result.originalTranscript ?? '') }; setReviewed(editGeneration.current === editAtStart && sourceGeneration.current === sourceAtStart ? result.reviewed ?? false : false); setRemote(null); setLoading(false); setMessage(editGeneration.current === editAtStart ? '已重新載入本機草稿' : '回讀完成；載入期間的新輸入已保留') } }).catch(error => { if (operation.current === token) { setLoading(false); setMessage(`回讀失敗：${error instanceof Error ? error.message : 'unknown'}`) } }) }}>重新載入</Button>{linkError && <Button kind="secondary" onClick={() => void retryLink()}>重試素材連結</Button>}</div>{remote && <StatusMessage tone="warning">遠端版本 v{remote.revision}：{remote.text || '空白'}。<Button kind="text" onClick={() => { setDraft(remote); setRemote(null); setMessage('已採用新版版本號；本頁未存文字仍保留，請再保存') }}>保留本頁文字並用新版重試</Button></StatusMessage>}<StatusMessage tone={message.includes('失敗') || message.includes('衝突') ? 'error' : 'info'}>{message}</StatusMessage></Card> // 顯示錯誤與保留草稿，不建立正式經歷。
} // demo owner 不映射到真帳號，正式權限與容量另待審查。
