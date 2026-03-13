const state = {
  tab: 'discover',
  recipes: [],
  favorites: [],
  lists: [],
  settings: null,
  filters: {},
  search: '',
  swipeRecipes: [],
  dislikedRecipeIds: new Set(),
  authToken: localStorage.getItem('auth_token') || '',
  user: null,
  googleClientId: '',
  googleInitRetries: 0,
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
      state.user = null;
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
};

function nav() {
  const tabs = [['discover', '🌿', 'Entdecken'], ['swipe', '🔥', 'Swipe'], ['favorites', '💚', 'Favoriten'], ['lists', '🛒', 'Listen'], ['profile', '👤', 'Profil']];
  return `<div class="bottom-nav">${tabs.map(([id, icon, title]) => `<div class="nav-btn ${state.tab === id ? 'active' : ''}" data-tab="${id}">${icon}<br>${title}</div>`).join('')}</div>`;
}

function header(title, right = '') {
  return `<div class="header"><h1>${title}</h1><div>${right}</div></div>`;
}

function card(recipe) {
  return `<div class="card" data-recipe="${recipe.id}"><div class="recipe-img">${recipe.image}</div><div class="card-title">${recipe.name}</div><div class="small">${recipe.duration} Min · ${recipe.ingredients_count} Zutaten</div></div>`;
}

function queue() {
  return state.swipeRecipes.filter((r) => !state.dislikedRecipeIds.has(r.id) && !state.favorites.some((f) => f.id === r.id));
}

function renderLogin() {
  return `<div class="phone">${header('Anmelden')}<div class="empty-state"><h2>Google Login</h2><p>Melde dich an, damit Favoriten und Einkaufslisten accountbasiert gespeichert werden.</p><div id="googleSignIn"></div>${!state.googleClientId ? '<p class="small">GOOGLE_CLIENT_ID fehlt am Server.</p>' : ''}</div></div>`;
}

function renderDiscover() {
  return `${header('Heute kochen')}<input class="search" id="searchInput" value="${state.search}" placeholder="Rezept suchen" /><div class="grid">${state.recipes.map(card).join('')}</div>`;
}

function renderSwipe() {
  const recipe = queue()[0];
  if (!recipe) return `${header('Menu-Swipe')}<div class="empty-state"><h3>Keine Karten mehr</h3></div>`;
  return `${header('Menu-Swipe')}<div class="big-card"><div class="big-media">${recipe.image}</div><h2>${recipe.name}</h2><div class="actions"><div class="circle dislike" id="swipeDislike">✕</div><div class="circle like" id="swipeLike">♥</div></div></div>`;
}

function renderFavorites() {
  return `${header('Favoriten')}<div class="grid">${state.favorites.map(card).join('')}</div>`;
}

function renderLists() {
  return `${header('Einkaufsliste')}<div class="list-overview"><button class="btn new-list-button" id="newList">＋ Neue Liste erstellen</button></div>${state.lists.map((list) => `<div class="list-card" data-list="${list.id}"><div class="list-color" style="background:${list.color}"></div><div class="list-main"><h3>${list.name}</h3><div class="list-count">${(list.items || []).length} Zutaten</div></div></div>`).join('')}`;
}

function renderProfile() {
  const s = state.settings || { profile_image: '👤', username: 'Nutzer', diet: 'Alles' };
  return `${header('Profil')}<div class="profile"><div class="avatar" id="changeAvatar">${s.profile_image}</div><h2>${s.username}</h2><p class="small">${state.user?.email || 'Smart Meal Matching · Green Edition'}</p></div><div class="stats"><div class="card"><h2>${state.favorites.length} ♥</h2><div>Favoriten</div></div><div class="card"><h2>${state.lists.length} 🛒</h2><div>Einkaufslisten</div></div></div><div class="list-item"><span>Ernährung</span><strong>${s.diet}</strong></div><div class="list-item" id="logout">↩ Logout</div>`;
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

function bindSwipeGestures() {
  // No-op fallback; click buttons remain primary interaction.
}

function bind() {
  document.querySelectorAll('.nav-btn').forEach((btn) => {
    btn.onclick = () => { state.tab = btn.dataset.tab; render(); };
  });

  const searchInput = document.getElementById('searchInput');
  if (searchInput) searchInput.oninput = async (e) => { state.search = e.target.value; await reloadData(); };

  document.querySelectorAll('[data-recipe]').forEach((el) => { el.onclick = () => openRecipe(el.dataset.recipe); });

  const swipeLike = document.getElementById('swipeLike');
  if (swipeLike) swipeLike.onclick = async () => { const r = queue()[0]; if (r) { await api.post(`/api/recipes/${r.id}/like`); await reloadData(); } };

  const swipeDislike = document.getElementById('swipeDislike');
  if (swipeDislike) swipeDislike.onclick = async () => { const r = queue()[0]; if (r) { await api.post(`/api/recipes/${r.id}/dislike`); await reloadData(); } };

  document.querySelectorAll('[data-list]').forEach((el) => { el.onclick = () => openListEditor(el.dataset.list); });

  const newList = document.getElementById('newList');
  if (newList) newList.onclick = async () => { const name = prompt('Name der Liste'); if (name) { await api.post('/api/lists', { name, color: '#7ed6df' }); await reloadData(); } };

  const changeAvatar = document.getElementById('changeAvatar');
  if (changeAvatar) changeAvatar.onclick = async () => { const emoji = prompt('Profilbild Emoji', state.settings?.profile_image || '👤'); if (emoji) { await api.patch('/api/settings', { profile_image: emoji }); await reloadData(); } };

  const logout = document.getElementById('logout');
  if (logout) logout.onclick = async () => {
    await api.post('/api/auth/logout', {});
    localStorage.removeItem('auth_token');
    state.authToken = '';
    state.user = null;
    render();
  };

  bindSwipeGestures();
}

async function reloadData() {
  if (!state.authToken) {
    render();
    return false;
  }

  try {
    const query = new URLSearchParams({ search: state.search, ...Object.fromEntries(Object.entries(state.filters).map(([k, v]) => [k, String(v)])) });
    state.recipes = await api.get(`/api/recipes?${query}`);
    state.swipeRecipes = await api.get(`/api/swipe-recipes?${query}`);
    state.favorites = await api.get('/api/favorites');
    state.dislikedRecipeIds = new Set(await api.get('/api/dislikes'));
    state.lists = await api.get('/api/lists');
    state.settings = await api.get('/api/settings');
    state.user = await api.get('/api/auth/me');
    render();
    return true;
  } catch (error) {
    console.error('Fehler beim Laden der Daten:', error);
    alert(`Daten konnten nicht geladen werden: ${error.message}`);
    return false;
  }
}

function initGoogleButton() {
  if (!state.googleClientId || !document.getElementById('googleSignIn')) return;
  if (!window.google || !window.google.accounts) {
    if (state.googleInitRetries < 20) {
      state.googleInitRetries += 1;
      setTimeout(initGoogleButton, 250);
    }
    return;
  }
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
    const ok = await reloadData();
    if (ok) return;

    localStorage.removeItem('auth_token');
    state.authToken = '';
    state.user = null;
  }

  render();
}

bootstrap();
