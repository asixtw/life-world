import type { AssetRef, Persona, Scenario, SourceRef } from './contracts' // 內容驗證不依賴正式資料庫。
import { validateScenario } from './engine' // 共用節點可達性檢查。

export function validateCatalog(personas: Persona[], scenarios: Scenario[], sources: SourceRef[], assets: AssetRef[]): string[] { // 在內容定版時一次找出錯誤。
  const errors: string[] = [] // 所有問題可同時回報給內容編輯者。
  const sourceIds = new Set(sources.map(item => item.id)) // 來源引用需存在。
  const assetIds = new Set(assets.map(item => item.id)) // 人物頭像需對應實檔。
  const personaIds = new Set(personas.map(item => item.id)) // 固定 ID 不得重複。
  const scenarioIds = new Set(scenarios.map(item => item.id)) // 場景 ID 不得重複。
  if (personaIds.size !== personas.length) errors.push('人物 ID 重複') // 防止選角錯亂。
  if (scenarioIds.size !== scenarios.length) errors.push('場景 ID 重複') // 防止會話串線。
  if (sourceIds.size !== sources.length) errors.push('來源 ID 重複') // 防止錯誤歸因。
  if (assetIds.size !== assets.length) errors.push('資產 ID 重複') // 防止展示錯圖。
  for (const persona of personas) { // 逐位檢查用途和引用。
    if (persona.usageScope !== 'demo') errors.push(`${persona.id} 用途不是 demo`) // 防止示範人物進正式資料。
    if (!assetIds.has(persona.avatarId)) errors.push(`${persona.id} 頭像資產不存在`) // 禁止空路徑。
    for (const id of persona.sourceRefs) if (!sourceIds.has(id)) errors.push(`${persona.id} 引用缺失來源 ${id}`) // 不容假引用。
  }
  for (const scenario of scenarios) { // 逐場景檢查 pack、節點和來源。
    if (!personas.some(item => item.packId === scenario.packId)) errors.push(`${scenario.id} 找不到同組人物`) // 避免錯組角色。
    errors.push(...validateScenario(scenario).map(error => `${scenario.id}: ${error}`)) // 分支全部需有目標節點。
    for (const id of scenario.sourceRefs) if (!sourceIds.has(id)) errors.push(`${scenario.id} 引用缺失來源 ${id}`) // 場景來源可追溯。
    for (const node of scenario.nodes) for (const turn of node.lines) for (const id of turn.sourceRefs) if (!sourceIds.has(id)) errors.push(`${turn.id} 引用缺失來源 ${id}`) // 每句引用檢查。
  }
  return errors // 空陣列代表資料契約可用，非人物真實性驗收。
}
