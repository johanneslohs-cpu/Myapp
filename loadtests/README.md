# k6 Lasttest: Free vs Starter vergleichen

Dieses Profil misst die wichtigsten API-Flows deiner App mit realistischen, authentifizierten Requests:

1. `POST /api/auth/guest`
2. `GET /api/recipes`
3. `GET /api/swipe-recipes`
4. `POST /api/auth/logout`

## 1) k6 installieren

- macOS (Homebrew): `brew install k6`
- Windows (choco): `choco install k6`
- Linux (Debian/Ubuntu): siehe offizielle k6-Doku

## 2) Free messen

```bash
BASE_URL=https://<dein-free-service>.onrender.com k6 run loadtests/k6-free-vs-starter.js
```

## 3) Starter messen

```bash
BASE_URL=https://<dein-starter-service>.onrender.com k6 run loadtests/k6-free-vs-starter.js
```

## 4) Ergebnis vergleichen

Wichtige Kennzahlen:

- `http_req_duration` (vor allem `p(95)` und `p(99)`)
- `http_req_failed`
- `checks`
- `iterations/s` und `http_reqs/s`

### Faustregeln für "produktionsreif"

- `http_req_failed < 2%`
- `p95 < 1200 ms`
- `p99 < 2500 ms`
- `checks > 98%`

Wenn Free diese Grenzwerte unter Ziel-Last nicht hält, ist Starter für dich sinnvoll.

## Optional: Parameter anpassen

### Suchbegriff setzen

```bash
BASE_URL=https://<service>.onrender.com SEARCH_TERM=pasta k6 run loadtests/k6-free-vs-starter.js
```

### Denkzeit zwischen Iterationen

Standard ist `PAUSE_SECONDS=1`.

```bash
BASE_URL=https://<service>.onrender.com PAUSE_SECONDS=0.5 k6 run loadtests/k6-free-vs-starter.js
```

## Profil anpassen (wenn du mehr Last willst)

Im Skript unter `options.scenarios.ramp_traffic.stages` kannst du VUs/Dauer erhöhen.
Beispiel für aggressiver:

- 2m auf 50 VUs
- 4m auf 100 VUs
- 4m auf 200 VUs
- 2m runter

## Hinweise

- Teste Free und Starter möglichst zur ähnlichen Tageszeit.
- Während Tests keine Deploys durchführen.
- Bei Render-Free können Cold-Start-/Plattformeffekte Werte verfälschen.
