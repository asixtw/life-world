import { describe, expect, it } from 'vitest' // 驗證名單與腳本數量，不替代人工來源審查。
import { personas, scenarios, sources } from '../content/catalog' // 僅載入展示內容。
import examples from '../content/examples.v1.json' // 多輪示例不作模型訓練宣稱。
import heldout from '../evaluation/inputs.v1.json' // 模型輸入不含參考答案。
import references from '../evaluation/reference.v1.json' // 人工評估參考另檔保管。
import expectedArt from '../assets/expected-persona-art.v1.json' // 缺圖需求與已交付資產分開。
import { choose, startSession, validateScenario } from '../src/engine' // 跑完每條腳本路徑。
import { validateCatalog } from '../src/validate' // 找出未交付資產以外的契約問題。

describe('十五人資料與六場劇場', () => { // 明確覆蓋任務數量和隔離。
  it('has five fixed personas per pack and unique IDs', () => { // 不以重複名稱湊數。
    expect(personas).toHaveLength(15) // 三組各五位。
    expect(new Set(personas.map(item => item.id)).size).toBe(15) // 固定人物 ID 唯一。
    for (const pack of ['three-kingdoms', 'international-dialogue', 'philosophy']) expect(personas.filter(item => item.packId === pack)).toHaveLength(5) // 每組都有五位。
    expect(scenarios).toHaveLength(6) // 每組有兩場。
  }) // 名單定版。
  it('keeps 45 distinct multi-turn examples and 30 held-out cases separate', () => { // 參考答案不載入 UI。
    expect(examples).toHaveLength(45) // 每人三段。
    expect(heldout).toHaveLength(30) // 每人兩題。
    expect(references).toHaveLength(30) // 每題有獨立評分規則。
    expect(heldout.every(item => !('referenceAnswer' in item))).toBe(true) // 參考答案不混進輸入。
    expect(new Set(examples.map(item => item.id)).size).toBe(45) // 示例 ID 無重複。
    expect(new Set(heldout.map(item => item.id)).size).toBe(30) // 保留案例 ID 無重複。
    for (const persona of personas) { expect(examples.filter(item => item.personaId === persona.id)).toHaveLength(3); expect(heldout.filter(item => item.personaId === persona.id)).toHaveLength(2) } // 覆蓋每個人物。
    expect(examples.every(item => item.turns.length >= 4)).toBe(true) // 每段為多輪。
  }) // 研究資料隔離。
  it('plays every primary route to a distinct ending', () => { // 六場各三條實質不同選項。
    for (const scenario of scenarios) { // 逐場景驗證分支。
      expect(validateScenario(scenario)).toEqual([]) // 沒有死路或缺節點。
      const starts = scenario.nodes.find(item => item.id === scenario.startNodeId)!.choices // 三條起始路徑。
      expect(starts).toHaveLength(3) // 選項數正確。
      const endings = starts.map(first => { let session = choose(startSession(personas.find(item => item.packId === scenario.packId)!.id, scenario), scenario, first.id); const next = scenario.nodes.find(item => item.id === session.nodeId)!.choices[0]; session = choose(session, scenario, next.id); expect(session.status).toBe('ended'); return scenario.nodes.find(item => item.id === session.nodeId)!.ending }) // 每路可完成。
      expect(new Set(endings).size).toBe(3) // 三條有不同結果。
    } // 所有劇場可回顧。
  }) // 完整路徑驗證。
  it('reports missing art honestly and no other broken references', () => { // 不以空路徑假稱頭像已交。
    expect(expectedArt).toHaveLength(15) // 十五位頭像需求固定。
    expect(expectedArt.every(item => item.status === 'missing_pending_generated_art')).toBe(true) // 圖像仍未到位。
    const errors = validateCatalog(personas, scenarios, sources, []) // 尚無實際資產。
    expect(errors).toHaveLength(15) // 只剩十五頭像缺件。
    expect(errors.every(item => item.includes('頭像資產不存在'))).toBe(true) // 來源與腳本引用皆有效。
  }) // 缺件不遮掩。
}) // 避免將程式測試誤寫成人工驗收。
