# Volunteer Scheduler

Drafts a weekly volunteer shift calendar from `signups.xlsx` for a person to review and approve. It never emails, texts or contacts anyone. Plan and decisions: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

**Status:** Phases 0–3 done. The tool reads `signups.xlsx`, uses confirmed free-text readings, and drafts a week that keeps every rule. Fair spreading and preferences come in Phase 4, and the review page and calendar file in Phases 5–6.

## Draft a week

```
python -m scheduler draft                     # next week
python -m scheduler draft --week 2026-11-09   # the week starting Monday Nov 9
```

This prints who's on each shift (★ = experienced), then a check of every rule: nobody outside their availability or over their weekly limit, no overlapping shifts, no shift overfilled, nothing on closed dates. It also lists any shift that's short or missing an experienced person. Nothing is saved or sent.

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
