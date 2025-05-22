import streamlit as st
import pandas as pd
import numpy as np
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Connect to Google Sheet ---
@st.cache_resource

def connect_to_gsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"], scope
    )
    client = gspread.authorize(creds)
    sheet = client.open("PlayCaller Logs")
    return sheet

sheet = connect_to_gsheet()
results_sheet = sheet.worksheet("results")
fav_sheet = sheet.worksheet("favorite_plays")

# --- Session state defaults ---
if "current_play" not in st.session_state:
    st.session_state.current_play = None
if "favorites" not in st.session_state:
    st.session_state.favorites = set()

# --- Load and prepare data ---
@st.cache_data

def load_data():
    df = pd.read_excel("play_database_cleaned_download.xlsx")
    rpo_keywords = ["rpo", "screen"]
    df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
        lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
    )
    return df

df = load_data()

# --- UI layout and styling ---
st.markdown("""
    <style>
    html, body, .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }
    .button-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 1rem;
        gap: 0.5rem;
        flex-wrap: nowrap;
    }
    .slider-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.85em;
        color: #6c757d;
        margin-top: -10px;
        margin-bottom: 5px;
        padding: 0 5px;
    }
    .highlight-box {
        border-left: 5px solid #28a745;
        background-color: #d4edda;
        padding: 12px 15px;
        border-radius: 6px;
        margin: 0.5rem auto;
        font-size: 0.95em;
        max-width: 700px;
    }
    .highlight-flex {
        display: flex;
        flex-wrap: wrap;
        justify-content: space-between;
        gap: 10px;
    }
    .highlight-item {
        min-width: 120px;
        flex: 1;
    }
    .bg-footer {
        text-align: center;
        margin-top: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("\ud83c\udfc8 Play Caller Assistant")

col1, col2 = st.columns(2)
with col1:
    down = st.selectbox("Select Down", ["1st", "2nd", "3rd"], key="down")
with col2:
    distance = st.selectbox("Select Distance", ["short", "medium", "long"], key="distance")

coverage = st.slider("Defensive Coverage Tendency", 0.0, 1.0, 0.5, 0.01, key="coverage")

st.markdown("""
    <div class="slider-labels">
        <span>Strictly Man</span>
        <span>Mainly Man</span>
        <span>Balanced</span>
        <span>Mainly Zone</span>
        <span>Strictly Zone</span>
    </div>
""", unsafe_allow_html=True)

# --- Play Suggestion Logic ---
def filter_by_depth(df, down, distance):
    if down == "1st":
        return df
    if down == "2nd" and distance == "long":
        return df[df["Play Depth"].str.contains("medium|long", case=False, na=False)]
    if down == "3rd" and distance == "long":
        return df[df["Play Depth"].str.contains("medium|long", case=False, na=False)]
    return df

def suggest_play():
    subset = filter_by_depth(df, down, distance)
    weights = {
        ("1st", None): {"dropback": 0.4, "rpo": 0.3, "run_option": 0.3},
        ("2nd", "long"): {"dropback": 0.7, "rpo": 0.3, "run_option": 0.0},
        ("3rd", "long"): {"dropback": 1.0, "rpo": 0.0, "run_option": 0.0},
    }.get((down, distance), {"dropback": 0.5, "rpo": 0.3, "run_option": 0.2})

    available = [cat for cat in weights if not subset[subset["Play Type Category Cleaned"] == cat].empty]
    if not available:
        return None

    category = random.choices(
        population=available,
        weights=[weights[cat] for cat in available],
        k=1
    )[0]

    pool = subset[subset["Play Type Category Cleaned"] == category].copy()
    if pool.empty:
        return None

    if category == "dropback":
        man = pool["Effective vs Man"].fillna(0.5)
        zone = pool["Effective vs Zone"].fillna(0.5)
        pool["Score"] = (1 - coverage) * man + coverage * zone
    else:
        pool["Score"] = 0.5

    top = pool.nlargest(10, "Score")
    return top.sample(1).iloc[0] if not top.empty else None

# --- Google Sheet Interaction ---
def load_favorites():
    try:
        return set(fav_sheet.col_values(1))
    except:
        return set()

def add_favorite(play_id):
    try:
        fav_sheet.append_row([play_id])
        st.session_state.favorites.add(play_id)
        st.toast("\ud83c\udf1f Added to favorites!")
    except Exception as e:
        st.error(f"Could not add favorite: {e}")

def log_play_result(play_name, down, distance, coverage, success):
    row = [datetime.now().isoformat(), play_name, down, distance, coverage, success]
    try:
        results_sheet.append_row(row)
        st.toast(f"Play logged as {'successful' if success else 'unsuccessful' }.", icon="\ud83d\udc4f")
        st.session_state.current_play = None
    except Exception as e:
        st.error(f"\u274c Failed to write to sheet: {e}", icon="\u274c")

# --- Main Interaction ---
if st.button("\ud83d\udfe2 Call a Play", key="call_play"):
    st.session_state.current_play = suggest_play()

play = st.session_state.current_play
if play is not None:
    st.markdown(f"""
    <div class=\"highlight-box\">
        <div class=\"highlight-flex\">
            <div class=\"highlight-item\"><strong>Formation:</strong><br>{play['Formation']}</div>
            <div class=\"highlight-item\"><strong>Play Name:</strong><br>{play['Play Name']}</div>
        </div>
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("\u2705 Successful", key="success_btn"):
            log_play_result(play["Play Name"], down, distance, coverage, True)
    with col2:
        if st.button("\u274c Unsuccessful", key="fail_btn"):
            log_play_result(play["Play Name"], down, distance, coverage, False)

    with st.expander("More Details"):
        st.markdown(f"**Adjustments**: {play['Route Adjustments']}")
        st.markdown(f"**Progression**: {play['Progression']}")
        st.markdown(f"**Notes**: {play['Notes']}")

    if play["Play ID"] not in st.session_state.favorites:
        if st.button("\ud83c\udf1f Add to Favorites"):
            add_favorite(play["Play ID"])
    else:
        st.info("\u2b50 Favorited play (ID match)")

st.markdown("""
    <div class="bg-footer">
        <img src="https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png" width="260">
    </div>
""", unsafe_allow_html=True)
