import { describe, expect, it } from 'vitest' // 媒體流程先寫真正風險的紅燈測試。
import { MediaWorkflow } from '../src/media-workflow' // 測取消、晚回應與文字來源分離。

describe('v1.1 媒體草稿契約', () => { // mock 只驗本機邏輯，不冒充後端。
  it('選檔後不自動上傳；明確上傳才取得素材回執', async () => { // 預覽和提交分開。
    let calls = 0 // 記錄 adapter 是否被呼叫。
    const flow = new MediaWorkflow({ upload: async () => { calls++; return 'material-1' }, recognize: async () => '辨識原文', save: async () => 2 }) // 虛構 adapter。
    flow.select({ id: 'local-1', name: 'fixture.png', kind: 'image' }) // 只選本機素材。
    expect(flow.snapshot().phase).toBe('ready') // 尚未上傳。
    expect(calls).toBe(0) // 不自動呼叫服務。
    await flow.uploadSelected() // 使用者明確提交。
    expect(calls).toBe(1) // 僅呼叫一次。
    expect(flow.snapshot().materialReceipt).toBe('material-1') // 回執來自 adapter。
  }) // 選取行為不產生正式經歷。
  it('取消後晚到辨識不能覆寫已編輯文字或原文', async () => { // 非同步世代使舊回應失效。
    let release!: (value: string) => void // 控制晚回應。
    const delayed = new Promise<string>(resolve => { release = resolve }) // 模擬已送出的辨識。
    const flow = new MediaWorkflow({ upload: async () => 'receipt', recognize: async () => delayed, save: async () => 2 }) // 無真服務。
    flow.select({ id: 'local-2', name: 'fixture.wav', kind: 'audio' }) // 保存原素材身分。
    await flow.uploadSelected() // 取得素材回執。
    const pending = flow.recognize() // 開始辨識。
    flow.cancel() // 使用者離開此工作。
    flow.editTranscript('我自己寫的版本') // 人工文字另存。
    release('遲到的辨識文字') // 舊回應仍可能抵達。
    await pending // 等候 callback 完成。
    expect(flow.snapshot().originalTranscript).toBe('') // 不接納晚回應。
    expect(flow.snapshot().editedTranscript).toBe('我自己寫的版本') // 不覆寫人工校對。
    expect(flow.snapshot().source?.id).toBe('local-2') // 原素材保留。
  }) // 取消不等於伺服器已撤銷，正式宿主須查狀態。
  it('版本衝突保留草稿並返回可核對錯誤', async () => { // 不可假裝保存成功。
    const flow = new MediaWorkflow({ upload: async () => 'receipt', recognize: async () => '', save: async () => { throw new Error('version-conflict') } }) // 模擬服務拒絕。
    flow.editTranscript('保留的摘要') // 草稿先在本地。
    await flow.saveDraft() // 明確保存。
    expect(flow.snapshot()).toMatchObject({ editedTranscript: '保留的摘要', phase: 'error', error: 'version-conflict', version: 1 }) // 版本不前進。
  }) // 重試由宿主確認版本後才執行。
  it('格式與容量由宿主驗證，拒絕檔案仍保留人工草稿', () => { // 本套件不宣告正式 5MiB 或 30 秒政策。
    const flow = new MediaWorkflow({ upload: async () => 'receipt', recognize: async () => '', save: async () => 2 }, undefined, source => source.sizeBytes && source.sizeBytes > 10 ? 'host-limit' : null) // 測試能力由宿主注入。
    flow.editTranscript('先前輸入的文字') // 其他輸入先存在。
    flow.select({ id: 'large', name: 'large.png', kind: 'image', sizeBytes: 11, mimeType: 'image/png', blob: new Blob(['too-large']) }) // 用本機 Blob 代表檔案。
    expect(flow.snapshot()).toMatchObject({ source: null, editedTranscript: '先前輸入的文字', phase: 'error', error: 'host-limit' }) // 拒絕後不丟原草稿。
  }) // 正式限制由 Jerry 接入時決定。
  it('辨識等待中清空校對欄位，晚回應只更新原文', async () => { // 空字串也是使用者有意編輯。
    let release!: (value: string) => void // 控制辨識回應時機。
    const delayed = new Promise<string>(resolve => { release = resolve }) // 模擬服務延遲。
    const flow = new MediaWorkflow({ upload: async () => 'receipt', recognize: async () => delayed, save: async () => 2 }) // 不用真 AI。
    flow.select({ id: 'audio', name: 'fixture.wav', kind: 'audio' }) // 保留素材。
    await flow.uploadSelected() // 明確上傳。
    flow.editTranscript('稍後刪除') // 原本有文字。
    const pending = flow.recognize() // 正在等待。
    flow.editTranscript('') // 人工清空仍是編輯。
    release('晚到原文') // 晚回應不應填回校對欄位。
    await pending // 讓回呼完成。
    expect(flow.snapshot()).toMatchObject({ originalTranscript: '晚到原文', editedTranscript: '', reviewed: false }) // 原文和人工校對分離。
  }) // 避免辨識覆蓋人工選擇。
}) // 不接觸正式人物、進度或獎勵。
