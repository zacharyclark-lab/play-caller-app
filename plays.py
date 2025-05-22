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
    html, body {
        padding: 0;
        margin: 0;
        background-color: #f5f7fa;
        font-family: 'Segoe UI', sans-serif;
    }
    .main, .block-container {
        max-width: 900px !important;
        margin: 0 auto !important;
        padding: 1rem 0;
    }
    .title {
        text-align: center;
        font-size: 2.5rem;
        margin: 1.5rem 0;
        font-weight: bold;
    }
    .section {
        padding: 1rem;
        background-color: white;
        border-radius: 8px;
        margin: 0.75rem auto;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    }
    .highlight-box {
        border-left: 4px solid #28a745;
        background-color: #e6f4ea;
        padding: 12px;
        border-radius: 8px;
        font-size: 1rem;
        margin-top: 1rem;
    }
    .highlight-flex {
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
    }
    .button-row-flex {
        display: flex;
        justify-content: center;
        gap: 1rem;
        margin-top: 1rem;
    }
    .stButton > button {
        font-size: 1.1rem !important;
        padding: 0.5rem 1.5rem !important;
        border-radius: 6px !important;
    }
    @media (max-width: 768px) {
        .main, .block-container { padding: 0.5rem !important; }
        .button-row-flex { flex-direction: column; }
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

# --- Controls Section ---
# Centered controls container
st.markdown("<div class='section' style='max-width:600px; margin:0 auto; padding:0.75rem;'>", unsafe_allow_html=True)
# Three segments: Downs, Distance, Coverage
seg_cols = st.columns([1,1,2])
# Downs buttons
with seg_cols[0]:
    st.markdown("#### Down")
    btns = st.columns(3)
    for i, d in enumerate(["1st","2nd","3rd"]):
        if btns[i].button(d, key=f"down_{d}", use_container_width=True):
            st.session_state.selected_down = d
    st.caption(f"Selected: {st.session_state.selected_down}")
# Distance buttons
with seg_cols[1]:
    st.markdown("#### Distance")
    btns = st.columns(3)
    for i, d in enumerate(["short","medium","long"]):
        if btns[i].button(d, key=f"dist_{d}", use_container_width=True):
            st.session_state.selected_distance = d
    st.caption(f"Selected: {st.session_state.selected_distance}")
# Coverage slider
with seg_cols[2]:
    st.markdown("#### Coverage")
    coverage = st.slider("", 0.0, 1.0, st.session_state.get('coverage', 0.5), 0.01, key="coverage", use_container_width=True)
    st.caption(f"Coverage: {coverage:.2f}")
st.markdown("</div>", unsafe_allow_html=True)
# --- Play Suggestion Logic ---", unsafe_allow_html=True)
# First row: Down buttons and Distance buttons side-by-side
row1 = st.columns([1,1,2])
# Downs in first segment
with row1[0]:
    st.markdown("#### Down")
    btn_cols = st.columns(3)
    for i, d in enumerate(["1st","2nd","3rd"]):
        if btn_cols[i].button(d, key=f"down_btn_{d}", use_container_width=True):
            st.session_state.selected_down = d
    st.caption(f"{st.session_state.selected_down}")
# Distance in next segment
with row1[1]:
    st.markdown("#### Distance")
    btn_cols = st.columns(3)
    for i, d in enumerate(["short","medium","long"]):
        if btn_cols[i].button(d, key=f"dist_btn_{d}", use_container_width=True):
            st.session_state.selected_distance = d
    st.caption(f"{st.session_state.selected_distance}")
# Coverage slider in larger segment
with row1[2]:
    st.markdown("#### Coverage")
    coverage = st.slider("",0.0,1.0,st.session_state.get('coverage',0.5),0.01,key="coverage")
    st.caption(f"{coverage:.2f}")
st.markdown("</div>", unsafe_allow_html=True)

# --- Play Suggestion Logic ---, unsafe_allow_html=True)

# --- Play Suggestion Logic ---
def filter_by_depth(df, down, distance):
    if down == "1st": return df
    if down in ["2nd","3rd"] and distance == "long":
        return df[df["Play Depth"].str.contains("medium|long", case=False, na=False)]
    return df

def suggest_play():
    down = st.session_state.selected_down
    distance = st.session_state.selected_distance
    subset = filter_by_depth(df, down, distance)
    weights = {
        ("1st", None): {"dropback":0.4,"rpo":0.3,"run_option":0.3},
        ("2nd","long"): {"dropback":0.7,"rpo":0.3,"run_option":0.0},
        ("3rd","long"): {"dropback":1.0,"rpo":0.0,"run_option":0.0},
    }.get((down,distance),{"dropback":0.5,"rpo":0.3,"run_option":0.2})
    available=[c for c in weights if not subset[subset["Play Type Category Cleaned"]==c].empty]
    if not available: return None
    category=random.choices(available,weights=[weights[c] for c in available],k=1)[0]
    pool=subset[subset["Play Type Category Cleaned"]==category].copy()
    if category=="dropback":
        man=pool["Effective vs Man"].fillna(0.5)
        zone=pool["Effective vs Zone"].fillna(0.5)
        pool["Score"]=(1-st.session_state.coverage)*man+st.session_state.coverage*zone
    else:
        pool["Score"]=0.5
    top=pool.nlargest(10,"Score")
    return top.sample(1).iloc[0] if not top.empty else None

# --- Google Sheet Interaction ---
def load_favorites():
    try: return set(fav_sheet.col_values(1))
    except: return set()

def add_favorite(play_id):
    try:
        fav_sheet.append_row([play_id])
        st.session_state.favorites.add(play_id)
        st.toast("🌟 Added to favorites!")
    except Exception as e:
        st.error(f"Could not add favorite: {e}")

def log_play_result(play_name, down, distance, coverage, success):
    row=[datetime.now().isoformat(),play_name,down,distance,coverage,success]
    try:
        results_sheet.append_row(row)
        st.toast(f"Play logged as {'successful' if success else 'unsuccessful'}.",icon="👏")
        st.session_state.current_play=None
    except Exception as e:
        st.error(f"❌ Failed to write to sheet: {e}")

# --- Main Interaction ---
if st.button("🟢 Call a Play",key="call_play"):
    st.session_state.current_play=suggest_play()

play=st.session_state.current_play
if play is not None:
    st.markdown(f"""
    <div class='section highlight-box'>
        <div class='highlight-flex'>
            <div><strong>Formation:</strong> {play['Formation']}</div>
            <div><strong>Play Name:</strong> {play['Play Name']}</div>
        </div>
    </div>""",unsafe_allow_html=True)
    st.markdown("<div class='button-row-flex'>",unsafe_allow_html=True)
    col1,col2=st.columns(2)
    with col1:
        if st.button("✅ Successful",key="success_btn"):
            log_play_result(play['Play Name'], st.session_state.selected_down, st.session_state.selected_distance, st.session_state.coverage,True)
    with col2:
        if st.button("❌ Unsuccessful",key="fail_btn"):
            log_play_result(play['Play Name'], st.session_state.selected_down, st.session_state.selected_distance, st.session_state.coverage,False)
    st.markdown("</div>",unsafe_allow_html=True)
    with st.expander("More Details"):
        st.write(f"**Adjustments**: {play.get('Route Adjustments','')}")
        st.write(f"**Progression**: {play.get('Progression','')}")
        st.write(f"**Notes**: {play.get('Notes','')}")
    if play['Play ID'] not in st.session_state.favorites:
        if st.button("🌟 Add to Favorites"):
            add_favorite(play['Play ID'])
    else:
        st.info("⭐ Favorited play")

st.markdown("""
<div class=\"bg-footer\">
    <img src=\"https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png\" width=\"260\">
</div>
""",unsafe_allow_html=True)
