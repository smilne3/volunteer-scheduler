# Volunteer Scheduler: Build Plan

The tool drafts each week's volunteer shift calendar from `signups.xlsx`. A person reviews the draft, and the calendar file only gets written after that review. The tool never contacts volunteers. Telling people their shifts stays with the coordinator.

---

## 1. Locked decisions

| # | Decision | Why |
|---|----------|-----|
| D1 | **Runs on this laptop only.** It's a Python command-line tool. There's no server, website or cloud service. | Volunteer contact details stay on the laptop. |
| D2 | **Reads `signups.xlsx` and never writes to it.** It reads the `Form Responses 1` sheet (sign-ups) and the `Shifts` sheet (shift definitions). | The spreadsheet stays the coordinator's file. Only people change it. |
| D3 | **Makes two things per week:** a one-page **review page** (`review.html`, opens in a browser and prints on one sheet) and a **calendar file** (`calendar.ics`) to import into Google Calendar. | These are the outputs you asked for. |
| D4 | **The calendar file is only written after someone approves the week.** `draft` makes the review page plus an editable assignments list. `approve` re-checks every rule, then writes `calendar.ics`. | "A person checks it before anyone is told" is enforced by the tool, not just by habit. |
| D5 | **Never emails, texts or contacts anyone.** The code has no email, SMS or network code. The calendar file has no attendees, organizer or email addresses, so importing it can't send Google invites. A test fails the build if any of these show up. | You said this is non-negotiable, so it's guarded in code and by tests. |
| D6 | **Rules come in a strict order** (see section 3). Rules about people (availability, weekly limit) are never broken. If a shift can't be fully staffed, the slot is left **empty and flagged** rather than breaking someone's limit. | "Never schedule outside availability or over limit" has to win over "keep every shift staffed" when the two conflict. |
| D7 | **Free-text availability is never trusted automatically.** The tool suggests how to read each free-text answer. The coordinator confirms or corrects the reading once, in `availability_review.csv`. Until it's confirmed, that person isn't scheduled, and the review page says so. | Misreading "Saturdays but not the 14th" would break D6. A one-time check per answer is cheap. |
| D8 | **One week per run, Monday to Sunday,** with real dates. By default the tool drafts next week. | Answers like "not the 14th" and "not Nov 26" only make sense with real dates. |
| D9 | **Fairness is measured across weeks, not just within one week.** Approved weeks are saved, and the scheduler favors people who've had fewer recent shifts. | There are 13 slots a week and 30 volunteers, so more than half go unscheduled in any given week. Fairness mostly means taking turns. |
| D10 | **The scheduler is a small optimization model** (Python + PuLP, which bundles a free solver). A separate checker re-verifies every rule on the result. | A simple "pick the first available person" approach can paint itself into a corner, for example by using the only experienced person on a shift that didn't need one. The checker means a solver bug can't slip past. |
| D11 | **Same input, same draft.** Ties are broken in a fixed order, so running it twice gives the same calendar. | Makes review and debugging predictable. |
| D12 | **Python 3.9** (already on this Mac, macOS 12). The virtual environment lives **outside iCloud** at `~/.venvs/volunteer-scheduler`. | Putting a venv in iCloud syncs thousands of small files and can break it. |

### Out of scope
- Sending any message, invite or reminder (D5)
- Editing the Google Form or the Google Sheet
- Syncing directly with Google Calendar through its API. You import the file by hand.
- Multiple coordinators editing at the same time

---

## 2. Facts from the current data

These come from the fake `signups.xlsx`. Real data should look similar.

- 5 shifts need **13 people a week** in total. 30 volunteers together offered up to **52 shifts a week**, so there's plenty of supply overall. Fairness and turn-taking are the main issues, not shortages.
- Thursday tutoring is the tightest shift. Only 6 people chose it with clean checkbox answers, and 3 of them are experienced.
- 11 of 30 availability answers are free text. On the first run, all 11 people show up as needing review.
- **The "needs experienced" values in the Shifts sheet are placeholders.** The coordinator needs to set them before real use.

---

## 3. Scheduling rules, in priority order

**Hard rules.** The tool never breaks these, and the checker rejects any calendar that does:
1. A person is only placed on a shift they're available for, on that date. This includes confirmed exceptions like "not Nov 14."
2. A person never gets more shifts than their weekly limit.
3. A person is never on two shifts that overlap in time.
4. A shift never gets more people than it needs.
5. Shifts on closed dates (set in `settings.json`, for example a holiday) aren't scheduled.

**Goals.** Within the hard rules, the scheduler meets these in order. Each one is fully settled before the next is considered:

1. **Experienced cover.** Every shift that needs an experienced person gets one.
2. **Coverage.** Fill as many slots as possible.
3. **Fair counts.** Nobody gets a second shift this week while someone available is still at zero. People who've had fewer shifts recently go first (from Phase 7 on).
4. **Preferences.** Put each person on shifts they marked as preferred whenever possible.
5. **Tie-break.** A fixed order seeded by the week's date, so it rotates from week to week but repeats if you rerun the same week.

**Preferences decide *which* shift someone gets. Fairness decides *how many*.** If you'd rather have preferences beat fair counts, swap goals 3 and 4. It's one setting.

"Experienced" means the person answered **Yes** to "Have you volunteered with us before?" The coordinator can mark more people as experienced in `settings.json`.

---

## 4. How it will be used (finished tool)

```
cd ~/volunteer-scheduler
python -m scheduler draft --week 2026-11-09     # Monday of the week; default = next week
#  → opens weeks/2026-11-09/review.html
#  coordinator reads it; if needed, edits weeks/2026-11-09/assignments.csv and runs draft --recheck
python -m scheduler approve --week 2026-11-09
#  → re-checks every rule, writes weeks/2026-11-09/calendar.ics, saves the week to history
#  coordinator imports calendar.ics into Google Calendar and tells volunteers themselves
```

### Folder layout

```
volunteer-scheduler/               (in iCloud Drive)
  signups.xlsx                     input, read only
  settings.json                    timezone, closed dates, extra experienced people, rule order
                                   (local only, not in git: it can name volunteers)
  settings.example.json            defaults, committed
  availability_review.csv          coordinator's confirmed readings of free-text answers
  docs/BUILD_PLAN.md
  scheduler/                       the code
  tests/
  weeks/2026-11-09/
    review.html                    one-page check
    assignments.csv                the draft; editable
    calendar.ics                   only after approve
    APPROVED                       marker with time and file fingerprint
```

---

## 5. Phases

Each phase ends with something you can run and check. Don't start the next phase until the current phase's "Done when" list passes.

### Phase 0: Setup
**Builds:** the folder layout, venv at `~/.venvs/volunteer-scheduler`, installed `openpyxl`, `pulp` and `pytest`, an empty `scheduler/` package, a `settings.example.json` with defaults (timezone from the laptop, no closed dates) copied to a local `settings.json`, and `.gitignore`. It also adds the D5 guard test early: it fails if any code imports email, SMS or network modules.
**Result (2026-10-22):** done. PuLP 3.3.1's bundled solver works on macOS 12.7.6 (Intel), so the OR-Tools fallback isn't needed.
**Done when:**
- `python -m scheduler --help` runs.
- A 5-line PuLP test problem solves on this Mac. If PuLP's bundled solver won't run on macOS 12, switch to OR-Tools now, before anything depends on it.
- `pytest` runs (with zero tests).

### Phase 1: Read and understand the spreadsheet
**Builds:** `python -m scheduler check-input`. It loads both sheets and turns each shift into a short ID made from its day and start time (`SAT-0900`, `SAT-1200`, `TUE-1500`, `WED-1700`, `THU-1500`). It reads clean checkbox answers into those IDs. Free-text answers are set aside and labeled "needs reading." It also handles duplicate sign-ups (same email: the newest response wins, and the older one is reported). It prints a table of what it understood for each person.
**Clear errors for:** the file missing or not downloaded from iCloud yet, a renamed sheet or column, a shift name in an answer that's not in the Shifts sheet, and a missing or non-number weekly limit.
**Done when:** the output on the fake data shows 19 clean readings and 11 "needs reading," and tests cover each error message.
**Result (2026-10-22):** done. Two details settled while building:
- **What stops the run vs. what doesn't.** File-level problems stop the run: missing file, missing sheet or column, or a bad Shifts sheet (every bad row is listed at once). A problem in one person's row, like a blank or non-number weekly limit or a missing email, only blocks that person and is listed under PROBLEMS.
- **Shift names not in the Shifts sheet.** If 2 or more responses contain the same shift-like name (a day plus a time range) that isn't in the Shifts sheet, it must be a form option missing from the sheet, so the run stops. If only one person typed something shift-like, it's treated as free text and noted.
- **Test data.** Tests use a committed copy of the fake data at `tests/fixtures/signups_fake.xlsx`, because the real `signups.xlsx` is gitignored.

### Phase 2: Free-text availability review
**Builds:** suggested readings for free-text answers, and the `availability_review.csv` loop.
- A rule-based reader handles common patterns: day names, "mornings/afternoons/evenings," "after 4," "not the 14th," "no weekends," "only," "flexible," and program names ("phone bank," "tutoring"). Its output is only a **suggestion**.
- Each free-text answer gets a row in `availability_review.csv` with: email, response timestamp, original answer, suggested reading, confirmed reading, and status.
- The confirmed reading uses a small fixed format: `SAT-0900, SAT-1200 except 2026-11-14` or `WED-1700 only 2026-11-11, 2026-11-25`.
- Only rows marked `confirmed` are used. If someone sends a new form response, their old confirmation stops applying and the answer comes up for review again.
- Free-text *preferences* ("Mornings if possible," "tutoring!!") get the same suggestion, but they don't need confirming. A misread preference can't break a rule, and the review page shows how each one was read.

**Done when:** each of the 11 fake answers gets a sensible suggestion. "Any weekday after 4" reads as phone bank only (tutoring starts at 3), and "Saturdays but not the 14th" keeps both Saturday shifts except Nov 14. An unconfirmed person is never available. Tests cover each pattern.
**Result (2026-10-22):** done. All 11 fake answers get the expected suggestion. Details settled while building:
- **Suggestions are conservative.** Anything uncertain ("maybe", "if", "every other week") is left out, with a note. For "every other week," the note offers both possible sets of dates ready to paste. Accepting a suggestion can never add availability the person didn't clearly give.
- **Confirming is one action.** A non-blank `confirmed_reading` means confirmed. The tool writes the `status` column (`to review` / `confirmed` / `error: …`). A reading with a mistake, like a Friday date on a Thursday shift, keeps the person off the schedule and says why.
- **Groups.** Readings can have groups separated by `;`, because "except"/"only" dates sometimes apply to just one shift (for example, Saturdays every week plus phone bank every other week).
- **Matching survives Excel.** Rows are matched by email plus the answer's letters and digits, not by timestamp. Excel rewrites dates, and can change the file's encoding, when it saves a CSV. So "a new response stops the old confirmation" means a new response with a *different* answer. The same answer resubmitted keeps its confirmation.
- **`check-input` maintains the review file.** It writes the file only when something changed, and skips writing (with a warning) if Excel has it open.
- **Preferences** are read automatically and always limited to the person's confirmed availability.

### Phase 3: Core scheduler plus independent checker
**Builds:** `python -m scheduler draft --week …`, which prints the schedule as plain text for now.
- The model only creates a choice for a (person, shift) pair if that person is available that date. That makes hard rule 1 impossible to break by construction. Rules 2 to 5 are constraints.
- Goals 1 and 2 (experienced cover, coverage). The order is enforced by solving in stages.
- **The checker** is separate code that takes any assignment list and reports every broken hard rule and every unmet goal. It's used on drafts here and on edited drafts in Phase 6.

**Done when:** these hand-built test cases pass:
- More people needed than are available → the slot is left empty and flagged, and nobody goes over their limit.
- The "experienced trap": the only experienced person is available for two shifts, and only one of them needs experience → they're put on the one that needs it.
- The Nov 14 exception is respected.
- A closed date has no shifts.
- The checker catches each type of broken rule when given a deliberately bad assignment list.

**Result (2026-10-22):** done. The fake week of Nov 9 is fully staffed with experienced cover everywhere and no rules broken. Riley still gets 3 shifts while 8 ready people get none, which is expected until Phase 4 adds fair counts. Details settled while building:
- **Settings are loaded and validated.** Unknown keys (typos), bad dates, a bad timezone and quoted true/false are all explained. If `settings.json` is missing, defaults are used and the report says so.
- **`allow_back_to_back_shifts` is a hard rule.** When it's off, the checker treats touching shifts on the same day (9–12 and 12–3) like overlapping ones.
- **The checker shares no rule code with the solver,** so a solver bug can't slip past it. It also catches problems that can only come from hand edits (Phase 6): unknown person or shift, wrong week, wrong weekday, duplicate rows.
- **A tie-break seeded by the week's date is already in place,** so drafts are repeatable now. Phase 4 adds fairness and preferences before it.
- **Extra tests beyond the plan:** 40 random scenarios where solver output must pass the checker, and 12 tiny random cases where the solver must match a brute-force search of every possible schedule.

### Phase 4: Preferences and fairness within a week
**Builds:** goals 3 to 5, plus a plain-English **reason** for every gap. For example: "TUE-1500 is 1 short: 3 people are available. Casey is at their weekly limit, and Harper's answer isn't confirmed yet."
**Done when:**
- Tests show nobody gets 2 shifts while an available person has 0.
- Preferred shifts are used when a choice exists.
- Running twice gives the same draft.
- Changing the week date changes the tie-break order.

**Result (2026-10-22):** done. The fake week of Nov 9 now gives 13 different people one shift each, every one of them on a shift they preferred, with no rules broken. Details settled while building:
- **"Fair" is measured as the sum of each person's shift count squared.** A k-th shift costs 2k−1, so moving a shift from someone with 2 to someone with 0 always scores better, and 2+2 beats 3+1. Tests check directly that no shift could be moved from a person with 2+ shifts to an available person with 0 without breaking a rule or losing experienced cover. That's checked on four fake weeks and 40 random scenarios.
- **Preferences count preferred shifts given,** and they're always limited to confirmed availability. They never cost coverage or experienced cover, because those stages are locked in first.
- **Gap reasons name each available person and why they weren't used** (weekly limit, overlap, back-to-back off). They also name people who came close: a date exception, an answer not yet confirmed whose *suggested* reading covers the shift, or a sign-up with a problem. A test confirms every unmet goal the checker finds gets a reason.

### Phase 5: The one-page review page
**Builds:** `weeks/<week>/review.html`, which opens automatically, plus `assignments.csv`. The page has a large **DRAFT, NOT APPROVED** banner and is laid out to print on one page. Contents, top to bottom:
1. **Problems first:** empty slots with reasons, missing experienced cover, unconfirmed free-text answers (and who was left out because of them), and duplicate sign-ups.
2. **The week:** each shift in date order with names, filled/needed, ★ for experienced and ♥ for a preferred shift.
3. **Fairness:** who's on 2 or more shifts, and available people who got nothing (with weeks since their last shift, once Phase 7 exists).
4. **Contact list** for scheduled people only, so the coordinator can tell them.

**Done when:** the page fits on one printed page for the fake data, all four sections show, and a draft with an empty slot shows it in red at the top.
**Result (2026-10-22):** done. Details settled while building:
- **Verified on paper, not by eye.** A test prints the page to PDF with headless Chrome and counts pages. It checks the fake week and a heavier week (a short shift, a sign-up problem, a duplicate response, 18 people scheduled). Both fit on one US Letter page. The test is skipped on machines without Chrome.
- **Escaping.** Everything from the form (names, phones, answers) is HTML-escaped, so a name containing HTML can't break the page or run code.
- **Hand edits are protected.** If a week's `assignments.csv` differs from a fresh draft, drafting again stops and asks for `--replace`, which keeps the old file as `assignments-before-<time>.csv`. An approved week (Phase 6's `APPROVED` marker) is never redrafted.
- **`assignments.csv` has a blank row for each open spot,** so filling a gap by hand is just typing a name and email.
- **Gap reasons are grouped** ("Answers not confirmed yet that may include it: Harper Demo, Morgan Pretend, Xan Exampleton") instead of one sentence per person.
- **Works on screen too:** light and dark mode, narrow screens. The banner stays dark red with white text in both modes.

### Phase 6: Edit, re-check, approve, calendar file
**Builds:**
- `draft --recheck` reads a hand-edited `assignments.csv`, runs the checker and refreshes the review page.
- `approve` refuses to run if any hard rule is broken. If there are empty slots, it asks for a typed "yes."
- Once approved, it writes `calendar.ics`: one event per shift, titled for example "Food Pantry (AM): Alex, Indy, Yael," with the names in the description. Times are stored in UTC, converted from the timezone in `settings.json`. Each event gets a stable ID made from the week and shift. There are **no ATTENDEE, ORGANIZER or email fields**.
- The `APPROVED` marker records the time and a fingerprint of `assignments.csv`. If the file changes later, the week has to be approved again.

**Done when:**
- Approving a broken edit is refused.
- The `.ics` file imports cleanly into a **test** Google Calendar with correct times.
- A test confirms the file has no `ATTENDEE`, `ORGANIZER` or `mailto:`.
- A test scans the code and fails if it finds `smtplib`, `requests`, `urllib`, `socket` or any SMS library.

**Result (2026-10-22):** done, except for one check that needs a person: importing the `.ics` into a real **test** Google Calendar. Instead, an independent iCalendar library (`icalendar` 6.3.2, used only for this one-off check and not added to the project) parsed the file with no errors, and all five events had the right local times. Details settled while building:
- **Reading edits is forgiving but strict where it matters.** A name without an email is matched if it fits exactly one volunteer. Excel-style dates (`11/10/26`), a shift name instead of its ID, and Windows-encoded saves are all accepted. Anything that can't be read is treated as a broken rule, so approval is refused.
- **The typed "yes" comes from the keyboard.** There's no `--yes` flag, so it can't become a habit. If there's no answer (e.g. run from a script), the week isn't approved.
- **The `APPROVED` marker is written last,** after `calendar.ics`, so an interrupted approval never looks complete. It stores the time, a SHA-256 fingerprint of `assignments.csv`, and how many times the week has been approved.
- **Calendar events:** the UID is stable per week and shift, and SEQUENCE counts approvals. Titles look like "Food Pantry (AM): Alex, Indy, Uma"; full names are used when first names clash, and open spots are shown as "(1 open)". Times are in UTC converted from `settings.timezone`, tested across the Nov 1 daylight-saving change. Lines are folded at 75 octets without splitting characters, with CRLF line endings.
- **Gap reasons in hand-edited drafts** list free people as "Available and free: …", since leaving them off is the coordinator's choice.
- **The commands moved to `scheduler/commands.py`;** `__main__.py` only parses arguments.

**Import note for the coordinator:** import into a dedicated calendar, for example "Volunteer Shifts." Google Calendar may create duplicates if you import a corrected file for a week you've already imported. To fix a week, delete that week's events first, then import again.

### Phase 7: Fairness across weeks
**Builds:** history read from approved weeks only, and goal 3 extended to prefer people with fewer shifts in the last 4 weeks (the number of weeks is a setting). The review page shows "weeks since last shift." Optionally, people who've completed an approved shift count as experienced from then on (off by default).
**Done when:** a 4-week test run on the fake data shows unscheduled people moving up each week, and nobody available goes 3 or more weeks without a shift while others get one every week.

### Phase 8: Polish for the coordinator
**Builds:** a short `README.md` for the coordinator (weekly steps, how to confirm free-text readings, how to import) and a double-clickable `Draft next week.command` file so they don't need to type commands. It also handles iCloud quirks: if `signups.xlsx` isn't downloaded yet, it says so. Excel's `~$` lock files are ignored.
**Done when:** someone who hasn't seen the code can do a full week from the README alone.

---

## 6. Open questions

These have defaults so building can start now. Each one is a single setting to change later.

1. **Which shifts need an experienced person?** Currently placeholders: Saturday pantry (both) and phone bank = Yes, tutoring = No.
2. **Can one person work both Saturday shifts (9 to 3) if their limit allows?** Default: yes. The fairness goal already makes it rare.
3. **Fair counts before preferences (section 3)?** Default: yes.
