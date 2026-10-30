import { describe, expect, it } from 'vitest' // 模擬草稿不接正式資料儲存。
import { personas, scenarios } from '../content/catalog' // 使用現有版本化示範資料。
import { choose, startSession } from '../src/engine' // 驗證真回合可安全還原。
import { emptyTheaterDraft, loadTheaterDraft, saveTheaterDraft, theaterDraftKey } from '../src/theater-draft' // 測同 owner 與壞資料退路。

const memoryStorage = () => { // 只在單元測試使用記憶體 Storage。
  const rows = new Map<string, string>() // 鍵值隔離於此測試。
  return { rows, storage: { getItem: (key: string) => rows.get(key) ?? null, setItem: (key: string, value: string) => { rows.set(key, value) } } as Storage } // 只實作草稿會用的介面。
} // 不碰瀏覽器或正式資料庫。

describe('劇場同 owner 模擬草稿', () => { // 只恢復明示 demo session。
  it('刷新可恢復路徑，其他 owner 不能讀取', () => { // 同一對話的回合與歷史須一同續作。
    const { storage } = memoryStorage() // 準備測試儲存。
    const persona = personas.find(item => item.name === '柏拉圖')! // 選實際示範人物。
    const scenario = scenarios.find(item => item.packId === persona.packId)! // 選同包場景。
    const first = startSession(persona.id, scenario) // 建立 demo 對話。
    const next = choose(first, scenario, scenario.nodes.find(item => item.id === scenario.startNodeId)!.choices[0].id) // 留一輪選擇。
    const draft = { ownerId: 'alpha', personaId: persona.id, scenarioId: scenario.id, session: next, history: [first] } // 保存完整路徑。
    expect(saveTheaterDraft(storage, draft)).toBe(true) // 同 owner 寫入成功。
    expect(loadTheaterDraft(storage, 'alpha', personas, scenarios)).toEqual(draft) // 刷新等價恢復。
    expect(loadTheaterDraft(storage, 'bravo', personas, scenarios)).toEqual(emptyTheaterDraft('bravo')) // 不讀取其他 owner。
  })
  it('跨 owner 偽造、壞 JSON 與被拒儲存均安全回退', () => { // fixture 欄位不得用來繞過隔離。
    const { storage, rows } = memoryStorage() // 可注入損毀內容。
    rows.set(theaterDraftKey('alpha'), JSON.stringify({ ownerId: 'bravo', personaId: 'x', scenarioId: 'y', session: null, history: [] })) // 鍵內 owner 不一致。
    expect(loadTheaterDraft(storage, 'alpha', personas, scenarios)).toEqual(emptyTheaterDraft('alpha')) // 不接受跨 owner 資料。
    rows.set(theaterDraftKey('alpha'), '{bad-json') // 模擬中斷寫入。
    expect(loadTheaterDraft(storage, 'alpha', personas, scenarios)).toEqual(emptyTheaterDraft('alpha')) // 壞 JSON 不炸畫面。
    const denied = { getItem: () => { throw new Error('denied') }, setItem: () => { throw new Error('quota') } } as unknown as Storage // 模擬瀏覽器拒絕。
    expect(loadTheaterDraft(denied, 'alpha', personas, scenarios)).toEqual(emptyTheaterDraft('alpha')) // 讀取失敗保留安全空狀態。
    expect(saveTheaterDraft(denied, emptyTheaterDraft('alpha'))).toBe(false) // 寫入失敗可供 UI 告知。
  })
})
