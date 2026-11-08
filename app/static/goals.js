'use strict'; // 單一目標與習慣編輯沿用既有 App、API 與元件。
const GoalsUI = (() => { // 將建立草稿與回顧編輯狀態集中管理。
  let draft = null, draftOwner = null, edit = null, historyTab = 'completed', viewed = null; // 各帳號隔離草稿，回顧保留失敗輸入。
  const labels = {active:'進行中',awaiting_review:'待回顧',needs_setup:'待補設定',completed:'已完成',ended:'曾經挑戰'}; // 統一生命週期文案。
  const today = () => state.me?.today || localInput().slice(0,10); // 優先使用伺服器判定日期。
  const open = g => ['active','awaiting_review','needs_setup'].includes(g.status); // 待回顧仍占用唯一目標。
  const key = () => 'lifeworld:goal-draft:' + state.me.owner_id; // 不共用不同帳號草稿。
  const day = value => new Date(value + 'T12:00:00Z'); // 日期運算不受本機夏令時間影響。
  const iso = value => value.toISOString().slice(0,10); // 統一日期鍵。
  const add = (value,n) => {const d=day(value);d.setUTCDate(d.getUTCDate()+n);return iso(d);}; // 以日曆日移動。
  const weekday = value => (day(value).getUTCDay()+6)%7; // 星期一為零。
  function load() { // 登入與重新整理後恢復目前帳號草稿。
    if(draftOwner === state.me.owner_id && draft) return draft; // 同帳號繼續目前編輯。
    draftOwner = state.me.owner_id; // 避免換帳號沿用畫面資料。
    try {draft=JSON.parse(localStorage.getItem(key()));} catch {draft=null;} // 儲存不可用時仍可暫存於記憶體。
    if(!draft || !Array.isArray(draft.actions) || draft.actions.length!==3) draft={request_id:newId(),step:0,title:'',outcome:'',deadline:'',start_date:today(),actions:[0,1,2].map(()=>({title:'',unit:'次',per_occurrence:'1',weekdays:[],dates:[],cycle:'month'}))}; // 不預填截止日或安排。
    return draft; // 只有正式提交成功才清除。
  } // 結束草稿讀取。
  function save() { // 即時保留名稱、步驟與日期。
    try {localStorage.setItem(key(),JSON.stringify(draft));} catch {toast('此瀏覽器無法保存本機草稿，請保持此頁開啟。');} // 明說未持久保存。
  } // 結束保存。
  function capture(form) { // 將目前可見欄位寫入對應編輯狀態。
    if(form?.id==='goal-form') { // 逐步表單只更新目前欄位。
      const d=load(); // 取得目前帳號草稿。
      if($('#goal-title',form)) d.title=$('#goal-title',form).value; // 保留名稱。
      if($('#outcome',form)) {d.outcome=$('#outcome',form).value;d.deadline=$('#goal-deadline',form).value;} // 保留成果與使用者截止日。
      if(d.step>=2&&d.step<=4) {const i=d.step-2,a=d.actions[i];a.title=$('#action-title-'+i,form).value;a.unit=$('#unit-'+i,form).value;a.per_occurrence=$('#target-'+i,form).value;} // 使用原有欄位識別碼承接習慣數量。
      save(); // 每次輸入立即保存。
    } // 回顧表單資料另由 submit 收集。
  } // 結束表單快照。
  function allDays(start,end) { // 只產生實際有效日期。
    const dates=[];for(let value=start;value&&value<=end;value=add(value,1)) {if(dates.length>=10000) throw new Error('這段安排超過可編輯日期數，請縮短期間。');dates.push(value);}return dates; // 避免無界迴圈。
  } // 結束日期列舉。
  function summary(a) { // 不把快選規律冒充實際完成。
    return `預計 ${a.dates?.length||0} 天 · 今天每次 ${a.per_occurrence} ${a.unit}${a.quantity_versions?.length>1?' · 分期標準：'+a.quantity_versions.map(v=>(v.effective_from==='0001-01-01'?'原始標準':v.effective_from+' 起')+' '+v.quantity+' '+a.unit).join('；'):''}${a.weekdays.length?' · 星期快選：'+a.weekdays.map(i=>dayNames[i]).join('、'):''}`; // 單日調整仍以日期陣列為準。
  } // 結束摘要。
  function calendar(a,index,start,end,mode='wizard') { // 共用建立與延長的日期編輯器。
    const cursor=a.cursor||start,d=day(cursor),monthly=a.cycle!=='week'; // 切換週期只改呈現。
    let first,last; // 計算可見區間。
    if(monthly) {first=iso(new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth(),1,12)));last=iso(new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+1,0,12)));} // 真實月份可有 28 至 31 天。
    else {first=add(cursor,-weekday(cursor));last=add(first,6);} // 星期一開始的七日。
    const attrs=`data-mode="${mode}" data-index="${index}"`; // 每個按鈕只修改指定習慣。
    const disabled=end<start; // 未選有效期間時不允許操作。
    const cells=allDays(first,last).map(value=>{const available=!disabled&&value>=start&&value<=end,selected=a.dates.includes(value);return `<button type="button" class="gj-day ${selected?'selected':''}" data-gj="toggle-day" ${attrs} data-date="${value}" aria-label="${value}" aria-pressed="${selected}" ${available?'':'disabled'}><span>${Number(value.slice(-2))}</span><small>${selected?'已安排':'－'}</small></button>`;}).join(''); // 勾選代表安排，不使用完成打勾。
    return `<section class="gj-calendar" aria-label="習慣日期安排"><div class="button-row"><button type="button" class="${monthly?'primary':'secondary'}" data-gj="cycle-month" ${attrs} aria-pressed="${monthly}">按月檢視</button><button type="button" class="${monthly?'secondary':'primary'}" data-gj="cycle-week" ${attrs} aria-pressed="${!monthly}">按週檢視</button></div><p class="small muted">星期快選套用目標期間內的日期，再點日期格單獨調整。安排不代表已完成。</p><div class="gj-weekdays">${dayNames.map((name,i)=>`<button type="button" class="secondary" data-gj="weekday" ${attrs} data-day="${i}" aria-label="星期${name}" aria-pressed="${a.weekdays.includes(i)}">${name}</button>`).join('')}</div><div class="button-row space-top"><button type="button" class="secondary" data-gj="weekdays" ${attrs}>平日</button><button type="button" class="secondary" data-gj="daily" ${attrs}>每天</button><button type="button" class="text-button" data-gj="clear" ${attrs}>清除安排</button></div><div class="gj-month-title"><button type="button" class="text-button" data-gj="previous-period" ${attrs} aria-label="上一段日期" ${first<=start?'disabled':''}>←</button><b>${monthly?first.slice(0,7):first+' ～ '+last}</b><button type="button" class="text-button" data-gj="next-period" ${attrs} aria-label="下一段日期" ${last>=end?'disabled':''}>→</button></div><div class="gj-date-grid">${monthly?'<span aria-hidden="true"></span>'.repeat(weekday(first)):''}${cells}</div><p class="gj-schedule-summary" role="status">${esc(summary(a))}</p></section>`; // 語意與日期數均可被輔助工具讀取。
  } // 結束排程畫面。
  function form() { // 分步建立目標與三個習慣。
    const existing=state.world?.goals.filter(open)||[]; // 不能從直接網址繞過限制。
    if(existing.length) return heading('先照顧目前的挑戰。','完成或結束後，再開始下一個目標。')+existing.map(goalCard).join(''); // 舊多目標也提供逐一整理入口。
    const d=load(),i=d.step-2,a=d.actions[i],titles=['為目標取名','達成的樣子與期限','第一個重要習慣','第二個重要習慣','第三個重要習慣','檢查這次挑戰']; // 固定且清楚的步驟。
    let content=''; // 僅渲染目前步驟，避免長表單。
    if(d.step===0) content=`<div class="field"><label for="goal-title">目標名稱</label><input id="goal-title" name="title" required maxlength="160" value="${esc(d.title)}" placeholder="例如：完成第一個作品"></div>`; // 命名是第一個操作。
    else if(d.step===1) content=`<div class="field"><label for="outcome">達成時會是什麼樣子？</label><textarea id="outcome" name="outcome" required maxlength="4000">${esc(d.outcome)}</textarea></div><div class="field"><label for="goal-deadline">挑戰截止日（必選）</label><input type="date" id="goal-deadline" name="deadline" required min="${today()}" value="${esc(d.deadline)}"><small id="goal-date-help">開始日：${esc(today())}；截止日包含 ${esc(state.me.timezone)} 當地整天。請選日期或使用下方快捷設定。</small><div class="button-row space-top"><button type="button" class="secondary" data-gj="deadline-offset" data-days="7">一週後</button><button type="button" class="secondary" data-gj="deadline-offset" data-days="30">30 天後</button></div></div>`; // 目標期限與月編輯週期分開。
    else if(d.step<5) content=`<div class="field"><label for="action-title-${i}">習慣 ${i+1} 名稱</label><input id="action-title-${i}" required maxlength="160" value="${esc(a.title)}" placeholder="例如：閱讀、運動、主動聯繫"></div><details class="gj-quantity"><summary>每次預期 ${esc(a.per_occurrence)} ${esc(a.unit)} · 調整數量</summary><div class="form-grid space-top"><div class="field"><label for="target-${i}">每次預期量</label><input id="target-${i}" type="number" min="0.000001" max="1000000000000" step="0.000001" required value="${esc(a.per_occurrence)}"></div><div class="field"><label for="unit-${i}">計量單位</label><input id="unit-${i}" required maxlength="20" value="${esc(a.unit)}"></div></div></details>${calendar(a,i,today(),d.deadline)}`; // 數量收起，日期直接操作。
    else content=`<h2>${esc(d.title)}</h2><p class="record-content">${esc(d.outcome)}</p><p>${today()} ～ ${esc(d.deadline)} · ${esc(state.me.timezone)}</p>${d.actions.map((item,n)=>`<article class="gj-summary-item"><h3>${n+1}. ${esc(item.title)}</h3><p>${esc(summary(item))}</p><button type="button" class="text-button" data-gj="edit-step" data-step="${n+2}">修改習慣 ${n+1}</button></article>`).join('')}<div class="callout">安排不是已完成。記錄真實經歷並確認貢獻後，進度才會累計；成果由你提供佐證並親自確認。</div>`; // 確認總覽不預加進度。
    return `<div class="narrow">${heading(titles[d.step],'一次專注一個目標，為它建立三個重要習慣。')}<form id="goal-form" class="card" data-step="${d.step}"><p class="step-label">第 ${d.step+1}／6 步 · 這份草稿只保存在目前裝置</p>${content}<div class="button-row space-top">${d.step?'<button type="button" class="secondary" data-gj="back">上一步</button>':''}<button type="submit" class="primary">${d.step===5?(state.me.lumi_hatched?'確認設定，開始挑戰':'確認設定，建立目標蛋 →'):'下一步 →'}</button><button type="button" class="text-button" data-gj="pause">稍後繼續</button></div></form></div>`; // 全部確認後才呼叫建立 API。
  } // 結束建立畫面。
  async function list() { // 目前挑戰與歷史分區。
    const goals=state.world.goals,current=goals.filter(open),archived=goals.filter(g=>g.status===historyTab); // 不混合進行中與過往目標。
    return `${heading('目前挑戰','完成或結束這一段，再開始下一個方向。',current.length?'':link('goal-new','＋ 新的目標','primary'))}${current.length>1?'<div class="callout">這是舊版保留的多個目標。請逐一完成或結束其他目標，再為保留的挑戰補設定。</div>':''}<div class="stack">${current.length?current.map(goalCard).join(''):empty('目前沒有進行中的挑戰，可以開始新的方向。')}</div><section class="space-top"><h2>目標旅程</h2><div class="button-row space-bottom" role="group" aria-label="歷史分類">${[['completed','已完成'],['ended','曾經挑戰']].map(([value,label])=>`<button type="button" class="${historyTab===value?'primary':'secondary'}" data-gj="history-tab" data-tab="${value}" aria-pressed="${historyTab===value}">${label}</button>`).join('')}</div><div class="stack">${archived.length?archived.map(goalCard).join(''):empty(historyTab==='completed'?'完成的成果會收藏在這裡。':'提前結束與到期未完成的挑戰會留在這裡。')}</div></section>`; // 歷史不提供恢復或複製捷徑。
  } // 結束目標列表。
  function futureQuantity(a, date) {
    // 明日已有待生效版本時，編輯欄位顯示該值，避免日期調整誤取消用量。
    return (a.quantity_versions||[]).filter(v=>v.effective_from<=add(date,1)).at(-1)?.quantity || a.per_occurrence;
  }
  function changeSummary() {
    if(!edit) return '';
    return `<h3>保存前核對</h3><p>用量從 ${add(edit.today,1)} 起生效（${esc(viewed.schedule_timezone||state.me.timezone)}）；今天與歷史投入、積分不重算。</p>${edit.actions.map((a,i)=>`<p>${i+1}. ${esc(edit.originals[i].title)} → ${esc(a.title)}；今天 ${esc(a.per_occurrence)} ${esc(a.unit)}，原訂明日用量 ${esc(futureQuantity(edit.originals[i],edit.today))} → ${esc(a.next_quantity)} ${esc(a.unit)}；預計 ${a.dates.length} 天</p>`).join('')}`;
  }
  function habitFields(a,i) {
    return `<div class="field"><label for="review-title-${i}">更正習慣 ${i+1} 名稱</label><input id="review-title-${i}" data-habit-field="title" data-index="${i}" maxlength="160" required value="${esc(a.title)}"><small>僅更正名稱，不替換習慣用途；單位固定為 ${esc(a.unit)}。</small></div><div class="field"><label for="review-quantity-${i}">明天起每次預期量</label><input id="review-quantity-${i}" data-habit-field="next_quantity" data-index="${i}" type="number" min="0.000001" max="1000000000000" step="0.000001" required value="${esc(a.next_quantity)}"><small>今天仍為 ${esc(a.per_occurrence)} ${esc(a.unit)}；需有明天起的執行日期。</small></div>`;
  }
  function reviewEditor(goal) { // 延長與舊目標設定共用三個日期編輯器。
    const action=edit.decision,minimum=action==='extend'?add(goal.deadline,1):edit.today; // 新期限不能縮短。
    return `<form id="goal-review-form" class="card"><h2>${action==='setup'?'補齊這次挑戰':action==='schedule'?'調整未來安排':'延長挑戰'}</h2><input type="hidden" name="decision" value="${action}">${action!=='schedule'?`<div class="field"><label for="review-deadline">新的截止日</label><input id="review-deadline" name="deadline" type="date" min="${minimum>edit.today?minimum:edit.today}" required value="${esc(edit.deadline)}"></div>`:''}${edit.deadline?edit.actions.map((a,i)=>`<details ${i===(edit.openHabit??0)?'open':''}><summary data-gj="open-habit" data-index="${i}">${esc(a.title)} · 檢視安排</summary>${habitFields(a,i)}${calendar(a,i,edit.today,edit.deadline,'review')}</details>`).join(''):'<p>先選截止日，再安排三個習慣。</p>'}<section class="callout" id="habit-change-summary" aria-live="polite">${changeSummary()}</section>${edit.conflict?'<button type="button" class="secondary" data-gj="reload-review">載入最新版本並重新核對</button>':''}<div class="field"><label for="review-reflection">想留下的回顧（選填）</label><textarea id="review-reflection" name="reflection" maxlength="4000">${esc(edit.reflection||'')}</textarea></div><label class="check-line"><input type="checkbox" name="confirmed" required ${edit.confirmed?'checked':''}>我已檢視截止日、三個習慣與生效日；名稱僅更正、不改變習慣用途。</label><div class="button-row"><button class="primary">確認保存安排</button><button type="button" class="secondary" data-gj="cancel-review">返回目標</button></div></form>`; // 失敗時保留輸入，不默默更新。
  } // 結束回顧編輯器。
  async function detail(id,localEdit=false) { // 真正讀取後端狀態，不只隱藏按鈕。
    let goal;try{goal=localEdit&&edit?.id===id&&viewed?.id===id?viewed:await api('/goals/'+encodeURIComponent(id));}catch(error){if([401,403,404].includes(error.status))throw error;goal=state.world?.goals.find(g=>g.id===id);if(!goal)throw error;}viewed=goal; // 每次進入重新判斷到期。
    const current=open(goal),pending=goal.pending_contributions,mode=edit?.id===id?edit.decision:null; // 保留此目標失敗後的編輯。
    const period=goal.deadline?`${goal.start_date} ～ ${goal.deadline} · ${goal.schedule_timezone}`:'舊目標尚未確認截止日，請先補設定。'; // 不替舊資料猜日期。
    const header=heading(goal.title,period,current?link('record?goal='+goal.id,'記錄本次行動','primary'):''); // 歷史不導向正式貢獻。
    if(mode&&mode!=='end') return header+reviewEditor(goal); // 延長時直接操作三個習慣。
    const controls=current?`<section class="card"><h2>${goal.status==='awaiting_review'?'這次挑戰到期了，先回顧一下。':goal.status==='needs_setup'?'先補齊舊目標設定。':'依照自己的節奏前進。'}</h2><p>到期與提前結束都不扣分；你的真實投入會保留。</p><div class="button-row">${goal.status==='needs_setup'?'<button type="button" class="primary" data-gj="setup">補齊目標設定</button>':`<button type="button" class="secondary" data-gj="extend">延長挑戰</button>`}<button type="button" class="secondary" data-gj="focus-complete">確認完成成果</button><button type="button" class="text-button" data-gj="end">結束這次挑戰</button></div>${mode==='end'?'<form id="goal-end-form" class="space-top"><div class="field"><label for="end-reflection">留下這次的回顧（選填）</label><textarea id="end-reflection" name="reflection" maxlength="4000"></textarea></div><label class="check-line"><input type="checkbox" id="goal-end-confirmed" name="confirmed" required>確認結束；保留歷史投入，這次不再恢復。</label><div class="button-row"><button class="primary">確認結束並收藏</button><button type="button" class="secondary" data-gj="cancel-review">繼續挑戰</button></div></form>':''}</section>`:''; // 明確確認避免誤結束。
    const completed=goal.status==='completed',ended=goal.status==='ended'; // 歷史分別呈現。
    const sources=`<div class="photo-grid">${goal.evidence.map(e=>`<a href="/api/evidence/${esc(e.id)}" target="_blank" rel="noopener"><img src="/api/evidence/${esc(e.id)}" alt="${esc(e.filename)}">${esc(e.filename)}</a>`).join('')}</div>`; // 真實佐證仍受後端權限保護。
    const completion=`<section class="card" id="goal-completion" tabindex="-1"><h2>${completed?'這段成果，已經收藏。':ended?'這段挑戰，已經收藏。':'我已達成成果'}</h2>${sources}${current?`<p>上傳相關佐證，再由你確認是否達標。</p><form id="upload-form" data-goal="${esc(id)}"><div class="field"><label for="evidence-file">拍攝或選擇圖片</label><input id="evidence-file" name="file" type="file" accept="image/png,image/jpeg" required></div><button class="secondary">上傳佐證</button></form><form id="complete-form" class="space-top" data-goal="${esc(id)}"><div class="field"><label for="reflection">完成感想（選填）</label><textarea id="reflection" name="reflection" maxlength="4000"></textarea></div><label class="check-line"><input type="checkbox" name="confirmed" required>我已檢視佐證，確認終極成果已達成。</label><button class="primary" ${goal.evidence.length?'':'disabled'}>確認完成並收藏成果</button></form>`:`<p>${esc(goal.reflection||'每一段投入，都值得留下。')}</p><p>${completed?'確認完成於 '+esc(time(goal.completed_at)):'結束於 '+esc(time(goal.ended_at))}</p>${link('goals','返回目標旅程','secondary')}${state.world.goals.some(open)?'':link('goal-new','種下下一個目標 →','primary')}`}</section>`; // 不新增恢復歷史功能。
    const pendingHTML=pending.length?`<section class="card"><h2>待處理與未採計貢獻</h2><p class="small muted">經歷已保存。只有延長後逐筆核對才更新進度，不再次發獎。</p>${pending.map(p=>`<article class="gj-summary-item"><h3>${esc(p.title)}</h3><p>${esc(time(p.occurred_at))} · ${esc(p.summary)}</p><p>${p.status==='accepted'?'已採計 '+esc(p.accepted_quantity):p.status==='unapplied'?'未採計':'等待回顧'} · 原填 ${esc(p.quantity)} ${esc(p.unit)}</p>${goal.status==='active'&&p.status==='pending'?`<form class="pending-accept-form" data-pending="${esc(p.id)}"><label>核對採計量<input type="number" name="quantity" min="0.000001" max="1000000000000" step="0.000001" value="${esc(p.quantity)}" required></label><label class="check-line"><input type="checkbox" name="confirmed" required>我已核對這段經歷與數量。</label><button class="secondary">確認採計這筆貢獻</button></form>`:''}</article>`).join('')}</section>`:''; // 一筆來源一個明確確認。
    const schedules='<details class="card" id="gd-schedule"><summary>排程與用量版本</summary><p>請展開上方各習慣的「查看日期與用量」，逐月檢視；修改安排請使用「調整未來安排」。查看不會更新投入。</p></details>';
    const vm=await DashboardUI.load(id);
    return DashboardUI.view(vm,goal)+`<div class="stack space-top">${schedules}<section id="gd-records" tabindex="-1">${ended?`<p class="tag">${goal.end_reason==='expired'?'到期未完成':'提前結束'}</p>`:''}${controls}${pendingHTML}${completion}${goal.reviews.length?`<section class="card"><h2>回顧紀錄</h2>${goal.reviews.map(r=>`<p>${esc(time(r.created_at))} · ${{extend:'延長挑戰',setup:'補齊設定',schedule:'修改未來安排',end:'結束挑戰'}[r.decision]} ${esc(r.reflection)}</p>`).join('')}</section>`:''}</section></div>`;

  } // 結束目標詳情。
  async function submit(form) { // 接入 App 共用提交與錯誤處理。
    if(form.id==='goal-form') { // 只在最後一步正式建立。
      capture(form);const d=load(); // 保存本次輸入。
      if(d.step<5) { // 前五步只做本機驗證。
        if(d.step>=2) {const a=d.actions[d.step-2];if(!a.dates.length) throw new Error('請至少安排一天再繼續。');} // 不接受無日期習慣。
        if(d.step>=2&&d.step<=4&&d.actions[d.step-2].dates.some(value=>value<today()||value>d.deadline)) throw new Error('請調整超出目標期間的排程，或使用清除安排後重新選擇。'); // 不靜默刪安排。
        d.step++;save();state.dirty=false;await render({localGoalEdit:true});return true; // 進下一步並保留草稿。
      } // 所有步驟通過才提交。
      const body={request_id:d.request_id,title:d.title,outcome:d.outcome,deadline:d.deadline,actions:d.actions.map(({title,unit,per_occurrence,dates,weekdays,cycle})=>({title,unit,per_occurrence,dates:[...dates].sort(),weekdays,cycle}))}; // 不把游標或畫面狀態送進 API。
      const hatched=state.me.lumi_hatched,goal=await api('/goals',{method:'POST',body}); // 相同草稿重試沿用 ID。
      try {localStorage.removeItem(key());} catch {} // 正式成功後才清草稿。
      state.guestSaveNoticePending=true; // 只有server成功保存後，在下一畫面提醒Guest保存期限。
      draft=null;edit=null;await refresh();navigate(hatched?'goal/'+goal.id:'birth');return true; // 只有首次顯示 Lumi 誕生。
    } // 其他表單使用回顧流程。
    if(!['goal-review-form','goal-end-form'].includes(form.id)&&!form.matches('.pending-accept-form')) return false; // 不攔截經歷或人物表單。
    const id=state.route.split('?')[0].split('/')[1],goal=await api('/goals/'+id),f=new FormData(form); // 先讀取當前可見版本。
    const revision=edit?.id===id?edit.revision:viewed?.id===id?viewed.revision:goal.revision; // 採使用者開始編輯時的版本。
    if(form.matches('.pending-accept-form')) {const body={expected_revision:revision,quantity:f.get('quantity'),confirmed:f.has('confirmed')};await api('/goals/'+id+'/pending/'+form.dataset.pending+'/accept',{method:'POST',body:{...body,request_id:requestId('pending:'+form.dataset.pending,body)}});} // 補計不重送經歷。
    else { // 延長、設定與結束。
      const decision=form.id==='goal-end-form'?'end':edit.decision; // 只有明確結束才關閉挑戰。
      const body={decision,expected_revision:revision,confirmed:f.has('confirmed'),reflection:f.get('reflection')||''}; // 保存回顧感想。
      if(decision!=='end') {edit.reflection=body.reflection;edit.confirmed=body.confirmed;body.deadline=edit.deadline;body.schedules=edit.actions.map(a=>({action_id:a.id,dates:a.dates,weekdays:a.weekdays,cycle:a.cycle,title:a.title,per_occurrence:a.next_quantity,expected_effective_from:add(edit.today,1)}));} // 失敗保留三個安排。
      try { await api('/goals/'+id+'/review',{method:'POST',body:{...body,request_id:requestId('goal-review:'+id,body)}}); }
      catch(error) {
        if(['revision_conflict','effective_date_changed'].includes(error.code) && edit) {edit.conflict=true;edit.confirmed=false;await render({localGoalEdit:true});}
        throw error;
      } // 衝突保留草稿，不能自動用新版號重送。

    } // 成功後刷新。
    edit=null;state.dirty=false;await refresh();await render({localGoalEdit:true});toast('已保存；真實投入與既有積分都保留。');return true; // 不以結束發獎。
  } // 結束共用提交。
  document.addEventListener('input',event=>{const form=event.target.closest('#goal-form');if(form) capture(form);if(edit&&event.target.id==='review-reflection')edit.reflection=event.target.value;
    if(edit&&event.target.dataset.habitField) {
      edit.actions[Number(event.target.dataset.index)][event.target.dataset.habitField]=event.target.value;
      edit.confirmed=false;const check=$('#goal-review-form input[name=confirmed]');if(check)check.checked=false;
      $('#habit-change-summary').innerHTML=changeSummary();
    }}); // 即時保存輸入。
  document.addEventListener('change',event=>{if(event.target.id==='review-deadline'&&edit){edit.deadline=event.target.value;edit.confirmed=false;state.dirty=false;render({localGoalEdit:true}).catch(showError);}}); // 期限改變後重新顯示日期供確認。
  document.addEventListener('click',async event=>{ // 只處理明確標記的目標控制項。
    const target=event.target.closest('[data-gj]');if(!target||target.disabled)return; // 忽略其他模組與停用日期。
    try { // 操作失敗保持目前畫面。
      capture($('#goal-form'));const action=target.dataset.gj; // 先保存可見欄位。
      // 快捷日期使用伺服器的Owner當地今天；不預填、不自動提交，仍由使用者核對。
      if(action==='deadline-offset'){const d=load();d.deadline=add(today(),Number(target.dataset.days));save();state.dirty=false;await render({localGoalEdit:true});$('#goal-deadline')?.focus();return;}
      if(action==='focus-complete'){const section=$('#goal-completion');section?.focus({preventScroll:true});section?.scrollIntoView({block:'start'});return;} // 成果主要入口導向可接續的操作區。
      if(action==='open-habit'){if(edit)edit.openHabit=Number(target.dataset.index);return;} // 保留手動展開的習慣面板。
      if(action==='resume'){event.preventDefault();state.dirty=false;navigate('goal-new');return;} // 相同網址也重新顯示保留的草稿。
      if(action==='pause'){save();state.dirty=false;$('#app').innerHTML=heading('設定已留在這裡。','準備好時，再繼續這次挑戰。','<a class="primary" href="#goal-new" data-gj="resume">繼續建立目標</a>');return;} // 取消不丟草稿。
      if(action==='history-tab'){historyTab=target.dataset.tab;await render({localGoalEdit:true});return;} // 切換歷史分類。
      if(action==='back'||action==='edit-step'){draft.step=action==='back'?draft.step-1:Number(target.dataset.step);save();state.dirty=false;await render({localGoalEdit:true});return;} // 返回不重建資料。
      if(action==='reload-review'&&edit){
        const g=await api('/goals/'+edit.id);viewed=g;edit.revision=g.revision;edit.today=g.today;edit.originals=g.actions;
        edit.actions=edit.actions.map(a=>({...a,per_occurrence:g.actions.find(x=>x.id===a.id).per_occurrence}));
        edit.conflict=false;edit.confirmed=false;await render({localGoalEdit:true});toast('已載入最新標準；保留你的修改，請重新核對摘要與日期。');return;
      }
      if(action==='cancel-review'){edit=null;state.dirty=false;await render({localGoalEdit:true});return;} // 明確取消回顧不修改正式資料。
      if(['extend','setup','schedule','end'].includes(action)){const id=state.route.split('?')[0].split('/')[1],g=await api('/goals/'+id);viewed=g;edit={id,decision:action,today:g.today||today(),revision:g.revision,originals:g.actions,deadline:action==='schedule'?g.deadline:'',actions:g.actions.map(a=>({...a,next_quantity:futureQuantity(a,g.today),dates:a.dates?[...a.dates]:[],weekdays:[...a.weekdays],cursor:g.today||today()}))};state.dirty=false;await render({localGoalEdit:true});return;} // 從已確認狀態建立本次編輯。
      const position=window.scrollY;const reviewing=target.dataset.mode==='review',context=reviewing?edit:load(),a=context.actions[Number(target.dataset.index)],start=reviewing?edit.today:today(),end=context.deadline; // 每個操作限定自己的習慣。
      if(reviewing){edit.openHabit=Number(target.dataset.index);edit.confirmed=false;} // 日期重繪不跳回第一個習慣。
      if(action==='cycle-week'||action==='cycle-month') a.cycle=action==='cycle-week'?'week':'month'; // 檢視切換不改已選日期。
      if(action==='previous-period'||action==='next-period'){const direction=action==='next-period'?1:-1,d=day(a.cursor||start);if(a.cycle==='week')a.cursor=add(iso(d),7*direction);else a.cursor=iso(new Date(Date.UTC(d.getUTCFullYear(),d.getUTCMonth()+direction,1,12)));} // 正確跨月與跨年。
      if(action==='toggle-day'){const value=target.dataset.date;a.dates=a.dates.includes(value)?a.dates.filter(x=>x!==value):[...a.dates,value].sort();} // 單日例外不修改其他日期。
      if(['weekday','weekdays','daily','clear'].includes(action)){const selected=action==='weekday'?Number(target.dataset.day):null;if(action==='clear')a.weekdays=[];else if(action==='weekday')a.weekdays=a.weekdays.includes(selected)?a.weekdays.filter(x=>x!==selected):[...a.weekdays,selected].sort();else a.weekdays=action==='daily'?[0,1,2,3,4,5,6]:[0,1,2,3,4];const past=reviewing?a.dates.filter(value=>value<start):[];a.dates=[...past,...allDays(start,end).filter(value=>a.weekdays.includes(weekday(value)))];} // 快選只改今天與未來，保留過去。
      if(!reviewing)save();state.dirty=false;await render({localGoalEdit:true});document.querySelector(`[data-gj="${action}"][data-index="${target.dataset.index}"]${target.dataset.date?'[data-date="'+target.dataset.date+'"]':''}`)?.focus({preventScroll:true});window.scrollTo(0,position); // 同時保留日期與可見週期。
    } catch(error){showError(error);} // 不清空使用者設定。
  }); // 結束日期與導覽事件。
  return {form,list,detail,submit,open,labels,today,capture,completion:()=>viewed}; // 僅公開 App 整合需要的介面。
})(); // 不建立另一個路由系統或資料庫。
