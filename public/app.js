const state = {
  tab: 'discover',
  recipes: [],
  favorites: [],
  lists: [],
  settings: null,
  filters: {},
  search: '',
  selectedRecipe: null,
  selectedList: null,
  swipedRecipeIds: new Set(),
  swipeBusy: false
};

const api = {
  get: (u) => fetch(u).then((r) => r.json()),
  post: (u, b) => fetch(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then((r) => r.json()),
  put: (u, b) => fetch(u, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then((r) => r.json()),
  patch: (u, b) => fetch(u, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }).then((r) => r.json()),
  delete: (u) => fetch(u, { method: 'DELETE' }).then((r) => r.json())
};

const app = document.getElementById('app');

const getSwipeQueue = () => state.recipes.filter((recipe) => !state.swipedRecipeIds.has(recipe.id));
const currentSwipeRecipe = () => getSwipeQueue()[0];

function nav() {
  const tabs = [
    ['discover', '🌿', 'Entdecken'],
    ['swipe', '🔥', 'Swipe'],
    ['favorites', '💚', 'Favoriten'],
    ['lists', '🛒', 'Listen'],
    ['profile', '👤', 'Profil']
  ];
  return `<div class="bottom-nav">${tabs.map(([id, icon, title]) => `<div class="nav-btn ${state.tab === id ? 'active' : ''}" data-tab="${id}">${icon}<br>${title}</div>`).join('')}</div>`;
}

function header(title, right = '') { return `<div class="header"><h1>${title}</h1><div>${right}</div></div>`; }

function renderDiscover() {
  return `${header('Heute kochen', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <input class="search" placeholder="Rezept suchen" value="${state.search}" id="searchInput" />
    <div class="chip-row">
      <div class="chip">🌱 Vegetarisch</div>
      <div class="chip">⏱ Unter 20 Min</div>
      <div class="chip">🔥 High Protein</div>
      <div class="chip">🥗 Fresh Spring</div>
    </div>
    <div class="hero" data-tab-jump="swipe">
      <div class="hero-image"><h2 class="hero-title">Swipe dich zu deinem nächsten Lieblingsgericht</h2></div>
      <div class="hero-sub">Wie Tinder für Rezepte – aber mit seriösen Infos zu Zutaten, Kalorien und Zubereitung.</div>
    </div>
    <h2 class="section-title">Für dich ausgewählt</h2>
    <div class="grid">${state.recipes.map(recipeCard).join('')}</div>`;
}

function recipeCard(r) {
  return `<div class="card" data-recipe="${r.id}">
    <div class="recipe-img">${r.image}</div>
    <div class="card-title">${r.name}</div>
    <div class="small">${r.duration} Min · ${r.ingredients_count} Zutaten</div>
  </div>`;
}

function renderSwipe() {
  const queue = getSwipeQueue();
  const r = queue[0];
  if (!r) {
    return `${header('Menu-Swipe')}<div class="empty-state"><h3>Keine Karten mehr im Swipe-Deck</h3><p>Auf „Entdecken“ findest du weiterhin alle Rezepte.</p></div>`;
  }
  return `${header('Menu-Swipe', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <p class="small">${queue.length} Rezepte im Swipe-Deck</p>
    <div class="swipe-stage">
      <div class="big-card" data-recipe="${r.id}" id="swipeCard">
        <div class="swipe-badge swipe-badge-like">LIKE</div>
        <div class="swipe-badge swipe-badge-nope">NOPE</div>
        <div class="big-media"><div style="font-size:136px">${r.image}</div><div class="chip">Match 92%</div></div>
        <h2>${r.name}</h2>
        <p class="big-meta">⏱ ${r.duration} Min · 🧾 ${r.ingredients_count} Zutaten · 🍽 ${r.cuisine}</p>
        <p class="big-copy">Ausgewogen, schnell und alltagstauglich – mit klaren Nährwerten und Schritt-für-Schritt-Anleitung für ein professionelles Kocherlebnis.</p>
      </div>
    </div>
    <div class="actions">
      <div class="circle dislike" id="swipeDislike">✕</div>
      <div class="circle" id="swipeInfo">i</div>
      <div class="circle like" id="swipeLike">♥</div>
    </div>`;
}

function renderFavorites() {
  return `${header('Deine Favoriten', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <input class="search" placeholder="Rezept suchen" value="${state.search}" id="searchInput" />
    <div class="grid">${state.favorites.map(recipeCard).join('')}
      <div class="card" id="toSwipe"><div class="recipe-img">➕</div><div>Weitere Favoriten hinzufügen</div></div>
    </div>`;
}

function renderLists() {
  return `${header('Einkaufsliste')}
    ${state.lists.map((l) => `<div class="list-item" data-list="${l.id}" style="border-left:8px solid ${l.color}"><div><div class="small">${new Date(l.updated_at).toLocaleDateString('de-DE')} aktualisiert</div><h3>${l.name}</h3></div><button class="btn">✎</button></div>`).join('')}
    <div class="list-item" id="newList"><h3>Neue Liste erstellen</h3><div style="font-size:40px">＋</div></div>`;
}

function renderProfile() {
  const s = state.settings;
  return `${header('Profil', `<button class="btn" id="openSettings">⚙</button>`)}
  <div class="profile"><div class="avatar" id="changeAvatar">${s.profile_image}</div><h2>${s.username}</h2><p class="small">Smart Meal Matching · Green Edition</p></div>
  <div class="stats"><div class="card"><h2>${state.favorites.length} ♥</h2><div>Favoriten</div></div><div class="card"><h2>${state.lists.length} 🛒</h2><div>Einkaufslisten</div></div></div>
  <div class="stats"><div class="card" id="openExcluded">Das esse ich nicht</div><div class="card" id="openDiet">${s.diet}</div></div>
  <div class="list-item" id="openFeedback">❓ Hilfe und Feedback</div>
  <div class="list-item" id="openLegal">⋯ Sonstiges</div>`;
}

function render() {
  let content = '';
  if (state.tab === 'discover') content = renderDiscover();
  if (state.tab === 'swipe') content = renderSwipe();
  if (state.tab === 'favorites') content = renderFavorites();
  if (state.tab === 'lists') content = renderLists();
  if (state.tab === 'profile') content = renderProfile();
  app.innerHTML = `<div class="phone">${content}</div>${nav()}<div id="modalRoot"></div>`;
  bind();
}

function modal(html) {
  document.getElementById('modalRoot').innerHTML = `<div class="modal"><div class="modal-content">${html}</div></div>`;
  document.querySelector('.modal').onclick = (e) => {
    if (e.target.classList.contains('modal')) closeModal();
  };
}
function closeModal() { document.getElementById('modalRoot').innerHTML = ''; }

function openRecipe(id) {
  const r = [...state.recipes, ...state.favorites].find((x) => x.id === Number(id));
  if (!r) return;
  state.selectedRecipe = r;
  let portions = 2;
  const draw = () => {
    modal(`<button class="btn" id="closeModal">← Zurück</button>
    <div class="recipe-img" style="font-size:180px">${r.image}</div>
    <h1>${r.name}</h1>
    <p>${r.duration} Min · ${r.cuisine}</p>
    <div class="actions">
      <button class="btn" id="likeRecipe">♥ Mag ich</button>
      <button class="btn" id="dislikeRecipe">✕ Mag ich nicht</button>
      <button class="btn" id="jumpSteps">Schritte</button>
      <button class="btn" id="jumpNutrition">Nährwerte</button>
    </div>
    <h2>Portionen</h2><div class="row"><button class="btn" id="minusPortion">-</button><h2>${portions}</h2><button class="btn" id="plusPortion">+</button></div>
    <h2>Zutaten</h2>
    ${(r.ingredients || []).map((i) => `<div class="ingredient"><span>${i}</span></div>`).join('')}
    <button class="btn" id="addToList">Zur Einkaufsliste hinzufügen</button>
    <h2 id="nutrition">Nährwerte pro Portion</h2>
    <p>${r.nutrition.kcal} kcal · KH ${r.nutrition.carbs}g · Eiweiß ${r.nutrition.protein}g · Fett ${r.nutrition.fat}g</p>
    <h2 id="steps">Schritte</h2>
    ${r.steps.map((s, i) => `<p><b>Schritt ${i + 1}</b><br>${s}</p>`).join('')}`);

    document.getElementById('closeModal').onclick = closeModal;
    document.getElementById('plusPortion').onclick = () => { portions += 1; draw(); };
    document.getElementById('minusPortion').onclick = () => { portions = Math.max(1, portions - 1); draw(); };
    document.getElementById('jumpSteps').onclick = () => document.getElementById('steps').scrollIntoView({ behavior: 'smooth' });
    document.getElementById('jumpNutrition').onclick = () => document.getElementById('nutrition').scrollIntoView({ behavior: 'smooth' });
    document.getElementById('likeRecipe').onclick = async () => { await api.post(`/api/recipes/${r.id}/like`); state.swipedRecipeIds.add(r.id); await reloadData(); closeModal(); };
    document.getElementById('dislikeRecipe').onclick = async () => { await api.post(`/api/recipes/${r.id}/dislike`); state.swipedRecipeIds.add(r.id); await reloadData(); closeModal(); };
    document.getElementById('addToList').onclick = () => openAddToList(r.ingredients);
  };
  draw();
}

async function handleSwipeAction(action) {
  const recipe = currentSwipeRecipe();
  if (!recipe || state.swipeBusy) return;
  state.swipeBusy = true;

  const card = document.getElementById('swipeCard');
  if (card) {
    card.classList.add(action === 'like' ? 'fly-right' : 'fly-left');
    await new Promise((resolve) => setTimeout(resolve, 260));
  }

  if (action === 'like') await api.post(`/api/recipes/${recipe.id}/like`);
  state.swipedRecipeIds.add(recipe.id);
  state.swipeBusy = false;
  await reloadData();
}

function bindSwipeGestures() {
  const card = document.getElementById('swipeCard');
  if (!card) return;
  let startX = 0;
  let currentX = 0;
  let dragging = false;

  const setPos = (dx) => {
    const rotation = dx / 18;
    card.style.transform = `translateX(${dx}px) rotate(${rotation}deg)`;
    const like = card.querySelector('.swipe-badge-like');
    const nope = card.querySelector('.swipe-badge-nope');
    if (like && nope) {
      like.style.opacity = dx > 0 ? Math.min(dx / 90, 1) : 0;
      nope.style.opacity = dx < 0 ? Math.min(Math.abs(dx) / 90, 1) : 0;
    }
  };

  card.onpointerdown = (e) => {
    dragging = true;
    startX = e.clientX;
    card.setPointerCapture(e.pointerId);
    card.style.transition = 'none';
  };

  card.onpointermove = (e) => {
    if (!dragging || state.swipeBusy) return;
    currentX = e.clientX - startX;
    setPos(currentX);
  };

  card.onpointerup = async () => {
    dragging = false;
    card.style.transition = '';
    if (currentX > 120) {
      await handleSwipeAction('like');
    } else if (currentX < -120) {
      await handleSwipeAction('skip');
    } else {
      card.style.transform = '';
      const like = card.querySelector('.swipe-badge-like');
      const nope = card.querySelector('.swipe-badge-nope');
      if (like) like.style.opacity = '0';
      if (nope) nope.style.opacity = '0';
    }
    currentX = 0;
  };
}

function openFilter() {
  const f = state.filters;
  modal(`<div class="header"><button class="btn" id="closeModal">✕</button><h2>Filter</h2></div>
    <h3>Kategorie</h3><div class="row tags" id="catRow">${['Hauptgericht', 'Frühstück', 'Dinner', 'Nachtisch'].map((c) => `<button class="btn ${f.category === c ? 'active' : ''}" data-category="${c}">${c}</button>`).join('')}</div>
    <h3>Kalorien</h3><div class="row tags"><button class="btn ${f.maxCalories === 300 ? 'active' : ''}" data-cal="300">unter 300</button><button class="btn ${f.maxCalories === 400 ? 'active' : ''}" data-cal="400">unter 400</button><button class="btn ${f.maxCalories === 500 ? 'active' : ''}" data-cal="500">unter 500</button></div>
    <h3>Eiweiß</h3><div class="row tags"><button class="btn ${f.minProtein === 30 ? 'active' : ''}" data-pro="30">über 30</button><button class="btn ${f.minProtein === 50 ? 'active' : ''}" data-pro="50">über 50</button></div>
    <h3>Dauer</h3><div class="row tags"><button class="btn ${f.maxDuration === 15 ? 'active' : ''}" data-dur="15">&lt;15 Min</button><button class="btn ${f.maxDuration === 30 ? 'active' : ''}" data-dur="30">&lt;30 Min</button><button class="btn ${f.maxDuration === 60 ? 'active' : ''}" data-dur="60">&lt;1 Std</button></div>
    <button class="btn" id="applyFilter">Filter anwenden</button>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-category]').forEach((b) => b.onclick = () => { state.filters.category = b.dataset.category; openFilter(); });
  document.querySelectorAll('[data-cal]').forEach((b) => b.onclick = () => { state.filters.maxCalories = Number(b.dataset.cal); openFilter(); });
  document.querySelectorAll('[data-pro]').forEach((b) => b.onclick = () => { state.filters.minProtein = Number(b.dataset.pro); openFilter(); });
  document.querySelectorAll('[data-dur]').forEach((b) => b.onclick = () => { state.filters.maxDuration = Number(b.dataset.dur); openFilter(); });
  document.getElementById('applyFilter').onclick = async () => { await reloadData(); closeModal(); };
}

async function openListEditor(id) {
  const list = await api.get(`/api/lists/${id}`);
  const draw = () => {
    modal(`<button class="btn" id="closeModal">← Zurück</button><h2>${list.name}</h2><h3>Zutaten</h3>
    ${list.items.map((item, i) => `<div class="ingredient"><label><input type="checkbox" data-check="${i}" ${item.checked ? 'checked' : ''}> ${item.name}</label><button class="btn" data-remove="${i}">✕</button></div>`).join('')}
    <button class="btn" id="addItem">＋ Zutat hinzufügen</button>
    <div style="height:20px"></div>
    <button class="btn" id="saveList">Einkaufsliste speichern</button>
    <button class="btn" id="deleteList">Einkaufsliste löschen</button>`);
    document.getElementById('closeModal').onclick = closeModal;
    document.querySelectorAll('[data-check]').forEach((c) => c.onchange = () => { list.items[c.dataset.check].checked = c.checked; });
    document.querySelectorAll('[data-remove]').forEach((b) => b.onclick = () => { list.items.splice(Number(b.dataset.remove), 1); draw(); });
    document.getElementById('addItem').onclick = () => { const name = prompt('Zutat'); if (name) { list.items.push({ name, checked: false }); draw(); } };
    document.getElementById('saveList').onclick = async () => { await api.put(`/api/lists/${id}`, { name: list.name, items: list.items }); await reloadData(); closeModal(); };
    document.getElementById('deleteList').onclick = async () => { await api.delete(`/api/lists/${id}`); await reloadData(); closeModal(); };
  };
  draw();
}

function openNewList() {
  modal(`<div class="header"><button class="btn" id="closeModal">✕</button><button class="btn" id="saveNewList">Speichern</button></div>
    <h1>Neue Einkaufsliste erstellen</h1><label>Bezeichnung</label><input id="listName" />
    <label>Farbe</label><div class="row">${['#7ed6df', '#f06262', '#81de91', '#cde94f', '#cd59d8'].map((c) => `<button class="circle" style="background:${c};width:46px;height:46px" data-color="${c}"></button>`).join('')}</div>`);
  let chosen = '#7ed6df';
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-color]').forEach((b) => b.onclick = () => { chosen = b.dataset.color; });
  document.getElementById('saveNewList').onclick = async () => {
    const name = document.getElementById('listName').value.trim();
    if (!name) return;
    await api.post('/api/lists', { name, color: chosen });
    await reloadData();
    closeModal();
  };
}

function openSettings() {
  const s = state.settings;
  modal(`<button class="btn" id="closeModal">← Einstellungen schließen</button>
    <h2>Einstellungen</h2>
    <label>Nutzername</label><input id="username" value="${s.username}" />
    <label>Abo verwalten</label><div class="list-item">${s.manage_subscription_note}</div>
    <button class="btn" id="saveSettings">Speichern</button>
    <button class="btn" style="color:red" id="logout">Abmelden</button>
    <button class="btn" style="color:red" id="deleteAccount">Account löschen</button>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('saveSettings').onclick = async () => { await api.patch('/api/settings', { username: document.getElementById('username').value }); await reloadData(); closeModal(); };
  document.getElementById('logout').onclick = () => alert('Du wurdest abgemeldet (Demo).');
  document.getElementById('deleteAccount').onclick = () => alert('Account löschen ist in dieser Demo deaktiviert.');
}

function openExcluded() {
  modal(`<button class="btn" id="closeModal">← Zurück</button><h2>Das esse ich nicht</h2>
    <button class="btn" id="addExclude">＋ Zutat hinzufügen</button>
    ${(state.settings.excluded || []).map((e) => `<div class="list-item"><label><input type="checkbox" data-ex="${e.id}" ${e.active ? 'checked' : ''}> ${e.name}</label></div>`).join('')}`);
  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('addExclude').onclick = async () => { const name = prompt('Neue Zutat'); if (name) { await api.post('/api/excluded', { name }); await reloadData(); openExcluded(); } };
  document.querySelectorAll('[data-ex]').forEach((b) => b.onchange = async () => { await api.patch(`/api/excluded/${b.dataset.ex}`, { active: b.checked }); await reloadData(); });
}

function openDiet() {
  const options = ['Ich esse alles', 'Vegetarisch', 'Vegan', 'Low-Carb', 'High-Protein', 'Pescetarisch'];
  modal(`<button class="btn" id="closeModal">← Zurück</button><h2>Ernährungsform</h2>
    ${options.map((o) => `<div class="list-item"><label><input type="radio" name="diet" value="${o}" ${state.settings.diet === o ? 'checked' : ''}> ${o}</label></div>`).join('')}`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('input[name="diet"]').forEach((r) => r.onchange = async () => { await api.patch('/api/settings', { diet: r.value }); await reloadData(); openDiet(); });
}

function openFeedback() {
  modal(`<button class="btn" id="closeModal">← Zurück</button><h2>Hilfe und Feedback</h2>
    <label>E-Mail-Adresse</label><input id="fMail" />
    <label>Betreff</label><input id="fSub" />
    <label>Nachricht</label><textarea id="fMsg"></textarea>
    <button class="btn" id="sendFeedback">Abschicken</button>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('sendFeedback').onclick = async () => {
    await api.post('/api/feedback', {
      email: document.getElementById('fMail').value,
      subject: document.getElementById('fSub').value,
      message: document.getElementById('fMsg').value
    });
    alert('Danke für dein Feedback!');
    closeModal();
  };
}

function openLegal() {
  modal(`<button class="btn" id="closeModal">← Zurück</button><h2>Sonstiges</h2>
    <p><b>Nutzungsbedingungen</b><br>Dies ist ein Beispieltext für Nutzungsbedingungen.</p>
    <p><b>Datenschutzerklärung</b><br>Dies ist ein Beispieltext zum Datenschutz und zur Datenverarbeitung.</p>
    <p><b>Datenschutzeinstellungen</b><br>Hier könnten Cookie- und Tracking-Einstellungen verwaltet werden.</p>
    <p><b>AGB</b><br>Dies ist ein Beispieltext für allgemeine Geschäftsbedingungen.</p>`);
  document.getElementById('closeModal').onclick = closeModal;
}

async function openAddToList(ingredients) {
  const lists = await api.get('/api/lists');
  modal(`<button class="btn" id="closeModal">← Zurück</button><h2>Zu Einkaufsliste hinzufügen</h2>
    ${lists.map((l) => `<div class="list-item" data-add-list="${l.id}">${l.name}</div>`).join('')}`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-add-list]').forEach((b) => b.onclick = async () => {
    const list = await api.get(`/api/lists/${b.dataset.addList}`);
    ingredients.forEach((i) => list.items.push({ name: i, checked: false }));
    await api.put(`/api/lists/${list.id}`, { name: list.name, items: list.items });
    await reloadData();
    closeModal();
  });
}

function bind() {
  document.querySelectorAll('.nav-btn').forEach((btn) => btn.onclick = async () => { state.tab = btn.dataset.tab; await reloadData(false); });
  const heroJump = document.querySelector('[data-tab-jump="swipe"]');
  if (heroJump) heroJump.onclick = async () => { state.tab = 'swipe'; await reloadData(false); };
  document.querySelectorAll('[data-recipe]').forEach((el) => el.onclick = () => openRecipe(el.dataset.recipe));
  const si = document.getElementById('searchInput');
  if (si) si.oninput = async (e) => { state.search = e.target.value; await reloadData(false); };
  const openFilterBtn = document.getElementById('openFilter'); if (openFilterBtn) openFilterBtn.onclick = openFilter;
  const sl = document.getElementById('swipeLike'); if (sl) sl.onclick = async () => handleSwipeAction('like');
  const sd = document.getElementById('swipeDislike'); if (sd) sd.onclick = async () => handleSwipeAction('skip');
  const sii = document.getElementById('swipeInfo'); if (sii) sii.onclick = () => currentSwipeRecipe() && openRecipe(currentSwipeRecipe().id);
  const ts = document.getElementById('toSwipe'); if (ts) ts.onclick = async () => { state.tab = 'swipe'; await reloadData(false); };
  document.querySelectorAll('[data-list]').forEach((el) => el.onclick = () => openListEditor(el.dataset.list));
  const nl = document.getElementById('newList'); if (nl) nl.onclick = openNewList;
  const os = document.getElementById('openSettings'); if (os) os.onclick = openSettings;
  const oe = document.getElementById('openExcluded'); if (oe) oe.onclick = openExcluded;
  const od = document.getElementById('openDiet'); if (od) od.onclick = openDiet;
  const of = document.getElementById('openFeedback'); if (of) of.onclick = openFeedback;
  const ol = document.getElementById('openLegal'); if (ol) ol.onclick = openLegal;
  const ca = document.getElementById('changeAvatar'); if (ca) ca.onclick = async () => { const e = prompt('Profilbild Emoji', state.settings.profile_image); if (e) { await api.patch('/api/settings', { profile_image: e }); await reloadData(); } };
  bindSwipeGestures();
}

async function reloadData(withRender = true) {
  const q = new URLSearchParams({ search: state.search, ...Object.fromEntries(Object.entries(state.filters).map(([k, v]) => [k, String(v)])) });
  state.recipes = await api.get(`/api/recipes?${q}`);
  state.favorites = await api.get('/api/favorites');
  state.lists = await api.get('/api/lists');
  state.settings = await api.get('/api/settings');
  if (withRender) render(); else render();
}

reloadData();
