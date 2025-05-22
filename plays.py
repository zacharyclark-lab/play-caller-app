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
if "selected_down" not in st.session_state:
    st.session_state.selected_down = "1st"
if "selected_distance" not in st.session_state:
    st.session_state.selected_distance = "short"

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

# --- App Styling ---
st.markdown("""
    <style>
    html, body, .main, .block-container {
        padding: 0;
        margin: 0;
        max-width: 100vw;
        overflow-x: hidden;
        background-color: #f5f7fa;
        font-family: 'Segoe UI', sans-serif;
    }
    .title {
        text-align: center;
        font-size: 3rem;
        margin: 2rem 0;
        font-weight: bold;
    }
    .section {
        padding: 1.5rem;
        background-color: white;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
    }
    .section h3 {
        margin-bottom: 1rem;
    }
    .highlight-box {
        border-left: 6px solid #28a745;
        background-color: #e6f4ea;
        padding: 16px 20px;
        border-radius: 10px;
        font-size: 1.1rem;
        margin-top: 1rem;
    }
    .highlight-flex {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
    }
    .highlight-item {
        flex: 1;
        margin-right: 2rem;
    }
    .button-row-flex {
        display: flex;
        justify-content: center;
        gap: 2rem;
        margin-top: 2rem;
    }
    .option-buttons {
        display: flex;
        gap: 0.5rem;
        justify-content: center;
        flex-wrap: wrap;
        margin-bottom: 1rem;
    }
    .option-button {
        padding: 0.75rem 1.5rem;
        font-size: 1.2rem;
        border: none;
        border-radius: 8px;
        background-color: #e9ecef;
        font-weight: 600;
        cursor: pointer;
    }
    .option-button.selected {
        background-color: #007bff;
        color: white;
        font-weight: bold;
    }
    button[kind="primary"], .stButton > button {
        font-size: 1.5rem !important;
        padding: 0.75rem 2rem !important;
        border-radius: 8px !important;
        font-weight: bold !important;
    }
    @media (max-width: 768px) {
        .option-buttons {
            flex-direction: column;
            align-items: center;
        }
        .button-row-flex {
            flex-direction: column;
        }
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

# --- Controls Section ---
st.markdown("<div class='section'>", unsafe_allow_html=True)
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("#### Down")
    st.markdown("<div class='option-buttons'>", unsafe_allow_html=True)
    for d in ["1st", "2nd", "3rd"]:
        button_class = "option-button selected" if st.session_state.selected_down == d else "option-button"
        if st.button(f"{d}", key=f"down_{d}"):
            st.session_state.selected_down = d
        st.markdown(f"<button disabled class='{button_class}'>{d}</button>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"Selected: **{st.session_state.selected_down}**")

with col2:
    st.markdown("#### Distance")
    st.markdown("<div class='option-buttons'>", unsafe_allow_html=True)
    for d in ["short", "medium", "long"]:
        button_class = "option-button selected" if st.session_state.selected_distance == d else "option-button"
        if st.button(f"{d}", key=f"dist_{d}"):
            st.session_state.selected_distance = d
        st.markdown(f"<button disabled class='{button_class}'>{d}</button>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown(f"Selected: **{st.session_state.selected_distance}**")

with col3:
    coverage = st.slider("#### Coverage", 0.0, 1.0, 0.5, 0.01, key="coverage")

st.markdown("</div>", unsafe_allow_html=True)

# (rest of the script remains unchanged)
