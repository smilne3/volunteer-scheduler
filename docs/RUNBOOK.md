# Volunteer Scheduler Runbook

This is for the volunteer coordinator who runs the schedule each week. You don't need to know anything about the code, and you'll never need to open it. Everything happens by double-clicking a file and reading a web page.

**What the scheduler does:** it reads the sign-up spreadsheet and drafts next week's shift schedule. It follows every person's availability and weekly limit, puts an experienced volunteer where one is needed, spreads shifts fairly, and gives people their preferred shifts when it can. You review the draft, change anything you like, and approve it. Approving makes a file you import into Google Calendar.

**What it never does:** it never emails, texts or invites anyone. Telling volunteers their shifts is always up to you.

**What you need:**
- The Mac where the scheduler is set up.
- The **scheduler folder** on that Mac, named `volunteer-scheduler`. It's in iCloud Drive.
- Access to the Google Sheet that collects the sign-up form's responses.
- Access to the shared volunteer-shifts calendar in Google Calendar.

**Contents**
- [The scheduler folder](#the-scheduler-folder)
- [Weekly review](#weekly-review)
- [When the sign-up form changes](#when-the-sign-up-form-changes)
- [Other changes](#other-changes)
- [When something goes wrong](#when-something-goes-wrong)
- [Keeping volunteers' details private](#keeping-volunteers-details-private)

---

## The scheduler folder

Everything you work with is in this one folder.

| File | What it's for |
|---|---|
| **Volunteer Scheduler.command** | Double-click to start. It opens a menu with every step below. |
| **Draft next week.command** | A shortcut that drafts next week in one double-click. |
| **How to use the scheduler.html** | A short version of this runbook. |
| **signups.xlsx** | The sign-up spreadsheet. You replace it each week. |
| **availability_review.csv** | Where you confirm availability that people typed instead of ticking boxes. |
| **weeks** folder | One folder per week, such as `2026-11-09` for the week starting Monday, November 9. |
| **settings.json** | Closed dates and a few other settings. See [Other changes](#other-changes). |

Each week's folder holds:
- **review.html:** the one-page review. Open it in any browser, and print it if you like.
- **assignments.csv:** who's on each shift, as a spreadsheet you can edit.
- **calendar.ics:** the file for Google Calendar. It only appears once you approve the week.

---

## Weekly review

Allow 15 to 30 minutes. Start a few days before the week begins, so you have time to contact volunteers.

**The short version:**
1. [Download the latest sign-ups.](#1-download-the-latest-sign-ups)
2. [Open the scheduler.](#2-open-the-scheduler)
3. [Check the sign-ups and confirm typed availability.](#3-check-the-sign-ups)
4. [Draft the week.](#4-draft-the-week)
5. [Review the draft.](#5-review-the-draft)
6. [Make changes, if you want to.](#6-make-changes-optional)
7. [Approve the week.](#7-approve-the-week)
8. [Add it to Google Calendar.](#8-add-it-to-google-calendar)
9. [Tell the volunteers.](#9-tell-the-volunteers)

### 1. Download the latest sign-ups

1. Open the Google Sheet with the form responses.
2. Choose **File → Download → Microsoft Excel (.xlsx)**.
3. The file lands in your **Downloads** folder under the sheet's name. Move it into the scheduler folder and rename it to exactly `signups.xlsx`, replacing the old one.

The spreadsheet must have two tabs, **Form Responses 1** and **Shifts**. See [The two tabs](#the-two-tabs) if either is missing.

### 2. Open the scheduler

Double-click **Volunteer Scheduler.command** in the scheduler folder. A Terminal window opens with this menu:

```
  1  Check the sign-ups
  2  Draft a week
  3  Re-check a week after editing its assignments.csv
  4  Approve a week (makes the Google Calendar file)
  5  Open the data folder
  6  Open the how-to guide
  q  Quit
```

Type a number and press **Return**. When you're finished, type **q** and press **Return**, then close the window.

The first time, macOS may say the file can't be opened. If so, right-click it, choose **Open**, then **Open** again. You only need to do this once.

### 3. Check the sign-ups

Choose **1**. The scheduler shows what it understood from each sign-up and ends with a summary:

```
SUMMARY: 19 ready, 11 need reading, 0 with problems, 0 with no availability given.
```

- **Ready:** these people ticked boxes on the form, so the scheduler knows exactly when they're free.
- **Need reading:** these people typed their availability, for example "Saturdays but not the 14th". **They won't be scheduled until you confirm what they meant.** See below.
- **Problems:** something in their response can't be used, such as "two" typed where a number was expected. They won't be scheduled until it's fixed in the Google Sheet. The message says what's wrong.

#### Confirming typed availability

1. Choose **5** to open the scheduler folder, then open **availability_review.csv** in Numbers or Excel.
2. Each row is one person's typed answer. Read the **answer**, the **suggested_reading** and the **notes**.
3. If the suggestion is right, copy it into **confirmed_reading**. If not, write your own (see the examples below). If you're not sure, leave it blank. That person just won't be scheduled yet.
4. Save it as CSV. In Numbers, use **File → Export To → CSV**. In Excel, use **File → Save** and keep the CSV format.
5. Choose **1** again. The **status** column now says **confirmed** for each row you filled in, or explains what to fix.

The suggestions are deliberately cautious. Anything uncertain, like "maybe Saturdays" or "every other week", is left out, and the notes explain why. For "every other week", the notes offer both possible sets of dates, ready to copy.

**How to write a reading.** Each shift has a short ID made of its day and start time: `SAT-0900` is Saturday at 9:00 am, and `WED-1700` is Wednesday at 5:00 pm. Option 1 lists all the IDs at the top.

| Reading | Means |
|---|---|
| `SAT-0900, SAT-1200` | Both Saturday shifts, every week |
| `SAT-0900, SAT-1200 except 2026-11-14` | Every Saturday except November 14 |
| `WED-1700 only 2026-11-11, 2026-11-25` | The Wednesday phone bank on those two dates only |
| `SAT-0900; WED-1700 only 2026-11-11` | Saturday morning every week, plus the phone bank on November 11 only |
| `none` | Not available for any shift |

Dates are written year-month-day. A date must fall on the same day of the week as its shift. If you put a Friday date on a Thursday shift, the status column shows an error and that person isn't scheduled until you fix it.

A confirmation stays in place week after week. If the person sends a new response with different availability, it comes back for review.

### 4. Draft the week

Choose **2**, then press **Return** to draft next week. To draft a different week, type a date in it, like `11/16`. The review page opens in your browser.

If a draft for that week already exists, you're asked whether to replace it. Press **Return** to keep the existing draft, for example if you've edited it. Type **yes** to start fresh. The old draft is kept as a copy in the week's folder.

### 5. Review the draft

The review page fits on one printed page. Read it from top to bottom.

**The banner at the top** shows where this week stands:

| Banner | Meaning |
|---|---|
| Red: **DRAFT, NOT APPROVED** | Don't share it yet. |
| Green: **APPROVED** | The calendar file is ready to import. |
| Red: **CHANGED SINCE APPROVAL** | The week was edited after approval. Approve it again before sharing. |

**1. Needs your attention.** Deal with these first.
- **Red items** are shifts that are short of people or missing an experienced volunteer. Each one says why, for example: "THU-1500 (Nov 26) is 2 short: 6 people are available. Casey Placeholder is at their weekly limit. Answers not confirmed yet that may include it: Harper Demo, Morgan Pretend."
- **Amber items** are things to tidy up: typed availability that isn't confirmed, sign-up problems, people who sent the form twice (the newest response is used), and notes about settings.

What to do about a red item:

| The reason says | You can |
|---|---|
| Someone's answer isn't confirmed yet | Confirm it (step 3), then draft again |
| Someone is "Available and free" | Add them to the shift (step 6) |
| Everyone available is at their weekly limit | Ask a volunteer if they'll take one more, then add them (step 6) |
| Nobody is available | Approve anyway and recruit someone, or leave the gap |

**2. The week.** Each shift shows how many people it has against how many it needs, such as **2/3**, and who's on it:
- **★** means experienced.
- **♥** means it's a shift they asked for.
- Open spots show in red, for example **1 open**.

**3. Fairness.** This section shows:
- How many available volunteers got a shift this week.
- Anyone with more than one shift.
- Who was available but not scheduled, and when they last worked. The scheduler gives priority to people who've waited longest, so someone left out this week moves up next week.

**4. Contact list.** Phone and email for everyone on this week's schedule, so you can tell them. Nobody else's details are shown.

**The last line** says how the schedule was made. Until you approve it, it reads "Drafted with AI from the sign-up form. Not yet checked by staff." Once approved, it reads "Drafted with AI from the sign-up form and checked by staff."

### 6. Make changes (optional)

To swap someone, add someone or take someone off:

1. Choose **5** to open the scheduler folder, then open **weeks → (the week) → assignments.csv**.
2. Each row is one person on one shift. Rows with no name are open spots.
   - **To swap someone:** replace their name and email with the new person's.
   - **To fill an open spot:** type the person's name, and email if you have it, into a blank row.
   - **To take someone off:** delete their row.
   - A name on its own is fine if it matches exactly one volunteer.
3. Save it as CSV.
4. In the scheduler, choose **3** and press **Return** for the week you edited.

The review page refreshes and tells you if your change breaks a rule, for example if that person isn't available that day or is over their limit. Fix it in the file and choose **3** again.

### 7. Approve the week

Choose **4** and press **Return** for the week.

- **If a rule is broken,** it won't approve, and it tells you what to fix.
- **If a shift is short or missing an experienced person,** it lists the gaps and asks you to type **yes** to approve anyway. Anything else cancels.
- **When it's approved,** the banner turns green, the calendar file **calendar.ics** is created, and a Finder window opens with it selected.

### 8. Add it to Google Calendar

Do this on a computer. The Google Calendar phone app can't import files.

1. Open Google Calendar, click the **gear** icon, then **Settings**.
2. Choose **Import & export**, then **Import**.
3. Click **Select file from your computer** and choose the week's **calendar.ics**.
4. Under **Add to calendar**, pick the **volunteer-shifts calendar**, not your personal one.
5. Click **Import**.

Each shift becomes one event, such as "Food Pantry (AM): Alex, Indy, Uma", with full names in the description. The description ends with "Drafted with AI from the sign-up form and checked by staff." Nobody gets an invitation.

### 9. Tell the volunteers

Use the contact list on the review page. The scheduler hasn't contacted anyone.

### If plans change after approving

1. Edit that week's **assignments.csv** (step 6), then choose **3** to check it, then **4** to approve it again.
2. In Google Calendar, delete that week's shift events.
3. Import the new **calendar.ics**.

Deleting the old events first keeps them from showing twice.

---

## When the sign-up form changes

The scheduler reads the downloaded spreadsheet, and it depends on two things matching exactly:

1. **The form's question titles**, which become the column headings in the **Form Responses 1** tab.
2. **The shift choices on the form**, which must match the shift names in the **Shifts** tab.

Capital letters, the kind of dash, and extra spaces don't matter. Everything else must match.

After **any** change to the form, download the sheet again and choose **1, Check the sign-ups**. If something doesn't match, it stops with a message that says what it expected and what it found.

| Change | What to do |
|---|---|
| Add a shift | [Add it to the form and the Shifts tab](#adding-a-shift) |
| Change a shift's time or name | [Update the Shifts tab and old answers](#changing-a-shifts-time-or-name) |
| Stop running a shift | [Remove it from the form, the Shifts tab and old answers](#stopping-a-shift) |
| More or fewer people on a shift | [Change the Shifts tab only](#changing-how-many-people-a-shift-needs) |
| Reword a question | [Avoid it, or fix the heading](#rewording-a-question) |
| Add a new question | Nothing. Extra questions are ignored. |
| Start a new form or relink the sheet | [Check the tab name](#starting-a-new-form) |

### The two tabs

**Form Responses 1** is created by Google Forms. The scheduler needs these question titles, word for word:

| Question title | What the scheduler expects |
|---|---|
| Timestamp | Added by Google Forms automatically |
| Full name | Their name |
| Email address | Turn on **Collect email addresses** in the form's settings, or ask it as a question with this exact title |
| Which shifts are you available for? | Checkboxes, one per shift |
| Which shifts would you prefer? | The same checkboxes |
| What is the most shifts you'd like per week? | A number, ideally a dropdown from 1 to 5 |
| Have you volunteered with us before? | Yes or No |
| Phone number | Optional, shown on the contact list |

**Shifts** is a tab you add to the same spreadsheet yourself. It has one row per shift:

| Shift | Day | Time | People needed | Needs at least one experienced volunteer? |
|---|---|---|---|---|
| Saturday Food Pantry 9am–12pm | Saturday | 9:00 AM – 12:00 PM | 3 | Yes |
| Saturday Food Pantry 12pm–3pm | Saturday | 12:00 PM – 3:00 PM | 3 | 2 |
| Tuesday Tutoring 3pm–5pm | Tuesday | 3:00 PM – 5:00 PM | 2 | No |

- **Shift** must match the form's checkbox wording, and it can't contain a comma.
- **Time** is the start and end time, like `9:00 AM – 12:00 PM`.
- **The experienced column** takes **Yes** (one experienced person), **No**, or a number such as **2**. A number is useful for a shift people often drop, so there's a backup. It can't be more than "People needed".
- No two shifts can start on the same day at the same time.

### Adding a shift

1. Add the new choice to **both** checkbox questions on the form ("available for" and "prefer"), with identical wording.
2. Add a row to the **Shifts** tab with that exact wording, plus its day, time, people needed and experienced setting.
3. Download the sheet and choose **1** to check it.

If you add the choice to the form but forget the Shifts tab, the check stops with "These shift names appear in several form answers but aren't in the Shifts sheet". Add the row and check again.

### Changing a shift's time or name

People who already answered still have the **old** wording in their responses. So:

1. Change the choice on the form, in both checkbox questions.
2. Change the row in the **Shifts** tab to match.
3. In the **Form Responses 1** tab, use **Edit → Find and replace** to change the old wording to the new wording in the two shift columns.
4. If the start time or day changed, the shift's short ID changes too, for example from `SAT-0900` to `SAT-1000`. Choose **1**. Any confirmed reading in **availability_review.csv** that still uses the old ID shows an error. Update those to the new ID.
5. If you already drafted a future week, draft it again (step 4) and type **yes** to replace it.

### Stopping a shift

1. Remove the choice from both checkbox questions on the form.
2. Delete its row from the **Shifts** tab.
3. In **Form Responses 1**, use **Find and replace** to replace the old wording with nothing, in both shift columns. Leftover commas are fine.
4. Download the sheet and choose **1** to check it.

If you skip step 3, people who chose that shift either stop the check or turn into "need reading" until you confirm them by hand.

### Changing how many people a shift needs

Change **People needed** or the experienced column in the **Shifts** tab. The form doesn't change. The next draft uses the new numbers.

### Rewording a question

**Try not to.** The scheduler finds each question by its exact title. If you reword one, the check stops with "missing these column headings" and lists what it found.

If you must reword a question, either:
- change the column heading in **Form Responses 1** back to the original title each time you download, or
- ask the person who set up the scheduler to update it. It's a small change.

### Starting a new form

If you make a new form, or unlink and relink the form to the sheet, Google may name the tab **Form Responses 2**. Rename it to **Form Responses 1**, and add a **Shifts** tab to the new spreadsheet if it doesn't have one. Old confirmations in **availability_review.csv** carry over as long as people's emails and answers are the same.

---

## Other changes

These live in **settings.json** in the scheduler folder. It's a plain text file. Open it with **TextEdit**, keep the quotation marks and commas exactly as they are, and save.

Before typing in TextEdit, turn off **Edit → Substitutions → Smart Quotes**. Otherwise TextEdit may turn `"` into curly quotes, and the scheduler then reports that settings.json isn't valid.

**Closing for a day,** such as a holiday. Add the date, year-month-day, to `closed_dates`:

```
"closed_dates": ["2026-11-26"],
```

For more than one date: `["2026-11-26", "2026-12-24"]`. Shifts on those dates aren't scheduled, and the review page marks them as closed.

**Counting someone as experienced** when their form says No. Add their email to `extra_experienced_emails`:

```
"extra_experienced_emails": ["pat@example.com"],
```

If the scheduler reports a problem in settings.json after you edit it, the message names the setting and how to fix it. If in doubt, ask the person who set it up.

---

## When something goes wrong

| You see | What to do |
|---|---|
| "…isn't downloaded to this Mac yet" | In Finder, right-click the file and choose **Download Now**, then try again. |
| "…looks open in Excel" | Close the file in Excel or Numbers, then try again. |
| "Can't find …signups.xlsx" | The file isn't in the scheduler folder, or it isn't named exactly `signups.xlsx`. |
| "…missing these column headings" or "no sheet named…" | A question or tab was renamed. See [When the sign-up form changes](#when-the-sign-up-form-changes). |
| "These shift names appear in several form answers but aren't in the Shifts sheet" | A shift on the form isn't in the Shifts tab. See [Adding a shift](#adding-a-shift). |
| "There's already a draft for that week" | Press **Return** to keep it, or type **yes** for a fresh draft. The old one is kept as a copy. |
| "…is already approved" | To change it, see [If plans change after approving](#if-plans-change-after-approving). |
| A volunteer who signed up isn't on any shift | Check the review page. They may need their typed availability confirmed (step 3), have a sign-up problem, have hit their limit, or be waiting their turn. The Fairness section shows when they last worked. |
| macOS says the .command file can't be opened | Right-click it, choose **Open**, then **Open** again. |
| The window says "Can't find the scheduler's code" | The scheduler isn't installed where the launcher expects. Ask the person who set it up. |

---

## Keeping volunteers' details private

- **Personal details stay on this Mac:** `signups.xlsx`, `availability_review.csv` and every week's review page contain volunteers' names, phone numbers and emails. Don't post them or forward them to people who don't need them.
- **The calendar file has names only:** **calendar.ics** has no phone numbers or emails, and importing it sends no invitations.
- **Nothing is sent from here:** the scheduler doesn't contact anyone or upload anything.
