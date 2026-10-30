import { Card } from './components' // 圖示對照與其他 P0 元件一致。
import { Icon, iconNames } from './Icons' // 32 個原生向量與四尺寸。
import './icon-gallery.css' // 對照表樣式限本區。

export function IconGallery() { // 供 Boyi／Jerry 直接核對尺寸與圖示 ID。
  return <Card title="v1.1 SVG 操作圖示"><p>32 個可編輯向量；24×24 viewBox、currentColor。純圖示按鈕需由宿主提供可讀標籤。</p><div className="icon-gallery">{iconNames.map(name => <div className="icon-gallery__item" key={name}><strong>{name}</strong><div>{([16, 20, 24, 32] as const).map(size => <span key={size} title={`${name} ${size}px`}><Icon name={name} size={size} /></span>)}</div></div>)}</div></Card> // 四種輸出大小共用同一條向量路徑。
} // 圖示不取代可操作元件。
