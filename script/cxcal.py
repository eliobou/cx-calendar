#!/usr/bin/env python3
"""Génère docs/cyclocross-elite.ics à partir de races.json.

Usage : python3 script/cxcal.py   (Python 3.9+, bibliothèque standard uniquement)
"""

import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
RACES = HERE / "races.json"
OUTPUT = HERE.parent / "docs" / "cyclocross-elite.ics"
CALENDAR_NAME = "Cyclocross Élite 2026-27"
DURATION = timedelta(minutes=60)
PARIS = ZoneInfo("Europe/Paris")
CATEGORIES = {"we": "Femmes", "me": "Hommes"}
UTC_FMT = "%Y%m%dT%H%M%SZ"


def escape(text):
    return (text.replace("\\", "\\\\").replace(";", "\\;")
            .replace(",", "\\,").replace("\n", "\\n"))


def fold(line):
    """Coupe les lignes à 75 octets (RFC 5545)."""
    if len(line.encode("utf-8")) <= 75:
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


def race_day(race, cat):
    return date.fromisoformat(race.get(f"{cat}_date") or race["date"])


def event(race, cat):
    day = race_day(race, cat)
    hour, minute = map(int, race[f"{cat}_time"].split(":"))
    start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=ZoneInfo(race["tz"]))
    confirmed = race.get("time_confirmed", False)
    description = "\n".join([
        f"{race['series']} · Élite {CATEGORIES[cat]}",
        f"Départ : {start.astimezone(PARIS):%H:%M} (heure de Paris)"
        + ("" if confirmed else " — heure estimée, à confirmer"),
        f"Lieu : {race['location']}",
    ])
    # DTSTAMP dérivé du contenu : le fichier ne change que si la course change.
    digest = hashlib.sha1(f"{start}{race['name']}{description}".encode()).hexdigest()
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=int(digest[:6], 16))
    return [
        "BEGIN:VEVENT",
        f"UID:{race['id']}-{cat}@cxcal",
        f"DTSTAMP:{stamp:{UTC_FMT}}",
        f"DTSTART:{start.astimezone(timezone.utc):{UTC_FMT}}",
        f"DTEND:{(start + DURATION).astimezone(timezone.utc):{UTC_FMT}}",
        f"SUMMARY:{escape(race['name'] + ' – ' + CATEGORIES[cat])}",
        f"LOCATION:{escape(race['location'])}",
        f"DESCRIPTION:{escape(description)}",
        f"CATEGORIES:{escape(race['series'])}",
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
    ]


def main():
    races = json.loads(RACES.read_text(encoding="utf-8"))["races"]
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//cxcal//Cyclocross Elite//FR",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape(CALENDAR_NAME)}",
        "X-WR-TIMEZONE:Europe/Paris",
        "REFRESH-INTERVAL;VALUE=DURATION:P1D",
        "X-PUBLISHED-TTL:P1D",
    ]
    for race in sorted(races, key=lambda r: (race_day(r, "we"), r["id"])):
        for cat in CATEGORIES:
            lines += event(race, cat)
    lines.append("END:VCALENDAR")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(fold(l) for l in lines) + "\r\n")
    print(f"{OUTPUT} : {lines.count('BEGIN:VEVENT')} événements")


if __name__ == "__main__":
    main()
