import json
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "app.db"


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


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
            CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK (id=1), username TEXT NOT NULL, profile_image TEXT NOT NULL, diet TEXT NOT NULL, manage_subscription_note TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS excluded_ingredients (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS feedback_messages (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, subject TEXT, message TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
            """
        )
        recipes = [
            ("Spaghetti Bolognese mit Tomatensauce", "Hauptgericht", 20, 16, "Pasta", 473, 28, "https://images.unsplash.com/photo-1621996346565-e3dbc646d9a9?auto=format&fit=crop&w=1200&q=80", "Klassische, herzhafte Pasta.", ["300g Spaghettinudeln", "200g Tomatensauce", "2 Zwiebeln", "4 Knoblauchzehen", "300g Hackfleisch"], ["Nudeln kochen.", "Zwiebeln und Knoblauch anschwitzen.", "Hackfleisch anbraten.", "Tomatensauce dazugeben und köcheln.", "Mit Nudeln servieren."], {"kcal": 473, "carbs": 52, "protein": 28, "fat": 17}, ["high-protein"]),
            ("Pizza Margherita", "Dinner", 30, 8, "Italienisch", 420, 16, "https://images.unsplash.com/photo-1604382355076-af4b0eb60143?auto=format&fit=crop&w=1200&q=80", "Klassische Pizza.", ["Pizzateig", "Tomatensauce", "Mozzarella", "Basilikum"], ["Teig ausrollen.", "Backen."], {"kcal": 420, "carbs": 48, "protein": 16, "fat": 18}, ["vegetarisch"]),
            ("Omelette nach mediterraner Art", "Frühstück", 15, 7, "Mediterran", 310, 22, "https://images.unsplash.com/photo-1510693206972-df098062cb71?auto=format&fit=crop&w=1200&q=80", "Schnell.", ["3 Eier", "Tomaten", "Spinat", "Feta"], ["Verquirlen.", "Braten."], {"kcal": 310, "carbs": 9, "protein": 22, "fat": 20}, ["vegetarisch", "low-carb", "high-protein"]),
            ("Brokkoli-Auflauf", "Hauptgericht", 40, 10, "Ofengericht", 390, 21, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80", "Cremig.", ["Brokkoli", "Sahne", "Käse", "Kartoffeln"], ["Vorgaren.", "Überbacken."], {"kcal": 390, "carbs": 28, "protein": 21, "fat": 22}, ["vegetarisch"]),
            ("Currywurst mit Pommes", "Dinner", 25, 6, "Deutsch", 610, 19, "https://images.unsplash.com/photo-1633321702518-7feccafb94d5?auto=format&fit=crop&w=1200&q=80", "Streetfood.", ["Wurst", "Pommes", "Currysauce"], ["Zubereiten."], {"kcal": 610, "carbs": 45, "protein": 19, "fat": 34}, []),
            ("Linsen-Kokos-Curry", "Hauptgericht", 30, 11, "Indisch", 440, 19, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80", "Wärmend und würzig.", ["Rote Linsen", "Kokosmilch", "Zwiebel", "Knoblauch", "Spinat"], ["Zwiebel anschwitzen.", "Linsen und Gewürze zugeben.", "Mit Kokosmilch köcheln.", "Spinat unterheben."], {"kcal": 440, "carbs": 49, "protein": 19, "fat": 16}, ["vegetarisch"]),
            ("Hähnchen Teriyaki Bowl", "Dinner", 28, 12, "Japanisch", 510, 36, "https://images.unsplash.com/photo-1546069901-ba9599a7e63c?auto=format&fit=crop&w=1200&q=80", "Saftig und ausgewogen.", ["Hähnchenbrust", "Reis", "Brokkoli", "Karotte", "Teriyaki-Sauce"], ["Reis kochen.", "Hähnchen anbraten.", "Gemüse garen.", "Alles mit Sauce mischen."], {"kcal": 510, "carbs": 54, "protein": 36, "fat": 14}, ["high-protein"]),
            ("Shakshuka mit Feta", "Frühstück", 22, 9, "Orientalisch", 360, 24, "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?auto=format&fit=crop&w=1200&q=80", "Tomatig und aromatisch.", ["Eier", "Tomaten", "Paprika", "Zwiebel", "Feta"], ["Gemüse anschwitzen.", "Tomaten einkochen.", "Eier stocken lassen.", "Mit Feta toppen."], {"kcal": 360, "carbs": 14, "protein": 24, "fat": 21}, ["vegetarisch", "low-carb"]),
            ("Ofengemüse mit Halloumi", "Hauptgericht", 35, 10, "Mediterran", 430, 20, "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1200&q=80", "Knusprig aus dem Ofen.", ["Zucchini", "Paprika", "Kichererbsen", "Halloumi", "Olivenöl"], ["Gemüse schneiden.", "Würzen.", "Backen.", "Halloumi kurz mitbacken."], {"kcal": 430, "carbs": 32, "protein": 20, "fat": 23}, ["vegetarisch"]),
            ("Lachs mit Zitronenreis", "Dinner", 27, 9, "Nordisch", 520, 34, "https://images.unsplash.com/photo-1467003909585-2f8a72700288?auto=format&fit=crop&w=1200&q=80", "Frisch und leicht.", ["Lachsfilet", "Reis", "Zitrone", "Dill", "Spinat"], ["Reis kochen.", "Lachs braten.", "Zitronenabrieb einrühren.", "Mit Spinat servieren."], {"kcal": 520, "carbs": 46, "protein": 34, "fat": 22}, ["high-protein"]),
            ("Quinoa-Salat mit Avocado", "Hauptgericht", 18, 10, "Modern", 390, 14, "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80", "Perfekt für Meal Prep.", ["Quinoa", "Avocado", "Tomaten", "Gurke", "Zitrone"], ["Quinoa kochen.", "Gemüse schneiden.", "Dressing anrühren.", "Alles mischen."], {"kcal": 390, "carbs": 41, "protein": 14, "fat": 18}, ["vegetarisch"]),
            ("Putenwrap mit Joghurt-Dip", "Hauptgericht", 20, 8, "Fusion", 410, 31, "https://images.unsplash.com/photo-1525755662778-989d0524087e?auto=format&fit=crop&w=1200&q=80", "Schnell für unterwegs.", ["Vollkorn-Wraps", "Putenbrust", "Salat", "Tomate", "Joghurt"], ["Pute braten.", "Gemüse schneiden.", "Dip rühren.", "Wraps füllen."], {"kcal": 410, "carbs": 36, "protein": 31, "fat": 14}, ["high-protein"]),
            ("Veggie Chili", "Hauptgericht", 32, 13, "Mexikanisch", 370, 18, "https://images.unsplash.com/photo-1515003197210-e0cd71810b5f?auto=format&fit=crop&w=1200&q=80", "Kräftig und sättigend.", ["Kidneybohnen", "Mais", "Tomaten", "Paprika", "Zwiebel"], ["Zwiebel anschwitzen.", "Gemüse zugeben.", "Mit Tomaten köcheln.", "Abschmecken."], {"kcal": 370, "carbs": 46, "protein": 18, "fat": 9}, ["vegetarisch"]),
            ("Bananen-Porridge Deluxe", "Frühstück", 12, 7, "Frühstück", 330, 13, "https://images.unsplash.com/photo-1517673400267-0251440c45dc?auto=format&fit=crop&w=1200&q=80", "Cremig und süß.", ["Haferflocken", "Banane", "Milch", "Zimt", "Nüsse"], ["Haferflocken kochen.", "Banane zerdrücken.", "Unterrühren.", "Mit Nüssen toppen."], {"kcal": 330, "carbs": 49, "protein": 13, "fat": 9}, ["vegetarisch"]),
            ("Rindergeschnetzeltes mit Pilzen", "Dinner", 34, 11, "Deutsch", 560, 39, "https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=1200&q=80", "Deftig und aromatisch.", ["Rindfleisch", "Champignons", "Zwiebel", "Sahne", "Spätzle"], ["Fleisch scharf anbraten.", "Pilze zugeben.", "Sauce rühren.", "Mit Spätzle servieren."], {"kcal": 560, "carbs": 33, "protein": 39, "fat": 29}, ["high-protein"]),
            ("Tomaten-Mozzarella-Pasta", "Hauptgericht", 19, 8, "Italienisch", 450, 17, "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1200&q=80", "Sommerlich leicht.", ["Penne", "Kirschtomaten", "Mozzarella", "Basilikum", "Olivenöl"], ["Pasta kochen.", "Tomaten anrösten.", "Pasta untermischen.", "Mozzarella zugeben."], {"kcal": 450, "carbs": 55, "protein": 17, "fat": 17}, ["vegetarisch"]),
            ("Falafel mit Tahini", "Dinner", 26, 10, "Orientalisch", 470, 18, "https://images.unsplash.com/photo-1540189549336-e6e99c3679fe?auto=format&fit=crop&w=1200&q=80", "Knusprig und würzig.", ["Kichererbsen", "Petersilie", "Knoblauch", "Tahini", "Fladenbrot"], ["Falafelmasse mixen.", "Bällchen formen.", "Ausbacken.", "Mit Tahini servieren."], {"kcal": 470, "carbs": 52, "protein": 18, "fat": 19}, ["vegetarisch"]),
            ("Süßkartoffel-Suppe", "Hauptgericht", 24, 9, "Suppenküche", 340, 9, "https://images.unsplash.com/photo-1547592166-23ac45744acd?auto=format&fit=crop&w=1200&q=80", "Samtig und mild.", ["Süßkartoffel", "Karotte", "Zwiebel", "Gemüsebrühe", "Ingwer"], ["Gemüse würfeln.", "Anschwitzen.", "Brühe zugeben.", "Pürieren."], {"kcal": 340, "carbs": 44, "protein": 9, "fat": 12}, ["vegetarisch"]),
            ("Gebratener Reis mit Ei", "Dinner", 17, 8, "Asiatisch", 400, 16, "https://images.unsplash.com/photo-1512058564366-18510be2db19?auto=format&fit=crop&w=1200&q=80", "Resteverwertung deluxe.", ["Reis", "Eier", "Erbsen", "Karotte", "Sojasauce"], ["Reis anbraten.", "Gemüse zugeben.", "Ei einrühren.", "Würzen."], {"kcal": 400, "carbs": 56, "protein": 16, "fat": 11}, ["vegetarisch"]),
            ("Hüttenkäse-Pfannkuchen", "Frühstück", 14, 6, "Fitness", 290, 27, "https://images.unsplash.com/photo-1528207776546-365bb710ee93?auto=format&fit=crop&w=1200&q=80", "Proteinreich in den Tag.", ["Hüttenkäse", "Eier", "Hafermehl", "Backpulver", "Beeren"], ["Teig mixen.", "Portionieren.", "Ausbacken.", "Mit Beeren servieren."], {"kcal": 290, "carbs": 19, "protein": 27, "fat": 11}, ["high-protein"]),
            ("Zucchini-Nudeln mit Pesto", "Hauptgericht", 16, 7, "Low Carb", 280, 12, "https://images.unsplash.com/photo-1473093295043-cdd812d0e601?auto=format&fit=crop&w=1200&q=80", "Leicht und grün.", ["Zucchini", "Basilikum", "Parmesan", "Knoblauch", "Olivenöl"], ["Zucchini spiralisieren.", "Pesto mixen.", "Kurz schwenken.", "Servieren."], {"kcal": 280, "carbs": 12, "protein": 12, "fat": 20}, ["vegetarisch", "low-carb"]),
            ("Chia-Pudding mit Beeren", "Frühstück", 10, 5, "Frühstück", 250, 10, "https://images.unsplash.com/photo-1490645935967-10de6ba17061?auto=format&fit=crop&w=1200&q=80", "Overnight und praktisch.", ["Chiasamen", "Milch", "Honig", "Beeren", "Vanille"], ["Alles verrühren.", "Kalt stellen.", "Mit Beeren toppen."], {"kcal": 250, "carbs": 21, "protein": 10, "fat": 13}, ["vegetarisch"]),
        ]
        existing_names = {row[0] for row in db.execute("SELECT name FROM recipes").fetchall()}
        for r in recipes:
            if r[0] in existing_names:
                continue
            db.execute(
                """INSERT INTO recipes (name,category,duration,ingredients_count,cuisine,calories,protein,image,description,ingredients_json,steps_json,nutrition_json,diet_tags)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], json.dumps(r[9]), json.dumps(r[10]), json.dumps(r[11]), json.dumps(r[12])),
            )
        image_updates = {
            "🍝": "https://images.unsplash.com/photo-1621996346565-e3dbc646d9a9?auto=format&fit=crop&w=1200&q=80",
            "🍕": "https://images.unsplash.com/photo-1604382355076-af4b0eb60143?auto=format&fit=crop&w=1200&q=80",
            "🍳": "https://images.unsplash.com/photo-1510693206972-df098062cb71?auto=format&fit=crop&w=1200&q=80",
            "🥦": "https://images.unsplash.com/photo-1512621776951-a57141f2eefd?auto=format&fit=crop&w=1200&q=80",
            "🍟": "https://images.unsplash.com/photo-1633321702518-7feccafb94d5?auto=format&fit=crop&w=1200&q=80",
        }
        for old_image, new_image in image_updates.items():
            db.execute("UPDATE recipes SET image=? WHERE image=?", (new_image, old_image))

        db.execute("INSERT OR IGNORE INTO settings (id,username,profile_image,diet,manage_subscription_note) VALUES (1,'Johannes','👤','Ich esse alles','Noch keine Abos verfügbar.')")
        if db.execute("SELECT COUNT(*) FROM shopping_lists").fetchone()[0] == 0:
            db.execute("INSERT INTO shopping_lists (name,color,updated_at) VALUES (?,?,?)", ("Liste vom 22.01.", "#7ed6df", datetime.utcnow().isoformat()))
            lid = db.execute("SELECT id FROM shopping_lists ORDER BY id DESC LIMIT 1").fetchone()[0]
            for i, n in enumerate(["300g Spaghettinudeln", "200g Tomatensauce", "2 Zwiebeln", "4 Knoblauchzehen", "300g Hackfleisch"]):
                db.execute("INSERT INTO shopping_items (list_id,name,checked) VALUES (?,?,?)", (lid, n, i % 2))


def row_to_recipe(row):
    d = dict(row)
    d["ingredients"] = json.loads(d.pop("ingredients_json"))
    d["steps"] = json.loads(d.pop("steps_json"))
    d["nutrition"] = json.loads(d.pop("nutrition_json"))
    d["diet_tags"] = json.loads(d["diet_tags"])
    return d


class Handler(BaseHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def body(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.end_headers()

    def do_GET(self):
        url = urlparse(self.path)
        p = url.path
        q = parse_qs(url.query)

        if p == "/api/recipes":
            with conn() as db:
                rows = [row_to_recipe(r) for r in db.execute("SELECT * FROM recipes WHERE name LIKE ?", (f"%{q.get('search',[''])[0]}%",)).fetchall()]
                diet = db.execute("SELECT diet FROM settings WHERE id=1").fetchone()["diet"]
                excludes = [r["name"].lower() for r in db.execute("SELECT name FROM excluded_ingredients WHERE active=1").fetchall()]
                disliked = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes").fetchall()}
                favs = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM favorites").fetchall()}

                def ok(r):
                    if r["id"] in disliked:
                        return False
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

        if p.startswith("/api/recipes/"):
            rid = int(p.split("/")[3])
            with conn() as db:
                row = db.execute("SELECT * FROM recipes WHERE id=?", (rid,)).fetchone()
            self.send_json(row_to_recipe(row) if row else {"error": "Nicht gefunden"}, 200 if row else 404)
            return

        if p == "/api/favorites":
            with conn() as db:
                rows = [row_to_recipe(r) for r in db.execute("SELECT r.* FROM recipes r JOIN favorites f ON f.recipe_id=r.id").fetchall()]
            self.send_json(rows)
            return

        if p == "/api/lists":
            with conn() as db:
                rows = []
                for row in db.execute("SELECT * FROM shopping_lists ORDER BY updated_at DESC").fetchall():
                    data = dict(row)
                    items = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (data["id"],)).fetchall()]
                    data["items"] = items
                    rows.append(data)
            self.send_json(rows)
            return

        if p.startswith("/api/lists/"):
            lid = int(p.split("/")[3])
            with conn() as db:
                lst = db.execute("SELECT * FROM shopping_lists WHERE id=?", (lid,)).fetchone()
                if not lst:
                    self.send_json({"error": "Nicht gefunden"}, 404)
                    return
                items = [dict(i) for i in db.execute("SELECT * FROM shopping_items WHERE list_id=?", (lid,)).fetchall()]
            data = dict(lst); data["items"] = items
            self.send_json(data); return

        if p == "/api/settings":
            with conn() as db:
                s = dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())
                s["excluded"] = [dict(r) for r in db.execute("SELECT * FROM excluded_ingredients").fetchall()]
            self.send_json(s); return

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
            if p.endswith("/like") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3]); db.execute("INSERT OR IGNORE INTO favorites (recipe_id) VALUES (?)", (rid,)); db.execute("DELETE FROM dislikes WHERE recipe_id=?", (rid,)); self.send_json({"ok": True}); return
            if p.endswith("/dislike") and p.startswith("/api/recipes/"):
                rid = int(p.split("/")[3]); db.execute("INSERT OR IGNORE INTO dislikes (recipe_id) VALUES (?)", (rid,)); db.execute("DELETE FROM favorites WHERE recipe_id=?", (rid,)); self.send_json({"ok": True}); return
            if p == "/api/lists":
                db.execute("INSERT INTO shopping_lists (name,color,updated_at) VALUES (?,?,?)", (b.get("name"), b.get("color", "#7ed6df"), datetime.utcnow().isoformat()))
                lid = db.execute("SELECT id FROM shopping_lists ORDER BY id DESC LIMIT 1").fetchone()[0]
                self.send_json(dict(db.execute("SELECT * FROM shopping_lists WHERE id=?", (lid,)).fetchone())); return
            if p == "/api/excluded":
                db.execute("INSERT OR IGNORE INTO excluded_ingredients (name,active) VALUES (?,1)", (b.get("name"),)); self.send_json({"ok": True}); return
            if p == "/api/feedback":
                db.execute("INSERT INTO feedback_messages (email,subject,message) VALUES (?,?,?)", (b.get("email"), b.get("subject"), b.get("message"))); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_PATCH(self):
        p = urlparse(self.path).path
        b = self.body()
        with conn() as db:
            if p == "/api/settings":
                cur = dict(db.execute("SELECT * FROM settings WHERE id=1").fetchone())
                db.execute("UPDATE settings SET username=?,diet=?,profile_image=? WHERE id=1", (b.get("username", cur["username"]), b.get("diet", cur["diet"]), b.get("profile_image", cur["profile_image"])))
                self.send_json({"ok": True}); return
            if p.startswith("/api/excluded/"):
                eid = int(p.split("/")[3]); db.execute("UPDATE excluded_ingredients SET active=? WHERE id=?", (1 if b.get("active") else 0, eid)); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_PUT(self):
        p = urlparse(self.path).path
        b = self.body()
        if p.startswith("/api/lists/"):
            lid = int(p.split("/")[3])
            with conn() as db:
                db.execute("UPDATE shopping_lists SET name=?, updated_at=? WHERE id=?", (b.get("name"), datetime.utcnow().isoformat(), lid))
                db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,))
                for it in b.get("items", []):
                    db.execute("INSERT INTO shopping_items (list_id,name,checked,image) VALUES (?,?,?,?)", (lid, it.get("name"), 1 if it.get("checked") else 0, it.get("image", "🧾")))
            self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        with conn() as db:
            if p.startswith("/api/favorites/"):
                rid = int(p.split("/")[3]); db.execute("DELETE FROM favorites WHERE recipe_id=?", (rid,)); db.execute("DELETE FROM dislikes WHERE recipe_id=?", (rid,)); self.send_json({"ok": True}); return
            if p.startswith("/api/lists/"):
                lid = int(p.split("/")[3]); db.execute("DELETE FROM shopping_items WHERE list_id=?", (lid,)); db.execute("DELETE FROM shopping_lists WHERE id=?", (lid,)); self.send_json({"ok": True}); return
        self.send_json({"error": "Unbekannt"}, 404)


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", 3000), Handler)
    print("App läuft auf http://localhost:3000")
    server.serve_forever()
