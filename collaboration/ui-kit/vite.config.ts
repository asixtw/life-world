import { defineConfig } from 'vite' // 設定獨立展示的建置與測試入口。
import react from '@vitejs/plugin-react' // 啟用 React 的 Vite 編譯。

export default defineConfig({ plugins: [react()], test: { environment: 'node' } }) // 不連接正式服務或資料庫。
