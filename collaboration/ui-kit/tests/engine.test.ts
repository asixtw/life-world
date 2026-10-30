import { describe, expect, it } from 'vitest' // 使用實際斷言驗證腳本與隔離契約。
import type { Scenario } from '../src/contracts' // 測試資料符合公開型別。
import { AdapterNotConfiguredError, choose, exportSession, requestLive, startSession, validateScenario } from '../src/engine' // 覆蓋主要邊界。

const scenario: Scenario = { id: 'fixture-one', packId: 'fixture', title: '測試', description: '純合成', knowledgeCutoff: '不適用', sourceRefs: [], startNodeId: 'start', usageScope: 'demo', nodes: [{ id: 'start', lines: [], choices: [{ id: 'yes', label: '繼續', reply: [], nextNodeId: 'end' }] }, { id: 'end', lines: [], choices: [], ending: '完成' }] } // 最小可達結尾場景。

describe('script contract', () => { // 正常、異常與隔離情境。
  it('reaches ending without mutating original session', () => { const first = startSession('p1', scenario); const second = choose(first, scenario, 'yes'); expect(first.status).toBe('active'); expect(second.status).toBe('ended'); expect(second.path).toEqual(['start', 'end']); expect(second.turns[0].evidence).toBe('generated_scene') }) // 確認回顧路徑與不可變性。
  it('rejects scene mismatch and missing links', () => { const first = startSession('p1', scenario); expect(() => choose(first, { ...scenario, id: 'other' }, 'yes')).toThrow(); expect(validateScenario({ ...scenario, nodes: [scenario.nodes[0]] })).toContain('yes 指向缺失節點') }) // 不得串錯場景。
  it('rejects a branch that loops without an ending', () => { const looping = { ...scenario, nodes: [{ ...scenario.nodes[0], choices: [{ id: 'loop', label: '重複', reply: [], nextNodeId: 'start' }] }, scenario.nodes[1]] }; expect(validateScenario(looping)).toContain('有分支無法到達結尾') }) // 每條路徑要能結束與回顧。
  it('exports explicit simulation metadata', () => { const result = JSON.parse(exportSession(startSession('p1', scenario))); expect(result.usageScope).toBe('demo'); expect(result.importToRealExperience).toBe(false); expect(result.exportKind).toBe('life-world-simulation') }) // 不自動匯入正式經歷。
  it('reports unconfigured live mode', async () => { await expect(requestLive(undefined, { sessionId: 's', personaId: 'p', scenarioId: 'x', turns: [], userText: 'hi', signal: new AbortController().signal })).rejects.toBeInstanceOf(AdapterNotConfiguredError) }) // 無端點不可假裝成功。
})
