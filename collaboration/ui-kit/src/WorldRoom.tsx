import { useState } from 'react' // 圖像失敗需有可讀替代。
import { StatusMessage } from './components' // 不把破圖視作完成狀態。
import './world-room.css' // 房間層級與錨點只限世界場景。
import { poseArt } from './LumiPoses' // 常駐者在 Quiet 切換獨立姿勢。

const dayWide = new URL('../assets/derived-v1_1/world/room-day@1280x960.png', import.meta.url).href // 橫向顯示版從 1448×1086 等比縮小。
const quietWide = new URL('../assets/derived-v1_1/world/room-quiet@1280x960.png', import.meta.url).href // Quiet 同尺寸顯示版。
const dayTall = new URL('../assets/derived-v1_1/world/room-day@768x1024.png', import.meta.url).href // 獨立直向原稿等比縮小。
const quietTall = new URL('../assets/derived-v1_1/world/room-quiet@768x1024.png', import.meta.url).href // 直向 Quiet 非橫圖拉伸。
const furniture = new URL('../assets/world-candidates-20261029/layers/furniture-cabinet.png', import.meta.url).href // 透明家具獨立層。
const plant = new URL('../assets/world-candidates-20261029/layers/foreground-plant.png', import.meta.url).href // 前景植物獨立層。
const shadow = new URL('../assets/world-candidates-20261029/layers/lumi-contact-shadow.png', import.meta.url).href // 角色接地陰影獨立層。
export function WorldRoom({ quiet, showLumi = true }: { quiet: boolean; showLumi?: boolean }) { // 同一場景切換日間與 Quiet，不把文字烤入背景。
  const [failed, setFailed] = useState<string[]>([]) // 任一圖層失敗時顯示可讀替代。
  const report = (id: string) => setFailed(previous => previous.includes(id) ? previous : [...previous, id]) // 每層只記一次錯誤。
  return <div className="world-room-wrap"><div className={`world-room ${quiet ? 'world-room--quiet' : ''}`} role="img" aria-label={quiet ? 'Quiet 房間與 Lumi 示範場景' : '日間房間與 Lumi 示範場景'}><picture className="world-room__base"><source media="(max-width: 600px)" srcSet={quiet ? quietTall : dayTall} /><img src={quiet ? quietWide : dayWide} alt="" onError={() => report('room-base')} /></picture><img className="world-room__furniture" src={furniture} alt="" onError={() => report('furniture')} /><img className="world-room__shadow" src={shadow} alt="" onError={() => report('shadow')} />{showLumi && <img className="world-room__lumi" src={quiet ? poseArt.quiet : poseArt.idle} alt="" onError={() => report('lumi')} />}<img className="world-room__foreground" src={plant} alt="" onError={() => report('foreground')} /></div>{failed.length > 0 && <StatusMessage tone="warning">房間圖層載入失敗：{failed.join('、')}。仍可使用下方文字操作。</StatusMessage>}</div> // 失敗不阻斷文字或目標卡。
} // 1920 檔為原稿放大衍生，不宣稱原生高解析；Boyi／Jerry 仍須審查。
