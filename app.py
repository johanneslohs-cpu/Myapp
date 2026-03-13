import hashlib
import hmac
import json
import secrets
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "app.db"

GUEST_DATA = {}


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def table_columns(db, table_name):
    return {r["name"] for r in db.execute(f"PRAGMA table_info({table_name})").fetchall()}


def ensure_column(db, table_name, column_name, ddl):
    if column_name not in table_columns(db, table_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")




def migrate_user_scoped_tables(db):
    fav_cols = table_columns(db, "favorites")
    if "id" not in fav_cols:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS favorites_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              recipe_id INTEGER NOT NULL,
              user_id INTEGER,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(recipe_id, user_id)
            );
            INSERT OR IGNORE INTO favorites_new (recipe_id, user_id, created_at)
            SELECT recipe_id, user_id, COALESCE(created_at, CURRENT_TIMESTAMP) FROM favorites;
            DROP TABLE favorites;
            ALTER TABLE favorites_new RENAME TO favorites;
            """
        )

    dis_cols = table_columns(db, "dislikes")
    if "id" not in dis_cols:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS dislikes_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              recipe_id INTEGER NOT NULL,
              user_id INTEGER,
              created_at TEXT DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(recipe_id, user_id)
            );
            INSERT OR IGNORE INTO dislikes_new (recipe_id, user_id, created_at)
            SELECT recipe_id, user_id, COALESCE(created_at, CURRENT_TIMESTAMP) FROM dislikes;
            DROP TABLE dislikes;
            ALTER TABLE dislikes_new RENAME TO dislikes;
            """
        )

    ex_cols = table_columns(db, "excluded_ingredients")
    if "user_id" in ex_cols:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS excluded_ingredients_new (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              active INTEGER DEFAULT 1,
              user_id INTEGER,
              UNIQUE(name, user_id)
            );
            INSERT OR IGNORE INTO excluded_ingredients_new (name, active, user_id)
            SELECT name, active, user_id FROM excluded_ingredients;
            DROP TABLE excluded_ingredients;
            ALTER TABLE excluded_ingredients_new RENAME TO excluded_ingredients;
            """
        )

def default_settings(username="Nutzer", avatar="👤"):
    return {
        "username": username,
        "profile_image": avatar,
        "diet": "Ich esse alles",
        "manage_subscription_note": "Hier könntest du dein Abo verwalten.",
        "excluded": [],
    }


def ensure_guest(token):
    if token not in GUEST_DATA:
        GUEST_DATA[token] = {
            "favorites": set(),
            "dislikes": set(),
            "lists": [],
            "next_list_id": 1,
            "settings": default_settings("Gast", "👤"),
        }
    return GUEST_DATA[token]


def hash_password(password):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000)
    return f"{salt}${dk.hex()}"


def verify_password(password, stored):
    if not stored or "$" not in stored:
        return False
    salt, digest = stored.split("$", 1)
    calc = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 200_000).hex()
    return hmac.compare_digest(calc, digest)


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
            CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, user_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            CREATE TABLE IF NOT EXISTS user_settings (user_id INTEGER PRIMARY KEY, username TEXT NOT NULL, profile_image TEXT NOT NULL, diet TEXT NOT NULL, manage_subscription_note TEXT NOT NULL);
            """
        )
        for t in ["favorites", "dislikes", "shopping_lists", "excluded_ingredients", "feedback_messages"]:
            ensure_column(db, t, "user_id", "INTEGER")

        migrate_user_scoped_tables(db)

        ensure_column(db, "users", "password_hash", "TEXT")
        ensure_column(db, "users", "username", "TEXT")
        ensure_column(db, "users", "profile_image", "TEXT")
        ensure_column(db, "sessions", "is_guest", "INTEGER NOT NULL DEFAULT 0")

        ensure_column(db, "user_settings", "manage_subscription_note", "TEXT NOT NULL DEFAULT 'Hier könntest du dein Abo verwalten.'")
        ensure_column(db, "user_settings", "username", "TEXT NOT NULL DEFAULT 'Nutzer'")
        ensure_column(db, "user_settings", "profile_image", "TEXT NOT NULL DEFAULT '👤'")
        ensure_column(db, "user_settings", "diet", "TEXT NOT NULL DEFAULT 'Ich esse alles'")

        seed_recipes(db)


def row_to_recipe(r):
    return {
        "id": r["id"], "name": r["name"], "category": r["category"], "duration": r["duration"],
        "ingredients_count": r["ingredients_count"], "cuisine": r["cuisine"], "calories": r["calories"],
        "protein": r["protein"], "image": r["image"], "description": r["description"] or "",
        "ingredients": json.loads(r["ingredients_json"]), "steps": json.loads(r["steps_json"]),
        "nutrition": json.loads(r["nutrition_json"]), "diet_tags": json.loads(r["diet_tags"]),
    }


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

    def auth_identity(self, db):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[len("Bearer "):].strip()
        else:
            token = ""
        token = token or self.headers.get("X-Auth-Token", "")
        if not token:
            return None
        s = db.execute("SELECT token,user_id,is_guest FROM sessions WHERE token=?", (token,)).fetchone()
        if not s:
            return None
        if s["is_guest"]:
            return {"token": token, "is_guest": True, "user_id": None}
        exists = db.execute("SELECT id FROM users WHERE id=?", (s["user_id"],)).fetchone()
        if not exists:
            db.execute("DELETE FROM sessions WHERE token=?", (token,))
            return None
        return {"token": token, "is_guest": False, "user_id": s["user_id"]}

    def require_identity(self, db):
        ident = self.auth_identity(db)
        if not ident:
            self.send_json({"error": "Nicht eingeloggt"}, 401)
            return None
        return ident

    def ensure_user_defaults(self, db, user_id, username="Nutzer", picture="👤"):
        if not db.execute("SELECT 1 FROM user_settings WHERE user_id=?", (user_id,)).fetchone():
            db.execute(
                "INSERT INTO user_settings (user_id, username, profile_image, diet, manage_subscription_note) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, picture, "Ich esse alles", "Hier könntest du dein Abo verwalten."),
            )

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        q = parse_qs(parsed.query)

        with conn() as db:
            if p == "/api/auth/me":
                ident = self.require_identity(db)
                if not ident:
                    return
                if ident["is_guest"]:
                    self.send_json({"mode": "guest", "name": "Gast"})
                    return
                u = db.execute("SELECT id,email,username,profile_image FROM users WHERE id=?", (ident["user_id"],)).fetchone()
                self.send_json({"mode": "user", **dict(u)})
                return

            if p.startswith("/api/"):
                ident = self.require_identity(db)
                if not ident:
                    return
            else:
                ident = None

            if p == "/api/recipes":
                rows = [row_to_recipe(r) for r in db.execute("SELECT * FROM recipes WHERE name LIKE ?", (f"%{q.get('search', [''])[0]}%",)).fetchall()]
                if ident["is_guest"]:
                    guest = ensure_guest(ident["token"])
                    favs = guest["favorites"]
                    excludes = [e["name"].lower() for e in guest["settings"]["excluded"] if e.get("active")]
                    diet = guest["settings"]["diet"]
                else:
                    uid = ident["user_id"]
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
                if ident["is_guest"]:
                    guest = ensure_guest(ident["token"])
                    disliked, favs = guest["dislikes"], guest["favorites"]
                else:
                    uid = ident["user_id"]
                    disliked = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes WHERE user_id=?", (uid,)).fetchall()}
                    favs = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM favorites WHERE user_id=?", (uid,)).fetchall()}
                self.send_json([r for r in rows if r["id"] not in disliked and r["id"] not in favs])
                return

            if p == "/api/dislikes":
                if ident["is_guest"]:
                    self.send_json(list(ensure_guest(ident["token"])["dislikes"]))
                else:
                    uid = ident["user_id"]
                    self.send_json([r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes WHERE user_id=?", (uid,)).fetchall()])
                return

            if p == "/api/favorites":
                if ident["is_guest"]:
                    favs = list(ensure_guest(ident["token"])["favorites"])
                    if not favs:
                        self.send_json([])
                        return
                    marks = ",".join(["?"] * len(favs))
                    rows = [row_to_recipe(r) for r in db.execute(f"SELECT * FROM recipes WHERE id IN ({marks})", tuple(favs)).fetchall()]
                else:
                    uid = ident["user_id"]
                    rows = [row_to_recipe(r) for r in db.execute("SELECT r.* FROM recipes r JOIN favorites f ON f.recipe_id=r.id WHERE f.user_id=?", (uid,)).fetchall()]
                self.send_json(rows)
                return

            if p == "/api/lists":
                if ident["is_guest"]:
                    self.send_json(ensure_guest(ident["token"])["lists"])
                else:
                    uid = ident["user_id"]
                    rows = []
                    for row in db.execute("SELECT * FROM shopping_lists WHERE user_id=? ORDER BY updated_at DESC", (uid,)).fetchall():
                        data = dict(row)
                        data["items"] = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (data["id"],)).fetchall()]
                        rows.append(data)
                    self.send_json(rows)
                return

            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3])
                if ident["is_guest"]:
                    lst = next((x for x in ensure_guest(ident["token"])["lists"] if x["id"] == lid), None)
                    if not lst:
                        self.send_json({"error": "Nicht gefunden"}, 404)
                        return
                    self.send_json(lst)
                else:
                    uid = ident["user_id"]
                    lst = db.execute("SELECT * FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid)).fetchone()
                    if not lst:
                        self.send_json({"error": "Nicht gefunden"}, 404)
                        return
                    data = dict(lst)
                    data["items"] = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (lid,)).fetchall()]
                    self.send_json(data)
                return

            if p == "/api/settings":
                if ident["is_guest"]:
                    self.send_json(ensure_guest(ident["token"])["settings"])
                else:
                    uid = ident["user_id"]
                    s = db.execute("SELECT * FROM user_settings WHERE user_id=?", (uid,)).fetchone()
                    if not s:
                        self.ensure_user_defaults(db, uid)
                        s = db.execute("SELECT * FROM user_settings WHERE user_id=?", (uid,)).fetchone()
                    data = dict(s)
                    data["excluded"] = [dict(r) for r in db.execute("SELECT * FROM excluded_ingredients WHERE user_id=?", (uid,)).fetchall()]
                    self.send_json(data)
                return

        fpath = PUBLIC / ("index.html" if p == "/" else p.lstrip("/"))
        if fpath.exists() and fpath.is_file():
            ctype = "text/plain"
            if fpath.suffix == ".html":
                ctype = "text/html; charset=utf-8"
            if fpath.suffix == ".css":
                ctype = "text/css; charset=utf-8"
            if fpath.suffix == ".js":
                ctype = "application/javascript; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(fpath.read_bytes())
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write((PUBLIC / "index.html").read_bytes())

    def do_POST(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            if p == "/api/auth/register":
                email = (b.get("email") or "").strip().lower()
                password = b.get("password") or ""
                username = (b.get("username") or "Nutzer").strip() or "Nutzer"
                if "@" not in email or len(password) < 6:
                    self.send_json({"error": "Ungültige Daten"}, 400)
                    return
                exists = db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()
                if exists:
                    self.send_json({"error": "E-Mail bereits vergeben"}, 409)
                    return
                db.execute(
                    "INSERT INTO users (google_sub,email,name,picture,password_hash,username,profile_image,updated_at) VALUES (?,?,?,?,?,?,?,?)",
                    (f"local:{email}", email, username, "👤", hash_password(password), username, "👤", datetime.utcnow().isoformat()),
                )
                user_id = db.execute("SELECT id FROM users WHERE lower(email)=?", (email,)).fetchone()["id"]
                self.ensure_user_defaults(db, user_id, username, "👤")
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions (token,user_id,is_guest) VALUES (?,?,0)", (token, user_id))
                self.send_json({"token": token, "mode": "user"})
                return

            if p == "/api/auth/login":
                email = (b.get("email") or "").strip().lower()
                password = b.get("password") or ""
                user = db.execute("SELECT id,password_hash,username,profile_image FROM users WHERE lower(email)=?", (email,)).fetchone()
                if not user or not verify_password(password, user["password_hash"]):
                    self.send_json({"error": "E-Mail oder Passwort falsch"}, 401)
                    return
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions (token,user_id,is_guest) VALUES (?,?,0)", (token, user["id"]))
                self.ensure_user_defaults(db, user["id"], user["username"] or "Nutzer", user["profile_image"] or "👤")
                self.send_json({"token": token, "mode": "user"})
                return

            if p == "/api/auth/guest":
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions (token,user_id,is_guest) VALUES (?,NULL,1)", (token,))
                ensure_guest(token)
                self.send_json({"token": token, "mode": "guest"})
                return

            ident = self.require_identity(db)
            if not ident:
                return

            if p == "/api/auth/logout":
                db.execute("DELETE FROM sessions WHERE token=?", (ident["token"],))
                if ident["is_guest"] and ident["token"] in GUEST_DATA:
                    del GUEST_DATA[ident["token"]]
                self.send_json({"ok": True})
                return

            if p.endswith("/like") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    g["favorites"].add(rid)
                    g["dislikes"].discard(rid)
                else:
                    uid = ident["user_id"]
                    db.execute("INSERT OR IGNORE INTO favorites (recipe_id,user_id) VALUES (?,?)", (rid, uid))
                    db.execute("DELETE FROM dislikes WHERE recipe_id=? AND user_id=?", (rid, uid))
                self.send_json({"ok": True})
                return

            if p.endswith("/dislike") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    g["dislikes"].add(rid)
                    g["favorites"].discard(rid)
                else:
                    uid = ident["user_id"]
                    db.execute("INSERT OR IGNORE INTO dislikes (recipe_id,user_id) VALUES (?,?)", (rid, uid))
                    db.execute("DELETE FROM favorites WHERE recipe_id=? AND user_id=?", (rid, uid))
                self.send_json({"ok": True})
                return

            if p == "/api/lists":
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    lid = g["next_list_id"]
                    g["next_list_id"] += 1
                    row = {"id": lid, "name": b.get("name"), "color": b.get("color", "#7ed6df"), "updated_at": datetime.utcnow().isoformat(), "items": []}
                    g["lists"].insert(0, row)
                    self.send_json(row)
                else:
                    uid = ident["user_id"]
                    db.execute("INSERT INTO shopping_lists (name,color,updated_at,user_id) VALUES (?,?,?,?)", (b.get("name"), b.get("color", "#7ed6df"), datetime.utcnow().isoformat(), uid))
                    lid = db.execute("SELECT id FROM shopping_lists ORDER BY id DESC LIMIT 1").fetchone()[0]
                    self.send_json(dict(db.execute("SELECT * FROM shopping_lists WHERE id=?", (lid,)).fetchone()))
                return

            if p == "/api/excluded":
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    name = (b.get("name") or "").strip()
                    if not name:
                        self.send_json({"error": "Name fehlt"}, 400)
                        return
                    existing = next((e for e in g["settings"]["excluded"] if e["name"].lower() == name.lower()), None)
                    if existing:
                        existing["active"] = 1
                    else:
                        next_id = max([x["id"] for x in g["settings"]["excluded"]], default=0) + 1
                        g["settings"]["excluded"].append({"id": next_id, "name": name, "active": 1})
                else:
                    db.execute("INSERT OR IGNORE INTO excluded_ingredients (name,active,user_id) VALUES (?,?,?)", (b.get("name"), 1, ident["user_id"]))
                self.send_json({"ok": True})
                return

            if p == "/api/feedback":
                if not ident["is_guest"]:
                    db.execute("INSERT INTO feedback_messages (email,subject,message,user_id) VALUES (?,?,?,?)", (b.get("email"), b.get("subject"), b.get("message"), ident["user_id"]))
                self.send_json({"ok": True})
                return

            if p == "/api/dislikes/reset":
                if ident["is_guest"]:
                    ensure_guest(ident["token"])["dislikes"].clear()
                else:
                    db.execute("DELETE FROM dislikes WHERE user_id=?", (ident["user_id"],))
                self.send_json({"ok": True})
                return

        self.send_json({"error": "Unbekannt"}, 404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            ident = self.require_identity(db)
            if not ident:
                return
            if p == "/api/settings":
                if ident["is_guest"]:
                    s = ensure_guest(ident["token"])["settings"]
                    s["username"] = b.get("username", s["username"])
                    s["diet"] = b.get("diet", s["diet"])
                    s["profile_image"] = b.get("profile_image", s["profile_image"])
                else:
                    uid = ident["user_id"]
                    cur = dict(db.execute("SELECT * FROM user_settings WHERE user_id=?", (uid,)).fetchone())
                    db.execute("UPDATE user_settings SET username=?,diet=?,profile_image=? WHERE user_id=?", (b.get("username", cur["username"]), b.get("diet", cur["diet"]), b.get("profile_image", cur["profile_image"]), uid))
                    db.execute("UPDATE users SET username=?, profile_image=?, updated_at=? WHERE id=?", (b.get("username", cur["username"]), b.get("profile_image", cur["profile_image"]), datetime.utcnow().isoformat(), uid))
                self.send_json({"ok": True})
                return

            if p.startswith("/api/excluded/"):
                eid = int(p.split("/")[3])
                if ident["is_guest"]:
                    ex = next((e for e in ensure_guest(ident["token"])["settings"]["excluded"] if e["id"] == eid), None)
                    if ex:
                        ex["active"] = 1 if b.get("active") else 0
                else:
                    db.execute("UPDATE excluded_ingredients SET active=? WHERE id=? AND user_id=?", (1 if b.get("active") else 0, eid, ident["user_id"]))
                self.send_json({"ok": True})
                return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_PUT(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            ident = self.require_identity(db)
            if not ident:
                return
            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    lst = next((x for x in g["lists"] if x["id"] == lid), None)
                    if not lst:
                        self.send_json({"error": "Nicht gefunden"}, 404)
                        return
                    lst["name"] = b.get("name", lst["name"])
                    lst["updated_at"] = datetime.utcnow().isoformat()
                    lst["items"] = [{"name": it.get("name"), "checked": bool(it.get("checked")), "image": it.get("image", "🧾")} for it in b.get("items", [])]
                else:
                    uid = ident["user_id"]
                    owned = db.execute("SELECT id FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid)).fetchone()
                    if not owned:
                        self.send_json({"error": "Nicht gefunden"}, 404)
                        return
                    db.execute("UPDATE shopping_lists SET name=?, updated_at=? WHERE id=?", (b.get("name"), datetime.utcnow().isoformat(), lid))
                    db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
                    for it in b.get("items", []):
                        db.execute("INSERT INTO shopping_items (list_id,name,checked,image) VALUES (?,?,?,?)", (lid, it.get("name"), 1 if it.get("checked") else 0, it.get("image", "🧾")))
                self.send_json({"ok": True})
                return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        with conn() as db:
            ident = self.require_identity(db)
            if not ident:
                return
            if p.startswith("/api/favorites/"):
                rid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    g["favorites"].discard(rid)
                    g["dislikes"].discard(rid)
                else:
                    uid = ident["user_id"]
                    db.execute("DELETE FROM favorites WHERE recipe_id=? AND user_id=?", (rid, uid))
                    db.execute("DELETE FROM dislikes WHERE recipe_id=? AND user_id=?", (rid, uid))
                self.send_json({"ok": True})
                return
            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    g["lists"] = [l for l in g["lists"] if l["id"] != lid]
                else:
                    uid = ident["user_id"]
                    db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
                    db.execute("DELETE FROM shopping_lists WHERE id=? AND user_id=?", (lid, uid))
                self.send_json({"ok": True})
                return
        self.send_json({"error": "Unbekannt"}, 404)


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", 3000), Handler)
    print("App läuft auf http://localhost:3000")
    server.serve_forever()
