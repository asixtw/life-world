import type { ReactNode, SVGProps } from 'react' // 圖示保留原生 SVG 屬性與語意。

const shapes = { // 所有操作圖示以可編輯向量筆畫繪製，不包點陣圖片。
  world: <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></>, // 世界：經緯球。
  goal: <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/></>, // 目標：靶心。
  record: <><rect x="5" y="3" width="14" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></>, // 紀錄：筆記。
  relation: <><circle cx="8" cy="8" r="3"/><circle cx="17" cy="15" r="3"/><path d="m10.5 9.5 4 3.5M3 20c0-3 2-5 5-5h3"/></>, // 交會：人物連線。
  back: <path d="m14 5-7 7 7 7M7 12h13"/>, // 返回箭頭。
  forward: <path d="m10 5 7 7-7 7M17 12H4"/>, // 前進箭頭。
  close: <path d="M5 5 19 19M19 5 5 19"/>, // 關閉叉。
  add: <path d="M12 4v16M4 12h16"/>, // 新增十字。
  search: <><circle cx="10" cy="10" r="6"/><path d="m15 15 5 5"/></>, // 搜尋鏡。
  settings: <><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></>, // 設定齒軸。
  star: <path d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3-5.7-3-5.7 3 1.1-6.3-4.6-4.5 6.4-.9z"/>, // 未選星標。
  starred: <path fill="currentColor" d="m12 3 2.8 5.8 6.4.9-4.6 4.5 1.1 6.3-5.7-3-5.7 3 1.1-6.3-4.6-4.5 6.4-.9z"/>, // 已選星標。
  microphone: <><rect x="9" y="3" width="6" height="12" rx="3"/><path d="M6 11a6 6 0 0 0 12 0M12 17v4M8 21h8"/></>, // 麥克風。
  stop: <rect x="5" y="5" width="14" height="14" rx="2"/>, // 停止。
  play: <path d="m7 4 13 8-13 8z"/>, // 播放。
  pause: <><path d="M7 5v14M17 5v14"/></>, // 暫停。
  upload: <><path d="M12 16V3m0 0-5 5m5-5 5 5M4 16v4h16v-4"/></>, // 上傳。
  image: <><rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="8" cy="9" r="1"/><path d="m4 17 5-5 3 3 3-4 5 6"/></>, // 圖片。
  camera: <><path d="M3 7h4l2-3h6l2 3h4v13H3z"/><circle cx="12" cy="13" r="4"/></>, // 相機。
  businessCard: <><rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="8" cy="11" r="2"/><path d="M5 16c0-2 6-2 6 0M14 10h5M14 14h5"/></>, // 名片。
  audioFile: <><path d="M6 2h8l4 4v16H6zM14 2v5h4"/><path d="M10 16a2 2 0 1 0 2 2v-6l4-1"/></>, // 音檔。
  retry: <><path d="M20 11a8 8 0 1 1-2-5M20 4v6h-6"/></>, // 重試。
  remove: <><path d="M4 7h16M9 4h6M7 7l1 14h8l1-14M10 11v6M14 11v6"/></>, // 移除。
  source: <><path d="M5 3h11l3 3v15H5zM16 3v4h3M8 11h8M8 15h8"/></>, // 來源文件。
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M7 3v4M17 3v4M3 10h18M7 14h3M14 14h3"/></>, // 日曆。
  confirm: <path d="m4 12 5 5L20 6"/>, // 確認勾。
  warning: <><path d="m12 3 10 18H2zM12 9v5M12 18h.01"/></>, // 警示三角。
  copy: <><rect x="8" y="8" width="12" height="13" rx="2"/><path d="M16 8V5a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h2"/></>, // 複製。
  draft: <><path d="M4 3h12l4 4v14H4zM16 3v5h4M8 12h8M8 16h5"/></>, // 草稿。
  quiet: <path d="M18 3A9 9 0 1 0 21 18 9 9 0 0 1 18 3z"/>, // 安靜月亮。
  soundOn: <><path d="M3 9h4l5-4v14l-5-4H3zM16 8c3 2 3 6 0 8M18 5c5 4 5 10 0 14"/></>, // 聲音開。
  soundOff: <><path d="M3 9h4l5-4v14l-5-4H3zM16 9l5 6M21 9l-5 6"/></>, // 聲音關。
} satisfies Record<string, ReactNode> // 保留每個規格 ID 的獨立向量。
export type IconName = keyof typeof shapes // 使用型別避免拼錯圖示 ID。
export const iconNames = Object.keys(shapes) as IconName[] // Gallery 可核對完整清單。
export function Icon({ name, size = 24, ...props }: SVGProps<SVGSVGElement> & { name: IconName; size?: 16 | 20 | 24 | 32 }) { // 尺寸、顏色及 aria 由宿主控制。
  return <svg {...props} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden={props['aria-label'] ? undefined : true}>{shapes[name]}</svg> // 無文字按鈕必須由宿主給 aria-label。
} // 這些是真可編輯 SVG path，不是包 PNG。
