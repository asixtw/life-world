import { describe, expect, it } from 'vitest' // 新世界候選使用真檔案及 hash，不以路徑占位。
// @ts-expect-error 此套件不增裝 Node 型別；Vitest 在 Node 執行此唯讀驗檔。
import { readFileSync } from 'node:fs' // 僅讀本套件資產。
// @ts-expect-error 此套件不增裝 Node 型別；Vitest 在 Node 執行此唯讀驗檔。
import { createHash } from 'node:crypto' // 核對 ZIP 來源清單雜湊。
// @ts-expect-error 此套件不增裝 Node 型別；Vitest 在 Node 執行此唯讀驗檔。
import { fileURLToPath } from 'node:url' // 資產路徑固定在 ui-kit。
import manifest from '../assets/manifest.json' // 候選與規格尺寸差異如實保存。

describe('v1.1 世界原稿與分層', () => { // 不把 CSS 顯示當點陣輸出。
  it('七張圖的 bytes、尺寸、透明模式和 SHA256 都與清單一致', () => { // 防止破圖或誤用候選。
    expect(manifest.worldCandidates.files).toHaveLength(7) // 四背景加三透明層。
    for (const item of manifest.worldCandidates.files) { const bytes = readFileSync(fileURLToPath(new URL(`../assets/${item.path}`, import.meta.url))); expect(bytes.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a'); expect(bytes.readUInt32BE(16)).toBe(item.width); expect(bytes.readUInt32BE(20)).toBe(item.height); expect(bytes[25]).toBe(item.mode === 'RGBA' ? 6 : 2); expect(createHash('sha256').update(bytes).digest('hex')).toBe(item.sha256) } // 實際檔案逐一核對。
  }) // 透明 PNG 與 RGB 背景分流。
  it('指定像素已衍生，但 1920 不是原生高解析', () => { expect(manifest.worldCandidates.targetOriginalSizeMet).toBe(false); expect(manifest.worldCandidates.targetDisplaySizesProduced).toBe(true); expect(manifest.worldCandidates.target1920IsDerivedUpscale).toBe(true); expect(manifest.worldCandidates.status).toContain('review_pending') }) // 不將放大圖冒充新原稿。
}) // Boyi／Jerry 視覺審查另列。
