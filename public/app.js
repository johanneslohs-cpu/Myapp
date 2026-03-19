const isCordovaFileRuntime = window.location.protocol === 'file:';
const DEFAULT_CORDOVA_API_BASE_URL = 'https://myapp-rezepte.onrender.com';

const API_BASE_URL = (
  window.MYAPP_API_BASE_URL
  || localStorage.getItem('myapp_api_base_url')
  || (isCordovaFileRuntime ? DEFAULT_CORDOVA_API_BASE_URL : '')
).replace(/\/$/, '');

function withApiBase(url) {
  if (!url) return url;
  if (/^https?:\/\//i.test(url)) return url;
  return `${API_BASE_URL}${url}`;
}

const MAX_SHOPPING_LISTS = 10;
const MAX_LIST_NAME_LENGTH = 30;

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
  auth: null,
  googleClientId: '',
  isCordova: Boolean(window.cordova) || isCordovaFileRuntime,
  cordovaReady: !isCordovaFileRuntime
};

let searchReloadTimer = null;


const LEGAL_DOCUMENTS = [
  {
    id: 'privacy',
    title: 'Datenschutzerklärung',
    subtitle: 'Stand: 18.03.2026',
    icon: '🔒',
    accent: 'privacy',
    content: `Datenschutzerklärung für BiteMatch
Stand: 18.03.2026

1. Verantwortlicher
Verantwortlich für die Verarbeitung personenbezogener Daten im Zusammenhang mit der Android-App BiteMatch ist:
Johannes Lohs
Steinfeldstraße 16
6921 Kennelbach
Österreich
E-Mail: bitematch.de@gmail.com

2. Allgemeines
BiteMatch ist eine Android-App zur Entdeckung und Verwaltung von Kochrezepten. Nutzer können Rezepte ansehen, per Swipe bewerten, Favoriten speichern, nach Zutaten und Nährwerten filtern, Zutaten zu Einkaufslisten hinzufügen, Einkaufslisten verwalten sowie persönliche Einstellungen und Profildaten anpassen.

3. Welche Daten verarbeitet werden
Im Rahmen der Nutzung von BiteMatch können insbesondere folgende personenbezogene Daten verarbeitet werden:
• Name
• E-Mail-Adresse
• Profilbild, sofern dieses über den Google-Login bereitgestellt oder vom Nutzer hochgeladen wird
• Kontodaten und Profildaten
• Favoriten, Filtereinstellungen, ausgeschlossene Zutaten, Ernährungspräferenzen und Einkaufslisten
• Inhalte, die Nutzer innerhalb der App selbst speichern oder verwalten
• Daten aus Support- oder Feedbackanfragen
• technische Verbindungsdaten und Protokolldaten, soweit dies für Betrieb, Sicherheit und Stabilität der App erforderlich ist
• Werbe- und gerätebezogene Daten im Zusammenhang mit eingeblendeter Werbung

4. Zwecke der Verarbeitung
Die Verarbeitung personenbezogener Daten erfolgt zu folgenden Zwecken:
• Bereitstellung und Betrieb der App
• Anmeldung und Verwaltung des Nutzerkontos
• Speicherung und Verwaltung von Favoriten, Filtern, Einkaufslisten und Profileinstellungen
• Personalisierung der App-Nutzung
• Bearbeitung von Support- und Feedbackanfragen
• Einblendung von Werbung
• Sicherstellung der technischen Stabilität und Sicherheit der App
• Verhinderung von Missbrauch

5. Rechtsgrundlagen
Die Verarbeitung personenbezogener Daten erfolgt, soweit anwendbar, auf folgenden Rechtsgrundlagen:
• zur Erfüllung des Nutzungsverhältnisses und zur Bereitstellung der App-Funktionen
• zur Wahrung berechtigter Interessen an einem sicheren, stabilen und wirtschaftlichen Betrieb der App
• auf Grundlage einer Einwilligung, soweit eine solche erforderlich ist

6. Anmeldung mit Google
Für die Nutzung von BiteMatch wird ein Login über Google angeboten. Im Rahmen dieses Logins können insbesondere Name, E-Mail-Adresse und Profilbild übernommen werden, soweit diese Daten vom Nutzer im Rahmen des Google-Logins freigegeben werden.
Diese Daten werden verwendet, um das Nutzerkonto anzulegen, die Anmeldung zu ermöglichen und die Nutzung der App bereitzustellen.

7. Werbung
In BiteMatch wird Werbung eingebunden. Im Zusammenhang mit der Anzeige von Werbung können durch eingesetzte Werbedienste personenbezogene Daten und gerätebezogene Informationen verarbeitet werden, soweit dies für die Ausspielung, Bereitstellung und technische Abwicklung von Werbung erforderlich ist.

8. Hosting und technische Bereitstellung
Zur technischen Bereitstellung der App und zugehöriger Dienste werden externe Hosting- und Infrastrukturdienstleister eingesetzt. Dabei können technisch notwendige Daten verarbeitet werden, insbesondere Verbindungs- und Serverprotokolldaten, soweit dies für Betrieb, Sicherheit und Stabilität erforderlich ist.

9. Empfänger von Daten
Personenbezogene Daten können an folgende Empfänger oder Kategorien von Empfängern übermittelt werden, soweit dies zur Bereitstellung der App erforderlich ist:
• Login-Dienstleister
• Werbedienstleister
• Hosting- und Infrastrukturdienstleister
• technische Auftragsverarbeiter, soweit diese für den Betrieb der App eingesetzt werden

10. Drittlandübermittlung
Es kann nicht ausgeschlossen werden, dass einzelne eingesetzte Dienste oder technische Anbieter Daten auch außerhalb der Europäischen Union oder des Europäischen Wirtschaftsraums verarbeiten. In solchen Fällen erfolgt die Verarbeitung nur im Rahmen der jeweils geltenden datenschutzrechtlichen Vorgaben.

11. Speicherdauer
Personenbezogene Daten werden nur so lange gespeichert, wie dies für die jeweiligen Zwecke erforderlich ist.
Im Regelfall gilt:
• Kontodaten werden bis zur Löschung des Nutzerkontos gespeichert
• Profil-, Favoriten-, Filter- und Einkaufslistendaten werden bis zur Löschung des Kontos oder bis zur Entfernung durch den Nutzer gespeichert
• Support- und Feedbackdaten werden so lange gespeichert, wie dies zur Bearbeitung und Nachverfolgung erforderlich ist
• technische Protokolldaten werden nur so lange gespeichert, wie dies für Sicherheit, Fehlerbehebung und Stabilität notwendig ist
• gesetzliche Aufbewahrungspflichten bleiben unberührt

12. Kontolöschung und Datenlöschung
Nutzer können ihr Konto innerhalb der App löschen.
Zusätzlich kann die Löschung des Kontos und der damit verbundenen personenbezogenen Daten über die E-Mail bitematch.de@gmail.com beantragt werden.
Mit der Löschung des Kontos werden die damit verbundenen personenbezogenen Daten gelöscht, soweit keine gesetzlichen Aufbewahrungspflichten oder zwingenden technischen Gründe entgegenstehen.

13. Datensicherheit
Es werden angemessene technische und organisatorische Maßnahmen getroffen, um personenbezogene Daten vor Verlust, Missbrauch, unbefugtem Zugriff, unbefugter Offenlegung oder unbefugter Veränderung zu schützen.

14. Rechte der betroffenen Personen
Betroffene Personen haben im Rahmen der gesetzlichen Vorschriften insbesondere folgende Rechte:
• Recht auf Auskunft
• Recht auf Berichtigung
• Recht auf Löschung
• Recht auf Einschränkung der Verarbeitung
• Recht auf Datenübertragbarkeit
• Recht auf Widerspruch
• Recht auf Widerruf erteilter Einwilligungen mit Wirkung für die Zukunft
• Recht auf Beschwerde bei einer zuständigen Aufsichtsbehörde

15. Beschwerderecht
Wenn du der Ansicht bist, dass die Verarbeitung deiner personenbezogenen Daten gegen geltendes Datenschutzrecht verstößt, kannst du dich bei einer zuständigen Datenschutzbehörde beschweren.

16. Änderungen dieser Datenschutzerklärung
Diese Datenschutzerklärung kann angepasst werden, wenn sich die App, ihre Funktionen, die eingesetzten Dienste oder die rechtlichen Anforderungen ändern.`,
  },
  {
    id: 'imprint',
    title: 'Impressum',
    subtitle: 'Anbieterkennzeichnung',
    icon: '📍',
    accent: 'imprint',
    content: `Impressum

Johannes Lohs
Steinfeldstraße 16
6921 Kennelbach
Österreich

E-Mail: bitematch.de@gmail.com

Medieninhaber und Herausgeber: Johannes Lohs
App: BiteMatch
Blattlinie: Informationen und Services rund um die Android-App BiteMatch zur Entdeckung und Verwaltung von Kochrezepten.`,
  },
  {
    id: 'terms',
    title: 'Nutzungsbedingungen',
    subtitle: 'Stand: 18.03.2026',
    icon: '📘',
    accent: 'terms',
    content: `Nutzungsbedingungen für BiteMatch
Stand: 18.03.2026

1. Geltungsbereich
Diese Nutzungsbedingungen regeln die Nutzung der mobilen Android-App „BiteMatch“ durch ihre Nutzer.

2. Leistungsbeschreibung
BiteMatch ist eine App zur Entdeckung, Filterung und Verwaltung von Rezepten. Nutzer können Rezepte ansehen, per Swipe bewerten, Favoriten speichern, Einkaufslisten verwalten sowie persönliche Einstellungen wie Ernährungsform oder ausgeschlossene Zutaten festlegen.

3. Nutzerkonto und Anmeldung
Die Nutzung bestimmter Funktionen setzt ein Nutzerkonto bzw. eine Anmeldung per Google-Login voraus. Nutzer sind verpflichtet, nur korrekte Angaben zu machen und ihren Zugang nicht missbräuchlich zu verwenden.

4. Zulässige Nutzung
Die App darf nur im Rahmen der geltenden Gesetze und dieser Nutzungsbedingungen verwendet werden. Untersagt ist insbesondere jede Nutzung, die den technischen Betrieb beeinträchtigt, Sicherheitsmechanismen umgeht oder Inhalte bzw. Funktionen missbräuchlich verwendet.

5. Verfügbarkeit
Es besteht kein Anspruch auf eine jederzeit unterbrechungsfreie Verfügbarkeit der App. Wartungen, technische Störungen, Weiterentwicklungen oder externe Ausfälle können zu Einschränkungen führen.

6. Inhalte und Haftung
Die in der App dargestellten Rezepte und Informationen dienen allgemeinen Informationszwecken. Trotz sorgfältiger Aufbereitung wird keine Gewähr für Vollständigkeit, Richtigkeit oder ständige Verfügbarkeit übernommen. Nutzer sind selbst dafür verantwortlich, Zutaten, Allergene, Unverträglichkeiten und Nährwerte im Einzelfall zu prüfen.

7. Werbung
Die App kann Werbung enthalten, insbesondere über AdMob. Auf die Inhalte externer Werbeanzeigen besteht kein Einfluss; für Inhalte externer Anbieter wird keine Haftung übernommen.

8. Änderungen der App
Der Anbieter ist berechtigt, Funktionen der App zu ändern, zu erweitern, einzuschränken oder einzustellen, soweit dies unter Berücksichtigung der Nutzerinteressen zumutbar ist.

9. Sperrung und Kündigung
Der Anbieter kann Nutzerkonten sperren oder löschen, wenn ein Verstoß gegen diese Nutzungsbedingungen oder ein Missbrauch der App vorliegt. Nutzer können ihr Konto entsprechend der in der App bereitgestellten Funktion löschen.

10. Datenschutz
Informationen zur Verarbeitung personenbezogener Daten ergeben sich aus der Datenschutzerklärung der App.

11. Schlussbestimmungen
Es gilt österreichisches Recht unter Ausschluss der Kollisionsnormen, soweit dem keine zwingenden Verbraucherschutzvorschriften entgegenstehen. Sollten einzelne Bestimmungen unwirksam sein, bleibt die Wirksamkeit der übrigen Bestimmungen unberührt.`,
  },
];

function legalPreview(text = '') {
  return text.split('\n').filter(Boolean).slice(0, 2).join(' · ');
}

function legalContentToHtml(text = '') {
  return text.split('\n').map((line) => {
    const trimmed = line.trim();
    if (!trimmed) return '<div class="legal-spacer"></div>';
    if (/^•\s/.test(trimmed)) return `<li>${trimmed.replace(/^•\s*/, '')}</li>`;
    return `<p>${trimmed}</p>`;
  }).join('');
}

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  const response = await fetch(withApiBase(url), { ...options, headers });
  const raw = await response.text();
  let data = {};
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch (_error) {
    data = { raw };
  }
  if (!response.ok) {
    const message = [data.error, data.details].filter(Boolean).join(': ') || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.code = data.code;
    error.details = data.details;
    error.raw = data.raw;
    throw error;
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

syncSystemUiTheme();

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

function syncRecipeCollections(recipe, action) {
  if (!recipe) return;
  if (action === 'like') {
    state.dislikedRecipeIds.delete(recipe.id);
    if (!state.favorites.some((entry) => entry.id === recipe.id)) state.favorites = [recipe, ...state.favorites];
  }
  if (action === 'skip') {
    state.favorites = state.favorites.filter((entry) => entry.id !== recipe.id);
    state.dislikedRecipeIds.add(recipe.id);
  }
  if (action === 'unlike') {
    state.favorites = state.favorites.filter((entry) => entry.id !== recipe.id);
  }
  if (action === 'like' || action === 'skip') {
    state.swipedRecipeIds.add(recipe.id);
    state.swipeRecipes = state.swipeRecipes.filter((entry) => entry.id !== recipe.id);
  }
}

function nav() {
  const tabs = [
    ['discover', '🌿', 'Entdecken', 'Rezepte'],
    ['swipe', '🔥', 'Swipe', 'Match'],
    ['favorites', '💚', 'Favoriten', 'Gespeichert'],
    ['lists', '🛒', 'Listen', 'Einkauf'],
    ['profile', '👤', 'Profil', 'Konto']
  ];
  return `<nav class="bottom-nav" aria-label="Hauptnavigation">${tabs.map(([id, icon, title, hint]) => `<button class="nav-btn ${state.tab === id ? 'active' : ''}" data-tab="${id}" aria-label="${title}" aria-current="${state.tab === id ? 'page' : 'false'}"><span class="nav-icon" aria-hidden="true">${icon}</span><span class="nav-copy"><span class="nav-title">${title}</span><span class="nav-hint">${hint}</span></span></button>`).join('')}</nav>`;
}

function syncNavigationBarTheme(themeColor) {
  const navigationBar = window.NavigationBar || window.navigationBar;
  if (!navigationBar) return;

  if (typeof navigationBar.backgroundColorByHexString === 'function') {
    navigationBar.backgroundColorByHexString(themeColor);
  } else if (typeof navigationBar.setColor === 'function') {
    navigationBar.setColor(themeColor, false);
  }

  if (typeof navigationBar.styleLight === 'function') navigationBar.styleLight();
  if (typeof navigationBar.styleDefault === 'function') navigationBar.styleDefault();
  if (typeof navigationBar.hide === 'function') navigationBar.hide();
  if (typeof navigationBar.immersiveMode === 'function') navigationBar.immersiveMode();
}

function syncSystemUiTheme() {
  const themeColor = '#0f1511';
  const metaTheme = document.querySelector('meta[name="theme-color"]');
  if (metaTheme) metaTheme.setAttribute('content', themeColor);
  if (document.body) {
    document.body.style.backgroundColor = themeColor;
    document.body.classList.toggle('cordova-immersive', false);
  }
  syncNavigationBarTheme(themeColor);

  const statusBar = window.StatusBar;
  if (!statusBar) return;

  if (typeof statusBar.backgroundColorByHexString === 'function') statusBar.backgroundColorByHexString(themeColor);
  if (typeof statusBar.styleLightContent === 'function') statusBar.styleLightContent();

  const canHideStatusBar = typeof statusBar.hide === 'function';
  const canOverlayWebView = typeof statusBar.overlaysWebView === 'function';

  if (canOverlayWebView) statusBar.overlaysWebView(canHideStatusBar);
  if (canHideStatusBar) statusBar.hide();

  if (document.body) document.body.classList.toggle('cordova-immersive', canHideStatusBar);
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

function runCordovaGooglePlus(method) {
  return new Promise((resolve, reject) => {
    if (!window.plugins || !window.plugins.googleplus || typeof window.plugins.googleplus[method] !== 'function') {
      resolve();
      return;
    }
    window.plugins.googleplus[method](resolve, reject);
  });
}

async function resetCordovaGoogleSession() {
  if (!state.isCordova) return;
  try {
    await runCordovaGooglePlus('logout');
  } catch (_error) {
    // Ignorieren: Einige Geräte liefern Fehler, wenn keine aktive Session mehr existiert.
  }

  try {
    await runCordovaGooglePlus('disconnect');
  } catch (_error) {
    // Ignorieren: Falls disconnect nicht unterstützt wird, bleibt logout ausreichend.
  }
}

const CORDOVA_GOOGLE_ERROR_HINTS = {
  10: 'DEVELOPER_ERROR: Meistens SHA-1/Fingerabdruck oder OAuth-Client in Firebase/Google Cloud falsch konfiguriert.',
  12500: 'SIGN_IN_FAILED: Häufig Konfigurationsproblem (SHA-1, Paketname oder fehlende Zustimmung im OAuth-Screen).',
  12501: 'SIGN_IN_CANCELLED: Anmeldung wurde vom Nutzer abgebrochen.',
  7: 'NETWORK_ERROR: Keine stabile Internetverbindung oder Google-Dienste nicht erreichbar.',
  8: 'INTERNAL_ERROR: Google Play Services interner Fehler, oft temporär.'
};

function formatAuthError(error) {
  const lines = ['Google Login fehlgeschlagen.'];
  if (error && error.stage) lines.push(`Schritt: ${error.stage}`);
  if (error && error.message) lines.push(`Fehler: ${error.message}`);
  if (error && error.code) {
    lines.push(`Code: ${error.code}`);
    const numericCode = Number(error.code);
    if (Number.isFinite(numericCode) && CORDOVA_GOOGLE_ERROR_HINTS[numericCode]) {
      lines.push(`Hinweis: ${CORDOVA_GOOGLE_ERROR_HINTS[numericCode]}`);
    }
  }
  if (error && error.status) lines.push(`HTTP-Status: ${error.status}`);
  if (error && error.details) lines.push(`Details: ${error.details}`);
  if (error && error.raw) lines.push(`Antwort: ${error.raw}`);
  if (error && error.context) lines.push(`Kontext: ${error.context}`);
  lines.push('Bitte sende diesen Text inkl. Code weiter, damit wir die Ursache gezielt beheben können.');
  return lines.join('\n');
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
  return `${header('Entdecken', `<button class="btn" id="openFilter">▼ Filter</button>`)}
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

function renderSwipeCard(recipe, { top = false } = {}) {
  if (!recipe) return '';
  return `<div class="big-card${top ? ' swipe-card-active' : ' swipe-card-next'}" data-recipe="${recipe.id}" ${top ? 'id="swipeCard"' : ''}>
    <div class="swipe-badge swipe-badge-like">LIKE</div>
    <div class="swipe-badge swipe-badge-nope">NOPE</div>
    <div class="big-media">${recipeImageMarkup(recipe, 'swipe-photo')}</div>
    <div class="swipe-body">
      <h2>${recipe.name}</h2>
      <div class="big-meta">
        <span>⏱ ${recipe.duration} Min</span>
        <span>🧾 ${recipe.ingredients_count} Zutaten</span>
        <span>🍽 ${recipe.cuisine}</span>
      </div>
    </div>
  </div>`;
}

function renderSwipe() {
  const queue = getSwipeQueue();
  const current = queue[0];
  const next = queue[1];
  if (!current) {
    return `${header('Menu-Swipe', `<button class="btn" id="openFilter">▼ Filter</button>`)}
      <div class="empty-state">
        <h3>Keine Karten mehr im Swipe-Deck</h3>
        <p>Auf „Entdecken“ findest du weiterhin alle Rezepte.</p>
        <button class="btn" id="resetDislikes">Abgelehnte Rezepte neu laden</button>
      </div>`;
  }
  return `${header('Menu-Swipe', `<button class="btn" id="openFilter">▼ Filter</button>`)}
    <p class="small">${queue.length} Rezepte im Swipe-Deck</p>
    <div class="swipe-stage">
      <div class="swipe-stack">
        ${next ? renderSwipeCard(next) : '<div class="big-card swipe-card-placeholder"></div>'}
        ${renderSwipeCard(current, { top: true })}
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
  return `${header('Deine Favoriten', `<button class="btn" id="openFilter">▼ Filter</button>`)}
    <input class="search" placeholder="Rezept suchen" value="${state.search}" id="searchInput" />
    <div class="grid">
      <div class="card favorite-add-card" id="toSwipe"><div class="recipe-img add-favorite-media"><span class="add-favorite-plus">＋</span></div><div class="favorite-add-label">Weitere Favoriten hinzufügen</div></div>${favorites.map(recipeCard).join('')}
    </div>`;
}

function renderLists() {
  const reachedListLimit = state.lists.length >= MAX_SHOPPING_LISTS;
  return `${header('Einkaufsliste')}
    <button class="btn new-list-button ${reachedListLimit ? 'disabled' : ''}" id="newList" ${reachedListLimit ? 'disabled' : ''}>＋ Neue Liste erstellen</button>
    ${reachedListLimit ? '<p class="list-limit-hint">Maximal 10 Einkaufslisten gleichzeitig möglich.</p>' : ''}
    <div class="lists-stack">${state.lists.map((l) => `<div class="list-card" data-list="${l.id}">
      <div class="list-color" style="background:${l.color}"></div>
      <div class="list-main">
        <div class="small">${l.updated_at ? new Date(l.updated_at).toLocaleDateString('de-DE') : 'Unbekannt'} aktualisiert</div>
        <h3>${l.name}</h3>
        <div class="list-count">${(l.items || []).length} Zutaten · ${(l.items || []).filter((item) => item.checked).length} erledigt</div>
      </div>
    </div>`).join('')}</div>
    ${!state.lists.length ? '<div class="empty-state"><h3>Noch keine Einkaufslisten</h3><p>Lege deine erste Liste an und sammle Zutaten aus Rezepten.</p></div>' : ''}`;
}

function renderProfile() {
  const s = state.settings;
  const profileImage = s.profile_image || '';
  const hasImageUrl = /^https?:\/\//.test(profileImage);
  const avatarContent = hasImageUrl
    ? `<img src="${profileImage}" alt="${s.username}" class="avatar-image" loading="lazy">`
    : (s.username || '?').trim().charAt(0).toUpperCase() || '?';

  return `${header('Profil', `<button class="btn profile-settings-btn" id="openSettings" aria-label="Einstellungen öffnen">⚙</button>`)}
  <div class="profile profile-hero"><div class="avatar" id="changeAvatar">${avatarContent}</div><h2>${s.username}</h2><p class="small profile-subtitle">Smart Meal Matching</p></div>
  <div class="stats profile-stats profile-stats-primary"><div class="card profile-card"><h2>${state.favorites.length} ♥</h2><div>Favoriten</div></div><div class="card profile-card"><h2>${state.lists.length} 🛒</h2><div>Einkaufslisten</div></div></div>
  <div class="stats profile-stats profile-stats-secondary"><div class="card profile-card profile-action-card" id="openExcluded">Das esse ich nicht</div><div class="card profile-card profile-action-card" id="openDiet">${s.diet}</div></div>
  <div class="list-item profile-list-item" id="openFeedback"><span>❓</span><span>Hilfe und Feedback</span></div>
  <div class="list-item profile-list-item" id="openLegal"><span>⋯</span><span>Sonstiges</span></div>`;
}

function render() {
  let content = '';
  if (state.tab === 'discover') content = renderDiscover();
  if (state.tab === 'swipe') content = renderSwipe();
  if (state.tab === 'favorites') content = renderFavorites();
  if (state.tab === 'lists') content = renderLists();
  if (state.tab === 'profile') content = renderProfile();
  const phoneClass = state.tab === 'swipe' ? 'phone phone-swipe' : 'phone';
  app.innerHTML = `<div class="${phoneClass}">${content}</div>${nav()}`;
  bind();
}

function modal(html, options = {}) {
  const root = ensureModalRoot();
  const previousModal = root.querySelector('.modal');
  const preservedScrollTop = options.preserveScroll ? (previousModal?.scrollTop || 0) : 0;
  root.innerHTML = `<div class="modal"><div class="modal-content">${html}</div></div>`;
  const modalElement = root.querySelector('.modal');
  modalElement.onclick = (e) => {
    if (e.target.classList.contains('modal')) closeModal();
  };
  if (options.preserveScroll) {
    requestAnimationFrame(() => { modalElement.scrollTop = preservedScrollTop; });
  }
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
  const MIN_PORTIONS = 1;
  const MAX_PORTIONS = 10;
  const draw = () => {
    const isFavorite = state.favorites.some((recipe) => recipe.id === r.id);
    const detailedIngredients = formatIngredientsWithPortions(r.ingredients || [], portions);
    modal(`<div class="recipe-detail">
      <div class="recipe-detail-top">
        <button class="btn" id="closeModal" type="button">← Zurück</button>
        <button class="btn recipe-like-btn ${isFavorite ? 'active' : ''}" id="likeRecipe" type="button" aria-label="Rezept liken">♥</button>
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
        <button class="btn" id="jumpIngredients" type="button">Zutaten</button>
        <button class="btn" id="jumpNutrition" type="button">Nährwerte</button>
        <button class="btn" id="jumpSteps" type="button">Zubereitung</button>
      </div>

      <div class="portion-panel" id="ingredients">
        <div><span class="small">Portionen</span><h2>${portions}</h2></div>
        <div class="row">
          <button class="btn" id="minusPortion" type="button" ${portions <= MIN_PORTIONS ? 'disabled' : ''}>−</button>
          <button class="btn" id="plusPortion" type="button" ${portions >= MAX_PORTIONS ? 'disabled' : ''}>＋</button>
        </div>
      </div>

      <h2 class="recipe-section-title">Zutaten</h2>
      <div class="recipe-ingredients">
        ${detailedIngredients.map((i, index) => {
          const picked = pickedIngredients.has(index);
          return `<div class="ingredient ingredient-card ${picked ? 'picked' : ''}"><span class="ingredient-text">${i}</span><button class="ingredient-pick ${picked ? 'picked' : ''}" type="button" data-ingredient-pick="${index}" title="Als gekauft markieren">${picked ? '✓' : '○'}</button></div>`;
        }).join('')}
      </div>

      <div class="tip-banner">Zutaten dabei, die du nicht magst? Über "Das esse ich nicht" im Profil kannst du Rezepte die sie enthalten ausblenden.</div>
      <button class="btn" id="addToList" type="button">Zur Einkaufsliste hinzufügen</button>

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
    </div>`, { preserveScroll: true });

    document.getElementById('closeModal').onclick = () => {
      state.selectedRecipe = null;
      closeModal();
    };
    document.getElementById('plusPortion').onclick = () => {
      portions = Math.min(MAX_PORTIONS, portions + 1);
      draw();
    };
    document.getElementById('minusPortion').onclick = () => {
      portions = Math.max(MIN_PORTIONS, portions - 1);
      draw();
    };
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
      if (currentlyFavorite) {
        await api.delete(`/api/favorites/${r.id}`);
        syncRecipeCollections(r, 'unlike');
      } else {
        await api.post(`/api/recipes/${r.id}/like`);
        syncRecipeCollections(r, 'like');
      }
      if (state.tab === 'swipe') render();
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
    await new Promise((resolve) => setTimeout(resolve, 320));
  }

  syncRecipeCollections(recipe, action);
  render();

  try {
    if (action === 'like') await api.post(`/api/recipes/${recipe.id}/like`);
    if (action === 'skip') await api.post(`/api/recipes/${recipe.id}/dislike`);
    await reloadData({ withRender: false });
  } finally {
    state.swipeBusy = false;
  }
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
        <button class="btn" id="closeModal" type="button">← Zurück</button>
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
    document.getElementById('closeModal').onclick = () => {
      state.selectedRecipe = null;
      closeModal();
    };
    document.querySelectorAll('[data-check]').forEach((c) => c.onchange = () => { list.items[c.dataset.check].checked = c.checked; });
    document.querySelectorAll('[data-remove]').forEach((b) => b.onclick = () => { list.items.splice(Number(b.dataset.remove), 1); draw(); });
    document.getElementById('addItem').onclick = () => { const name = prompt('Zutat'); if (name) { list.items.push({ name, checked: false }); draw(); } };
    document.getElementById('saveList').onclick = async () => { await api.put(`/api/lists/${id}`, { name: list.name, items: list.items }); await reloadData(); closeModal(); };
    document.getElementById('deleteList').onclick = async () => { await api.delete(`/api/lists/${id}`); await reloadData(); closeModal(); };
  };
  draw();
}

function openNewList() {
  if (state.lists.length >= MAX_SHOPPING_LISTS) {
    alert('Du kannst maximal 10 Einkaufslisten gleichzeitig anlegen.');
    return;
  }

  modal(`<div class="list-form">
    <div class="header"><button class="btn" id="closeModal">✕</button><button class="btn" id="saveNewList">Speichern</button></div>
    <h1>Neue Einkaufsliste erstellen</h1>
    <p class="small">Gib deiner Liste einen Namen und wähle eine Farbe, damit du sie schnell wiederfindest.</p>
    <div class="form-group">
      <label for="listName">Bezeichnung</label>
      <input id="listName" maxlength="30" placeholder="z.B. Wochenmarkt Samstag" />
      <div class="list-form-meta">
        <span class="small">Maximal 30 Zeichen</span>
        <span class="small" id="listNameCounter">0/30</span>
      </div>
    </div>
    <div class="form-group"><label>Farbcode</label><div class="row color-row">${['#7ed6df', '#f06262', '#81de91', '#cde94f', '#cd59d8'].map((c) => `<button class="color-pick ${c === '#7ed6df' ? 'active' : ''}" style="background:${c}" data-color="${c}" aria-label="Farbe ${c}"></button>`).join('')}</div></div>
  </div>`);
  let chosen = '#7ed6df';
  const nameInput = document.getElementById('listName');
  const counter = document.getElementById('listNameCounter');
  const syncCounter = () => {
    const trimmed = nameInput.value.slice(0, MAX_LIST_NAME_LENGTH);
    if (trimmed !== nameInput.value) nameInput.value = trimmed;
    counter.textContent = `${trimmed.length}/${MAX_LIST_NAME_LENGTH}`;
  };
  syncCounter();
  nameInput.addEventListener('input', syncCounter);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-color]').forEach((b) => b.onclick = () => { chosen = b.dataset.color; document.querySelectorAll('[data-color]').forEach((x)=>x.classList.remove('active')); b.classList.add('active'); });
  document.getElementById('saveNewList').onclick = async () => {
    const name = nameInput.value.trim();
    if (!name) return;
    if (name.length > MAX_LIST_NAME_LENGTH) {
      alert('Der Listenname darf maximal 30 Zeichen lang sein.');
      return;
    }
    if (state.lists.length >= MAX_SHOPPING_LISTS) {
      alert('Du kannst maximal 10 Einkaufslisten gleichzeitig anlegen.');
      return;
    }
    try {
      await api.post('/api/lists', { name, color: chosen });
      await reloadData();
      closeModal();
    } catch (error) {
      alert(error.message || 'Die Liste konnte nicht erstellt werden.');
    }
  };
}

function openSettings() {
  const s = state.settings;
  modal(`<div class="settings-modal">
    <div class="settings-topbar">
      <div>
        <div class="settings-kicker">Profil</div>
        <h2>Einstellungen</h2>
      </div>
      <button class="btn settings-close-btn" id="closeModal" aria-label="Einstellungen schließen">✕</button>
    </div>
    <div class="settings-hero">
      <div class="settings-kicker">Übersicht</div>
      <p>Verwalte hier deinen Nutzernamen, dein Abo und deinen Account, ohne dass sich Funktionen in der App ändern.</p>
    </div>
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
    await resetCordovaGoogleSession();
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
      await resetCordovaGoogleSession();
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
  const maxReached = excluded.length >= 20;

  modal(`<div class="excluded-modal">
    <button class="btn modal-back-btn compact-back-btn" id="closeModal">← Zurück</button>
    <div class="excluded-hero">
      <div>
        <p class="excluded-kicker">Persönlicher Filter</p>
        <h2>Das esse ich nicht</h2>
        <p class="small excluded-note">Alle Rezepte mit diesen Zutaten werden automatisch ausgeblendet. Du kannst bis zu 20 Zutaten gleichzeitig ausschließen.</p>
      </div>
      <div class="excluded-count ${maxReached ? 'is-limit' : ''}">${excluded.length}/20</div>
    </div>
    <div class="excluded-add-row">
      <input id="excludeName" class="search" placeholder="z. B. Pilze, Sellerie, Lachs" ${maxReached ? 'disabled' : ''} />
      <button class="btn" id="addExclude" ${maxReached ? 'disabled' : ''}>Hinzufügen</button>
    </div>
    ${maxReached ? '<p class="excluded-limit-note">Maximal 20 Zutaten gleichzeitig möglich. Entferne erst eine Zutat, bevor du eine neue hinzufügst.</p>' : ''}
    <div class="excluded-list">
      ${excluded.map((entry) => `<div class="excluded-chip"><span>${entry.name}</span><button class="excluded-remove" data-remove-ex="${entry.id}" title="Zutat entfernen">✕</button></div>`).join('')}
      ${excluded.length ? '' : '<div class="empty-state"><h3>Noch keine Zutaten</h3><p>Füge Zutaten hinzu, die du nicht essen möchtest.</p></div>'}
    </div>
  </div>`);

  const addIngredient = async () => {
    const input = document.getElementById('excludeName');
    const name = input.value.trim();
    if (!name) return;
    if (excluded.length >= 20) {
      alert('Du kannst maximal 20 Zutaten gleichzeitig ausschließen.');
      return;
    }
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
  modal(`<div class="diet-modal"><button class="btn modal-back-btn compact-back-btn" id="closeModal">← Zurück</button><h2>Ernährungsform</h2>
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
    <button class="btn modal-back-btn compact-back-btn" id="closeModal">← Zurück</button>
    <div class="feedback-hero">
      <p class="feedback-kicker">Support</p>
      <h2>Hilfe und Feedback</h2>
      <p class="small feedback-intro">Wir melden uns so schnell wie möglich bei dir zurück.</p>
    </div>
    <div class="feedback-form">
      <label for="fMail">E-Mail-Adresse <span class="feedback-label-note">(für Rückfragen)</span></label>
      <input id="fMail" type="email" placeholder="name@beispiel.de" autocomplete="email" />
      <label for="fSub">Betreff</label>
      <input id="fSub" placeholder="Worum geht es?" maxlength="30" />
      <div class="feedback-hint">Maximal 30 Zeichen.</div>
      <label for="fMsg">Nachricht</label>
      <textarea id="fMsg" placeholder="Beschreibe dein Anliegen oder Feedback..." maxlength="250"></textarea>
      <div class="feedback-counter" id="fMsgCounter">0/250</div>
    </div>
    <button class="btn" id="sendFeedback">Abschicken</button>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;

  const mailInput = document.getElementById('fMail');
  const subjectInput = document.getElementById('fSub');
  const messageInput = document.getElementById('fMsg');
  const counter = document.getElementById('fMsgCounter');

  const clampValue = (input, maxLength) => {
    if (input.value.length > maxLength) input.value = input.value.slice(0, maxLength);
  };

  const syncCounter = () => {
    clampValue(messageInput, 250);
    counter.textContent = `${messageInput.value.length}/250`;
  };

  subjectInput.addEventListener('input', () => clampValue(subjectInput, 30));
  subjectInput.addEventListener('paste', () => setTimeout(() => clampValue(subjectInput, 30), 0));
  messageInput.addEventListener('input', syncCounter);
  messageInput.addEventListener('paste', () => setTimeout(syncCounter, 0));
  syncCounter();

  document.getElementById('sendFeedback').onclick = async () => {
    const email = mailInput.value.trim();
    const subject = subjectInput.value.trim();
    const message = messageInput.value.trim();

    if (!email) {
      alert('Bitte gib deine E-Mail-Adresse ein.');
      return;
    }
    if (!email.includes('@')) {
      alert('Bitte gib eine gültige E-Mail-Adresse ein.');
      return;
    }
    if (!subject) {
      alert('Bitte gib einen Betreff ein.');
      return;
    }
    if (subject.length > 30) {
      alert('Der Betreff darf maximal 30 Zeichen lang sein.');
      return;
    }
    if (!message) {
      alert('Bitte gib eine Nachricht ein.');
      return;
    }
    if (message.length > 250) {
      alert('Die Nachricht darf maximal 250 Zeichen lang sein.');
      return;
    }

    await api.post('/api/feedback', { email, subject, message });
    alert('Danke für dein Feedback!');
    closeModal();
  };
}

function openLegal() {
  modal(`<div class="legal-modal legal-overview">
    <div class="legal-topbar">
      <button class="btn modal-back-btn compact-back-btn" id="closeModal">← Zurück</button>
      <div class="legal-badge">BiteMatch Legal</div>
    </div>
    <div class="legal-hero-card">
      <div>
        <p class="legal-eyebrow">Sonstiges</p>
        <h2>Rechtliches klar, modern und schnell auffindbar.</h2>
        <p class="small legal-intro">Hier findest du die wichtigsten Dokumente. Tippe auf einen Eintrag, um ihn direkt in einer übersichtlichen Leseansicht zu öffnen.</p>
      </div>
    </div>
    <div class="legal-list">
      ${LEGAL_DOCUMENTS.map((doc) => `<button class="legal-entry legal-${doc.accent}" data-legal-doc="${doc.id}">
        <span class="legal-entry-icon">${doc.icon}</span>
        <span class="legal-entry-copy">
          <strong>${doc.title}</strong>
          <span>${doc.subtitle}</span>
          <small>${legalPreview(doc.content)}</small>
        </span>
        <span class="legal-entry-arrow">→</span>
      </button>`).join('')}
    </div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.querySelectorAll('[data-legal-doc]').forEach((button) => {
    button.onclick = () => openLegalDocument(button.dataset.legalDoc);
  });
}

function openLegalDocument(docId) {
  const doc = LEGAL_DOCUMENTS.find((entry) => entry.id === docId);
  if (!doc) return;
  modal(`<div class="legal-modal legal-reader legal-${doc.accent}">
    <div class="legal-topbar">
      <button class="btn modal-back-btn compact-back-btn" id="backToLegal">← Sonstiges</button>
      <button class="btn" id="closeModal">✕</button>
    </div>
    <div class="legal-reader-hero">
      <div class="legal-entry-icon">${doc.icon}</div>
      <div>
        <p class="legal-eyebrow">${doc.subtitle}</p>
        <h2>${doc.title}</h2>
        <p class="small legal-intro">Dieses Dokument kannst du jederzeit über den Bereich „Sonstiges“ erneut aufrufen.</p>
      </div>
    </div>
    <div class="legal-reader-body">${legalContentToHtml(doc.content)}</div>
  </div>`);
  document.getElementById('closeModal').onclick = closeModal;
  document.getElementById('backToLegal').onclick = openLegal;
}

async function openAddToList(ingredients) {
  const lists = await api.get('/api/lists');
  modal(`<div class="add-to-list-modal">
    <div class="add-to-list-head">
      <button class="btn" id="closeModal" type="button">← Zurück</button>
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
  document.querySelectorAll('.nav-btn').forEach((btn) => btn.onclick = () => {
    state.tab = btn.dataset.tab;
    render();
  });
  const heroJump = document.querySelector('[data-tab-jump="swipe"]');
  if (heroJump) heroJump.onclick = () => {
    state.tab = 'swipe';
    render();
  };
  document.querySelectorAll('[data-recipe]').forEach((el) => {
    if (el.id === 'swipeCard') return;
    el.onclick = () => openRecipe(el.dataset.recipe);
  });
  const si = document.getElementById('searchInput');
  if (si) si.oninput = (e) => {
    state.search = e.target.value;
    const caretStart = e.target.selectionStart ?? state.search.length;
    const caretEnd = e.target.selectionEnd ?? state.search.length;
    render();
    const nextSearchInput = document.getElementById('searchInput');
    if (nextSearchInput) {
      nextSearchInput.focus();
      nextSearchInput.setSelectionRange(caretStart, caretEnd);
    }
    if (searchReloadTimer) clearTimeout(searchReloadTimer);
    searchReloadTimer = setTimeout(() => {
      reloadData({ withRender: false, scope: 'recipes' });
    }, 220);
  };
  const openFilterBtn = document.getElementById('openFilter'); if (openFilterBtn) openFilterBtn.onclick = openFilter;
  const sl = document.getElementById('swipeLike'); if (sl) sl.onclick = async () => handleSwipeAction('like');
  const sd = document.getElementById('swipeDislike'); if (sd) sd.onclick = async () => handleSwipeAction('skip');
  const sii = document.getElementById('swipeInfo'); if (sii) sii.onclick = () => currentSwipeRecipe() && openRecipe(currentSwipeRecipe().id);
  const rd = document.getElementById('resetDislikes'); if (rd) rd.onclick = async () => { await api.post('/api/dislikes/reset'); state.swipedRecipeIds.clear(); state.dislikedRecipeIds.clear(); await reloadData(); };
  const ts = document.getElementById('toSwipe'); if (ts) ts.onclick = () => {
    state.tab = 'swipe';
    render();
  };
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
  const canUseGoogleWeb = !state.isCordova;
  const canUseGoogleCordova = state.isCordova;
  modal(`<div class="auth-shell">
    <section class="auth-panel">
      <div class="auth-hero">
        <div class="auth-brand-row">
          <img class="auth-brand-logo" src="/assets/bitematch-logo.svg" alt="BiteMatch Logo" />
          <div>
            <div class="auth-brand">BiteMatch</div>
            <p class="auth-kicker">Dein persönlicher Rezept-Match</p>
          </div>
        </div>
        <p class="auth-copy">Melde dich an und behalte Favoriten, Einkaufslisten und deine persönlichen Einstellungen immer griffbereit.</p>
      </div>
      <div class="auth-actions">
        ${canUseGoogleWeb ? '<div id="googleSignIn" class="auth-google-slot"></div>' : ''}
        ${canUseGoogleCordova ? '<button class="btn auth-google-btn" id="googleSignInCordova">Mit Google anmelden</button>' : ''}
        ${state.googleClientId ? '' : '<p class="muted auth-note">Google-Login ist gerade nicht verfügbar.</p>'}
        <button class="btn auth-guest-btn" id="authGuest">Ohne Konto fortfahren</button>
      </div>
    </section>
  </div>`);

  const authBackdrop = document.querySelector('#modalRoot .modal');
  if (authBackdrop) authBackdrop.classList.add('auth-backdrop');

  document.getElementById('authGuest').onclick = async () => {
    const res = await api.post('/api/auth/guest', {});
    resetLocalUserState();
    state.token = res.token; localStorage.setItem('auth_token', res.token); closeModal(); await startAuthFlow();
  };

  const initializeGoogleWeb = () => {
    if (state.isCordova) return;
    if (!state.googleClientId) return;
    if (!window.google || !window.google.accounts || !window.google.accounts.id) return;
    window.google.accounts.id.initialize({
      client_id: state.googleClientId,
      callback: async (response) => {
        try {
          const res = await api.post('/api/auth/google', { credential: response.credential });
          resetLocalUserState();
          state.token = res.token;
          localStorage.setItem('auth_token', res.token);
          closeModal();
          await startAuthFlow();
        } catch (error) {
          alert(formatAuthError(error));
        }
      }
    });
    window.google.accounts.id.renderButton(
      document.getElementById('googleSignIn'),
      { theme: 'outline', size: 'large', text: 'signin_with', shape: 'pill', width: 320 }
    );
  };

  const signInWithCordovaGoogle = () => new Promise((resolve, reject) => {
    if (!window.plugins || !window.plugins.googleplus) {
      const pluginError = new Error('Google Plugin wurde in der App nicht gefunden.');
      pluginError.code = 'plugin_missing';
      pluginError.stage = 'cordova_plugin_check';
      reject(pluginError);
      return;
    }
    window.plugins.googleplus.login(
      {
        webClientId: state.googleClientId,
        scopes: 'profile email',
        offline: false
      },
      (userData) => resolve(userData),
      (error) => {
        const rawError = typeof error === 'string' ? { message: error } : (error || {});
        const message = rawError.error || rawError.message || 'Google Plugin Login fehlgeschlagen';
        const normalizedError = new Error(message);
        normalizedError.stage = 'cordova_plugin_login';
        normalizedError.code = rawError.code || rawError.status || '';
        normalizedError.details = JSON.stringify(rawError);
        normalizedError.context = `isCordova=${Boolean(state.isCordova)}, cordovaReady=${Boolean(state.cordovaReady)}, hasPlugin=${Boolean(window.plugins && window.plugins.googleplus)}, webClientId=${state.googleClientId || '-'}, errorKeys=${Object.keys(rawError).join(',') || '-'}`;
        reject(normalizedError);
      }
    );
  });

  const cordovaGoogleBtn = document.getElementById('googleSignInCordova');
  if (cordovaGoogleBtn) {
    cordovaGoogleBtn.onclick = async () => {
      if (!state.googleClientId) {
        alert('Google-Login ist gerade nicht verfügbar.');
        return;
      }
      if (!state.cordovaReady) {
        alert('App startet noch. Bitte versuche es in ein paar Sekunden erneut.');
        return;
      }
      try {
        await resetCordovaGoogleSession();
        const loginData = await signInWithCordovaGoogle();
        const idToken = loginData && (loginData.idToken || loginData.id_token);
        if (!idToken) {
          const loginKeys = loginData ? Object.keys(loginData).join(', ') : 'keine Daten';
          const missingTokenError = new Error(`Kein Google ID-Token erhalten. Verfügbare Felder: ${loginKeys}`);
          missingTokenError.code = 'missing_id_token';
          missingTokenError.stage = 'extract_id_token';
          missingTokenError.details = loginData ? JSON.stringify(loginData) : '';
          throw missingTokenError;
        }
        const res = await api.post('/api/auth/google', { credential: idToken });
        resetLocalUserState();
        state.token = res.token;
        localStorage.setItem('auth_token', res.token);
        closeModal();
        await startAuthFlow();
      } catch (error) {
        if (!error.stage) error.stage = 'unknown';
        alert(formatAuthError(error));
      }
    };
  }

  initializeGoogleWeb();
  if (!state.isCordova && !window.google) {
    const waitForGoogle = setInterval(() => {
      if (window.google) {
        clearInterval(waitForGoogle);
        initializeGoogleWeb();
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

async function reloadData(options = {}) {
  const { withRender = true, scope = 'all' } = options;
  try {
    const q = new URLSearchParams({ search: state.search, ...Object.fromEntries(Object.entries(state.filters).map(([k, v]) => [k, String(v)])) });

    if (scope === 'all' || scope === 'recipes') {
      const [recipes, swipeRecipes] = await Promise.all([
        api.get(`/api/recipes?${q}`),
        api.get(`/api/swipe-recipes?${q}`)
      ]);
      state.recipes = recipes;
      state.swipeRecipes = swipeRecipes;
    }

    if (scope === 'all') {
      const [favorites, dislikes, lists, settings] = await Promise.all([
        api.get('/api/favorites'),
        api.get('/api/dislikes'),
        api.get('/api/lists'),
        api.get('/api/settings')
      ]);
      state.favorites = favorites;
      state.dislikedRecipeIds = new Set(dislikes);
      state.lists = lists;
      state.settings = settings;
    }

    if (withRender) render();
  } catch (error) {
    console.error('Fehler beim Laden der Daten:', error);
    alert(`Daten konnten nicht geladen werden: ${error.message}`);
  }
}

async function loadPublicConfig() {
  try {
    const config = await api.get('/api/public-config');
    state.googleClientId = (config.googleClientId || '').trim();
  } catch (error) {
    console.warn('Konnte Public-Config nicht laden, nutze Fallbacks.', error);
    state.googleClientId = '';
  }
}

async function bootstrap() {
  await loadPublicConfig();
  await startAuthFlow();
}

if (isCordovaFileRuntime) {
  document.addEventListener('deviceready', () => {
    state.cordovaReady = true;
    syncSystemUiTheme();
    bootstrap();
  }, { once: true });
} else {
  bootstrap();
}
