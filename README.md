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

**Saving:** new entries are written to the CSV files on the machine running the app. If the
app is hosted on Streamlit Community Cloud, those files are reset whenever the app restarts,
so use the download buttons on the Data tab to keep a backup.

`app.py` is the original test app and is unchanged.
