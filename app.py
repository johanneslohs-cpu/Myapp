import json
import os
import secrets
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "app.db"
GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "1014015739173-sj85p3bdscndu859jtveok8kjrgfqr2q.apps.googleusercontent.com",
)


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def table_columns(db, table_name):
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_column(db, table_name, column_name, ddl):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def seed_recipes(db):
    if db.execute("SELECT COUNT(*) FROM recipes").fetchone()[0] > 0:
        return
    recipes = [
        ("Spaghetti Bolognese", "Hauptgericht", 20, 8, "Italienisch", 473, 28, "🍝", "Klassisch.", ["Spaghetti", "Tomatensauce", "Hackfleisch"], ["Nudeln kochen", "Sauce kochen"], {"kcal": 473, "carbs": 52, "protein": 28, "fat": 17}, ["high-protein"]),
        ("Pizza Margherita", "Dinner", 30, 6, "Italienisch", 420, 16, "🍕", "Einfach.", ["Teig", "Mozzarella", "Tomatensauce"], ["Belegen", "Backen"], {"kcal": 420, "carbs": 48, "protein": 16, "fat": 18}, ["vegetarisch"]),
        ("Shakshuka", "Frühstück", 22, 7, "Orientalisch", 360, 24, "🍳", "Aromatisch.", ["Eier", "Tomaten", "Paprika"], ["Sauce", "Eier stocken"], {"kcal": 360, "carbs": 14, "protein": 24, "fat": 21}, ["vegetarisch", "low-carb"]),
    ]
    for r in recipes:
        db.execute(
            """
            INSERT INTO recipes (name, category, duration, ingredients_count, cuisine, calories, protein, image, description, ingredients_json, steps_json, nutrition_json, diet_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], json.dumps(r[9]), json.dumps(r[10]), json.dumps(r[11]), json.dumps(r[12])),
        )


def init_db():
    with conn() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS recipes (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              category TEXT NOT NULL,
              duration INTEGER NOT NULL,
              ingredients_count INTEGER NOT NULL,
              cuisine TEXT NOT NULL,
              calories INTEGER NOT NULL,
              protein INTEGER NOT NULL,
              image TEXT NOT NULL,
              description TEXT,
              ingredients_json TEXT NOT NULL,
              steps_json TEXT NOT NULL,
              nutrition_json TEXT NOT NULL,
              diet_tags TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS favorites (recipe_id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS dislikes (recipe_id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS shopping_lists (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, color TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS shopping_items (id INTEGER PRIMARY KEY AUTOINCREMENT, list_id INTEGER NOT NULL, name TEXT NOT NULL, checked INTEGER DEFAULT 0, image TEXT DEFAULT '🧾');
            CREATE TABLE IF NOT EXISTS excluded_ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS feedback_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, subject TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, google_sub TEXT UNIQUE NOT NULL, email TEXT, name TEXT, picture TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, username TEXT NOT NULL, profile_image TEXT NOT NULL, diet TEXT NOT NULL, manage_subscription_note TEXT NOT NULL);
            """
        )

        for t in ["favorites", "dislikes", "shopping_lists", "excluded_ingredients", "feedback_messages"]:
            ensure_column(db, t, "user_id", "INTEGER")

        ensure_column(db, "users", "email", "TEXT")
        ensure_column(db, "users", "name", "TEXT")
        ensure_column(db, "users", "picture", "TEXT")
        ensure_column(db, "users", "created_at", "TEXT DEFAULT CURRENT_TIMESTAMP")
        ensure_column(db, "users", "updated_at", "TEXT DEFAULT CURRENT_TIMESTAMP")

        ensure_column(db, "user_settings", "manage_subscription_note", "TEXT NOT NULL DEFAULT 'Hier könntest du dein Abo verwalten.'")

        seed_recipes(db)


def row_to_recipe(r):
    return {
        "id": r["id"], "name": r["name"], "category": r["category"], "duration": r["duration"],
        "ingredients_count": r["ingredients_count"], "cuisine": r["cuisine"], "calories": r["calories"],
        "protein": r["protein"], "image": r["image"], "description": r["description"],
        "ingredients": json.loads(r["ingredients_json"]), "steps": json.loads(r["steps_json"]),
        "nutrition": json.loads(r["nutrition_json"]), "diet_tags": json.loads(r["diet_tags"]),
    }


def verify_google_token(credential):
    with urlopen(f"https://oauth2.googleapis.com/tokeninfo?id_token={credential}") as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    if GOOGLE_CLIENT_ID and payload.get("aud") != GOOGLE_CLIENT_ID:
        raise ValueError("Google Client ID stimmt nicht überein")
    return payload


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        b = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def body(self):
        l = int(self.headers.get("Content-Length", 0))
        if l <= 0:
            return {}
        return json.loads(self.rfile.read(l).decode("utf-8"))

    def auth_user(self, db):
        auth = self.headers.get("Authorization", "")
        token = auth.removeprefix("Bearer ").strip() or self.headers.get("X-Auth-Token", "")
        if not token:
            return None
        row = db.execute("SELECT user_id FROM sessions WHERE token=?", (token,)).fetchone()
        return row["user_id"] if row else None

    def require_user(self, db):
        uid = self.auth_user(db)
        if not uid:
            self.send_json({"error": "Nicht eingeloggt"}, 401)
            return None
        return uid

    def ensure_user_defaults(self, db, user_id, username="Neuer Nutzer", picture="👤"):
        existing = db.execute("SELECT user_id FROM user_settings WHERE user_id=?", (user_id,)).fetchone()
        if not existing:
            db.execute(
                "INSERT INTO user_settings (user_id, username, profile_image, diet, manage_subscription_note) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, picture, "Ich esse alles", "Hier könntest du dein Abo verwalten."),
            )

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        q = parse_qs(parsed.query)

        if p == "/api/config":
            self.send_json({"googleClientId": GOOGLE_CLIENT_ID})
            return

        with conn() as db:
            if p == "/api/auth/me":
                uid = self.require_user(db)
                if not uid:
                    return
                u = db.execute("SELECT id,email,name,picture FROM users WHERE id=?", (uid,)).fetchone()
                self.send_json(dict(u))
                return

            if p.startswith("/api/") and p not in ["/api/config", "/api/auth/me"]:
                uid = self.require_user(db)
                if not uid:
                    return
            else:
                uid = None

            if p == "/api/recipes":
                rows = [row_to_recipe(r) for r in db.execute("SELECT * FROM recipes WHERE name LIKE ?", (f"%{q.get('search', [''])[0]}%",)).fetchall()]
                favs = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM favorites WHERE user_id=?", (uid,)).fetchall()}
                s = db.execute("SELECT diet FROM user_settings WHERE user_id=?", (uid,)).fetchone()
                diet = s["diet"] if s else "Ich esse alles"
                excludes = [r["name"].lower() for r in db.execute("SELECT name FROM excluded_ingredients WHERE active=1 AND user_id=?", (uid,)).fetchall()]

                def ok(r):
                    if "category" in q and r["category"] != q["category"][0]:
                        return False
                    if "maxCalories" in q and r["calories"] >= int(q["maxCalories"][0]):
                        return False
                    if "minProtein" in q and r["protein"] <= int(q["minProtein"][0]):
                        return False
                    if "maxDuration" in q and r["duration"] >= int(q["maxDuration"][0]):
                        return False
                    if q.get("favoritesOnly", ["0"])[0] == "1" and r["id"] not in favs:
                        return False
                    if diet != "Ich esse alles":
                        d = diet.lower()
                        if "vegetarisch" in d and "vegetarisch" not in r["diet_tags"]:
                            return False
                        if "vegan" in d and "vegan" not in r["diet_tags"]:
                            return False
                    ing = " ".join(r["ingredients"]).lower()
                    return not any(e in ing for e in excludes)

                self.send_json([r for r in rows if ok(r)])
                return

            if p == "/api/swipe-recipes":
                rows = [row_to_recipe(r) for r in db.execute("SELECT * FROM recipes WHERE name LIKE ?", (f"%{q.get('search', [''])[0]}%",)).fetchall()]
                disliked = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes WHERE user_id=?", (uid,)).fetchall()}
                favs = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM favorites WHERE user_id=?", (uid,)).fetchall()}
                self.send_json([r for r in rows if r["id"] not in disliked and r["id"] not in favs])
                return

            if p == "/api/dislikes":
                self.send_json([r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes WHERE user_id=?", (uid,)).fetchall()])
                return

            if p == "/api/favorites":
                rows = [row_to_recipe(r) for r in db.execute("SELECT r.* FROM recipes r JOIN favorites f ON f.recipe_id=r.id WHERE f.user_id=?", (uid,)).fetchall()]
                self.send_json(rows)
                return

            if p == "/api/lists":
                rows = []
                for row in db.execute("SELECT * FROM shopping_lists WHERE user_id=? ORDER BY updated_at DESC", (uid,)).fetchall():
                    data = dict(row)
                    data["items"] = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (data["id"],)).fetchall()]
                    rows.append(data)
                self.send_json(rows)
                return

            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3])
                lst = db.execute("SELECT * FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid)).fetchone()
                if not lst:
                    self.send_json({"error": "Nicht gefunden"}, 404)
                    return
                data = dict(lst)
                data["items"] = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (lid,)).fetchall()]
                self.send_json(data)
                return

            if p == "/api/settings":
                s = db.execute("SELECT * FROM user_settings WHERE user_id=?", (uid,)).fetchone()
                self.send_json({**dict(s), "excluded": [dict(r) for r in db.execute("SELECT * FROM excluded_ingredients WHERE user_id=?", (uid,)).fetchall()]})
                return

        fpath = PUBLIC / ("index.html" if p == "/" else p.lstrip("/"))
        if fpath.exists() and fpath.is_file():
            ctype = "text/plain"
            if fpath.suffix == ".html": ctype = "text/html; charset=utf-8"
            if fpath.suffix == ".css": ctype = "text/css; charset=utf-8"
            if fpath.suffix == ".js": ctype = "application/javascript; charset=utf-8"
            self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(fpath.read_bytes()); return
        self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.end_headers(); self.wfile.write((PUBLIC / "index.html").read_bytes())

    def do_POST(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            if p == "/api/auth/google":
                try:
                    payload = verify_google_token(b.get("credential", ""))
                except Exception as e:
                    self.send_json({"error": f"Google-Login fehlgeschlagen: {e}"}, 401)
                    return
                sub = payload.get("sub")
                if not sub:
                    self.send_json({"error": "Ungültiger Google-Token"}, 401)
                    return
                u = db.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()
                if u:
                    user_id = u["id"]
                    db.execute("UPDATE users SET email=?, name=?, picture=?, updated_at=? WHERE id=?", (payload.get("email", ""), payload.get("name", ""), payload.get("picture", ""), datetime.utcnow().isoformat(), user_id))
                else:
                    db.execute("INSERT INTO users (google_sub, email, name, picture, updated_at) VALUES (?, ?, ?, ?, ?)", (sub, payload.get("email", ""), payload.get("name", ""), payload.get("picture", ""), datetime.utcnow().isoformat()))
                    user_id = db.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]
                self.ensure_user_defaults(db, user_id, payload.get("name", "Nutzer"), "👤")
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
                self.send_json({"token": token, "user": {"id": user_id, "email": payload.get("email", ""), "name": payload.get("name", ""), "picture": payload.get("picture", "")}})
                return

            uid = self.require_user(db)
            if not uid:
                return

            if p == "/api/auth/logout":
                token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
                db.execute("DELETE FROM sessions WHERE token=?", (token,))
                self.send_json({"ok": True})
                return
            if p.endswith("/like") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3]); db.execute("INSERT OR IGNORE INTO favorites (recipe_id,user_id) VALUES (?,?)", (rid, uid)); db.execute("DELETE FROM dislikes WHERE recipe_id=? AND user_id=?", (rid, uid)); self.send_json({"ok": True}); return
            if p.endswith("/dislike") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3]); db.execute("INSERT OR IGNORE INTO dislikes (recipe_id,user_id) VALUES (?,?)", (rid, uid)); db.execute("DELETE FROM favorites WHERE recipe_id=? AND user_id=?", (rid, uid)); self.send_json({"ok": True}); return
            if p == "/api/lists":
                db.execute("INSERT INTO shopping_lists (name,color,updated_at,user_id) VALUES (?,?,?,?)", (b.get("name"), b.get("color", "#7ed6df"), datetime.utcnow().isoformat(), uid))
                lid = db.execute("SELECT id FROM shopping_lists ORDER BY id DESC LIMIT 1").fetchone()[0]
                self.send_json(dict(db.execute("SELECT * FROM shopping_lists WHERE id=?", (lid,)).fetchone())); return
            if p == "/api/excluded":
                db.execute("INSERT OR IGNORE INTO excluded_ingredients (name,active,user_id) VALUES (?,?,?)", (b.get("name"), 1, uid)); self.send_json({"ok": True}); return
            if p == "/api/feedback":
                db.execute("INSERT INTO feedback_messages (email,subject,message,user_id) VALUES (?,?,?,?)", (b.get("email"), b.get("subject"), b.get("message"), uid)); self.send_json({"ok": True}); return
            if p == "/api/dislikes/reset":
                db.execute("DELETE FROM dislikes WHERE user_id=?", (uid,)); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            uid = self.require_user(db)
            if not uid:
                return
            if p == "/api/settings":
                cur = dict(db.execute("SELECT * FROM user_settings WHERE user_id=?", (uid,)).fetchone())
                db.execute("UPDATE user_settings SET username=?,diet=?,profile_image=? WHERE user_id=?", (b.get("username", cur["username"]), b.get("diet", cur["diet"]), b.get("profile_image", cur["profile_image"]), uid))
                self.send_json({"ok": True}); return
            if p.startswith("/api/excluded/"):
                eid = int(p.split("/")[3]); db.execute("UPDATE excluded_ingredients SET active=? WHERE id=? AND user_id=?", (1 if b.get("active") else 0, eid, uid)); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_PUT(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            uid = self.require_user(db)
            if not uid:
                return
            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3])
                owned = db.execute("SELECT id FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid)).fetchone()
                if not owned:
                    self.send_json({"error": "Nicht gefunden"}, 404)
                    return
                db.execute("UPDATE shopping_lists SET name=?, updated_at=? WHERE id=?", (b.get("name"), datetime.utcnow().isoformat(), lid))
                db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
                for it in b.get("items", []):
                    db.execute("INSERT INTO shopping_items (list_id,name,checked,image) VALUES (?,?,?,?)", (lid, it.get("name"), 1 if it.get("checked") else 0, it.get("image", "🧾")))
                self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        with conn() as db:
            uid = self.require_user(db)
            if not uid:
                return
            if p.startswith("/api/favorites/"):
                rid = int(p.split("/")[3]); db.execute("DELETE FROM favorites WHERE recipe_id=? AND user_id=?", (rid, uid)); db.execute("DELETE FROM dislikes WHERE recipe_id=? AND user_id=?", (rid, uid)); self.send_json({"ok": True}); return
            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3]); db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,)); db.execute("DELETE FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid)); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", 3000), Handler)
    print("App läuft auf http://localhost:3000")
    server.serve_forever()
