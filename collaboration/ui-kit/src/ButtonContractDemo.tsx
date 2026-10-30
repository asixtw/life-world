import { useRef, useState } from 'react' // 實際 DOM ref 與原生 submit 行為核對。
import { Button, Card, StatusMessage } from './components' // 不為測試另造按鈕實作。

export function ButtonContractDemo() { // 只在隔離 gallery 驗證元件可供宿主接入。
  const submitRef = useRef<HTMLButtonElement>(null) // 呼叫端取得真正 DOM button。
  const [result, setResult] = useState('尚未送出') // 成功與錯誤可讀。
  return <Card title="v1.1 Button 原生契約"><form onSubmit={event => { event.preventDefault(); setResult(submitRef.current?.type === 'submit' && submitRef.current?.getAttribute('aria-label') === '送出示範' ? 'ref、type 與 aria 均已透傳' : '按鈕原生契約失敗') }}><div className="action-row"><Button ref={submitRef} type="submit" aria-label="送出示範">送出</Button><Button type="button" aria-label="停用示範" disabled>停用</Button></div></form><StatusMessage tone={result.includes('失敗') ? 'error' : 'info'}>{result}</StatusMessage></Card> // 不提交正式資料。
} // ref 與事件實際操作由 Chrome QA 覆蓋。
