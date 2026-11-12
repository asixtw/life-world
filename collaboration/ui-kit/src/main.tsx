import { ArtReview } from './ArtReview' // 固定審查入口只渲染實際元件，避免互動流程。
import React from 'react' // 啟用 React 嚴格模式。
import { createRoot } from 'react-dom/client' // 掛載獨立展示。
import App from './App' // 引入 gallery 主頁。
import './design-tokens.css'
import './styles.css' // 保留既有元件結構。
import './design-language.css' // v1 語意 Token 適配。

createRoot(document.getElementById('root')!).render(<React.StrictMode><div className="lw-kit">{new URLSearchParams(window.location.search).has('art-review') ? <ArtReview /> : <App />}</div></React.StrictMode>) // 獨立展示以局部 CSS scope 包住，不污染正式 App。
