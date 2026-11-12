import { useState } from 'react'

/** 主站與 React Main Web 使用同一靜態元件庫；無產品 API 或會員資料。 */
export function DesignLanguageGallery({quiet=false,reducedMotion=false}:{quiet?:boolean;reducedMotion?:boolean}={}) {
  const [failed,setFailed]=useState(false)
  const src=`/design-language-v1/design-lab/index.html?quiet=${quiet?'1':'0'}&reduced=${reducedMotion?'1':'0'}`
  return <section className="design-language-page"><p className="fine-print">統一設計語言 v1.0 · 本機候選 · 新角色與蛋待目視驗收</p><iframe className="design-language-frame" title="Life World 統一設計語言元件庫" src={src} onError={()=>setFailed(true)} />{failed&&<p role="alert">元件庫暫時無法載入。<a href={src}>獨立開啟元件庫</a></p>}</section>
}
