# MyApp – Rezept-App

Jetzt mit **Google-Login** und nutzerbezogener Speicherung.

## Features

- Login/Registrierung mit Google-Konto
- Favoriten pro Account
- Einkaufslisten pro Account
- Profileinstellungen pro Account
- Daten bleiben beim erneuten Login (auch auf anderem Gerät, solange derselbe Server genutzt wird)

## Stack

- Frontend: HTML/CSS/JavaScript
- Backend: Python (`http.server`)
- Datenbank: SQLite (`sqlite3`)

## Start

```bash
export GOOGLE_CLIENT_ID="deine-google-client-id.apps.googleusercontent.com"
python3 app.py
```

Dann im Browser öffnen: `http://localhost:3000`

## Google OAuth einrichten

1. In der Google Cloud Console ein OAuth Client (Web) erstellen.
2. JavaScript Origin z. B. `http://localhost:3000` eintragen.
3. Client-ID als `GOOGLE_CLIENT_ID` setzen.

