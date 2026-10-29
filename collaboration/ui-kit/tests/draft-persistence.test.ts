import { describe, expect, it } from 'vitest' // 草稿儲存先寫失敗與隔離契約。
import { MemoryDraftRepository, VersionConflictError, saveTextThenLink, retryMaterialLink } from '../src/draft-persistence' // IndexedDB 與記憶體共用同一資料契約。

describe('v1.1 owner 草稿隔離', () => { // 此測試不接正式帳號或資料庫。
  it('相同 draftId 不得跨 owner 讀取', async () => { // owner 是鍵的一部分。
    const store = new MemoryDraftRepository() // 用純記憶體驗儲存契約。
    await store.save({ ownerId: 'demo-a', draftId: 'draft-1', revision: 0, text: 'A 的內容', materials: [] }, 0) // A 的草稿。
    expect(await store.load('demo-b', 'draft-1')).toBeNull() // B 不得看到 A。
    expect((await store.load('demo-a', 'draft-1'))?.text).toBe('A 的內容') // A 可回讀。
  }) // 正式認證仍須宿主提供 owner。
  it('舊 revision 保存被拒，既有內容不遭覆寫', async () => { // 版本衝突是可回復錯誤。
    const store = new MemoryDraftRepository() // 模擬兩個頁籤。
    const first = await store.save({ ownerId: 'demo-a', draftId: 'draft-1', revision: 0, text: '初稿', materials: [] }, 0) // revision 1。
    await store.save({ ...first, text: '另一頁更新' }, 1) // revision 2。
    await expect(store.save({ ...first, text: '過期頁面' }, 1)).rejects.toBeInstanceOf(VersionConflictError) // 舊頁不得覆寫。
    expect((await store.load('demo-a', 'draft-1'))?.text).toBe('另一頁更新') // 保留較新版本。
  }) // UI 須提供重新核對退路。
  it('文字已存但素材連結失敗，重試沿用同一草稿', async () => { // 部分成功不能清空或創造新草稿。
    const store = new MemoryDraftRepository() // 只驗本地資料流程。
    const failed = await saveTextThenLink(store, { ownerId: 'demo-a', draftId: 'draft-1', revision: 0, text: '已寫文字', materials: [] }, 0, 'material-1', async () => { throw new Error('link-failed') }) // 模擬連結失敗。
    expect(failed).toMatchObject({ linkError: 'link-failed', draft: { draftId: 'draft-1', revision: 1, text: '已寫文字', materials: [] } }) // 文字保存成功仍可見。
    const retried = await retryMaterialLink(store, failed.draft, 'material-1', async () => {}) // 同一 draftId 重試。
    expect(retried).toMatchObject({ draft: { draftId: 'draft-1', revision: 2, text: '已寫文字', materials: ['material-1'] }, linkError: null }) // 無新草稿或重複連結。
  }) // 正式上傳與連結 API 待 Jerry 審查。
}) // 純函式測試與真 IndexedDB 瀏覽器測試分開。
