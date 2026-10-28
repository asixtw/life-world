import type { DialogueChoice, DialogueTurn, LiveAdapter, LiveRequest, LiveResponse, Scenario, SimulationSession } from './contracts' // 使用公開契約避免引擎暗改資料。

export class ScriptError extends Error {} // 場景格式或操作錯誤給 UI 可讀退路。
export class AdapterNotConfiguredError extends Error { constructor() { super('即時 AI 尚未設定；請改用預寫腳本。') } } // 不把腳本偽裝成即時 AI。

export function getNode(scenario: Scenario, nodeId: string) { // 所有節點查找限於目前場景。
  const node = scenario.nodes.find(item => item.id === nodeId) // 依固定 ID 查找分支。
  if (!node) throw new ScriptError(`找不到場景節點：${nodeId}`) // 明確報告內容錯誤。
  return node // 回傳已存在的節點。
}

export function validateScenario(scenario: Scenario): string[] { // 供內容匯入與契約測試使用。
  const errors: string[] = [] // 收集全部可修正問題。
  const ids = new Set(scenario.nodes.map(node => node.id)) // 偵測重複及缺失 ID。
  if (ids.size !== scenario.nodes.length) errors.push('節點 ID 重複') // 避免分支查找不確定。
  if (!ids.has(scenario.startNodeId)) errors.push('起始節點不存在') // 起點必須能到達。
  for (const node of scenario.nodes) { // 逐一查核分支與終點。
    if (!node.ending && node.choices.length === 0) errors.push(`${node.id} 沒有選項或結尾`) // 防止死路。
    for (const choice of node.choices) if (!ids.has(choice.nextNodeId)) errors.push(`${choice.id} 指向缺失節點`) // 防止空連結。
  }
  const reachesEnd = (nodeId: string, seen = new Set<string>()): boolean => { // 檢查每條路徑是否可達回顧。
    if (seen.has(nodeId)) return false // 沒有出口的循環不算可完成。
    const node = scenario.nodes.find(item => item.id === nodeId) // 缺失節點已由上方回報。
    if (!node) return false // 避免壞引用造成例外。
    if (node.ending) return true // 有回顧的節點才算完成。
    return node.choices.length > 0 && node.choices.every(choice => reachesEnd(choice.nextNodeId, new Set([...seen, nodeId]))) // 每個可選分支都需有結尾。
  }
  if (ids.has(scenario.startNodeId) && !reachesEnd(scenario.startNodeId)) errors.push('有分支無法到達結尾') // 防止玩家進入無法完成的路徑。
  return errors // 呼叫者可顯示所有錯誤。
}

export function startSession(personaId: string, scenario: Scenario, now = new Date()): SimulationSession { // 建立隔離的示範 session。
  const errors = validateScenario(scenario) // 在開始前先驗資料。
  if (errors.length) throw new ScriptError(errors.join('；')) // 不展示壞資料。
  return { id: crypto.randomUUID(), schemaVersion: '1.0', usageScope: 'demo', channel: 'script', personaId, scenarioId: scenario.id, nodeId: scenario.startNodeId, path: [scenario.startNodeId], turns: [...getNode(scenario, scenario.startNodeId).lines], status: 'active', startedAt: now.toISOString() } // 每次開始產生新 ID 與獨立回合陣列。
}

export function choose(session: SimulationSession, scenario: Scenario, choiceId: string, now = new Date()): SimulationSession { // 選項產生不可變的新狀態。
  if (session.status !== 'active' || session.scenarioId !== scenario.id) throw new ScriptError('這段對話已結束或場景已切換') // 阻止跨場景串線。
  const node = getNode(scenario, session.nodeId) // 僅使用目前節點的選項。
  const choice: DialogueChoice | undefined = node.choices.find(item => item.id === choiceId) // 防止任意跳節點。
  if (!choice) throw new ScriptError('這個選項已不可使用') // 讓 UI 能保留與返回。
  const next = getNode(scenario, choice.nextNodeId) // 目的地必須存在。
  const visitor: DialogueTurn = { id: `${session.id}:${choice.id}`, speaker: 'visitor', text: choice.label, evidence: 'generated_scene', sourceRefs: [] } // 使用者選擇也只屬演練。
  return { ...session, nodeId: next.id, path: [...session.path, next.id], turns: [...session.turns, visitor, ...choice.reply, ...next.lines], status: next.ending ? 'ended' : 'active', endedAt: next.ending ? now.toISOString() : undefined } // 只有結尾節點結束。
}

export function exportSession(session: SimulationSession): string { // 匯出只供使用者手動下載。
  return JSON.stringify({ ...session, exportKind: 'life-world-simulation', importToRealExperience: false }, null, 2) // 防止與正式紀錄混淆。
}

export async function requestLive(adapter: LiveAdapter | undefined, request: LiveRequest): Promise<LiveResponse> { // 即時回覆的唯一可替換入口。
  if (!adapter) throw new AdapterNotConfiguredError() // 無端點時提供明確退路。
  if (request.signal.aborted) throw new DOMException('已取消', 'AbortError') // 取消後不呼叫服務。
  const response = await adapter.reply(request) // 由宿主注入 adapter。
  if (request.signal.aborted) throw new DOMException('已取消', 'AbortError') // 捨棄取消後的遲到回覆。
  if (!response.turn.id || !response.turn.text) throw new ScriptError('即時回覆格式不完整') // 不顯示無效訊息。
  return response // 回傳來源與候選對話。
}
