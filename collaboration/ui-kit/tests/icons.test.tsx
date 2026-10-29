import { describe, expect, it } from 'vitest' // SVG 合約不以截圖作唯一驗證。
import { renderToStaticMarkup } from 'react-dom/server' // 檢查實際輸出屬性。
import { Icon, iconNames } from '../src/Icons' // 所有必要操作圖示集中核對。

describe('v1.1 操作 SVG', () => { // 真向量筆畫支援四個尺寸。
  it('交齊 32 個獨立 ID 且沒有空圖示', () => { // 清單數量及每個 path 均需有效。
    expect(iconNames).toHaveLength(32) // 規格的世界至聲音關共 32 項。
    expect(new Set(iconNames).size).toBe(iconNames.length) // ID 不重複。
    for (const name of iconNames) expect(renderToStaticMarkup(<Icon name={name} />)).toMatch(/<(path|rect|circle)/) // 不允許空殼 SVG。
  }) // 由原生 SVG 組成，不放 PNG。
  it('保留 24 viewBox、currentColor 和可讀標籤', () => { // 宿主可用於四尺寸與無文字按鈕。
    for (const size of [16, 20, 24, 32] as const) { const html = renderToStaticMarkup(<Icon name="confirm" size={size} aria-label="確認" />); expect(html).toContain(`width="${size}"`); expect(html).toContain('viewBox="0 0 24 24"'); expect(html).toContain('stroke="currentColor"'); expect(html).toContain('aria-label="確認"') } // 尺寸不改向量基準。
  }) // 無標籤時 Icon 自身標為裝飾，由文字按鈕提供名稱。
}) // 語意與可操作按鈕仍由宿主審查。
