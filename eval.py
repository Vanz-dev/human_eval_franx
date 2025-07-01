import streamlit as st
import pandas as pd
import os
import ast
import html
import json
from datetime import datetime

# ─── Page Setup ─────────────────────────────────────────────────────
st.set_page_config(page_title="Franx Evaluation", layout="wide")

st.markdown("""
<style>
.entity {
  background-color: #facc15;
  color: #111827;
  padding: 4px 8px;
  border-radius: 6px;
  font-weight: 600;
  font-size: 14px;
  margin: 2px 2px 6px 0;
  display: inline-block;
  box-shadow: 0 1px 2px rgba(0,0,0,0.2);
}
.entity-label {
  background-color: #0073e6; 
  color: #ffffff;
  font-size: 13.5px;
  font-style: italic;
  padding: 2px 6px;
  border-radius: 4px;
  margin-left: 6px;
  display: inline-block;
}
</style>
""", unsafe_allow_html=True)


# ─── Load & Cache Data ─────────────────────────────────────────────
@st.cache_data
def load_data():
    df = pd.read_csv("combined_all.csv")
    #df["fine_grained_roles"] = df["fine_grained_roles"].apply(ast.literal_eval)
    df["predicted_fine_margin"] = df["predicted_fine_margin"].apply(ast.literal_eval)
    return df

@st.cache_data
def load_taxonomy():
    with open("taxonomy.json", "r") as f:
        return json.load(f)

df = load_data()
taxonomy_data = load_taxonomy()

# ─── Taxonomy Mapping ──────────────────────────────────────────────
fine_role_info = {
    entry["fine_role"]: {
        "description": entry["description"],
        "example": entry["example"],
        "coarse_role": entry["coarse_role"]
    }
    for entry in taxonomy_data
}

# ─── Highlight Function ─────────────────────────────────────────────
def highlight_entities(text, records, label_column,
                       default_color="#facc15", compare_column=None):
    out, last = [], 0
    records = sorted(records, key=lambda r: r["start_offset"])
    for ent in records:
        s, e = ent["start_offset"], ent["end_offset"]+1
        mention = html.escape(text[s:e])
        labels = ent[label_column]
        label_str = ", ".join(labels)
        bg = default_color
        if compare_column:
            is_match = set(labels) == set(ent[compare_column])
            bg = "#96f1b3" if is_match else "#d87575"
            other = ", ".join(ent[compare_column])
            label_str = f"pred: {label_str} ⇄ gold: {other}"
        out.append(html.escape(text[last:s]))
        out.append(
            f"<span class='entity' style='background:{bg}'>{mention}</span>"
            f"<span class='entity-label'>{html.escape(label_str)}</span>"
        )
        last = e
    out.append(html.escape(text[last:]))
    return "".join(out)

# ─── Role Display Function ─────────────────────────────────────────
def display_role_info(role_list, title):
    st.markdown(f"**{title}**")
    for role in role_list:
        info = fine_role_info.get(role, {})
        st.markdown(
            f"<span style='background:#e0e0e0;padding:4px 8px;border-radius:5px;margin:3px;display:inline-block;'>{html.escape(role)}</span>",
            unsafe_allow_html=True
        )
        with st.expander(f"📘 {role}"):
            st.markdown(f"**Coarse Role**: `{info.get('coarse_role', 'N/A')}`")
            st.markdown(f"**Description:** {info.get('description', 'No description available.')}")
            st.markdown(f"**Example:** _{info.get('example', 'No example available.')}_")

# ─── Session State ──────────────────────────────────────────────────


with st.expander("📘 Instructions for Evaluators", expanded=False):
    st.markdown("""
    ##### 1. 🌍 Select a Language
    Use the sidebar dropdown to choose:
    - **en** – English  
    - **hi** – Hindi  
    - **ru** – Russian  
    - **bg** – Bulgarian  
    - **pt** – Portuguese

    ##### 2. 👤 Identify Yourself
    Enter your **name or session ID** and press `Enter` to begin.

    ##### 3. 📄 Review the Article Carefully
    Pay attention to:
    - 🔸 **Highlighted entity**
    - 🔹 **Fine-grained role labels**  
      _Click to expand each to view descriptions and examples._

    ##### 4. ✅ Answer Thoughtfully
    - Select the label that best fits the context.  
    - You can choose **Unsure** or **Not Applicable** if needed.

    ##### 5. ⚠️ Submitting Your Response
    - Once you click **Submit**, your response is saved and **cannot be edited**.  
    - Submit only when you're confident.  
    - You may skip to the next entity or article if needed.

    ##### 6. 🧘 Flexibility & Exit
    - You're **not required** to annotate everything.  
    - Continue for as long as you're comfortable.  
    - Close the tab anytime to exit.
    """)



if "article_index" not in st.session_state:
    st.session_state.article_index = 0
if "entity_index" not in st.session_state:
    st.session_state.entity_index = 0
if "lang" not in st.session_state:
    st.session_state.lang = df["lang"].unique()[0]

st.markdown("""
<div style='background-color:#eef2ff; border-left: 6px solid #6366f1; padding: 12px 20px; border-radius: 10px; margin-top: 1rem; box-shadow: 0 1px 4px rgba(0,0,0,0.1);'>
<h4 style='margin:0; color:#3730a3;'>👤 Please enter your <strong>name</strong> for this evaluation:</h4>
<p style='margin-top:6px; color:#6366f1; font-size:14px;'>Press Enter to begin</p>
</div>
""", unsafe_allow_html=True)

session_name = st.text_input("", value="", placeholder="e.g. John")

if session_name:
    st.markdown(f"**Evaluator:** {session_name}")
# ─── Sidebar ────────────────────────────────────────────────────────
st.sidebar.title("🔧 Settings")
st.sidebar.selectbox("🌍 Select Language", df["lang"].unique(), key="lang")

# ─── Filter and Group Articles ──────────────────────────────────────
lang_df = df[df["lang"] == st.session_state.lang].reset_index(drop=True)
grouped = lang_df.groupby("article_id")
# Track previous language selection
if "previous_lang" not in st.session_state:
    st.session_state.previous_lang = st.session_state.lang

# Reset progression if language changes
if st.session_state.lang != st.session_state.previous_lang:
    st.session_state.article_index = 0
    st.session_state.entity_index = 0
    st.session_state.previous_lang = st.session_state.lang
    st.rerun()

article_ids = list(grouped.groups.keys())

if st.session_state.article_index >= len(article_ids):
    st.success("🎉 You've completed all articles in this language!")
    st.stop()

current_article_id = article_ids[st.session_state.article_index]
article_df = grouped.get_group(current_article_id).reset_index(drop=True)

# ─── Check Entity Bounds ────────────────────────────────────────────
if st.session_state.entity_index >= len(article_df):
    st.session_state.article_index += 1
    st.session_state.entity_index = 0
    st.rerun()

# ─── Fetch Current Entity ───────────────────────────────────────────
row = article_df.iloc[st.session_state.entity_index]
context = row["text"]
mention = row["entity_mention"]
start = row["start_offset"]
end = row["end_offset"]
main_role = row["p_main_role"]
predicted_roles = row["predicted_fine_margin"]
article_id = row["article_id"]

# ─── Build Highlighted Record ───────────────────────────────────────
record = {
    "start_offset": start,
    "end_offset": end,
    "predicted_fine_margin": predicted_roles
}
records = [record]
highlighted_html = highlight_entities(context, records, "predicted_fine_margin",)


# ─── Layout ─────────────────────────────────────────────────────────
left_col, right_col = st.columns([1.4, 1])

with left_col:
    article_num = st.session_state.article_index + 1
    total_articles = len(article_ids)
    entity_num = st.session_state.entity_index + 1
    total_entities = len(article_df)

    st.markdown(f"**Language:** {row['lang']}  &nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp; "
                f"**Article {article_num} of {total_articles}**  &nbsp;&nbsp;&nbsp; | &nbsp;&nbsp;&nbsp; "
                f"**Entity {entity_num} of {total_entities} in this article**", unsafe_allow_html=True)

    st.markdown("### 📄 Article Context")
    #st.markdown(f"<div style='background-color:#f9fafb;padding:1rem;border-radius:8px;max-height:900px;overflow-y:auto;font-size:15px;line-height:1.6;'>{highlighted_html}</div>", unsafe_allow_html=True)
    # Assuming `highlighted_html` holds your entity-highlighted article
    st.markdown("""
    <style>
    .article-box {
        background-color: #fdfdfd;
        border-left: 6px solid #6366f1;
        padding: 1.25rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        font-size: 17px;
        line-height: 1.75;
        font-family: 'Segoe UI', 'Georgia', sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"<div class='article-box'>{highlighted_html}</div>", unsafe_allow_html=True)
st.markdown("""
<style>
.sticky-eval {
    position: -webkit-sticky;
    position: sticky;
    top: 1rem;
    align-self: flex-start;
}
</style>
""", unsafe_allow_html=True)
with right_col:
    st.markdown("<div class='sticky-eval'>", unsafe_allow_html=True)

    st.markdown("### 📝 Evaluation")
 

    



    st.markdown(f"**Entity Mention**: <span style='color:#007BFF; font-weight:600;'>{html.escape(mention)}</span>", unsafe_allow_html=True)
    st.markdown(f"**Main Role**: <span style='background:#cbd5e1;padding:4px 8px;border-radius:5px;margin:3px;display:inline-block;'>{html.escape(main_role)}</span>", unsafe_allow_html=True)

    display_role_info(predicted_roles, "Predicted Fine-Grained Roles")

    with st.form("eval_form"):
        st.markdown("### 📝 Evaluation")

        makes_sense = st.radio("✅ Does the annotation make sense?", ["Yes", "No", "Unsure"])


        issues = st.radio("❗ What’s wrong?", 
                              ["Incorrect entity", "Incorrect fine-grained roles", "Not applicable"])
            
        multi_labels = st.radio("(Answer if the entity has multiple fine-grained roles) How many labels are correct?",["One", "Two", "Three or more", "Not applicable"])

        confidence = st.slider("🔍 Confidence in your answer", 1, 5, 3)

        submitted = st.form_submit_button("Submit")

        if submitted:
            response = {
                "session_name": session_name,
                "timestamp": datetime.now().isoformat(),
                "article_id": article_id,
                "lang": row["lang"],
                "entity_mention": mention,
                "main_role": main_role,
                "predicted_roles": predicted_roles,
                "makes_sense": makes_sense,
                "issues": issues,
                "multi_labels": multi_labels,
                "confidence": confidence
            }

            output_file = f"responses_{row['lang']}.csv"
            pd.DataFrame([response]).to_csv(output_file, mode="a", header=not os.path.exists(output_file), index=False)

            st.success("✅ Response recorded!")
            st.session_state.entity_index += 1
            st.rerun()
