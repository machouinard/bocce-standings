# East Portal Bocce Standings

A single-page standings site for the East Portal Bocce Club Friday night league.

- **Results live in a Google Sheet** (one tab per season, plus a `Seasons` tab). The page reads it in the browser every time it loads, so updating the sheet updates the site — no rebuild or deploy.
- **Hosting:** GitHub Pages serves `index.html` from the `main` branch.

## Sheet format

**Season tab** (e.g. `2026 Fall`): column A is the team name; row 1 has a date (`m/d`) above each game column, with each Friday's date appearing twice (game 1 and game 2). Cells are `W`, `L`, `F` (forfeit, counts as a loss), `BYE`, or blank. Blank cells on a date that has passed are shown as **rematches owed**. Columns without a date header (like the W/L totals) are ignored.

**Seasons tab:** `Tab | Season | Year | Note`. The top row is the season the site shows by default; other rows appear in the season picker.

The sheet must be shared as **Anyone with the link → Viewer**.

## Configuration

`SHEET_ID` near the top of the script in `index.html`.

## Standings rules

Sorted by win percentage, then wins, then fewest losses. GB = games behind the leader. Teams with identical records share a rank.
