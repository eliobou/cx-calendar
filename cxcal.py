#!/usr/bin/env python3
"""Generate a dynamic .ics calendar of elite cyclocross races.

- Reads the season schedule from races.json.
- For upcoming races, fetches the startlist from ProCyclingStats (cross site),
  ranks the riders with the UCI cyclocross ranking and writes the top N
  in the event description.
- Optionally commits and pushes the .ics to a git repository (GitHub Pages).

Only the Python 3.9+ standard library is used.
"""

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
DISPLAY_TZ = ZoneInfo("Europe/Paris")
CATEGORIES = {"we": "Femmes", "me": "Hommes"}

DEFAULT_CONFIG = {
    "output": "docs/cyclocross-elite.ics",
    "calendar_name": "Cyclocross Élite 2026-27",
    "top_n": 10,
    "lookahead_days": 7,
    "event_duration_minutes": 60,
    "request_delay_seconds": 2.0,
    "pcs_base": "https://cx.procyclingstats.com",
    "pcs_years": [2026, 2027],
    "ranking_urls": {
        "me": ["{base}/rankings/me/uci-ranking", "{base}/rankings/uci-ranking"],
        "we": ["{base}/rankings/we/uci-ranking"],
    },
    "fetch_startlists": True,
    "git_push": False,
    "git_repo": ".",
}

USER_AGENT = "cxcal/1.0 (personal calendar script; contact via GitHub repo)"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def load_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def save_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class Fetcher:
    """HTTP GET with polite delay and an in-memory cache for one run."""

    def __init__(self, delay, offline_dir=None):
        self.delay = delay
        self.offline_dir = Path(offline_dir) if offline_dir else None
        self.cache = {}
        self.last_request = 0.0

    def get(self, url):
        if url in self.cache:
            return self.cache[url]
        if self.offline_dir:
            # Test mode: map URL to a local fixture file.
            fixture = self.offline_dir / (slugify(url) + ".html")
            body = fixture.read_text(encoding="utf-8") if fixture.exists() else None
            self.cache[url] = body
            return body
        wait = self.delay - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read().decode("utf-8", errors="replace")
        except (urllib.error.URLError, TimeoutError) as exc:
            log(f"  fetch failed {url}: {exc}")
            body = None
        self.cache[url] = body
        return body


# ---------------------------------------------------------------------------
# ProCyclingStats parsing
# ---------------------------------------------------------------------------

RIDER_LINK_RE = re.compile(r'<a[^>]+href="/?rider/([a-z0-9\-]+)"[^>]*>(.*?)</a>', re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")


def clean_text(fragment):
    return " ".join(html.unescape(TAG_RE.sub(" ", fragment)).split())


def main_content(page):
    """Keep only the main content, dropping menus and sidebars when possible."""
    for marker in ('class="page-content', 'class="content', "<main"):
        idx = page.find(marker)
        if idx != -1:
            page = page[idx:]
            break
    for marker in ('class="footer', "<footer"):
        idx = page.find(marker)
        if idx != -1:
            page = page[:idx]
            break
    return page


def parse_startlist(page):
    """Return riders [(slug, display_name)] in page order (= bib order on PCS)."""
    riders, seen = [], set()
    for slug, label in RIDER_LINK_RE.findall(main_content(page)):
        name = clean_text(label)
        if slug in seen or not name:
            continue
        seen.add(slug)
        riders.append((slug, name))
    return riders


def parse_ranking(page):
    """Return {rider_slug: (rank, points)} from a PCS ranking table."""
    ranking = {}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S | re.I):
        link = RIDER_LINK_RE.search(row)
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S | re.I)
        if not link or not cells:
            continue
        rank_txt = clean_text(cells[0])
        if not rank_txt.isdigit():
            continue
        numbers = [clean_text(c) for c in cells if clean_text(c).replace(".", "").isdigit()]
        points = numbers[-1] if len(numbers) > 1 else ""
        ranking.setdefault(link.group(1), (int(rank_txt), points))
    return ranking


START_TIME_RE = re.compile(r"Start\s*time\s*:?\s*(?:</[^>]+>\s*<[^>]+>\s*)*(\d{1,2}[:h]\d{2})", re.I)


def parse_start_time(page):
    match = START_TIME_RE.search(page or "")
    return match.group(1).replace("h", ":").zfill(5) if match else None


# ---------------------------------------------------------------------------
# PCS race discovery
# ---------------------------------------------------------------------------

def discover_pcs_races(fetcher, cfg, cache_path):
    """Build {slug: [names]} from the PCS season calendars (cached for 7 days)."""
    cached = load_json(cache_path, {})
    if cached.get("fetched") and \
            datetime.fromisoformat(cached["fetched"]) > datetime.now() - timedelta(days=7):
        return cached["races"]
    races = {}
    link_re = re.compile(r'href="/?race/([a-z0-9\-]+)/(\d{4})[^"]*"[^>]*>(.*?)</a>', re.S | re.I)
    for year in cfg["pcs_years"]:
        page = fetcher.get(f"{cfg['pcs_base']}/races.php?year={year}")
        for slug, _yr, label in link_re.findall(page or ""):
            races.setdefault(slug, set()).add(clean_text(label))
    races = {k: sorted(v) for k, v in races.items()}
    if races:
        save_json(cache_path, {"fetched": datetime.now().isoformat(), "races": races})
    return races


def guess_slugs(race, pcs_races):
    """Score PCS slugs against the race location and name; best first."""
    town = slugify(race["location"].split(",")[0].split("(")[0])
    name_tokens = {t for t in slugify(race["name"]).split("-") if len(t) > 3}
    scored = []
    for slug, labels in pcs_races.items():
        hay = slug + " " + " ".join(slugify(label) for label in labels)
        score = 0
        if town and town in hay:
            score += 10
        score += sum(1 for t in name_tokens if t in hay)
        if score >= 10:
            scored.append((score, slug))
    return [slug for _s, slug in sorted(scored, reverse=True)[:3]]


def candidate_urls(base, slug, years, cat):
    for year in years:
        yield f"{base}/race/{slug}/{year}/{cat}/startlist", f"{base}/race/{slug}/{year}/{cat}"
        yield f"{base}/race/{slug}-{cat}/{year}/startlist", f"{base}/race/{slug}-{cat}/{year}"


# ---------------------------------------------------------------------------
# Race data enrichment
# ---------------------------------------------------------------------------

def race_date(race, cat):
    return date.fromisoformat(race.get(f"{cat}_date") or race["date"])


def season_years(race_day, cfg):
    # PCS may file a cross race under the calendar year or the season end year.
    years = [race_day.year] + [y for y in cfg["pcs_years"] if y != race_day.year]
    return years


def load_rankings(fetcher, cfg):
    rankings = {}
    for cat, urls in cfg["ranking_urls"].items():
        rankings[cat] = {}
        for url in urls:
            page = fetcher.get(url.format(base=cfg["pcs_base"]))
            parsed = parse_ranking(page or "")
            if len(parsed) >= 20:
                rankings[cat] = parsed
                break
    # Guard against a gender-less URL returning the men's ranking for women.
    if rankings.get("we") and rankings.get("we") == rankings.get("me"):
        rankings["we"] = {}
    return rankings


def build_top(riders, ranking, top_n):
    """Rank startlist riders by UCI ranking; fall back to bib order."""
    if ranking and sum(1 for slug, _ in riders if slug in ranking) >= 3:
        ranked = sorted(
            riders, key=lambda r: ranking.get(r[0], (10_000, ""))[0])
        top = []
        for slug, name in ranked[:top_n]:
            rank, points = ranking.get(slug, (None, ""))
            label = f"#{rank} UCI" if rank else "non classé"
            if points:
                label += f", {points} pts"
            top.append(f"{name} ({label})")
        return top, "classement UCI"
    return [name for _slug, name in riders[:top_n]], "ordre des dossards (classement UCI indisponible)"


def update_startlists(races, fetcher, cfg, state, today, force_all=False):
    rankings = None
    pcs_races = None
    horizon = today + timedelta(days=cfg["lookahead_days"])
    for race in races:
        for cat in CATEGORIES:
            day = race_date(race, cat)
            if not force_all and not (today - timedelta(days=1) <= day <= horizon):
                continue
            key = f"{race['id']}-{cat}"
            entry = state.setdefault(key, {})
            log(f"Checking {key} ({day})")
            if rankings is None:
                rankings = load_rankings(fetcher, cfg)
                log(f"  rankings loaded: me={len(rankings.get('me', {}))} we={len(rankings.get('we', {}))}")
            slugs = []
            forced = (race.get("pcs") or {}).get(cat)
            if forced:
                slugs = [forced]
            elif entry.get("slug"):
                slugs = [entry["slug"]]
            else:
                if pcs_races is None:
                    pcs_races = discover_pcs_races(fetcher, cfg, BASE_DIR / "cache" / "pcs_races.json")
                slugs = guess_slugs(race, pcs_races)
            found = False
            for slug in slugs:
                for start_url, info_url in candidate_urls(
                        cfg["pcs_base"], slug, season_years(day, cfg), cat):
                    riders = parse_startlist(fetcher.get(start_url) or "")
                    if len(riders) < 3:
                        continue
                    top, method = build_top(riders, rankings.get(cat), cfg["top_n"])
                    entry.update({
                        "slug": slug, "url": start_url, "top": top, "method": method,
                        "count": len(riders), "checked": datetime.now(timezone.utc).isoformat(),
                    })
                    start_time = parse_start_time(fetcher.get(info_url))
                    if start_time:
                        entry["time"] = start_time
                    log(f"  {len(riders)} riders, top: {', '.join(top[:3])}...")
                    found = True
                    break
                if found:
                    break
            if not found:
                entry["checked"] = datetime.now(timezone.utc).isoformat()
                log("  startlist not published yet (or PCS slug unknown)")
    return state


# ---------------------------------------------------------------------------
# ICS generation
# ---------------------------------------------------------------------------

def ics_escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Fold lines to 75 octets as required by RFC 5545."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts, chunk = [], b""
    for ch in line:
        enc = ch.encode("utf-8")
        if len(chunk) + len(enc) > (75 if not parts else 74):
            parts.append(chunk.decode("utf-8"))
            chunk = b""
        chunk += enc
    parts.append(chunk.decode("utf-8"))
    return "\r\n ".join(parts)


def build_event(race, cat, entry, cfg, now_utc):
    day = race_date(race, cat)
    local_time = entry.get("time") or race[f"{cat}_time"]
    confirmed = bool(entry.get("time")) or race.get("time_confirmed", False)
    hour, minute = map(int, local_time.split(":"))
    start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(race["tz"]))
    end = start + timedelta(minutes=cfg["event_duration_minutes"])
    paris = start.astimezone(DISPLAY_TZ)

    lines = [
        f"{race['series']} · Élite {CATEGORIES[cat]}",
        f"Départ : {paris:%H:%M} (heure de Paris)" + ("" if confirmed else " — heure estimée, à confirmer"),
        f"Lieu : {race['location']}",
        "",
    ]
    if entry.get("top"):
        lines.append(f"Top {len(entry['top'])} de la startlist ({entry['method']}, "
                     f"{entry['count']} partants) :")
        lines += [f"{i}. {rider}" for i, rider in enumerate(entry["top"], 1)]
        lines += ["", f"Startlist : {entry['url']}"]
    elif cfg["fetch_startlists"] and day >= now_utc.date():
        lines.append("Startlist pas encore publiée (vérifiée chaque jour).")
    if entry.get("checked"):
        checked = datetime.fromisoformat(entry["checked"]).astimezone(DISPLAY_TZ)
        lines.append(f"Dernière vérification : {checked:%d/%m/%Y %H:%M}")
    description = "\n".join(lines)

    digest = hashlib.sha1(f"{start}{description}".encode()).hexdigest()
    if entry.get("digest") != digest:
        entry["digest"] = digest
        entry["sequence"] = entry.get("sequence", -1) + 1
        entry["modified"] = now_utc.strftime("%Y%m%dT%H%M%SZ")

    fmt = "%Y%m%dT%H%M%SZ"
    props = [
        "BEGIN:VEVENT",
        f"UID:{race['id']}-{cat}@cxcal",
        f"DTSTAMP:{entry['modified']}",
        f"LAST-MODIFIED:{entry['modified']}",
        f"SEQUENCE:{entry['sequence']}",
        f"DTSTART:{start.astimezone(timezone.utc):{fmt}}",
        f"DTEND:{end.astimezone(timezone.utc):{fmt}}",
        f"SUMMARY:{ics_escape(race['name'] + ' – ' + CATEGORIES[cat])}",
        f"LOCATION:{ics_escape(race['location'])}",
        f"DESCRIPTION:{ics_escape(description)}",
        f"CATEGORIES:{ics_escape(race['series'])}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]
    return props


def build_calendar(races, state, cfg):
    now_utc = datetime.now(timezone.utc)
    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//cxcal//Cyclocross Elite//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{ics_escape(cfg['calendar_name'])}",
        "X-WR-TIMEZONE:Europe/Paris",
        "REFRESH-INTERVAL;VALUE=DURATION:PT6H",
        "X-PUBLISHED-TTL:PT6H",
    ]
    for race in sorted(races, key=lambda r: race_date(r, "we")):
        for cat in CATEGORIES:
            entry = state.setdefault(f"{race['id']}-{cat}", {})
            out += build_event(race, cat, entry, cfg, now_utc)
    out.append("END:VCALENDAR")
    return "\r\n".join(fold(line) for line in out) + "\r\n"


# ---------------------------------------------------------------------------
# Publishing
# ---------------------------------------------------------------------------

def git_publish(repo, output):
    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True)
    git("add", str(output))
    if git("diff", "--cached", "--quiet").returncode == 0:
        log("No change to publish.")
        return
    res = git("commit", "-m", f"Update cyclocross calendar {datetime.now():%Y-%m-%d %H:%M}")
    if res.returncode != 0:
        log(f"git commit failed: {res.stderr.strip()}")
        return
    res = git("push")
    log("Pushed to remote." if res.returncode == 0 else f"git push failed: {res.stderr.strip()}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default=BASE_DIR / "config.json")
    parser.add_argument("--races", default=BASE_DIR / "races.json")
    parser.add_argument("--no-fetch", action="store_true", help="only rebuild the .ics from cache")
    parser.add_argument("--all", action="store_true", help="check startlists of every race")
    parser.add_argument("--check", action="store_true",
                        help="print the PCS slug guessed for each race and exit")
    parser.add_argument("--today", help="override today's date (YYYY-MM-DD), for testing")
    parser.add_argument("--offline", help="directory of HTML fixtures (testing)")
    args = parser.parse_args()

    cfg = {**DEFAULT_CONFIG, **(load_json(args.config, {}) or {})}
    races = load_json(args.races)["races"]
    state_path = BASE_DIR / "cache" / "state.json"
    state = load_json(state_path, {})
    today = date.fromisoformat(args.today) if args.today else datetime.now(DISPLAY_TZ).date()
    fetcher = Fetcher(cfg["request_delay_seconds"], args.offline)

    if args.check:
        pcs_races = discover_pcs_races(fetcher, cfg, BASE_DIR / "cache" / "pcs_races.json")
        print(f"{len(pcs_races)} races found on PCS calendars")
        for race in races:
            forced = race.get("pcs")
            guess = forced or guess_slugs(race, pcs_races) or "?? (add 'pcs' in races.json)"
            print(f"{race['id']:22} -> {guess}")
        return 0

    if cfg["fetch_startlists"] and not args.no_fetch:
        update_startlists(races, fetcher, cfg, state, today, force_all=args.all)

    ics = build_calendar(races, state, cfg)
    repo = Path(cfg["git_repo"]).expanduser()
    if not repo.is_absolute():
        repo = (BASE_DIR / repo).resolve()
    output = Path(cfg["output"]).expanduser()
    if not output.is_absolute():
        output = repo / output
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8", newline="") as fh:
        fh.write(ics)
    save_json(state_path, state)
    log(f"Wrote {output} ({ics.count('BEGIN:VEVENT')} events)")

    if cfg["git_push"]:
        git_publish(repo, output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
