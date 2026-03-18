import hashlib
import hmac
import json
import os
import secrets
import smtplib
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from email.message import EmailMessage

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "public"
DB_PATH = ROOT / "app.db"

GUEST_DATA = {}
GOOGLE_CLIENT_ID = os.getenv(
    "GOOGLE_CLIENT_ID",
    "1014015739173-sj85p3bdscndu859jtveok8kjrgfqr2q.apps.googleusercontent.com",
).strip()


def parse_google_client_ids():
    raw_ids = os.getenv("GOOGLE_CLIENT_IDS", "")
    configured = [cid.strip() for cid in raw_ids.split(",") if cid.strip()]
    if GOOGLE_CLIENT_ID and GOOGLE_CLIENT_ID not in configured:
        configured.append(GOOGLE_CLIENT_ID)
    return configured


GOOGLE_ALLOWED_CLIENT_IDS = parse_google_client_ids()
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3000"))
CORS_ALLOW_ORIGIN = os.getenv("CORS_ALLOW_ORIGIN", "*")



FEEDBACK_RECIPIENT = os.getenv("FEEDBACK_RECIPIENT", "bitematch.de@gmail.com").strip()
FEEDBACK_SMTP_HOST = os.getenv("FEEDBACK_SMTP_HOST", "smtp.gmail.com").strip()
FEEDBACK_SMTP_PORT = int(os.getenv("FEEDBACK_SMTP_PORT", "465"))
FEEDBACK_SMTP_USER = os.getenv("FEEDBACK_SMTP_USER", FEEDBACK_RECIPIENT).strip()
FEEDBACK_SMTP_PASSWORD = os.getenv("FEEDBACK_SMTP_PASSWORD", os.getenv("GMAIL_APP_PASSWORD", "")).replace(" ", "").strip()
FEEDBACK_SMTP_SECURITY = os.getenv("FEEDBACK_SMTP_SECURITY", "auto").strip().lower()


def send_feedback_email(sender_email, subject, message):
    if not FEEDBACK_SMTP_USER:
        raise RuntimeError("FEEDBACK_SMTP_USER ist nicht konfiguriert")
    if not FEEDBACK_SMTP_PASSWORD:
        raise RuntimeError("FEEDBACK_SMTP_PASSWORD oder GMAIL_APP_PASSWORD ist nicht konfiguriert")

    reply_to = sender_email or FEEDBACK_RECIPIENT
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = FEEDBACK_SMTP_USER
    msg["To"] = FEEDBACK_RECIPIENT
    msg["Reply-To"] = reply_to
    msg.set_content(
        f"Feedback von: {sender_email} (für Rückfragen)\n\n"
        f"Betreff: {subject}\n\n"
        f"Nachricht:\n{message}"
    )

    security_mode = FEEDBACK_SMTP_SECURITY
    if security_mode == "auto":
        security_mode = "ssl" if FEEDBACK_SMTP_PORT == 465 else "starttls"

    if security_mode == "ssl":
        with smtplib.SMTP_SSL(FEEDBACK_SMTP_HOST, FEEDBACK_SMTP_PORT, timeout=15) as smtp:
            smtp.login(FEEDBACK_SMTP_USER, FEEDBACK_SMTP_PASSWORD)
            smtp.send_message(msg)
        return

    if security_mode == "starttls":
        with smtplib.SMTP(FEEDBACK_SMTP_HOST, FEEDBACK_SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(FEEDBACK_SMTP_USER, FEEDBACK_SMTP_PASSWORD)
            smtp.send_message(msg)
        return

    raise RuntimeError("FEEDBACK_SMTP_SECURITY muss auto, ssl oder starttls sein")


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


RECIPE_CATALOG = [('Griechische Riesenbohnen aus dem Ofen',
  'Hauptgericht',
  45,
  11,
  'Mediterran',
  158,
  6,
  'https://parea.pm/wp-content/uploads/2022/07/gigantes-griechische-riesenbohnen-aus-dem-ofen-rezept-4.jpg',
  'Butterbohnen in würziger Tomatensauce aus dem Ofen.',
  ['1 EL Olivenöl',
   '2 Dosen Butterbohnen (je 400 g), abgespült und abgetropft',
   '1 Bund Frühlingszwiebeln, in Ringe geschnitten',
   '400 g gehackte Tomaten (Dose)',
   '1 TL Honig',
   '½ TL Chiliflocken',
   'je ½ TL gemahlener Zimt und getrockneter Oregano',
   'Salz',
   'Pfeffer',
   '100 g frischer Babyspinat',
   'Saft ½ Zitrone'],
  ['Backofen auf 200°C vorheizen.',
   'Frühlingszwiebeln in Olivenöl weich dünsten.',
   'Bohnen, Tomaten und Gewürze einrühren und 30 Minuten backen.',
   'Spinat unterheben und mit Zitronensaft abschmecken.'],
  {'kcal': 158, 'carbs': 17, 'protein': 6, 'fat': 6},
  ['vegetarisch']),
 ('Rauchig-süßes Wurzelgemüse',
  'Beilage',
  30,
  7,
  'Modern',
  78,
  1,
  'https://www.senf.de/media/87/7a/f9/1712222223/Wurzelgemse%20aus%20dem%20Ofen_(1).jpg?ts=1753701236',
  'Geröstete Karotten und Pastinaken mit Zitronennote.',
  ['15 g Butter', '2 EL Zucker', '300 g Babykarotten', '300 g Babypastinaken, längs halbiert', '½ TL geräuchertes Meersalz', 'Saft ½ Zitrone', '1 EL gehackte Petersilie'],
  ['Ofen auf 220°C oder Grill vorheizen.', 'Butter und Zucker in der Pfanne schmelzen.', 'Gemüse kurz köcheln und auf Blech verteilen.', '10–15 Minuten rösten, mit Zitrone und Petersilie servieren.'],
  {'kcal': 78, 'carbs': 11, 'protein': 1, 'fat': 2},
  ['vegetarisch']),
 ('Shakshuka – Eier in Tomaten-Paprika-Sauce',
  'Frühstück',
  30,
  10,
  'Orientalisch',
  300,
  18,
  'https://images.lecker.de/shakshuka-gebackene-eier-in-paprika-tomaten-sugo,id=64923cbb,b=lecker,w=1600,rm=sk.jpeg',
  'Würzige Tomatensauce mit pochierten Eiern.',
  ['2 EL Olivenöl',
   '1 Zwiebel',
   '1 grüne Paprika, gewürfelt',
   '3 Knoblauchzehen, fein gehackt',
   'je 1 TL gemahlener Koriander, Paprika und Kreuzkümmel',
   '¼ TL Chiliflocken',
   'Salz',
   'Pfeffer',
   '800 g gehackte Tomaten (Dose)',
   '4 EL Tomatensoße oder Passata',
   '6–8 Eier',
   'frische Petersilie und Minze zum Garnieren'],
  ['Zwiebel und Paprika weich anschwitzen.', 'Knoblauch und Gewürze kurz rösten.', 'Tomaten zugeben und Sauce einkochen.', 'Eier in Mulden stocken lassen und mit Kräutern servieren.'],
  {'kcal': 300, 'carbs': 15, 'protein': 18, 'fat': 18},
  ['vegetarisch']),
 ('Afrikanischer Erdnuss-Hähnchen-Eintopf',
  'Hauptgericht',
  55,
  11,
  'Afrikanisch',
  441,
  38,
  'https://rezepte.genius.tv/wp-content/uploads/2020/12/Afrikanischer-Erdnuss-H%C3%A4hnchen-Topf_shutterstock_293822378.jpg',
  'Herzhafter Eintopf mit Hähnchen, Erdnussbutter und Spinat.',
  ['4 Hähnchenkeulen (je ca. 150 g)',
   '2 Knoblauchzehen',
   '1 EL geriebener Ingwer',
   'Salz',
   'weißer Pfeffer',
   '2 EL Olivenöl',
   '1 große Zwiebel, gewürfelt',
   '2 EL Tomatenmark',
   '700 ml Wasser',
   '2 Hühnerbrühwürfel',
   '200 g stückige Tomaten (Dose)',
   '125 g Erdnussbutter',
   '250 g Champignons, in Scheiben',
   '200 g frischer Spinat'],
  ['Hähnchen würzen und anbraten.', 'Zwiebeln und Tomatenmark anschwitzen.', 'Brühe, Tomaten und Erdnussbutter einrühren und köcheln.', 'Champignons und Spinat zugeben und fertig garen.'],
  {'kcal': 441, 'carbs': 13, 'protein': 38, 'fat': 27},
  ['omnivor', 'high-protein']),
 ('Okonomiyaki – Japanischer Kohl-Pfannkuchen',
  'Hauptgericht',
  35,
  9,
  'Japanisch',
  134,
  8,
  'https://www.krautundrueben.de/sites/krautundrueben.de/files/styles/original/public/2024-01/Okonomiyaki-AdobeStock.jpg?itok=wEMwcIiz',
  'Kohlpfannkuchen mit herzhaften Toppings.',
  ['2 Tassen (ca. 250 g) fein geschnittener Weißkohl',
   '1 Karotte, gerieben',
   '1 kleine Zwiebel, dünn geschnitten',
   '½ TL Salz',
   '4 Eier',
   '1 EL Sojasoße',
   '1 EL Sesamöl',
   '½ Tasse (60 g) Mehl',
   'Öl zum Braten',
   'Mayonnaise',
   'Frühlingszwiebeln',
   'Nori-Streifen'],
  ['Gemüse salzen und Wasser ziehen lassen.', 'Eier, Sojasauce, Sesamöl und Mehl verrühren.', 'Gemüse unterheben und Teig portionsweise braten.', 'Mit Mayo, Nori und Frühlingszwiebeln servieren.'],
  {'kcal': 134, 'carbs': 12, 'protein': 8, 'fat': 6},
  ['vegetarisch']),
 ('Mujadara – Linsen-Reis mit Zwiebeln',
  'Hauptgericht',
  45,
  6,
  'Libanesisch',
  530,
  20,
  'https://www.eat-this.org/wp-content/uploads/2024/02/mujadarra-die-leckersten-arabischen-linsen-mit-reis-2-edited-2.jpg',
  'Linsen und Reis mit knusprigen Zwiebeln.',
  ['200 g braune oder grüne Linsen', '180 g Basmatireis', '3 mittelgroße Zwiebeln (2 gewürfelt, 1 in Ringe)', '2 EL Olivenöl', '1 TL Salz', '750 ml Wasser'],
  ['Linsen einweichen und Reis waschen.', 'Zwiebelringe langsam karamellisieren.', 'Gewürfelte Zwiebeln mit Linsen und Reis kochen.', 'Ruhen lassen und mit knusprigen Zwiebeln toppen.'],
  {'kcal': 530, 'carbs': 80, 'protein': 20, 'fat': 15},
  ['vegan']),
 ('Veganes Chili sin Carne',
  'Hauptgericht',
  40,
  13,
  'Mexikanisch',
  367,
  15,
  'https://byanjushka.com/wp-content/uploads/2022/02/veganes_chili_sin_carne_3-500x500.jpg',
  'Bohnen-Linsen-Chili mit Avocado.',
  ['1 Zwiebel',
   '1 grüne Paprika',
   '2 Knoblauchzehen, fein gehackt',
   '1 EL Olivenöl',
   '1 TL getrockneter Chili',
   '50 g getrocknete Tomaten, in Stücke geschnitten',
   '250 ml Gemüsebrühe',
   '250 ml Wasser',
   '250 g gekochte Linsen (braun)',
   '400 g Kidneybohnen, abgespült',
   '300 g Mais (Dose)',
   '400 g gehackte Tomaten (Dose)',
   '2 EL Tomatenmark',
   '2 TL Kreuzkümmel',
   '1 TL Paprikapulver',
   '1 TL Oregano',
   '2 TL Ahornsirup',
   '1 Avocado zum Garnieren'],
  ['Zwiebel, Paprika und Knoblauch anschwitzen.', 'Gewürze und getrocknete Tomaten mitrösten.', 'Bohnen, Linsen, Mais und Tomaten köcheln.', 'Mit Ahornsirup abschmecken und mit Avocado servieren.'],
  {'kcal': 367, 'carbs': 54, 'protein': 15, 'fat': 13},
  ['vegan']),
 ('Vegane Lo-Mein-Nudeln',
  'Hauptgericht',
  30,
  12,
  'Asiatisch',
  466,
  19,
  'https://img.chefkoch-cdn.de/rezepte/3129231466181773/bilder/1381184/crop-640x427/vegane-lo-mein-nudelpfanne.jpg',
  'Gemüse-Nudeln mit würziger Sojasauce.',
  ['250 g Spaghetti',
   '2 EL Olivenöl',
   '2 Knoblauchzehen, fein gehackt',
   '150 g Champignons, in Scheiben',
   '1 rote Paprika, in Streifen',
   '1 Karotte, in dünne Stifte',
   '50 ml Weißwein',
   '100 g Tiefkühl-Erbsen',
   '100 g frischer Spinat',
   '2 EL Sojasoße',
   '2 EL Hefeflocken',
   '1 EL Ahornsirup',
   '1 TL Ingwer (Pulver)',
   '1 TL Sriracha (optional)'],
  ['Nudeln al dente kochen.', 'Gemüse in Öl anbraten und mit Wein ablöschen.', 'Erbsen und Spinat unterheben.', 'Sauce einrühren und mit Nudeln vermengen.'],
  {'kcal': 466, 'carbs': 72, 'protein': 19, 'fat': 10},
  ['vegan']),
 ('Veganes Kokos-Kichererbsen-Curry',
  'Hauptgericht',
  35,
  10,
  'Indisch',
  465,
  13,
  'https://www.justspices.de/media/recipe/food_inminutes_kokoskichererbsencurry-2_2_.jpg',
  'Cremiges Curry mit Kichererbsen und Basilikum.',
  ['200 g Basmatireis',
   '400 ml Kokosmilch',
   '2 Zwiebeln, gewürfelt',
   '2 EL Olivenöl',
   '2 Knoblauchzehen, gehackt',
   'Saft 1 Limette',
   '2 EL rote Currypaste',
   '2 Dosen Kichererbsen (je 400 g), abgetropft',
   '1 EL Sojasoße',
   '2 gehackte Tomaten',
   'eine Handvoll frisches Basilikum',
   '1 TL Ahornsirup',
   'optional 200 g Zuckerschoten'],
  ['Reis kochen.', 'Zwiebeln, Knoblauch und Currypaste anschwitzen.', 'Kokosmilch und Kichererbsen köcheln.', 'Tomaten und Basilikum zugeben und mit Limette abschmecken.'],
  {'kcal': 465, 'carbs': 65, 'protein': 13, 'fat': 17},
  ['vegan']),
 ('Veganes Chili sin Carne mit Kichererbsen',
  'Hauptgericht',
  40,
  12,
  'Mexikanisch',
  437,
  20,
  'https://image.brigitte.de/12729588/t/wt/v3/w1440/r1.5/-/veganes-chili.jpg',
  'Gemüsereiches Chili mit Bohnen und Kichererbsen.',
  ['2 Knoblauchzehen',
   '1 Zwiebel, fein gehackt',
   '250 ml Gemüsebrühe',
   '1 rote Paprika',
   '1 Karotte',
   '1 Zucchini, gewürfelt',
   '800 g gehackte Tomaten (Dose)',
   '2 EL Tomatenmark',
   '150 g Mais (Dose)',
   '400 g Kidneybohnen',
   '400 g Kichererbsen, abgespült',
   '2 EL Sojasoße',
   '2 TL Paprika',
   '1 TL Kreuzkümmel',
   '½ TL Chilipulver'],
  ['Zwiebel und Knoblauch anrösten.', 'Gemüse mit Brühe weich köcheln.', 'Tomaten, Bohnen und Gewürze ergänzen.', '20 Minuten köcheln und heiß servieren.'],
  {'kcal': 437, 'carbs': 73, 'protein': 20, 'fat': 11},
  ['vegan']),
 ('Veganes Thai-Kartoffel-Curry',
  'Hauptgericht',
  45,
  13,
  'Thai',
  480,
  15,
  'https://www.einfachkochen.de/sites/einfachkochen.de/files/styles/full_width_tablet_4_3/public/2023-08/2023_kartoffelcurry_aufmacher.jpg?h=4521fff0&itok=od3dUXwJ',
  'Kartoffel-Kokos-Curry mit Kichererbsen und Brokkoli.',
  ['2 Zwiebeln',
   '3 Knoblauchzehen, fein gehackt',
   '250 ml Gemüsebrühe',
   '3 große Kartoffeln, gewürfelt',
   '1 Dose Kichererbsen (400 g), abgetropft',
   '200 g Erbsen (frisch oder TK)',
   '1 rote Paprika',
   '1 Brokkoli, in mundgerechte Stücke',
   'eine Handvoll Spinat',
   '400 ml Kokosmilch',
   '2 EL rote Currypaste',
   '1 TL frisch geriebener Ingwer',
   '½ TL Kurkuma',
   '¼ TL Zimt',
   '¼ TL Chiliflocken',
   '1 EL Limettensaft',
   'frische Petersilie',
   'vegane Joghurtalternative zum Servieren'],
  ['Zwiebeln und Knoblauch in Brühe anschwitzen.', 'Kartoffeln und Gewürze kurz rösten.', 'Kokosmilch, Kichererbsen und Gemüse köcheln.', 'Spinat unterheben und mit Limette abschmecken.'],
  {'kcal': 480, 'carbs': 70, 'protein': 15, 'fat': 19},
  ['vegan']),
 ('Jamaikanischer Quinoa-Reis mit Bohnen',
  'Hauptgericht',
  30,
  8,
  'Jamaikanisch',
  226,
  8,
  'https://www.gutekueche.at/storage/media/recipe/161126/jamaikanischer-bohnenreis.jpg',
  'Quinoa mit Kokosmilch, Bohnen und Ingwer.',
  ['200 g Quinoa',
   '400 ml Kokosmilch',
   '200 ml Wasser',
   '1 Zwiebel',
   '2 Knoblauchzehen',
   '1 TL frisch geriebener Ingwer',
   '400 g Kidneybohnen (Dose), abgespült',
   'Salz',
   '1 Scotch-Bonnet-Chili oder andere Chili nach Geschmack'],
  ['Quinoa gründlich spülen.', 'Kokosmilch mit Wasser aufkochen.', 'Aromaten und Bohnen einrühren.', 'Quinoa 20 Minuten garen und abschmecken.'],
  {'kcal': 226, 'carbs': 28, 'protein': 8, 'fat': 10},
  ['vegan']),
 ('Mediterraner Fisch in Tomatensoße',
  'Hauptgericht',
  30,
  9,
  'Mediterran',
  212,
  36,
  'https://v.cdn.ww.com/media/system/wine/57f30641567432a7136e77c9/8e29fa33-c28d-4725-b80d-f8eef0e5a956/ire5ys0dcoafqzctvepl.jpg',
  'Zarter Weißfisch in würziger Paprika-Tomatensauce.',
  ['4 weiße Fischfilets (je ca. 150 g)',
   '120 ml heißes Wasser',
   '2 EL Tomatenmark',
   '1 TL Paprikapulver',
   '1 TL Honig oder Zucker',
   'eine Prise Cayennepfeffer',
   '½ TL Chiliflocken',
   '100 g geröstete rote Paprika aus dem Glas, gehackt',
   '3 Knoblauchzehen, in dünne Scheiben',
   'frischer Koriander oder Petersilie'],
  ['Tomatenmark mit Gewürzen und Wasser anrühren.', 'Paprika und Knoblauch in Pfanne verteilen.', 'Fisch darauflegen und Sauce angießen.', '12–15 Minuten sanft köcheln lassen.'],
  {'kcal': 212, 'carbs': 10, 'protein': 36, 'fat': 3},
  ['pescetarisch', 'high-protein']),
 ('Lachs mit Granatapfel-Glasur',
  'Hauptgericht',
  25,
  8,
  'Modern',
  339,
  34,
  'https://hauptsache-lecker.de/wp-content/uploads/2024/12/slow-cooker-lachs-weihnachten.jpg',
  'Knuspriger Lachs mit süß-herber Glasur.',
  ['4 Lachsfilets (je ca. 160 g)',
   '2 EL brauner Zucker',
   '1 TL Salz',
   '2 TL Speisestärke',
   '½ TL schwarzer Pfeffer',
   '50 ml Granatapfelmelasse',
   '1 EL Olivenöl',
   'optional Granatapfelkerne und gehackte frische Minze'],
  ['Backofen auf 200°C vorheizen.', 'Lachs würzen und in Pfanne anbraten.', 'Kurz im Ofen fertig garen.', 'Mit Granatapfelmelasse glasieren und servieren.'],
  {'kcal': 339, 'carbs': 16, 'protein': 34, 'fat': 14},
  ['pescetarisch', 'high-protein']),
 ('Gebackener Weißfisch mit Basilikum-Tapenade',
  'Hauptgericht',
  30,
  8,
  'Mediterran',
  842,
  161,
  'https://cdn.gutekueche.de/media/recipe/43894/conv/seeteufel-mit-tapenade-und-tomaten-default.jpg',
  'Fischfilet mit Oliven-Basilikum-Tapenade überbacken.',
  ['100 g grüne entsteinte Oliven',
   '30 g frische Basilikumblätter',
   '2 EL Olivenöl',
   '1 EL Kapern',
   '1 Knoblauchzehe',
   'fein abgeriebene Schale 1 Zitrone',
   '4 weiße Fischfilets (je 200 g)',
   'frisch gemahlener schwarzer Pfeffer',
   'Zitronenspalten zum Servieren'],
  ['Tapenade im Mixer fein pürieren.', 'Fischfilets würzen und auf Blech legen.', 'Tapenade aufstreichen.', '12–15 Minuten bei 180°C backen.'],
  {'kcal': 842, 'carbs': 1, 'protein': 161, 'fat': 17},
  ['pescetarisch', 'high-protein']),
 ('Sardinen-Pasta mit Zitrone und Kapern',
  'Hauptgericht',
  25,
  9,
  'Italienisch',
  404,
  7,
  'https://sardinele.de/cdn/shop/articles/Portugalisku_sardiniu_makaronai_su_citrina_kapareliais_ir_cili_pipirais_aff144ef-df78-46f5-a3a5-9e7886c99b72.jpg?v=1752845843&width=1200',
  'Pasta mit Sardinen, Kapern und Zitronenaroma.',
  ['400 g Spaghetti oder Engelshaar-Pasta',
   '3 EL Olivenöl',
   '2 Schalotten, fein gewürfelt',
   '1 TL Zitronenschale',
   '2 EL Zitronensaft',
   '½ TL Chiliflocken',
   '2 Dosen Sardinen in Öl (je 120 g), grob zerteilt',
   '2 EL Kapern, abgespült',
   'eine Handvoll frische Petersilie oder Basilikum, grob gehackt'],
  ['Pasta al dente kochen.', 'Schalotten mit Zitrone und Chili anschwitzen.', 'Sardinen und Kapern unterheben.', 'Mit Pasta, Kräutern und etwas Kochwasser vermengen.'],
  {'kcal': 404, 'carbs': 44, 'protein': 7, 'fat': 22},
  ['pescetarisch']),
 ('Koshari – Linsen-Reis-Nudel-Mix',
  'Hauptgericht',
  60,
  10,
  'Ägyptisch',
  550,
  18,
  'https://www.leckerschmecker.me/wp-content/uploads/sites/6/2025/08/aegyptisches-koshari-ls.jpg?w=1200',
  'Ägyptischer Mix aus Linsen, Reis, Nudeln und Tomatensauce.',
  ['4 große Zwiebeln, in Ringe geschnitten',
   '2 EL Mehl',
   'Öl zum Frittieren',
   '500 ml Tomatensauce',
   '300 g braune Linsen',
   '200 g Reis',
   '1 TL Kreuzkümmel',
   '½ TL Koriander',
   '200 g kleine Makkaroni',
   '1 Dose Kichererbsen (400 g), abgetropft'],
  ['Zwiebelringe mehlieren und knusprig frittieren.', 'Tomatensauce würzig einkochen.', 'Linsen und Reis garen, Nudeln separat kochen.', 'Alles schichten und mit Röstzwiebeln toppen.'],
  {'kcal': 550, 'carbs': 90, 'protein': 18, 'fat': 12},
  ['vegan']),
 ('Fruchtiges Quinoa-Porridge',
  'Frühstück',
  25,
  10,
  'Modern',
  418,
  19,
  'https://hurrythefoodup.com/wp-content/uploads/2022/10/noatmeal-recipe-finished-500x375.jpg',
  'Warmes Quinoa-Porridge mit Nektarine und Himbeeren.',
  ['80 g Quinoa',
   'je 10 g Chia-, Lein- und Hanfsamen',
   '1 EL Zucker',
   '½ TL Vanilleextrakt',
   '½ TL Zimt',
   '250 ml Sojamilch',
   '125 ml Wasser',
   '1 Nektarine, in Scheiben',
   '50 g Himbeeren',
   '1 EL Ahornsirup'],
  ['Quinoa gründlich waschen.', 'Mit Samen, Gewürzen, Milch und Wasser aufkochen.', '15–20 Minuten cremig köcheln lassen.', 'Mit Obst und Ahornsirup servieren.'],
  {'kcal': 418, 'carbs': 51, 'protein': 19, 'fat': 16},
  ['vegan']),
 ('Knusprig gebackener Schellfisch',
  'Hauptgericht',
  25,
  8,
  'Klassisch',
  390,
  36,
  'https://ruteundrolle.de/wp-content/uploads/2017/11/gebackener-Schellfisch.jpeg',
  'Ofenfisch mit Panko-Parmesan-Kruste.',
  ['4 Schellfischfilets (je ca. 180 g)',
   '50 g Panko-Semmelbrösel',
   '30 g geriebener Parmesan',
   '1 TL italienische Kräuter (getrocknet)',
   '30 g geschmolzene Butter',
   'Saft 1 Zitrone',
   'Salz',
   'Pfeffer'],
  ['Ofen auf 220°C vorheizen.', 'Brösel mit Parmesan und Butter mischen.', 'Auf gewürzte Filets verteilen.', '12–15 Minuten goldbraun backen.'],
  {'kcal': 390, 'carbs': 18, 'protein': 36, 'fat': 20},
  ['pescetarisch', 'high-protein']),
 ('Lachs mit Bagel-Gewürz',
  'Hauptgericht',
  20,
  3,
  'Modern',
  550,
  51,
  'https://www.zauberdergewuerze.de/magazin/wp-content/uploads/2025/01/istock-1430353060.jpg',
  'Einfacher Lachs mit knuspriger Gewürzkruste.',
  ['700 g Lachsfilet', '3 EL Everything-Bagel-Gewürzmischung', '1 EL Olivenöl'],
  ['Lachs trocken tupfen und würzen.', 'Pfanne mit Öl erhitzen.', '4–5 Minuten auf der Hautseite braten.', 'Wenden, fertig garen und servieren.'],
  {'kcal': 550, 'carbs': 1, 'protein': 51, 'fat': 37},
  ['pescetarisch', 'high-protein']),
 ('Schwarzer Tilapia',
  'Hauptgericht',
  20,
  5,
  'Amerikanisch',
  400,
  46,
  'https://www.nourish-and-fete.com/wp-content/uploads/2022/09/blackened-tilapia-5.jpg',
  'Kräftig gewürzter Tilapia aus der Pfanne.',
  ['4 Tilapiafilets (je ca. 150 g)', '2 EL Schwarz-Gewürzmischung', '2 EL Pflanzenöl', 'optional Avocado-Tomaten-Topping'],
  ['Filets würzen und rundum bedecken.', 'Öl in der Pfanne erhitzen.', 'Fisch beidseitig 3–4 Minuten braten.', 'Optional mit Avocado-Tomaten-Topping servieren.'],
  {'kcal': 400, 'carbs': 7, 'protein': 46, 'fat': 22},
  ['pescetarisch', 'high-protein']),
 ('Barramundi mit Mango-Slaw',
  'Hauptgericht',
  25,
  8,
  'Tropisch',
  540,
  8,
  'https://thishealthytable.com/wp-content/uploads/2023/01/barramundi-recipe-720x720.jpg',
  'Gebratener Fisch mit frischem Mango-Krautsalat.',
  ['600 g Barramundi-Filets', '2 EL Butter', 'Salz', 'Pfeffer', '400 g Krautsalatmix (Weißkraut, Rotkohl, Karotten)', '1 reife Mango, gewürfelt', '2 EL griechischer Joghurt', 'Saft 1 Limette'],
  ['Slaw aus Kraut, Mango, Joghurt und Limette mischen.', 'Fischfilets würzen.', 'In Butter je Seite 4–5 Minuten braten.', 'Mit Slaw anrichten.'],
  {'kcal': 540, 'carbs': 42, 'protein': 8, 'fat': 38},
  ['pescetarisch']),
 ('Gebratene Auberginen und Garnelen mit Harissa',
  'Hauptgericht',
  35,
  9,
  'Nordafrikanisch',
  441,
  43,
  'https://www.zauberdergewuerze.de/magazin/wp-content/uploads/2019/05/harissa-garnelen.jpg',
  'Röst-Aubergine mit scharfen Garnelen und Minze.',
  ['2 Auberginen (ca. 600 g), gewürfelt',
   '3 EL Olivenöl',
   '2 EL Harissa-Paste',
   '1 TL gemahlener Kreuzkümmel',
   'Salz',
   '400 g große Garnelen, geschält und entdarmt',
   '1 TL Kreuzkümmelsamen',
   'geriebene Schale 1 Zitrone',
   '1 EL Zitronensaft',
   'einige Zweige frische Minze'],
  ['Auberginen mit Harissa würzen und im Ofen rösten.', 'Garnelen mit Kreuzkümmel kurz braten.', 'Auberginen und Zitrone in die Pfanne geben.', 'Mit Minze bestreuen und servieren.'],
  {'kcal': 441, 'carbs': 39, 'protein': 43, 'fat': 14},
  ['pescetarisch', 'high-protein']),
 ('Tilapia mit Kokoskruste',
  'Hauptgericht',
  30,
  8,
  'Tropisch',
  351,
  46,
  'https://www.wisdomlib.org/uploads/recipes/coconut-tilapia-with-apricot-d-13896.jpg',
  'Ofen-Tilapia in würziger Kokospanade.',
  ['4 Tilapiafilets', '200 ml Kokosmilch', '100 g Kokosraspel', '½ TL Salz', 'je ½ TL Kreuzkümmel, Paprika und Knoblauchpulver', '¼ TL Ingwerpulver', '¼ TL Kurkuma', 'Prise Cayennepfeffer'],
  ['Fisch in Kokosmilch wenden.', 'Kokosraspel mit Gewürzen mischen.', 'Filets panieren und aufs Blech legen.', '15–20 Minuten goldbraun backen.'],
  {'kcal': 351, 'carbs': 13, 'protein': 46, 'fat': 14},
  ['pescetarisch', 'high-protein']),
 ('Kabeljau mit Kräuter-Zitrus-Kruste',
  'Hauptgericht',
  25,
  8,
  'Mediterran',
  177,
  31,
  'https://www.wajos.de/cdn/shop/articles/Wajos_kabeljau-zitronensenf_kopie_4482aa77-569a-4ad4-bd76-790f8f7ad417_600x.jpg?v=1641551537',
  'Aromatischer Kabeljau mit Zitruskruste.',
  ['4 Kabeljaufilets (je 170 g)',
   'fein abgeriebene Schale von 1 Zitrone und 1 Orange',
   'je ½ TL getrockneter Oregano, Thymian und Dill',
   '½ TL Knoblauchpulver',
   '½ TL Zwiebelpulver',
   '¼ TL geräuchertes Paprikapulver',
   '¼ TL gemahlener Koriander',
   'schwarzer Pfeffer',
   '2 EL Olivenöl'],
  ['Ofen auf 190°C vorheizen.', 'Zitrusabrieb mit Kräutern mischen.', 'Filets ölen und würzen.', '12–15 Minuten backen.'],
  {'kcal': 177, 'carbs': 1, 'protein': 31, 'fat': 5},
  ['pescetarisch', 'high-protein']),
 ('Honig-Knoblauch-Garnelen',
  'Hauptgericht',
  20,
  9,
  'Asiatisch',
  231,
  25,
  'https://www.pfeffersackundsoehne.de/cdn/shop/articles/honig-knoblauch-garnelen_teller-gericht-zentriert_3zu2-web_pfeffersack-soehne_e7160645-48fb-4e31-9fd1-13f9fadbb549.png?v=1750155020&width=1024',
  'Schnelle Garnelen in süß-salziger Sauce.',
  ['450 g große Garnelen, geschält und entdarmt',
   '3 EL Sojasoße',
   '2 EL Honig',
   '1 EL Reisessig',
   '3 Knoblauchzehen, fein gehackt',
   '1 TL frisch geriebener Ingwer',
   '1 TL Sesamöl',
   '2 Frühlingszwiebeln, in Ringe geschnitten',
   '1 EL Sesamsamen'],
  ['Garnelen kurz anbraten und herausnehmen.', 'Knoblauch und Ingwer rösten.', 'Sauce einrühren und leicht eindicken.', 'Garnelen zurückgeben und glasieren.'],
  {'kcal': 231, 'carbs': 17, 'protein': 25, 'fat': 7},
  ['pescetarisch']),
 ('Lachs gefüllt mit Spinat und Feta',
  'Hauptgericht',
  35,
  8,
  'Mediterran',
  300,
  39,
  'https://www.eatclub.de/wp-content/uploads/2023/05/lachs-mit-spinat-fullung.jpg',
  'Gefüllte Lachsfilets aus Ofen und Pfanne.',
  ['4 Lachsfilets (je ca. 180 g)', '1 Zwiebel', '2 Knoblauchzehen, fein gehackt', '200 g frischer Spinat', '100 g Feta, zerbröckelt', '2 EL Olivenöl', 'Salz', 'Pfeffer'],
  ['Lachsfilets einschneiden.', 'Spinatfüllung mit Zwiebel, Knoblauch und Feta herstellen.', 'Filets füllen und kurz anbraten.', 'Im Ofen 10–12 Minuten fertig garen.'],
  {'kcal': 300, 'carbs': 6, 'protein': 39, 'fat': 14},
  ['pescetarisch', 'high-protein']),
 ('Huhn mit grünen Bohnen – asiatische Pfanne',
  'Hauptgericht',
  35,
  12,
  'Asiatisch',
  453,
  38,
  'https://img.chefkoch-cdn.de/rezepte/3769081574061217/bilder/1394513/crop-640x800/asiatische-haehnchen-bohnen-pfanne.jpg',
  'Wokgericht mit mariniertem Hähnchen und Bohnen.',
  ['600 g Hähnchenschenkel ohne Knochen, in dünne Streifen geschnitten',
   '2 EL Sojasoße',
   '1 EL Shaoxing-Wein',
   '1 TL Speisestärke',
   '300 g grüne Bohnen, halbiert',
   '3 Knoblauchzehen, fein gehackt',
   '1 Stück Ingwer (2 cm), in Stifte geschnitten',
   '2 Frühlingszwiebeln, in Ringe geschnitten',
   '2 EL Sojasoße',
   '1 EL Austernsauce',
   '1 TL Hoisin',
   '1 EL Reisessig',
   '1 TL Honig',
   '1 TL Sesamöl',
   '1 TL Speisestärke',
   '100 ml Hühnerbrühe'],
  ['Hähnchen marinieren.', 'Bohnen im Wok vorbraten.', 'Hähnchen scharf anbraten und Aromaten zugeben.', 'Sauce einrühren und kurz eindicken lassen.'],
  {'kcal': 453, 'carbs': 20, 'protein': 38, 'fat': 25},
  ['omnivor', 'high-protein']),
 ('Koreanisches Rindfleisch aus dem Slow Cooker',
  'Hauptgericht',
  500,
  9,
  'Koreanisch',
  516,
  46,
  'https://www.slowcookerclub.com/wp-content/uploads/2021/06/slow-cooker-korean-beef-12-3.jpg',
  'Zartes Rind in süß-würziger Sojasauce.',
  ['900 g Rinderbraten',
   '120 ml Sojasoße',
   '60 g brauner Zucker',
   '2 EL Reisessig',
   '1 EL Sesamöl',
   '½ TL Chiliflocken',
   '1 TL Knoblauchpulver',
   '½ TL Ingwerpulver',
   '2 Frühlingszwiebeln, in Ringe',
   '1 EL Sesamsamen'],
  ['Sauce aus Sojasauce, Zucker und Gewürzen mischen.', 'Fleisch in Slow Cooker legen.', '6–8 Stunden auf Low schmoren.', 'Zerpflücken und mit Sesam servieren.'],
  {'kcal': 516, 'carbs': 14, 'protein': 46, 'fat': 31},
  ['omnivor', 'high-protein']),
 ('Zitronen-Knoblauch-Butter-Kabeljau',
  'Hauptgericht',
  25,
  9,
  'Mediterran',
  254,
  31,
  'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcRsotb0CIEdwGJjQW5RlwfTO_Jk79TCuMKqTg&s',
  'Saftiger Kabeljau in Zitronen-Butter aus dem Ofen.',
  ['4 Kabeljaufilets',
   '3 EL Butter',
   '1 EL Olivenöl',
   '3 Knoblauchzehen, gehackt',
   '1 TL Zitronenschale',
   'Saft ½ Zitrone',
   '½ TL Paprika',
   '¼ TL Chiliflocken',
   'Salz',
   'Pfeffer',
   '2 EL frisch gehackte Petersilie'],
  ['Ofen auf 200°C vorheizen.', 'Kabeljau würzen und in Form legen.', 'Butter mit Knoblauch und Gewürzen schmelzen.', '12–15 Minuten backen und mit Petersilie servieren.'],
  {'kcal': 254, 'carbs': 2, 'protein': 31, 'fat': 13},
  ['pescetarisch', 'high-protein']),
 ('Gebratenes Schweinehackfleisch mit Pak Choi',
  'Hauptgericht',
  20,
  8,
  'Chinesisch',
  285,
  18,
  'https://marleyspoon.com/media/recipes/180672/main_photos/large/chinesische_nudeln_mit_schweinehack-f74d84e124cebecc1fdd48665880bb27.jpeg',
  'Herzhafte Pfanne mit Schweinehack und Pak Choi.',
  ['300 g Schweinehackfleisch',
   '2 EL Shaoxing-Wein',
   '2 EL helle Sojasoße',
   '1 EL dunkle Sojasoße',
   '1 kleiner Pak Choi (ca. 300 g)',
   '3 Knoblauchzehen, fein gehackt',
   '1 EL Chiliöl (optional)',
   '1 TL Zucker'],
  ['Pak Choi vorbereiten.', 'Hackfleisch anbraten.', 'Sauce und Gewürze einrühren.', 'Stiele und Blätter kurz mitgaren.'],
  {'kcal': 285, 'carbs': 8, 'protein': 18, 'fat': 20},
  ['omnivor']),
 ('Green-Goddess-Bowl',
  'Hauptgericht',
  30,
  10,
  'Modern',
  450,
  13,
  'https://assets.epicurious.com/photos/58efc4b2bf5d820f40d36f21/1:1/w_1307,h_1307,c_limit/04122017-buddhabowls-recipe.jpg',
  'Grüne Bowl mit Bohnen, Spargel und Kräuterdressing.',
  ['200 g Sorghum oder alternativ Reis, gekocht',
   '200 g grüner Spargel, geputzt',
   '100 g Rucola',
   '200 g gekochte weiße Bohnen',
   '1 Avocado, in Würfel',
   '½ Gurke, in Scheiben',
   '2 EL Kürbiskerne',
   '1 Bund Petersilie',
   '1 Bund Basilikum',
   '60 ml Olivenöl',
   '2 EL Zitronensaft',
   '1 Knoblauchzehe',
   'Salz'],
  ['Sorghum oder Reis kochen.', 'Spargel blanchieren und abschrecken.', 'Dressing aus Kräutern und Zitrone mixen.', 'Alles in Bowls anrichten und beträufeln.'],
  {'kcal': 450, 'carbs': 50, 'protein': 13, 'fat': 22},
  ['vegan']),
 ('Tofu-Paprikasch',
  'Hauptgericht',
  35,
  10,
  'Osteuropäisch',
  420,
  17,
  'https://assets.ichkoche.at/image/11/108893.jpg?v=1&twic=v1/focus=50px50p/cover=730x566',
  'Würzig-cremiges Paprikasch mit knusprigem Tofu.',
  ['400 g fester Tofu, in Würfeln',
   '2 EL Olivenöl',
   '1 Zwiebel',
   '2 Knoblauchzehen, fein gehackt',
   '200 g Champignons, geviertelt',
   '1 rote Paprika, gewürfelt',
   '1 Tomate, gehackt',
   '2 EL Paprikapulver',
   '1 Prise Cayennepfeffer',
   '400 ml Kokosmilch',
   '1 EL Apfelessig'],
  ['Tofu ausdrücken und anbraten.', 'Gemüse glasig dünsten.', 'Paprika und Tomate mitrösten.', 'Mit Kokosmilch köcheln und Tofu zurückgeben.'],
  {'kcal': 420, 'carbs': 15, 'protein': 17, 'fat': 30},
  ['vegan']),
 ('Brokkoli-Rindfleisch-Pfanne',
  'Hauptgericht',
  30,
  9,
  'Asiatisch',
  394,
  32,
  'https://marleyspoon.com/media/recipes/65779/main_photos/large/schnelle_rindfleischpfanne-b5e0ef3a90e146132fb0d2099f9f2a73.jpeg',
  'Schnelle Pfanne mit mariniertem Rind und Brokkoli.',
  ['500 g Flanksteak oder anderes mageres Rindfleisch, in dünne Streifen geschnitten',
   '2 EL Sojasoße',
   '1 EL Sesamöl',
   '1 EL Reisessig',
   '1 TL Zucker',
   '1 EL Speisestärke',
   '3 Knoblauchzehen, fein gehackt',
   '300 g Brokkoliröschen',
   '100 ml Rinder- oder Gemüsebrühe',
   '2 EL Austernsauce'],
  ['Fleisch marinieren.', 'Fleisch scharf anbraten und herausnehmen.', 'Brokkoli anbraten und mit Brühe dünsten.', 'Fleisch und Sauce zugeben und kurz erhitzen.'],
  {'kcal': 394, 'carbs': 8, 'protein': 32, 'fat': 26},
  ['omnivor', 'high-protein']),
 ('Rindfleisch mit chinesischem Brokkoli',
  'Hauptgericht',
  30,
  8,
  'Chinesisch',
  363,
  25,
  'https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEi_QO2Cysf-myGEwiwH0f_MB6X_jEFy00IC5T-fLKaqp6cO-TH3-E7YfY0NMxqh1s-GFiW9QDrPRzv2olzViGVVY1XUlonGsvlBKtF_HRQWKmQb4xoeVOBlPgmNPFtF2sQFRD8AzvUX48ooJPYoeQf7DX7dUrwl-LbupRVbRTmjJLyuHJFhWMmHX0hEYnU/s800/20250108_193307.jpg',
  'Wokgericht mit Gai Lan und mariniertem Rind.',
  ['400 g Rindfleisch', '1 EL Sesamöl', '1 EL Speisestärke', '2 EL Sojasoße', '1 TL Zucker', '1 EL Reiswein', '300 g Gai Lan', '2 Knoblauchzehen, fein gehackt'],
  ['Fleisch marinieren.', 'Knoblauch und Fleisch kurz im Wok braten.', 'Gai Lan Stängel und Blätter separat garen.', 'Alles zusammenführen und heiß servieren.'],
  {'kcal': 363, 'carbs': 14, 'protein': 25, 'fat': 23},
  ['omnivor']),
 ('Lamm-Pfanne mit Paprika',
  'Hauptgericht',
  25,
  7,
  'Asiatisch',
  419,
  29,
  'https://www.kuechengoetter.de/uploads/media/630x630/08/58608-lamm-pepato-mit-paprika-und-kichererbsen.jpg?v=2-17',
  'Scharf angebratenes Lamm mit Paprika.',
  ['400 g Lammfleisch, dünn geschnitten',
   '1 EL Sojasoße',
   '1 EL dunkle Sojasoße',
   '1 EL Sesamöl',
   '1 TL Speisestärke',
   '1 TL frisch geriebener Ingwer',
   '2 Frühlingszwiebeln, in Stücke geschnitten',
   '2 grüne Paprika, in Streifen geschnitten'],
  ['Lamm marinieren.', 'Ingwer kurz anrösten.', 'Fleisch scharf anbraten und herausnehmen.', 'Paprika braten, Fleisch zurückgeben und mischen.'],
  {'kcal': 419, 'carbs': 5, 'protein': 29, 'fat': 31},
  ['omnivor']),
 ('Keto Egg Roll in a Bowl',
  'Hauptgericht',
  20,
  6,
  'Amerikanisch',
  439,
  35,
  'https://www.ketoconnect.net/wp-content/uploads/2020/12/plated-recipe-in-front-of-a-cutting-board-650x650.jpg',
  'Dekonstruierte Frühlingsrolle mit Ei und Hack.',
  ['400 g gehacktes Fleisch nach Wahl', '400 g fein geschnittener Weißkohl- oder Krautmix', '4 Eier', '2 EL Sojasoße oder Kokosaminos', '2 Frühlingszwiebeln, gehackt'],
  ['Hackfleisch anbraten.', 'Kohl hinzufügen und weich braten.', 'Eier in Mulde stocken lassen.', 'Alles mischen und mit Sojasauce abschmecken.'],
  {'kcal': 439, 'carbs': 8, 'protein': 35, 'fat': 29},
  ['omnivor', 'high-protein']),
 ('Three Cup Tintenfisch',
  'Hauptgericht',
  20,
  7,
  'Taiwanesisch',
  213,
  16,
  'https://www.creatable.de/wp-content/uploads/2024/12/Three-Cup_Squid_Dreierlei-Tintenfisch.jpg',
  'Tintenfisch mit Sesamöl, Soja und Thai-Basilikum.',
  ['500 g kleine Tintenfische, in Stücke geschnitten',
   '2 EL Sesamöl',
   '2 Scheiben frischer Ingwer',
   '1 rote Chili, in Scheiben',
   '2 EL Sojasoße',
   '2 EL Reiswein',
   '1 EL Zucker',
   'eine Handvoll frisches Thai-Basilikum',
   '1 TL schwarzes Sesamöl'],
  ['Tintenfisch reinigen und kurz blanchieren.', 'Ingwer und Chili in Sesamöl anbraten.', 'Tintenfisch und Sauce kurz schmoren.', 'Mit Basilikum und schwarzem Sesamöl vollenden.'],
  {'kcal': 213, 'carbs': 17, 'protein': 16, 'fat': 9},
  ['pescetarisch']),
 ('Meeresfrüchte-Pfanne mit Garnelen und Tintenfisch',
  'Hauptgericht',
  20,
  8,
  'Asiatisch',
  208,
  14,
  'https://image.brigitte.de/12792452/t/C1/v3/w960/r1/-/frutti-di-mare.jpg',
  'Schnelle Pfanne mit blanchierten Meeresfrüchten.',
  ['300 g große Garnelen',
   '300 g Tintenfischringe',
   '1 Zwiebel, fein gehackt',
   '3 Frühlingszwiebeln, in Ringe geschnitten',
   '1 Stück Ingwer, fein gehackt',
   '2 EL Öl',
   'Salz',
   'optional 1 EL Sojasoße'],
  ['Meeresfrüchte vorbereiten und kurz blanchieren.', 'Zwiebel und Ingwer anbraten.', 'Frühlingszwiebeln zugeben.', 'Meeresfrüchte kurz fertig braten.'],
  {'kcal': 208, 'carbs': 6, 'protein': 14, 'fat': 15},
  ['pescetarisch']),
 ('Tintenfisch mit Ingwer und Frühlingszwiebeln',
  'Hauptgericht',
  20,
  7,
  'Chinesisch',
  306,
  28,
  'https://i0.wp.com/magentratzerl.de/wp-content/uploads/2024/04/calamari-hongshao1.jpg?fit=1024%2C768&ssl=1',
  'Aromatische Pfanne mit zart gegartem Tintenfisch.',
  ['500 g Tintenfisch, in Stücke geschnitten',
   '2 EL neutrales Öl',
   '2 Knoblauchzehen, fein gehackt',
   '1 Stück Ingwer (2 cm), in dünne Streifen',
   '4 Frühlingszwiebeln, in 5 cm lange Stücke',
   'Salz',
   'weißer Pfeffer',
   'optional 1 TL Fischsoße'],
  ['Tintenfisch schneiden und vorbereiten.', 'Knoblauch und Ingwer kurz anbraten.', 'Tintenfisch 2–3 Minuten braten.', 'Frühlingszwiebeln und Würze zugeben.'],
  {'kcal': 306, 'carbs': 13, 'protein': 28, 'fat': 15},
  ['pescetarisch']),
 ('Ein-Topf-Lachs-Reis-Bowl',
  'Hauptgericht',
  35,
  8,
  'Asiatisch',
  602,
  30,
  'https://i0.wp.com/rommelsbacher.blog/wp-content/uploads/2023/08/Poke-Bowl-Titel-Rommelsbacher-3.jpg?fit=723%2C723&ssl=1',
  'Reiskochergericht mit Lachs und Sesamnoten.',
  ['300 g weißer Reis', '450 ml Wasser', '250 g Lachsfilet', '2 Knoblauchzehen, gehackt', '2 EL Sojasoße', '1 EL Sesamöl', '1 TL Zucker', '½ TL Salz', 'Frühlingszwiebeln', 'Sesamsamen'],
  ['Reis gründlich waschen.', 'Mit Gewürzen in den Reiskocher geben.', 'Lachsfilet obenauf legen und Programm starten.', 'Lachs zerpflücken und mit Sesam garnieren.'],
  {'kcal': 602, 'carbs': 83, 'protein': 30, 'fat': 14},
  ['pescetarisch']),
 ('Rote-Curry-Jakobsmuscheln mit Brokkoli',
  'Hauptgericht',
  25,
  10,
  'Thai',
  504,
  49,
  'https://images.eatsmarter.de/sites/default/files/styles/1600x1200/public/fruchtiges-curry-mit-jakobsmuscheln-33993.jpg',
  'Jakobsmuscheln in rotem Kokoscurry.',
  ['400 g Jakobsmuscheln',
   'Salz',
   '2 EL neutrales Öl',
   '2 EL rote Currypaste',
   '2 Knoblauchzehen, fein gehackt',
   '1 Stück Ingwer, fein gehackt',
   '400 ml Kokosmilch',
   '200 g Brokkoliröschen',
   '1 EL Fischsoße',
   '1 TL Zucker',
   'Saft 1 Limette'],
  ['Muscheln trocken tupfen und scharf anbraten.', 'Currypaste, Knoblauch und Ingwer rösten.', 'Kokosmilch und Brokkoli köcheln.', 'Muscheln zurückgeben und mit Limette abschmecken.'],
  {'kcal': 504, 'carbs': 17, 'protein': 49, 'fat': 29},
  ['pescetarisch', 'high-protein']),
 ('Lachs mit Spinat und Pilzen',
  'Hauptgericht',
  25,
  8,
  'Mediterran',
  327,
  28,
  'https://www.leckerschmecker.me/wp-content/uploads/sites/6/2024/10/lachs-mit-spinat-und-pilzen.jpeg?w=1200&h=900&crop=1',
  'Knuspriger Lachs auf Spinat-Pilz-Gemüse.',
  ['4 Lachsfilets', '2 EL Olivenöl', '2 Knoblauchzehen, fein gehackt', '200 g Champignons, in Scheiben', '200 g Spinat', '1 TL Paprika', '½ TL Knoblauchpulver', 'Salz', 'Pfeffer'],
  ['Lachs würzen und knusprig anbraten.', 'Knoblauch und Pilze in derselben Pfanne braten.', 'Spinat unterheben und würzen.', 'Lachs zurücklegen und kurz ziehen lassen.'],
  {'kcal': 327, 'carbs': 6, 'protein': 28, 'fat': 21},
  ['pescetarisch']),
 ('Lachs mit Frühlingszwiebeln, Knoblauch und Sojasoße',
  'Hauptgericht',
  20,
  7,
  'Asiatisch',
  385,
  27,
  'https://www.gutekueche.at/storage/media/recipe/157877/lachs-mit-sticky-sojasauce.jpg',
  'Gebratener Lachs mit aromatischer Soja-Sauce.',
  ['4 Lachsfilets', '2 Frühlingszwiebeln, fein geschnitten', '3 Knoblauchzehen, fein gehackt', '2 EL Sojasoße', '1 TL frisch geriebener Ingwer', '1 EL Reiswein'],
  ['Lachsfilets braten oder dämpfen.', 'Frühlingszwiebeln, Knoblauch und Ingwer anschwitzen.', 'Sojasauce und Reiswein aufkochen.', 'Sauce über den Lachs geben und servieren.'],
  {'kcal': 385, 'carbs': 3, 'protein': 27, 'fat': 28},
  ['pescetarisch']),
 ('Lachs-Bratreis',
  'Hauptgericht',
  25,
  8,
  'Asiatisch',
  347,
  17,
  'https://images.lecker.de/glasierter-lachs-auf-ruck-zuck-bratreis,id=ff0139c2,b=lecker,w=1600,ca=17.40,5.32,84.40,72.07,rm=sk.jpeg',
  'Gebratener Reis mit Lachs, Ei und Gemüse.',
  ['200 g gegarter Lachs, in Stücke zerteilt',
   '200 g gefrorenes Mischgemüse',
   '400 g gekochter Reis vom Vortag',
   '2 Eier',
   '2 Knoblauchzehen, fein gehackt',
   '2 EL Sojasoße',
   '1 TL Sesamöl',
   'Frühlingszwiebeln zum Garnieren'],
  ['Lachs anbraten und beiseite stellen.', 'Gemüse und Knoblauch anbraten.', 'Eier in Mulde stocken lassen.', 'Reis, Lachs und Würze einrühren.'],
  {'kcal': 347, 'carbs': 30, 'protein': 17, 'fat': 17},
  ['pescetarisch']),
 ('Lachs-Pfannengericht mit Gemüse',
  'Hauptgericht',
  25,
  9,
  'Asiatisch',
  482,
  32,
  'https://eat.de/wp-content/uploads/2025/01/mediterrane-lachspfanne-mit-gemuese-4385.jpg',
  'Marinierter Lachs mit Paprika und Champignons.',
  ['500 g Lachsfilet, in Würfel geschnitten',
   '2 EL Sojasoße',
   '1 EL Honig',
   '2 Knoblauchzehen, zerdrückt',
   '1 TL Speisestärke',
   '1 Zwiebel',
   '2 Paprika',
   '200 g Champignons, jeweils grob geschnitten'],
  ['Lachs würfeln und marinieren.', 'Kurz anbraten und herausnehmen.', 'Gemüse braten und Marinade einrühren.', 'Lachs zurückgeben und fertig köcheln.'],
  {'kcal': 482, 'carbs': 36, 'protein': 32, 'fat': 25},
  ['pescetarisch', 'high-protein']),
 ('Marinierte Garnelen',
  'Basisrezept',
  15,
  5,
  'Asiatisch',
  143,
  26,
  'https://www.einfachkochen.de/sites/einfachkochen.de/files/styles/facebook/public/2022-06/2022_garnelen-marinade_aufmacher.jpg?h=4521fff0&itok=SF4dW44y',
  'Grundrezept für zarte, marinierte Garnelen.',
  ['450 g rohe Garnelen, geschält', '1 EL Speisestärke', '1 EL Reiswein (michiu)', 'Salz', 'optional 1 EL Sojasoße'],
  ['Garnelen abspülen und trocknen.', 'Marinade verrühren.', 'Garnelen 10 Minuten ziehen lassen.', 'Danach in Pfanne, Wok oder Grill weiterverarbeiten.'],
  {'kcal': 143, 'carbs': 4, 'protein': 26, 'fat': 2},
  ['pescetarisch']),
 ('Kokos-Reisschüssel mit gebratenem Gemüse (Tofu)',
  'Hauptgericht',
  35,
  10,
  'Asiatisch',
  500,
  20,
  'https://img.hellofresh.com/f_auto,fl_lossy,h_300,q_auto,w_450/hellofresh_s3/image/lutz-luftige-kokos-reis-wolke-c4a2130c.jpg',
  'Kokosreis mit Gemüse und gebratenem Tofu.',
  ['200 g Basmatireis',
   '400 ml Kokosmilch',
   '250 ml Wasser',
   '200 g Tofu oder alternativ Hähnchenbrust, in Würfel',
   '1 Kopf Brokkoli',
   '1 rote Paprika',
   '2 Karotten, in Stücke',
   '2 EL Sojasoße',
   'Saft 1 Limette',
   '1 TL gerösteter Sesam'],
  ['Reis mit Kokosmilch und Wasser garen.', 'Tofu würfeln und anbraten.', 'Gemüse bissfest braten.', 'Mit Sojasauce und Limette abschmecken und anrichten.'],
  {'kcal': 500, 'carbs': 70, 'protein': 20, 'fat': 18},
  ['vegan']),
 ('Indische Frankies – Gewürzte Wraps',
  'Hauptgericht',
  45,
  12,
  'Indisch',
  550,
  15,
  'https://www.creatable.de/wp-content/uploads/2024/12/Frankie_Roll_indisches_Wrap.jpg',
  'Vegane Wraps mit Kartoffel-Blumenkohl-Füllung und Chutney.',
  ['4 große Weizentortillas',
   '500 g Kartoffeln, gewürfelt',
   '1 kleiner Blumenkohl, in Röschen',
   '1 Dose Kichererbsen (400 g)',
   '2 EL Currypulver',
   '1 TL Kreuzkümmel',
   '1 TL Garam Masala',
   'Salz',
   '1 Bund Koriander',
   '1 Bund Minze',
   '1 Knoblauchzehe',
   'Saft 1 Limette',
   '1 rote Zwiebel, in Ringe',
   '2 EL Essig',
   '1 TL Zucker'],
  ['Gemüse vorbereiten und anbraten.', 'Gewürze rösten und mit Wasser garen.', 'Chutney mixen und Zwiebeln einlegen.', 'Tortillas füllen, rollen und servieren.'],
  {'kcal': 550, 'carbs': 75, 'protein': 15, 'fat': 15},
  ['vegan']),
 ('Shakshuka mit Spinat und Feta',
  'Frühstück',
  30,
  9,
  'Orientalisch',
  320,
  18,
  'https://www.merkur.de/assets/images/37/293/37293915-gruene-shakshuka-mit-spinat-und-feta-29fBQ7cwmUec.jpg',
  'Tomatige Shakshuka-Variante mit Spinat und Feta.',
  ['2 EL Olivenöl',
   '1 Zwiebel, fein gehackt',
   '2 Knoblauchzehen, gehackt',
   '200 g frischer Spinat',
   '1 TL Paprika',
   '½ TL Kreuzkümmel',
   '¼ TL Chiliflocken',
   '400 g passierte Tomaten',
   '4 Eier',
   '100 g Feta, zerbröckelt'],
  ['Zwiebel und Knoblauch anschwitzen.', 'Spinat und Gewürze einrühren.', 'Tomaten kurz einkochen.', 'Eier in Mulden garen und Feta darüberstreuen.'],
  {'kcal': 320, 'carbs': 10, 'protein': 18, 'fat': 22},
  ['vegetarisch'])]




def seed_recipes(db):
    names = [r[0] for r in RECIPE_CATALOG]
    marks = ",".join(["?"] * len(names))
    db.execute(f"DELETE FROM recipes WHERE name NOT IN ({marks})", tuple(names))
    for r in RECIPE_CATALOG:
        existing = db.execute("SELECT id FROM recipes WHERE name=?", (r[0],)).fetchone()
        payload = (r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], json.dumps(r[9]), json.dumps(r[10]), json.dumps(r[11]), json.dumps(r[12]), r[0])
        if existing:
            db.execute(
                """
                UPDATE recipes
                SET category=?, duration=?, ingredients_count=?, cuisine=?, calories=?, protein=?, image=?, description=?,
                    ingredients_json=?, steps_json=?, nutrition_json=?, diet_tags=?
                WHERE name=?
                """,
                payload,
            )
        else:
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


def verify_google_id_token(id_token):
    if not id_token:
        return None, {"code": "missing_id_token", "message": "Kein ID-Token vom Google-Plugin erhalten."}
    if not GOOGLE_ALLOWED_CLIENT_IDS:
        return None, {"code": "missing_client_id", "message": "Kein gültiger Google Client im Backend gesetzt (GOOGLE_CLIENT_ID/GOOGLE_CLIENT_IDS)."}

    try:
        with urlopen(f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}", timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body_text = ""
        try:
            body_text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body_text = ""
        parsed = {}
        if body_text:
            try:
                parsed = json.loads(body_text)
            except Exception:
                parsed = {}
        google_error = parsed.get("error")
        google_description = parsed.get("error_description")
        details = [
            f"HTTP {exc.code}",
            f"Google error={google_error}" if google_error else "",
            f"Beschreibung={google_description}" if google_description else "",
            f"Body={body_text[:280]}" if body_text and not parsed else "",
        ]
        return None, {
            "code": "tokeninfo_http_error",
            "message": "Google tokeninfo hat den Token abgelehnt: " + "; ".join([d for d in details if d]),
        }
    except URLError as exc:
        reason = getattr(exc, "reason", exc)
        return None, {
            "code": "tokeninfo_network_error",
            "message": f"Google tokeninfo Netzwerkfehler: {type(reason).__name__}: {reason}",
        }
    except Exception as exc:
        return None, {
            "code": "tokeninfo_request_failed",
            "message": f"Google tokeninfo Anfrage fehlgeschlagen: {type(exc).__name__}: {exc}",
        }

    audience = data.get("aud")
    authorized_party = data.get("azp")
    allowed = set(GOOGLE_ALLOWED_CLIENT_IDS)
    if audience not in allowed and authorized_party not in allowed:
        allowed_ids = ", ".join(GOOGLE_ALLOWED_CLIENT_IDS)
        return None, {
            "code": "audience_mismatch",
            "message": f"Falsche Audience/Authorized Party. Erlaubt: {allowed_ids}. Erhalten aud={audience or '-'}, azp={authorized_party or '-'}",
        }

    if data.get("email_verified") not in {"true", True}:
        return None, {
            "code": "email_not_verified",
            "message": "Google-Konto hat keine verifizierte E-Mail-Adresse.",
        }

    if not data.get("sub"):
        return None, {
            "code": "missing_sub",
            "message": "Google Token enthält kein 'sub'-Feld.",
        }

    return data, None


def matches_diet(recipe, diet):
    if diet == "Ich esse alles":
        return True

    tags = set(recipe["diet_tags"])
    if diet == "Vegan":
        return "vegan" in tags
    if diet == "Vegetarisch":
        return "vegan" in tags or "vegetarisch" in tags
    if diet == "Pescetarisch":
        return "vegan" in tags or "vegetarisch" in tags or "pescetarisch" in tags
    if diet == "High-Protein":
        return recipe["protein"] > 30
    return True


def row_to_recipe(r):
    return {
        "id": r["id"], "name": r["name"], "category": r["category"], "duration": r["duration"],
        "ingredients_count": r["ingredients_count"], "cuisine": r["cuisine"], "calories": r["calories"],
        "protein": r["protein"], "image": r["image"], "description": r["description"] or "",
        "ingredients": json.loads(r["ingredients_json"]), "steps": json.loads(r["steps_json"]),
        "nutrition": json.loads(r["nutrition_json"]), "diet_tags": json.loads(r["diet_tags"]),
    }


class Handler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", CORS_ALLOW_ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

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
            if p == "/api/public-config":
                self.send_json({"googleClientId": GOOGLE_CLIENT_ID})
                return

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
                    if not matches_diet(r, diet):
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
                    excludes = [e["name"].lower() for e in guest["settings"]["excluded"] if e.get("active")]
                    diet = guest["settings"].get("diet", "Ich esse alles")
                else:
                    uid = ident["user_id"]
                    disliked = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM dislikes WHERE user_id=?", (uid,)).fetchall()}
                    favs = {r["recipe_id"] for r in db.execute("SELECT recipe_id FROM favorites WHERE user_id=?", (uid,)).fetchall()}
                    s = db.execute("SELECT diet FROM user_settings WHERE user_id=?", (uid,)).fetchone()
                    diet = s["diet"] if s else "Ich esse alles"
                    excludes = [r["name"].lower() for r in db.execute("SELECT name FROM excluded_ingredients WHERE active=1 AND user_id=?", (uid,)).fetchall()]

                def ok(r):
                    if r["id"] in disliked or r["id"] in favs:
                        return False
                    if "category" in q and r["category"] != q["category"][0]:
                        return False
                    if "maxCalories" in q and r["calories"] >= int(q["maxCalories"][0]):
                        return False
                    if "minProtein" in q and r["protein"] <= int(q["minProtein"][0]):
                        return False
                    if "maxDuration" in q and r["duration"] >= int(q["maxDuration"][0]):
                        return False
                    if not matches_diet(r, diet):
                        return False
                    ing = " ".join(r["ingredients"]).lower()
                    return not any(e in ing for e in excludes)

                self.send_json([r for r in rows if ok(r)])
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

            if p == "/api/auth/google":
                id_token = b.get("credential") or b.get("id_token") or ""
                payload, token_error = verify_google_id_token(id_token)
                if not payload:
                    self.send_json({
                        "error": "Google Login fehlgeschlagen",
                        "details": token_error["message"],
                        "code": token_error["code"],
                    }, 401)
                    return
                sub = payload["sub"]
                email = (payload.get("email") or "").strip().lower()
                name = (payload.get("name") or "Nutzer").strip() or "Nutzer"
                picture = payload.get("picture") or "👤"

                user = db.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()
                if user:
                    user_id = user["id"]
                    db.execute(
                        "UPDATE users SET email=?, name=?, picture=?, username=COALESCE(username, ?), profile_image=COALESCE(profile_image, ?), updated_at=? WHERE id=?",
                        (email, name, picture, name, picture, datetime.utcnow().isoformat(), user_id),
                    )
                else:
                    db.execute(
                        "INSERT INTO users (google_sub,email,name,picture,username,profile_image,updated_at) VALUES (?,?,?,?,?,?,?)",
                        (sub, email, name, picture, name, picture, datetime.utcnow().isoformat()),
                    )
                    user_id = db.execute("SELECT id FROM users WHERE google_sub=?", (sub,)).fetchone()["id"]

                self.ensure_user_defaults(db, user_id, name, picture)
                token = secrets.token_urlsafe(32)
                db.execute("INSERT INTO sessions (token,user_id,is_guest) VALUES (?,?,0)", (token, user_id))
                self.send_json({"token": token, "mode": "user"})
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
                email = (b.get("email") or "").strip()
                subject = (b.get("subject") or "").strip()
                message = (b.get("message") or "").strip()

                if not email or "@" not in email:
                    self.send_json({"error": "Bitte gib eine gültige E-Mail-Adresse ein."}, 400)
                    return
                if not subject:
                    self.send_json({"error": "Bitte gib einen Betreff ein."}, 400)
                    return
                if len(subject) > 30:
                    self.send_json({"error": "Der Betreff darf maximal 30 Zeichen lang sein."}, 400)
                    return
                if not message:
                    self.send_json({"error": "Bitte gib eine Nachricht ein."}, 400)
                    return
                if len(message) > 250:
                    self.send_json({"error": "Die Nachricht darf maximal 250 Zeichen lang sein."}, 400)
                    return

                try:
                    send_feedback_email(email, subject, message)
                except Exception as exc:
                    self.send_json({"error": "Feedback konnte nicht per E-Mail versendet werden.", "details": str(exc)}, 500)
                    return

                if not ident["is_guest"]:
                    db.execute("INSERT INTO feedback_messages (email,subject,message,user_id) VALUES (?,?,?,?)", (email, subject, message, ident["user_id"]))
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
            if p == "/api/account":
                if ident["is_guest"]:
                    self.send_json({"error": "Gast-Accounts können nicht gelöscht werden"}, 400)
                    return

                uid = ident["user_id"]
                db.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
                db.execute("DELETE FROM favorites WHERE user_id=?", (uid,))
                db.execute("DELETE FROM dislikes WHERE user_id=?", (uid,))
                db.execute("DELETE FROM excluded_ingredients WHERE user_id=?", (uid,))
                db.execute("DELETE FROM feedback_messages WHERE user_id=?", (uid,))
                db.execute("DELETE FROM shopping_items WHERE list_id IN (SELECT id FROM shopping_lists WHERE user_id=?)", (uid,))
                db.execute("DELETE FROM shopping_lists WHERE user_id=?", (uid,))
                db.execute("DELETE FROM user_settings WHERE user_id=?", (uid,))
                db.execute("DELETE FROM users WHERE id=?", (uid,))

                self.send_json({"ok": True})
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

            if p.startswith("/api/excluded/"):
                eid = int(p.split("/")[3])
                if ident["is_guest"]:
                    g = ensure_guest(ident["token"])
                    g["settings"]["excluded"] = [e for e in g["settings"]["excluded"] if e["id"] != eid]
                else:
                    uid = ident["user_id"]
                    db.execute("DELETE FROM excluded_ingredients WHERE id=? AND user_id=?", (eid, uid))
                self.send_json({"ok": True})
                return
        self.send_json({"error": "Unbekannt"}, 404)


if __name__ == "__main__":
    init_db()
    server = HTTPServer((HOST, PORT), Handler)
    print(f"App läuft auf http://{HOST}:{PORT}")
    server.serve_forever()
