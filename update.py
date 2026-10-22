#!/usr/bin/env python3
"""Rīta atjauninājums no VolleyballLife (deterministisks, bez AI).

Lasa katras spēlētājas VolleyballLife profilu, pievieno:
  * nākamos turnīrus, kuros viņa ir pieteikta  -> data.json "upcoming"
  * katra pabeigtā turnīra mačus ar rezultātiem  -> data.json "results"
  * gala vietu turnīrā                           -> data.json "results"
Spēles tiek ņemtas tikai tad, ja pārim ir tieši viena partnere (citādi nav
skaidrs, kurā pārī viņa spēlēja). Esošie ieraksti netiek mainīti.

Palaišana:  python3 update.py [ceļš/uz/data.json]
"""
import datetime
import json
import re
import sys
import time
import urllib.request

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Riga")
except Exception:  # pragma: no cover
    TZ = datetime.timezone(datetime.timedelta(hours=3))

API = "https://api-v8.volleyballlife.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")

# spēlētājas id data.json -> VolleyballLife profila id
VBL = {
    "liva-ebere": 410021,
    "loreta-cabule": 403848,
    "monika-mamaja": 360060,
    "bonija-runce": 332711,
    "kitija-adamsone": 259411,
    "marta-vildere": 261353,
    "deniela-konstantinova": 258656,
    "anna-rita": 170656,
    "evelina-krieva": 333617,
    "karlina-kazaka": 410830,
}
# VolleyballLife vārds -> latviskā rakstība
LV_NAMES = {
    "evelina krieva": "Evelīna Krieva",
    "karlina kazaka": "Karlīna Kazaka",
    "liva ebere": "Līva Ēbere",
    "loreta cabule": "Loreta Cabule",
    "monika mamaja": "Monika Mamaja",
    "bonija runce": "Bonija Runce",
    "ki martini adamsone": "Kitija Martini Ādamsone",
    "marta vildere": "Marta Vildere",
    "deniela konstantinova": "Deniela Konstantinova",
    "anna rita": "Anna Rīta",
}
DAY_LV = {"pools": "grupu turnīrs"}


def get(path, tries=3):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{path}: {last}")


def lv_name(n):
    return LV_NAMES.get((n or "").strip().lower(), n)


def lv_team(n):
    m = re.match(r"^(.*?)\s+Pair\s+(\d+)\s*(.*)$", n or "")
    if m:
        rest = (" " + m.group(3)) if m.group(3) else ""
        return f"{m.group(1)} {m.group(2)}. pāris{rest}"
    return n or ""


def round_name(day_name):
    k = (day_name or "").strip()
    return DAY_LV.get(k.lower(), f"{k} izslēgšanas spēles" if k else "")


def walk_matches(o):
    if isinstance(o, dict):
        if "games" in o and "homeTeam" in o and "awayTeam" in o:
            yield o
        for v in o.values():
            yield from walk_matches(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk_matches(v)


def team_id(side):
    return side.get("teamId") if isinstance(side, dict) else None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    d = json.load(open(path, encoding="utf-8"))
    meta = d.setdefault("meta", {})
    season = meta.get("seasonStart", "2026-08-01")
    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()
    names = {p["id"]: p["name"] for p in d["players"]}

    res_ids = {r["id"] for r in d["results"]}
    added, new_up, notes, errors = [], {}, [], []
    hydrated = {}

    def hydrate(td):
        if td not in hydrated:
            hydrated[td] = get(f"/division/{td}/hydrate")
        return hydrated[td]

    for pid, vid in VBL.items():
        try:
            prof = get(f"/playerprofile/{vid}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{names.get(pid, pid)}: {e}")
            continue
        for t in prof.get("tournaments", []):
            date = (t.get("date") or "")[:10]
            if not date or date < season:
                continue
            partners = [lv_name(p.get("name")) for p in t.get("partners", [])]
            single = len(partners) == 1
            try:
                h = hydrate(t["tdId"])
            except Exception as e:  # noqa: BLE001
                errors.append(f"{t.get('tournament')}: {e}")
                h = None
            days = (h or {}).get("days") or []
            start = min((x.get("date") or date)[:10] for x in days) if days else date
            end = max((x.get("date") or date)[:10] for x in days) if days else date
            loc = (((h or {}).get("location") or {}).get("name")) or ""
            ev_url = f"https://volleyballlife.com/event/{t['id']}"
            event = t.get("tournament", "")
            division = t.get("division", "")

            # --- nākamais turnīrs ---
            if end >= today and t.get("finish") is None:
                uid = f"u-vbl-{t['id']}"
                u = new_up.get(uid) or {
                    "id": uid, "players": [], "team": "", "date": start,
                    "endDate": end if end != start else "", "sport": "beach",
                    "event": event + (f" ({division} divīzija)" if division else ""),
                    "opponent": "", "location": loc, "source": ev_url,
                }
                if pid not in u["players"]:
                    u["players"].append(pid)
                u["team"] = ", ".join(sorted({x for x in (u["team"].split(", ") if u["team"] else [])} | {lv_team(t.get("teamName", ""))}))
                new_up[uid] = u
                continue

            # jau ir citu avotu mači šim turnīram šai spēlētājai?
            covered = any(r["player"] == pid and start <= r["date"] <= end and "volleyballlife.com" not in (r.get("source") or "")
                          for r in d["results"])

            if not single:
                note = f"{names.get(pid, pid)}: {event} – pāris nav nosakāms (pieteikti {len(partners)} vārdi)"
                if note not in notes:
                    notes.append(note)
                continue

            partner = partners[0]
            # --- mači ---
            if h and not covered:
                tid = t.get("teamId")
                teams = {x["id"]: x for x in h.get("teams", [])}
                day_of = {}
                for day in days:
                    for m in walk_matches(day):
                        day_of[id(m)] = day
                for day in days:
                    for m in walk_matches(day):
                        hid, aid = team_id(m["homeTeam"]), team_id(m["awayTeam"])
                        if tid not in (hid, aid) or not m.get("isMatch", True) or m.get("isBye"):
                            continue
                        home = hid == tid
                        games = [(g.get("home"), g.get("away")) if home else (g.get("away"), g.get("home"))
                                 for g in m.get("games", [])]
                        games = [g for g in games if g[0] is not None and g[1] is not None and (g[0] or g[1])]
                        if not games:
                            continue
                        won = sum(1 for a, b in games if a > b)
                        lost = sum(1 for a, b in games if b > a)
                        if won == lost:
                            continue  # mačs vēl nav pabeigts
                        opp = teams.get(aid if home else hid, {}).get("name", "")
                        mdate = (day.get("date") or date)[:10]
                        rid = f"r-{pid}-{mdate}-vbl-m{m.get('id')}"
                        if rid in res_ids:
                            continue
                        r = {
                            "id": rid, "player": pid, "date": mdate, "sport": "beach",
                            "event": event + (f", {loc}" if loc else ""),
                            "round": " · ".join(x for x in [f"{division} divīzija" if division else "", round_name(day.get("name"))] if x),
                            "opponent": lv_team(opp), "partner": partner,
                            "score": ", ".join(f"{a}-{b}" for a, b in games),
                            "result": "W" if won > lost else "L", "stats": "", "source": ev_url,
                        }
                        d["results"].append(r); res_ids.add(rid); added.append(r)

            # --- gala vieta ---
            fin = t.get("finish")
            pl_id = f"r-{pid}-{date}-vbl-{t['id']}-{t['tdId']}"
            if isinstance(fin, int) and pl_id not in res_ids:
                r = {
                    "id": pl_id, "player": pid, "date": date, "sport": "beach",
                    "event": event + (f", {loc}" if loc else ""),
                    "round": (f"{division} divīzija, " if division else "") + "gala vieta",
                    "opponent": "", "partner": partner, "score": f"{fin}. vieta", "result": "",
                    "stats": "", "source": ev_url,
                }
                d["results"].append(r); res_ids.add(pl_id); added.append(r)

    # nākamie turnīri: nepievieno, ja tai pašai spēlētājai tajā datumā jau ir ieraksts
    up = {u["id"]: u for u in d.get("upcoming", [])}
    for uid, u in new_up.items():
        dup = any(o["id"] != uid and set(o.get("players", [])) & set(u["players"]) and o["date"] == u["date"]
                  for o in up.values())
        if not dup:
            up[uid] = u
    cutoff = (now.date() - datetime.timedelta(days=1)).isoformat()
    d["upcoming"] = sorted([u for u in up.values() if (u.get("endDate") or u["date"]) >= cutoff], key=lambda u: u["date"])

    # kopsavilkums un žurnāls
    who = {}
    for r in added:
        who.setdefault(names.get(r["player"], r["player"]), []).append(r)
    parts = []
    for n, rs in who.items():
        w = sum(1 for r in rs if r["result"] == "W"); l = sum(1 for r in rs if r["result"] == "L")
        pl = [r["score"] for r in rs if not r["result"]]
        bit = n + ": " + (f"{w} uzvaras, {l} zaudējumi" if (w or l) else "") + ((", " if (w or l) else "") + "gala vieta " + pl[0] if pl else "")
        parts.append(bit)
    text = ("VolleyballLife: pievienoti " + str(len(added)) + " ieraksti (" + "; ".join(parts) + ")") if added else "VolleyballLife: jaunu rezultātu nav"
    text += f"; nākamie turnīri: {len(new_up)}"
    if errors:
        text += "; kļūdas: " + "; ".join(errors[:3])
    meta["updatedAt"] = now.isoformat(timespec="minutes")
    meta.setdefault("log", []).append({"at": meta["updatedAt"], "text": text})
    meta["log"] = meta["log"][-30:]
    if added:
        meta["summary"] = "; ".join(parts)
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(text)
    for n in notes:
        print("  piezīme:", n)
    if errors and len(errors) >= len(VBL):
        sys.exit(1)  # nekas nestrādāja


if __name__ == "__main__":
    main()
