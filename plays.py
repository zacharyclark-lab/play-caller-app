import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Google Sheets Connection ---
@st.cache_resource
def connect_to_gsheet():
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

sheet = connect_to_gsheet()
if sheet is None:
    st.stop()

results_sheet = sheet.worksheet("results")
fav_sheet = sheet.worksheet("favorite_plays")

# --- Session State Defaults ---
st.session_state.setdefault("current_play", None)
st.session_state.setdefault("favorites", set())
st.session_state.setdefault("selected_down", "1st")
st.session_state.setdefault("selected_distance", "short")

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
def load_styles(css_path: str = "styles.css"):
    default_css = """
    .main .block-container { max-width: 700px; padding: 1rem 1.5rem; }
    .title { text-align: center; font-size: 2.5rem; margin: 1rem 0; font-weight: 700; }
    .play-box { border-left: 4px solid #28a745; background-color: #e6f4ea;
                padding: 1rem; border-radius: 6px; margin-bottom: 1rem; }
    """
    try:
        with open(css_path) as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.markdown(f"<style>{default_css}</style>", unsafe_allow_html=True)

load_styles()

st.markdown("<div class='title'>🏈 Play Caller Assistant</div>", unsafe_allow_html=True)

# --- Sidebar Controls ---
st.sidebar.markdown("## ⚙️ Controls")
st.sidebar.checkbox("Enable Keyboard Mode", key="kb_mode")

# --- Main Controls ---
st.markdown("### Select Down & Distance")
st.radio("Down", ["1st", "2nd", "3rd"], key="selected_down", horizontal=True)
st.radio("Distance", ["short", "medium", "long"], key="selected_distance", horizontal=True)

# --- Suggest Play Logic ---
def suggest_play(df, down, distance, coverage=None):
    subset = df.copy()
    if down in ("2nd", "3rd") and distance == "long":
        subset = subset[subset["Play Depth"].str.contains("medium|long", case=False, na=False)]
    weight_table = {
        ("1st", "short"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("1st", "medium"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("1st", "long"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("2nd", "short"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("2nd", "medium"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("2nd", "long"): {"dropback": .6, "rpo": .3, "run_option": .1},
        ("3rd", "short"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("3rd", "medium"): {"dropback": .33, "rpo": .33, "run_option": .34},
        ("3rd", "long"): {"dropback": .85, "rpo": .075, "run_option": .075},
    }
    weights = weight_table.get((down, distance), {"dropback": .33, "rpo": .33, "run_option": .34})
    available = {cat: w for cat, w in weights.items() if not subset[subset["Play Type Category Cleaned"] == cat].empty}
    if not available:
        return None
    cats, wts = zip(*available.items())
    chosen_cat = random.choices(cats, weights=wts, k=1)[0]
    pool = subset[subset["Play Type Category Cleaned"] == chosen_cat]
    return pool.sample(1).iloc[0] if not pool.empty else None

# --- Keyboard-Mode Capture via Hidden Button ---
if st.session_state.kb_mode:
    # 1) Hidden trigger button
    st.button("", key="hotkey_trigger")

    # 2) JS to map keys to hidden button clicks and URL param
    components.html(
        """
<script>
window.addEventListener('keydown', e => {
    const k = e.key;
    if (['1','2','3'].includes(k)) {
        // click hidden Streamlit button
        const btn = window.parent.document.querySelector('button[k=\\"hotkey_trigger\\"]');
        if (btn) btn.click();
        // set URL param for key
        const url = new URL(window.parent.location);
        url.searchParams.set('hotkey', k);
        window.parent.history.replaceState(null, '', url);
    }
});
</script>
        """,
        height=0
    )

    # 3) On rerun, check URL param and invoke suggest_play
    params = st.query_params
    if 'hotkey' in params:
        k = params['hotkey'][0]
        st.experimental_set_query_params()  # clear param
        mapping = {'1':('1st','long'), '2':('2nd','long'), '3':('3rd','long')}
        if k in mapping:
            down, dist = mapping[k]
            st.session_state.selected_down = down
            st.session_state.selected_distance = dist
            st.session_state.current_play = suggest_play(df, down, dist)

# --- Main Interaction ---
if st.button("🟢 Call a Play"):
    st.session_state.current_play = suggest_play(
        df, st.session_state.selected_down, st.session_state.selected_distance
    )

# --- Display Selected Play ---
play = st.session_state.current_play
if play is not None:
    st.markdown(
        f"<div class='play-box'><strong>Formation:</strong> {play['Formation']}<br>"
        f"<strong>Play:</strong> {play['Play Name']}</div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ Successful"):
            results_sheet.append_row([
                datetime.now().isoformat(), play['Play Name'],
                st.session_state.selected_down, st.session_state.selected_distance, None, True
            ])
            st.session_state.current_play = None
    with col2:
        if st.button("❌ Unsuccessful"):
            results_sheet.append_row([
                datetime.now().isoformat(), play['Play Name'],
                st.session_state.selected_down, st.session_state.selected_distance, None, False
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
```python
st.markdown(
    "<div class='button-row-flex'><img src='https://raw.githubusercontent.com/zacharyclark-lab/play-caller-app/main/football.png' width='260'></div>",
    unsafe_allow_html=True
)
```
