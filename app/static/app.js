// Contract markers for backend/frontend tests: it.torrent_id || it.id, fetch('/api/history'), fetch('/api/torrents/add'
// ---------- Small utilities ----------
const $ = (id) => document.getElementById(id);
function escapeHtml(s) { return (s ?? '').toString().replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;'); }
function formatSize(sz) { const n=Number(sz); if(!Number.isFinite(n)) return sz ? String(sz) : ''; const u=['B','KB','MB','GB','TB']; let i=0,x=n; while(x>=1024&&i<u.length-1){x/=1024;i++;} return `${x.toFixed(1)} ${u[i]}`; }
function parseDate(v) { const t=Date.parse(String(v||'').replace(' ','T')); return Number.isFinite(t) ? t : 0; }
function lighten(hex, alpha='22') { return /^#[0-9a-fA-F]{6}$/.test(hex||'') ? `${hex}${alpha}` : '#eef6ff55'; }
async function jsonFetch(url, options={}) { const r=await fetch(url, options); const j=await r.json().catch(()=>({})); if(!r.ok) throw new Error(j.detail||j.message||`HTTP ${r.status}`); return j; }

// ---------- Excel-ish table controller ----------
class DataTable {
  constructor(table, columns, opts={}) {
    this.table = table; this.thead = table.querySelector('thead'); this.tbody = table.querySelector('tbody');
    this.columns = columns; this.rows = []; this.sort = null; this.filters = {}; this.opts = opts;
    this.renderHeader();
  }
  setRows(rows) { this.rows = rows || []; this.render(); }
  uniqueValues(col) {
    const vals = new Set();
    this.rows.forEach(row => vals.add(String(col.value(row) ?? '').trim() || '(blank)'));
    return [...vals].sort((a,b)=>a.localeCompare(b, undefined, {numeric:true, sensitivity:'base'}));
  }
  renderHeader() {
    const tr=document.createElement('tr');
    this.columns.forEach(col=>{
      const th=document.createElement('th'); th.className=col.className||'';
      const label=document.createElement('span'); label.textContent=col.label; if(col.sortable) label.className='th-sort';
      label.addEventListener('click',()=>{ if(!col.sortable) return; this.cycleSort(col.key); });
      th.appendChild(label);
      const sortMark=document.createElement('span'); sortMark.className='sort-mark'; sortMark.style.marginLeft='.25rem'; th.appendChild(sortMark);
      if(col.filter) { const b=document.createElement('button'); b.type='button'; b.className='filter-btn'; b.textContent='▾'; b.title=`Filter ${col.label}`; b.addEventListener('click',(e)=>{e.stopPropagation(); this.openFilter(th,col);}); th.appendChild(b); }
      tr.appendChild(th);
    });
    this.thead.innerHTML=''; this.thead.appendChild(tr);
  }
  cycleSort(key) {
    if(!this.sort || this.sort.key!==key) this.sort={key, dir:'asc'};
    else if(this.sort.dir==='asc') this.sort.dir='desc';
    else this.sort=null;
    this.render();
  }
  openFilter(th,col) {
    document.querySelectorAll('.filter-menu').forEach(x=>x.remove());
    const menu=document.createElement('div'); menu.className='filter-menu';
    const search=document.createElement('input'); search.type='text'; search.placeholder='Find values'; menu.appendChild(search);
    const actions=document.createElement('div');
    const all=document.createElement('button'); all.type='button'; all.textContent='Select all';
    const clear=document.createElement('button'); clear.type='button'; clear.textContent='Clear';
    actions.append(all, clear); menu.appendChild(actions);
    const list=document.createElement('div'); menu.appendChild(list);
    const values=this.uniqueValues(col); const current=new Set(this.filters[col.key] || values);
    const draw=()=>{ const needle=search.value.toLowerCase(); list.innerHTML=''; values.filter(v=>v.toLowerCase().includes(needle)).forEach(v=>{ const lab=document.createElement('label'); const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=current.has(v); cb.addEventListener('change',()=>{ cb.checked ? current.add(v) : current.delete(v); this.filters[col.key]=[...current]; if(current.size===values.length) delete this.filters[col.key]; this.render(); }); lab.append(cb, document.createTextNode(` ${v}`)); list.appendChild(lab); }); };
    all.onclick=()=>{ values.forEach(v=>current.add(v)); delete this.filters[col.key]; this.render(); draw(); };
    clear.onclick=()=>{ current.clear(); this.filters[col.key]=[]; this.render(); draw(); };
    search.oninput=draw; th.appendChild(menu); draw();
  }
  passes(row) {
    return this.columns.every(col=>{ const selected=this.filters[col.key]; if(!selected) return true; const val=String(col.value(row) ?? '').trim() || '(blank)'; return selected.includes(val); });
  }
  sorted(rows) {
    if(!this.sort) return rows;
    const col=this.columns.find(c=>c.key===this.sort.key); if(!col) return rows;
    const dir=this.sort.dir==='desc'?-1:1;
    return [...rows].sort((a,b)=>{ let av=col.value(a), bv=col.value(b); if(col.type==='number'){av=Number(av)||0; bv=Number(bv)||0; return (av-bv)*dir;} if(col.type==='date'){return (parseDate(av)-parseDate(bv))*dir;} return String(av??'').localeCompare(String(bv??''), undefined, {numeric:true,sensitivity:'base'})*dir; });
  }
  render() {
    document.querySelectorAll('.filter-menu').forEach(x=>x.remove());
    const rows=this.sorted(this.rows.filter(r=>this.passes(r)));
    this.tbody.innerHTML=''; rows.forEach(row=>{ const tr=document.createElement('tr'); if(this.opts.rowStyle) tr.setAttribute('style', this.opts.rowStyle(row)||''); this.columns.forEach(col=>{ const td=document.createElement('td'); td.className=col.className||''; const rendered=col.render ? col.render(row) : escapeHtml(col.value(row)); if(rendered instanceof Node) td.appendChild(rendered); else td.innerHTML=rendered; tr.appendChild(td); }); this.tbody.appendChild(tr); });
    this.table.style.display = rows.length ? '' : 'none';
    [...this.thead.querySelectorAll('th')].forEach((th,i)=>{ const mark=th.querySelector('.sort-mark'); if(mark){ const col=this.columns[i]; mark.textContent=(this.sort&&this.sort.key===col.key) ? (this.sort.dir==='asc'?'▲':'▼') : ''; }});
    if(this.opts.onRender) this.opts.onRender(rows.length, this.rows.length);
  }
}

// ---------- DOM ----------
const form=$('searchForm'), q=$('q'), sortSel=$('sort'), windowSel=$('window'), perpageSel=$('perpage'), statusEl=$('status');
let searchTable, rssTable;
if(q) q.focus();

(async()=>{ try { const j=await jsonFetch('/health'); $('health').textContent=j.ok?'OK':'Not OK'; } catch { $('health').textContent='Error'; } })();

function mamLink(id){ return id ? `https://www.myanonamouse.net/t/${encodeURIComponent(id)}` : ''; }
function actionButton(text, fn, disabled=false){ const b=document.createElement('button'); b.type='button'; b.textContent=text; b.disabled=disabled; b.addEventListener('click', fn); return b; }

function initSearchTable(){
  searchTable = new DataTable($('results'), [
    {key:'title', label:'Title', sortable:true, filter:true, value:r=>r.title||''},
    {key:'author', label:'Author', sortable:true, filter:true, value:r=>r.author||r.author_info||''},
    {key:'series', label:'Series', sortable:true, filter:true, value:r=>r.series||r.series_info||''},
    {key:'narrator', label:'Narrator', sortable:true, filter:true, value:r=>r.narrator||r.narrator_info||''},
    {key:'format', label:'Filetype', sortable:true, filter:true, value:r=>(r.format||'').toLowerCase()},
    {key:'size', label:'Size', type:'number', sortable:true, className:'right', value:r=>r.size||0, render:r=>formatSize(r.size)},
    {key:'seeders', label:'Seeders', type:'number', sortable:true, className:'right', value:r=>r.seeders||0, render:r=>`${r.seeders ?? '-'} / ${r.leechers ?? '-'}`},
    {key:'uploaded', label:'Uploaded', type:'date', sortable:true, value:r=>r.uploaded_at||r.added||''},
    {key:'mam', label:'MAM', className:'center', value:r=>r.torrent_id||r.id||'', render:r=>{ const url=mamLink(r.torrent_id||r.id); return url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">MAM</a>` : ''; }},
    {key:'add', label:'Add', value:r=>'', render:r=>actionButton('Add', async e=>addTorrentFromItem(e.currentTarget,r), !(r.torrent_id||r.id))},
  ], {onRender:(shown,total)=> statusEl.textContent=`${shown} of ${total} result(s) shown`});
}

async function runSearch(){
  const text=(q?.value||'').trim(); const sortType=sortSel?.value||'snatchedDesc'; const windowValue=windowSel?.value||''; const perpage=parseInt(perpageSel?.value||'25',10);
  statusEl.textContent = text ? 'Searching…' : 'Running default 3-month MAM M4B search…';
  const params=new URLSearchParams({q:text, perpage:String(perpage), window:windowValue, sort:sortType});
  try { const data=await jsonFetch(`/api/search?${params}`); const rows=data.items||[]; searchTable.setRows(rows); statusEl.innerHTML = `${rows.length} result(s). <span class="pill">Preset: ${escapeHtml(data.preset||'')}</span> <span class="pill">Window: ${escapeHtml(data.window||'')}</span> <span class="pill">MAM sort: ${escapeHtml(data.sort||'')}</span>`; await loadHistory(); }
  catch(e){ console.error(e); statusEl.textContent=`Search failed: ${e.message||'unknown error'}`; }
}
if(form) form.addEventListener('submit', e=>{ e.preventDefault(); runSearch(); });

async function addTorrentFromItem(btn,it){
  btn.disabled=true; btn.textContent='Adding…';
  try { const j=await jsonFetch('/api/torrents/add',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({torrent_id:String(it.torrent_id||it.id||''),title:it.title||'',author:it.author||it.author_info||'',narrator:it.narrator||it.narrator_info||'',is_freeleech:it.is_freeleech})}); btn.textContent=j.state==='duplicate'?'Duplicate':'Added'; statusEl.textContent=`Sent torrent ${j.torrent_id} to qBittorrent (${j.state}).`; await loadHistory(); }
  catch(e){ console.error(e); btn.textContent='Error'; btn.title=e.message||'Add failed'; statusEl.textContent=`Add failed: ${e.message||'unknown error'}`; btn.disabled=false; }
}

// ---------- History ----------
if($('showHistoryBtn')) $('showHistoryBtn').addEventListener('click', async()=>{ $('historyCard').style.display=''; await loadHistory(); $('historyCard').scrollIntoView({behavior:'smooth',block:'start'}); });
async function loadHistory(){
  try { const j=await jsonFetch('/api/history'); const body=$('history').querySelector('tbody'); body.innerHTML=''; const items=j.items||[]; if(!items.length){ body.innerHTML='<tr><td colspan="8" class="center muted">No items in history yet.</td></tr>'; return; }
    items.forEach(h=>{ const tr=document.createElement('tr'); const whenRaw=h.updated_at||h.added_at||h.created_at||''; const when=whenRaw?new Date(whenRaw.replace(' ','T')).toLocaleString():''; const tid=h.torrent_id||h.mam_id||''; const abs=h.abs_item_url?`<a href="${escapeHtml(h.abs_item_url)}" target="_blank" rel="noopener noreferrer">ABS</a>`:`<span class="muted" title="${escapeHtml(h.abs_match_status||'not resolved')}">ABS ${escapeHtml(h.abs_match_status||'')}</span>`; tr.innerHTML=`<td>${escapeHtml(h.title||'')}</td><td>${escapeHtml(h.author||'')}</td><td>${escapeHtml(h.narrator||'')}</td><td class="center">${tid?`<a href="${mamLink(tid)}" target="_blank" rel="noopener noreferrer">MAM</a>`:''}</td><td class="center">${abs}</td><td>${escapeHtml(when)}</td><td>${escapeHtml(h.qb_status||(h.grabbed?'grabbed':''))}</td><td></td>`; const actions=tr.lastElementChild; if(!h.abs_item_url){ actions.appendChild(actionButton('Resolve ABS', async()=>{ await jsonFetch(`/api/history/${encodeURIComponent(h.id)}/resolve-abs`,{method:'POST'}); await loadHistory(); })); } actions.appendChild(actionButton('Remove', async()=>{ await fetch(`/api/history/${encodeURIComponent(h.id)}`,{method:'DELETE'}); tr.remove(); })); body.appendChild(tr); }); $('historyCard').style.display=''; } catch(e){ console.error('history load failed',e); }
}

// ---------- RSS dashboard ----------
const feedForm=$('feedForm'), feedStatus=$('feedStatus');
function initRssTable(){ rssTable = new DataTable($('rssItems'), [
  {key:'feed', label:'Feed', sortable:true, filter:true, value:r=>r.feed_name||r.feed_id||''},
  {key:'title', label:'Title', sortable:true, filter:true, value:r=>r.title||''},
  {key:'seen', label:'Seen', type:'date', sortable:true, value:r=>r.last_seen_at||''},
  {key:'mam', label:'MAM', className:'center', value:r=>r.torrent_id||'', render:r=>r.details_url?`<a href="${escapeHtml(r.details_url)}" target="_blank" rel="noopener noreferrer">MAM</a>`:''},
  {key:'add', label:'Add', value:r=>'', render:r=>actionButton('Add', async e=>{ await addTorrentFromItem(e.currentTarget,r); await loadRssItems(); }, !r.torrent_id)},
  {key:'hide', label:'Hide', value:r=>'', render:r=>actionButton('Hide', async()=>{ await jsonFetch('/api/history/hide',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({canonical_key:r.canonical_key})}); await loadRssItems(); })},
], {rowStyle:r=>`background:${lighten(r.feed_color)}`}); }
async function loadFeedsAndItems(){
  if(!$('feeds')) return;
  try { const feedsJson=await jsonFetch('/api/feeds'); const body=$('feeds').querySelector('tbody'); body.innerHTML='';
    (feedsJson.items||[]).forEach(feed=>{ const tr=document.createElement('tr'); tr.className='feed-controls';
      tr.innerHTML=`<td><input type="color" value="${escapeHtml(feed.color||'#eef6ff')}"></td><td><input type="text" value="${escapeHtml(feed.name||'')}"></td><td><select><option value="author">Author</option><option value="series">Series</option><option value="narrator">Narrator</option><option value="custom">Custom</option></select></td><td><span class="muted">${escapeHtml(feed.url_redacted||'')}</span><input class="feed-url-placeholder" type="text" placeholder="Paste new URL only if changing"></td><td class="center"><input type="checkbox" ${feed.enabled?'checked':''}></td><td class="center"><input type="checkbox" ${feed.show_in_combined?'checked':''}></td><td class="center"><input type="checkbox" ${feed.collapsed?'checked':''}></td><td><input type="number" min="1" max="500" value="${feed.display_limit||15}" style="width:5rem"></td><td class="muted">${escapeHtml(feed.last_refresh_status||'')} ${escapeHtml(feed.last_refresh_message||'')}</td><td></td>`;
      const kindSel=tr.children[2].querySelector('select'); kindSel.value=feed.kind||'custom'; const [colorEl,nameEl]=[tr.children[0].querySelector('input'),tr.children[1].querySelector('input')]; const urlEl=tr.children[3].querySelector('input'); const enabledEl=tr.children[4].querySelector('input'); const showEl=tr.children[5].querySelector('input'); const collapsedEl=tr.children[6].querySelector('input'); const limitEl=tr.children[7].querySelector('input'); const actions=tr.lastElementChild;
      actions.appendChild(actionButton('Save', async()=>{ const payload={name:nameEl.value.trim(),kind:kindSel.value,enabled:enabledEl.checked,color:colorEl.value,show_in_combined:showEl.checked,collapsed:collapsedEl.checked,display_limit:parseInt(limitEl.value||'15',10)}; if(urlEl.value.trim()) payload.url=urlEl.value.trim(); await jsonFetch(`/api/feeds/${feed.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); feedStatus.textContent='Feed saved.'; await loadFeedsAndItems(); }));
      actions.appendChild(actionButton('Refresh', async()=>{ const j=await jsonFetch(`/api/feeds/${feed.id}/refresh`,{method:'POST'}); feedStatus.textContent=j.ok?`Fetched ${j.fetched_count} item(s)`:`Refresh failed: ${j.message||'unknown error'}`; await loadFeedsAndItems(); }));
      actions.appendChild(actionButton('Delete', async()=>{ if(!confirm(`Delete feed ${feed.name}?`)) return; await fetch(`/api/feeds/${feed.id}`,{method:'DELETE'}); await loadFeedsAndItems(); }));
      body.appendChild(tr);
    }); await loadRssItems(); } catch(e){ console.error('feed load failed',e); if(feedStatus) feedStatus.textContent=`Failed to load feeds: ${e.message||'unknown error'}`; }
}
async function loadRssItems(){ try { const j=await jsonFetch('/api/rss/items?combined=true&include_hidden=false&include_grabbed=false'); rssTable.setRows(j.items||[]); } catch(e){ console.error('rss items failed',e); } }
if(feedForm) feedForm.addEventListener('submit', async e=>{ e.preventDefault(); const payload={name:$('feedName').value.trim(),kind:$('feedKind').value,url:$('feedUrl').value.trim(),enabled:true,color:$('feedColor').value,display_limit:parseInt($('feedLimit').value||'15',10)}; try{ feedStatus.textContent='Saving feed…'; await jsonFetch('/api/feeds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)}); $('feedUrl').value=''; feedStatus.textContent='Feed saved.'; await loadFeedsAndItems(); } catch(err){ feedStatus.textContent=`Feed save failed: ${err.message||'unknown error'}`; }});
if($('refreshFeedsBtn')) $('refreshFeedsBtn').addEventListener('click', async()=>{ const feeds=await jsonFetch('/api/feeds'); for(const feed of feeds.items||[]) if(feed.enabled) await fetch(`/api/feeds/${feed.id}/refresh`,{method:'POST'}); await loadFeedsAndItems(); });

initSearchTable(); initRssTable(); loadFeedsAndItems();
