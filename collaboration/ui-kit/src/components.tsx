import type { ReactNode } from 'react' // 共用展示元件的子內容型別。
import { useEffect, useRef } from 'react' // 對話框處理初始焦點與 Escape。

export type ButtonKind = 'primary' | 'secondary' | 'text' | 'icon' | 'danger' // 六類按鈕由切換樣式涵蓋。
export function Button({ children, kind = 'primary', loading = false, success = false, error = false, disabled = false, onClick, title }: { children: ReactNode; kind?: ButtonKind; loading?: boolean; success?: boolean; error?: boolean; disabled?: boolean; onClick?: () => void; title?: string }) { // 統一按鈕狀態及事件。
  return <button className={`button button--${kind} ${success ? 'is-success' : ''} ${error ? 'is-error' : ''}`} type="button" disabled={disabled || loading} aria-busy={loading} title={title} onClick={onClick}>{loading ? '處理中…' : children}</button> // 原生 button 支援鍵盤、停用與焦點。
}

export function Field({ label, help, error, children }: { label: string; help?: string; error?: string; children: ReactNode }) { // 文字、長文與其他輸入共用標籤。
  return <label className={`field ${error ? 'field--error' : ''}`}><span className="field__label">{label}</span>{children}{error ? <span role="alert" className="field__error">{error}</span> : help ? <span className="field__help">{help}</span> : null}</label> // 錯誤附文字，不只靠顏色。
}

export function Card({ title, children, subtle = false }: { title?: string; children: ReactNode; subtle?: boolean }) { // 卡片容納長內容與不同狀態。
  return <section className={`card ${subtle ? 'card--subtle' : ''}`}>{title && <h3>{title}</h3>}{children}</section> // 保持語意標題。
}

export function StatusMessage({ tone, children }: { tone: 'info' | 'success' | 'error' | 'warning'; children: ReactNode }) { // 載入、成功、失敗與權限退路共用訊息。
  return <div className={`status status--${tone}`} role={tone === 'error' ? 'alert' : 'status'}>{children}</div> // 螢幕閱讀器可收到狀態。
}

export function Dialog({ title, open, onClose, children, variant = 'dialog' }: { title: string; open: boolean; onClose: () => void; children: ReactNode; variant?: 'dialog' | 'sheet' }) { // 展示面板可關閉並恢復焦點。
  const closeRef = useRef<HTMLButtonElement>(null) // 記錄第一個可操作控制。
  const previousRef = useRef<HTMLElement | null>(null) // 關閉後回到原控制。
  useEffect(() => { if (!open) return; previousRef.current = document.activeElement as HTMLElement; closeRef.current?.focus(); const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); if (event.key === 'Tab') { const dialog = closeRef.current?.closest('[role=dialog]'); const focusable = [...(dialog?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href]') ?? [])]; if (!focusable.length) return; const first = focusable[0]; const last = focusable[focusable.length - 1]; if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() } } }; document.addEventListener('keydown', onKey); return () => { document.removeEventListener('keydown', onKey); previousRef.current?.focus() } }, [open, onClose]) // 監聽器與焦點隨面板清理。
  if (!open) return null // 關閉時從 DOM 移除 overlay。
  return <div className={`dialog-backdrop ${variant === 'sheet' ? 'dialog-backdrop--sheet' : ''}`} onMouseDown={event => { if (event.target === event.currentTarget) onClose() }}><section className={`dialog ${variant === 'sheet' ? 'dialog--sheet' : ''}`} role="dialog" aria-modal="true" aria-label={title}><header className="dialog__head"><h2>{title}</h2><button ref={closeRef} className="icon-close" type="button" aria-label="關閉面板" onClick={onClose}>×</button></header>{children}</section></div> // 點背景與 Escape 均可退出。
}


