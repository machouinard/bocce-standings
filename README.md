# East Portal Bocce Standings

A single-page standings site for the East Portal Bocce Club Friday night league.

- **Results live in a Google Sheet** (one tab per season, plus a `Seasons` tab). The page reads it in the browser every time it loads, so updating the sheet updates the site — no rebuild or deploy.
- **Hosting:** GitHub Pages serves `index.html` from the `main` branch.

## Sheet format

**Season tab** (e.g. `2026 Fall`): column A is the team name; row 1 has a date (`m/d`) above each game column, with each Friday's date appearing twice (game 1 and game 2). Cells are `W`, `L`, `F` (forfeit, counts as a loss), `BYE`, or blank. Blank cells on a date that has passed are shown as **rematches owed**. Columns without a date header (like the W/L totals) are ignored.

**Seasons tab:** `Tab | Season | Year | Note`. The top row is the season the site shows by default; other rows appear in the season picker.

The sheet must be shared as **Anyone with the link → Viewer**.

**Optional per-season tabs** (the page uses them when present):

- `<season> Schedule`: `Date | Court | Team | Opponent`, one row per match, byes as `Opponent = BYE`. Adds opponents, the head-to-head grid, the "This Friday" card, named rematch pairs with "play by" dates (make-ups within 2 weeks, Rules §3), and a "Results to check" list when the two teams' results disagree.
- `<season> Teams`: `Team | Short | Captain`. `Short` is the label used in tight spots like the head-to-head grid.

## New season

The league sends a schedule PDF (and roster PDF) before each season. Turn them into sheet tabs with:

```
uv run tools/season_import.py --season "2027 Spring" \
  --schedule "Schedule-Friday Spring 2027.pdf" --roster "Roster-Friday 630PM.pdf" --with-results
```

That writes `2027 Spring import.xlsx` with the results grid (byes pre-filled, dropdowns, W/L totals), the Schedule tab and the Teams tab. In Google Sheets: File → Import → Upload → **Insert new sheet(s)**. Then add the row it prints to the top of the Seasons tab. Team-name typos in the PDFs are matched to the closest name automatically, and the script warns about anything it can't match.

## Configuration

`SHEET_ID` near the top of the script in `index.html`.

## Standings rules

Sorted by win percentage, then wins, then fewest losses. GB = games behind the leader. Teams with identical records share a rank.

That's it.
