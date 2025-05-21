import streamlit as st
import pandas as pd
import random

# Load the play database
@st.cache_data
def load_data():
    return pd.read_excel("play_database_cleaned_download.xlsx")
df = load_data()

st.title("🧠 Play Caller Assistant")

# User inputs
col1, col2 = st.columns(2)
with col1:
    down = st.selectbox("Select Down", ["1st", "2nd", "3rd"])
with col2:
    distance = st.selectbox("Select Distance", ["short", "medium", "long"])

coverage = st.slider("Defensive Coverage Tendency", 0.0, 1.0, 0.5, 0.01)
coverage_label = (
    "Strictly Man" if coverage == 0 else
    "Strictly Zone" if coverage == 1 else
    "Mainly Man" if coverage < 0.5 else
    "Mainly Zone" if coverage > 0.5 else
    "Balanced"
)
st.caption(f"Tendency: {coverage_label}")

# Play filtering logic
def suggest_play():
    subset = df[df["Play Depth"].str.contains(distance)]
    if subset.empty:
        return None

    def score(row):
        return (1 - coverage) * row["Effective vs Man"] + coverage * row["Effective vs Zone"]

    subset["Score"] = subset.apply(score, axis=1)
    weighted = subset.sort_values(by="Score", ascending=False).head(10)
    return weighted.sample(1).iloc[0]

if st.button("📟 Call a Play"):
    play = suggest_play()
    if play is not None:
        st.success(f"**{play['Play Name']}**")
        st.markdown(f"**Type**: {play['Play Type Category']}")
        st.markdown(f"**Depth**: {play['Play Depth']}")
        st.markdown(f"**Primary Read**: {play['Primary Read']}")
        st.markdown(f"**Notes**: {play['Notes']}")
    else:
        st.warning("No suitable play found. Try changing filters.")
