# config.py
"""
Configuration constants for Play Caller Assistant
"""

# Google Sheets
GSHEET_NAME = "PlayCaller Logs"
WORKSHEET_RESULTS = "results"
WORKSHEET_FAVORITES = "favorite_plays"

# Local database
PLAY_DB_PATH = "play_database_cleaned_download.xlsx"

# CSS
CSS_PATH = "styles.css"

# Play logic
RPO_KEYWORDS = ["rpo", "screen"]
WEIGHT_TABLE = {
    ("1st", "short"):  {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("1st", "medium"): {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("1st", "long"):   {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("2nd", "short"):  {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("2nd", "medium"): {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("2nd", "long"):   {"dropback":  .6,  "rpo":  .3,  "run_option": .1},
    ("3rd", "short"):  {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("3rd", "medium"): {"dropback": .33,  "rpo": .33,  "run_option": .34},
    ("3rd", "long"):   {"dropback": .85,  "rpo": .075,"run_option": .075},
}

# Defaults
FALLBACK_CSV = "fallback_logs.csv"


# gsheets.py
"""
Google Sheets connection and batch write logic.
"""
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Optional, List, Dict, Any
from config import GSHEET_NAME, WORKSHEET_RESULTS, WORKSHEET_FAVORITES, FALLBACK_CSV
import pandas as pd
import asyncio

# Sync fallback

def _append_to_csv(path: str, rows: List[List[Any]]):
    df = pd.DataFrame(rows)
    df.to_csv(path, mode='a', header=False, index=False)

# Cached sync client
from functools import lru_cache
@lru_cache()
def get_gsheet_client() -> Optional[gspread.Spreadsheet]:
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            __import__('streamlit').secrets['gcp_service_account'], scope
        )
        client = gspread.authorize(creds)
        return client.open(GSHEET_NAME)
    except Exception:
        return None

# Batch logs in memory
pending_results: List[List[Any]] = []
pending_favorites: List[List[Any]] = []

def buffer_result(row: List[Any]):
    pending_results.append(row)

def buffer_favorite(row: List[Any]):
    pending_favorites.append(row)

async def flush_buffers():
    sheet = get_gsheet_client()
    if sheet:
        results_ws = sheet.worksheet(WORKSHEET_RESULTS)
        fav_ws = sheet.worksheet(WORKSHEET_FAVORITES)
        for r in pending_results:
            try:
                results_ws.append_row(r)
            except Exception:
                _append_to_csv(FALLBACK_CSV, [r])
        for r in pending_favorites:
            try:
                fav_ws.append_row(r)
            except Exception:
                _append_to_csv(FALLBACK_CSV, [r])
    else:
        _append_to_csv(FALLBACK_CSV, pending_results + pending_favorites)
    pending_results.clear()
    pending_favorites.clear()

# data.py
"""
Data loading and preprocessing.
"""
import pandas as pd
from config import PLAY_DB_PATH, RPO_KEYWORDS
import streamlit as st

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    df = pd.read_excel(PLAY_DB_PATH)
    df['Play Type Category Cleaned'] = (
        df['Play Type Category']
        .apply(lambda x: 'rpo' if any(k in str(x).lower() for k in RPO_KEYWORDS) else x)
    )
    return df

# plays.py
"""
Play suggestion logic.
"""
import pandas as pd
import random
from typing import Optional
from config import WEIGHT_TABLE


def suggest_play(
    df: pd.DataFrame,
    down: str,
    distance: str,
    coverage: Optional[str] = None
) -> Optional[pd.Series]:
    subset = df.copy()
    # Filter by distance and coverage (future: add coverage filtering)
    if coverage:
        subset = subset[subset['Coverage'].str.contains(coverage, case=False, na=False)]
    if down in ('2nd', '3rd') and distance == 'long':
        subset = subset[subset['Play Depth'].str.contains('medium|long', case=False, na=False)]
    weights = WEIGHT_TABLE.get((down, distance), {})
    available = {cat: w for cat, w in weights.items()
                 if not subset[subset['Play Type Category Cleaned'] == cat].empty}
    if not available:
        return None
    cats, wts = zip(*available.items())
    chosen_cat = random.choices(cats, weights=wts, k=1)[0]
    pool = subset[subset['Play Type Category Cleaned'] == chosen_cat]
    return pool.sample(1).iloc[0] if not pool.empty else None

# ui.py
"""
Streamlit UI: theming, controls, analytics, keyboard shortcuts.
"""
import streamlit as st
from datetime import datetime
from config import CSS_PATH
from data import load_data
from plays import suggest_play
from gsheets import (
    buffer_result, buffer_favorite, flush_buffers, get_gsheet_client
)
import matplotlib.pyplot as plt
import asyncio

# Page config & theme
st.set_page_config(page_title="Play Caller Assistant", layout="centered", initial_sidebar_state="expanded")

# Load styles
try:
    with open(CSS_PATH) as f:
        css = f.read()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.markdown("""
    <style>.main .block-container { max-width: 700px; padding: 1rem 1.5rem; }
    .title { text-align: center; font-size: 2.5rem; margin: 1rem 0; font-weight: 700; }
    .play-box { border-left: 4px solid #28a745; background-color: #e6f4ea;
                padding: 1rem; border-radius: 6px; margin-bottom: 1rem; }
    </style>
    """, unsafe_allow_html=True)

# Sidebar: Favorites & Stats
st.sidebar.header("⭐ My Favorites")
fav_ids = []
if get_gsheet_client():
    fav_ids = get_gsheet_client().worksheet(st.secrets['favorite_plays']).col_values(1)
st.sidebar.write(fav_ids)

# Main title
st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

df = load_data()

# Controls: Down, Distance, Coverage, Search
st.markdown("### Select Down, Distance & Coverage")
col1, col2, col3 = st.columns(3)
with col1:
    down = st.radio("Down", ["1st","2nd","3rd"], horizontal=True)
with col2:
    distance = st.radio("Distance", ["short","medium","long"], horizontal=True)
with col3:
    coverage = st.selectbox("Coverage", ["", "man", "zone", "blitz"])

search_term = st.text_input("🔍 Search Plays", key="search")

# Suggestion
if st.button("🟢 Call a Play"):
    play = suggest_play(df, down, distance, coverage)
    st.session_state.current_play = play

play = st.session_state.get('current_play')
if play is not None:
    st.markdown(
        f"<div class='play-box'><strong>Formation:</strong> {play['Formation']}<br>"
        f"<strong>Play:</strong> {play['Play Name']}</div>", unsafe_allow_html=True
    )
    st.image(f"https://myrepo/plays/{play['Play ID']}.png", caption=play['Play Name'])
    # success/failure buttons
    c1, c2, c3 = st.columns([1,1,1], gap="small")
    with c1:
        if st.button("✅ Successful"):
            buffer_result([datetime.now().isoformat(), play['Play Name'], down, distance, coverage, True])
            st.session_state.current_play = None
    with c2:
        if st.button("❌ Unsuccessful"):
            buffer_result([datetime.now().isoformat(), play['Play Name'], down, distance, coverage, False])
            st.session_state.current_play = None
    with c3:
        if st.button("🌟 Add to Favorites"):
            buffer_favorite([play['Play ID']])
            st.sidebar.write(play['Play ID'])
    # Details
    with st.expander("Details"):
        st.write(f"**Adjustments**: {play.get('Route Adjustments','')}")
        st.write(f"**Progression**: {play.get('Progression','')}")
        st.write(f"**Notes**: {play.get('Notes','')}")

# Analytics
with st.expander("📊 Success Rate by Category"):
    try:
        import pandas as pd
        logs = pd.DataFrame(get_gsheet_client().worksheet(WORKSHEET_RESULTS).get_all_records())
        stats = logs.groupby('Play Type Category').agg(
            success_rate=('Successful','mean'), count=('Successful','size')
        ).sort_values('count', ascending=False)
        fig, ax = plt.subplots()
        ax.bar(stats.index, stats['success_rate'])
        ax.set_ylabel('Success Rate')
        ax.set_xticklabels(stats.index, rotation=45, ha='right')
        st.pyplot(fig)
    except Exception:
        st.write("Could not load analytics.")

# Keyboard shortcuts (JS)
st.markdown("""
<script>
document.addEventListener('keydown', function(e) {
  if (e.key === 's') document.querySelector('button[kind="primary"]').click();
  if (e.key === 'f') document.querySelectorAll('button')[2].click();
  if (e.key === 'n') document.querySelectorAll('button')[0].click();
});
</script>
""", unsafe_allow_html=True)

# Flush buffers periodically
def _flush():
    asyncio.run(flush_buffers())

st.button("Flush Logs", on_click=_flush)
