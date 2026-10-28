'use strict'; // 及早拒絕未宣告變數與模糊指派
window.ConnectionsUI = (() => { // 封裝故事探索、來源與人工配對
  let c, owner = null, source = null, sourceRequest = 0, lastExplore = 'people', lastCollection = 'people?view=cards'; // 共用帳號與當前來源狀態
  const trail = [], positions = new Map(), reviewEdits = new Map(), discardedReviews = new Set(); // 區分保留與使用者明確捨棄的核對修改
  const h = value => c.esc(value); // 使用者文字一律跳脫後才呈現
  const query = () => new URLSearchParams(location.hash.split('?')[1] || ''); // 以 URL 保存目前故事與焦點
  const button = (action, label, attrs = '', style = 'secondary') => `<button type="button" class="${style}" data-cx="${action}" ${attrs}>${label}</button>`; // 將交會事件與舊人物按鈕隔離
  const dialog = () => document.querySelector('#source-dialog'); // 來源使用獨立原生對話框
  function initialize(context) { c = context; } // 注入原 App 的 API、路由及狀態
  function entries(form) { return [...form.elements].filter(n=>n.name&&!['submit','button','file','reset'].includes(n.type)&&(!['checkbox','radio'].includes(n.type)||n.checked)).flatMap(n=>n.multiple?[...n.selectedOptions].map(o=>[n.name,o.value]):[[n.name,n.value]]); } // 切頁鎖住控制項後仍能保留值，不使用會排除 disabled 的 FormData
  function ensureOwner() { // 帳號切換時不保留前一人的來源與路徑
    const next = c.state.me?.owner_id || null; // 不依人物名稱辨識帳號
    if (next !== owner) { owner = next; source = null; sourceRequest++; trail.length = 0; positions.clear(); reviewEdits.clear(); discardedReviews.clear(); lastExplore = 'people'; lastCollection = 'people?view=cards'; if(dialog()?.open) dialog().close(); } // 清除私人畫面快取
  } // 完成帳號隔離
  function tabs(active) { // 交會取代星圖，收藏冊保留原用途
    return `<nav class="view-switch" role="tablist" aria-label="人物檢視方式"><a role="tab" aria-label="交會" aria-selected="${active==='explore'}" href="#${h(lastExplore)}">✧ 交會</a><a role="tab" aria-label="收藏冊" aria-selected="${active==='cards'}" href="#${h(lastCollection)}">▦ 收藏冊</a></nav>`; // 不再顯示星圖分頁
  } // 完成共享切換入口
  function worldMini() { // 首頁改為故事探索入口，不顯示星圖
    return `<section id="world-relationships" class="card space-top"><div class="section-title"><h2>旅途中遇見的人</h2>${c.link('people','進入交會 →','text-button')}</div><p>沿著一段真實經歷，重新發現故事中的交集。</p><p class="small muted">人物參與與提及分開呈現，每條線索都能回到來源。</p>${c.link('people?view=cards','開啟人物收藏冊','secondary')}</section>`; // 首頁摘要不曝光人物姓名
  } // 完成世界入口
  function rawForEditor(root) { // 取得實際原文，避免把摘要當證據
    return document.querySelector('#raw-text')?.value ?? (root.dataset.mode==='manage'?source?.raw_text:c.state.draft?.raw_text) ?? ''; // 管理及核對都引用原始紀錄
  } // 完成原文讀取
  function spans(raw, name) { // 尋找每一處 Unicode 字元範圍
    const text = [...raw], needle = [...name], result = []; // JS 依 Unicode 字元計數，與 Python 一致
    if (!needle.length) return result; // 空名字沒有來源位置
    for(let i=0;i<=text.length-needle.length;i++) if(text.slice(i,i+needle.length).join('')===name) result.push({start:i,end:i+needle.length,label:`第 ${result.length+1} 處 · ${text.slice(Math.max(0,i-8),i+needle.length+8).join('')}`}); // 同名不同位置提供脈絡
    return result; // 不以第一個同名位置默默代替全部
  } // 完成來源定位
  function mentionRow(m = {}) { // 原文人名及位置保留，身分可稍後核對
    return `<div class="story-mention-editor"><div class="field"><label>原文提及名字<input name="mention_name" maxlength="100" value="${h(m.name||'')}" placeholder="原文中出現的稱呼"></label></div><div class="field"><label>提及位置<select name="mention_start" data-start="${m.start??''}"></select></label></div><input type="hidden" name="mention_person" value="${h(m.person_id||'')}">${m.person_id?'<span class="small muted">保留先前人工配對；可於來源核對更正。</span>':''}${button('remove-mention','移除此處提及','','text-button')}</div>`; // 保留原文片段，不從名字自動配對
  } // 完成提及輸入列
  function editor(story = null, mode = 'record') { // 草稿與更正共用人物整理元件
    if(c.state.me?.status==='guest') return '<p class="small muted">建立帳號後，可選填整理人物參與與提及；無人物經歷仍可正常保存。</p>'; // 不要求所有人都建立人物
    const selected = new Map((story?.participants||[]).map(p=>[p.person_id,p.interacted])); // 保留使用者的明確選擇
    return `<section class="story-editor" data-story-editor data-mode="${mode}"><label class="check-line"><input id="include-story" name="include_story" type="checkbox" ${story?'checked':''}>整理這段故事的人物，加入交會（選填）</label><div class="story-editor-body" ${story?'':'hidden'}><div class="field"><label for="story-title">故事標題（選填）</label><input id="story-title" name="story_title" maxlength="160" value="${h(story?.title||'')}"></div><fieldset><legend>這次實際參與的人</legend><input class="participant-filter" placeholder="篩選人物稱呼" aria-label="篩選參與人物"><div class="participant-options">${c.state.world.people.map(p=>`<div class="participant-option" data-name="${h(p.name)}"><label class="check-line"><input type="checkbox" name="story_participant" value="${h(p.id)}" ${selected.has(p.id)?'checked':''}>${h(p.name)} <small>${h(p.roles.join('、'))}</small></label><label class="check-line small"><input type="checkbox" name="story_interacted" value="${h(p.id)}" ${selected.get(p.id)?'checked':''} ${selected.has(p.id)?'':'disabled'}>有直接互動</label></div>`).join('')||'<p class="small muted">尚未有人物，可先用上方新增人物入口。</p>'}</div><p class="small muted">同場不代表彼此熟識，也不自動計入直接互動或見面。</p></fieldset><fieldset><legend>另外提到的人（選填）</legend><div class="story-mention-rows">${(story?.mentions||[]).map(mentionRow).join('')}</div>${button('add-mention','新增提及')}<p class="small muted">先保存原文稱呼；同名人物需人工配對，提及不等於參與。</p></fieldset>${mode==='review'?`<div class="field"><label for="story-interaction-kind">直接互動類型</label><select id="story-interaction-kind" name="story_interaction_type"><option value="unknown">未分類</option><option value="in_person">實體見面</option><option value="call">電話</option><option value="message">訊息</option><option value="other">其他</option></select></div>`:''}${mode!=='record'?'<label class="check-line"><input type="checkbox" id="story-reviewed" name="story_reviewed">我已核對參與者、直接互動及提及原文，知道配對不代表出席。</label>':''}</div></section>`; // 候選與正式接受在最後核對時分開
  } // 完成共用整理元件
  function updateSpans(row) { // 名字或原文更動後重新核對位置
    const input=row.querySelector('[name=mention_name]'), select=row.querySelector('[name=mention_start]'), root=row.closest('[data-story-editor]'); // 取得該處線索
    const previous=select.value||select.dataset.start, found=spans(rawForEditor(root),input.value); // 保留舊位置但重新驗證原文
    select.innerHTML=found.length?found.map(s=>`<option value="${s.start}" ${String(s.start)===String(previous)?'selected':''}>${h(s.label)}</option>`).join(''):'<option value="">原文找不到此名字，請修正</option>'; // 不容許失效片段直接保存
    delete select.dataset.start; // 之後以使用者選取位置為準
  } // 完成提及位置更新
  function collectEditor(form, validate=true) { // 只取得使用者指定的角色，不推論名字
    const root=form.querySelector('[data-story-editor]'); if(!root || !root.querySelector('#include-story').checked) return null; // 未選擇整理時維持舊 API
    const participants=[...root.querySelectorAll('[name=story_participant]:checked')].map(n=>({person_id:n.value,interacted:!![...root.querySelectorAll('[name=story_interacted]:checked')].find(x=>x.value===n.value)})); // 參與與互動獨立保存
    const mentions=[...root.querySelectorAll('.story-mention-editor')].map(row=>{updateSpans(row); const name=row.querySelector('[name=mention_name]').value, value=row.querySelector('[name=mention_start]').value; if(validate && (!name||value==='')) throw new Error('提及名字必須出現在原文，請選取正確位置。'); return {name,start:value===''?-1:Number(value),end:value===''?-1:Number(value)+[...name].length,person_id:row.querySelector('[name=mention_person]').value||null};}); // 逐處保留配對身分與精確來源
    return {title:root.querySelector('#story-title').value,participants,mentions}; // 不混入積分、進度或 owner
  } // 完成人工資料收集
  function hydrateEditors() { document.querySelectorAll('.story-mention-editor').forEach(updateSpans); const old=document.querySelector('#interaction-type'), input=document.querySelector('#include-story'); if(old&&input) old.closest('.field').hidden=input.checked; } // 使用新故事時隱藏重複的舊互動類型，保留同次事件入口
  function remember(route, y) { // 保存探索位置與核對修改，避免返回時重設
    ensureOwner(); // 先清除跨帳號暫存
    if(route.startsWith('people')) { positions.set(route,{y,open:[...document.querySelectorAll('#connections-explorer details[open]')].map(n=>n.dataset.keep)}); if(new URLSearchParams(route.split('?')[1]||'').get('view')==='cards') lastCollection=route; else lastExplore=route; } // 兩種入口分別保留條件
    if(route.startsWith('review/') && c.state.draft?.id && !discardedReviews.has(c.state.draft.id) && document.querySelector('#review-form')) { const form=document.querySelector('#review-form'); reviewEdits.set(c.state.draft.id,{values:entries(form),story:collectEditor(form,false),dirty:c.state.dirty||reviewEdits.get(c.state.draft.id)?.dirty||false}); } // 返回原文不代表摘要已正式保存
  } // 完成路由暫存
  function restore(route) { // 恢復展開與核對內容，不將暫存冒充伺服器保存
    const saved=positions.get(route); if(saved) { document.querySelectorAll('#connections-explorer details').forEach(n=>n.open=saved.open.includes(n.dataset.keep)); window.scrollTo(0,saved.y); } // 回到相同探索閱讀位置
    const edit=route.startsWith('review/')?reviewEdits.get(c.state.draft?.id):null, form=document.querySelector('#review-form'); // 只還原同一草稿
    if(edit && form) { if(edit.story) { const root=form.querySelector('[data-story-editor]'); root.outerHTML=editor(edit.story,'review'); } for(const [name,value] of edit.values) { const nodes=[...form.elements].filter(n=>n.name===name); for(const n of nodes) { if(n.type==='checkbox') n.checked=edit.values.some(([key,v])=>key===name&&v===n.value); else if(n.type!=='file'&&!name.startsWith('mention_')) n.value=value; } } c.state.dirty=edit.dirty; } // 還原明確輸入，不把載入當成修改
    hydrateEditors(); // 完成精確來源位置選項
    if(form && route.startsWith('review/')) discardedReviews.delete(c.state.draft?.id); // 重新開始核對後可再追蹤新的修改
  } // 完成返回恢復
  function clearReview(id) { reviewEdits.delete(id); discardedReviews.add(id); } // 確認或明確捨棄後不能被舊 DOM 重新寫回
  function markEditorDirty(root) { if(root.closest('#source-dialog')) source.editDirty=true; else c.state.dirty=true; } // 來源更正與主頁草稿的未保存狀態分開
  function snapshotEditor() { const form=document.querySelector('#record-form,#review-form'); return form?{story:collectEditor(form,false),mode:form.id==='record-form'?'record':'review'}:null; } // 升級／新增人物前保留動態列
  function restoreEditor(saved) { if(saved?.story) { const root=document.querySelector('[data-story-editor]'); if(root) root.outerHTML=editor(saved.story,saved.mode); hydrateEditors(); } } // 輪換帳號或新增人物後重建已輸入內容
  function routeFor(changes={}) { const q=query(); q.delete('view'); for(const [key,value] of Object.entries(changes)) { if(value===null||value==='') q.delete(key); else q.set(key,value); } return 'people'+(q.size?'?'+q:''); } // 僅修改指定故事條件
  function go(route, push=true) { // 內部探索保持方向與可返回路徑
    if(push && c.state.route!==route) { remember(c.state.route,window.scrollY); trail.push(c.state.route); if(trail.length>100) trail.shift(); } // 限制本次頁面歷史量
    if(closeSource()) c.navigate(route); // 未保存更正先處理，不能直接離開
  } // 完成探索跳轉
  function personTile(p, current=false) { return `<button type="button" class="connection-person ${current?'current':''}" data-cx="focus" data-id="${h(p.id)}"><span class="person-avatar category-${h(p.category)}">${h([...p.name][0])}</span><strong>${h(p.name)}</strong><small>${current?'正在探索':'沿著此人繼續 ↗'}</small></button>`; } // 人物圍繞故事，不畫未確認關係線
  async function renderContent() { // 以真實焦點查詢取代星圖
    ensureOwner(); const q=query(), ticket=c.state.renderGeneration, focus=q.get('focus'), sort=q.get('order')||'recent', offset=Number(q.get('offset')||0); // 保留 URL 的探索位置
    const params=new URLSearchParams({sort,limit:'8',offset:String(Math.max(0,offset))}); if(focus) params.set('person_id',focus); // 每次只讀一頁相關故事
    const [list,legacy]=await Promise.all([c.api('/connections?'+params),c.api('/connections?involvement=legacy&limit=5')]); // 查詢已審閱故事與舊資料待核對入口
    let s=q.get('story')?await c.api('/connections/stories/'+encodeURIComponent(q.get('story'))):list.items[0]; // 以事件為畫面焦點
    if(ticket!==c.state.renderGeneration) return ''; // 拒絕舊非同步回應覆蓋目前頁面
    const p=c.state.world.people.find(p=>p.id===focus), others=list.items.filter(x=>x.id!==s?.id), via=q.get('via'); // 依同一份人物資料延伸故事
    const sourceButton=s?button('source','查看完整來源',`data-id="${h(s.id)}"`,'primary'):''; // 來源入口固定可見
    const header=`${c.heading('沿著故事，重新遇見。','從真實經歷出發，看見人與故事之間的交集。')}${tabs('explore')}<div class="connection-toolbar">${trail.length?button('back','上一步'):''}${focus?button('reset','從最近故事開始'):''}<label>故事順序<select id="connection-sort"><option value="recent" ${sort==='recent'?'selected':''}>最近的經歷</option><option value="oldest" ${sort==='oldest'?'selected':''}>較早的經歷</option></select></label></div>${p?`<p class="small">正在探索：${h(p.name)} · ${c.link('person/'+p.id+'?return='+encodeURIComponent(location.hash.slice(1)),'查看人物完整頁','text-button')}</p>`:''}${via?'<div class="connection-origin">從提及來源而來；不代表參與原故事。</div>':''}`; // 說明探索路徑，不宣稱人物私人關係
    const pending=legacy.total?`<section class="card space-top"><h2>等待核對的舊經歷</h2><p class="small muted">舊人物關聯尚未確認參與或提及，不直接進入探索。</p>${legacy.items.map(x=>`<div class="list-item"><span>${h(x.title)}</span>${button('manage','核對這段故事',`data-id="${h(x.id)}"`)}</div>`).join('')}</section>`:''; // 不遺失舊內容或假定已參與
    if(!s) return `<div id="connections-explorer">${header}${c.empty(p?'還沒有這位人物實際參與的故事。可以查看人物卡的已核對提及，或返回上一段。':'從一段真實經歷開始，人物與故事會慢慢連起來。',c.link('record','記錄一段經歷','primary'))}${pending}</div>`; // 無下一段也有可理解退路
    const participants=s.participants.map(x=>personTile(x,x.id===focus)), title=focus?`${p?.name||'此人物'}的其他故事`:'接著探索另一段故事'; // 不載入全部人物網絡
    return `<div id="connections-explorer">${header}<article id="connection-story" class="connection-story"><div class="connection-scene"><span class="tag">${h(c.time(s.occurred_at))}</span><span class="tag">使用者已審閱</span><div class="connection-scene-people">${s.participants.slice(0,2).map(x=>`<span class="person-avatar category-${h(x.category)}">${h([...x.name][0])}</span>`).join('')}</div><div class="memory-card"><span aria-hidden="true">✳</span><h2>${h(s.title)}</h2><small>${s.participants.length} 位實際參與者 · ${s.mentions.length} 處提及</small></div></div><div class="connection-copy"><div class="eyebrow">THIS MOMENT · 故事片刻</div><p class="record-content">${h(s.summary)}</p>${sourceButton}</div></article><section class="space-top"><h2>實際參與人物</h2><div class="connection-people">${participants.slice(0,3).join('')}</div>${participants.length>3?`<details data-keep="participants"><summary>還有 ${participants.length-3} 位</summary><div class="connection-people">${participants.slice(3).join('')}</div></details>`:''}<p class="small muted">同場不代表彼此熟識；只有明確核對的直接互動才計入互動統計。</p>${s.participants.length?'':c.empty('這段故事沒有記錄共同參與者。')}</section><section class="space-top"><h2>活動中提及的人物</h2>${s.mentions.map(m=>`<button type="button" class="mention-row" data-cx="mention-source" data-id="${h(s.id)}" data-mention="${h(m.id)}" aria-label="查看${h(m.name)}的提及來源"><span class="mention-symbol">@</span><span><strong>${h(m.name)}</strong><small>${m.status==='matched'?'已人工配對':m.status==='rejected'?'已拒絕配對':'待核對人物'} · 未記錄出席</small></span><span>↗</span></button>`).join('')||'<p class="small muted">這段經歷沒有另外提及其他人物。</p>'}</section><section class="space-top"><h2>${h(title)}</h2>${others.map(x=>`<button type="button" class="connection-story-row card" data-cx="story" data-id="${h(x.id)}"><span><strong>${h(x.title)}</strong><small>${h(c.time(x.occurred_at))} · ${x.participants.length} 位參與</small></span><span>→</span></button>`).join('')||'<p class="small muted">目前沒有其他參與故事，可沿著另一位參與者繼續。</p>'}<div class="button-row">${offset?button('page','上一頁',`data-offset="${Math.max(0,offset-8)}"`):''}${offset+list.items.length<list.total?button('page','更多故事',`data-offset="${offset+8}"`):''}</div></section><div class="callout space-top">連結來自使用者已審閱的紀錄，不代表第三人獨立證實，也不代表人物之間有私人關係。</div>${pending}</div>`; // 分層呈現當前故事與下一段方向
  } // 完成聚焦探索畫面
  async function render() { try { return await renderContent(); } catch(error) { return `<div id="connections-explorer">${c.heading('交會暫時無法載入。','已保存的經歷仍在，請重試或回到最近故事。')}${tabs('explore')}<div class="callout" role="alert">${h(error.message)}</div><div class="button-row space-top">${button('refresh','重新載入交會')}${button('reset','從最近故事開始')}${c.link('history','查看已保存經歷','text-button')}</div></div>`; } } // 清單／舊連結失敗也有明確退路，不停在鎖住的舊畫面
  function quote(raw, mention) { const chars=[...raw]; return mention?h(chars.slice(Math.max(0,mention.start-50),mention.start).join(''))+'<mark>'+h(chars.slice(mention.start,mention.end).join(''))+'</mark>'+h(chars.slice(mention.end,mention.end+50).join('')):h(raw); } // 依精確位置高亮，不替換全部同名文字
  function sourceHtml(s, selected) { // 在來源中保持參與、提及及信任界線
    const m=s.mentions.find(m=>m.id===selected); // 定位這次點擊的人名位置
    return `<h2 id="source-heading" tabindex="-1">${h(s.title)}</h2><p class="small muted">${h(c.time(s.occurred_at))} · ${s.reviewed?'使用者已審閱':'舊版關聯待核對'}</p>${s.available?'':'<div class="callout">已撤回交會展示；原始經歷與獎勵仍保留。</div>'}<div class="tags"><span class="tag">原始文字</span><span class="tag">私人紀錄</span></div><h3 class="space-top">事件摘要</h3><p>${h(s.summary)}</p><h3>原文片段${m?' · 已定位提及處':''}</h3><div class="source-quote">${quote(s.raw_text,m)}</div><details data-keep="raw"><summary>查看完整原始紀錄</summary><div class="raw-source">${h(s.raw_text)}</div></details><h3 class="space-top">實際參與人物</h3><p>${s.participants.map(p=>h(p.name)+(p.interacted?'（有直接互動）':'（同場）')).join('、')||'尚未確認共同參與者'}</p><h3>活動中提及的人物</h3>${s.mentions.map(x=>`<section class="source-mention ${x.id===m?.id?'selected':''}"><strong>${h(x.name)}</strong><span class="tag">${x.status==='matched'?'已配對':x.status==='rejected'?'已拒絕配對':'待核對人物'}</span><p class="small">${h(x.status==='matched'?x.person_name+' · 未記錄出席':'尚未確認原文所指身分')}</p><div class="button-row">${button('match','核對人物',`data-mention="${h(x.id)}"`)}${x.status==='matched'?button('follow-mention','探索'+h(x.person_name)+'的故事',`data-id="${h(x.person_id)}"`):''}</div></section>`).join('')||'<p class="small muted">沒有另外提及人物。</p>'}<div class="callout space-top">使用者審閱不等於第三人證實；人物配對只確認身分，不代表參與原故事或存在私人關係。</div><div class="button-row space-top">${button('edit-source','核對／更正人物')}${button('availability',s.available?'撤回交會展示':'恢復交會展示',`data-available="${s.available?'false':'true'}"`)}</div>${s.history?.length?`<details class="space-top"><summary>人工更正歷史（${s.history.length}）</summary>${s.history.map(x=>`<p class="small">${h(c.time(x.created_at))} · ${h({match:'人物身分核對',people:'人物角色更正',availability:'交會展示狀態'}[x.action]||x.action)}</p>`).join('')}</details>`:''}`; // 不把內部資料格式直接顯示給產品使用者
  } // 完成來源抽屜
  async function openSource(id, mention=null, manage=false) { // 來源每次向後端重新驗證
    ensureOwner(); const ticket=++sourceRequest, box=dialog(); source={id,selected:mention,manage}; // 丟棄過期非同步來源
    document.querySelector('#source-error').textContent=''; document.querySelector('#source-content').innerHTML='<h2 id="source-heading">正在讀取來源…</h2><p role="status">請稍候，正在確認可存取的原始紀錄。</p>'; if(!box.open) box.showModal(); // 重試前清除舊錯誤，保留可理解的載入回饋
    try { const result=await c.api('/connections/stories/'+encodeURIComponent(id)+(manage?'?manage=true':'')); if(ticket!==sourceRequest||!box.open) return; source={...result,selected:mention,manage}; document.querySelector('#source-content').innerHTML=sourceHtml(source,mention); box.scrollTop=0; document.querySelector('#source-heading').focus(); } // 成功後才顯示正式資料
    catch(error) { if(ticket===sourceRequest&&box.open) document.querySelector('#source-content').innerHTML=`<h2>來源暫時無法開啟</h2><p role="alert">${h(error.message)}</p>${button('retry-source','重試來源')}`; } // 網路／權限失敗仍可重試或關閉
  } // 完成安全來源讀取
  function closeSource(force=false) { if(dialog()?.open&&source?.editDirty&&!force) { document.querySelector('#source-error').innerHTML='還有人物整理尚未保存。請繼續編輯、確認保存，或明確捨棄。 '+button('discard-source-edit','捨棄更正並關閉','','text-button'); return false; } if(force&&source) source.editDirty=false; sourceRequest++; if(dialog()?.open) dialog().close(); return true; } // 保護來源更正且拒絕較晚回應重新開啟
  async function matchForm(mentionId) { // 同名人物需要使用者自己選擇
    const m=source.mentions.find(m=>m.id===mentionId); if(!m) throw new Error('線索已變更，請重新讀取來源。'); // 不引用失效來源
    document.querySelector('#source-content').innerHTML=`<h2>這裡說的是誰？</h2><div class="source-quote">${quote(source.raw_text,m)}</div><form id="mention-match-form" data-id="${h(m.id)}" data-revision="${m.revision}"><div class="field"><label for="match-search">搜尋候選人物</label><input id="match-search" placeholder="姓名、角色或標籤"></div>${button('match-search','搜尋候選人物')}<div class="field space-top"><label for="match-person">配對人物</label><select id="match-person" name="person_id" required><option value="">請選取既有人物</option></select></div><label class="check-line"><input name="confirmed" type="checkbox" required>我確認原文所指的是這位人物；不代表參與或私人關係。</label><button class="primary">確認對應人物</button></form><div class="button-row space-top">${button('retry-source','暫不配對')}${button('unmatch','取消人物配對',`data-mention="${h(m.id)}"`)}${button('reject-match','拒絕這次配對',`data-mention="${h(m.id)}"`)}</div>`; // 沒有預選同名者，避免暗中確認
    await loadCandidates('',m.person_id); // 初次提供可辨識候選清單
  } // 完成人工校對表單
  async function loadCandidates(search, selected=null) { const result=await c.api('/people?limit=100&q='+encodeURIComponent(search)); const node=document.querySelector('#match-person'); if(node) node.innerHTML='<option value="">請選取既有人物</option>'+result.items.map(p=>`<option value="${h(p.id)}" ${p.id===selected?'selected':''}>${h(p.name)} · ${h(p.roles.join('、')||'未設定角色')} · ${h(p.id.slice(-6))}</option>`).join(''); } // 顯示角色及識別碼尾碼以分辨同名
  async function submit(form) { // 只攔截交會自己的表單
    if(form.id==='mention-match-form') { const f=new FormData(form), body={expected_revision:Number(form.dataset.revision),person_id:f.get('person_id'),status:'matched',confirmed:f.has('confirmed')}; await c.api('/connections/mentions/'+form.dataset.id+'/match',{method:'POST',body:{...body,request_id:c.requestId('mention:'+form.dataset.id,body)}}); await openSource(source.id,form.dataset.id,true); c.toast('人物身分已保存；未增加參與或見面。'); return true; } // 成功才顯示已配對
    if(form.id==='story-people-form') { const story=collectEditor(form); if(!story) throw new Error('請選擇整理故事人物，或取消更正。'); const body={expected_revision:source.revision,story,confirmed:!!form.querySelector('#story-reviewed')?.checked}; await c.api('/connections/stories/'+source.id+'/people',{method:'PUT',body:{...body,request_id:c.requestId('story:'+source.id,body)}}); await c.refresh(); await openSource(source.id,null,true); c.toast('人物角色已保存，積分不變。'); return true; } // 只更新角色，不重新確認原經歷
    return false; // 其餘表單交回現有流程
  } // 完成提交轉接
  async function click(target) { // 處理故事、人物與來源操作
    const action=target.dataset.cx; if(!action) return false; // 不干涉其他模組
    if(action==='back') { const back=trail.pop(); if(back) go(back,false); } // 使用者探索路徑不當成私人關係
    if(action==='reset') { trail.length=0; go('people',false); } // 回到最近故事的明確起點
    if(action==='refresh') await c.render(); // 清單網路失敗後重試相同條件
    if(action==='focus') go(routeFor({focus:target.dataset.id,story:null,via:null,offset:null})); // 切人物時查其實際參與故事
    if(action==='story') go(routeFor({story:target.dataset.id})); // 保留焦點及順序
    if(action==='page') go(routeFor({offset:target.dataset.offset,story:null})); // 不載入全部經歷
    if(['source','mention-source','manage'].includes(action)) await openSource(target.dataset.id,target.dataset.mention,action==='manage'); // 先來源再身分
    if(action==='retry-source') await openSource(source.id,source.selected,source.manage); // 失敗後用相同原文來源重試
    if(action==='close-source') closeSource(); // 返回同一個探索位置
    if(action==='discard-source-edit') closeSource(true); // 使用者明確捨棄才關閉來源整理
    if(action==='match') await matchForm(target.dataset.mention); // 人工選候選身分
    if(action==='match-search') await loadCandidates(document.querySelector('#match-search').value); // 不使用 AI 任意選人
    if(action==='follow-mention') go(routeFor({focus:target.dataset.id,story:null,via:source.id,offset:null})); // 提及只導向此人的另一段故事
    if(action==='unmatch'||action==='reject-match') { const m=source.mentions.find(m=>m.id===target.dataset.mention), body={expected_revision:m.revision,person_id:null,status:action==='unmatch'?'unmatched':'rejected',confirmed:true}; await c.api('/connections/mentions/'+m.id+'/match',{method:'POST',body:{...body,request_id:c.requestId('mention:'+m.id,body)}}); await openSource(source.id,m.id,true); } // 可以取消或拒絕，不刪原文
    if(action==='availability') { const body={expected_revision:source.revision,available:target.dataset.available==='true'}; await c.api('/connections/stories/'+source.id+'/availability',{method:'POST',body:{...body,request_id:c.requestId('availability:'+source.id,body)}}); await openSource(source.id,null,true); } // 管理退路保留原始經歷
    if(action==='edit-source') { const s=await c.api('/connections/stories/'+source.id+'?manage=true'); source={...s,manage:true}; const story={title:s.title,participants:s.participants.map(p=>({person_id:p.id,interacted:p.interacted})),mentions:s.mentions.map(m=>({name:m.name,start:m.start,end:m.end,person_id:m.person_id}))}; document.querySelector('#source-content').innerHTML=`<h2>核對／更正故事人物</h2><div class="raw-source">${h(s.raw_text)}</div><form id="story-people-form">${editor(story,'manage')}<p class="small muted">不更改原文或積分。新增互動先保留未分類，可到人物時間線分類。</p><button class="primary">確認保存人物整理</button></form>${button('retry-source','取消更正')}`; hydrateEditors(); } // 舊資料由使用者明確分類
    if(action==='add-mention') { const root=target.closest('[data-story-editor]'); root.querySelector('.story-mention-rows').insertAdjacentHTML('beforeend',mentionRow()); hydrateEditors(); markEditorDirty(root); } // 新增未配對原文線索
    if(action==='remove-mention') { const root=target.closest('[data-story-editor]'); target.closest('.story-mention-editor').remove(); markEditorDirty(root); } // 明確移除此處線索
    return true; // 交會事件已處理
  } // 完成互動轉接
  function change(target) { // 人物整理與排序變更
    if(target.id==='connection-sort') { go(routeFor({order:target.value,story:null,offset:null})); return true; } // 排序依透明時間規則
    if(target.id==='include-story') {target.closest('[data-story-editor]').querySelector('.story-editor-body').hidden=!target.checked; hydrateEditors();} // 未使用時收起複雜欄位，避免重複互動分類
    if(target.name==='story_participant') { const row=target.closest('.participant-option'), check=row.querySelector('[name=story_interacted]'); check.disabled=!target.checked; if(!target.checked) check.checked=false; } // 取消參與時不殘留直接互動
    if(target.name==='mention_name') { target.closest('.story-mention-editor').querySelector('[name=mention_person]').value=''; updateSpans(target.closest('.story-mention-editor')); } // 名字更正不沿用舊身分
    return false; // 保留現有表單事件
  } // 完成欄位變更
  document.addEventListener('input',event=>{ if(event.target.matches('.participant-filter')) event.target.closest('fieldset').querySelectorAll('.participant-option').forEach(row=>row.hidden=!row.dataset.name.includes(event.target.value)); }); // 避免長人物清單難找，篩選不改勾選
  document.addEventListener('input',event=>{const root=event.target.closest('#source-dialog [data-story-editor]'); if(root&&!event.target.matches('.participant-filter')) markEditorDirty(root);}); // 來源編輯不污染主畫面的草稿旗標
  window.addEventListener('beforeunload',event=>{if(source?.editDirty){event.preventDefault();event.returnValue='';}}); // 刷新也保護未保存的角色更正
  document.addEventListener('DOMContentLoaded',()=>{dialog().addEventListener('cancel',event=>{event.preventDefault();closeSource();}); dialog().addEventListener('close',()=>{sourceRequest++; if(c?.state.route.startsWith('people')) {if(source?.available===false) c.navigate('people'); else c.render().catch(error=>c.toast(error.message));}});}); // 關閉後更新已配對標示與撤回路徑，Esc 也遵守未保存保護
  return {initialize,ensureOwner,tabs,worldMini,render,editor,collectEditor,hydrateEditors,remember,restore,clearReview,snapshotEditor,restoreEditor,click,submit,change,closeSource,go}; // 對 App 暴露必要介面
})(); // 不把角色或來源寫入 localStorage
