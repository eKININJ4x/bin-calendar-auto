"""Generate a subscribed bin calendar from Barking & Dagenham Council data."""
import argparse
from datetime import date, datetime, timedelta, timezone, time
from zoneinfo import ZoneInfo
import hashlib
import json
import os
from pathlib import Path
import urllib.request

BASE = Path(__file__).resolve().parent
OUT = BASE / "docs" / "bin_collection_schedule.ics"
STATE = BASE / "docs" / "last_success.json"
REFRESH_DAYS = 21

def ical_escape(value):
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\\;")

def fetch_data(uprn):
    url = f"https://www.lbbd.gov.uk/rest/bin/{uprn}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/json, */*",
        "User-Agent": "Mozilla/5.0 (compatible; BinCalendar/1.1)",
        "Referer": "https://www.lbbd.gov.uk/rubbish-recycling/household-bin-collection/check-your-bin-collection-days",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

def fetch_fallback(uprn, postcode):
    """Try the independent UK Bin Day service if the council rejects cloud requests."""
    from urllib.parse import urlencode
    params = urlencode({"postcode": postcode})
    url = f"https://ukbinday.co.uk/api/v2/E09000002/view/{uprn}?{params}"
    request = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "BinCalendarAuto/1.2"
    })
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = json.load(response)
    if not isinstance(raw, dict) or raw.get("deeplink"):
        raise ValueError("Fallback service cannot provide collection dates for this property")
    rows = raw.get("dates")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Fallback service returned no collection dates")
    events = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid fallback collection entry")
        kind = row.get("type")
        label = kind.get("label") if isinstance(kind, dict) else None
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Missing fallback bin type")
        day = date.fromisoformat(row["date"])
        events.add((label.strip(), day))
    if not events:
        raise ValueError("Fallback calendar empty")
    return sorted(events, key=lambda item: (item[1], item[0]))

def parse_dates(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get("results"), list):
        raise ValueError("Unexpected council response: missing results list")
    events = set()
    for record in raw["results"]:
        if not isinstance(record, dict):
            raise ValueError("Unexpected bin record")
        name = record.get("bin_name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Missing bin name")
        future = record.get("futurecollections") or []
        if not isinstance(future, list):
            raise ValueError("Unexpected futurecollections format")
        for item in [record.get("nextcollection"), *future]:
            if item is None or item == "":
                continue
            if not isinstance(item, str):
                raise ValueError("Unexpected collection date format")
            try:
                day = datetime.strptime(item.strip(), "%A %d %B %Y").date()
            except ValueError as exc:
                raise ValueError(f"Invalid collection date: {item!r}") from exc
            events.add((name.strip(), day))
    if not events:
        raise ValueError("No collections received: preserving previous calendar")
    return sorted(events, key=lambda x: (x[1], x[0]))

def build_calendar(events, *, stamp=None):
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Bin Calendar Auto//EN",
        "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "X-WR-CALNAME:Bin Collections",
        "X-WR-CALDESC:Automatically updated council bin collections",
    ]
    for name, day in events:
        uid = hashlib.sha256(f"{name}\x00{day.isoformat()}".encode()).hexdigest()[:24] + "@bin-calendar-auto"
        lines += [
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
            f"DTEND;VALUE=DATE:{(day + timedelta(days=1)):%Y%m%d}",
            f"SUMMARY:{ical_escape(name)} Collection",
            "TRANSP:TRANSPARENT", "END:VEVENT",
        ]
    grouped = {}
    for name, day in events:
        grouped.setdefault(day, set()).add(name)
    for day, names in sorted(grouped.items()):
        eve = day - timedelta(days=1)
        start = datetime.combine(eve, time(18, 0), tzinfo=ZoneInfo("Europe/London"))
        end = start + timedelta(minutes=15)
        uid = hashlib.sha256(f"reminder\x00{day.isoformat()}".encode()).hexdigest()[:24] + "@bin-calendar-auto"
        short_names = ", ".join(sorted(name.split(" (")[0] for name in names))
        lines += [
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}",
            f"DTSTART;TZID=Europe/London:{start:%Y%m%dT%H%M%S}",
            f"DTEND;TZID=Europe/London:{end:%Y%m%dT%H%M%S}",
            f"SUMMARY:{ical_escape('Put bins out: ' + short_names)}",
            "DESCRIPTION:Evening-before reminder for tomorrow's bin collection.",
            "BEGIN:VALARM", "ACTION:DISPLAY",
            "DESCRIPTION:Put your bins out for tomorrow",
            "TRIGGER:-PT0M", "END:VALARM", "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

def should_run(today, force=False):
    if force or not STATE.exists() or not OUT.exists():
        return True
    try:
        previous = date.fromisoformat(json.loads(STATE.read_text(encoding="utf-8"))["last_success"])
        return (today - previous).days >= REFRESH_DAYS or today < previous
    except (OSError, ValueError, KeyError, TypeError):
        return True

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--fixture", help="Local council-shaped JSON test data")
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("Europe/London")).date()
    if not should_run(today, args.force or bool(args.fixture)):
        print("Not due yet: most recent refresh was less than 21 days ago.")
        return
    if args.fixture:
        raw = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    else:
        uprn = os.getenv("BIN_UPRN", "").strip()
        if not uprn.isdigit():
            raise SystemExit("Set the BIN_UPRN repository Actions secret to your property UPRN.")
        try:
            raw = fetch_data(uprn)
            events = parse_dates(raw)
            print("Source: Barking & Dagenham Council")
        except Exception as primary_error:
            print(f"Council request failed: {type(primary_error).__name__}: {primary_error}")
            postcode = os.getenv("BIN_POSTCODE", "").strip()
            if not postcode:
                raise RuntimeError(
                    "Council request failed. Set BIN_POSTCODE as an Actions secret "
                    "to enable the independent fallback provider."
                ) from primary_error
            try:
                events = fetch_fallback(uprn, postcode)
                print("Source: UK Bin Day fallback")
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Council and fallback both failed; old calendar preserved. "
                    f"Fallback: {type(fallback_error).__name__}: {fallback_error}"
                ) from fallback_error
    if args.fixture:
        events = parse_dates(raw)
    content = build_calendar(events)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(content.encode("utf-8"))
    STATE.write_text(json.dumps({"last_success": today.isoformat(), "event_count": len(events)}, indent=2) + "\n", encoding="utf-8")
    print(f"Calendar refreshed: {len(events)} collections; latest date: {events[-1][1]}")

if __name__ == "__main__":
    main()
