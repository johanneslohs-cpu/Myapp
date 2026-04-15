import http from 'k6/http';
import { check, sleep } from 'k6';
import { Counter } from 'k6/metrics';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:3000').replace(/\/$/, '');
const SEARCH_TERM = __ENV.SEARCH_TERM || '';
const PAUSE_SECONDS = Number(__ENV.PAUSE_SECONDS || '1');
const AUTH_PER_ITERATION = (__ENV.AUTH_PER_ITERATION || '0') === '1';
const REAUTH_EVERY = Math.max(0, Number(__ENV.REAUTH_EVERY || '50'));

const errorCounter = new Counter('scenario_errors');
let sessionToken = null;
let iterationCount = 0;

export const options = {
  scenarios: {
    ramp_traffic: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '2m', target: 25 },
        { duration: '4m', target: 50 },
        { duration: '4m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'],
    http_req_duration: ['p(95)<1200', 'p(99)<2500'],
    checks: ['rate>0.98'],
    scenario_errors: ['count<5'],
  },
};

function jsonHeaders(token = null) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

function failStep(name, response) {
  errorCounter.add(1);
  console.error(`${name} failed with ${response.status}: ${response.body?.slice?.(0, 200) || ''}`);
}

function guestLogin() {
  const guestLogin = http.post(
    `${BASE_URL}/api/auth/guest`,
    JSON.stringify({}),
    { headers: jsonHeaders() }
  );

  const loginOk = check(guestLogin, {
    'guest login status 200': (r) => r.status === 200,
    'guest login returns token': (r) => {
      try {
        return !!r.json('token');
      } catch (e) {
        return false;
      }
    },
  });

  if (!loginOk) {
    failStep('guest_login', guestLogin);
    return null;
  }

  return guestLogin.json('token');
}

function logoutGuest(token) {
  if (!token) {
    return;
  }
  const authParams = { headers: jsonHeaders(token) };
  const logout = http.post(
    `${BASE_URL}/api/auth/logout`,
    JSON.stringify({}),
    authParams
  );
  const logoutOk = check(logout, {
    'logout status 200': (r) => r.status === 200,
  });
  if (!logoutOk) {
    failStep('logout', logout);
  }
}

function ensureSessionToken() {
  if (AUTH_PER_ITERATION) {
    return guestLogin();
  }
  if (!sessionToken) {
    sessionToken = guestLogin();
    return sessionToken;
  }
  if (REAUTH_EVERY > 0 && iterationCount > 0 && iterationCount % REAUTH_EVERY === 0) {
    logoutGuest(sessionToken);
    sessionToken = guestLogin();
  }
  return sessionToken;
}

export default function () {
  const token = ensureSessionToken();
  if (!token) {
    sleep(PAUSE_SECONDS);
    return;
  }
  const authParams = { headers: jsonHeaders(token) };

  const recipes = http.get(
    `${BASE_URL}/api/recipes?search=${encodeURIComponent(SEARCH_TERM)}`,
    authParams
  );
  const recipesOk = check(recipes, {
    'recipes status 200': (r) => r.status === 200,
    'recipes payload is array': (r) => {
      try {
        return Array.isArray(r.json());
      } catch (e) {
        return false;
      }
    },
  });
  if (!recipesOk) {
    failStep('recipes', recipes);
  }

  const swipe = http.get(
    `${BASE_URL}/api/swipe-recipes?search=${encodeURIComponent(SEARCH_TERM)}`,
    authParams
  );
  const swipeOk = check(swipe, {
    'swipe-recipes status 200': (r) => r.status === 200,
    'swipe-recipes payload is array': (r) => {
      try {
        return Array.isArray(r.json());
      } catch (e) {
        return false;
      }
    },
  });
  if (!swipeOk) {
    failStep('swipe_recipes', swipe);
  }

  if (AUTH_PER_ITERATION) {
    logoutGuest(token);
  }

  iterationCount += 1;
  sleep(PAUSE_SECONDS);
}
