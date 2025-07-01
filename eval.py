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
    df = pd.read_csv("combined_all.csv", encoding="utf-8")
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

# ─── Session Setup ─────────────────────────────────────────────────
if "article_index" not in st.session_state:
    st.session_state.article_index = 0
if "entity_index" not in st.session_state:
    st.session_state.entity_index = 0
if "lang" not in st.session_state:
    st.session_state.lang = df["lang"].unique()[0]
if "responses" not in st.session_state:
    st.session_state.responses = []
if "just_submitted" not in st.session_state:
    st.session_state.just_submitted = False
if "last_response" not in st.session_state:
    st.session_state.last_response = None

# ─── Instructions ──────────────────────────────────────────────────
with st.expander("📘 Instructions for Evaluators", expanded=False):
    st.markdown("""
    ##### 1. 🌍 Select a Language (Sidebar)
    ##### 2. 👤 Enter your name or session ID
    ##### 3. 📄 Read the article and highlight
    ##### 4. ✅ Annotate carefully
    ##### 5. 📥 Download and continue
    """)

st.markdown("#### 👤 Enter your name:")
session_name = st.text_input("", value="", placeholder="e.g. John")
if not session_name:
    st.stop()

# ─── Sidebar Language Picker ───────────────────────────────────────
st.sidebar.title("🔧 Settings")
st.sidebar.selectbox("🌍 Select Language", df["lang"].unique(), key="lang")

# ─── Handle Language Switch ─────────────────────────────────────────
if "previous_lang" not in st.session_state:
    st.session_state.previous_lang = st.session_state.lang

if st.session_state.lang != st.session_state.previous_lang:
    st.session_state.article_index = 0
    st.session_state.entity_index = 0
    st.session_state.previous_lang = st.session_state.lang
    st.rerun()

# ─── Article & Entity Setup ─────────────────────────────────────────
lang_df = df[df["lang"] == st.session_state.lang].reset_index(drop=True)
grouped = lang_df.groupby("article_id")
article_ids = list(grouped.groups.keys())

if st.session_state.article_index >= len(article_ids):
    st.success("🎉 You've completed all articles in this language!")
    st.stop()

current_article_id = article_ids[st.session_state.article_index]
article_df = grouped.get_group(current_article_id).reset_index(drop=True)

if st.session_state.entity_index >= len(article_df):
    st.session_state.article_index += 1
    st.session_state.entity_index = 0
    st.rerun()

# ─── Current Entity Row ─────────────────────────────────────────────
row = article_df.iloc[st.session_state.entity_index]
context = row["text"]
mention = row["entity_mention"]
start = row["start_offset"]
end = row["end_offset"]
main_role = row["p_main_role"]
predicted_roles = row["predicted_fine_margin"]
article_id = row["article_id"]
lang = row["lang"]

record = {"start_offset": start, "end_offset": end, "predicted_fine_margin": predicted_roles}
highlighted_html = highlight_entities(context, [record], "predicted_fine_margin")

# ─── Layout ─────────────────────────────────────────────────────────
left_col, right_col = st.columns([1.4, 1])
with left_col:
    st.markdown(f"**Language:** {lang} | **Article {st.session_state.article_index+1}/{len(article_ids)}** | **Entity {st.session_state.entity_index+1}/{len(article_df)}**")
    st.markdown("### 📄 Article Context")
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

with right_col:
    st.markdown("### 📝 Evaluation")
    st.markdown(f"**Entity Mention**: <span style='color:#007BFF; font-weight:600;'>{html.escape(mention)}</span>", unsafe_allow_html=True)
    st.markdown(f"**Main Role**: <span style='background:#cbd5e1;padding:4px 8px;border-radius:5px;margin:3px;display:inline-block;'>{html.escape(main_role)}</span>", unsafe_allow_html=True)
    display_role_info(predicted_roles, "Predicted Fine-Grained Roles")

    with st.form("eval_form"):
        makes_sense = st.radio("✅ Does the annotation make sense?", ["Yes", "No", "Unsure"])
        issues = st.radio("❗ What’s wrong?", ["Incorrect entity", "Incorrect fine-grained roles", "Not applicable"])
        multi_labels = st.radio("(Answer if the entity has multiple fine-grained roles) How many labels are correct?", ["zero", "One", "Two", "Three or more", "Not applicable"])
        confidence = st.slider("🔍 Confidence in your answer", 1, 5, 3)

        if st.form_submit_button("Submit"):
            response = {
                "session_name": session_name,
                "timestamp": datetime.now().isoformat(),
                "article_id": article_id,
                "lang": lang,
                "entity_mention": mention,
                "main_role": main_role,
                "predicted_roles": ", ".join(predicted_roles),
                "makes_sense": makes_sense,
                "issues": issues,
                "multi_labels": multi_labels,
                "confidence": confidence
            }
            st.session_state.responses.append(response)
            st.session_state.last_response = response
            st.session_state.just_submitted = True
            st.success("✅ Response submitted. Scroll down to continue.")

# ─── Download & Continue Block ─────────────────────────────────────
if st.session_state.just_submitted and st.session_state.last_response:
    st.markdown("---")
    st.markdown("### ✅ Done Evaluating?")

    response_df = pd.DataFrame(st.session_state.responses)
    csv = response_df.to_csv(index=False).encode("utf-8")

    st.download_button(
        label="📥 Download All Responses",
        data=csv,
        file_name=f"responses_{session_name}.csv",
        mime="text/csv"
    )

    # Save last response locally
    os.makedirs("responses", exist_ok=True)
    local_path = f"responses/responses_{lang}.csv"
    pd.DataFrame([st.session_state.last_response]).to_csv(
        local_path, mode="a", header=not os.path.exists(local_path), index=False
    )

    if st.button("➡️ Continue to Next"):
        st.session_state.entity_index += 1
        st.session_state.just_submitted = False
        st.session_state.last_response = None
        st.rerun()
