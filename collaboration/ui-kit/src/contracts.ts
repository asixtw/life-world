// 本檔只定義示範資料與整合邊界，不寫正式人物或獎勵。
export type EvidenceKind = 'source_fact' | 'literary_account' | 'interpretation' | 'design_assumption' | 'generated_scene' | 'unknown' // 區分可追溯資料與創作。
export type UsageScope = 'demo' | 'product_candidate' // 讓素材用途在型別層清楚分流。
export interface SourceRef { id: string; title: string; creator: string; date: string | null; locator: string; url?: string; evidence: EvidenceKind; reviewed: boolean; verificationStatus?: 'machine_checked_locator' | 'unverified' } // 機器定位與人工核對分欄。
export interface AssetRef { id: string; path: string; alt: string; scope: UsageScope; format: string; width: number; height: number } // 圖像 ID 需能解析到實檔。
export interface Persona { id: string; packId: string; name: string; kind: 'fictional' | 'historical' | 'role'; version: string; summary: string; motivation: string; perspective: string; voice: string; boundary: string; knowledgeCutoff: string; sourceRefs: string[]; fieldEvidence: { field: 'summary' | 'motivation' | 'perspective' | 'voice' | 'boundary' | 'knowledgeCutoff'; evidence: EvidenceKind; sourceRefs: string[] }[]; avatarId: string; usageScope: 'demo' } // 人物每項設定明示詮釋或設計假設。
export interface DialogueTurn { id: string; speaker: 'visitor' | 'persona' | 'narrator'; speakerId?: string; text: string; evidence: EvidenceKind; sourceRefs: string[] } // speakerId 將角色發話綁到穩定人物 ID。
export interface DialogueChoice { id: string; label: string; reply: DialogueTurn[]; nextNodeId: string } // 分支只能指向同場景的節點。
export interface DialogueNode { id: string; lines: DialogueTurn[]; choices: DialogueChoice[]; ending?: string } // 結尾節點以 ending 顯示回顧。
export interface Scenario { id: string; packId: string; title: string; description: string; knowledgeCutoff: string; sourceRefs: string[]; startNodeId: string; nodes: DialogueNode[]; usageScope: 'demo' } // 場景資料由獨立內容包供給。
export interface SimulationSession { id: string; schemaVersion: '1.0'; usageScope: 'demo'; channel: 'script' | 'live'; personaId: string; scenarioId: string; nodeId: string; path: string[]; turns: DialogueTurn[]; status: 'active' | 'ended' | 'cancelled' | 'error'; startedAt: string; endedAt?: string } // 匯出內容沒有正式資料欄位。
export interface LiveRequest { sessionId: string; personaId: string; scenarioId: string; turns: DialogueTurn[]; userText: string; signal: AbortSignal } // 即時服務須由宿主提供，不暴露金鑰。
export interface LiveResponse { turn: DialogueTurn; sourceRefs: SourceRef[] } // 後端回應須附來源，前端仍標候選。
export interface LiveAdapter { reply(request: LiveRequest): Promise<LiveResponse> } // Jerry 可替換的供應商中立介面。
export type HatchStage = 'idle' | 'glow' | 'crack' | 'deepcrack' | 'open' | 'complete' // 孵化畫面的固定狀態 ID。
export interface HatchEvent { type: 'start' | 'advance' | 'skip' | 'cancel' | 'replay' | 'complete'; stage: HatchStage; receiptId?: string } // 回呼只報展示事件，不改帳本。
export interface TransitionEvent { type: 'start' | 'complete' | 'cancel'; transitionId: string } // 視覺轉場的完成與取消可由宿主觀察。
