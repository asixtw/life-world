import { describe, expect, it } from 'vitest' // 驗證內容引用與用途邊界。
import type { AssetRef, Persona, Scenario } from '../src/contracts' // 測試使用最小合成資料。
import { validateCatalog } from '../src/validate' // 不使用正式人物資料。

const avatar: AssetRef = { id: 'avatar-test', path: 'assets/test.png', alt: '虛構測試圖', scope: 'demo', format: 'png', width: 256, height: 256 } // 只測 ID 關聯。
const persona: Persona = { id: 'p-test', packId: 'test', name: '測試', kind: 'fictional', version: '1', summary: '虛構', motivation: '測試', perspective: '測試', voice: '測試', boundary: '測試', knowledgeCutoff: '不適用', sourceRefs: [], fieldEvidence: [], avatarId: avatar.id, usageScope: 'demo' } // 不冒充真實資料。
const scenario: Scenario = { id: 's-test', packId: 'test', title: '測試', description: '虛構', knowledgeCutoff: '不適用', sourceRefs: [], startNodeId: 'end', usageScope: 'demo', nodes: [{ id: 'end', lines: [], choices: [], ending: '完成' }] } // 可達結尾。

describe('catalog references', () => { // 找到空路徑與錯誤引用。
  it('accepts a linked demo fixture', () => { expect(validateCatalog([persona], [scenario], [], [avatar])).toEqual([]) }) // 合格 fixture 應通過。
  it('reports missing avatar and source', () => { const errors = validateCatalog([{ ...persona, avatarId: 'missing', sourceRefs: ['fake'] }], [scenario], [], [avatar]); expect(errors).toContain('p-test 頭像資產不存在'); expect(errors).toContain('p-test 引用缺失來源 fake') }) // 不把缺圖或假引用當完成。
  it('rejects duplicate persona id', () => { expect(validateCatalog([persona, persona], [scenario], [], [avatar])).toContain('人物 ID 重複') }) // 穩定 ID 必須唯一。
})
