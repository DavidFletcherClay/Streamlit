# Streamlit

## Exercise Tracker

A personal exercise log with charts, run with:

```bash
pip install -r requirements.txt
streamlit run exercise_tracker.py
```

### What it does
- **Overview** - active days, timed minutes per week, distance, an activity calendar (active / rest / not logged) and the most recent days.
- **Cardio** - per-activity trends (rowing split per 500 m, speed, distance, duration, machine calories, elevation) with a trend line, rowing personal bests by distance, and a session table.
- **Strength** - per-exercise top weight, volume (weight × reps) and reps over time, with a kg/lbs toggle, plus the heaviest weight for every exercise.
- **Body** - weigh-ins with BMI (height 189 cm).
- **Log workout** - form to add cardio, sport, outdoor, strength or rest-day entries.
- **Data** - edit, add or delete any row, download CSV backups, restore from a backup, and a list of imported entries that needed interpreting.

### Data files (`data/`)
- `exercise_log.csv` - one row per cardio activity, or per strength exercise at one weight.
  - `duration` is minutes:seconds (`37:43`; 1h54 is `114:00`).
  - `distance_km` is in km (rowing 5000 m = `5.0`).
  - `reps` is one number per set, separated by `;` (`10;10;8`).
  - `unit` is `kg`, `lbs` (machine stacks) or `bw` (body weight).
- `body_weight.csv` - date and weight in kg.

The history from 1 June to 9 November 2026 was imported from the original text log. Entries
with typos or ambiguous values have a note saying what was assumed - see the bottom of the
**Data** tab.

## Saving to Dropbox

When Dropbox is set up, the app reads and writes `exercise_log.csv` and `body_weight.csv` in
your Dropbox. The first time it runs it copies the history from `data/` there. Without Dropbox
it falls back to the local `data/` folder. The sidebar shows which one is in use.

If a file was changed in Dropbox after the page loaded (for example from another device), the
app refuses to save over it and asks you to press **Reload data**. Dropbox also keeps its own
version history of each file.

One-time setup (Dropbox's page names may differ slightly from these):

1. Go to <https://www.dropbox.com/developers/apps> and choose **Create app** →
   **Scoped access** → **App folder**, and give it a name.
2. On the app's **Permissions** tab tick `files.content.read` and `files.content.write`,
   then **Submit**.
3. On the **Settings** tab copy the **App key** and **App secret**.
4. On your computer run `pip install dropbox` then `python get_dropbox_token.py`, paste the key
   and secret, approve access in the browser, and paste back the code.
5. It prints a `[dropbox]` block. Put it in `.streamlit/secrets.toml` (see
   `.streamlit/secrets.toml.example`) or, when hosted, in the app's **Secrets** settings.

The files then appear in Dropbox under **Apps → <your app name> → Exercise Tracker**.

## Using it on an iPhone

The app runs in Safari, but it has to be hosted somewhere your phone can reach. The free
option is Streamlit Community Cloud:

1. Sign in at <https://share.streamlit.io> with GitHub and create an app from this repository,
   with **Main file path** `exercise_tracker.py`.
2. In the app's **Secrets** settings paste the `[dropbox]` block plus a password:

   ```toml
   app_password = "choose-something"

   [dropbox]
   app_key = "..."
   app_secret = "..."
   refresh_token = "..."
   folder = "/Exercise Tracker"
   ```

   The password matters: the app gets a public web address and can write to your Dropbox.
3. Open the app's address in Safari on the iPhone, tap **Share** → **Add to Home Screen**.

On a phone the app opens on the **Log** tab. The summary numbers sit two to a row, and the
date-range and kg/lbs controls are in the sidebar (the `>>` button at the top left).

`app.py` is the original test app and is unchanged.
