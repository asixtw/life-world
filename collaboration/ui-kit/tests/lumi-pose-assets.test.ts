import { describe, expect, it } from 'vitest' // 檢查新原稿是真實透明檔案。
// @ts-expect-error Node 型別不另增專案依賴。
import { readFileSync } from 'node:fs'
// @ts-expect-error Node 型別不另增專案依賴。
import { createHash } from 'node:crypto'
// @ts-expect-error Node 型別不另增專案依賴。
import { fileURLToPath } from 'node:url'
import source from '../assets/lumi-poses-candidate-20261029/manifest.json' // ZIP 中實際雜湊與 bbox。
import kit from '../assets/manifest.json' // 上層交付狀態不得過早升格。

describe('v1.1 Lumi 姿勢及兩片殼', () => {
  it('八張 1254 方形 RGBA 原稿的 bytes 與雜湊一致', () => {
    expect(source.assets).toHaveLength(8)
    for (const item of source.assets) {
      const bytes = readFileSync(fileURLToPath(new URL(`../assets/lumi-poses-candidate-20261029/${item.path}`, import.meta.url)))
      expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
      expect([bytes.readUInt32BE(16), bytes.readUInt32BE(20), bytes[25]]).toEqual([1254, 1254, 6])
      expect(bytes.length).toBe(item.size_bytes)
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256)
    }
  })
  it('明示缺顯示版與錨點驗收', () => {
    expect(kit.lumiPoseCandidates.poseIds).toHaveLength(6)
    expect(kit.lumiPoseCandidates.shellIds).toEqual(['shell-left', 'shell-right'])
    expect(kit.lumiPoseCandidates.targetDisplaySizesProduced).toBe(false)
    expect(kit.lumiPoseCandidates.uniformAnchorVerified).toBe(false)
  })
})
