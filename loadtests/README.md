# k6 Lasttest: Free vs Starter vergleichen

Dieses Profil misst die wichtigsten API-Flows deiner App mit realistischen, authentifizierten Requests.

Standardmäßig verhält es sich jetzt wie eine echte Session:

- Login als Gast nur beim Session-Start (nicht bei jeder Iteration)
- Danach wiederholte `GET /api/recipes` + `GET /api/swipe-recipes`
- Optional periodische Re-Auth

Optional (für Vergleich mit altem Verhalten) kannst du wieder "Login/Logout je Iteration" aktivieren.

1. `POST /api/auth/guest` (Session-Start)
2. `GET /api/recipes`
3. `GET /api/swipe-recipes`
4. optional: `POST /api/auth/logout` (bei Re-Auth oder Legacy-Modus)

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

### Auth-Verhalten steuern (neu)

Standard (realitätsnäher):

- `AUTH_PER_ITERATION=0` (Default): ein VU behält seine Session über viele Iterationen.
- `REAUTH_EVERY=50` (Default): nach 50 Iterationen wird einmal neu eingeloggt.

```bash
BASE_URL=https://<service>.onrender.com AUTH_PER_ITERATION=0 REAUTH_EVERY=50 k6 run loadtests/k6-free-vs-starter.js
```

Legacy-Vergleich (altes, aggressiveres Muster):

- `AUTH_PER_ITERATION=1`: Login + Logout bei jeder Iteration.

```bash
BASE_URL=https://<service>.onrender.com AUTH_PER_ITERATION=1 k6 run loadtests/k6-free-vs-starter.js
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

## Wenn p95/p99 bei 50 VUs bei ~6–7s liegen: konkrete Maßnahmen

Wenn du bei 50 VUs `p95 ≈ 6500 ms` und `p99 ≈ 7000 ms` siehst, ist das klar über den Zielwerten. Gehe in dieser Reihenfolge vor:

1. **Umgebung prüfen (größter Hebel)**
   - Free-Instanzen haben oft deutliche Plattform-Latenz und CPU-Engpässe.
   - Miss **Free vs Starter** direkt nacheinander mit identischem Skript.
   - Falls nur Free langsam ist: zuerst auf Starter umstellen, dann erneut messen.

2. **Parallele Worker erhöhen**
   - Der Server startet standardmäßig mit `WEB_CONCURRENCY=1`.
   - Setze `WEB_CONCURRENCY` auf `2` oder `4` (abhängig von deinem Plan) und miss erneut.
   - Das reduziert Queueing unter Last deutlich.

3. **Test realitätsnäher machen**
   - Nutze den neuen Standard (`AUTH_PER_ITERATION=0`), damit Sessions über Iterationen bestehen bleiben.
   - Für Vergleich/Regression kannst du mit `AUTH_PER_ITERATION=1` bewusst den zusätzlichen Auth-Overhead zuschalten.
   - So trennst du Auth-Overhead klar von eigentlicher Endpoint-Performance.

4. **DB/Storage richtig wählen**
   - Wenn möglich Redis für Gast-Tokens aktivieren (`REDIS_URL`), damit Auth-Prüfung nicht nur auf DB/Memory basiert.
   - Bei produktiver Last eher Postgres + Redis statt lokaler Free-Storage-Nutzung.

5. **Nutzlast begrenzen**
   - Nutze Pagination/Windowing (`limit`, `offset`) konsequent.
   - Vermeide `full=1`, wenn Kartenansicht reicht.
   - Setze testweise `PAUSE_SECONDS=0.5..1.5`, damit das Muster echter Nutzer besser getroffen wird.

6. **Flaschenhals gezielt messen**
   - k6 getrennt pro Endpoint laufen lassen (nur `/api/recipes`, nur `/api/swipe-recipes`, nur Auth).
   - Dann erkennst du sofort, welcher Schritt p95/p99 nach oben zieht.

### Entscheidungsregel

- Wenn nach Upgrade + `WEB_CONCURRENCY`-Tuning weiterhin `p95 > 2500 ms` bleibt:
  - Endpoint-spezifisch optimieren (Filterlogik, DB-Zugriffe, Caching pro Nutzerprofil).
- Wenn die Werte nach Upgrade sofort deutlich sinken:
  - Bottleneck war primär Plattform/CPU, nicht die API-Logik.
