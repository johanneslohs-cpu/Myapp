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
  swipeBusy: false,
  swipeRecipes: [],
  dislikedRecipeIds: new Set(),
  token: localStorage.getItem('auth_token') || '',
  auth: null
};

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(url, { ...options, headers });
  const raw = await response.text();
  const data = raw ? JSON.parse(raw) : {};
  if (!response.ok) {
    const message = data.error || `HTTP ${response.status}`;
    throw new Error(message);
  }
  return data;
}

const api = {
  get: (u) => request(u),
  post: (u, b) => request(u, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  put: (u, b) => request(u, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  patch: (u, b) => request(u, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(b || {}) }),
  delete: (u) => request(u, { method: 'DELETE' })
};

const app = document.getElementById('app');

const FALLBACK_FOOD_IMAGES = [
  'https://images.unsplash.com/photo-1498837167922-ddd27525d352?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80',
  'https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1200&q=80'
];

function hashString(value = '') {
  return [...value].reduce((sum, c) => sum + c.charCodeAt(0), 0);
}

function recipeFallbackImage(recipe) {
  const key = `${recipe.name || ''}-${recipe.cuisine || ''}-${recipe.category || ''}`;
  return FALLBACK_FOOD_IMAGES[hashString(key) % FALLBACK_FOOD_IMAGES.length];
}

const getSwipeQueue = () => state.swipeRecipes.filter((recipe) => !state.swipedRecipeIds.has(recipe.id));
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

function recipeImageMarkup(recipe, className = 'recipe-photo') {
  const image = recipe.image || '';
  const source = /^https?:\/\//.test(image) ? image : recipeFallbackImage(recipe);
  return `<img class="${className}" src="${source}" alt="${recipe.name}" loading="lazy">`;
}

function resetLocalUserState() {
  state.tab = 'discover';
  state.search = '';
  state.filters = {};
  state.selectedRecipe = null;
  state.selectedList = null;
  state.swipedRecipeIds = new Set();
  state.swipeBusy = false;
  state.swipeRecipes = [];
  state.dislikedRecipeIds = new Set();
  state.recipes = [];
  state.favorites = [];
  state.lists = [];
  state.settings = null;
}

function parseIngredientEntry(entry) {
  const raw = String(entry || '').trim();
  const m = raw.match(/^(\d+[\d.,]*)\s*(g|kg|ml|l|EL|TL|Stk\.?|Stück|Prise|Bund|Dose|Dosen)?\s+(.+)$/i);
  if (m) {
    const amount = Number(m[1].replace(',', '.'));
    return { amount: Number.isFinite(amount) ? amount : 1, unit: m[2] || '', name: m[3] };
  }
  return { amount: null, unit: '', name: raw };
}

function formatIngredientsWithPortions(ingredients = [], portions = 2) {
  const factor = Math.max(1, portions) / 2;
  return ingredients.map((ingredient) => {
    const parsed = parseIngredientEntry(ingredient);
    if (parsed.amount === null) return parsed.name;
    const scaledAmount = Math.round(parsed.amount * factor * 10) / 10;
    return `${String(scaledAmount).replace('.', ',')} ${parsed.unit} ${parsed.name}`.replace(/\s+/g, ' ').trim();
  });
}

function ingredientMergeKey(name = '') {
  return String(name || '').trim().replace(/\s+/g, ' ').toLowerCase();
}

function mergeShoppingItems(existingItems = [], incomingIngredients = []) {
  const merged = existingItems.map((item) => ({ ...item }));
  const indexByName = new Map();

  merged.forEach((item, index) => {
    const key = ingredientMergeKey(item.name);
    if (!key || indexByName.has(key)) return;
    indexByName.set(key, index);
  });

  incomingIngredients.forEach((ingredient) => {
    const ingredientName = String(ingredient || '').trim();
    if (!ingredientName) return;
    const key = ingredientMergeKey(ingredientName);
    if (!key) return;
    const existingIndex = indexByName.get(key);

    if (existingIndex === undefined) {
      merged.push({ name: ingredientName, checked: false });
      indexByName.set(key, merged.length - 1);
      return;
    }

    const parsedExisting = parseIngredientEntry(merged[existingIndex].name);
    const parsedIncoming = parseIngredientEntry(ingredientName);
    const sameBaseName = ingredientMergeKey(parsedExisting.name) === ingredientMergeKey(parsedIncoming.name);
    const sameUnit = ingredientMergeKey(parsedExisting.unit) === ingredientMergeKey(parsedIncoming.unit);
    const hasAmounts = parsedExisting.amount !== null && parsedIncoming.amount !== null;

    if (sameBaseName && sameUnit && hasAmounts) {
      const summedAmount = Math.round((parsedExisting.amount + parsedIncoming.amount) * 10) / 10;
      const normalizedUnit = parsedExisting.unit || parsedIncoming.unit;
      const normalizedName = parsedExisting.name;
      merged[existingIndex].name = `${String(summedAmount).replace('.', ',')} ${normalizedUnit} ${normalizedName}`.replace(/\s+/g, ' ').trim();
    }
  });

  return merged;
}

function fullStepText(step) {
  return `${step} Arbeite sauber und mit mittlerer Hitze, schmecke am Ende sorgfältig mit Salz, Pfeffer und frischen Kräutern ab und richte das Gericht anschließend direkt heiß an.`;
}

function renderDiscover() {
  return `${header('Heute kochen', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <input class="search" placeholder="Rezept suchen" value="${state.search}" id="searchInput" />
    <div class="hero" data-tab-jump="swipe">
      <div class="hero-image"><h2 class="hero-title">Swipe dich zu deinem nächsten Lieblingsgericht</h2></div>
      <div class="hero-sub">Entdecke täglich leckere und nährstoffreiche neue Rezepte</div>
    </div>
    <h2 class="section-title">Für dich ausgewählt</h2>
    <div class="grid">${state.recipes.map(recipeCard).join('')}</div>`;
}

function recipeCard(r) {
  return `<div class="card" data-recipe="${r.id}">
    <div class="recipe-img">${recipeImageMarkup(r)}</div>
    <div class="card-title">${r.name}</div>
    <div class="small">${r.duration} Min · ${r.ingredients_count} Zutaten</div>
  </div>`;
}

function renderSwipe() {
  const queue = getSwipeQueue();
  const r = queue[0];
  if (!r) {
    return `${header('Menu-Swipe', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
      <div class="empty-state">
        <h3>Keine Karten mehr im Swipe-Deck</h3>
        <p>Auf „Entdecken“ findest du weiterhin alle Rezepte.</p>
        <button class="btn" id="resetDislikes">Abgelehnte Rezepte neu laden</button>
      </div>`;
  }
  return `${header('Menu-Swipe', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <p class="small">${queue.length} Rezepte im Swipe-Deck</p>
    <div class="swipe-stage">
      <div class="big-card" data-recipe="${r.id}" id="swipeCard">
        <div class="swipe-badge swipe-badge-like">LIKE</div>
        <div class="swipe-badge swipe-badge-nope">NOPE</div>
        <div class="big-media">${recipeImageMarkup(r, 'swipe-photo')}</div>
        <div class="swipe-body">
          <h2>${r.name}</h2>
          <div class="big-meta">
            <span>⏱ ${r.duration} Min</span>
            <span>🧾 ${r.ingredients_count} Zutaten</span>
            <span>🍽 ${r.cuisine}</span>
          </div>
        </div>
        <p class="big-copy">Ausgewogen, schnell und alltagstauglich – mit klaren Nährwerten und Schritt-für-Schritt-Anleitung für ein professionelles Kocherlebnis.</p>
      </div>
    </div>
    <div class="actions">
      <div class="circle dislike" id="swipeDislike">✕</div>
      <div class="circle" id="swipeInfo">i</div>
      <div class="circle like" id="swipeLike">♥</div>
    </div>`;
}

function recipeMatchesSearchAndFilter(recipe) {
  const searchValue = state.search.trim().toLowerCase();
  if (searchValue && !recipe.name.toLowerCase().includes(searchValue)) return false;

  const f = state.filters;
  if (f.category && recipe.category !== f.category) return false;
  if (f.maxCalories && recipe.calories >= f.maxCalories) return false;
  if (f.minProtein && recipe.protein <= f.minProtein) return false;
  if (f.maxDuration && recipe.duration >= f.maxDuration) return false;

  return true;
}

function filteredFavorites() {
  return state.favorites.filter(recipeMatchesSearchAndFilter);
}

function renderFavorites() {
  const favorites = filteredFavorites();
  return `${header('Deine Favoriten', `<button class="btn" id="openFilter">⏷ Filter</button>`)}
    <input class="search" placeholder="Rezept suchen" value="${state.search}" id="searchInput" />
    <div class="grid">${favorites.map(recipeCard).join('')}
      <div class="card favorite-add-card" id="toSwipe"><div class="recipe-img add-favorite-media"><span class="add-favorite-plus">＋</span></div><div>Weitere Favoriten hinzufügen</div></div>
    </div>`;
}

function renderLists() {
  return `${header('Einkaufsliste')}
    <div class="list-overview">
      <button class="btn new-list-button" id="newList">＋ Neue Liste erstellen</button>
    </div>
    ${state.lists.map((l) => `<div class="list-card" data-list="${l.id}">
      <div class="list-color" style="background:${l.color}"></div>
      <div class="list-main">
        <div class="small">${l.updated_at ? new Date(l.updated_at).toLocaleDateString('de-DE') : 'Unbekannt'} aktualisiert</div>
        <h3>${l.name}</h3>
        <div class="list-count">${(l.items || []).length} Zutaten · ${(l.items || []).filter((item) => item.checked).length} erledigt</div>
      </div>
    </div>`).join('')}
    ${!state.lists.length ? '<div class="empty-state"><h3>Noch keine Einkaufslisten</h3><p>Lege deine erste Liste an und sammle Zutaten aus Rezepten.</p></div>' : ''}`;
}

function renderProfile() {
  const s = state.settings;
  const profileImage = s.profile_image || '';
  const hasImageUrl = /^https?:\/\//.test(profileImage);
  const avatarContent = hasImageUrl
    ? `<img src="${profileImage}" alt="${s.username}" class="avatar-image" loading="lazy">`
    : (s.username || '?').trim().charAt(0).toUpperCase() || '?';

  return `${header('Profil', `<button class="btn" id="openSettings">⚙</button>`)}
  <div class="profile"><div class="avatar" id="changeAvatar">${avatarContent}</div><h2>${s.username}</h2><p class="small">Smart Meal Matching · Green Edition</p></div>
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
  app.innerHTML = `<div class="phone">${content}</div>${nav()}`;
  bind();
}

function modal(html) {
  const root = ensureModalRoot();
  root.innerHTML = `<div class="modal"><div class="modal-content">${html}</div></div>`;
  document.querySelector('.modal').onclick = (e) => {
    if (e.target.classList.contains('modal')) closeModal();
  };
}
function ensureModalRoot() {
  let root = document.getElementById('modalRoot');
  if (!root) {
    root = document.createElement('div');
    root.id = 'modalRoot';
    document.body.appendChild(root);
  }
  return root;
}

function closeModal() { ensureModalRoot().innerHTML = ''; }

function openRecipe(id) {
  const r = [...state.recipes, ...state.favorites].find((x) => x.id === Number(id));
  if (!r) return;
  state.selectedRecipe = r;
  let portions = 2;
  let pickedIngredients = new Set();
  const draw = () => {
    const isFavorite = state.favorites.some((recipe) => recipe.id === r.id);
    const detailedIngredients = formatIngredientsWithPortions(r.ingredients || [], portions);
    modal(`<div class="recipe-detail">
      <div class="recipe-detail-top">
        <button class="btn" id="closeModal">← Zurück</button>
        <button class="btn recipe-like-btn ${isFavorite ? 'active' : ''}" id="likeRecipe" aria-label="Rezept liken">♥</button>
      </div>
      <div class="recipe-hero">
        <div class="recipe-hero-media">${recipeImageMarkup(r, 'detail-photo')}</div>
        <div class="recipe-hero-content">
          <h1>${r.name}</h1>
          <p class="small">${r.duration} Min · ${r.cuisine}</p>
          <div class="recipe-meta-tags">
            <span>${r.ingredients_count} Zutaten</span>
            <span>${r.nutrition.kcal} kcal</span>
          </div>
        </div>
      </div>

      <div class="recipe-tabs">
        <button class="btn" id="jumpIngredients">Zutaten</button>
        <button class="btn" id="jumpNutrition">Nährwerte</button>
        <button class="btn" id="jumpSteps">Zubereitung</button>
      </div>

      <div class="portion-panel" id="ingredients">
        <div><span class="small">Portionen</span><h2>${portions}</h2></div>
        <div class="row">
          <button class="btn" id="minusPortion">−</button>
          <button class="btn" id="plusPortion">＋</button>
        </div>
      </div>

      <h2 class="recipe-section-title">Zutaten</h2>
      <div class="recipe-ingredients">
        ${detailedIngredients.map((i, index) => {
          const picked = pickedIngredients.has(index);
          return `<div class="ingredient ingredient-card ${picked ? 'picked' : ''}"><span class="ingredient-text">${i}</span><button class="ingredient-pick ${picked ? 'picked' : ''}" data-ingredient-pick="${index}" title="Als gekauft markieren">${picked ? '✓' : '○'}</button></div>`;
        }).join('')}
      </div>

      <div class="tip-banner">Zutaten dabei, die du nicht magst? Über "Das esse ich nicht" im Profil kannst du sie ausblenden.</div>
      <button class="btn" id="addToList">Zur Einkaufsliste hinzufügen</button>

      <h2 class="recipe-section-title" id="nutrition">Nährwerte pro Portion</h2>
      <div class="nutrition-grid">
        <div class="nutrition-item highlight"><span>Kalorien</span><strong>${r.nutrition.kcal} kcal</strong></div>
        <div class="nutrition-item"><span>Kohlenhydrate</span><strong>${r.nutrition.carbs} g</strong></div>
        <div class="nutrition-item"><span>Eiweiß</span><strong>${r.nutrition.protein} g</strong></div>
        <div class="nutrition-item"><span>Fett</span><strong>${r.nutrition.fat} g</strong></div>
      </div>

      <h2 class="recipe-section-title" id="steps">Zubereitung</h2>
      <div class="steps-list">
        ${r.steps.map((s, i) => `<div class="step-card"><div class="step-index">${String(i + 1).padStart(2, '0')}</div><div><h3>Schritt ${i + 1}</h3><p>${fullStepText(s)}</p></div></div>`).join('')}
      </div>
    </div>`);

    document.getElementById('closeModal').onclick = closeModal;
    document.getElementById('plusPortion').onclick = () => { portions += 1; draw(); };
    document.getElementById('minusPortion').onclick = () => { portions = Math.max(1, portions - 1); draw(); };
    document.getElementById('jumpIngredients').onclick = () => document.getElementById('ingredients').scrollIntoView({ behavior: 'smooth' });
    document.getElementById('jumpSteps').onclick = () => document.getElementById('steps').scrollIntoView({ behavior: 'smooth' });
    document.getElementById('jumpNutrition').onclick = () => document.getElementById('nutrition').scrollIntoView({ behavior: 'smooth' });
    document.querySelectorAll('[data-ingredient-pick]').forEach((button) => {
      button.onclick = () => {
        const index = Number(button.dataset.ingredientPick);
        if (pickedIngredients.has(index)) pickedIngredients.delete(index);
        else pickedIngredients.add(index);
        draw();
      };
    });
    document.getElementById('likeRecipe').onclick = async () => {
      const currentlyFavorite = state.favorites.some((recipe) => recipe.id === r.id);
      if (currentlyFavorite) await api.delete(`/api/favorites/${r.id}`);
      else await api.post(`/api/recipes/${r.id}/like`);
      if (currentlyFavorite) {
        await api.delete(`/api/favorites/${r.id}`);
        state.favorites = state.favorites.filter((recipe) => recipe.id !== r.id);
      } else {
        await api.post(`/api/recipes/${r.id}/like`);
        if (!state.favorites.some((recipe) => recipe.id === r.id)) state.favorites = [...state.favorites, r];
      }
      state.swipedRecipeIds.add(r.id);
      state.favorites = await api.get('/api/favorites');
      draw();
    };
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
  if (action === 'skip') {
    await api.post(`/api/recipes/${recipe.id}/dislike`);
    state.dislikedRecipeIds.add(recipe.id);
  }
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
  let moved = false;

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
    moved = false;
    startX = e.clientX;
    card.setPointerCapture(e.pointerId);
    card.style.transition = 'none';
  };

  card.onpointermove = (e) => {
    if (!dragging || state.swipeBusy) return;
    currentX = e.clientX - startX;
    if (Math.abs(currentX) > 12) moved = true;
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
      if (!moved) {
        const recipe = currentSwipeRecipe();
        if (recipe) openRecipe(recipe.id);
      }
    }
    currentX = 0;
    moved = false;
  };
}

function openFilter() {
  const f = state.filters;
  const toggleFilter = (key, value) => {
    if (state.filters[key] === value) {
      delete state.filters[key];
    } else {
      state.filters[key] = value;
    }
    openFilter();
  };

  modal(`<div class="filter-modal">
      <div class="header"><button class="btn" id="closeModal">✕</button><h2>Filter</h2></div>
      <div class="filter-section"><h3>Kategorie</h3><div class="filter-options tags" id="catRow">${['Hauptgericht', 'Frühstück', 'Dinner', 'Nachtisch'].map((c) => `<button class="btn ${f.category === c ? 'active' : ''}" data-category="${c}">${c}</button>`).join('')}</div></div>
      <div class="filter-section"><h3>Kalorien</h3><div class="filter-options tags"><button class="btn ${f.maxCalories === 300 ? 'active' : ''}" data-cal="300">unter 300</button><button class="btn ${f.maxCalories === 400 ? 'active' : ''}" data-cal="400">unter 400</button><button class="btn ${f.maxCalories === 500 ? 'active' : ''}" data-cal="500">unter 500</button><button class="btn ${f.maxCalories === 700 ? 'active' : ''}" data-cal="700">unter 700</button></div></div>
      <div class="filter-section"><h3>Eiweiß</h3><div class="filter-options tags"><button class="btn ${f.minProtein === 30 ? 'active' : ''}" data-pro="30">über 30 g</button><button class="btn ${f.minProtein === 50 ? 'active' : ''}" data-pro="50">über 50 g</button><button class="btn ${f.minProtein === 70 ? 'active' : ''}" data-pro="70">über 70 g</button></div></div>
      <div class="filter-section"><h3>Dauer</h3><div class="filter-options tags"><button class="btn ${f.maxDuration === 15 ? 'active' : ''}" data-dur="15">&lt;15 Min</button><button class="btn ${f.maxDuration === 30 ? 'active' : ''}" data-dur="30">&lt;30 Min</button><button class="btn ${f.maxDuration === 60 ? 'active' : ''}" data-dur="60">&lt;1 Std</button></div></div>
      <div class="filter-actions">
        <button class="btn" id="resetFilter">Filter zurücksetzen</button>
        <button class="btn" id="applyFilter">Filter anwenden</button>
      </div>
    </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-category]').forEach((b) => b.onclick = () => toggleFilter('category', b.dataset.category));
  document.querySelectorAll('[data-cal]').forEach((b) => b.onclick = () => toggleFilter('maxCalories', Number(b.dataset.cal)));
  document.querySelectorAll('[data-pro]').forEach((b) => b.onclick = () => toggleFilter('minProtein', Number(b.dataset.pro)));
  document.querySelectorAll('[data-dur]').forEach((b) => b.onclick = () => toggleFilter('maxDuration', Number(b.dataset.dur)));
  document.getElementById('resetFilter').onclick = () => { state.filters = {}; openFilter(); };
  document.getElementById('applyFilter').onclick = async () => { await reloadData(); closeModal(); };
}

async function openListEditor(id) {
  const list = await api.get(`/api/lists/${id}`);
  const draw = () => {
    const doneCount = list.items.filter((item) => item.checked).length;
    modal(`<div class="list-editor">
      <div class="header">
        <button class="btn" id="closeModal">← Zurück</button>
        <button class="btn" id="saveList">Speichern</button>
      </div>
      <h2>${list.name}</h2>
      <p class="small">${doneCount} von ${list.items.length} Zutaten abgehakt · Tippe auf Kreise zum Abhaken.</p>
      <div class="shopping-items">
        ${list.items.map((item, i) => `<div class="shopping-row">
          <label class="shopping-check">
            <input type="checkbox" data-check="${i}" ${item.checked ? 'checked' : ''}>
            <span class="shopping-dot"></span>
          </label>
          <span class="shopping-name ${item.checked ? 'done' : ''}">${item.name}</span>
          <button class="btn" data-remove="${i}">✕</button>
        </div>`).join('')}
      </div>
      <div class="row">
        <button class="btn" id="addItem">＋ Zutat hinzufügen</button>
        <button class="btn" id="deleteList">Liste löschen</button>
      </div>
    </div>`);
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
  modal(`<div class="list-form">
    <div class="header"><button class="btn" id="closeModal">✕</button><button class="btn" id="saveNewList">Speichern</button></div>
    <h1>Neue Einkaufsliste erstellen</h1>
    <p class="small">Gib deiner Liste einen Namen und wähle eine Farbe, damit du sie schnell wiederfindest.</p>
    <div class="form-group"><label for="listName">Bezeichnung</label><input id="listName" placeholder="z.B. Wochenmarkt Samstag" /></div>
    <div class="form-group"><label>Farbcode</label><div class="row color-row">${['#7ed6df', '#f06262', '#81de91', '#cde94f', '#cd59d8'].map((c) => `<button class="color-pick ${c === '#7ed6df' ? 'active' : ''}" style="background:${c}" data-color="${c}" aria-label="Farbe ${c}"></button>`).join('')}</div></div>
  </div>`);
  let chosen = '#7ed6df';
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-color]').forEach((b) => b.onclick = () => { chosen = b.dataset.color; document.querySelectorAll('[data-color]').forEach((x)=>x.classList.remove('active')); b.classList.add('active'); });
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
  modal(`<div class="settings-modal">
    <button class="btn" id="closeModal">← Einstellungen schließen</button>
    <h2>Einstellungen</h2>
    <div class="settings-section">
      <label for="username">Nutzername</label>
      <input id="username" value="${s.username}" />
    </div>
    <div class="settings-section">
      <label>Abo verwalten</label>
      <div class="settings-note">${s.manage_subscription_note}</div>
    </div>
    <div class="settings-actions">
      <button class="btn" id="saveSettings">Speichern</button>
      <button class="btn settings-danger" id="logout">Abmelden</button>
      <button class="btn settings-danger" id="deleteAccount">Account löschen</button>
    </div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('saveSettings').onclick = async () => { await api.patch('/api/settings', { username: document.getElementById('username').value }); await reloadData(); closeModal(); };
  document.getElementById('logout').onclick = async () => {
    await api.post('/api/auth/logout');
    state.token='';
    localStorage.removeItem('auth_token');
    resetLocalUserState();
    startAuthFlow();
  };
  document.getElementById('deleteAccount').onclick = () => {
    modal(`<div class="settings-modal">
      <h2>Account wirklich löschen?</h2>
      <p class="small">Wenn du auf „Ja" klickst, werden alle gespeicherten Daten zu deinem Account dauerhaft gelöscht.</p>
      <div class="settings-actions">
        <button class="btn" id="cancelDeleteAccount">Nein</button>
        <button class="btn settings-danger" id="confirmDeleteAccount">Ja</button>
      </div>
    </div>`);

    document.getElementById('cancelDeleteAccount').onclick = () => openSettings();
    document.getElementById('confirmDeleteAccount').onclick = async () => {
      await api.delete('/api/account');
      state.token = '';
      localStorage.removeItem('auth_token');
      resetLocalUserState();
      closeModal();
      await startAuthFlow();
    };
  };
}

function openExcluded() {
  const excluded = (state.settings.excluded || []).filter((entry) => entry.active);

  modal(`<div class="excluded-modal">
    <button class="btn" id="closeModal">← Zurück</button>
    <h2>Das esse ich nicht</h2>
    <p class="small excluded-note">Alle Rezepte, die eine dieser Zutaten enthalten, werden automatisch ausgeblendet.</p>
    <div class="excluded-add-row">
      <input id="excludeName" class="search" placeholder="z. B. Pilze, Sellerie, Lachs" />
      <button class="btn" id="addExclude">Hinzufügen</button>
    </div>
    <div class="excluded-list">
      ${excluded.map((entry) => `<div class="excluded-chip"><span>${entry.name}</span><button class="excluded-remove" data-remove-ex="${entry.id}" title="Zutat entfernen">✕</button></div>`).join('')}
      ${excluded.length ? '' : '<div class="empty-state"><h3>Noch keine Zutaten</h3><p>Füge Zutaten hinzu, die du nicht essen möchtest.</p></div>'}
    </div>
  </div>`);

  const addIngredient = async () => {
    const input = document.getElementById('excludeName');
    const name = input.value.trim();
    if (!name) return;
    await api.post('/api/excluded', { name });
    await reloadData();
    openExcluded();
  };

  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('addExclude').onclick = addIngredient;
  document.getElementById('excludeName').onkeydown = async (event) => {
    if (event.key !== 'Enter') return;
    event.preventDefault();
    await addIngredient();
  };
  document.querySelectorAll('[data-remove-ex]').forEach((button) => {
    button.onclick = async () => {
      await api.delete(`/api/excluded/${button.dataset.removeEx}`);
      await reloadData();
      openExcluded();
    };
  });
}

function openDiet() {
  const options = ['Ich esse alles', 'Pescetarisch', 'Vegetarisch', 'Vegan', 'High-Protein'];
  modal(`<div class="diet-modal"><button class="btn" id="closeModal">← Zurück</button><h2>Ernährungsform</h2>
    <p class="small">Wähle die Ernährungsweise, die am besten zu dir passt.</p>
    <div class="diet-options">
      ${options.map((o) => `<label class="diet-option ${state.settings.diet === o ? 'active' : ''}"><input type="radio" name="diet" value="${o}" ${state.settings.diet === o ? 'checked' : ''}><span class="diet-radio-dot"></span><span>${o}</span></label>`).join('')}
    </div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('input[name="diet"]').forEach((r) => r.onchange = async () => { await api.patch('/api/settings', { diet: r.value }); await reloadData(); openDiet(); });
}

function openFeedback() {
  modal(`<div class="feedback-modal">
    <button class="btn" id="closeModal">← Zurück</button>
    <h2>Hilfe und Feedback</h2>
    <p class="small feedback-intro">Wir melden uns so schnell wie möglich bei dir zurück.</p>
    <div class="feedback-form">
      <label for="fMail">E-Mail-Adresse</label>
      <input id="fMail" type="email" placeholder="name@beispiel.de" autocomplete="email" />
      <label for="fSub">Betreff</label>
      <input id="fSub" placeholder="Worum geht es?" />
      <label for="fMsg">Nachricht</label>
      <textarea id="fMsg" placeholder="Beschreibe dein Anliegen oder Feedback..."></textarea>
    </div>
    <button class="btn" id="sendFeedback">Abschicken</button>
  </div>`);
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
  modal(`<div class="legal-modal">
    <button class="btn" id="closeModal">← Zurück</button>
    <h2>Sonstiges</h2>
    <p class="small legal-intro">Hier findest du alle rechtlichen und administrativen Informationen übersichtlich gesammelt.</p>
    <div class="legal-list">
      <article class="legal-card">
        <h3>Nutzungsbedingungen</h3>
        <p>Dies ist ein Beispieltext für Nutzungsbedingungen.</p>
      </article>
      <article class="legal-card">
        <h3>Datenschutzerklärung</h3>
        <p>Dies ist ein Beispieltext zum Datenschutz und zur Datenverarbeitung.</p>
      </article>
      <article class="legal-card">
        <h3>Datenschutzeinstellungen</h3>
        <p>Hier könnten Cookie- und Tracking-Einstellungen verwaltet werden.</p>
      </article>
      <article class="legal-card">
        <h3>AGB</h3>
        <p>Dies ist ein Beispieltext für allgemeine Geschäftsbedingungen.</p>
      </article>
    </div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
}

async function openAddToList(ingredients) {
  const lists = await api.get('/api/lists');
  modal(`<div class="add-to-list-modal">
    <div class="add-to-list-head">
      <button class="btn" id="closeModal">← Zurück</button>
      <h2>Zu Einkaufsliste hinzufügen</h2>
      <p class="small">Wähle eine Liste. Gleiche Zutaten werden zusammengeführt und Mengen addiert.</p>
    </div>
    <div class="add-to-list-grid">
      ${lists.map((l) => `<button class="add-to-list-option" data-add-list="${l.id}">
        <span class="add-to-list-name">${l.name}</span>
        <span class="add-to-list-meta">${(l.items || []).length} Zutaten</span>
      </button>`).join('') || '<div class="empty-state"><h3>Noch keine Listen</h3><p>Lege erst eine Einkaufsliste an, um Zutaten hinzuzufügen.</p></div>'}
    </div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  if (!lists.length) return;
  document.querySelectorAll('[data-add-list]').forEach((b) => b.onclick = async () => {
    const list = await api.get(`/api/lists/${b.dataset.addList}`);
    const mergedItems = mergeShoppingItems(list.items || [], ingredients || []);
    await api.put(`/api/lists/${list.id}`, { name: list.name, items: mergedItems });
    await reloadData();
    closeModal();
  });
}

function bind() {
  document.querySelectorAll('.nav-btn').forEach((btn) => btn.onclick = async () => { state.tab = btn.dataset.tab; await reloadData(false); });
  const heroJump = document.querySelector('[data-tab-jump="swipe"]');
  if (heroJump) heroJump.onclick = async () => { state.tab = 'swipe'; await reloadData(false); };
  document.querySelectorAll('[data-recipe]').forEach((el) => {
    if (el.id === 'swipeCard') return;
    el.onclick = () => openRecipe(el.dataset.recipe);
  });
  const si = document.getElementById('searchInput');
  if (si) si.oninput = async (e) => { state.search = e.target.value; await reloadData(false); };
  const openFilterBtn = document.getElementById('openFilter'); if (openFilterBtn) openFilterBtn.onclick = openFilter;
  const sl = document.getElementById('swipeLike'); if (sl) sl.onclick = async () => handleSwipeAction('like');
  const sd = document.getElementById('swipeDislike'); if (sd) sd.onclick = async () => handleSwipeAction('skip');
  const sii = document.getElementById('swipeInfo'); if (sii) sii.onclick = () => currentSwipeRecipe() && openRecipe(currentSwipeRecipe().id);
  const rd = document.getElementById('resetDislikes'); if (rd) rd.onclick = async () => { await api.post('/api/dislikes/reset'); state.swipedRecipeIds.clear(); state.dislikedRecipeIds.clear(); await reloadData(); };
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


function authModal() {
  modal(`<div class="auth-modal"><h2>Anmelden</h2>
    <p class="small">Melde dich mit Google an oder fahre als Gast fort.</p>
    <div id="googleSignIn" class="auth-google-slot"></div>
    <button class="btn auth-guest-btn" id="authGuest">Als Gast einloggen</button></div>`);

  document.getElementById('authGuest').onclick = async () => {
    const res = await api.post('/api/auth/guest', {});
    resetLocalUserState();
    state.token = res.token; localStorage.setItem('auth_token', res.token); closeModal(); await startAuthFlow();
  };

  const initializeGoogle = () => {
    if (!window.google || !window.google.accounts || !window.google.accounts.id) return;
    window.google.accounts.id.initialize({
      client_id: '1014015739173-sj85p3bdscndu859jtveok8kjrgfqr2q.apps.googleusercontent.com',
      callback: async (response) => {
        try {
          const res = await api.post('/api/auth/google', { credential: response.credential });
          resetLocalUserState();
          state.token = res.token;
          localStorage.setItem('auth_token', res.token);
          closeModal();
          await startAuthFlow();
        } catch (error) {
          alert(`Google Login fehlgeschlagen: ${error.message}`);
        }
      }
    });
    window.google.accounts.id.renderButton(
      document.getElementById('googleSignIn'),
      { theme: 'outline', size: 'large', text: 'signin_with', shape: 'pill', width: 280 }
    );
  };

  initializeGoogle();
  if (!window.google) {
    const waitForGoogle = setInterval(() => {
      if (window.google) {
        clearInterval(waitForGoogle);
        initializeGoogle();
      }
    }, 150);
    setTimeout(() => clearInterval(waitForGoogle), 5000);
  }
}


async function startAuthFlow() {
  if (!state.token) { authModal(); return; }
  try {
    state.auth = await api.get('/api/auth/me');
    await reloadData();
  } catch (error) {
    resetLocalUserState();
    state.token = '';
    localStorage.removeItem('auth_token');
    authModal();
  }
}

async function reloadData(withRender = true) {
  try {
    const q = new URLSearchParams({ search: state.search, ...Object.fromEntries(Object.entries(state.filters).map(([k, v]) => [k, String(v)])) });
    state.recipes = await api.get(`/api/recipes?${q}`);
    state.swipeRecipes = await api.get(`/api/swipe-recipes?${q}`);
    state.favorites = await api.get('/api/favorites');
    state.dislikedRecipeIds = new Set(await api.get('/api/dislikes'));
    state.lists = await api.get('/api/lists');
    state.settings = await api.get('/api/settings');
    if (withRender) render(); else render();
  } catch (error) {
    console.error('Fehler beim Laden der Daten:', error);
    alert(`Daten konnten nicht geladen werden: ${error.message}`);
  }
}

startAuthFlow();
