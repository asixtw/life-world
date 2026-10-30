import manifest from '../assets/manifest.json' // 正規化資產清單記錄 ID、路徑與來源。

const images: Record<string, string> = { // 只打包十八張畫面顯示圖，不將原稿當前端資源重複載入。
  ...import.meta.glob('../assets/persona-art/lifeworld-pack-art-three-kingdoms/assets/display/*.png', { eager: true, query: '?url', import: 'default' }), // 三國展示尺寸。
  ...import.meta.glob('../assets/persona-art/lifeworld-pack-art-international-dialogue/exports/*.png', { eager: true, query: '?url', import: 'default' }), // 國際職務展示尺寸。
  ...import.meta.glob('../assets/persona-art/lifeworld-pack-art-philosophy/assets/display/*.png', { eager: true, query: '?url', import: 'default' }), // 哲學展示尺寸。
} // Vite 產物中的 URL 與 manifest ID 對應。

export function PersonaArt({ id, className = '' }: { id: string; className?: string }) { // 只依固定資產 ID 載圖。
  const asset = manifest.personaArt.find(item => item.id === id) // 找到來源與替代文字。
  if (!asset) return <span role="status" className="fine-print">缺少人物圖像：{id}</span> // 未交付時明示缺件。
  const src = images[`../assets/${asset.displayPath}`] // 使用 Vite 打包後的實際路徑。
  if (!src) return <span role="status" className="fine-print">圖像路徑尚未接入：{id}</span> // 不用空圖占位。
  return <img className={className} src={src} alt={asset.alt} loading="lazy" /> // alt 明示虛構或藝術詮釋。
}
