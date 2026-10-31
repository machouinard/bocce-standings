# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4", "openpyxl>=3.1"]
# ///
"""Turn the league's schedule (and optionally roster) PDF into sheet tabs.

Usage:
  uv run tools/season_import.py --season "2027 Spring" \
      --schedule "Schedule-Friday Spring 2027.pdf" --roster "Roster-Friday 630PM.pdf" \
      [--with-results] [--out season.xlsx]

Writes an .xlsx with these tabs, ready for Google Sheets
(File > Import > Upload > "Insert new sheet(s)"):
  "<season> Schedule"  Date | Court | Team | Opponent   (byes: Opponent = BYE)
  "<season> Teams"     Team | Short | Captain
  "<season>"           (with --with-results) the empty results grid, BYEs filled in

Team names are matched to the existing results tab in the live sheet when there is
one, so typos in the PDFs (e.g. "Castlle Rock Hotshots", "2PAC LIVES") are fixed.
"""
import argparse, csv, difflib, io, re, sys, urllib.parse, urllib.request
from datetime import date

from pypdf import PdfReader

SHEET_ID = "1miUoIW9SfAvgpenrAoiXBBaoT2Tz7JySQedyDTllIT4"
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
DATE_RE = re.compile(r"^([A-Za-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?$")
STOP = {"bocce", "club", "is", "for", "in", "al", "my", "the", "team"}


def key(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def pdf_text(path, layout):
    r = PdfReader(path)
    mode = {"extraction_mode": "layout"} if layout else {}
    return "\n".join(p.extract_text(**mode) for p in r.pages)


def parse_schedule(path):
    text = pdf_text(path, layout=True)
    year = None
    m = re.search(r"\b(20\d\d)\b", text)
    if m:
        year = int(m.group(1))
    playoff = re.search(r"Playoffs[^\n]*", text)
    playoff = re.sub(r"\s+", " ", playoff.group(0)).strip() if playoff else ""

    weeks, block = [], None  # block = {"date": (m, d) | None, "rows": [...]}

    def new_block():
        nonlocal block
        block = {"date": None, "rows": []}
        weeks.append(block)

    for line in text.splitlines():
        toks = [t.strip() for t in re.split(r"\s{2,}", line.strip()) if t.strip()]
        if not toks:
            continue
        if toks[0].upper() == "BYE" and len(toks) == 2:
            new_block()
            block["rows"].append(("", toks[1], "BYE"))
            continue
        if "vs" not in toks:
            continue
        i = toks.index("vs")
        if i < 2:
            continue
        team_a, team_b, court = toks[i - 1], toks[i + 1] if i + 1 < len(toks) else "", toks[i - 2]
        if not court.isdigit():
            continue
        if block is None or (court == "1" and block["rows"] and block["rows"][-1][0] != ""):
            new_block()
        for t in toks[: i - 2]:
            dm = DATE_RE.match(t)
            if dm and dm.group(1)[:3].lower() in MONTHS:
                block["date"] = (MONTHS[dm.group(1)[:3].lower()], int(dm.group(2)))
        block["rows"].append((court, team_a, team_b))

    weeks = [w for w in weeks if w["rows"]]
    missing = [i + 1 for i, w in enumerate(weeks) if not w["date"]]
    if missing:
        sys.exit(f"Could not find a date for week(s) {missing} in {path}")
    return year, playoff, weeks


def parse_roster(path, names):
    lines = [l.strip() for l in pdf_text(path, layout=False).splitlines() if l.strip()]
    captains = {}
    for i, l in enumerate(lines):
        cm = re.match(r"(.+?)\s*[-–]\s*Captain$", l, re.I)
        if cm and i > 0:
            team = canon(lines[i - 1], names, quiet=True)
            if team:
                captains[team] = cm.group(1).strip()
    return captains


def canon(name, names, quiet=False):
    k = key(name)
    by_key = {key(n): n for n in names}
    if k in by_key:
        return by_key[k]
    close = difflib.get_close_matches(k, by_key, n=1, cutoff=0.85)
    if close:
        if not quiet:
            print(f"  note: '{name}' -> '{by_key[close[0]]}'")
        return by_key[close[0]]
    return None


def fetch_tab(tab):
    url = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&headers=1"
           f"&sheet={urllib.parse.quote(tab)}")
    try:
        return list(csv.reader(io.StringIO(urllib.request.urlopen(url, timeout=15).read().decode())))
    except Exception:
        return None


def live_team_names(season):
    # Google returns the first tab when a tab name doesn't exist, so only trust
    # a season tab that the Seasons tab lists.
    seasons = fetch_tab("Seasons")
    if not seasons or seasons[0][0].strip().lower() != "tab":
        return None
    if season not in {r[0].strip() for r in seasons[1:] if r}:
        return None
    rows = fetch_tab(season)
    if not rows or rows[0][0].strip().lower() != "team":
        return None
    return [r[0].strip() for r in rows[1:] if r and r[0].strip()]


def short_name(name):
    words = re.findall(r"[A-Za-z0-9']+", name)
    if len(words) >= 3 and [w.lower() for w in words[:2]] == ["castle", "rock"]:
        return "CR " + " ".join(words[2:])
    rest = [w for w in words if w.lower() not in STOP]
    return rest[-1] if len(rest) == 1 else (rest[0] if rest else name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", required=True, help='Tab name, e.g. "2027 Spring"')
    ap.add_argument("--schedule", required=True)
    ap.add_argument("--roster")
    ap.add_argument("--with-results", action="store_true", help="also build the empty results tab")
    ap.add_argument("--out")
    a = ap.parse_args()

    year, playoff, weeks = parse_schedule(a.schedule)
    sched_names = sorted({t for w in weeks for _, x, y in w["rows"] for t in (x, y) if t != "BYE"})

    names = live_team_names(a.season)
    if names:
        print(f"Matching team names to the existing '{a.season}' tab ({len(names)} teams).")
    else:
        # Use the most common spelling in the schedule, folding near-duplicates (typos).
        counts = {}
        for w in weeks:
            for _, x, y in w["rows"]:
                for t in (x, y):
                    if t != "BYE":
                        counts[t] = counts.get(t, 0) + 1
        names = []
        for t in sorted(counts, key=lambda t: -counts[t]):
            if not canon(t, names, quiet=True):
                names.append(t)
        names.sort(key=str.lower)

    fixed = []
    for w in weeks:
        for court, x, y in w["rows"]:
            cx = canon(x, names)
            cy = "BYE" if y == "BYE" else canon(y, names)
            if not cx or not cy:
                sys.exit(f"Unknown team in schedule: '{x}' vs '{y}'. Known: {names}")
            fixed.append((w["date"], court, cx, cy))

    # Sanity checks: each team appears exactly once per week.
    for w in weeks:
        seen = [canon(t, names, quiet=True) for _, x, y in w["rows"] for t in (x, y) if t != "BYE"]
        dup = {t for t in seen if seen.count(t) > 1}
        if dup or len(set(seen)) != len(names):
            print(f"  WARNING: week of {w['date'][0]}/{w['date'][1]}: duplicates {dup or '-'}, "
                  f"{len(names) - len(set(seen))} team(s) not scheduled")

    captains = parse_roster(a.roster, names) if a.roster else {}
    for n in names:
        if a.roster and n not in captains:
            print(f"  WARNING: no captain found for {n}")

    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.worksheet.datavalidation import DataValidation
    from openpyxl.formatting.rule import CellIsRule
    from openpyxl.utils import get_column_letter as col

    hdr_fill, hdr_font = PatternFill("solid", fgColor="1F4E3D"), Font(bold=True, color="FFFFFF")

    def header(ws, values):
        for i, v in enumerate(values, 1):
            c = ws.cell(1, i, v)
            c.fill, c.font = hdr_fill, hdr_font
        ws.freeze_panes = "A2"

    def text(ws, r, c, v):
        cell = ws.cell(r, c, v)
        cell.number_format = "@"
        return cell

    wb = Workbook()
    ws = wb.active
    ws.title = f"{a.season} Schedule"
    header(ws, ["Date", "Court", "Team", "Opponent"])
    for r, ((m, d), court, x, y) in enumerate(fixed, 2):
        text(ws, r, 1, f"{m}/{d}")
        if court:
            ws.cell(r, 2, int(court))
        text(ws, r, 3, x)
        text(ws, r, 4, y)
    for c, w in zip("ABCD", (8, 7, 24, 24)):
        ws.column_dimensions[c].width = w

    ws = wb.create_sheet(f"{a.season} Teams")
    header(ws, ["Team", "Short", "Captain"])
    for r, n in enumerate(names, 2):
        text(ws, r, 1, n)
        text(ws, r, 2, short_name(n))
        text(ws, r, 3, captains.get(n, ""))
    for c, w in zip("ABC", (24, 14, 24)):
        ws.column_dimensions[c].width = w

    if a.with_results:
        ws = wb.create_sheet(a.season, 0)
        dates = [w["date"] for w in weeks]
        byes = {(w["date"], x) for w in weeks for _, x, y in w["rows"] if y == "BYE"}
        ws.cell(1, 1, "Team")
        for i, (m, d) in enumerate(dates):
            for k in (0, 1):
                text(ws, 1, 2 + 2 * i + k, f"{m}/{d}")
        last = col(1 + 2 * len(dates))
        wc, lc = 2 + 2 * len(dates), 3 + 2 * len(dates)
        ws.cell(1, wc, "W")
        ws.cell(1, lc, "L")
        for c in ws[1]:
            c.fill, c.font = hdr_fill, hdr_font
            c.alignment = Alignment(horizontal="center")
        for r, n in enumerate(names, 2):
            ws.cell(r, 1, n)
            for i, dt in enumerate(dates):
                if (dt, n) in byes:
                    ws.cell(r, 2 + 2 * i, "BYE")
                    ws.cell(r, 3 + 2 * i, "BYE")
            ws.cell(r, wc, f'=COUNTIF(B{r}:{last}{r},"W")')
            ws.cell(r, lc, f'=COUNTIF(B{r}:{last}{r},"L")+COUNTIF(B{r}:{last}{r},"F")')
        rng = f"B2:{last}{len(names) + 21}"
        dv = DataValidation(type="list", formula1='"W,L,F,BYE"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(rng)
        for v, bg, fg in (("W", "D4EDDA", "155724"), ("L", "F8D7DA", "721C24"),
                          ("F", "FFE5B4", "8A4B00"), ("BYE", "F2F2F2", "C00000")):
            ws.conditional_formatting.add(rng, CellIsRule(
                operator="equal", formula=[f'"{v}"'],
                fill=PatternFill("solid", bgColor=bg), font=Font(color=fg)))
        ws.column_dimensions["A"].width = 24
        for c in range(2, lc + 1):
            ws.column_dimensions[col(c)].width = 6.5
        ws.freeze_panes = "B2"

    out = a.out or f"{a.season} import.xlsx"
    wb.save(out)
    print(f"\nWrote {out}: {len(weeks)} weeks, {len(names)} teams, {len(captains)} captains.")
    print("Seasons tab row (Tab | Season | Year | Note):")
    print(f"  {a.season} | {a.season} League | {year or date.today().year} | {playoff}")


if __name__ == "__main__":
    main()
