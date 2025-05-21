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
    sheet = client.open("PlayCaller Logs")
    return sheet

sheet = connect_to_gsheet()
results_sheet = sheet.worksheet("results")
fav_sheet = sheet.worksheet("favorite_plays")

# --- Session state defaults ---
if "current_play" not in st.session_state:
    st.session_state.current_play = None

# --- Load and prepare data ---
@st.cache_data
def load_data():
    df = pd.read_excel("play_database_cleaned_download.xlsx")  # Assign a unique ID based on row index
    return df

df = load_data()

rpo_keywords = ["rpo", "screen"]
df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
    lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
)

# --- UI layout and styling ---
st.markdown("""
    <style>
    .button-row {
        display: flex;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1rem;
    }
    .button-row button {
        flex: 1;
        font-size: 0.9rem !important;
    }
    html, body, .main {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }
    h1 {
        font-size: 1.8rem !important;
        margin-bottom: 1rem !important;
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
    .bg-footer {
        text-align: center;
        margin-top: 3rem;
    }
    .highlight-box {
        border-left: 5px solid #28a745;
        background-color: #d4edda;
        padding: 12px 15px;
        border-radius: 6px;
        margin: 2rem auto 1rem auto;
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
    </style>
""", unsafe_allow_html=True)

st.title("🏈 Play Caller Assistant")

# Down selector uses the staged value, only updated after success/fail
col1, col2 = st.columns([1, 1])
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

coverage_label = (
    "Strictly Man" if coverage == 0 else
    "Strictly Zone" if coverage == 1 else
    "Mainly Man" if coverage < 0.5 else
    "Mainly Zone" if coverage > 0.5 else
    "Balanced"
)

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

# --- Favorite Play Management ---
def load_favorites():
    try:
        fav_ids = fav_sheet.col_values(1)
        return set(fav_ids)
    except:
        return set()

def add_favorite(play_id):
    try:
        fav_sheet.append_row([play_id])
        st.toast("🌟 Added to favorites!")
    except Exception as e:
        st.error(f"Could not add favorite: {e}")

favorites = load_favorites()

# --- Log play ---
def log_play_result(play_name, down, distance, coverage, success):
    timestamp = datetime.now().isoformat()
    row = [timestamp, play_name, down, distance, coverage, success]
    try:
        results_sheet.append_row(row)
        st.toast(f"Play logged as {'successful' if success else 'unsuccessful'}.", icon="👏")
        st.session_state.current_play = None
    except Exception as e:
        st.error(f"❌ Failed to write to sheet: {e}", icon="❌")

if st.button("🟢Call a Play", key="call_play"):
    st.session_state.current_play = suggest_play()

play = st.session_state.current_play
if play is not None:
    st.markdown("""<div class=\"highlight-box\" style=\"margin-top: 0.5rem !important;\">
            <div class="highlight-flex">
                <div class="highlight-item">
                    <strong>Formation:</strong><br>{}
                </div>
                <div class="highlight-item">
                    <strong>Play Name:</strong><br>{}
                </div>
            </div>
        </div>
    """.format(play['Formation'], play['Play Name']), unsafe_allow_html=True)

    st.markdown("<div class='button-row'>", unsafe_allow_html=True)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("✅ Successful", key="success_btn", help="Mark this play as successful"):
            log_play_result(play["Play Name"], down, distance, coverage, True)
    with col2:
        if st.button("❌ Unsuccessful", key="fail_btn", help="Mark this play as unsuccessful"):
            log_play_result(play["Play Name"], down, distance, coverage, False)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(f"**Adjustments**: {play['Route Adjustments']}", unsafe_allow_html=True)
    st.markdown(f"**Progression**: {play['Progression']}", unsafe_allow_html=True)
    st.markdown(f"**Notes**: {play['Notes']}", unsafe_allow_html=True)

    if play["Play ID"] not in favorites:
        if st.button("🌟 Add to Favorites"):
            add_favorite(play["Play ID"])
    else:
        st.info("⭐ Favorited play (ID match)")

# --- Footer ---
st.markdown("""
    <div class="bg-footer">
        <img src="https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png" width="260">
    </div>
""", unsafe_allow_html=True)
