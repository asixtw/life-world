import { describe,it,expect } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
// @ts-expect-error 沿用套件既有測試方式；Vitest 在 Node 執行，不新增 Node 型別依賴。
import { readFileSync,existsSync } from 'node:fs'
import { DesignLanguageGallery } from '../src/DesignLanguage'
import { Button } from '../src/components'

describe('統一設計語言可攜式輸出',()=>{
  it('提供共用元件庫入口，不導入私人 API',()=>{
    const html=renderToStaticMarkup(<DesignLanguageGallery />)
    expect(html).toContain('/design-language-v1/design-lab/index.html')
    expect(html).toContain('title="Life World 統一設計語言元件庫"')
    expect(html).not.toContain('/api/')
  })
  it('所有候選都有實際透明顯示檔與來源狀態',()=>{
    const root=new URL('../public/design-language-v1/',import.meta.url)
    const manifest=JSON.parse(readFileSync(new URL('art/design-v1/manifest.json',root),'utf8'))
    expect(manifest.assets).toHaveLength(20)
    for(const asset of manifest.assets){
      expect(existsSync(new URL(asset.web_path,root))).toBe(true)
      expect(asset.approval_status).toBe('candidate_owner_visual_review_pending')
      expect(asset.anchor).toEqual([256,448])
    }
  })
  it('載入按鈕保留原始標籤與 aria-busy',()=>{
    const html=renderToStaticMarkup(<Button loading>保存這份較長的示例</Button>)
    expect(html).toContain('保存這份較長的示例')
    expect(html).toContain('aria-busy="true"')
    expect(html).toContain('button__loading')
  })
})
