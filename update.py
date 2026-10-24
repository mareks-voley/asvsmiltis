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


def round_name(day_name, day=None):
    k = (day_name or "").strip()
    if day is not None:
        if day.get("poolPlay") and not day.get("bracketPlay"):
            return "grupu turnīrs"
        if day.get("bracketPlay"):
            return "izslēgšanas spēles"
    return DAY_LV.get(k.lower(), f"{k} izslēgšanas spēles" if k else "")


def div_name(division):
    dv = re.sub(r"\s*(Division|Div\.?)\s*$", "", (division or "").strip(), flags=re.I)
    return f"{dv} divīzija" if dv else ""


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


def next_event_text(d, names, today):
    fut = [u for u in d.get("upcoming", []) if (u.get("endDate") or u.get("date", "")) >= today]
    if not fut:
        return ""
    first = min(u["date"] for u in fut)
    evs = [u for u in fut if u["date"] == first]
    y, m, dd = first.split("-")
    bits = []
    for u in evs:
        who = ", ".join(names.get(p, p) for p in u.get("players", []))
        bits.append(f"{who} ({u.get('event', '')}, {u.get('location', '')})")
    return f" Nākamie turnīri {int(dd)}.{int(m)}.: " + "; ".join(bits) + "."


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "data.json"
    d = json.load(open(path, encoding="utf-8"))
    meta = d.setdefault("meta", {})
    season = meta.get("seasonStart", "2026-08-01")
    now = datetime.datetime.now(TZ)
    today = now.date().isoformat()
    names = {p["id"]: p["name"] for p in d["players"]}
    up_before = json.dumps(sorted(u["id"] for u in d.get("upcoming", [])))

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
            event = re.sub(r"\s+", " ", t.get("tournament", "")).strip()
            division = t.get("division", "")

            my_name = f"{prof.get('firstName', '')} {prof.get('lastName', '')}".strip().lower()
            finished = t.get("finish") is not None or end < today

            # --- nākamais / notiekošs turnīrs ---
            if not finished:
                uid = f"u-vbl-{t['id']}"
                u = new_up.get(uid) or {
                    "id": uid, "players": [], "team": "", "date": start,
                    "endDate": end if end != start else "", "sport": "beach",
                    "event": event + (f" ({div_name(division)})" if division else ""),
                    "opponent": "", "location": loc, "source": ev_url,
                }
                if pid not in u["players"]:
                    u["players"].append(pid)
                u["team"] = ", ".join(sorted({x for x in (u["team"].split(", ") if u["team"] else [])} | {lv_team(t.get("teamName", ""))}))
                new_up[uid] = u
                if start > today:
                    continue  # vēl nav sācies – mačus nav ko ņemt

            # jau ir citu avotu mači šim turnīram šai spēlētājai?
            covered = any(r["player"] == pid and start <= r["date"] <= end and "volleyballlife.com" not in (r.get("source") or "")
                          for r in d["results"])

            # --- mači (partneri nosaka pēc katra mača sastāva "lineups") ---
            match_partners = []
            if h and not covered:
                tid = t.get("teamId")
                teams = {x["id"]: x for x in h.get("teams", [])}
                me = teams.get(tid, {})
                pl_by_id = {x.get("id"): (x.get("name") or f"{x.get('firstName', '')} {x.get('lastName', '')}").strip()
                            for x in me.get("players", [])}
                my_ids = {i for i, n in pl_by_id.items() if n.lower() == my_name}
                for day in days:
                    for m in walk_matches(day):
                        hid, aid = team_id(m["homeTeam"]), team_id(m["awayTeam"])
                        if tid not in (hid, aid) or not m.get("isMatch", True) or m.get("isBye"):
                            continue
                        lineup = None
                        for lu in m.get("lineups") or []:
                            if lu.get("teamId") == tid:
                                for pos in lu.get("positions") or []:
                                    lineup = set(pos.get("players") or [])
                        if lineup is not None and my_ids:
                            if not (lineup & my_ids):
                                continue  # šo maču spēlēja citas komandas biedrenes
                            others = [pl_by_id.get(i, "") for i in lineup - my_ids]
                            partner = lv_name(others[0]) if others else ""
                        elif len(partners) == 1:
                            partner = partners[0]
                        else:
                            continue  # nav zināms, vai viņa spēlēja
                        home = hid == tid
                        games = [(g.get("home"), g.get("away")) if home else (g.get("away"), g.get("home"))
                                 for g in m.get("games", [])]
                        games = [g for g in games if g[0] is not None and g[1] is not None and (g[0] or g[1])]
                        if not games:
                            continue
                        won = sum(1 for a, b in games if a > b)
                        lost = sum(1 for a, b in games if b > a)
                        need = 2 if len(m.get("games", [])) >= 3 else 1
                        if max(won, lost) < need:
                            continue  # mačs vēl nav pabeigts
                        match_partners.append(partner)
                        opp = teams.get(aid if home else hid, {}).get("name", "")
                        mdate = (day.get("date") or date)[:10]
                        rid = f"r-{pid}-{mdate}-vbl-m{m.get('id')}"
                        if rid in res_ids:
                            continue
                        r = {
                            "id": rid, "player": pid, "date": mdate, "sport": "beach",
                            "event": event + (f", {loc}" if loc else ""),
                            "round": " · ".join(x for x in [div_name(division), round_name(day.get("name"), day)] if x),
                            "opponent": lv_team(opp), "partner": partner,
                            "score": ", ".join(f"{a}-{b}" for a, b in games),
                            "result": "W" if won > lost else "L", "stats": "", "source": ev_url,
                        }
                        d["results"].append(r); res_ids.add(rid); added.append(r)

            # --- gala vieta ---
            fin = t.get("finish")
            if len(partners) == 1:
                partner = partners[0]
            elif match_partners:
                partner = max(set(match_partners), key=match_partners.count)
            else:
                partner = None
            pl_id = f"r-{pid}-{date}-vbl-{t['id']}-{t['tdId']}"
            if isinstance(fin, int) and pl_id not in res_ids:
                if partner is None:
                    note = f"{names.get(pid, pid)}: {event} – pāris nav nosakāms (pieteikti {len(partners)} vārdi, nav mača sastāvu)"
                    if note not in notes:
                        notes.append(note)
                    continue
                r = {
                    "id": pl_id, "player": pid, "date": date, "sport": "beach",
                    "event": event + (f", {loc}" if loc else ""),
                    "round": (div_name(division) + ", " if division else "") + "gala vieta",
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
    today = now.date().isoformat()
    vbl_logged_today = any(str(l.get("at", ""))[:10] == today and str(l.get("text", "")).startswith("VolleyballLife")
                           for l in meta.get("log", []))
    up_after = json.dumps(sorted(u["id"] for u in d.get("upcoming", [])))
    if not added and vbl_logged_today and "--force" not in sys.argv and up_after == up_before:
        print(text + " (bez izmaiņām, fails netiek mainīts)")
        return
    # vai šodien datus jau labojis kāds cits (Claude rīta uzdevums / pārbaude)?
    touched_today = any(str(l.get("at", ""))[:10] == today and not str(l.get("text", "")).startswith("VolleyballLife")
                        for l in meta.get("log", []))
    meta["updatedAt"] = now.isoformat(timespec="minutes")
    meta.setdefault("log", []).append({"at": meta["updatedAt"], "text": text})
    meta["log"] = meta["log"][-30:]
    if added:
        meta["summary"] = "; ".join(parts)
    elif not touched_today:
        # neatstāj vakardienas kopsavilkumu: ieliek "nekā jauna" + nākamo turnīru
        meta["summary"] = "Šonakt jaunu rezultātu nebija." + next_event_text(d, names, today)
    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(text)
    for n in notes:
        print("  piezīme:", n)
    if errors and len(errors) >= len(VBL):
        sys.exit(1)  # nekas nestrādāja


if __name__ == "__main__":
    main()
