const state = {
  tab: 'discover', recipes: [], favorites: [], lists: [], settings: null,
  filters: {}, search: '', swipeBusy: false, swipeRecipes: [], dislikedRecipeIds: new Set(),
  authToken: localStorage.getItem('auth_token') || '', user: null, googleClientId: '',
};

const app = document.getElementById('app');

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.authToken) headers.Authorization = `Bearer ${state.authToken}`;
  const response = await fetch(url, { ...options, headers });
  const raw = await response.text();
  const data = raw ? JSON.parse(raw) : {};
  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('auth_token');
      state.authToken = '';
      render();
    }
    throw new Error(data.error || `HTTP ${response.status}`);
  }
  return data;
}

const api = {
  get: (u) => request(u),
  post: (u, b) => request(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  put: (u, b) => request(u, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  patch: (u, b) => request(u, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  delete: (u) => request(u, { method: 'DELETE' }),
};

function nav() {
  const tabs = [['discover', '🌿', 'Entdecken'], ['swipe', '🔥', 'Swipe'], ['favorites', '💚', 'Favoriten'], ['lists', '🛒', 'Listen'], ['profile', '👤', 'Profil']];
  return `<div class="bottom-nav">${tabs.map(([id, icon, title]) => `<div class="nav-btn ${state.tab === id ? 'active' : ''}" data-tab="${id}">${icon}<br>${title}</div>`).join('')}</div>`;
}
function header(title, right = '') { return `<div class="header"><h1>${title}</h1><div>${right}</div></div>`; }
function card(r) { return `<div class="card" data-recipe="${r.id}"><div class="recipe-img">${r.image}</div><div class="card-title">${r.name}</div><div class="small">${r.duration} Min · ${r.ingredients_count} Zutaten</div></div>`; }
function queue() { return state.swipeRecipes.filter((r) => !state.dislikedRecipeIds.has(r.id) && !state.favorites.some((f) => f.id === r.id)); }

function renderLogin() {
  return `<div class="phone">${header('Anmelden')}<div class="empty-state"><h2>Google Login</h2><p>Melde dich an, damit Favoriten und Einkaufslisten accountbasiert gespeichert werden.</p><div id="googleSignIn"></div>${!state.googleClientId ? '<p class="small">GOOGLE_CLIENT_ID fehlt am Server.</p>' : ''}</div></div>`;
}

function renderDiscover() {
  return `${header('Heute kochen')}<input class="search" id="searchInput" value="${state.search}" placeholder="Rezept suchen" /><div class="grid">${state.recipes.map(card).join('')}</div>`;
}
function renderSwipe() {
  const r = queue()[0];
  if (!r) return `${header('Menu-Swipe')}<div class="empty-state"><h3>Keine Karten mehr</h3></div>`;
  return `${header('Menu-Swipe')}<div class="big-card"><div class="big-media">${r.image}</div><h2>${r.name}</h2><div class="actions"><div class="circle dislike" id="swipeDislike">✕</div><div class="circle like" id="swipeLike">♥</div></div></div>`;
}
function renderFavorites() {
  return `${header('Favoriten')}<div class="grid">${state.favorites.map(card).join('')}</div>`;
}
function renderLists() {
  return `${header('Einkaufsliste')}<div class="list-overview"><button class="btn new-list-button" id="newList">＋ Neue Liste erstellen</button></div>${state.lists.map((l) => `<div class="list-card" data-list="${l.id}"><div class="list-color" style="background:${l.color}"></div><div class="list-main"><h3>${l.name}</h3><div class="list-count">${(l.items || []).length} Zutaten</div></div></div>`).join('')}`;
}
function renderProfile() {
  const s = state.settings;
  return `${header('Profil')}<div class="profile"><div class="avatar" id="changeAvatar">${s.profile_image}</div><h2>${s.username}</h2><p class="small">${state.user?.email || ''}</p></div><div class="stats"><div class="card"><h2>${state.favorites.length} ♥</h2></div><div class="card"><h2>${state.lists.length} 🛒</h2></div></div><div class="list-item" id="logout">↩ Logout</div>`;
}

function render() {
  if (!state.authToken) {
    app.innerHTML = `${renderLogin()}<div id="modalRoot"></div>`;
    initGoogleButton();
    return;
  }
  let content = renderDiscover();
  if (state.tab === 'swipe') content = renderSwipe();
  if (state.tab === 'favorites') content = renderFavorites();
  if (state.tab === 'lists') content = renderLists();
  if (state.tab === 'profile') content = renderProfile();
  app.innerHTML = `<div class="phone">${content}</div>${nav()}<div id="modalRoot"></div>`;
  bind();
}

async function reloadData() {
  if (!state.authToken) return render();
  const q = new URLSearchParams({ search: state.search });
  state.recipes = await api.get(`/api/recipes?${q}`);
  state.swipeRecipes = await api.get(`/api/swipe-recipes?${q}`);
  state.favorites = await api.get('/api/favorites');
  state.dislikedRecipeIds = new Set(await api.get('/api/dislikes'));
  state.lists = await api.get('/api/lists');
  state.settings = await api.get('/api/settings');
  state.user = await api.get('/api/auth/me');
  render();
}

async function openRecipe(id) {
  const recipe = [...state.recipes, ...state.favorites].find((r) => r.id === Number(id));
  if (!recipe) return;
  document.getElementById('modalRoot').innerHTML = `<div class="modal"><div class="modal-content"><button class="btn" id="closeModal">← Zurück</button><h2>${recipe.name}</h2><p>${recipe.description || ''}</p><button class="btn" id="likeRecipe">♥ Favorit</button><button class="btn" id="dislikeRecipe">✕ Ablehnen</button></div></div>`;
  document.getElementById('closeModal').onclick = () => { document.getElementById('modalRoot').innerHTML = ''; };
  document.getElementById('likeRecipe').onclick = async () => { await api.post(`/api/recipes/${recipe.id}/like`); await reloadData(); };
  document.getElementById('dislikeRecipe').onclick = async () => { await api.post(`/api/recipes/${recipe.id}/dislike`); await reloadData(); };
}

async function openListEditor(id) {
  const list = await api.get(`/api/lists/${id}`);
  document.getElementById('modalRoot').innerHTML = `<div class="modal"><div class="modal-content"><button class="btn" id="closeModal">← Zurück</button><h2>${list.name}</h2>${list.items.map((it, i) => `<div class="list-item"><label><input type="checkbox" data-check="${i}" ${it.checked ? 'checked' : ''}/> ${it.name}</label></div>`).join('')}<button class="btn" id="saveList">Speichern</button></div></div>`;
  document.getElementById('closeModal').onclick = () => { document.getElementById('modalRoot').innerHTML = ''; };
  document.getElementById('saveList').onclick = async () => {
    const items = list.items.map((it, i) => ({ ...it, checked: document.querySelector(`[data-check="${i}"]`).checked }));
    await api.put(`/api/lists/${list.id}`, { name: list.name, items });
    await reloadData();
  };
}

function bind() {
  document.querySelectorAll('.nav-btn').forEach((btn) => btn.onclick = async () => { state.tab = btn.dataset.tab; render(); });
  const si = document.getElementById('searchInput'); if (si) si.oninput = async (e) => { state.search = e.target.value; await reloadData(); };
  document.querySelectorAll('[data-recipe]').forEach((el) => el.onclick = () => openRecipe(el.dataset.recipe));
  const sl = document.getElementById('swipeLike'); if (sl) sl.onclick = async () => { const r = queue()[0]; if (r) { await api.post(`/api/recipes/${r.id}/like`); await reloadData(); } };
  const sd = document.getElementById('swipeDislike'); if (sd) sd.onclick = async () => { const r = queue()[0]; if (r) { await api.post(`/api/recipes/${r.id}/dislike`); await reloadData(); } };
  document.querySelectorAll('[data-list]').forEach((el) => el.onclick = () => openListEditor(el.dataset.list));
  const nl = document.getElementById('newList'); if (nl) nl.onclick = async () => { const name = prompt('Name der Liste'); if (name) { await api.post('/api/lists', { name, color: '#7ed6df' }); await reloadData(); } };
  const ca = document.getElementById('changeAvatar'); if (ca) ca.onclick = async () => { const e = prompt('Profilbild Emoji', state.settings.profile_image); if (e) { await api.patch('/api/settings', { profile_image: e }); await reloadData(); } };
  const lo = document.getElementById('logout'); if (lo) lo.onclick = async () => { await api.post('/api/auth/logout', {}); localStorage.removeItem('auth_token'); state.authToken = ''; render(); };
}

function initGoogleButton() {
  if (!state.googleClientId || !window.google || !window.google.accounts || !document.getElementById('googleSignIn')) return;
  window.google.accounts.id.initialize({
    client_id: state.googleClientId,
    callback: async ({ credential }) => {
      const res = await api.post('/api/auth/google', { credential });
      state.authToken = res.token;
      localStorage.setItem('auth_token', res.token);
      await reloadData();
    },
  });
  window.google.accounts.id.renderButton(document.getElementById('googleSignIn'), { theme: 'outline', size: 'large', text: 'signin_with' });
}

async function bootstrap() {
  const cfg = await fetch('/api/config').then((r) => r.json()).catch(() => ({}));
  state.googleClientId = cfg.googleClientId || '';
  if (state.authToken) {
    try { await reloadData(); return; } catch (e) { localStorage.removeItem('auth_token'); state.authToken = ''; }
  }
  render();
}

bootstrap();
