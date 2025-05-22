import streamlit as st
import pandas as pd
import numpy as np
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Google Sheets Connection ---
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
    return client.open("PlayCaller Logs")

sheet = connect_to_gsheet()
results_sheet = sheet.worksheet("results")
fav_sheet = sheet.worksheet("favorite_plays")

# --- Session State Defaults ---
if "current_play" not in st.session_state:
    st.session_state.current_play = None
if "favorites" not in st.session_state:
    st.session_state.favorites = set()
if "selected_down" not in st.session_state:
    st.session_state.selected_down = "1st"
if "selected_distance" not in st.session_state:
    st.session_state.selected_distance = "short"
if "coverage" not in st.session_state:
    st.session_state.coverage = 0.5

# --- Data Loading ---
@st.cache_data(show_spinner=False)

def load_data():
    df = pd.read_excel("play_database_cleaned_download.xlsx")
    rpo_keywords = ["rpo", "screen"]
    df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
        lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
    )
    return df

df = load_data()

# --- Styling ---
st.markdown("""
<style>
.main .block-container {
    max-width: 700px;
    padding: 1rem 1.5rem;
}
.title {
    text-align: center;
    font-size: 2.5rem;
    margin-top: 1rem;
    margin-bottom: 1.5rem;
    font-weight: 700;
}
.controls {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin-bottom: 1rem;
}
.controls > div {
    flex: 1;
}
.controls .buttons {
    display: flex;
    justify-content: space-around;
    margin-top: 0.5rem;
}
.stButton > button {
    flex: 1;
    margin: 0 0.25rem;
    font-size: 1.1rem !important;
    padding: 0.6rem;
}
.play-box {
    border-left: 4px solid #28a745;
    background-color: #e6f4ea;
    padding: 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

# --- App Title ---
st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

# --- Controls Section ---
# Inline buttons for Down and Distance, along with Coverage slider
st.markdown("<div class='controls'>", unsafe_allow_html=True)
# Down buttons inline
st.markdown("<div><strong>Down</strong></div>", unsafe_allow_html=True)
down_cols = st.columns(3)
for i, d in enumerate(["1st","2nd","3rd"]):
    if down_cols[i].button(d, key=f"down_{d}", use_container_width=True):
        st.session_state.selected_down = d
# Distance buttons inline
st.markdown("<div><strong>Distance</strong></div>", unsafe_allow_html=True)
dist_cols = st.columns(3)
for i, d in enumerate(["short","medium","long"]):
    if dist_cols[i].button(d, key=f"dist_{d}", use_container_width=True):
        st.session_state.selected_distance = d
# Coverage slider inline
st.markdown("<div><strong>Coverage</strong></div>", unsafe_allow_html=True)
coverage = st.slider("", 0.0, 1.0, st.session_state.coverage, 0.05, key="coverage")
st.markdown("</div>", unsafe_allow_html=True)

# --- Suggest Play Button ---
if st.button("🟢 Call a Play"):
    st.session_state.current_play = None  # reset
    play = None
    # Suggest play logic
    subset = df.copy()
    if st.session_state.selected_down in ["2nd", "3rd"] and st.session_state.selected_distance == "long":
        subset = subset[subset["Play Depth"].str.contains("medium|long", case=False, na=False)]
    weights = {
        ("1st", None): {"dropback":0.4, "rpo":0.3, "run_option":0.3},
        ("2nd","long"): {"dropback":0.7, "rpo":0.3, "run_option":0.0},
        ("3rd","long"): {"dropback":1.0, "rpo":0.0, "run_option":0.0}
    }.get((st.session_state.selected_down, st.session_state.selected_distance),
          {"dropback":0.5, "rpo":0.3, "run_option":0.2})
    cats = [c for c in weights if not subset[subset["Play Type Category Cleaned"]==c].empty]
    if cats:
        cat = random.choices(cats, weights=[weights[c] for c in cats], k=1)[0]
        pool = subset[subset["Play Type Category Cleaned"]==cat].copy()
        if cat == "dropback":
            man = pool["Effective vs Man"].fillna(0.5)
            zone = pool["Effective vs Zone"].fillna(0.5)
            pool["Score"] = (1-st.session_state.coverage)*man + st.session_state.coverage*zone
        else:
            pool["Score"] = 0.5
        top = pool.nlargest(10, "Score")
        if not top.empty:
            st.session_state.current_play = top.sample(1).iloc[0]

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
            results_sheet.append_row([datetime.now().isoformat(), play['Play Name'],
                                      st.session_state.selected_down, st.session_state.selected_distance,
                                      st.session_state.coverage, True])
            st.session_state.current_play = None
    with col2:
        if st.button("❌ Unsuccessful"):
            results_sheet.append_row([datetime.now().isoformat(), play['Play Name'],
                                      st.session_state.selected_down, st.session_state.selected_distance,
                                      st.session_state.coverage, False])
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
