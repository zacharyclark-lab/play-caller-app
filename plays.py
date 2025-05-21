
import streamlit as st
import pandas as pd
import random

# Load the play database
@st.cache_data
def load_data():
    return pd.read_excel("play_database_cleaned_download.xlsx")

df = load_data()

# Page layout and background style
st.markdown(
    '''
    <style>
    body {
        background: linear-gradient(to bottom, #f5f7fa 0%, #c3d8dc 100%);
    }

    .main > div {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 90vh;
    }

    .play-box {
        background-color: white;
        padding: 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
        max-width: 700px;
        width: 100%;
        text-align: center;
    }

    .slider-labels {
        display: flex;
        justify-content: space-between;
        padding: 2px 10px 10px 10px;
        font-size: 0.85em;
        color: #6c757d;
        margin-top: -10px;
        margin-bottom: 5px;
    }

    .bg-footer {
        text-align: center;
        margin-top: 2rem;
    }
    </style>
    ''',
    unsafe_allow_html=True
)

# UI Section
with st.container():
    st.markdown('<div class="play-box">', unsafe_allow_html=True)
    st.title("🏈 Play Caller Assistant")

    col1, col2 = st.columns(2)
    with col1:
        down = st.selectbox("Select Down", ["1st", "2nd", "3rd"])
    with col2:
        distance = st.selectbox("Select Distance", ["short", "medium", "long"])

    coverage = st.slider("Defensive Coverage Tendency", 0.0, 1.0, 0.5, 0.01, key="coverage_slider")

    coverage_label = (
        "Strictly Man" if coverage == 0 else
        "Strictly Zone" if coverage == 1 else
        "Mainly Man" if coverage < 0.5 else
        "Mainly Zone" if coverage > 0.5 else
        "Balanced"
    )

    st.markdown(
        '''
        <div class="slider-labels">
            <span>Strictly Man</span>
            <span>Mainly Man</span>
            <span>Balanced</span>
            <span>Mainly Zone</span>
            <span>Strictly Zone</span>
        </div>
        ''',
        unsafe_allow_html=True
    )
    st.caption(f"Tendency: {coverage_label}")
    call_button = st.button("📟 Call a Play")
    st.markdown('</div>', unsafe_allow_html=True)

# Logic
def suggest_play():
    subset = df[df["Play Depth"].str.contains(distance, case=False, na=False)]

    # Clean up play type categories
    rpo_keywords = ["rpo", "screen"]
    df["Play Type Category Cleaned"] = df["Play Type Category"].apply(
        lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
    )
    subset["Play Type Category Cleaned"] = subset["Play Type Category"].apply(
        lambda x: "rpo" if any(k in str(x).lower() for k in rpo_keywords) else x
    )

    # Weights based on down/distance
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
        man = row.get("Effective vs Man", 0.5) or 0.5
        zone = row.get("Effective vs Zone", 0.5) or 0.5
        return (1 - coverage) * man + coverage * zone

    pool["Score"] = pool.apply(score, axis=1)
    top = pool.sort_values("Score", ascending=False).head(10)
    return top.sample(1).iloc[0] if not top.empty else None

# Display play call if button pressed
if call_button:
    play = suggest_play()
    if play is not None:
        st.markdown(
            f'''
            <div style="
                border-left: 5px solid #28a745;
                background-color: #d4edda;
                padding: 12px 15px;
                border-radius: 6px;
                margin-bottom: 10px;
                font-size: 0.95em;
            ">
                <div style="display: flex; flex-wrap: wrap; justify-content: space-between; gap: 10px;">
                    <div style="min-width: 120px; flex: 1;">
                        <strong>Formation:</strong><br>{play['Formation']}
                    </div>
                    <div style="min-width: 120px; flex: 1;">
                        <strong>Play Name:</strong><br>{play['Play Name']}
                    </div>
                </div>
            </div>
            ''',
            unsafe_allow_html=True
        )
        st.markdown(f"**Type**: {play['Play Type Category']} ({play['Play Type']})")
        st.markdown(f"**Depth**: {play['Play Depth']}")
        st.markdown(f"**Primary Read**: {play['Primary Read']}")
        st.markdown(f"**Progression**: {play['Progression']}")
        st.markdown(f"**Adjustments**: {play['Route Adjustments']}")
        st.markdown(f"**Notes**: {play['Notes']}")
    else:
        st.warning("No suitable play found. Try changing filters.")

# Footer image
st.markdown(
    '''
    <div class="bg-footer">
        <img src="https://raw.githubusercontent.com/yourusername/yourrepo/main/football.png" width="120">
    </div>
    ''',
    unsafe_allow_html=True
)
