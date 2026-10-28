import React from 'react' // 啟用 React 嚴格模式。
import { createRoot } from 'react-dom/client' // 掛載獨立展示。
import App from './App' // 引入 gallery 主頁。
import './styles.css' // 套用現有暖白與薄荷色系的設計 token。

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>) // 不掛載正式 App 容器。
