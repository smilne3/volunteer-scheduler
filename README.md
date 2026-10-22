# Volunteer Scheduler

Drafts a weekly volunteer shift calendar from `signups.xlsx` for a person to review and approve. It never emails, texts or contacts anyone. Plan and decisions: [docs/BUILD_PLAN.md](docs/BUILD_PLAN.md).

**Status:** all phases (0–8) done. The full weekly routine works (check the sign-ups, draft, review, edit, approve, import into Google Calendar), shifts rotate fairly from week to week, and the coordinator can do all of it by double-clicking.

**For the coordinator:** double-click **Volunteer Scheduler.command** in the data folder and follow the numbered menu. The plain-language guide **How to use the scheduler.html** is in the same folder. Everything below is for whoever sets up or maintains the tool.

**Two folders:**
- **Code:** this repo, at `~/code/volunteer-scheduler`. It's not synced; GitHub is its backup.
- **Data:** `signups.xlsx`, `settings.json`, `availability_review.csv`, the `weeks/` folders and your screenshots. These live in the iCloud folder `~/volunteer-scheduler`.

The tool reads data from `~/volunteer-scheduler` unless you set `VOLUNTEER_SCHEDULER_DATA` to another folder, or pass `--file`. Keep the code out of iCloud: iCloud and git don't mix safely.

## Each week (command-line version)

The menu does all of this for you: `python -m scheduler menu`, or double-click **Volunteer Scheduler.command**. If you'd rather type commands, run these in the code folder after activating the environment (see [Setup](#setup-once-per-laptop)). Files mentioned below, like `weeks/…`, are in the data folder `~/volunteer-scheduler`.

**1. Check the sign-ups.**
```
python -m scheduler check-input
```
This shows what the tool understood from `signups.xlsx`. If anyone typed their availability instead of ticking boxes, confirm it first (see [Confirm free-text availability](#confirm-free-text-availability)). Until it's confirmed, they won't be scheduled.

**2. Draft the week.**
```
python -m scheduler draft                     # next week
python -m scheduler draft --week 2026-11-09   # the week starting Monday Nov 9
```
This writes `weeks/<Monday>/review.html` and opens it in your browser, and writes `weeks/<Monday>/assignments.csv`. The review page is marked **DRAFT, NOT APPROVED**, prints on one sheet, and has four sections: what needs your attention (short shifts in red, with reasons), the week (★ experienced, ♥ a shift they preferred), fairness, and a contact list for scheduled people only.

**3. Change anything you want to.** Edit `assignments.csv` (one row per person per shift, plus a blank row for each open spot), then re-check it:
```
python -m scheduler draft --week 2026-11-09 --recheck
```
This checks your edits against every rule and refreshes the review page. You can type a volunteer's name without their email if the name matches one person.

**4. Approve.**
```
python -m scheduler approve --week 2026-11-09
```
If any rule is broken, approval is refused and the problem is listed. If a shift is short or missing an experienced person, you'll be asked to type `yes` to approve anyway. Approving writes `weeks/<Monday>/calendar.ics` and turns the review page's banner green.

**5. Import into Google Calendar** (on a computer):
1. Open Google Calendar, click the gear, then **Settings**.
2. Choose **Import & export**, then **Import**.
3. Select `calendar.ics`, choose your **volunteer-shifts calendar** (not your personal one), and click **Import**.

Each shift is one event, like "Food Pantry (AM): Alex, Indy, Uma", with full names in the description. The file has no guest list or email addresses, so importing it can't send invitations.

If you already imported a week and then changed it, delete that week's shift events in Google Calendar first, then import the new file, so nothing is duplicated.

**6. Tell volunteers yourself.** The tool never contacts anyone. The contact list on the review page has the phone numbers and emails you need.

**If you change a week after approving it,** the review page shows **CHANGED SINCE APPROVAL**. Run `draft --recheck` and `approve` again for a new `calendar.ics`.

## How it chooses

In this order:
1. Every shift that needs an experienced person gets one.
2. As many slots as possible are filled.
3. **Fair counts:** nobody gets a second shift while someone available has none. After that, shifts go to people with fewer shifts in the last 4 approved weeks (`fairness_lookback_weeks`), so people take turns from week to week. The review page shows when each waiting person last had a shift.
4. **Preferences:** people get shifts they marked as preferred whenever possible. Set `fair_counts_before_preferences` to `false` to swap steps 3 and 4.
5. Remaining ties are broken in a fixed order that changes each week, so the same week always drafts the same way.

These rules are never broken: nobody is scheduled outside their availability or over their weekly limit, nobody is on overlapping shifts, no shift gets more people than it needs, and nothing is scheduled on closed dates. If a shift can't be fully staffed, it's left short and the review page says why. For example: "THU-1500 (Nov 26) is 2 short: 6 people are available. Answers not confirmed yet that may include it: Harper Demo, Morgan Pretend."

## Confirm free-text availability

When someone types their availability instead of ticking boxes ("Saturdays but not the 14th"), the tool won't schedule them until a person confirms what it means.

1. Run `python -m scheduler check-input`. It creates or updates `availability_review.csv` next to `signups.xlsx`, with one row per free-text answer and a **suggested_reading**.
2. Open the file. For each row, copy the suggested reading into **confirmed_reading**, or write your own. Leave it blank if you're not sure yet.
3. Save it as CSV and run `check-input` again. The **status** column shows `confirmed`, `to review`, or an error explaining what to fix.

Suggestions leave out anything uncertain ("maybe Sat", "every other week"), and the notes column says why. Accepting a suggestion never adds availability the person didn't clearly give.

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

Requires Python 3.9 or newer. Keep both the code and the virtual environment outside iCloud.

```
git clone https://github.com/smilne3/volunteer-scheduler.git ~/code/volunteer-scheduler
python3 -m venv ~/.venvs/volunteer-scheduler
source ~/.venvs/volunteer-scheduler/bin/activate
pip install -r ~/code/volunteer-scheduler/requirements.txt
mkdir -p ~/volunteer-scheduler                      # the data folder (can be a link into iCloud Drive)
cp ~/code/volunteer-scheduler/settings.example.json ~/volunteer-scheduler/settings.json   # then edit it
cd ~/code/volunteer-scheduler && python -m scheduler install-launchers
```

`install-launchers` writes three files into the data folder, set up for this laptop:
- **Volunteer Scheduler.command:** double-click for the menu.
- **Draft next week.command:** double-click to draft next week in one step.
- **How to use the scheduler.html:** the coordinator's guide.

Run it again if the code or the environment moves. It never overwrites files it didn't make. The first time you double-click a `.command` file, macOS may ask you to confirm: right-click it, choose **Open**, then **Open** again.

Each session:

```
cd ~/code/volunteer-scheduler
source ~/.venvs/volunteer-scheduler/bin/activate
```

Run the tests with `pytest`. One test prints the review page to PDF with Google Chrome to check it fits on one page, and it's skipped if Chrome isn't installed.

## Settings

`settings.json` is local only and not in git, because it can name volunteers. `settings.example.json` shows the defaults.

| Setting | Default | Meaning |
|---|---|---|
| `timezone` | `America/New_York` | Timezone the shift times are in. The calendar file uses it. |
| `closed_dates` | `[]` | Dates with no shifts, e.g. `["2026-11-26"]` |
| `extra_experienced_emails` | `[]` | People to count as experienced even if their form says No |
| `fair_counts_before_preferences` | `true` | Spread shift counts fairly before honoring preferences |
| `allow_back_to_back_shifts` | `true` | Whether one person can work both Saturday shifts |
| `fairness_lookback_weeks` | `4` | How many past approved weeks count toward fairness. `0` turns it off. |
| `count_approved_shifts_as_experience` | `false` | Whether working an approved shift (once its date has passed) makes someone count as experienced |

## Private data stays out of git

`signups.xlsx`, `settings.json`, `availability_review.csv` and the `weeks/` folder hold volunteers' details. They live in the data folder, not this repo, and `.gitignore` blocks them too in case one is copied in by mistake. This repo is public, so never force-add them. Tests use only the made-up data in `tests/fixtures`.
