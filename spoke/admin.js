// Spoke admin GUI
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const PER_PAGE = 15;
const ICON = {text: '✍️', image: '📷', video: '🎬'};

const api = async (method, url, body) => {
  const r = await fetch(url, {method, headers: {'Content-Type': 'application/json'}, body: body ? JSON.stringify(body) : undefined});
  if (!r.ok) throw new Error(await r.text());
  return r.json();
};
const toast = msg => {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2600);
};
const esc = s => (s || '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));

let type = 'text', images = [], editing = null, editingSlug = '', page = 1, current = [];

// ---------- views ----------
function show(view) {
  $('#v-compose').hidden = view !== 'compose';
  $('#v-posts').hidden = view !== 'posts';
  $$('nav button').forEach(b => b.classList.toggle('on', b.dataset.view === view));
  history.replaceState(null, '', '#' + view);
  if (view === 'posts') loadPosts();
}
$$('nav button').forEach(b => b.onclick = () => {
  if (b.dataset.view === 'compose' && editing) reset();  // "New post" always starts blank
  show(b.dataset.view);
});

// ---------- composer ----------
function setType(t) {
  type = t;
  $$('.tabs button').forEach(b => b.classList.toggle('on', b.dataset.t === t));
  $('#photo').hidden = t !== 'image';
  $('#video').hidden = t !== 'video';
  $('#body').placeholder = t === 'text' ? "What's on your mind? (**bold**, *italic*, [link](https://…))" : 'Add a caption…';
}
$$('.tabs button').forEach(b => b.onclick = () => setType(b.dataset.t));

function reset() {
  editing = null; editingSlug = ''; images = [];
  ['title', 'body', 'tags', 'embed', 'slug'].forEach(i => $('#' + i).value = '');
  renderThumbs();
  $('#slugrow').hidden = true;
  $('#cancel').hidden = true;
  $('#post').textContent = 'Post';
}

async function save() {
  const p = {
    type, title: $('#title').value, body: $('#body').value, tags: $('#tags').value,
    images: images.map(file => ({file})), embed_code: $('#embed').value,
  };
  if (type === 'image' && !images.length) return toast('Add at least one photo');
  if (type === 'video' && !p.embed_code.trim()) return toast('Paste a video link or embed code');
  if (type === 'text' && !p.body.trim() && !p.title.trim()) return toast('Write something first');
  const was = editing, oldSlug = editingSlug;
  if (was) p.slug = $('#slug').value;
  let saved;
  try {
    saved = was ? await api('PUT', '/api/posts/' + was, p) : await api('POST', '/api/posts', p);
  } catch (e) { return toast(e.message); }
  reset();
  if (was) {
    toast(saved.slug !== oldSlug ? `Updated. New URL: /post/${saved.slug}/` : 'Updated');
    show('posts');
  } else {
    toast('Posted');
  }
}
$('#post').onclick = save;
$('#cancel').onclick = () => { reset(); show('posts'); };

// ---------- photos: upload, thumbnails, reorder ----------
const thumbSrc = f => '/thumbs/' + encodeURIComponent(f.replace(/\.[^.]+$/, '')) + '.webp';
function renderThumbs() {
  $('#thumbs').innerHTML = images.map((f, i) => `
    <div class="thumb" draggable="true" data-i="${i}">
      ${i ? '' : '<em>Cover</em>'}
      <img draggable="false" alt="" src="${thumbSrc(f)}" onerror="this.onerror=null;this.src='/media/${encodeURIComponent(f)}'">
      <span data-x="${i}" title="Remove">×</span>
      <div class="mv">
        <button type="button" data-i="${i}" data-m="-1" aria-label="Move earlier">‹</button>
        <button type="button" data-i="${i}" data-m="1" aria-label="Move later">›</button>
      </div>
    </div>`).join('');
}
async function upload(files) {
  for (const f of files) {
    if (!f.type.startsWith('image/')) continue;
    try {
      const r = await fetch('/api/upload', {method: 'POST', headers: {'X-Filename': encodeURIComponent(f.name)}, body: f});
      if (!r.ok) throw new Error(await r.text());
      images.push((await r.json()).file);
      renderThumbs();
    } catch (e) { toast(e.message); }
  }
}
const drop = $('#drop');
drop.onclick = () => $('#file').click();
$('#file').onchange = e => { upload(e.target.files); e.target.value = ''; };
drop.ondragover = e => { e.preventDefault(); drop.classList.add('over'); };
drop.ondragleave = () => drop.classList.remove('over');
drop.ondrop = e => { e.preventDefault(); drop.classList.remove('over'); upload(e.dataTransfer.files); };

const T = $('#thumbs');
let from = null;
const move = (a, b) => {
  if (b < 0 || b >= images.length || a === b) return;
  images.splice(b, 0, images.splice(a, 1)[0]);
  renderThumbs();
};
T.onclick = e => {
  const d = e.target.dataset;
  if (d.x !== undefined) { images.splice(+d.x, 1); renderThumbs(); }
  else if (d.m) move(+d.i, +d.i + +d.m);
};
T.ondragstart = e => {
  const t = e.target.closest('.thumb');
  if (!t) return;
  from = +t.dataset.i;
  t.classList.add('drag');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', '');
};
T.ondragover = e => {
  const t = e.target.closest('.thumb');
  if (from === null || !t) return;
  e.preventDefault();
  $$('.thumb.over').forEach(x => x.classList.remove('over'));
  t.classList.add('over');
};
T.ondrop = e => {
  e.preventDefault();
  const t = e.target.closest('.thumb'), f = from;
  from = null;
  if (t && f !== null) move(f, +t.dataset.i);
};
T.ondragend = () => { from = null; renderThumbs(); };

// ---------- your posts ----------
async function loadPosts() {
  const r = await api('GET', `/api/posts?page=${page}&per=${PER_PAGE}`);
  page = r.page;
  current = r.posts;
  $('#count').textContent = r.total ? `${r.total} post${r.total === 1 ? '' : 's'}` : '';
  $('#posts').innerHTML = r.posts.length ? r.posts.map(row).join('') : '<small>Nothing yet. Write your first post under New post.</small>';
  $('#pager').hidden = r.pages < 2;
  $('#pageinfo').textContent = `Page ${r.page} of ${r.pages}`;
  $('#newer').disabled = r.page <= 1;
  $('#older').disabled = r.page >= r.pages;
}
function row(p) {
  const label = p.title || p.body || (p.type === 'video' ? 'Video' : p.images.length + ' photo(s)');
  const icon = p.type === 'image' && p.images.length
    ? `<img class="pt" alt="" src="${thumbSrc(p.images[0].file)}" onerror="this.onerror=null;this.src='/media/${encodeURIComponent(p.images[0].file)}'">`
    : `<div class="ico">${ICON[p.type]}</div>`;
  return `<div class="item">${icon}<div class="t"><b>${esc(label)}</b>
    <small>${p.date.replace('T', ' ').slice(0, 16)}${p.tags.length ? ' · #' + p.tags.map(esc).join(' #') : ''}</small></div>
    <button data-e="${p.id}">Edit</button><button data-d="${p.id}">Delete</button></div>`;
}
$('#newer').onclick = () => { page--; loadPosts(); };
$('#older').onclick = () => { page++; loadPosts(); };
$('#posts').onclick = async e => {
  if (e.target.dataset.d) {
    if (!confirm('Delete this post?')) return;
    await api('DELETE', '/api/posts/' + e.target.dataset.d);
    toast('Deleted');
    loadPosts();
  } else if (e.target.dataset.e) {
    edit(e.target.dataset.e);
  }
};
function edit(id) {
  const p = current.find(x => x.id === id);
  if (!p) return;
  reset();
  setType(p.type);
  editing = id; editingSlug = p.slug;
  images = p.images.map(i => i.file);
  renderThumbs();
  $('#title').value = p.title;
  $('#body').value = p.body;
  $('#tags').value = p.tags.join(', ');
  $('#embed').value = p.embed_code;
  $('#slug').value = p.slug;
  $('#slugrow').hidden = false;
  $('#post').textContent = 'Save changes';
  $('#cancel').hidden = false;
  show('compose');
  scrollTo({top: 0});
}

// ---------- settings ----------
const FIELDS = ['title', 'description', 'author', 'posts_per_page', 'base_url'];
$('#gear').onclick = async () => {
  const {config: c, themes} = await api('GET', '/api/config');
  FIELDS.forEach(k => $('#c_' + k).value = c[k]);
  $('#c_theme').innerHTML = themes.map(t => `<option ${t === c.theme ? 'selected' : ''}>${t}</option>`).join('');
  $('#dlg').showModal();
};
$('#c_close').onclick = () => $('#dlg').close();
$('#c_save').onclick = async () => {
  const body = {theme: $('#c_theme').value};
  FIELDS.forEach(k => body[k] = $('#c_' + k).value);
  try { await api('PUT', '/api/config', body); $('#dlg').close(); toast('Settings saved'); }
  catch (e) { toast(e.message); }
};

// ---------- start ----------
setType('text');
show(location.hash === '#posts' ? 'posts' : 'compose');
api('GET', '/api/config').then(r => $('#ver').textContent = r.version);
