import { describe, expect, it } from 'vitest' // 十種輸入與狀態的靜態語意契約。
import { renderToStaticMarkup } from 'react-dom/server'
import { createElement } from 'react'
import { InputControl } from '../src/InputGallery'
import type { InputKind, InputState } from '../src/InputGallery'

const kinds: InputKind[] = ['text', 'textarea', 'password', 'number', 'datetime-local', 'search', 'select', 'checkbox', 'radio', 'switch']
describe('v1.1 受控輸入矩陣', () => {
  it('十種輸入均有可讀標籤與原生控制', () => {
    for (const kind of kinds) {
      const html = renderToStaticMarkup(createElement(InputControl, { kind, state: 'empty', value: kind === 'checkbox' || kind === 'switch' ? false : '', onChange: () => {} }))
      expect(html).toMatch(/<input|<textarea|<select/)
      expect(html).toMatch(/<label|<legend/)
    }
  })
  it('錯誤、停用、載入狀態提供可讀語意', () => {
    const render = (state: InputState) => renderToStaticMarkup(createElement(InputControl, { kind: 'text', state, value: '草稿', onChange: () => {} }))
    expect(render('error')).toContain('aria-invalid="true"')
    expect(render('error')).toContain('role="alert"')
    expect(render('disabled')).toContain('disabled=""')
    expect(render('loading')).toContain('aria-busy="true"')
    expect(render('loading')).toContain('readOnly=""')
    expect(render('help')).toContain('此欄內容僅保留在本頁')
  })
})
