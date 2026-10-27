#!/usr/bin/env python3
"""Lapas pārbaude: atrod kļūdas data.json un publicētajā lapā.

Palaišana:  python3 check.py [data.json] [--live] [--json]
  --live  salīdzina arī ar publicēto https://asvsmiltis.com/data.json
  --json  izvada rezultātu JSON formā (aģentam)
Izejas kods: 0 = viss kārtībā (var būt brīdinājumi), 1 = ir kļūdas.
"""
import datetime
import json
import os
import re
import sys
import urllib.request

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover
    TZ = datetime.timezone(datetime.timedelta(hours=3))

SITE = "https://asvsmiltis.com/data.json"
EXPECTED = {
    "anna-rita": "Anna Rīta",
    "kitija-adamsone": "Kitija Martini Ādamsone",
    "deniela-konstantinova": "Deniela Konstantinova",
    "marta-vildere": "Marta Vildere",
    "bonija-runce": "Bonija Runce",
    "evelina-krieva": "Evelīna Krieva",
    "liva-ebere": "Līva Ēbere",
    "loreta-cabule": "Loreta Cabule",
    "monika-mamaja": "Monika Mamaja",
    "karlina-kazaka": "Karlīna Kazaka",
}
WRONG_SPELLINGS = ["Vīldere", "Cābule", "Mārtiņa", "Adamsone,", "Ki Martini", "Evelina Krieva", "Karlina Kazaka", "Liva Ebere"]
INDOOR_WORDS = re.compile(r"\b(indoor|zāles volejbol|zālē)\b", re.I)
SET_RE = re.compile(r"^\d{1,2}-\d{1,2}$")
PLACE_RE = re.compile(r"^\d{1,3}\. vieta$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    live = "--live" in sys.argv
    as_json = "--json" in sys.argv
    path = args[0] if args else "data.json"
    base = os.path.dirname(os.path.abspath(path))
    errors, warnings = [], []
    E = errors.append
    W = warnings.append

    try:
        raw = open(path, encoding="utf-8").read()
        d = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        E(f"data.json nav derīgs JSON: {e}")
        return finish(errors, warnings, as_json)

    now = datetime.datetime.now(TZ)
    today = now.date()
    meta = d.get("meta", {})
    season = meta.get("seasonStart", "2026-08-01")

    # --- svaigums ---
    try:
        upd = datetime.datetime.fromisoformat(meta["updatedAt"])
        age_h = (now - upd).total_seconds() / 3600
        if age_h > 26:
            E(f"Dati nav atjaunināti {age_h:.0f} stundas (meta.updatedAt={meta['updatedAt']})")
    except Exception:  # noqa: BLE001
        E("meta.updatedAt trūkst vai nav derīgs")
    today_logs = [l for l in meta.get("log", []) if str(l.get("at", "")).startswith(today.isoformat())]
    if not any("VolleyballLife" in l.get("text", "") for l in today_logs):
        W("Šodien žurnālā nav VolleyballLife skripta ieraksta (GitHub Actions varēja nenostrādāt)")
    if now.hour * 60 + now.minute >= 6 * 60 + 5 and not any(
            str(l.get("text", "")).startswith("Rīta atjauninājums") for l in today_logs):
        W("Šodien žurnālā nav ieraksta \"Rīta atjauninājums…\" – Claude rīta uzdevums nav publicējis (nav push uz main)")
    elif now.hour * 60 + now.minute >= 6 * 60 + 5 and not any(
            str(l.get("text", "")).startswith("Rīta atjauninājums")
            and not str(l.get("text", "")).startswith("Rīta atjauninājums: sākums") for l in today_logs):
        W("Rīta uzdevums šodien nopušoja tikai sākuma ierakstu (\"Rīta atjauninājums: sākums\"), bet ne gala atjauninājumu – tas apstājās pusceļā (skolu lapas/WebFetch)")
    for l in today_logs:
        t = l.get("text", "")
        if str(t).startswith("Pārbaude:"):
            continue  # pārbaudes aģenta paša kopsavilkums, ne avota kļūda
        if re.search(r"DNS|nebija pieejam|nav pieejam|403|429|kļūd", t, re.I):
            W(f"Šodienas žurnālā minēta kļūda: {t[:200]}")

    # --- spēlētājas ---
    players = d.get("players", [])
    ids = [p.get("id") for p in players]
    if set(ids) != set(EXPECTED):
        E(f"Spēlētāju saraksts neatbilst: trūkst {sorted(set(EXPECTED) - set(ids))}, lieki {sorted(set(ids) - set(EXPECTED))}")
    if len(ids) != len(set(ids)):
        E("Spēlētāju id atkārtojas")
    for p in players:
        pid = p.get("id")
        if pid in EXPECTED and p.get("name") != EXPECTED[pid]:
            E(f"Nepareizs vārds {pid}: '{p.get('name')}' (jābūt '{EXPECTED[pid]}')")
        for k in ("team", "school", "class"):
            if not p.get(k):
                E(f"{pid}: trūkst lauka '{k}'")
        ph = p.get("photo")
        if ph and not os.path.exists(os.path.join(base, ph)):
            E(f"{pid}: foto fails nav atrasts ({ph})")
        if "indoor" in (p.get("sports") or []):
            E(f"{pid}: sports satur 'indoor' (lapa ir tikai par pludmales volejbolu)")

    # --- rezultāti ---
    seen_ids, seen_keys = set(), {}
    for r in d.get("results", []):
        rid = r.get("id", "?")
        for k in ("id", "player", "date", "sport", "event", "score", "source"):
            if not r.get(k):
                E(f"Rezultātam {rid} trūkst '{k}'")
        if rid in seen_ids:
            E(f"Rezultāta id atkārtojas: {rid}")
        seen_ids.add(rid)
        if r.get("player") not in EXPECTED:
            E(f"Rezultāts {rid}: nezināma spēlētāja '{r.get('player')}'")
        if r.get("sport") != "beach":
            E(f"Rezultāts {rid}: sport='{r.get('sport')}' (atļauts tikai 'beach')")
        txt = " ".join(str(r.get(k, "")) for k in ("event", "round", "stats"))
        if INDOOR_WORDS.search(txt):
            E(f"Rezultāts {rid} izskatās pēc zāles volejbola: {txt[:120]}")
        for w in WRONG_SPELLINGS:
            if w in json.dumps(r, ensure_ascii=False):
                E(f"Rezultātā {rid} nepareiza rakstība: '{w}'")
        dt = r.get("date", "")
        if not DATE_RE.match(dt):
            E(f"Rezultāts {rid}: nederīgs datums '{dt}'")
        else:
            if dt > (today + datetime.timedelta(days=1)).isoformat():
                E(f"Rezultāts {rid}: datums nākotnē ({dt})")
            if dt < season:
                W(f"Rezultāts {rid}: datums pirms sezonas sākuma ({dt})")
        sc, res = (r.get("score") or "").strip(), r.get("result", "")
        if res not in ("W", "L", ""):
            E(f"Rezultāts {rid}: nederīgs result '{res}'")
        if PLACE_RE.match(sc):
            if res:
                E(f"Rezultāts {rid}: gala vietai nedrīkst būt W/L")
            if r.get("opponent"):
                W(f"Rezultāts {rid}: gala vietai ir pretinieks '{r.get('opponent')}'")
        else:
            sets = [s.strip() for s in sc.split(",") if s.strip()]
            if not sets or not all(SET_RE.match(s) for s in sets):
                E(f"Rezultāts {rid}: nesaprotams rezultāts '{sc}'")
            else:
                won = sum(1 for s in sets if int(s.split("-")[0]) > int(s.split("-")[1]))
                lost = sum(1 for s in sets if int(s.split("-")[0]) < int(s.split("-")[1]))
                calc = "W" if won > lost else ("L" if lost > won else "")
                if res and calc and res != calc:
                    E(f"Rezultāts {rid}: result='{res}', bet seti '{sc}' rāda '{calc}'")
                if not r.get("opponent"):
                    E(f"Rezultāts {rid}: mačam nav pretinieka")
        tmv = r.get("time", "")
        if tmv and not re.match(r"^\d{2}:\d{2}$", tmv):
            E(f"Rezultāts {rid}: nederīgs laiks '{tmv}' (jābūt HH:MM)")
        if "-vbl-m" in rid and not tmv and r.get("date", "") >= "2026-10-26":
            W(f"Rezultātam {rid} nav mača laika (time) – secība dienas ietvaros var būt nepareiza")
        key = (r.get("player"), r.get("date"), (r.get("opponent") or "").lower(), sc, r.get("round") if PLACE_RE.match(sc) else "")
        if key in seen_keys:
            E(f"Dublikāts: {rid} un {seen_keys[key]} (viens un tas pats mačs)")
        seen_keys[key] = rid
        if r.get("source") and not str(r["source"]).startswith("http"):
            E(f"Rezultāts {rid}: avots nav saite")

    # --- nākamās spēles ---
    yesterday = (today - datetime.timedelta(days=1)).isoformat()
    useen = set()
    for u in d.get("upcoming", []):
        uid = u.get("id", "?")
        if uid in useen:
            E(f"Nākamās spēles id atkārtojas: {uid}")
        useen.add(uid)
        for k in ("id", "players", "date", "event", "sport"):
            if not u.get(k):
                E(f"Nākamajai spēlei {uid} trūkst '{k}'")
        if u.get("sport") != "beach":
            E(f"Nākamā spēle {uid}: sport='{u.get('sport')}'")
        if len(u.get("players", [])) != 1:
            E(f"Nākamā spēle {uid}: jābūt tieši vienai spēlētājai (katrai meitenei savs ieraksts ar savas skolas saiti), ir {len(u.get('players', []))}")
        for pid in u.get("players", []):
            if pid not in EXPECTED:
                E(f"Nākamā spēle {uid}: nezināma spēlētāja '{pid}'")
        if u.get("date") and not DATE_RE.match(u["date"]):
            E(f"Nākamā spēle {uid}: nederīgs datums")
        if u.get("endDate") and u.get("date") and u["endDate"] < u["date"]:
            E(f"Nākamā spēle {uid}: beigu datums pirms sākuma")
        if (u.get("endDate") or u.get("date") or "9999") < yesterday:
            E(f"Nākamā spēle {uid} jau ir pagātnē ({u.get('date')}) — jāizņem vai jāpārvērš rezultātā")
        if not u.get("source"):
            W(f"Nākamajai spēlei {uid} nav avota saites")

    # --- spēlētājas bez neviena tuvākā turnīra (30 dienas) ---
    # 2026-10-22: USC rudens turnīri (Surf City, BVNE) bija skolas kalendārā, bet ne data.json.
    horizon = (today + datetime.timedelta(days=30)).isoformat()
    covered = set()
    for u in d.get("upcoming", []):
        if (u.get("date") or "9999") <= horizon:
            covered.update(u.get("players", []))
    missing = [EXPECTED[p] for p in EXPECTED if p not in covered and p != "anna-rita"]
    if missing:
        W("Nav neviena tuvākā turnīra 30 dienās: " + ", ".join(missing) + " — pārbaudi skolu kalendārus")

    # --- gala vieta turnīram, kas vēl notiek (VolleyballLife pagaidu vieta) ---
    running = {u.get("source") for u in d.get("upcoming", []) if (u.get("endDate") or u.get("date") or "") >= today.isoformat() and u.get("source")}
    for r in d.get("results", []):
        if PLACE_RE.match((r.get("score") or "").strip()) and r.get("source") in running:
            E(f"Rezultāts {r.get('id')}: gala vieta '{r.get('score')}' turnīram, kas vēl notiek (tā ir tikai pagaidu vieta) — jāizņem")

    # --- publicētā lapa ---
    if live:
        try:
            req = urllib.request.Request(SITE + "?t=" + str(int(now.timestamp())), headers={"User-Agent": "Mozilla/5.0 asvsmiltis-check"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                pub = json.load(resp)
            if pub.get("meta", {}).get("updatedAt") != meta.get("updatedAt"):
                W(f"Publicētā lapa vēl rāda {pub.get('meta', {}).get('updatedAt')}, repozitorijā {meta.get('updatedAt')} (GitHub Pages var kavēties dažas minūtes)")
            if len(pub.get("results", [])) != len(d.get("results", [])):
                W(f"Publicētajā lapā {len(pub.get('results', []))} rezultāti, repozitorijā {len(d.get('results', []))}")
        except Exception as e:  # noqa: BLE001
            W(f"Neizdevās nolasīt publicēto lapu {SITE}: {e}")

    return finish(errors, warnings, as_json, d)


def finish(errors, warnings, as_json, d=None):
    if as_json:
        print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=1))
    else:
        print("KĻŪDAS:" if errors else "Kļūdu nav.")
        for e in errors:
            print("  ✗", e)
        if warnings:
            print("Brīdinājumi:")
            for w in warnings:
                print("  !", w)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
