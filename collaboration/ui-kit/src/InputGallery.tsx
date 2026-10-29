import { useState } from 'react' // 受控輸入與六種狀態僅留在展示。
import { Button, Card, Field, StatusMessage } from './components'
import './input-gallery.css' // 不改正式頁面樣式。

export type InputState = 'empty' | 'filled' | 'help' | 'error' | 'disabled' | 'loading'
export type InputKind = 'text' | 'textarea' | 'password' | 'number' | 'datetime-local' | 'search' | 'select' | 'checkbox' | 'radio' | 'switch'
export type InputValue = string | boolean
export type InputControlProps = { kind: InputKind; state: InputState; value: InputValue; onChange: (value: InputValue) => void } // 正式容器可接自己的值和事件。
const kinds: { id: InputKind; label: string }[] = [{ id: 'text', label: '文字' }, { id: 'textarea', label: '長文' }, { id: 'password', label: '密碼' }, { id: 'number', label: '數字' }, { id: 'datetime-local', label: '日期時間' }, { id: 'search', label: '搜尋' }, { id: 'select', label: '下拉' }, { id: 'checkbox', label: 'Checkbox' }, { id: 'radio', label: 'Radio' }, { id: 'switch', label: 'Switch' }]
const states: { id: InputState; label: string }[] = [{ id: 'empty', label: '空白' }, { id: 'filled', label: '填寫' }, { id: 'help', label: '說明' }, { id: 'error', label: '錯誤' }, { id: 'disabled', label: '停用' }, { id: 'loading', label: '載入' }]
const initial = (kind: InputKind, state: InputState): InputValue => kind === 'checkbox' || kind === 'switch' ? state === 'filled' : kind === 'radio' ? state === 'filled' ? 'b' : 'a' : state !== 'filled' ? '' : kind === 'number' ? '3' : kind === 'datetime-local' ? '2026-10-29T09:00' : kind === 'select' ? 'one' : '示範內容'

export function InputControl({ kind, state, value, onChange }: InputControlProps) { // 不讀取或提交正式表單。
  const disabled = state === 'disabled'
  const busy = state === 'loading'
  const error = state === 'error'
  const label = kinds.find(item => item.id === kind)?.label ?? kind
  const help = state === 'help' ? '此欄內容僅保留在本頁 fixture。' : undefined
  const errorText = error ? '請檢查此欄的示範內容。' : undefined
  if (kind === 'radio') return <fieldset className="field input-gallery__choice" disabled={disabled || busy} aria-busy={busy}><legend>{label}</legend>{['a', 'b'].map(id => <label key={id}><input type="radio" name="input-gallery-radio" checked={value === id} onChange={() => onChange(id)} aria-invalid={error} />選項 {id.toUpperCase()}</label>)}{errorText && <span role="alert" className="field__error">{errorText}</span>}{help && <span className="field__help">{help}</span>}</fieldset>
  if (kind === 'checkbox' || kind === 'switch') return <Field label={label} help={help} error={errorText}><input type="checkbox" role={kind === 'switch' ? 'switch' : undefined} checked={Boolean(value)} disabled={disabled || busy} aria-busy={busy} aria-invalid={error} onChange={event => onChange(event.target.checked)} /></Field>
  if (kind === 'textarea') return <Field label={label} help={help} error={errorText}><textarea rows={3} value={String(value)} disabled={disabled} readOnly={busy} aria-busy={busy} aria-invalid={error} onChange={event => onChange(event.target.value)} /></Field>
  if (kind === 'select') return <Field label={label} help={help} error={errorText}><select value={String(value)} disabled={disabled || busy} aria-busy={busy} aria-invalid={error} onChange={event => onChange(event.target.value)}><option value="">請選擇</option><option value="one">第一項</option><option value="two">第二項</option></select></Field>
  return <Field label={label} help={help} error={errorText}><input type={kind} value={String(value)} disabled={disabled} readOnly={busy} aria-busy={busy} aria-invalid={error} onChange={event => onChange(event.target.value)} /></Field>
}

export function InputGallery() { // 矩陣中每種輸入與每種狀態都能獨立切換檢查。
  const [state, setState] = useState<InputState>('empty')
  const [values, setValues] = useState<Record<InputKind, InputValue>>(() => Object.fromEntries(kinds.map(item => [item.id, initial(item.id, 'empty')])) as Record<InputKind, InputValue>)
  const choose = (next: InputState) => { setState(next); setValues(Object.fromEntries(kinds.map(item => [item.id, initial(item.id, next)])) as Record<InputKind, InputValue>) }
  return <Card title="受控輸入矩陣"><p>十種輸入 × 六種狀態；內容只在本頁，宿主可接 typed value／onChange。載入為不定狀態，不捏造百分比。</p><div className="action-row" aria-label="輸入狀態">{states.map(item => <Button key={item.id} kind={state === item.id ? 'primary' : 'secondary'} aria-pressed={state === item.id} onClick={() => choose(item.id)}>{item.label}</Button>)}</div><div className="form-grid input-gallery">{kinds.map(item => <InputControl key={item.id} kind={item.id} state={state} value={values[item.id]} onChange={value => setValues(previous => ({ ...previous, [item.id]: value }))} />)}</div>{state === 'loading' && <StatusMessage tone="info">輸入資料處理中；可切換狀態或返回。</StatusMessage>}</Card>
}
