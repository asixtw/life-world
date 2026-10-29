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
}) // 不接觸正式人物、進度或獎勵。
