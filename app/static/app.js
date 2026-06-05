// ---------- DOM lookups ----------
const form = document.getElementById('searchForm');
const q = document.getElementById('q');
const sortSel = document.getElementById('sort');
const perpageSel = document.getElementById('perpage');
const statusEl = document.getElementById('status');
const table = document.getElementById('results');
const tbody = table.querySelector('tbody');
const showHistoryBtn = document.getElementById('showHistoryBtn');

// Focus the search box
if (q) q.focus();

// ---------- Health check ----------
(async () => {
  try {
    const r = await fetch('/health');
    const j = await r.json();
    document.getElementById('health').textContent = j.ok ? 'OK' : 'Not OK';
  } catch {
    document.getElementById('health').textContent = 'Error';
  }
})();

// ---------- Show History (even without searching) ----------
if (showHistoryBtn) {
  showHistoryBtn.addEventListener('click', async () => {
    const card = document.getElementById('historyCard');
    card.style.display = '';           // reveal card
    await loadHistory();               // populate
    card.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
}

// ---------- Submit handler (Enter or button) ----------
if (form) {
  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    await runSearch();
  });
}

// ---------- Search flow ----------
async function runSearch() {
  const text = (q?.value || '').trim();
  const sortType = (sortSel?.value) || 'default';
  const perpage = parseInt(perpageSel?.value || '25', 10);

  statusEl.textContent = 'Searching…';
  table.style.display = 'none';
  tbody.innerHTML = '';

  try {
    const params = new URLSearchParams({ q: text, perpage: String(perpage) });
    const resp = await fetch(`/api/search?${params.toString()}`);
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();

    const rows = data.items || data.results || [];
    if (!rows.length) {
      statusEl.textContent = 'No results.';
      return;
    }

    rows.forEach((it) => {
      const tr = document.createElement('tr');
      const sl = `${it.seeders ?? '-'} / ${it.leechers ?? '-'}`;

      // Add-to-qB button
      const addBtn = document.createElement('button');
      addBtn.textContent = 'Add';
      // enable if we have a direct dl hash OR at least an id
      addBtn.disabled = !(it.torrent_id || it.id);
      addBtn.addEventListener('click', async () => {
        addBtn.disabled = true;
        addBtn.textContent = 'Adding…';
        try {
          const resp = await fetch('/api/torrents/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              torrent_id: String(it.torrent_id || it.id || ''),
              title: it.title || '',
              author: it.author || it.author_info || '',
              narrator: it.narrator || it.narrator_info || '',
              is_freeleech: it.is_freeleech
            })
          });
          if (!resp.ok) {
            let msg = `HTTP ${resp.status}`;
            try {
              const j = await resp.json();
              if (j?.detail) msg += ` — ${j.detail}`;
            } catch {}
            throw new Error(msg);
          }
          addBtn.textContent = 'Added';
          await loadHistory();
        } catch (e) {
          console.error(e);
          addBtn.textContent = 'Error';
          addBtn.disabled = false;
        }
      });

      // Torrent details link on MAM
      const detailsId = it.torrent_id || it.id;
      const detailsURL = detailsId ? `https://www.myanonamouse.net/t/${encodeURIComponent(detailsId)}` : '';

      tr.innerHTML = `
        <td>${escapeHtml(it.title || '')}</td>
        <td>${escapeHtml(it.author || it.author_info || '')}</td>
        <td>${escapeHtml(it.narrator || it.narrator_info || '')}</td>
        <td>${escapeHtml(it.format || '')}</td>
        <td class="right">${formatSize(it.size)}</td>
        <td class="right">${sl}</td>
        <td>${escapeHtml(it.uploaded_at || it.added || '')}</td>
        <td class="center">
          ${detailsURL ? `<a href="${detailsURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}
        </td>
        <td></td>
      `;
      tr.lastElementChild.appendChild(addBtn);
      tbody.appendChild(tr);
    });

    table.style.display = '';
    statusEl.textContent = `${rows.length} results shown`;
    await loadHistory();
  } catch (e) {
    console.error(e);
    statusEl.textContent = 'Search failed.';
  }
}

// ---------- Helpers ----------
function escapeHtml(s) {
  return (s || '').toString()
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatSize(sz) {
  if (sz == null || sz === '') return '';
  const n = Number(sz);
  if (!Number.isFinite(n)) return String(sz);
  const units = ['B','KB','MB','GB','TB'];
  let i = 0, x = n;
  while (x >= 1024 && i < units.length - 1) { x /= 1024; i++; }
  return `${x.toFixed(1)} ${units[i]}`;
}

async function loadHistory() {
  try {
    const r = await fetch('/api/history');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const j = await r.json();

    const card = document.getElementById('historyCard');
    const hist = document.getElementById('history');
    const htbody = hist.querySelector('tbody');
    htbody.innerHTML = '';

    const items = j.items || [];

    if (!items.length) {
      const colSpan = hist.querySelector('thead tr').children.length;
      const tr = document.createElement('tr');
      tr.className = 'empty';
      tr.innerHTML = `<td colspan="${colSpan}" class="center muted">No items in history yet.</td>`;
      htbody.appendChild(tr);
      card.style.display = '';
      return;
    }

    items.forEach((h) => {
      const tr = document.createElement('tr');
      const whenRaw = h.updated_at || h.added_at || h.created_at || '';
      const when = whenRaw ? new Date(whenRaw.replace(' ', 'T')).toLocaleString() : '';
      const torrentId = h.torrent_id || h.mam_id || '';
      const linkURL = torrentId ? `https://www.myanonamouse.net/t/${encodeURIComponent(torrentId)}` : '';

      const rmBtn = document.createElement('button');
      rmBtn.textContent = 'Remove';
      rmBtn.addEventListener('click', async () => {
        rmBtn.disabled = true;
        try {
          const resp = await fetch(`/api/history/${encodeURIComponent(h.id)}`, { method: 'DELETE' });
          if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
          tr.remove();
          if (!htbody.children.length) {
            const colSpan = hist.querySelector('thead tr').children.length;
            const emptyTr = document.createElement('tr');
            emptyTr.className = 'empty';
            emptyTr.innerHTML = `<td colspan="${colSpan}" class="center muted">No items in history yet.</td>`;
            htbody.appendChild(emptyTr);
          }
        } catch (e) {
          console.error('remove failed', e);
          rmBtn.disabled = false;
        }
      });

      tr.innerHTML = `
        <td>${escapeHtml(h.title || '')}</td>
        <td>${escapeHtml(h.author || '')}</td>
        <td>${escapeHtml(h.narrator || '')}</td>
        <td class="center">${linkURL ? `<a href="${linkURL}" target="_blank" rel="noopener noreferrer" title="Open on MAM">🔗</a>` : ''}</td>
        <td>${escapeHtml(when)}</td>
        <td>${escapeHtml(h.qb_status || (h.grabbed ? 'grabbed' : ''))}</td>
        <td></td>
      `;
      tr.lastElementChild.appendChild(rmBtn);
      htbody.appendChild(tr);
    });

    card.style.display = '';
  } catch (e) {
    console.error('history load failed', e);
  }
}


// ---------- MAM RSS dashboard ----------
const feedForm = document.getElementById('feedForm');
const feedStatus = document.getElementById('feedStatus');
const refreshFeedsBtn = document.getElementById('refreshFeedsBtn');

function cellText(tr, text) {
  const td = document.createElement('td');
  td.textContent = text || '';
  tr.appendChild(td);
  return td;
}

async function loadFeedsAndItems() {
  if (!document.getElementById('feeds')) return;
  try {
    const feedsResp = await fetch('/api/feeds');
    const feedsJson = await feedsResp.json();
    const feedsBody = document.querySelector('#feeds tbody');
    feedsBody.innerHTML = '';
    for (const feed of (feedsJson.items || [])) {
      const tr = document.createElement('tr');
      cellText(tr, feed.name);
      cellText(tr, feed.kind);
      cellText(tr, feed.url_redacted);
      const action = document.createElement('td');
      const btn = document.createElement('button');
      btn.textContent = 'Refresh';
      btn.addEventListener('click', async () => {
        btn.disabled = true;
        feedStatus.textContent = `Refreshing ${feed.name}…`;
        try {
          const r = await fetch(`/api/feeds/${encodeURIComponent(feed.id)}/refresh`, { method: 'POST' });
          const j = await r.json();
          feedStatus.textContent = j.ok ? `Fetched ${j.fetched_count} item(s)` : `Refresh failed: ${j.message || 'unknown error'}`;
          await loadRssItems();
        } finally {
          btn.disabled = false;
        }
      });
      action.appendChild(btn);
      tr.appendChild(action);
      feedsBody.appendChild(tr);
    }
    await loadRssItems();
  } catch (e) {
    console.error('feed load failed', e);
    if (feedStatus) feedStatus.textContent = 'Failed to load feeds.';
  }
}

async function loadRssItems() {
  const table = document.getElementById('rssItems');
  if (!table) return;
  const r = await fetch('/api/rss/items');
  const j = await r.json();
  const body = table.querySelector('tbody');
  body.innerHTML = '';
  for (const item of (j.items || [])) {
    if (item.grabbed || item.hidden) continue;
    const tr = document.createElement('tr');
    cellText(tr, item.title);
    cellText(tr, String(item.feed_id || ''));
    const linkTd = document.createElement('td');
    if (item.details_url) {
      const a = document.createElement('a');
      a.href = item.details_url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = '🔗';
      linkTd.appendChild(a);
    }
    tr.appendChild(linkTd);
    const addTd = document.createElement('td');
    const addBtn = document.createElement('button');
    addBtn.textContent = 'Add';
    addBtn.disabled = !item.torrent_id;
    addBtn.addEventListener('click', async () => {
      addBtn.disabled = true;
      addBtn.textContent = 'Adding…';
      const resp = await fetch('/api/torrents/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ torrent_id: item.torrent_id, title: item.title })
      });
      addBtn.textContent = resp.ok ? 'Added' : 'Error';
      await loadRssItems();
      await loadHistory();
    });
    addTd.appendChild(addBtn);
    tr.appendChild(addTd);
    const hideTd = document.createElement('td');
    const hideBtn = document.createElement('button');
    hideBtn.textContent = 'Hide';
    hideBtn.addEventListener('click', async () => {
      await fetch('/api/history/hide', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ canonical_key: item.canonical_key })
      });
      await loadRssItems();
    });
    hideTd.appendChild(hideBtn);
    tr.appendChild(hideTd);
    body.appendChild(tr);
  }
}

if (feedForm) {
  feedForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
      name: document.getElementById('feedName').value.trim(),
      kind: document.getElementById('feedKind').value,
      url: document.getElementById('feedUrl').value.trim(),
      enabled: true
    };
    feedStatus.textContent = 'Saving feed…';
    const resp = await fetch('/api/feeds', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!resp.ok) {
      feedStatus.textContent = 'Feed save failed.';
      return;
    }
    document.getElementById('feedUrl').value = '';
    feedStatus.textContent = 'Feed saved.';
    await loadFeedsAndItems();
  });
}

if (refreshFeedsBtn) {
  refreshFeedsBtn.addEventListener('click', async () => {
    const feedsResp = await fetch('/api/feeds');
    const feedsJson = await feedsResp.json();
    for (const feed of (feedsJson.items || [])) {
      await fetch(`/api/feeds/${encodeURIComponent(feed.id)}/refresh`, { method: 'POST' });
    }
    await loadFeedsAndItems();
  });
}

loadFeedsAndItems();
