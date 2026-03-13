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

## Start

```bash
python3 app.py
```

Dann im Browser öffnen: `http://localhost:3000`
