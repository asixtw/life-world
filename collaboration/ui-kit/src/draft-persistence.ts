export type DraftRecord = { ownerId: string; draftId: string; revision: number; text: string; materials: string[] } // owner、draft 與版本共同界定草稿。
export interface DraftRepository { load(ownerId: string, draftId: string): Promise<DraftRecord | null>; save(draft: DraftRecord, expectedRevision: number): Promise<DraftRecord> } // 儲存介面不預設正式 API。
export class VersionConflictError extends Error { constructor() { super('version-conflict'); this.name = 'VersionConflictError' } } // 過期頁籤需讓使用者核對。
const identity = (ownerId: string, draftId: string) => `${ownerId}\u0000${draftId}` // 同名草稿跨 owner 不共用鍵。
const copy = (draft: DraftRecord): DraftRecord => ({ ...draft, materials: [...draft.materials] }) // 避免外部改動已存資料。

export class MemoryDraftRepository implements DraftRepository { // 單元測試與無 IndexedDB 環境的明示 mock。
  private records = new Map<string, DraftRecord>() // 只在此實例記憶體存活。
  async load(ownerId: string, draftId: string) { const draft = this.records.get(identity(ownerId, draftId)); return draft ? copy(draft) : null } // owner 鍵必須匹配。
  async save(draft: DraftRecord, expectedRevision: number) { const key = identity(draft.ownerId, draft.draftId); const prior = this.records.get(key); if ((prior?.revision ?? 0) !== expectedRevision) throw new VersionConflictError(); const next = copy({ ...draft, revision: expectedRevision + 1 }); this.records.set(key, next); return copy(next) } // 原子版本檢查模型。
} // 不宣稱持久化。

export class IndexedDbDraftRepository implements DraftRepository { // 真瀏覽器 IndexedDB，僅屬隔離 demo 命名空間。
  constructor(private factory: IDBFactory = indexedDB, private databaseName = 'lifeworld-ui-kit-demo-v11') {} // 正式 App 不使用此 DB。
  private open(): Promise<IDBDatabase> { return new Promise((resolve, reject) => { const request = this.factory.open(this.databaseName, 1); request.onupgradeneeded = () => { if (!request.result.objectStoreNames.contains('drafts')) request.result.createObjectStore('drafts', { keyPath: 'key' }) }; request.onsuccess = () => resolve(request.result); request.onerror = () => reject(request.error ?? new Error('indexeddb-open-failed')) }) } // 無權限或配額失敗明確拒絕。
  async load(ownerId: string, draftId: string): Promise<DraftRecord | null> { const db = await this.open(); return new Promise((resolve, reject) => { const tx = db.transaction('drafts', 'readonly'); const request = tx.objectStore('drafts').get(identity(ownerId, draftId)); let result: DraftRecord | null = null; request.onsuccess = () => { if (request.result) { const { key: _key, ...record } = request.result as DraftRecord & { key: string }; result = copy(record) } }; tx.oncomplete = () => { db.close(); resolve(result) }; tx.onerror = () => { db.close(); reject(tx.error ?? new Error('indexeddb-read-failed')) } }) } // 只回傳指定 owner 的指定 draft。
  async save(draft: DraftRecord, expectedRevision: number): Promise<DraftRecord> { const db = await this.open(); return new Promise((resolve, reject) => { const tx = db.transaction('drafts', 'readwrite'); const store = tx.objectStore('drafts'); const key = identity(draft.ownerId, draft.draftId); const request = store.get(key); let failure: Error | null = null; let next: DraftRecord | null = null; request.onsuccess = () => { const current = request.result as (DraftRecord & { key: string }) | undefined; if ((current?.revision ?? 0) !== expectedRevision) { failure = new VersionConflictError(); tx.abort(); return } next = copy({ ...draft, revision: expectedRevision + 1 }); store.put({ key, ...next }) }; tx.oncomplete = () => { db.close(); if (next) resolve(copy(next)); else reject(new Error('indexeddb-save-empty')) }; tx.onabort = () => { db.close(); reject(failure ?? tx.error ?? new Error('indexeddb-save-failed')) }; tx.onerror = () => { /* onabort 統一回報，避免重複通知。 */ } }) } // 同一 readwrite 交易中比對版本再寫入。
} // 重整後仍可回讀，瀏覽器實測另列。

export type LinkResult = { draft: DraftRecord; linkError: string | null } // 文字已存與素材連結結果分開。
export async function saveTextThenLink(repository: DraftRepository, draft: DraftRecord, expectedRevision: number, materialId: string, link: (idempotencyKey: string) => Promise<void>): Promise<LinkResult> { // 文字成功後才嘗試連結素材。
  const saved = await repository.save(draft, expectedRevision) // 文字先持久化，失敗則交 UI 保留本機草稿。
  return retryMaterialLink(repository, saved, materialId, link) // 連結失敗仍回同一 draftId。
} // 不造第二筆正式經歷。
export async function retryMaterialLink(repository: DraftRepository, draft: DraftRecord, materialId: string, link: (idempotencyKey: string) => Promise<void>): Promise<LinkResult> { // 重試使用固定鍵，避免重複連結。
  if (draft.materials.includes(materialId)) return { draft, linkError: null } // 已連結不再送出。
  try { await link(`${draft.ownerId}:${draft.draftId}:${materialId}`); const updated = await repository.save({ ...draft, materials: [...draft.materials, materialId] }, draft.revision); return { draft: updated, linkError: null } } catch (error) { return { draft, linkError: error instanceof Error ? error.message : 'link-failed' } } // 失敗仍保留已存文字、版本與原 draftId。
} // 真實素材服務的冪等鍵與權限由 Jerry 審查。
