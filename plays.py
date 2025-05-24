# requirements.txt:
# streamlit
# pandas
# gspread
# oauth2client
# matplotlib
# openpyxl

import streamlit as st
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import matplotlib.pyplot as plt

# --- Configuration Constants ---
GSHEET_NAME = "PlayCaller Logs"
WORKSHEET_RESULTS = "results"
WORKSHEET_FAVORITES = "favorite_plays"
PLAY_DB_PATH = "play_database_cleaned_download.xlsx"
CSS_PATH = "styles.css"
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

# --- Batch Buffers ---
pending_results = []
pending_favorites = []

# --- Google Sheets Connection ---
@st.cache_resource
def get_gsheet():
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client = gspread.authorize(creds)
        return client.open(GSHEET_NAME)
    except Exception:
        return None

# Flush buffers
def flush_buffers():
    sheet = get_gsheet()
    if not sheet:
        pending_results.clear()
        pending_favorites.clear()
        return
    res_ws = sheet.worksheet(WORKSHEET_RESULTS)
    fav_ws = sheet.worksheet(WORKSHEET_FAVORITES)
    for row in pending_results:
        try:
            res_ws.append_row(row)
        except Exception:
            pass
    for row in pending_favorites:
        try:
            fav_ws.append_row(row)
        except Exception:
            pass
    pending_results.clear()
    pending_favorites.clear()

# --- Data Loading ---
@st.cache_data(show_spinner=False)
def load_data():
    df = pd.read_excel(PLAY_DB_PATH)
    df['Play Type Category Cleaned'] = df['Play Type Category'].apply(
        lambda x: 'rpo' if any(k in str(x).lower() for k in RPO_KEYWORDS) else x
    )
    return df

# --- Play Suggestion Logic ---
def suggest_play(df, down, distance, coverage=None):
    subset = df.copy()
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
    chosen = random.choices(cats, weights=wts, k=1)[0]
    pool = subset[subset['Play Type Category Cleaned'] == chosen]
    return pool.sample(1).iloc[0] if not pool.empty else None

# --- Streamlit UI ---
st.set_page_config(page_title="Play Caller Assistant", layout="centered")
# Load styles
try:
    with open(CSS_PATH) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    st.markdown(
        "<style>.main .block-container { max-width:700px; padding:1rem 1.5rem; }" +
        ".title { text-align:center; font-size:2.5rem; font-weight:700; }" +
        ".play-box { border-left:4px solid #28a745; background:#e6f4ea; padding:1rem; " +
        "border-radius:6px; margin-bottom:1rem; }</style>",
        unsafe_allow_html=True
    )
# Title
st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

df = load_data()

# Sidebar Favorites
st.sidebar.header("⭐ Favorites")
sheet = get_gsheet()
fav_ids = []
if sheet:
    try:
        fav_ids = sheet.worksheet(WORKSHEET_FAVORITES).col_values(1)
    except Exception:
        pass
st.sidebar.write(fav_ids)

# Controls
st.markdown("### Select Down, Distance & Coverage")
col1, col2, col3 = st.columns(3)
with col1:
    down = st.radio("Down", ["1st","2nd","3rd"], horizontal=True)
with col2:
    distance = st.radio("Distance", ["short","medium","long"], horizontal=True)
with col3:
    coverage = st.selectbox("Coverage", ["", "man", "zone", "blitz"])

# Call a play
def call_play():
    play = suggest_play(df, down, distance, coverage)
    st.session_state.current_play = play
if st.button("🟢 Call a Play", key="call"): call_play()

# Display play
play = st.session_state.get('current_play')
if play is not None:
    st.markdown(
        f"<div class='play-box'><strong>Formation:</strong> {play['Formation']}<br>" +
        f"<strong>Play:</strong> {play['Play Name']}</div>", unsafe_allow_html=True
    )
    st.image(f"https://myrepo/plays/{play['Play ID']}.png", caption=play['Play Name'])
    c1, c2, c3 = st.columns([1,1,1], gap="small")
    with c1:
        if st.button("✅ Successful", key="succ"):
            pending_results.append([datetime.now().isoformat(), play['Play Name'], down, distance, coverage, True])
            st.session_state.current_play = None
    with c2:
        if st.button("❌ Unsuccessful", key="fail"):
            pending_results.append([datetime.now().isoformat(), play['Play Name'], down, distance, coverage, False])
            st.session_state.current_play = None
    with c3:
        if st.button("🌟 Favorite", key="fav"):
            pending_favorites.append([play['Play ID']])
            st.sidebar.write(play['Play ID'])
    with st.expander("Details"):
        st.write(f"**Adjustments**: {play.get('Route Adjustments','')}")
        st.write(f"**Progression**: {play.get('Progression','')}")
        st.write(f"**Notes**: {play.get('Notes','')}")

# Analytics
with st.expander("📊 Success Rate by Category"):
    try:
        logs = pd.DataFrame(sheet.worksheet(WORKSHEET_RESULTS).get_all_records())
        stats = logs.groupby('Play Type Category').agg(
            success_rate=('Successful','mean'), count=('Successful','size')
        ).sort_values('count', ascending=False)
        fig, ax = plt.subplots()
        ax.bar(stats.index, stats['success_rate'])
        ax.set_ylabel('Success Rate')
        ax.set_xticklabels(stats.index, rotation=45, ha='right')
        st.pyplot(fig)
    except Exception:
        st.write("Analytics unavailable.")

# (Keyboard shortcuts removed due to Streamlit sandboxing limitations)

# Flush logs button
if st.button("Flush Logs"):
    flush_buffers()
if st.button("Flush Logs"):
    flush_buffers()
if st.button("Flush Logs"):
    flush_buffers()
