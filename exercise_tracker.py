"""Exercise tracker - Streamlit app.

Run with:  streamlit run exercise_tracker.py

Data lives in two CSV files, in Dropbox if configured (see storage.py), otherwise in ./data:
  exercise_log.csv  - one row per cardio activity, or per strength exercise at one weight
  body_weight.csv   - body-weight check-ins
"""
from __future__ import annotations

import datetime as dt
import hmac
import re
from pathlib import Path

import io

import altair as alt
import pandas as pd
import streamlit as st

import storage

# Bundled starting data, copied to the storage location the first time the app runs.
SEED_DIR = Path(__file__).parent / "data"
LOG_NAME = "exercise_log.csv"
WEIGHT_NAME = "body_weight.csv"
WEIGHT_COLUMNS = ["date", "weight_kg", "notes"]

LBS_PER_KG = 2.20462262
HEIGHT_CM = 189
BIRTH_AGE_NOTE = 55  # age as stated in the log; not used for any calculation

COLUMNS = [
    "date", "session", "category", "activity", "duration", "distance_km", "elevation_m",
    "calories", "level", "incline_pct", "weight", "unit", "reps", "steps", "notes",
]
CATEGORIES = ["Cardio", "Strength", "Sport", "Outdoor", "Rest"]
DEFAULT_ACTIVITIES = {
    "Cardio": ["Rowing machine", "Exercise bike", "Treadmill", "Stair climber", "Cross trainer"],
    "Sport": ["Squash", "Padel"],
    "Outdoor": ["Kayaking", "Canoeing", "Kayak surfing", "Hike", "Walk", "Cycling (outdoor)"],
    "Strength": [
        "Bicep curl (bar)", "Bicep curl (machine)", "Bicep curl (dumbbell)", "Tricep curl",
        "Tricep extension", "Lat pulldown", "Low row", "Seated chest press", "Shoulder press",
        "Kettlebell overhead lift", "Dumbbell overhead lift", "Leg extension", "Leg curl", "Leg raises",
    ],
    "Rest": ["Rest day"],
}

st.set_page_config(page_title="Exercise Tracker", page_icon="🏋️", layout="wide",
                   initial_sidebar_state="auto")


def check_password() -> None:
    """If an app_password is set in secrets, ask for it once per browser session."""
    try:
        expected = st.secrets.get("app_password")
    except Exception:
        expected = None
    if not expected or st.session_state.get("authenticated"):
        return
    st.title("🏋️ Exercise Tracker")
    with st.form("login"):
        pw = st.text_input("Password", type="password")
        if st.form_submit_button("Unlock", type="primary"):
            if hmac.compare_digest(pw.encode(), str(expected).encode()):
                st.session_state["authenticated"] = True
                st.rerun()
            st.error("Wrong password.")
    st.stop()


check_password()


def dropbox_setup_screen() -> None:
    """One-time Dropbox connection that works entirely from a phone browser."""
    if not storage.needs_connecting():
        return
    st.title("☁️ Connect Dropbox")
    try:
        has_password = bool(st.secrets.get("app_password"))
    except Exception:
        has_password = False
    if not has_password:
        st.warning("Add an `app_password` line to your Secrets first, then come back here.")
        st.stop()
    st.markdown("Your app key and secret are in place. Two more steps:")
    st.markdown("**1.** Tap this link, sign in to Dropbox if asked, and tap **Allow**. "
                "Dropbox then shows you a code - copy it.")
    st.link_button("Open Dropbox", storage.connect_url(), type="primary")
    code = st.text_input("**2.** Paste the code here")
    if st.button("Connect") and code.strip():
        try:
            token = storage.finish_connect(code)
        except Exception as err:
            st.error(f"Dropbox didn't accept that code ({err}). Codes only work once and expire "
                     "quickly - tap 'Open Dropbox' again to get a fresh one.")
        else:
            st.success("Connected! One last step:")
            st.markdown(
                "Copy the line below (tap the copy icon at its right). Then in Streamlit go to "
                "**Manage app → ⋮ → Settings → Secrets** and paste it under the other lines in "
                "the `[dropbox]` section, then **Save**."
            )
            st.code(f'refresh_token = "{token}"', language="toml")
            st.caption("Keep this private - it lets the app read and write its Dropbox folder.")
    st.stop()


dropbox_setup_screen()


def metric_cols(n: int) -> list:
    """Metric 'columns' that wrap two-per-row on a phone instead of stacking one per row."""
    row = st.container(horizontal=True, wrap=True, gap="medium")

    class _Cell:
        def metric(self, *args, **kwargs):
            kwargs.setdefault("width", 150)
            return row.metric(*args, **kwargs)

    return [_Cell() for _ in range(n)]


# --------------------------------------------------------------------------- helpers
def parse_duration(value) -> float | None:
    """'37:43' -> 37.72 minutes, '1:05:00' -> 65.0. Blank -> None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        parts = [float(p) for p in s.split(":")]
    except ValueError:
        return None
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return parts[0] + parts[1] / 60
    return parts[0] * 60 + parts[1] + parts[2] / 60


def fmt_minutes(minutes: float | None) -> str:
    if minutes is None or pd.isna(minutes):
        return ""
    total = int(round(minutes * 60))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_reps(text: str) -> str:
    """Normalise user rep input to 'a;b;c'. Accepts '10,10,8', '3x10', '2x10, 1x5'."""
    out: list[str] = []
    for chunk in re.split(r"[;,]", str(text)):
        chunk = chunk.strip().lower().replace(" ", "")
        if not chunk:
            continue
        m = re.fullmatch(r"(\d+)x(\d+)", chunk)
        if m:
            out += [m.group(2)] * int(m.group(1))
        elif chunk.isdigit():
            out.append(chunk)
        else:
            raise ValueError(f"Could not understand reps '{chunk}'")
    return ";".join(out)


def rep_list(value) -> list[int]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [int(r) for r in str(value).split(";") if r.strip().isdigit()]


def seed_bytes(name: str, columns: list[str]) -> bytes:
    path = SEED_DIR / name
    return path.read_bytes() if path.exists() else (",".join(columns) + "\n").encode()


@st.cache_data(ttl=300, show_spinner="Loading your log…")
def load_log(location: str) -> tuple[pd.DataFrame, str | None]:  # location only keys the cache
    data, rev = storage.read(LOG_NAME, seed_bytes(LOG_NAME, COLUMNS))
    df = pd.read_csv(io.BytesIO(data), dtype={"reps": str, "level": str, "duration": str})
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = None
    df = df[COLUMNS]
    df["date"] = pd.to_datetime(df["date"]).dt.date
    for c in ["session", "category", "activity", "duration", "level", "unit", "reps", "notes"]:
        df[c] = df[c].fillna("").astype(str)
    for c in ["distance_km", "elevation_m", "calories", "incline_pct", "weight", "steps"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df, rev


@st.cache_data(ttl=300, show_spinner=False)
def load_weights(location: str) -> tuple[pd.DataFrame, str | None]:
    data, rev = storage.read(WEIGHT_NAME, seed_bytes(WEIGHT_NAME, WEIGHT_COLUMNS))
    df = pd.read_csv(io.BytesIO(data))
    df["date"] = pd.to_datetime(df["date"]).dt.date
    if "notes" not in df.columns:
        df["notes"] = ""
    df["notes"] = df["notes"].fillna("").astype(str)
    return df[WEIGHT_COLUMNS].sort_values("date"), rev


def _save(name: str, df: pd.DataFrame, rev: str | None) -> bool:
    """Write a CSV to storage. Returns False (and shows why) if it could not be saved."""
    try:
        storage.write(name, df.to_csv(index=False).encode(), rev)
    except storage.ConflictError:
        st.error(
            f"{name} was changed in Dropbox after this page loaded, so your change was NOT saved "
            "(to avoid overwriting the newer version). Press 'Reload data' in the sidebar and try again."
        )
        return False
    except Exception as err:  # network / auth problems
        st.error(f"Could not save {name}: {err}")
        return False
    st.cache_data.clear()
    return True


def save_log(df: pd.DataFrame) -> bool:
    return _save(LOG_NAME, df[COLUMNS].sort_values(["date", "session"], kind="stable"), log_rev)


def save_weights(df: pd.DataFrame) -> bool:
    return _save(WEIGHT_NAME, df[WEIGHT_COLUMNS].sort_values("date"), weights_rev)


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    """Add derived columns used by the charts."""
    d = df.copy()
    d["minutes"] = d["duration"].map(parse_duration)
    d["speed_kmh"] = d["distance_km"] / (d["minutes"] / 60)
    # Rowing split: time per 500 m, in minutes
    d["split_500m"] = d["minutes"] / (d["distance_km"] * 2)
    d["split_500m_s"] = d["split_500m"] * 60
    reps = d["reps"].map(rep_list)
    d["sets"] = reps.map(len)
    d["total_reps"] = reps.map(sum)
    d["weight_kg"] = d.apply(
        lambda r: r["weight"] / LBS_PER_KG if r["unit"] == "lbs" else (r["weight"] if r["unit"] == "kg" else None),
        axis=1,
    ).astype(float)
    d["weight_lbs"] = d["weight_kg"] * LBS_PER_KG
    d["week"] = pd.to_datetime(d["date"]).dt.to_period("W-SUN").dt.start_time
    return d


def bmi(weight_kg: float) -> float:
    return weight_kg / (HEIGHT_CM / 100) ** 2


# --------------------------------------------------------------------------- load
location = storage.location_label()
try:
    raw, log_rev = load_log(location)
    weights, weights_rev = load_weights(location)
except storage.DropboxLoginError as err:
    st.error(f"Could not load your data from {location}.\n\n{err}")
    st.stop()
except Exception as err:
    st.error(f"Could not load your data from {location}.\n\n{err}")
    st.info("Check the [dropbox] settings in your Streamlit secrets (see README).")
    st.stop()
log = enrich(raw)

# --------------------------------------------------------------------------- sidebar
st.sidebar.title("🏋️ Exercise Tracker")
st.sidebar.caption(f"Age {BIRTH_AGE_NOTE} · Height {HEIGHT_CM} cm")
if storage.backend() == "dropbox":
    st.sidebar.success(f"Saving to {location}", icon="☁️")
else:
    st.sidebar.warning("Saving to local files only - Dropbox is not set up (see README).", icon="💾")
if st.sidebar.button("🔄 Reload data", help="Fetch the latest version of your files"):
    st.cache_data.clear()
    st.rerun()
if not weights.empty:
    latest = weights.iloc[-1]
    st.sidebar.metric(
        "Latest body weight",
        f"{latest.weight_kg:.1f} kg",
        help=f"Recorded {latest.date:%d %b %Y}. BMI {bmi(latest.weight_kg):.1f}",
    )

if log.empty:
    min_d = max_d = dt.date.today()
else:
    min_d, max_d = log["date"].min(), max(log["date"].max(), dt.date.today())
date_range = st.sidebar.date_input("Date range", (min_d, max_d), min_value=min_d, max_value=max_d)
if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = date_range
else:
    start, end = min_d, max_d
weight_unit = st.sidebar.radio("Show strength weights in", ["kg", "lbs"], horizontal=True)
st.sidebar.caption(
    "Machine calories are shown as displayed by the machine - they were not adjusted for body weight."
)

view = log[(log["date"] >= start) & (log["date"] <= end)]
active = view[view["category"] != "Rest"]

# "Log" comes first so it is the tab you land on when opening the app on a phone at the gym.
tab_add, tab_overview, tab_cardio, tab_strength, tab_body, tab_data = st.tabs(
    ["➕ Log", "📊 Overview", "🚣 Cardio", "💪 Strength", "⚖️ Body", "🗂️ Data"]
)

# --------------------------------------------------------------------------- overview
with tab_overview:
    days = (end - start).days + 1
    active_days = active["date"].nunique()
    moving = active[active["category"] != "Strength"]
    c1, c2, c3, c4, c5 = metric_cols(5)
    c1.metric("Active days", f"{active_days} / {days}")
    c2.metric("Timed activity", f"{moving['minutes'].sum() / 60:.1f} h",
              help="Sum of recorded durations (strength sets are not timed).")
    c3.metric("Distance", f"{moving['distance_km'].sum():.0f} km",
              help="All recorded distances: machines, walks, hikes and kayaking.")
    c4.metric("Rowed", f"{view.loc[view.activity == 'Rowing machine', 'distance_km'].sum():.1f} km")
    c5.metric("Strength sets", int(view["sets"].sum()))

    # Current streak of active days, counted back from the most recent logged day
    streak = 0
    if not log.empty:
        active_dates = set(log.loc[log.category != "Rest", "date"])
        d = log["date"].max()
        while d in active_dates:
            streak += 1
            d -= dt.timedelta(days=1)
    st.caption(f"Current streak: **{streak}** consecutive active day(s) up to your last logged day.")

    st.subheader("Weekly timed minutes by category")
    weekly = (
        moving.groupby(["week", "category"], as_index=False)["minutes"].sum()
        if not moving.empty else pd.DataFrame(columns=["week", "category", "minutes"])
    )
    st.altair_chart(
        alt.Chart(weekly).mark_bar().encode(
            x=alt.X("week:T", title="Week starting"),
            y=alt.Y("minutes:Q", title="Minutes"),
            color=alt.Color("category:N", title=None, legend=alt.Legend(orient="bottom")),
            tooltip=["week:T", "category:N", alt.Tooltip("minutes:Q", format=".0f")],
        ),
        width="stretch",
    )
    st.caption("Strength work has no duration in the log, so it is counted in sets below rather than minutes.")

    left, right = st.columns(2)
    with left:
        st.subheader("Activity calendar")
        cal = view.copy()
        cal["d"] = pd.to_datetime(cal["date"])
        per_day = cal.groupby("d").agg(
            minutes=("minutes", "sum"),
            sets=("sets", "sum"),
            rest=("category", lambda s: (s == "Rest").all()),
            what=("activity", lambda s: ", ".join(dict.fromkeys(s))),
        ).reset_index()
        all_days = pd.DataFrame({"d": pd.date_range(start, end)})
        per_day = all_days.merge(per_day, on="d", how="left")
        per_day["status"] = per_day.apply(
            lambda r: "Not logged" if pd.isna(r["what"]) else ("Rest" if r["rest"] else "Active"), axis=1
        )
        per_day["what"] = per_day["what"].fillna("")
        per_day["weekday"] = per_day["d"].dt.strftime("%a")
        per_day["week"] = per_day["d"].dt.to_period("W-SUN").dt.start_time
        st.altair_chart(
            alt.Chart(per_day).mark_rect(cornerRadius=2).encode(
                x=alt.X("week:O", title=None, axis=alt.Axis(format="%d %b", formatType="time", labelAngle=-45)),
                y=alt.Y("weekday:O", sort=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], title=None),
                color=alt.Color(
                    "status:N",
                    scale=alt.Scale(domain=["Active", "Rest", "Not logged"],
                                    range=["#2a9d8f", "#e9c46a", "#e5e5e5"]),
                    title=None,
                ),
                tooltip=[alt.Tooltip("d:T", title="Date"), "status:N", alt.Tooltip("what:N", title="Activities")],
            ).properties(height=220),
            width="stretch",
        )
    with right:
        st.subheader("Sessions per activity")
        counts = (
            active.groupby(["activity", "category"])["date"].nunique()
            .reset_index(name="days").sort_values("days", ascending=False)
        )
        st.altair_chart(
            alt.Chart(counts).mark_bar().encode(
                x=alt.X("days:Q", title="Days done"),
                y=alt.Y("activity:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)),
                color=alt.Color("category:N", legend=None),
                tooltip=["activity", "days"],
            ).properties(height=max(220, 24 * len(counts))),
            width="stretch",
        )

    st.subheader("Most recent days")
    recent_dates = sorted(view["date"].unique(), reverse=True)[:7]
    for d in recent_dates:
        day = view[view["date"] == d]
        parts = []
        for _, r in day.iterrows():
            bits = [r["activity"]]
            if r["minutes"] and not pd.isna(r["minutes"]):
                bits.append(fmt_minutes(r["minutes"]))
            if not pd.isna(r["distance_km"]):
                bits.append(f"{r['distance_km']:g} km")
            if not pd.isna(r["weight"]):
                bits.append(f"{r['weight']:g} {r['unit']} × {r['reps'].replace(';', ', ')}")
            parts.append(" ".join(bits))
        st.markdown(f"**{d:%a %d %b}** — " + " · ".join(parts))

# --------------------------------------------------------------------------- cardio
with tab_cardio:
    timed = view[view["category"].isin(["Cardio", "Sport", "Outdoor"])]
    options = sorted(timed["activity"].unique())
    if not options:
        st.info("No cardio in this date range.")
    else:
        default = options.index("Rowing machine") if "Rowing machine" in options else 0
        act = st.selectbox("Activity", options, index=default)
        a = timed[timed["activity"] == act].copy()

        c1, c2, c3, c4 = metric_cols(4)
        c1.metric("Sessions", len(a))
        c2.metric("Total time", fmt_minutes(a["minutes"].sum()) or "—")
        c3.metric("Total distance", f"{a['distance_km'].sum():.2f} km")
        c4.metric("Longest", f"{a['distance_km'].max():.2f} km" if a["distance_km"].notna().any() else "—")

        a["date_t"] = pd.to_datetime(a["date"])
        metric_opts = {"Distance (km)": "distance_km", "Duration (min)": "minutes"}
        if a["speed_kmh"].notna().any():
            metric_opts["Average speed (km/h)"] = "speed_kmh"
        if act == "Rowing machine":
            metric_opts = {"Split per 500 m (m:ss)": "split_500m_s", **metric_opts}
        if a["calories"].notna().any():
            metric_opts["Machine calories"] = "calories"
        if a["elevation_m"].notna().any():
            metric_opts["Elevation (m)"] = "elevation_m"
        label = st.radio("Chart", list(metric_opts), horizontal=True)
        col = metric_opts[label]
        plot = a.dropna(subset=[col])
        y_axis = alt.Axis(labelExpr="floor(datum.value / 60) + ':' + "
                          "(datum.value % 60 < 10 ? '0' : '') + round(datum.value % 60)") \
            if col == "split_500m_s" else alt.Axis()
        base = alt.Chart(plot).encode(
            x=alt.X("date_t:T", title="Date"),
            y=alt.Y(f"{col}:Q", title=label, axis=y_axis,
                    scale=alt.Scale(zero=col not in ("split_500m_s", "speed_kmh"))),
            tooltip=[alt.Tooltip("date_t:T", title="Date"), "duration", "distance_km", "calories", "notes"],
        )
        chart = base.mark_line(point=True)
        if len(plot) >= 3:
            chart = chart + base.transform_regression("date_t", col).mark_line(strokeDash=[4, 4], opacity=0.5)
        st.altair_chart(chart, width="stretch")
        if col == "split_500m_s":
            st.caption("Lower is faster. Dashed line = trend.")

        if act == "Rowing machine":
            st.subheader("Rowing personal bests")
            pbs = []
            for dist in sorted(a["distance_km"].dropna().unique()):
                same = a[(a["distance_km"] == dist) & a["minutes"].notna()]
                if len(same):
                    best = same.loc[same["minutes"].idxmin()]
                    pbs.append({
                        "Distance (m)": int(round(dist * 1000)),
                        "Best time": fmt_minutes(best["minutes"]),
                        "Split /500m": fmt_minutes(best["split_500m"]),
                        "Date": best["date"],
                        "Times rowed": len(same),
                    })
            pb_df = pd.DataFrame(pbs)
            if not pb_df.empty:
                st.dataframe(pb_df[pb_df["Times rowed"] >= 1], hide_index=True, width="stretch")
            fastest = a.dropna(subset=["split_500m"])
            fastest = fastest[fastest["distance_km"] >= 2]
            if not fastest.empty:
                f = fastest.loc[fastest["split_500m"].idxmin()]
                st.caption(
                    f"Fastest average split on a row of 2 km or more: **{fmt_minutes(f['split_500m'])} /500m** "
                    f"({f['distance_km']*1000:.0f} m on {f['date']:%d %b})."
                )

        st.subheader("Sessions")
        show = a.sort_values("date", ascending=False)[
            ["date", "session", "duration", "distance_km", "speed_kmh", "calories", "level",
             "incline_pct", "elevation_m", "notes"]
        ]
        st.dataframe(
            show, hide_index=True, width="stretch",
            column_config={"speed_kmh": st.column_config.NumberColumn("km/h", format="%.1f")},
        )

# --------------------------------------------------------------------------- strength
with tab_strength:
    s = view[(view["category"] == "Strength")].copy()
    if s.empty:
        st.info("No strength work in this date range.")
    else:
        wcol = "weight_kg" if weight_unit == "kg" else "weight_lbs"
        exercises = s.groupby("activity")["date"].nunique().sort_values(ascending=False)
        ex = st.selectbox(
            "Exercise", exercises.index,
            format_func=lambda e: f"{e} ({exercises[e]} days)",
        )
        e = s[s["activity"] == ex].copy()
        e["volume"] = e[wcol] * e["total_reps"]
        per_day = e.groupby("date", as_index=False).agg(
            top_weight=(wcol, "max"), volume=("volume", "sum"),
            reps=("total_reps", "sum"), sets=("sets", "sum"),
        )
        per_day["date_t"] = pd.to_datetime(per_day["date"])

        logged_units = sorted(set(e["unit"]) - {""})
        c1, c2, c3 = metric_cols(3)
        best = e.loc[e[wcol].idxmax()] if e[wcol].notna().any() else None
        c1.metric("Heaviest", f"{best[wcol]:.1f} {weight_unit}" if best is not None else "—",
                  help=None if best is None else
                  f"{best['weight']:g} {best['unit']} on {best['date']:%d %b}")
        c2.metric("Days trained", len(per_day))
        c3.metric("Total reps", int(e["total_reps"].sum()))
        if "lbs" in logged_units and weight_unit == "kg":
            st.caption("This exercise was logged in lbs (machine stack) - converted to kg for display.")
        if "kg" in logged_units and weight_unit == "lbs":
            st.caption("This exercise was logged in kg - converted to lbs for display.")

        metric = st.radio("Chart", ["Top weight", "Volume (weight × reps)", "Total reps"], horizontal=True)
        ycol = {"Top weight": "top_weight", "Volume (weight × reps)": "volume", "Total reps": "reps"}[metric]
        ytitle = {"top_weight": f"Top weight ({weight_unit})", "volume": f"Volume ({weight_unit} × reps)",
                  "reps": "Reps"}[ycol]
        st.altair_chart(
            alt.Chart(per_day.dropna(subset=[ycol])).mark_line(point=True).encode(
                x=alt.X("date_t:T", title="Date"),
                y=alt.Y(f"{ycol}:Q", title=ytitle),
                tooltip=[alt.Tooltip("date_t:T", title="Date"),
                         alt.Tooltip("top_weight:Q", format=".1f"), "sets", "reps",
                         alt.Tooltip("volume:Q", format=".0f")],
            ),
            width="stretch",
        )

        st.subheader("Heaviest weight per exercise")
        bests = []
        for name, g in s.groupby("activity"):
            if g[wcol].notna().any():
                b = g.loc[g[wcol].idxmax()]
                bests.append({"Exercise": name, f"Best ({weight_unit})": round(b[wcol], 1),
                              "As logged": f"{b['weight']:g} {b['unit']}", "Reps": b["reps"].replace(";", ", "),
                              "First reached": b["date"], "Days trained": g["date"].nunique()})
        st.dataframe(pd.DataFrame(bests).sort_values("Days trained", ascending=False),
                     hide_index=True, width="stretch")

        st.subheader(f"{ex} - all sets")
        st.dataframe(
            e.sort_values("date", ascending=False)[["date", "session", "weight", "unit", "reps", "notes"]],
            hide_index=True, width="stretch",
        )

# --------------------------------------------------------------------------- body
with tab_body:
    st.subheader("Body weight")
    if weights.empty:
        st.info("No weigh-ins yet.")
    else:
        w = weights.copy()
        w["BMI"] = w["weight_kg"].map(bmi).round(1)
        w["weight_lbs"] = (w["weight_kg"] * LBS_PER_KG).round(1)
        w["date_t"] = pd.to_datetime(w["date"])
        c1, c2, c3 = metric_cols(3)
        c1.metric("Latest", f"{w.iloc[-1].weight_kg:.1f} kg",
                  delta=f"{w.iloc[-1].weight_kg - w.iloc[0].weight_kg:+.1f} kg since {w.iloc[0].date:%d %b}",
                  delta_color="inverse")
        c2.metric("BMI", f"{w.iloc[-1].BMI:.1f}", help=f"weight (kg) / height (m)², using {HEIGHT_CM} cm")
        c3.metric("Weigh-ins", len(w))
        st.altair_chart(
            alt.Chart(w).mark_line(point=True).encode(
                x=alt.X("date_t:T", title="Date"),
                y=alt.Y("weight_kg:Q", title="kg", scale=alt.Scale(zero=False)),
                tooltip=[alt.Tooltip("date_t:T", title="Date"), "weight_kg", "weight_lbs", "BMI"],
            ),
            width="stretch",
        )
        st.dataframe(w[["date", "weight_kg", "weight_lbs", "BMI", "notes"]].sort_values("date", ascending=False),
                     hide_index=True, width="stretch")

    with st.form("weigh_in", clear_on_submit=True):
        st.markdown("**Add a weigh-in**")
        c1, c2, c3 = st.columns([1, 1, 2])
        wd = c1.date_input("Date", dt.date.today(), key="w_date")
        wkg = c2.number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=103.0, step=0.1)
        wnote = c3.text_input("Notes", key="w_notes")
        if st.form_submit_button("Save weigh-in"):
            new = pd.concat([weights, pd.DataFrame([{"date": wd, "weight_kg": wkg, "notes": wnote}])])
            if save_weights(new):
                st.toast(f"Saved {wkg:.1f} kg for {wd:%d %b %Y}")
                st.rerun()

# --------------------------------------------------------------------------- add workout
with tab_add:
    st.subheader("Log a workout")
    # Most-used activities first, so the usual one is a single tap away.
    usage = raw.groupby("activity")["date"].nunique()
    known = {
        cat: sorted(set(DEFAULT_ACTIVITIES.get(cat, [])) | set(raw.loc[raw.category == cat, "activity"]),
                    key=lambda a: (-usage.get(a, 0), a))
        for cat in CATEGORIES
    }
    c1, c2, c3 = st.columns(3)
    cat = c1.selectbox("Category", CATEGORIES)
    choice = c2.selectbox("Activity / exercise", known[cat] + ["Other…"])
    the_date = c3.date_input("Date", dt.date.today())
    activity = st.text_input("Name of new activity") if choice == "Other…" else choice

    with st.form("add_entry", clear_on_submit=True):
        row = {c: "" for c in COLUMNS}
        row.update(date=the_date, category=cat, activity=activity)
        if cat == "Strength":
            c1, c2, c3 = st.columns(3)
            weight = c1.number_input("Weight", min_value=0.0, step=0.5, value=0.0)
            default_unit = 0 if raw.loc[raw.activity == activity, "unit"].eq("kg").any() else 1
            unit = c2.selectbox("Unit", ["kg", "lbs", "bw"], index=default_unit,
                                help="bw = body weight (no added load)")
            reps_text = c3.text_input("Reps", placeholder="e.g. 10,10,8  or  3x10  or  2x10, 1x5")
            st.caption("Used more than one weight? Save each weight as its own entry.")
        elif cat != "Rest":
            c1, c2, c3 = st.columns(3)
            time_text = c1.text_input("Time (min:sec)", placeholder="e.g. 37:43  or  1:05:00 for 1h05")
            dist = c2.text_input("Distance (km)", placeholder="e.g. 5.0 (rowing 5000m = 5.0)")
            cals = c3.text_input("Machine calories")
            with st.expander("More: level, incline, elevation, steps"):
                c1, c2 = st.columns(2)
                level = c1.text_input("Level", placeholder="e.g. 10 or 5-10")
                incline = c2.text_input("Incline %")
                elev = c1.text_input("Elevation (m)")
                steps = c2.text_input("Step count")
        notes = st.text_input("Notes")
        session = st.text_input("Session (optional)", placeholder="e.g. Morning / Evening")
        submitted = st.form_submit_button("Save entry", type="primary")

    if submitted:
        try:
            if not activity:
                raise ValueError("Please give the activity a name.")
            row.update(session=session, notes=notes)
            if cat == "Strength":
                reps = parse_reps(reps_text)
                if not reps:
                    raise ValueError("Please enter at least one set of reps.")
                row.update(weight=weight if unit != "bw" else None, unit=unit, reps=reps)
            elif cat != "Rest":
                if time_text.strip():
                    if not re.fullmatch(r"\d+(:[0-5]?\d){1,2}|\d+", time_text.strip()):
                        raise ValueError("Time should look like 37:43 (min:sec) or 1:05:00 (h:min:sec).")
                    row["duration"] = fmt_minutes(parse_duration(time_text.replace(" ", "")))

                def num(v, label):
                    if not str(v).strip():
                        return None
                    try:
                        return float(str(v).replace(",", ""))
                    except ValueError:
                        raise ValueError(f"{label} must be a number")

                row.update(distance_km=num(dist, "Distance"), calories=num(cals, "Calories"),
                           level=level, incline_pct=num(incline, "Incline"),
                           elevation_m=num(elev, "Elevation"), steps=num(steps, "Steps"))
            new = pd.concat([raw, pd.DataFrame([row])], ignore_index=True)
            if save_log(new):
                st.toast(f"Saved: {activity} on {the_date:%d %b %Y}")
                st.rerun()
        except ValueError as err:
            st.error(str(err))

# --------------------------------------------------------------------------- data
with tab_data:
    st.subheader("All entries")
    st.caption(
        "Edit cells directly, add rows at the bottom, or select rows and press Delete. "
        "Duration is minutes:seconds (e.g. 37:43; use 114:00 for 1h54). Reps are separated by ';'. "
        "Rowing distance is in km (5000 m = 5.0)."
    )
    edited = st.data_editor(
        raw.sort_values("date", ascending=False).reset_index(drop=True),
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        height=500,
        column_config={
            "date": st.column_config.DateColumn("date", required=True),
            "category": st.column_config.SelectboxColumn("category", options=CATEGORIES, required=True),
            "unit": st.column_config.SelectboxColumn("unit", options=["", "kg", "lbs", "bw"]),
        },
        key="editor",
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("💾 Save changes", type="primary"):
        if save_log(edited):
            st.toast("Saved.")
            st.rerun()
    c2.download_button("⬇️ Download exercise log (CSV)", raw.to_csv(index=False), "exercise_log.csv", "text/csv")
    c3.download_button("⬇️ Download body weights (CSV)", weights.to_csv(index=False), "body_weight.csv", "text/csv")

    with st.expander("Restore from a CSV backup"):
        up = st.file_uploader("Exercise log CSV", type="csv")
        if up is not None and st.button("Replace exercise log with this file"):
            df_up = pd.read_csv(up, dtype=str)
            missing = set(COLUMNS) - set(df_up.columns)
            if missing:
                st.error(f"File is missing columns: {', '.join(sorted(missing))}")
            else:
                if _save(LOG_NAME, df_up[COLUMNS], log_rev):
                    st.toast("Exercise log replaced.")
                    st.rerun()

    flagged = raw[raw["notes"].str.contains("assumed|verify|truncated|Logged as", case=False)]
    if not flagged.empty:
        st.subheader("Entries I had to interpret when importing")
        st.caption("These came from typos or ambiguous text in the original log - please check them.")
        st.dataframe(flagged, hide_index=True, width="stretch")
