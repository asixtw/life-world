import type { Persona, Scenario, SimulationSession } from './contracts' // 草稿只保存隔離劇場資料。

export interface TheaterDraft { ownerId: string; personaId: string; scenarioId: string; session: SimulationSession | null; history: SimulationSession[] } // 不含正式人物、經歷與獎勵欄位。
export const browserTheaterStorage = (): Storage | null => { try { return window.sessionStorage } catch { return null } } // 瀏覽器封鎖 storage getter 時保持可操作。
export const theaterDraftKey = (ownerId: string) => `life-world:simulation-demo:v1:${encodeURIComponent(ownerId)}` // 每個 fixture owner 有不同 sessionStorage 鍵。
export const emptyTheaterDraft = (ownerId: string, personaId = '', scenarioId = ''): TheaterDraft => ({ ownerId, personaId, scenarioId, session: null, history: [] }) // 靜態展示選角可作初始值。
const validSession = (value: unknown, personaId: string, scenarioId: string, scenarios: Scenario[]): value is SimulationSession => { // 壞草稿不得直接渲染。
  if (!value || typeof value !== 'object') return false // 缺失物件不是有效對話。
  const item = value as Partial<SimulationSession> // 只讀取已知欄位。
  const scenario = scenarios.find(entry => entry.id === scenarioId) // 路徑必須屬同一場景。
  return item.schemaVersion === '1.0' && item.usageScope === 'demo' && item.channel === 'script' && item.personaId === personaId && item.scenarioId === scenarioId && typeof item.id === 'string' && typeof item.nodeId === 'string' && !!scenario?.nodes.some(node => node.id === item.nodeId) && Array.isArray(item.path) && item.path.every(id => typeof id === 'string' && scenario.nodes.some(node => node.id === id)) && Array.isArray(item.turns) && item.turns.every(turn => typeof turn?.id === 'string' && typeof turn?.text === 'string') && ['active', 'ended'].includes(item.status ?? '') // 不接收 live 或正式資料。
} // 內容仍是未經信任的本機 fixture，React 只以文字渲染。
export function loadTheaterDraft(storage: Storage | null, ownerId: string, personas: Persona[], scenarios: Scenario[], initialPersonaId = '', initialScenarioId = ''): TheaterDraft { // 僅讀取同 owner 模擬草稿。
  const fallback = emptyTheaterDraft(ownerId, initialPersonaId, initialScenarioId) // 無資料或壞資料時保持初始選擇。
  if (!storage) return fallback // 儲存介面不可用時仍可使用本頁。
  try { // 瀏覽器可能禁止儲存，不能中斷劇場。
    const raw = storage.getItem(theaterDraftKey(ownerId)) // 不掃描其他 owner 或正式命名空間。
    if (!raw) return fallback // 首次開啟沒有草稿。
    const value = JSON.parse(raw) as Partial<TheaterDraft> // 從不執行草稿內容。
    if (value.ownerId !== ownerId || typeof value.personaId !== 'string' || typeof value.scenarioId !== 'string' || !Array.isArray(value.history)) return fallback // 擋跨 owner 與壞欄位。
    const persona = personas.find(item => item.id === value.personaId) // 只接現有示範角色。
    const scenario = scenarios.find(item => item.id === value.scenarioId && item.packId === persona?.packId) // 不接跨 pack 場景。
    if (!persona || !scenario) return fallback // 內容版本變動時不顯示錯配對話。
    if (value.session === null && value.history.length === 0) return { ...fallback, personaId: persona.id, scenarioId: scenario.id } // 無對話時可恢復選項。
    if (!validSession(value.session, persona.id, scenario.id, scenarios) || !value.history.every(item => validSession(item, persona.id, scenario.id, scenarios) && item.id === value.session?.id)) return fallback // 所有快照必須屬同一對話。
    return { ownerId, personaId: persona.id, scenarioId: scenario.id, session: value.session, history: value.history } // 恢復同 owner 的完整路徑。
  } catch { return fallback } // JSON 損毀或儲存被拒都回退到安全空草稿。
} // 不自動匯入正式 Experience／Person／Reward。
export function saveTheaterDraft(storage: Storage | null, draft: TheaterDraft): boolean { // 寫入本頁模擬續作快照。
  if (!storage) return false // 無介面時由 UI 顯示刷新風險。
  try { storage.setItem(theaterDraftKey(draft.ownerId), JSON.stringify(draft)); return true } catch { return false } // 配額與權限錯誤可讓畫面告知使用者。
} // 不發送網路請求。
