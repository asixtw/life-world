import { Card } from './components' // 姿勢審查仍使用隔離的 UI 元件。
import './lumi-poses.css' // 不污染正式 App 樣式。

export const poseArt = { // 六姿勢載入同錨點 512 顯示版；1254 原稿另存且不改 bytes。
  idle: new URL('../assets/derived-v1_1/poses/idle@512.png', import.meta.url).href,
  quiet: new URL('../assets/derived-v1_1/poses/quiet@512.png', import.meta.url).href,
  welcome: new URL('../assets/derived-v1_1/poses/welcome@512.png', import.meta.url).href,
  listening: new URL('../assets/derived-v1_1/poses/listening@512.png', import.meta.url).href,
  confirmed: new URL('../assets/derived-v1_1/poses/confirmed@512.png', import.meta.url).href,
  celebrate: new URL('../assets/derived-v1_1/poses/celebrate@512.png', import.meta.url).href,
} as const

export const shellArt = { // 左右殼是兩個共畫布透明衍生檔，仍可分別裝配。
  left: new URL('../assets/derived-v1_1/shells/shell-left@512.png', import.meta.url).href,
  right: new URL('../assets/derived-v1_1/shells/shell-right@512.png', import.meta.url).href,
} as const

export const hatchShadowArt = new URL('../assets/derived-v1_1/effects/contact-shadow@512.png', import.meta.url).href // 接地陰影保留獨立透明層。

const poseLabels = { idle: '常駐', quiet: 'Quiet', welcome: '歡迎', listening: '傾聽', confirmed: '確認', celebrate: '慶祝' } as const // 標籤不烤入圖片。

export function LumiPoseGallery() { // 固定檢視六個顯示版，供共同錨點及亮邊審查。
  return <Card title="Lumi 六姿勢候選"><p>六張原稿保持原樣；512／256／128 顯示版以透明畫布等比對齊落地點。共同錨點為程式候選，細部輪廓與殼裂口仍待 Boyi／Jerry 審查。</p><div className="lumi-poses">{Object.entries(poseArt).map(([id, src]) => <figure key={id}><img src={src} alt={`Lumi ${poseLabels[id as keyof typeof poseArt]} 姿勢`} /><figcaption>{poseLabels[id as keyof typeof poseArt]}</figcaption></figure>)}</div></Card>
} // 候選展示不等於產品驗收。
