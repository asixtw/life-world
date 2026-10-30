import { useState } from 'react' // 單一圖層載入失敗時保留可讀退路。
import { poseArt } from './LumiPoses' // 一般確認使用無殼 confirmed 姿勢，與首次孵化區分。
export const nourishmentArt = new URL('../assets/derived-v1_1/effects/nourishment@512.png', import.meta.url).href // 獨立透明養分顯示版，原稿不改像素。
export function PositiveFeedback({ confirmedReceiptId }: { confirmedReceiptId?: string }) { // 只有宿主的已確認回執才能顯示養分；fixture 必須明示。
  const [failed, setFailed] = useState<string[]>([])
  if (!confirmedReceiptId) return null // 無回執不提前出現 Lumi，也不自行確認目標。
  return <div className="positive-feedback" role="img" aria-label="確認後養分到達，Lumi 陪伴努力；純視覺回饋">{!failed.includes(nourishmentArt) && <img className="nourishment-layer" src={nourishmentArt} alt="" onError={() => setFailed(previous => [...previous, nourishmentArt])} />}{!failed.includes(poseArt.confirmed) && <img className="feedback-lumi" src={poseArt.confirmed} alt="" onError={() => setFailed(previous => [...previous, poseArt.confirmed])} />}{failed.length > 0 && <span className="hatch-art__fallback">回饋圖片載入失敗；確認紀錄仍可閱讀。</span>}</div> // 光效在後、無殼 Lumi 在前；不含任何帳本操作。
} // Quiet 與減少動效皆為無聲定格，不依賴動畫完成。
