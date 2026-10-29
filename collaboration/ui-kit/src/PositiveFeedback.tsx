import { poseArt } from './LumiPoses' // 一般確認使用無殼 confirmed 姿勢，與首次孵化區分。
export const nourishmentArt = new URL('../assets/shared-art/additions-20261029/originals/lw-effects-nourishment-v2.png', import.meta.url).href // 獨立透明養分圖層，原稿不改像素。
export function PositiveFeedback({ confirmedReceiptId }: { confirmedReceiptId?: string }) { // 只有宿主的已確認回執才能顯示養分；fixture 必須明示。
  if (!confirmedReceiptId) return null // 無回執不提前出現 Lumi，也不自行確認目標。
  return <div className="positive-feedback" role="img" aria-label="確認後養分到達，Lumi 陪伴努力；純視覺回饋"><img className="nourishment-layer" src={nourishmentArt} alt="" /><img className="feedback-lumi" src={poseArt.confirmed} alt="" /></div> // 光效在後、無殼 Lumi 在前；不含任何帳本操作。
} // Quiet 與減少動效皆為無聲定格，不依賴動畫完成。
