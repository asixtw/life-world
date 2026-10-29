import { useEffect, useRef, useState } from 'react' // 音軌生命週期由 gallery 清理。
import { Button, Card, StatusMessage } from './components' // 可讀播放狀態。
import { SoundPolicy } from './sound-policy' // 預設關閉、Quiet 無聲、回執去重。
import soundManifest from '../assets/audio-candidates/manifest.json' // 真 WAV 檔案的來源及技術量測。
import './sound-gallery.css' // 音效候選列表限本套件樣式。

const urls = { ...import.meta.glob('../assets/audio-candidates/wav/*.wav', { eager: true, query: '?url', import: 'default' }), ...import.meta.glob('../assets/audio-candidates/m4a/*.m4a', { eager: true, query: '?url', import: 'default' }), ...import.meta.glob('../assets/audio-candidates/ogg/*.ogg', { eager: true, query: '?url', import: 'default' }) } as Record<string, string> // 只載入真實存在的三格式檔案。
type SoundFormat = 'wav' | 'm4a' | 'ogg' // 播放版選項由使用者明示。
export function SoundGallery({ quiet }: { quiet: boolean }) { // 三格式仍待 Boyi／Jerry 審查。
  const [enabled, setEnabled] = useState(false) // 使用者未啟用前無聲。
  const [format, setFormat] = useState<SoundFormat>('wav') // 原稿優先，播放器不自動啟動。
  const [message, setMessage] = useState('聲音預設關閉；此頁不自動播放。') // 初始靜默。
  const [receiptId, setReceiptId] = useState('demo-receipt-1') // 僅供去重 fixture。
  const policy = useRef(new SoundPolicy()).current // 同頁操作維持已播回執集合。
  const current = useRef<HTMLAudioElement | null>(null) // 切換聲音時停止舊音軌。
  policy.setEnabled(enabled) // 元件開關映射政策。
  policy.setQuiet(quiet) // Quiet 永遠優先。
  useEffect(() => { if (quiet || !enabled) { current.current?.pause(); current.current = null } }, [quiet, enabled]) // 偏好變更立即停止播放。
  useEffect(() => { current.current?.pause(); current.current = null }, [format]) // 切換格式時不讓上一音軌繼續播放。
  useEffect(() => () => { current.current?.pause(); current.current = null }, []) // 卸載不留下音軌。
  const play = async (assetId: string) => { const url = urls[`../assets/audio-candidates/${format}/${assetId}.${format}`]; if (!url) { setMessage(`缺少音檔 ${assetId}.${format}`); return } try { current.current?.pause(); const audio = new Audio(url); current.current = audio; await audio.play(); setMessage(`正在試聽 ${assetId}.${format}；這是原創程式合成候選。`) } catch (error) { setMessage(`音效播放失敗：${error instanceof Error ? error.message : 'unknown'}；原操作不受影響。`) } } // 失敗不阻斷頁面操作。
  return <Card title="v1.1 音效候選"><p>五事件各兩個真實 48 kHz WAV 原稿與 AAC／M4A、Ogg 播放版；由原創程式合成，Boyi 尚未聽審。</p><label className="toggle"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} /> 明確開啟試聽</label><label>試聽格式<select value={format} onChange={event => setFormat(event.target.value as SoundFormat)}><option value="wav">WAV 原稿</option><option value="m4a">AAC／M4A</option><option value="ogg">Ogg Vorbis</option></select></label>{quiet && <StatusMessage tone="info">Quiet 模式無聲。</StatusMessage>}<div className="sound-gallery">{soundManifest.events.map(item => <div className="sound-gallery__row" key={item.id}><span>{item.event} · 候選 {item.candidate} · {item.durationSeconds} 秒 · 峰值 {item.peakDbfs} dBFS</span><Button kind="secondary" disabled={!enabled || quiet} onClick={() => void play(item.id)}>試聽 {item.id}</Button></div>)}</div><div className="action-row"><label>虛構回執<input value={receiptId} onChange={event => setReceiptId(event.target.value)} /></label><Button disabled={!enabled || quiet} onClick={() => { if (policy.request('experience-confirmed', receiptId)) void play('experience-confirmed-01'); else setMessage('同回執已略過、缺回執或聲音已關閉。') }}>播放確認事件 fixture</Button></div><StatusMessage tone="info">{message}</StatusMessage></Card> // 音效只在明確 click 或宿主確認事件下播放。
} // 正式回執、音量政策及編碼格式仍待審查。
