'use strict';

// ------------------------------------------------------------------ helpers
const $ = id => document.getElementById(id);
const collator = new Intl.Collator('th', { numeric: true, sensitivity: 'base' });

const ICON_PATHS = {
  refresh: '<path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/>',
  message: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.5.5l3-3a5 5 0 0 0-7-7l-1.7 1.7"/><path d="M14 11a5 5 0 0 0-7.5-.5l-3 3a5 5 0 0 0 7 7l1.7-1.7"/>',
  monitor: '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M8 21h8M12 17v4"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  chev: '<path d="m9 6 6 6-6 6"/>',
  zip: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 11v6m-2-2 2 2 2-2"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/>',
  folderOpen: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v1H7.5a2 2 0 0 0-1.9 1.4L3 19z"/><path d="M3 19h15.5a2 2 0 0 0 1.9-1.4L22 12H7.5"/>',
  close: '<path d="M18 6 6 18M6 6l12 12"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5"/><path d="M5 21h14"/>',
  upload: '<path d="M12 21V9m-5 5 5-5 5 5"/><path d="M5 3h14"/>',
  back: '<path d="M19 12H5m7-7-7 7 7 7"/>',
  left: '<path d="m15 18-6-6 6-6"/>',
  right: '<path d="m9 18 6-6-6-6"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  play: '<path d="M7 4v16l13-8z" fill="currentColor"/>',
  folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" fill="currentColor" stroke="none"/>',
  image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-5-5L5 21"/>',
  video: '<rect x="2" y="5" width="15" height="14" rx="2"/><path d="m17 10 5-3v10l-5-3"/>',
  audio: '<path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/>',
  pdf: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
  doc: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h6"/>',
  sheet: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18"/>',
  slide: '<rect x="2" y="4" width="20" height="13" rx="2"/><path d="M12 17v4M8 21h8"/>',
  archive: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 3v2m0 2v2m0 2v2m-2 2h4v4h-4z"/>',
  text: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8M8 9h2"/>',
  apk: '<rect x="5" y="2" width="14" height="20" rx="2"/><path d="M11 18h2"/>',
  other: '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
};
const icon = name => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
  'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (ICON_PATHS[name] || ICON_PATHS.other) + '</svg>';

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function store(key, value) {
  try {
    if (value === undefined) return localStorage.getItem('nss.' + key);
    localStorage.setItem('nss.' + key, value);
  } catch (e) { /* private mode */ }
  return null;
}

function sizeText(n) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return (i ? n.toFixed(n < 10 ? 1 : 0) : n) + ' ' + units[i];
}

function dateText(seconds) {
  const d = new Date(seconds * 1000);
  const now = new Date();
  const time = d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit' });
  if (d.toDateString() === now.toDateString()) return 'วันนี้ ' + time;
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (d.toDateString() === yesterday.toDateString()) return 'เมื่อวาน ' + time;
  return d.toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: '2-digit' }) + ' ' + time;
}

const join = (...parts) => parts.filter(Boolean).join('/');
const relOf = item => join(item.dir, item.name);
const q = s => encodeURIComponent(s);
const fileUrl = (rel, inline, item) => '/files/' + rel.split('/').map(q).join('/') +
  (inline ? '?inline=1&v=' + Math.round(item.mtime) + '-' + item.size : '');
const extOf = name => (name.includes('.') ? name.split('.').pop().slice(0, 4).toUpperCase() : '');

async function api(url, options) {
  const res = await fetch(url, Object.assign({ cache: 'no-store' }, options));
  if (res.status === 401) { location.href = '/'; throw new Error('ต้องใส่ PIN ใหม่'); }
  const type = res.headers.get('Content-Type') || '';
  const data = type.includes('json') ? await res.json() : await res.text();
  if (!res.ok) {
    const error = new Error((data && data.error) || data || ('ผิดพลาด ' + res.status));
    error.status = res.status;
    throw error;
  }
  return data;
}

let toastTimer = 0;
function toast(message, ms = 3000) {
  const t = $('toast');
  t.textContent = message;
  t.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.hidden = true; }, ms);
}

function startDownload(url, name) {
  const a = el('a');
  a.href = url;
  if (name) a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
}

function errorText(e) {
  return e instanceof TypeError ? 'ต่อคอมไม่ได้ (คอมปิดอยู่ หรือไม่ได้อยู่ Wi-Fi เดียวกัน)' : e.message;
}

// ------------------------------------------------- history layers (back key)
// Android's back button closes the preview / selection first, then goes up a folder.
const layers = [];
let pendingPath = null;
function openLayer(close) {
  layers.push(close);
  history.pushState({ layer: layers.length }, '');
}
function closeLayer() {
  if (layers.length) history.back();
}
window.addEventListener('popstate', e => {
  const depth = (e.state && e.state.layer) || 0;
  while (layers.length > depth) layers.pop()();
  if (pendingPath !== null && !layers.length) {
    const path = pendingPath;
    pendingPath = null;
    go(path);
  }
});

// ------------------------------------------------------------------- state
const GROUPS = {
  image: ['image'], video: ['video'], pdf: ['pdf'], doc: ['doc', 'sheet', 'slide', 'text'],
  audio: ['audio'], archive: ['archive'], other: ['apk', 'other'],
};
const state = {
  path: '',
  items: [],
  search: '',
  results: null,
  truncated: false,
  kind: 'all',
  sort: store('sort') || 'date-desc',
  view: store('view') || 'list',
  shown: [],
  selected: new Map(),
  selecting: false,
};
let loadSeq = 0;

function pathFromHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  if (!raw) return '';
  try {
    return raw.split('/').filter(Boolean).map(decodeURIComponent).join('/');
  } catch (e) {
    return '';
  }
}

function go(path) {
  if (layers.length) {
    pendingPath = path;
    history.go(-layers.length);
    return;
  }
  if ($('q').value) { $('q').value = ''; state.search = ''; state.results = null; }
  const hash = '#/' + path.split('/').filter(Boolean).map(q).join('/');
  if (location.hash === hash || (!path && !location.hash)) load();
  else location.hash = hash;
}

// ---------------------------------------------------------------- loading
async function load(quiet) {
  state.path = pathFromHash();
  renderCrumbs();
  if (state.search) { runSearch(); return; }
  const seq = ++loadSeq;
  if (!quiet) showSkeleton();
  try {
    const data = await api('/api/list?path=' + q(state.path));
    if (seq !== loadSeq) return;
    state.items = data.items.map(item => Object.assign(item, { dir: state.path }));
    render();
  } catch (e) {
    if (seq !== loadSeq) return;
    if (e.status === 404 && state.path) { toast('ไม่พบโฟลเดอร์นี้แล้ว กลับหน้าแรก'); go(''); return; }
    state.items = [];
    render();
    $('status').textContent = errorText(e);
  }
}

async function runSearch() {
  const seq = ++loadSeq;
  $('status').textContent = 'กำลังค้นหา…';
  try {
    const data = await api('/api/search?q=' + q(state.search));
    if (seq !== loadSeq) return;
    state.results = data.items;
    state.truncated = data.truncated;
    render();
  } catch (e) {
    if (seq === loadSeq) $('status').textContent = errorText(e);
  }
}

function showSkeleton() {
  const list = $('list');
  list.className = 'list';
  list.replaceChildren(...Array.from({ length: 6 }, () => el('li', 'skeleton')));
  $('empty').hidden = true;
  $('status').textContent = '';
}

// --------------------------------------------------------------- rendering
function visibleItems() {
  let items = state.search ? (state.results || []) : state.items;
  if (state.kind !== 'all') items = items.filter(i => i.kind !== 'folder' && GROUPS[state.kind].includes(i.kind));
  const [field, direction] = state.sort.split('-');
  const sign = direction === 'asc' ? 1 : -1;
  const compare = {
    name: (a, b) => collator.compare(a.name, b.name),
    date: (a, b) => a.mtime - b.mtime,
    size: (a, b) => (a.size || 0) - (b.size || 0) || collator.compare(a.name, b.name),
  }[field];
  return items.slice().sort((a, b) => {
    const folderA = a.kind === 'folder', folderB = b.kind === 'folder';
    if (folderA !== folderB) return folderA ? -1 : 1;
    return sign * compare(a, b);
  });
}

function render() {
  const items = visibleItems();
  state.shown = items;
  const list = $('list');
  list.className = 'list' + (state.view === 'grid' ? ' grid' : '');
  list.replaceChildren(...items.map(rowFor));
  $('viewBtn').innerHTML = icon(state.view === 'grid' ? 'list' : 'grid');
  $('zipFolderBtn').hidden = !!state.search || !state.items.length;
  $('crumbs').scrollLeft = $('crumbs').scrollWidth;  // keep the current folder name visible

  const folders = items.filter(i => i.kind === 'folder').length;
  const files = items.length - folders;
  const total = items.reduce((sum, i) => sum + (i.size || 0), 0);
  const parts = [];
  if (folders) parts.push(folders + ' โฟลเดอร์');
  if (files) parts.push(files + ' ไฟล์ · ' + sizeText(total));
  $('status').textContent = state.search
    ? 'ค้นหา "' + state.search + '" ทุกโฟลเดอร์: พบ ' + items.length + ' รายการ' +
      (state.truncated ? ' (แสดงบางส่วน พิมพ์ให้เจาะจงขึ้น)' : '')
    : parts.join(' · ');

  const empty = !items.length;
  $('empty').hidden = !empty;
  if (empty) {
    $('emptyText').textContent = state.search
      ? 'ไม่พบไฟล์ที่ชื่อมีคำว่า "' + state.search + '"'
      : state.kind !== 'all' && (state.items.length)
        ? 'ไม่มีไฟล์ชนิดนี้ในโฟลเดอร์นี้'
        : 'โฟลเดอร์นี้ยังว่าง — ลากไฟล์ใส่โฟลเดอร์ Netdoi Share บนคอม หรือกด "ส่งไฟล์เข้าคอม"';
  }
}

function renderCrumbs() {
  const nav = $('crumbs');
  nav.replaceChildren();
  const parts = state.path ? state.path.split('/') : [];
  const home = el('button', '', 'หน้าแรก');
  home.type = 'button';
  home.addEventListener('click', () => go(''));
  nav.append(home);
  parts.forEach((part, i) => {
    const sep = el('span', 'sep');
    sep.innerHTML = icon('chev');
    const button = el('button', '', part);
    button.type = 'button';
    button.addEventListener('click', () => go(parts.slice(0, i + 1).join('/')));
    nav.append(sep, button);
  });
  nav.scrollLeft = nav.scrollWidth;
}

function fileIcon(item) {
  const box = el('div', 'ficon k-' + item.kind);
  box.innerHTML = icon(item.kind === 'folder' ? 'folder' : item.kind);
  const ext = item.kind === 'folder' ? '' : extOf(item.name);
  if (ext) {
    box.classList.add('with-ext');
    box.append(el('span', '', ext));
  }
  return box;
}

function highlight(target, text, needle) {
  const at = needle ? text.toLowerCase().indexOf(needle.toLowerCase()) : -1;
  if (at < 0) { target.textContent = text; return; }
  target.append(text.slice(0, at), el('mark', '', text.slice(at, at + needle.length)), text.slice(at + needle.length));
}

function rowFor(item) {
  const key = relOf(item);
  const row = el('li', 'row' + (state.selected.has(key) ? ' sel' : ''));
  row.dataset.key = key;

  const thumb = el('div', 'thumb');
  thumb.append(fileIcon(item));
  if (item.thumb) {
    const img = new Image();
    img.loading = 'lazy';
    img.decoding = 'async';
    img.alt = '';
    if (item.kind === 'pdf') img.className = 'page';
    img.src = '/api/thumb?path=' + q(key) + '&v=' + Math.round(item.mtime) + '-' + item.size;
    img.addEventListener('error', () => img.remove());
    thumb.append(img);
  }
  if (item.kind === 'video') {
    const badge = el('span', 'play-badge');
    badge.innerHTML = icon('play');
    thumb.append(badge);
  }
  const check = el('span', 'check');
  check.innerHTML = icon('check');
  thumb.append(check);

  const meta = el('div', 'meta');
  const name = el('div', 'name');
  highlight(name, item.name, state.search);
  const sub = [item.kind === 'folder'
    ? (item.count === null ? 'โฟลเดอร์' : item.count + ' รายการ')
    : sizeText(item.size), dateText(item.mtime)];
  if (state.search) sub.push('ใน ' + (item.dir || 'หน้าแรก'));
  meta.append(name, el('div', 'sub', sub.join(' · ')));

  let more;
  if (item.kind === 'folder') {
    more = el('button', 'icon-btn more');
    more.type = 'button';
    more.setAttribute('aria-label', 'โหลดโฟลเดอร์นี้เป็น zip');
    more.innerHTML = icon('zip');
    more.addEventListener('click', e => { e.stopPropagation(); requestZip(item.dir, [item.name]); });
  } else {
    more = el('a', 'icon-btn more');
    more.href = fileUrl(key);
    more.download = item.name;
    more.setAttribute('aria-label', 'โหลดไฟล์นี้');
    more.innerHTML = icon('download');
    more.addEventListener('click', e => { e.stopPropagation(); toast('เริ่มโหลด ' + item.name); });
  }
  row.append(thumb, meta, more);

  // Tap opens, tap on the picture or long-press selects (like the phone's Files app).
  let timer = 0, longPressed = false, startX = 0, startY = 0;
  row.addEventListener('pointerdown', e => {
    if (e.target.closest('.more')) return;
    longPressed = false;
    startX = e.clientX; startY = e.clientY;
    timer = setTimeout(() => {
      longPressed = true;
      if (navigator.vibrate) navigator.vibrate(15);
      toggleSelect(item);
    }, 450);
  });
  const cancel = () => clearTimeout(timer);
  row.addEventListener('pointermove', e => {
    if (Math.abs(e.clientX - startX) > 10 || Math.abs(e.clientY - startY) > 10) cancel();
  });
  row.addEventListener('pointerup', cancel);
  row.addEventListener('pointercancel', cancel);
  row.addEventListener('contextmenu', e => e.preventDefault());
  row.addEventListener('click', e => {
    if (e.target.closest('.more')) return;
    if (longPressed) { longPressed = false; return; }
    if (state.selecting || e.target.closest('.thumb')) toggleSelect(item);
    else if (item.kind === 'folder') go(key);
    else openViewer(item);
  });
  return row;
}

// --------------------------------------------------------------- selection
function toggleSelect(item) {
  const key = relOf(item);
  if (state.selected.has(key)) state.selected.delete(key);
  else state.selected.set(key, item);
  if (!state.selecting && state.selected.size) {
    state.selecting = true;
    document.body.classList.add('selecting');
    openLayer(endSelecting);
  }
  if (state.selecting && !state.selected.size) { closeLayer(); return; }
  updateSelection();
}

function endSelecting() {
  state.selecting = false;
  state.selected.clear();
  document.body.classList.remove('selecting');
  updateSelection();
}

function updateSelection() {
  document.querySelectorAll('#list .row').forEach(row => {
    row.classList.toggle('sel', state.selected.has(row.dataset.key));
  });
  $('selbar').hidden = !state.selecting;
  const items = [...state.selected.values()];
  const folders = items.filter(i => i.kind === 'folder').length;
  const size = items.reduce((sum, i) => sum + (i.size || 0), 0);
  $('selCount').textContent = 'เลือก ' + items.length;
  $('selSize').textContent = sizeText(size) + (folders ? ' + ' + folders + ' โฟลเดอร์' : '');
  const single = items.length === 1 && items[0].kind !== 'folder';
  $('selDownload').lastChild.textContent = single ? 'โหลด' : 'โหลด zip';
  const allShown = state.shown.length && state.shown.every(i => state.selected.has(relOf(i)));
  $('selAll').textContent = allShown ? 'ไม่เลือก' : 'ทั้งหมด';
}

$('selClose').addEventListener('click', closeLayer);
$('selAll').addEventListener('click', () => {
  const allShown = state.shown.every(i => state.selected.has(relOf(i)));
  state.shown.forEach(i => {
    if (allShown) state.selected.delete(relOf(i));
    else state.selected.set(relOf(i), i);
  });
  if (!state.selected.size) { closeLayer(); return; }
  updateSelection();
});
$('selDownload').addEventListener('click', () => {
  const items = [...state.selected.values()];
  if (!items.length) return;
  if (items.length === 1 && items[0].kind !== 'folder') {
    startDownload(fileUrl(relOf(items[0])), items[0].name);
    toast('เริ่มโหลด ' + items[0].name);
  } else {
    const sameDir = items.every(i => i.dir === items[0].dir);
    if (sameDir) requestZip(items[0].dir, items.map(i => i.name));
    else requestZip('', items.map(relOf));
  }
  closeLayer();
});

async function requestZip(dir, names) {
  if (!names.length) { toast('ไม่มีไฟล์ให้โหลด'); return; }
  toast('กำลังเตรียม zip…');
  try {
    const job = await api('/api/zip', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir, names }),
    });
    startDownload(job.url, job.filename);
    toast('เริ่มโหลด ' + job.filename + ' — ดูความคืบหน้าในแถบดาวน์โหลด', 5000);
  } catch (e) {
    toast(errorText(e), 5000);
  }
}

$('zipFolderBtn').addEventListener('click', () => {
  if (state.path) {
    const parts = state.path.split('/');
    const name = parts.pop();
    requestZip(parts.join('/'), [name]);
  } else {
    requestZip('', state.items.map(i => i.name));
  }
});

// ------------------------------------------------------------------ viewer
const viewer = { list: [], index: 0, seq: 0 };

function openViewer(item) {
  viewer.list = state.shown.filter(i => i.kind !== 'folder');
  viewer.index = Math.max(0, viewer.list.indexOf(item));
  $('viewer').hidden = false;
  document.body.style.overflow = 'hidden';
  openLayer(closeViewer);
  showViewerItem();
}

function stopMedia(container) {
  container.querySelectorAll('video, audio').forEach(media => {
    media.pause();
    media.removeAttribute('src');
    media.load();
  });
}

function closeViewer() {
  stopMedia($('vBody'));
  $('vBody').replaceChildren();
  $('viewer').hidden = true;
  document.body.style.overflow = '';
}

function infoCard(item, message, extra) {
  const card = el('div', 'vcard');
  const big = el('div', 'big');
  big.append(fileIcon(item));
  card.append(big, el('h3', '', item.name));
  if (extra) card.append(extra);
  card.append(el('p', '', message));
  const button = el('a', 'btn primary block');
  button.href = fileUrl(relOf(item));
  button.download = item.name;
  button.innerHTML = icon('download');
  button.append('โหลดไฟล์ (' + sizeText(item.size) + ')');
  card.append(button);
  return card;
}

const spinner = () => el('div', 'spinner');

async function showViewerItem() {
  const seq = ++viewer.seq;
  const item = viewer.list[viewer.index];
  const rel = relOf(item);
  const body = $('vBody');
  stopMedia(body);
  body.replaceChildren();
  body.classList.remove('zoom');
  body.scrollTop = 0;
  $('vName').textContent = item.name;
  $('vMeta').textContent = [sizeText(item.size), dateText(item.mtime),
    (viewer.index + 1) + '/' + viewer.list.length].join(' · ');
  $('vDownload').href = fileUrl(rel);
  $('vDownload').download = item.name;
  $('vPrev').hidden = viewer.index <= 0;
  $('vNext').hidden = viewer.index >= viewer.list.length - 1;

  if (item.preview === 'image') {
    const img = el('img', 'photo');
    img.alt = item.name;
    img.src = fileUrl(rel, true, item);
    img.addEventListener('click', () => body.classList.toggle('zoom'));
    img.addEventListener('error', () => body.replaceChildren(infoCard(item, 'แสดงรูปนี้ไม่ได้')));
    body.append(img);
  } else if (item.preview === 'video') {
    const video = el('video');
    video.controls = true;
    video.autoplay = true;
    video.playsInline = true;
    video.preload = 'metadata';
    video.src = fileUrl(rel, true, item);
    video.addEventListener('error', () => {
      if (seq === viewer.seq) body.replaceChildren(infoCard(item, 'เบราว์เซอร์เล่นวิดีโอนี้ไม่ได้ โหลดไปเปิดในแอปวิดีโอแทน'));
    });
    body.append(video);
  } else if (item.preview === 'audio') {
    const audio = el('audio');
    audio.controls = true;
    audio.autoplay = true;
    audio.src = fileUrl(rel, true, item);
    body.append(infoCard(item, 'กำลังเล่นเสียง', audio));
  } else if (item.preview === 'pdf') {
    body.append(spinner());
    try {
      const info = await api('/api/pdfinfo?path=' + q(rel));
      if (seq !== viewer.seq) return;
      const px = Math.min(window.innerWidth, 1100) * (window.devicePixelRatio || 1);
      const width = px <= 900 ? 900 : px <= 1400 ? 1400 : 2000;
      const pages = el('div', 'pages');
      const shown = Math.min(info.pages, 500);
      for (let i = 0; i < shown; i++) {
        const figure = el('figure');
        const img = el('img');
        img.loading = 'lazy';
        img.alt = 'หน้า ' + (i + 1);
        img.style.aspectRatio = '1 / 1.414';
        img.src = '/api/pdfpage?path=' + q(rel) + '&page=' + i + '&w=' + width +
          '&v=' + Math.round(item.mtime) + '-' + item.size;
        img.addEventListener('load', () => { img.style.aspectRatio = 'auto'; img.style.minHeight = '0'; });
        figure.append(img, el('figcaption', '', 'หน้า ' + (i + 1) + ' / ' + info.pages));
        pages.append(figure);
      }
      body.replaceChildren();
      if (info.pages > shown) body.append(el('div', 'vnote', 'แสดง ' + shown + ' หน้าแรก จาก ' + info.pages + ' หน้า โหลดไฟล์เพื่อดูทั้งหมด'));
      body.append(pages);
      body.classList.add('zoom');
    } catch (e) {
      if (seq === viewer.seq) body.replaceChildren(infoCard(item, errorText(e)));
    }
  } else if (item.preview === 'text') {
    body.append(spinner());
    try {
      const data = await api('/api/text?path=' + q(rel));
      if (seq !== viewer.seq) return;
      body.replaceChildren();
      body.classList.add('zoom');
      if (data.truncated) body.append(el('div', 'vnote', 'แสดงแค่ส่วนแรกของไฟล์ โหลดไฟล์เพื่อดูทั้งหมด'));
      body.append(el('pre', '', data.text));
    } catch (e) {
      if (seq === viewer.seq) body.replaceChildren(infoCard(item, errorText(e)));
    }
  } else {
    body.append(infoCard(item, 'ไฟล์ชนิดนี้เปิดดูในเว็บไม่ได้ โหลดแล้วเปิดด้วยแอปในโทรศัพท์'));
  }
}

function step(delta) {
  const next = viewer.index + delta;
  if (next < 0 || next >= viewer.list.length) return;
  viewer.index = next;
  showViewerItem();
}

$('vClose').addEventListener('click', closeLayer);
$('vPrev').addEventListener('click', () => step(-1));
$('vNext').addEventListener('click', () => step(1));
$('vDownload').addEventListener('click', () => toast('เริ่มโหลด ' + $('vName').textContent));
document.addEventListener('keydown', e => {
  if ($('viewer').hidden) return;
  if (e.key === 'ArrowLeft') step(-1);
  else if (e.key === 'ArrowRight') step(1);
  else if (e.key === 'Escape') closeLayer();
});
(() => {
  let x = 0, y = 0, touches = 0;
  const body = $('vBody');
  body.addEventListener('touchstart', e => {
    touches = e.touches.length;
    x = e.touches[0].clientX;
    y = e.touches[0].clientY;
  }, { passive: true });
  body.addEventListener('touchend', e => {
    if (touches !== 1 || body.classList.contains('zoom')) return;
    if (window.visualViewport && window.visualViewport.scale > 1.05) return;
    const dx = e.changedTouches[0].clientX - x;
    const dy = e.changedTouches[0].clientY - y;
    if (Math.abs(dx) > 60 && Math.abs(dy) < 60) step(dx < 0 ? 1 : -1);
  }, { passive: true });
})();

// ----------------------------------------------------------------- uploads
const upload = { active: false, cancelled: false, xhr: null };

function sendFile(file, dir, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    upload.xhr = xhr;
    xhr.open('POST', '/upload?dir=' + q(dir) + '&name=' + q(file.name));
    xhr.upload.onprogress = e => onProgress(e.loaded);
    xhr.onload = () => {
      if (xhr.status === 200) resolve(xhr.responseText);
      else if (xhr.status === 401) { location.href = '/'; reject(new Error('ต้องใส่ PIN ใหม่')); }
      else reject(new Error(xhr.responseText || 'ส่งไม่สำเร็จ'));
    };
    xhr.onerror = () => reject(new Error('การเชื่อมต่อหลุด'));
    xhr.onabort = () => reject(new Error('ยกเลิก'));
    xhr.send(file);
  });
}

async function startUploads(files, dir) {
  if (upload.active) { toast('รอให้ชุดก่อนส่งเสร็จก่อน'); return; }
  upload.active = true;
  upload.cancelled = false;
  const sheet = $('uploads');
  const total = files.reduce((sum, f) => sum + f.size, 0) || 1;
  let done = 0, ok = 0;
  const rows = files.map(file => {
    const row = el('li');
    const status = el('span', 's', 'รอ');
    row.append(el('span', 'n', file.name), status);
    return { row, status };
  });
  $('upList').replaceChildren(...rows.map(r => r.row));
  $('upTitle').textContent = 'กำลังส่ง ' + files.length + ' ไฟล์ (' + sizeText(total) + ')';
  $('upSub').textContent = 'ไปที่: ' + (dir || 'หน้าแรก') + ' · อย่าปิดจอระหว่างส่ง';
  $('upTotal').value = 0;
  $('upCancel').hidden = false;
  $('upHide').hidden = true;
  sheet.hidden = false;

  for (let i = 0; i < files.length; i++) {
    const { row, status } = rows[i];
    if (upload.cancelled) { status.textContent = 'ยกเลิก'; status.className = 's err'; continue; }
    status.textContent = '0%';
    row.scrollIntoView({ block: 'nearest' });
    try {
      const saved = await sendFile(files[i], dir, loaded => {
        status.textContent = Math.floor(loaded / (files[i].size || 1) * 100) + '%';
        $('upTotal').value = (done + loaded) / total * 100;
      });
      ok++;
      status.textContent = saved === files[i].name ? 'เสร็จ' : 'เสร็จ → ' + saved;
      status.className = 's ok';
    } catch (e) {
      status.textContent = e.message;
      status.className = 's err';
    }
    done += files[i].size;
    $('upTotal').value = done / total * 100;
  }

  upload.active = false;
  upload.xhr = null;
  $('upTitle').textContent = ok === files.length ? 'ส่งครบ ' + ok + ' ไฟล์' : 'สำเร็จ ' + ok + '/' + files.length + ' ไฟล์';
  $('upCancel').hidden = true;
  $('upHide').hidden = false;
  if (ok === files.length) setTimeout(() => { if (!upload.active) sheet.hidden = true; }, 4000);
  if (!state.search && state.path === dir) load(true);
}

$('pick').addEventListener('change', () => {
  const files = Array.from($('pick').files);
  $('pick').value = '';
  if (files.length) startUploads(files, state.path);
});
$('upCancel').addEventListener('click', () => {
  upload.cancelled = true;
  if (upload.xhr) upload.xhr.abort();
});
$('upHide').addEventListener('click', () => { $('uploads').hidden = true; });
window.addEventListener('beforeunload', e => { if (upload.active) e.preventDefault(); });

// ------------------------------------------------------------ screen shot
let shotUrl = null;
$('screenBtn').addEventListener('click', () => {
  $('screen').hidden = false;
  document.body.style.overflow = 'hidden';
  openLayer(() => { $('screen').hidden = true; document.body.style.overflow = ''; });
});
$('sClose').addEventListener('click', closeLayer);
$('sShot').addEventListener('click', () => $('sShot').parentElement.classList.toggle('zoom'));
$('sGrab').addEventListener('click', async () => {
  const grab = $('sGrab');
  grab.disabled = true;
  $('sMeta').textContent = 'กำลังบันทึก…';
  try {
    const res = await fetch('/capture', { method: 'POST', cache: 'no-store' });
    if (res.status === 401) { location.href = '/'; return; }
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    if (shotUrl) URL.revokeObjectURL(shotUrl);
    shotUrl = URL.createObjectURL(blob);
    const d = new Date();
    const p = n => String(n).padStart(2, '0');
    const stamp = d.getFullYear() + p(d.getMonth() + 1) + p(d.getDate()) + '_' +
      p(d.getHours()) + p(d.getMinutes()) + p(d.getSeconds());
    $('sShot').src = shotUrl;
    $('sShot').hidden = false;
    $('sSave').href = shotUrl;
    $('sSave').download = 'screen_' + stamp + '.png';
    $('sSave').hidden = false;
    $('sSaveBig').href = shotUrl;
    $('sSaveBig').download = $('sSave').download;
    $('sSaveBig').hidden = false;
    $('sGrab').lastChild.textContent = 'บันทึกภาพจอใหม่';
    $('sMeta').textContent = 'บันทึกเมื่อ ' + d.toLocaleTimeString('th-TH') + ' · แตะรูปเพื่อขยาย · กด ⤓ เก็บรูป';
  } catch (e) {
    $('sMeta').textContent = errorText(e);
  } finally {
    grab.disabled = false;
  }
});

// ------------------------------------------------------------- text / clipboard
let clipsTimer = 0;
let clipsKey = '';

async function copyText(text) {
  // navigator.clipboard needs https; on plain http fall back to the old copy command.
  if (navigator.clipboard && window.isSecureContext) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* fall back */ }
  }
  const area = el('textarea');
  area.value = text;
  area.setAttribute('readonly', '');
  area.style.position = 'fixed';
  area.style.top = '0';
  area.style.opacity = '0';
  document.body.append(area);
  area.select();
  area.setSelectionRange(0, text.length);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
  area.remove();
  return ok;
}

function renderClips(items) {
  const key = items.map(c => c.id).join(',');
  if (key === clipsKey) return;
  clipsKey = key;
  const list = $('tList');
  list.replaceChildren(...items.map(clip => {
    const item = el('li', 'clip');
    const head = el('div', 'clip-head');
    head.append(el('span', 'tag' + (clip.from === 'pc' ? ' pc' : ''), clip.from === 'pc' ? 'คอม → โทรศัพท์' : 'โทรศัพท์ → คอม'),
      el('span', '', dateText(clip.time)));
    const text = el('div', 'clip-text', clip.text);
    text.addEventListener('click', () => text.classList.toggle('open'));
    const actions = el('div', 'clip-actions');
    const copy = el('button', 'btn primary');
    copy.type = 'button';
    copy.innerHTML = icon('copy');
    copy.append('คัดลอก');
    copy.addEventListener('click', async () => {
      toast(await copyText(clip.text) ? 'คัดลอกแล้ว วางได้เลย' : 'คัดลอกไม่ได้ กดค้างที่ข้อความเพื่อเลือกเอง');
    });
    actions.append(copy);
    const url = (clip.text.match(/https?:\/\/[^\s<>"]+/) || [])[0];
    if (url) {
      const open = el('a', 'btn ghost');
      open.href = url;
      open.target = '_blank';
      open.rel = 'noopener noreferrer';
      open.innerHTML = icon('link');
      open.append('เปิดลิงก์');
      actions.append(open);
    }
    item.append(head, text, actions);
    return item;
  }));
  $('tMsg').textContent = items.length ? '' : 'ยังไม่มีข้อความ';
}

async function loadClips() {
  try {
    renderClips((await api('/api/clips')).items);
  } catch (e) {
    $('tMsg').textContent = errorText(e);
  }
}

$('textBtn').addEventListener('click', () => {
  $('texts').hidden = false;
  document.body.style.overflow = 'hidden';
  clipsKey = '';
  loadClips();
  clipsTimer = setInterval(() => { if (!document.hidden) loadClips(); }, 3000);
  openLayer(() => {
    clearInterval(clipsTimer);
    $('texts').hidden = true;
    document.body.style.overflow = '';
  });
});
$('tClose').addEventListener('click', closeLayer);

$('tSend').addEventListener('click', async () => {
  const text = $('tInput').value;
  if (!text.trim()) { toast('พิมพ์หรือวางข้อความก่อน'); $('tInput').focus(); return; }
  $('tSend').disabled = true;
  try {
    const result = await api('/api/clips', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    $('tInput').value = '';
    toast(result.copied ? 'ส่งแล้ว ที่คอมกด Ctrl+V วางได้เลย' : 'ส่งแล้ว (copy ลงคอมไม่ได้ เปิดดูจากประวัติ)', 4000);
    loadClips();
  } catch (e) {
    toast(errorText(e), 4000);
  } finally {
    $('tSend').disabled = false;
  }
});

$('tPull').addEventListener('click', async () => {
  $('tPull').disabled = true;
  try {
    const result = await api('/api/clips/pull', { method: 'POST' });
    await loadClips();
    toast(await copyText(result.item.text) ? 'ได้แล้ว และคัดลอกลงโทรศัพท์แล้ว' : 'ได้แล้ว กด "คัดลอก" ที่ข้อความ', 4000);
  } catch (e) {
    toast(errorText(e), 4000);
  } finally {
    $('tPull').disabled = false;
  }
});

$('tClear').addEventListener('click', async () => {
  if (!$('tList').children.length) return;
  if ($('tClear').dataset.armed !== '1') {
    $('tClear').dataset.armed = '1';
    $('tClear').textContent = 'กดอีกครั้งเพื่อล้าง';
    setTimeout(() => { $('tClear').dataset.armed = ''; $('tClear').textContent = 'ล้าง'; }, 3000);
    return;
  }
  $('tClear').dataset.armed = '';
  $('tClear').textContent = 'ล้าง';
  try {
    renderClips((await api('/api/clips/clear', { method: 'POST' })).items);
  } catch (e) {
    toast(errorText(e));
  }
});

// ------------------------------------------------------------ toolbar wiring
document.querySelectorAll('[data-icon]').forEach(node => {
  node.insertAdjacentHTML('afterbegin', icon(node.dataset.icon));
});

$('sort').value = state.sort;
$('sort').addEventListener('change', () => {
  state.sort = $('sort').value;
  store('sort', state.sort);
  render();
});
$('viewBtn').addEventListener('click', () => {
  state.view = state.view === 'grid' ? 'list' : 'grid';
  store('view', state.view);
  render();
});
$('chips').addEventListener('click', e => {
  const chip = e.target.closest('button[data-kind]');
  if (!chip) return;
  state.kind = chip.dataset.kind;
  document.querySelectorAll('#chips button').forEach(b => b.classList.toggle('on', b === chip));
  render();
});
$('refreshBtn').addEventListener('click', () => { load(); toast('โหลดรายการใหม่แล้ว', 1500); });

let searchTimer = 0;
$('q').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    state.search = $('q').value.trim();
    if (state.search) runSearch();
    else { state.results = null; load(true); }
  }, 300);
});

window.addEventListener('hashchange', () => load());
document.addEventListener('visibilitychange', () => {
  // Coming back to the browser after dropping files on the PC shows them right away.
  if (!document.hidden && !upload.active && !layers.length) load(true);
});

load();
