export type LocalSource = { id: string; name: string; kind: 'image' | 'audio' | 'business-card' | 'file' } // 本機素材身分不等於已上傳回執。
export type MediaPhase = 'idle' | 'ready' | 'uploading' | 'uploaded' | 'recognizing' | 'review' | 'saving' | 'saved' | 'error' // 不把等待畫成成功。
export type MediaSnapshot = { phase: MediaPhase; source: LocalSource | null; materialReceipt: string | null; originalTranscript: string; editedTranscript: string; reviewed: boolean; version: number; error: string | null } // 原文、校對、素材各自保存。
export type MediaAdapter = { upload: (source: LocalSource, signal: AbortSignal) => Promise<string>; recognize: (receipt: string, signal: AbortSignal) => Promise<string>; save: (draft: MediaSnapshot, signal: AbortSignal) => Promise<number> } // 正式容器決定權限、容量與網路。
export class MediaWorkflow { // 隔離 fixture 的可取消流程，不呼叫正式 API。
  private state: MediaSnapshot = { phase: 'idle', source: null, materialReceipt: null, originalTranscript: '', editedTranscript: '', reviewed: false, version: 1, error: null } // 初始不宣稱任何保存。
  private generation = 0 // 每次取消或來源變更都讓晚回應失效。
  private controller: AbortController | null = null // 只取消當前本機請求。
  constructor(private adapter: MediaAdapter, private onChange?: (state: MediaSnapshot) => void) {} // 宿主注入能力與通知。
  snapshot(): MediaSnapshot { return { ...this.state, source: this.state.source && { ...this.state.source } } } // 外部不能改內部快照。
  private publish(patch: Partial<MediaSnapshot>) { this.state = { ...this.state, ...patch }; this.onChange?.(this.snapshot()) } // 每次狀態轉移通知受控展示。
  private begin() { this.controller?.abort(); this.controller = new AbortController(); return { id: ++this.generation, signal: this.controller.signal } } // 新請求失效舊請求。
  private active(id: number) { return id === this.generation } // 晚回應不能覆寫新草稿。
  select(source: LocalSource) { this.cancel(); this.publish({ source: { ...source }, materialReceipt: null, originalTranscript: '', reviewed: false, phase: 'ready', error: null }) } // 選取只產生本機預覽。
  remove() { this.cancel(); this.publish({ source: null, materialReceipt: null, originalTranscript: '', reviewed: false, phase: 'idle', error: null }) } // 其他人工文字仍保留。
  editTranscript(value: string) { this.publish({ editedTranscript: value, reviewed: false, phase: this.state.phase === 'saved' ? 'review' : this.state.phase }) } // 修改必須重新校對。
  markReviewed() { if (this.state.editedTranscript.trim()) this.publish({ reviewed: true, phase: 'review' }) } // 不自動確認人物或成果。
  cancel() { this.generation++; this.controller?.abort(); this.controller = null; if (['uploading', 'recognizing', 'saving'].includes(this.state.phase)) this.publish({ phase: this.state.materialReceipt ? 'uploaded' : this.state.source ? 'ready' : 'idle', error: null }) } // 取消本機等待，正式伺服器狀態仍需宿主核對。
  async uploadSelected() { // 明確按下上傳才呼叫 adapter。
    if (!this.state.source) { this.publish({ phase: 'error', error: 'no-source' }); return } // 沒有素材不送出。
    const { id, signal } = this.begin(); this.publish({ phase: 'uploading', error: null }) // 展示上傳中，不造假百分比。
    try { const receipt = await this.adapter.upload(this.state.source, signal); if (this.active(id)) this.publish({ materialReceipt: receipt, phase: 'uploaded' }) } catch (error) { if (this.active(id)) this.publish({ phase: 'error', error: error instanceof Error ? error.message : 'upload-failed' }) } // 失敗保留本機素材。
  } // 服務回執為空應由宿主 adapter 驗證。
  async recognize() { // 辨識獨立於上傳，需明確素材回執。
    if (!this.state.materialReceipt) { this.publish({ phase: 'error', error: 'no-material-receipt' }); return } // 不憑進度動畫假稱上傳成功。
    const { id, signal } = this.begin(); this.publish({ phase: 'recognizing', error: null }) // 狀態不提供假精度。
    try { const original = await this.adapter.recognize(this.state.materialReceipt, signal); if (this.active(id)) this.publish({ originalTranscript: original, editedTranscript: this.state.editedTranscript || original, reviewed: false, phase: 'review' }) } catch (error) { if (this.active(id)) this.publish({ phase: 'error', error: error instanceof Error ? error.message : 'recognition-failed' }) } // 原素材與人工文字均保留。
  } // 取消後晚回應由世代識別擋下。
  async saveDraft() { // 儲存僅交宿主 adapter，版本不自行增加。
    const { id, signal } = this.begin(); this.publish({ phase: 'saving', error: null }) // 明示正在保存。
    try { const version = await this.adapter.save(this.snapshot(), signal); if (this.active(id)) this.publish({ version, phase: 'saved' }) } catch (error) { if (this.active(id)) this.publish({ phase: 'error', error: error instanceof Error ? error.message : 'save-failed' }) } // 衝突保留所有編輯及舊版本。
  } // 正式提交、計分與人物建立不屬此流程。
} // 此模組可由正式容器接真能力，但未宣稱已接入。
