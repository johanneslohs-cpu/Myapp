# MyApp – Rezept-App

Rezept-App mit lokalem Login-System (E-Mail + Passwort), Registrierung und Gastmodus.

## Features

- Account erstellen und anmelden
- Als Gast fortfahren (Gastdaten werden nicht dauerhaft gespeichert)
- Favoriten, Einkaufslisten und Profileinstellungen pro Account
- Gespeicherte Daten werden beim nächsten Login wieder geladen

## Stack

- Backend: Python (`http.server`) + SQLite
- Frontend: Vanilla HTML/CSS/JS

## Lokal starten

```bash
python3 app.py
```

Dann im Browser öffnen: `http://localhost:3000`

## Eigenes JSON mit vielen Rezepten einbinden (z. B. 800 Rezepte)

Die App kann statt des eingebauten Katalogs ein externes Rezept-JSON laden.

1. Lege dein JSON als `recipes.json` im Projekt-Root ab  
   *(alternativ beliebiger Pfad über `RECIPE_JSON_PATH`)*.
2. Starte die App normal, oder mit explizitem Pfad:

```bash
RECIPE_JSON_PATH=/pfad/zu/deinen-rezepten.json python3 app.py
```

### Wo auf GitHub hochladen? (konkret)

**Empfohlen:** direkt ins Projekt-Root (also in denselben Ordner wie `app.py`).

Dann sollte deine Repo-Struktur z. B. so aussehen:

```text
Myapp/
├─ app.py
├─ README.md
├─ recipes.json   ← hier
├─ public/
└─ ...
```

**Dateiname:** standardmäßig genau **`recipes.json`**.

Dann musst du nichts weiter konfigurieren, weil das Backend automatisch diese Datei sucht.

Wenn die Datei anders heißt oder in einem Unterordner liegt, setze auf Render (oder lokal) die Umgebungsvariable:

```bash
RECIPE_JSON_PATH=/opt/render/project/src/dein-ordner/deine-datei.json
```

### Erwartetes JSON-Format

Die Datei kann entweder direkt eine Liste von Rezepten sein:

```json
[
  {
    "name": "Tomatenpasta",
    "category": "Hauptgericht",
    "duration": 20,
    "cuisine": "Italienisch",
    "calories": 540,
    "protein": 18,
    "image": "https://...",
    "description": "Schnell und einfach",
    "ingredients": ["200 g Pasta", "400 g Tomaten"],
    "steps": ["Pasta kochen", "Sauce machen"],
    "nutrition": { "kcal": 540, "carbs": 70, "protein": 18, "fat": 12 },
    "diet_tags": ["vegetarisch"]
  }
]
```

...oder ein Objekt mit `recipes` (oder `data`) als Liste enthalten.

Hinweise:
- `name`/`title`, `steps`/`instructions`, `image`/`image_url` werden unterstützt.
- `ingredients_count` wird automatisch aus `ingredients` abgeleitet, falls nicht gesetzt.
- Ungültige Einträge werden übersprungen; beim Start siehst du dazu Logs in der Konsole.
- Zusätzlich wird auch dein deutsches Schema unterstützt, z. B.:
  - `bezeichnung`
  - `zubereitungsdauer_minuten`
  - `ernaehrungsart`
  - `zutaten` als Objekte mit `name`, `menge`, `einheit` (werden strukturiert übernommen)
  - `naehrwerte.kalorien_kcal`, `naehrwerte.kohlenhydrate_g`, `naehrwerte.eiweiss_g`, `naehrwerte.fett_g`
  - `bild_url`


## Muss `app.py` auf meinem Laptop laufen?

**Kurz: Ja, wenn du nur lokal startest.**

- Wenn du `python3 app.py` auf deinem Laptop startest, ist dein Laptop der Server.
- Andere Geräte können die App dann nur nutzen, solange dein Laptop läuft und erreichbar ist.
- Für "von überall" solltest du die App auf einem **dauerhaft laufenden Server/Cloud-Dienst** deployen (z. B. Render).

Dann gilt:
- Nicht dein Laptop hostet die App, sondern der Cloud-Server.
- Deine Android/Cordova-App spricht die öffentliche URL an (z. B. `https://deine-app.onrender.com`).


## Ohne Laptop: Schnellster Weg (Render, Schritt für Schritt)

Wenn du willst, dass die App **ohne deinen Laptop** läuft, muss sie auf einem Internet-Server laufen.
Der einfachste Weg für dich ist Render:

1. Erstelle einen GitHub-Account (falls noch nicht vorhanden)
2. Lade dieses Projekt als Repository zu GitHub hoch
3. Gehe auf https://render.com und logge dich ein
4. Klicke auf **New +** → **Blueprint**
5. Wähle dein GitHub-Repository aus
6. Render erkennt die Datei `render.yaml` automatisch und erstellt den Service
7. Warte bis Deploy fertig ist
8. Öffne die URL von Render (z. B. `https://myapp-rezepte.onrender.com`)

Danach gilt:
- Deine App läuft auf Render weiter, auch wenn dein Laptop aus ist.
- Deine Cordova/Android-App kann diese öffentliche URL nutzen.

> Hinweis zu Daten: Die App nutzt aktuell SQLite (`app.db`). Auf kostenlosen Cloud-Instanzen kann Speicher flüchtig sein.
> Das heißt: Daten können nach Neustarts verloren gehen. Für dauerhaft sichere Daten ist später eine externe Datenbank sinnvoll.

## Von überall erreichbar machen (einfachster Weg)

Wenn du möchtest, dass die App auch auf anderen Geräten (z. B. Android) funktioniert, ist der einfachste Weg:

1. **Code bei GitHub hochladen**
2. **Bei Render.com einen Web Service erstellen**
3. Start Command: `python3 app.py`
4. Render setzt automatisch den richtigen `PORT` (wird von der App unterstützt)
5. Du bekommst eine öffentliche URL wie `https://deine-app.onrender.com`

Dann ist die App weltweit erreichbar.

## Cordova / APK

Falls du eine Cordova-APK nutzt und die API auf einer anderen Domain läuft, kannst du die API-URL setzen:

```js
window.MYAPP_API_BASE_URL = 'https://deine-app.onrender.com';
```

Alternativ kann sie auch in `localStorage` gesetzt werden:

```js
localStorage.setItem('myapp_api_base_url', 'https://deine-app.onrender.com');
```

### Cordova schnell bauen (Android APK)

Die Frontend-Dateien sind so vorbereitet, dass sie im Cordova-`file://`-Kontext laufen.

- CSS/JS werden relativ geladen (wichtig für Cordova-Assets)
- Wenn keine API-URL gesetzt ist, nutzt die App in Cordova automatisch:
  `https://myapp-rezepte.onrender.com`

Einfacher Build-Ablauf:

```bash
cordova platform add android
cordova build android --release -- --packageType=apk
```

### AdMob in Cordova neu einrichten

Für die neue, einfache AdMob-Integration in der Profilansicht erwartet das Frontend das Cordova-Plugin **`admob-plus-cordova`**. Ohne dieses Plugin meldet der Button **"Werbung anzeigen"** bewusst einen klaren Fehler.

Plugin-Installation im Cordova-Wrapper:

```bash
cordova plugin add admob-plus-cordova --save --variable APP_ID_ANDROID=ca-app-pub-ANDROID_APP_ID --variable APP_ID_IOS=ca-app-pub-IOS_APP_ID
```

Plugin-Version prüfen/aktualisieren:

```bash
cordova plugin list | grep admob-plus
cordova plugin rm admob-plus-cordova
cordova plugin add admob-plus-cordova@2.0.0-alpha.19 --save --variable APP_ID_ANDROID=ca-app-pub-ANDROID_APP_ID --variable APP_ID_IOS=ca-app-pub-IOS_APP_ID
```

Wichtig:

- Die **App-IDs** kommen beim Plugin-Install als Variablen hinein, nicht in `public/app.js`.
- Für lokale Tests solltest du die offiziellen Google-Test-App-IDs verwenden:
  - Android: `ca-app-pub-3940256099942544~3347511713`
  - iOS: `ca-app-pub-3940256099942544~1458002511`
- Wenn das Laden trotz korrekter App-ID hängt, liegt es in der Praxis oft an Consent/Datenschutz-Flow (UMP) oder Netzwerkrestriktionen auf dem Gerät.
- Das Frontend nutzt aktuell automatisch Googles **Test-Interstitial-ID**, solange keine eigene Ad-Unit gesetzt wurde.
- Deine echte Interstitial-Ad-Unit kannst du später z. B. per Runtime-Konfiguration setzen:

```js
window.MYAPP_ADMOB_CONFIG = {
  android: {
    interstitialAdUnitId: 'ca-app-pub-.../...',
  },
  ios: {
    interstitialAdUnitId: 'ca-app-pub-.../...',
  },
};
```

Alternativ kannst du dieselbe Struktur auch in `localStorage` unter `myapp_admob_config` speichern.

Typische Fehlerbilder beim Laden:

- **Kein Fill (`no fill`, meist Fehlercode 3)**: Es gibt in diesem Moment für Gerät/Standort/Anfrage keine passende Anzeige. Das ist kein Codefehler und kann temporär sein.
- **Fehlende Einwilligung (UMP/GDPR)**: Wenn personalisierte Werbung nur nach Consent erlaubt ist, muss der Consent-Dialog vorher vollständig abgeschlossen werden.
- **Falscher Ad-Unit-Typ**: Für `new admob.InterstitialAd(...)` muss eine normale **Interstitial-ID** verwendet werden. Eine **Rewarded** oder **Rewarded-Interstitial-ID** kann zu Ladefehlern führen.
- **Netzwerk blockiert trotz Internet**: VPN, Private DNS, Firewall/Adblocker oder restriktives WLAN können AdMob-Requests unterbinden.

### Statusleiste in Cordova ausblenden

Damit die Android-Statusleiste (Uhrzeit/Akku/weißer Balken oben) wirklich verschwindet, reicht reines Frontend-CSS nicht aus.
Die App nutzt dafür in Cordova die StatusBar-API. Falls das Plugin in deinem Cordova-Projekt noch fehlt, ergänze es zusätzlich im eigentlichen Cordova-Wrapper:

```bash
cordova plugin add cordova-plugin-statusbar
```

Optional kannst du in `config.xml` zusätzlich eine immersive Darstellung erzwingen, z. B. mit:

```xml
<preference name="Fullscreen" value="true" />
```

Wenn du später einen anderen Server nutzen willst, setze vor dem Build die gewünschte URL
über `window.MYAPP_API_BASE_URL` oder `localStorage` (siehe oben).

## Google-Login (Render + Google Cloud)

Bei Fehlern wie **`Error 400: origin_mismatch`** muss die Render-Domain in der Google-Cloud-OAuth-Konfiguration hinterlegt sein.

1. Öffne in der Google Cloud Console: **APIs & Services → Credentials**
2. Wähle deinen **OAuth 2.0 Client (Web application)**
3. Trage unter **Authorized JavaScript origins** ein:
   - `https://myapp-rezepte.onrender.com`
4. Speichere die Änderung
5. Setze auf Render die Environment-Variable `GOOGLE_CLIENT_ID` auf genau diese Client-ID

Wichtig: Frontend und Backend müssen dieselbe Google-Client-ID verwenden.

## Feedback-E-Mails (wichtig für Gmail)

Damit der Feedback-Button wirklich E-Mails versendet, müssen auf dem Server die SMTP-Variablen gesetzt sein.

Für Gmail funktioniert das typischerweise so:

- `FEEDBACK_SMTP_USER=bitematch.de@gmail.com`
- `FEEDBACK_SMTP_PASSWORD=<dein Google App-Passwort>`
- optional `GMAIL_APP_PASSWORD=<dein Google App-Passwort>` statt `FEEDBACK_SMTP_PASSWORD`
- `FEEDBACK_SMTP_HOST=smtp.gmail.com`
- `FEEDBACK_SMTP_PORT=465`
- optional `FEEDBACK_SMTP_SECURITY=ssl`

Alternativ für STARTTLS:

- `FEEDBACK_SMTP_PORT=587`
- `FEEDBACK_SMTP_SECURITY=starttls`

Wichtig:

- Nach dem Setzen der Variablen auf Render muss der Service neu deployt bzw. neu gestartet werden.
- Das Gmail-App-Passwort darf aus 16 Zeichen bestehen; Leerzeichen in der Eingabe sind zwar zur Lesbarkeit üblich, werden serverseitig jetzt automatisch entfernt.
- `FEEDBACK_SMTP_USER` muss das Gmail-Konto sein, für das das App-Passwort erzeugt wurde.

## Konfigurierbare Umgebungsvariablen

- `HOST` (Default: `0.0.0.0`)
- `PORT` (Default: `3000`)
- `CORS_ALLOW_ORIGIN` (Default: `*`)
- `GOOGLE_CLIENT_ID` (Default: eingebauter Web-Client; für Deployments auf Render explizit setzen)
- `FEEDBACK_RECIPIENT` (Default: `bitematch.de@gmail.com`)
- `FEEDBACK_SMTP_HOST` (Default: `smtp.gmail.com`)
- `FEEDBACK_SMTP_PORT` (Default: `465`)
- `FEEDBACK_SMTP_USER` (Default: Wert von `FEEDBACK_RECIPIENT`)
- `FEEDBACK_SMTP_PASSWORD` (alternativ `GMAIL_APP_PASSWORD`)
- `FEEDBACK_SMTP_SECURITY` (`auto`, `ssl` oder `starttls`; Default: `auto`)

Beispiel lokal:

```bash
HOST=0.0.0.0 PORT=3000 CORS_ALLOW_ORIGIN=* python3 app.py
```
