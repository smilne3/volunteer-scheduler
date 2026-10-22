# Volunteer Scheduler

Drafts a weekly volunteer shift calendar from `signups.xlsx` for a person to review and approve. It never emails, texts or contacts anyone. Plan and decisions: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

**Status:** Phases 0–5 done. The tool reads `signups.xlsx`, uses confirmed free-text readings, drafts a week that keeps every rule, spreads shifts fairly, honors preferences, explains any gap, and produces a one-page review page. Approving the week and the calendar file come in Phase 6.

## Draft a week

```
python -m scheduler draft                     # next week
python -m scheduler draft --week 2026-11-09   # the week starting Monday Nov 9
```

This checks every rule (nobody outside their availability or over their weekly limit, no overlapping shifts, no shift overfilled, nothing on closed dates), then writes two files to `weeks/<Monday>/` and opens the first in your browser:

- **`review.html`**: the one-page review page. It shows what needs your attention, the week (★ experienced, ♥ a shift they preferred, open spots in red), fairness, and a contact list for scheduled people only. It's marked DRAFT, NOT APPROVED, and prints on one sheet.
- **`assignments.csv`**: the same draft as a spreadsheet you can edit, with one row per person per shift and a blank row for each open spot.

Nothing is sent to anyone. Use `--no-open` to skip opening the browser. If you've edited a week's `assignments.csv`, drafting that week again won't overwrite it unless you add `--replace`, and even then the old file is kept as `assignments-before-<time>.csv`.

**How it chooses**, in this order:
1. Every shift that needs an experienced person gets one.
2. As many slots as possible are filled.
3. **Fair counts:** nobody gets a second shift while someone available has none.
4. **Preferences:** people get shifts they marked as preferred whenever possible. Set `fair_counts_before_preferences` to `false` to swap steps 3 and 4.
5. Remaining ties are broken in a fixed order that changes each week, so the same week always drafts the same way.

If a shift is short or has no experienced person, the draft says why, for example: "THU-1500 (Nov 26) is 2 short: 6 people are available. Casey is at their weekly limit. Harper's answer may include it but isn't confirmed yet." The FAIRNESS lines list who has more than one shift and who was available but not scheduled.

## Check the spreadsheet

```
python -m scheduler check-input                 # reads signups.xlsx in this folder
python -m scheduler check-input --file other.xlsx
```

This shows each volunteer's shifts (✓ available, ♥ preferred), which free-text answers still need reading, problems that block someone from being scheduled (for example, a blank weekly limit), duplicate responses, and how many ready volunteers each shift has. It never changes the spreadsheet.

## Confirm free-text availability

When someone types their availability instead of ticking boxes ("Saturdays but not the 14th"), the tool won't schedule them until a person confirms what it means.

1. Run `python -m scheduler check-input`. It creates or updates `availability_review.csv` next to `signups.xlsx`, with one row per free-text answer and a **suggested_reading**.
2. Open the file. For each row, copy the suggested reading into **confirmed_reading**, or write your own. Leave it blank if you're not sure yet.
3. Save it as CSV and run `check-input` again. The **status** column shows `confirmed`, `to review`, or an error explaining what to fix.

Suggestions leave out anything uncertain ("maybe Sat", "every other week") and the notes column says why, so accepting a suggestion never adds availability the person didn't clearly give.

**How to write a reading:**

| Reading | Means |
|---|---|
| `SAT-0900, SAT-1200` | Both Saturday shifts, every week |
| `SAT-0900, SAT-1200 except 2026-11-14` | Every Saturday except Nov 14 |
| `WED-1700 only 2026-11-11, 2026-11-25` | Phone bank on those dates only |
| `SAT-0900; WED-1700 only 2026-11-11` | Saturday mornings every week, plus phone bank on Nov 11 only. `;` separates groups, and `except`/`only` apply to their own group. |
| `none` | Confirmed: no shifts |

Shift IDs are the day plus start time, listed at the top of the `check-input` report. A date has to fall on the same day as the shift it's attached to. The tool catches typos like a Friday date on a Thursday shift.

**When a confirmation stops applying:** if someone sends a new response with *different* availability, their old confirmation no longer applies, and the answer comes back for review. The report notes this once. The same answer sent again keeps its confirmation.

Free-text **preferences** ("Mornings if possible") are read automatically and never need confirming. They only affect which shift someone gets, never whether they're available.

## Setup (once per laptop)

Requires Python 3.9 or newer. The virtual environment lives outside the project folder, because the folder syncs to iCloud.

```
python3 -m venv ~/.venvs/volunteer-scheduler
source ~/.venvs/volunteer-scheduler/bin/activate
pip install -r requirements.txt
cp settings.example.json settings.json   # then edit settings.json
```

## Each session

```
cd ~/volunteer-scheduler
source ~/.venvs/volunteer-scheduler/bin/activate
python -m scheduler --help
pytest
```

## Settings

`settings.json` is local only and not in git, because it can name volunteers. `settings.example.json` shows the defaults.

| Setting | Default | Meaning |
|---|---|---|
| `timezone` | `America/New_York` | Timezone the shift times are in |
| `closed_dates` | `[]` | Dates with no shifts, e.g. `["2026-11-26"]` |
| `extra_experienced_emails` | `[]` | People to count as experienced even if their form says No |
| `fair_counts_before_preferences` | `true` | Spread shift counts fairly before honoring preferences |
| `allow_back_to_back_shifts` | `true` | Whether one person can work both Saturday shifts |
| `fairness_lookback_weeks` | `4` | How many past approved weeks count toward fairness |
| `count_approved_shifts_as_experience` | `false` | Whether finishing an approved shift makes someone experienced |

## Private data stays out of git

`signups.xlsx`, `settings.json`, `availability_review.csv` and the `weeks/` folder hold volunteers' details and are in `.gitignore`. This repo is public, so never force-add them.
