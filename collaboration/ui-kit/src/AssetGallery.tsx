import { nourishmentArt } from './PositiveFeedback' // 與回饋畫面使用同一原稿。
import { useState } from 'react' // 圖像狀態可點選，不以空路徑占位。
import { Button, Card } from './components' // 保持同一元件語意。

const imageRoot = '../assets/shared-art/lifeworld-fullkit-shared-art/' // 兩份經 SHA256 核對的 ZIP 合併後路徑。
const images = [ // 十一張實際交付插畫與顯示輸出。
  { id: 'lw-egg-rest-v1', title: '靜置蛋', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-rest-v1@512.png', import.meta.url).href }, // 靜置狀態。
  { id: 'lw-egg-softglow-v1', title: '微光蛋', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-softglow-v1@512.png', import.meta.url).href }, // 微光狀態。
  { id: 'lw-egg-initialcrack-v1', title: '初裂蛋', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-initialcrack-v1@512.png', import.meta.url).href }, // 初裂狀態。
  { id: 'lw-egg-deepcrack-v1', title: '深裂蛋', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-egg-deepcrack-v1@512.png', import.meta.url).href }, // 深裂狀態。
  { id: 'lw-lumi-companion-v1', title: '陪伴 Lumi', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-lumi-companion-v1@512.png', import.meta.url).href }, // 常駐陪伴者。
  { id: 'lw-lumi-quiet-v1', title: '安靜 Lumi', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-lumi-quiet-v1@512.png', import.meta.url).href }, // Quiet 狀態。
  { id: 'lw-app-icon-v1', title: 'App 代表圖', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-app-icon-v1@512.png', import.meta.url).href }, // 方形主圖。
  { id: 'lw-share-illustration-v1', title: '分享圖', src: new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-share-illustration-v1@600x315.png', import.meta.url).href }, // 寬版分享圖。
  { id: 'lw-egg-shellsplit-v2', title: '舊合併分離蛋殼', src: new URL('../assets/shared-art/additions-20261029/originals/lw-egg-shellsplit-v2.png', import.meta.url).href }, // 舊候選供對照，不冒稱新左右殼。
  { id: 'lw-lumi-completion-v2', title: '舊 Lumi 完成定格', src: new URL('../assets/shared-art/additions-20261029/originals/lw-lumi-completion-v2.png', import.meta.url).href }, // 舊圖供比對；一般回饋已改無殼。
  { id: 'lw-effects-nourishment-v2', title: '獨立養分光效', src: nourishmentArt }, // 透明合成圖層。
] // 所有路徑由 Vite 靜態納入建置。

export function AssetGallery() { // 查看尺寸、裁切與 Quiet 對照的可操作展示。
  const [selected, setSelected] = useState(images[0]) // 初始顯示靜置蛋。
  return <Card title="共用插畫與圖示"><p>以下十一項含實際 PNG 原稿；新三圖以原生 1254 畫布等比顯示，世界房間候選已在獨立頁接入。</p><div className="action-row">{images.map(item => <Button key={item.id} kind={selected.id === item.id ? 'primary' : 'secondary'} onClick={() => setSelected(item)}>{item.title}</Button>)}</div><div className="asset-preview"><img src={selected.src} alt={`${selected.title}：Life World 共用美術展示`} /><div><strong>{selected.title}</strong><p className="fine-print">資產 ID：{selected.id}</p><p className="fine-print">原稿、版本、來源與檔案雜湊記於共用資產清單。</p></div></div><div className="asset-crops" aria-label="圖示裁切預覽"><div><img src={new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-app-icon-v1@192.png', import.meta.url).href} alt="App 圖示 192 像素" /><span>192 px</span></div><div><img className="crop-circle" src={new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-app-icon-v1@48.png', import.meta.url).href} alt="App 圖示圓形裁切 48 像素" /><span>48 px · 圓形</span></div><div><img className="crop-rounded" src={new URL('../assets/shared-art/lifeworld-fullkit-shared-art/exports/lw-app-icon-v1@180.png', import.meta.url).href} alt="App 圖示圓角裁切 180 像素" /><span>180 px · 圓角</span></div></div><p className="fine-print">資產包根目錄：{imageRoot}；人物肖像及三封面已於劇場接入。</p></Card> // 可切換實際檔案，不標記缺圖為已交。
}
