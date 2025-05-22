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
    body, html, .main, .block-container {
        padding: 0 !important;
        margin: 0 !important;
        max-width: 100vw !important;
        overflow-x: hidden !important;
    }
    .button-row-container {
        display: flex;
        justify-content: center;
        width: 100%;
        margin-bottom: 1rem;
    }
    .button-row-container > div {
        display: flex;
        flex-direction: row;
        flex-wrap: nowrap;
        gap: 0.5rem;
        width: 100%;
        max-width: 700px;
        justify-content: space-between;
    }
    .button-row {
        display: flex;
        flex-direction: row;
        justify-content: center;
        gap: 0.5rem;
        flex-wrap: nowrap;
        margin-bottom: 1rem;
    }
    .button-row button {
        flex: 1 1 45%;
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
        margin-top: 1rem;
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
    </style>
""", unsafe_allow_html=True)

st.title("🏈 Play Caller Assistant")

col1, col2 = st.columns([1, 1], gap="small")
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

# --- Filtering logic ---
def filter_by_depth(df, down, distance):
    if down == "1st":
        return df
    if down == "2nd":
        if distance == "long":
            return df[df["Play Depth"].str.contains("medium|long", case=False, na=False)]
        else:
            return df
    if down == "3rd":
        if distance == "long":
            return df[df["Play Depth"].str.contains("medium|long", case=False, na=False)]
        else:
            return df
    return df
