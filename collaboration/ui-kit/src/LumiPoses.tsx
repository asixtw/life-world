import { Card } from './components' // 姿勢審查仍使用隔離的 UI 元件。
import './lumi-poses.css' // 不污染正式 App 樣式。

export const poseArt = { // 六姿勢均是真正透明 PNG 原稿，未假稱具備完整顯示版。
  idle: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-idle-candidate-v1.png', import.meta.url).href,
  quiet: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-quiet-candidate-v1.png', import.meta.url).href,
  welcome: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-welcome-candidate-v1.png', import.meta.url).href,
  listening: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-listening-candidate-v1.png', import.meta.url).href,
  confirmed: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-confirmed-candidate-v1.png', import.meta.url).href,
  celebrate: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-lumi-celebrate-candidate-v1.png', import.meta.url).href,
} as const

export const shellArt = { // 左右殼是兩個獨立檔案，可分別裝配與替換。
  left: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-shell-left-candidate-v1.png', import.meta.url).href,
  right: new URL('../assets/lumi-poses-candidate-20261029/originals/lw-shell-right-candidate-v1.png', import.meta.url).href,
} as const

const poseLabels = { idle: '常駐', quiet: 'Quiet', welcome: '歡迎', listening: '傾聽', confirmed: '確認', celebrate: '慶祝' } as const // 標籤不烤入圖片。

export function LumiPoseGallery() { // 固定檢視六個可用姿勢，供尺度及亮邊審查。
  return <Card title="Lumi 六姿勢候選"><p>六張 1254×1254 透明原稿；兩張沿用、四張新生成。錨點與共同尺度尚待 Boyi／Jerry 校準，512／256／128 顯示版未齊。</p><div className="lumi-poses">{Object.entries(poseArt).map(([id, src]) => <figure key={id}><img src={src} alt={`Lumi ${poseLabels[id as keyof typeof poseArt]} 姿勢`} /><figcaption>{poseLabels[id as keyof typeof poseArt]}</figcaption></figure>)}</div></Card>
} // 候選展示不等於產品驗收。
