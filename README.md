# Volunteer Scheduler

Drafts a weekly volunteer shift calendar from `signups.xlsx` for a person to review and approve. It never emails, texts or contacts anyone. Plan and decisions: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

**Status:** Phase 0 (setup) only. The tool doesn't schedule anything yet.

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
