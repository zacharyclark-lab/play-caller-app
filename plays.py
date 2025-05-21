import streamlit as st
import pandas as pd
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
    sheet = client.open("PlayCaller Logs").worksheet("results")
    return sheet

sheet = connect_to_gsheet()

def log_play_result(play_name, down, distance, coverage, success):
    timestamp = datetime.now().isoformat()
    row = [timestamp, play_name, down, distance, coverage, success]
    try:
        sheet.append_row(row)
        st.success(f"✅ Logged: {row}")
    except Exception as e:
        st.error(f"❌ Failed to write to sheet: {e}")

# Load and prepare data
@st.cache_data
def load_data():
    return pd.read_excel("play_database_cleaned_download.xlsx")

df = load_data()

rpo_keywords = ["rpo", "screen"]
df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
    lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
)

# --- UI layout and styling ---
st.markdown("""
    <style>
    .slider-labels {
        display: flex;
        justify-content: space-between;
        font-size: 0.85em;
        color: #6c757d;
        margin-top: -10px;
        margin-bottom: 5px;
        padding: 0 5px;
    }
    .bg-footer {
        text-align: center;
        margin-top: 3rem;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🏈 Play Caller Assistant")

col1, col2 = st.columns(2)
with col1:
    down = st.selectbox("Select Down", ["1st", "2nd", "3rd"])
with col2:
    distance = st.selectbox("Select Distance", ["short", "medium", "long"])

coverage = st.slider("Defensive Coverage Tendency", 0.0, 1.0, 0.5, 0.01)

st.markdown("""
    <div class="slider-labels">
        <span>Strictly Man</span>
        <span>Mainly Man</span>
        <span>Balanced</span>
        <span>Mainly Zone</span>
        <span>Strictly Zone</span>
    </div>
""", unsafe_allow_html=True)

coverage_label = (
    "Strictly Man" if coverage == 0 else
    "Strictly Zone" if coverage == 1 else
    "Mainly Man" if coverage < 0.5 else
    "Mainly Zone" if coverage > 0.5 else
    "Balanced"
)

st.caption(f"Tendency: {coverage_label}")

# --- Play selection logic ---
def suggest_play():
    subset = df[df["Play Depth"].str.contains(distance, case=False, na=False)].copy()

    if down == "1st":
        weights = {"dropback": 0.4, "rpo": 0.3, "run_option": 0.3}
    elif down == "2nd" and distance == "long":
        weights = {"dropback": 0.7, "rpo": 0.3, "run_option": 0.0}
    elif down == "3rd" and distance == "long":
        weights = {"dropback": 1.0, "rpo": 0.0, "run_option": 0.0}
    else:
        weights = {"dropback": 0.5, "rpo": 0.3, "run_option": 0.2}

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

    def score(row):
        if category == "dropback":
            man = row["Effective vs Man"] if pd.notnull(row["Effective vs Man"]) else 0.5
            zone = row["Effective vs Zone"] if pd.notnull(row["Effective vs Zone"]) else 0.5
            return (1 - coverage) * man + coverage * zone
        else:
            return 0.5

    pool["Score"] = pool.apply(score, axis=1)
    top = pool.sort_values("Score", ascending=False).head(10)
    return top.sample(1).iloc[0] if not top.empty else None

# --- Session state to preserve play across reruns ---
if "current_play" not in st.session_state:
    st.session_state.current_play = None

if st.button("📟 Call a Play"):
    st.session_state.current_play = suggest_play()

play = st.session_state.current_play
if play is not None:
    st.subheader(f"📋 {play['Play Name']} ({play['Play Type Category']})")
    st.markdown(f"**Formation**: {play['Formation']}")
    st.markdown(f"**Play Type**: {play['Play Type']}")
    st.markdown(f"**Depth**: {play['Play Depth']}")
    st.markdown(f"**Primary Read**: {play['Primary Read']}")
    st.markdown(f"**Progression**: {play['Progression']}")
    st.markdown(f"**Adjustments**: {play['Route Adjustments']}")
    st.markdown(f"**Notes**: {play['Notes']}")
    st.markdown(f"**Match Score**: {round(play['Score'], 2)}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Mark as Successful"):
            log_play_result(play["Play Name"], down, distance, coverage, True)
            st.success("✅ Marked as successful and logged.")
    with col2:
        if st.button("❌ Mark as Unsuccessful"):
            log_play_result(play["Play Name"], down, distance, coverage, False)
            st.info("❌ Marked as unsuccessful and logged.")

# --- Footer ---
st.markdown("""
    <div class="bg-footer">
        <img src="https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png" width="260">
    </div>
""", unsafe_allow_html=True)
