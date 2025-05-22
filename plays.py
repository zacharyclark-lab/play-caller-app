import streamlit as st
import pandas as pd
import numpy as np
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Google Sheets Connection ---
@st.experimental_singleton(ttl=3600)
def connect_to_gsheet():
    """
    Connect to the Google Sheets document using service account credentials.
    Cached as a singleton for up to 1 hour (3600 seconds).
    Includes error handling to provide user feedback on failure.
    """
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            st.secrets["gcp_service_account"], scope
        )
        client = gspread.authorize(creds)
        return client.open("PlayCaller Logs")
    except Exception as e:
        st.error(f"Unable to connect to Google Sheets: {e}")
        return None

# Attempt connection and halt if unsuccessful
sheet = connect_to_gsheet()
if sheet is None:
    st.stop()

results_sheet = sheet.worksheet("results")
fav_sheet = sheet.worksheet("favorite_plays")

# --- Session State Defaults ---
# Initialize defaults concisely using setdefault
st.session_state.setdefault("current_play", None)
st.session_state.setdefault("favorites", set())
st.session_state.setdefault("selected_down", "1st")
st.session_state.setdefault("selected_distance", "short")
st.session_state.setdefault("coverage", 0.5)

# --- Data Loading ---
@st.cache_data(show_spinner=False)
def load_data():
    """
    Load and preprocess play data from Excel, cleaning RPO keywords.
    """
    df = pd.read_excel("play_database_cleaned_download.xlsx")
    rpo_keywords = ["rpo", "screen"]
    df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
        lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
    )
    return df

df = load_data()

# --- Styling ---
def load_styles(css_path: str = "styles.css"):
    """
    Load CSS styles from an external file for cleaner maintenance.
    Place your CSS definitions in styles.css in the same directory.
    """
    try:
        with open(css_path) as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning(f"CSS file '{css_path}' not found. Using default Streamlit theme.")

load_styles()

# --- App Title ---
st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

# --- Controls Section ---
col1, col2, col3 = st.columns(3)
with col1:
    st.radio("Down", ["1st","2nd","3rd"],
             index=["1st","2nd","3rd"].index(st.session_state.selected_down),
             key="selected_down")
with col2:
    st.radio("Distance", ["short","medium","long"],
             index=["short","medium","long"].index(st.session_state.selected_distance),
             key="selected_distance")
with col3:
    st.slider("Coverage", 0.0, 1.0, st.session_state.coverage,
              0.05, key="coverage")

# --- Suggest Play Logic ---
def suggest_play(df, down, distance, coverage):
    subset = df.copy()
    if down in ["2nd", "3rd"] and distance == "long":
        subset = subset[
            subset["Play Depth"].str.contains("medium|long", case=False, na=False)
        ]
    weights = {
        ("1st", None):   {"dropback": 0.4, "rpo": 0.3, "run_option": 0.3},
        ("2nd","long"): {"dropback": 0.7, "rpo": 0.3, "run_option": 0.0},
        ("3rd","long"): {"dropback": 1.0, "rpo": 0.0, "run_option": 0.0}
    }.get((down, distance), {"dropback": 0.5, "rpo": 0.3, "run_option": 0.2})
    candidates = [c for c in weights if not subset[
        subset["Play Type Category Cleaned"]==c
    ].empty]
    if not candidates:
        return None
    cat = random.choices(candidates, weights=[weights[c] for c in candidates], k=1)[0]
    pool = subset[subset["Play Type Category Cleaned"]==cat].copy()
    if cat == "dropback":
        man = pool["Effective vs Man"].fillna(0.5)
        zone = pool["Effective vs Zone"].fillna(0.5)
        pool["Score"] = (1-coverage)*man + coverage*zone
    else:
        pool["Score"] = 0.5
    top = pool.nlargest(10, "Score")
    return top.sample(1).iloc[0] if not top.empty else None

# --- Main Interaction ---
if st.button("🟢 Call a Play"):
    st.session_state.current_play = suggest_play(
        df,
        st.session_state.selected_down,
        st.session_state.selected_distance,
        st.session_state.coverage
    )

# --- Display Selected Play ---
play = st.session_state.current_play
if play is not None:
    st.markdown(
        f"<div class='play-box'><strong>Formation:</strong> {play['Formation']}<br>"
        f"<strong>Play:</strong> {play['Play Name']}</div>",
        unsafe_allow_html=True
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Successful"):
            results_sheet.append_row([
                datetime.now().isoformat(), play['Play Name'],
                st.session_state.selected_down,
                st.session_state.selected_distance,
                st.session_state.coverage, True
            ])
            st.session_state.current_play = None
    with col2:
        if st.button("❌ Unsuccessful"):
            results_sheet.append_row([
                datetime.now().isoformat(), play['Play Name'],
                st.session_state.selected_down,
                st.session_state.selected_distance,
                st.session_state.coverage, False
            ])
            st.session_state.current_play = None
    if st.button("🌟 Add to Favorites"):
        fav_sheet.append_row([play['Play ID']])
        st.session_state.favorites.add(play['Play ID'])

    with st.expander("Details"):
        st.write(f"**Adjustments**: {play.get('Route Adjustments','')}")
        st.write(f"**Progression**: {play.get('Progression','')}")
        st.write(f"**Notes**: {play.get('Notes','')}")

# --- Footer ---
st.markdown(
    "<div class='button-row-flex'><img src='https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png' width='260'></div>",
    unsafe_allow_html=True
)
