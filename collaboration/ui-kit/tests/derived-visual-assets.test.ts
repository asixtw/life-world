import { describe, expect, it } from 'vitest' // 衍生輸出與原稿 bytes 分開核對。
// @ts-expect-error 本套件不增裝 Node 型別；Vitest 在 Node 執行。
import { readFileSync } from 'node:fs'
// @ts-expect-error 本套件不增裝 Node 型別；Vitest 在 Node 執行。
import { createHash } from 'node:crypto'
// @ts-expect-error 本套件不增裝 Node 型別；Vitest 在 Node 執行。
import { fileURLToPath } from 'node:url'
import derived from '../assets/derived-v1_1/manifest.json'

describe('v1.1 原稿衍生 PNG', () => {
  it('40 個真檔的尺寸、RGBA/RGB 與 SHA 均吻合；透明層不變成底色', () => {
    expect(derived.files).toHaveLength(40)
    for (const item of derived.files) {
      const bytes = readFileSync(fileURLToPath(new URL(`../assets/${item.path}`, import.meta.url)))
      const source = readFileSync(fileURLToPath(new URL(`../assets/${item.sourcePath}`, import.meta.url)))
      expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a')
      expect([bytes.readUInt32BE(16), bytes.readUInt32BE(20), bytes[25]]).toEqual([item.width, item.height, item.mode === 'RGBA' ? 6 : 2])
      expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256)
      expect(createHash('sha256').update(source).digest('hex')).toBe(item.sourceSha256)
      if (item.mode === 'RGBA') expect(item.trueTransparentBackground).toBe(true)
    }
  })
  it('六姿勢 512/256/128 共落地點、背景按橫直比例輸出', () => {
    for (const size of [512, 256, 128]) {
      const poses = derived.files.filter(item => item.path.includes('/poses/') && item.path.endsWith(`@${size}.png`))
      expect(poses).toHaveLength(6)
      expect(poses.map(item => item.anchorPx)).toEqual(Array(6).fill(null).map(() => [Math.round(627 * size / 1254), Math.round(1030 * size / 1254)]))
      expect(Math.max(...poses.map(item => item.visibleBbox![3])) - Math.min(...poses.map(item => item.visibleBbox![3]))).toBeLessThanOrEqual(2)
    }
    for (const suffix of ['1920x1440', '1280x960', '768x1024']) expect(derived.files.filter(item => item.path.includes('/world/') && item.path.includes(suffix))).toHaveLength(2)
    expect(derived.world1920IsDerivedUpscale).toBe(true)
    expect(derived.pairedShellClosureVerified).toBe(false)
  })
})
