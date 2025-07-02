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
                
    ##### 1. 👤 Identify Yourself
    Enter your **name** and press `Enter` to begin.
                
    ##### 2. 🌍 Select a Language
    Use the sidebar dropdown to choose:
    - **en** – English  
    - **hi** – Hindi  
    - **ru** – Russian  
    - **bg** – Bulgarian  
    - **pt** – Portuguese

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

    ##### 6. 🧘 Flexibility & Exit
    - You're **not required** to annotate everything.  
    - Continue for as long as you're comfortable.  
    - Close the tab anytime to exit.
                
    ##### 7. 📥 Download Your Responses
    - After completing, you can download all your responses as a CSV file.
    - Kindly send the downloaded file to the project team for analysis.
    """)

# ——— Idea 2: Label-wise breakdown of evaluation questions ———

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

# ——— Add this after loading and filtering the language-specific DataFrame ———
lang_df = df[df["lang"] == st.session_state.lang].reset_index(drop=True)
grouped = lang_df.groupby("article_id")
article_ids = list(grouped.groups.keys())

# ——— Define number of segments per language ———
language_segments = {
    "bg": 1,   # 10 articles, 14 entities
    "pt": 1,   # low annotator coverage
    "hi": 5,   # 142 entities → ~28 per segment
    "ru": 3,   # 45 entities → ~15 per segment
    "en": 4,   # 58 entities → ~14-15 per segment
}

NUM_SEGMENTS = language_segments.get(st.session_state.lang, 1)

# Compute total number of entities for the selected language
total_entities = len(lang_df)
entities_per_segment = total_entities // NUM_SEGMENTS + (total_entities % NUM_SEGMENTS > 0)

# Compute total number of entities per article
article_entity_counts = lang_df.groupby("article_id").size().reset_index(name="entity_count")
article_entity_counts = article_entity_counts.sort_values("article_id")

# Group articles into segments
segments = []
current_segment = []
current_count = 0

for _, row in article_entity_counts.iterrows():
    article_id = row["article_id"]
    count = row["entity_count"]
    if current_count + count > entities_per_segment and current_segment:
        segments.append(current_segment)
        current_segment = []
        current_count = 0
    current_segment.append(article_id)
    current_count += count
if current_segment:
    segments.append(current_segment)

# ——— Add segment selector to sidebar ———
if "segment_index" not in st.session_state:
    st.session_state.segment_index = 0

segment_labels = [f"Segment {i+1}" for i in range(len(segments))]
st.sidebar.selectbox("📚 Select Segment", segment_labels, key="segment_label")
st.session_state.segment_index = segment_labels.index(st.session_state.segment_label)
segment_id = st.session_state.segment_index + 1

# Reset indices if segment changed
if "previous_segment_index" not in st.session_state:
    st.session_state.previous_segment_index = st.session_state.segment_index

if st.session_state.segment_index != st.session_state.previous_segment_index:
    st.session_state.article_index = 0
    st.session_state.entity_index = 0
    st.session_state.previous_segment_index = st.session_state.segment_index
    st.rerun()



# Get articles for the selected segment
selected_article_ids = segments[st.session_state.segment_index]
filtered_df = lang_df[lang_df["article_id"].isin(selected_article_ids)].reset_index(drop=True)
grouped = filtered_df.groupby("article_id")
article_ids = list(grouped.groups.keys())

# ——— The rest of your code (article_index, entity_index, etc.) remains unchanged but now uses `filtered_df` instead of full lang_df ———






current_article_id = article_ids[st.session_state.article_index]
article_df = grouped.get_group(current_article_id).reset_index(drop=True)
total_entities_in_segment = len(filtered_df)
current_entity = sum(
    len(grouped.get_group(aid))
    for aid in article_ids[:st.session_state.article_index]
) + st.session_state.entity_index + 1

progress_ratio = current_entity / total_entities_in_segment if total_entities_in_segment > 0 else 0
progress_ratio = min(progress_ratio, 1.0)
st.progress(progress_ratio)

if progress_ratio >= 1.0:
    st.balloons()
    st.markdown("## 🎉 You're All Done!")
    st.success(f"Thank you, **{session_name}**, for completing this segment in **{st.session_state.lang.upper()}**.")

    if st.session_state.responses:
        st.markdown("### 📥 Download Your Responses")
        response_df = pd.DataFrame(st.session_state.responses)
        csv = response_df.to_csv(index=False).encode('utf-8')

        st.download_button(
            label="📥 Download CSV File",
            data=csv,
            file_name=f"responses_{session_name}.csv",
            mime='text/csv'
        )

        st.markdown("📧 **Please send the downloaded file to [`Vanshikaa.Jani@mbzuai.ac.ae`](mailto:Vanshikaa.Jani@mbzuai.ac.ae) for evaluation.**")

    st.info("You can close the tab or change the segment/language from the sidebar to continue.")
    st.stop()



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

def parse_roles(predicted_roles):
    import ast
    if isinstance(predicted_roles, str):
        try:
            return list(ast.literal_eval(predicted_roles))
        except Exception:
            return [predicted_roles]
    elif isinstance(predicted_roles, dict):
        return list(predicted_roles.keys())
    elif isinstance(predicted_roles, set):
        return list(predicted_roles)
    return list(predicted_roles) if isinstance(predicted_roles, list) else []

def render_label_wise_questions(predicted_roles):
    label_responses = {}
    parsed_roles = parse_roles(predicted_roles)

    for idx, label in enumerate(parsed_roles):
        total_labels = len(parsed_roles)
        label_num = idx + 1

        st.markdown(f"### 🏷️ Label {label_num} of {total_labels}: **{label}**")

        with st.container():
            makes_sense = st.radio(
                f"✅ Does the annotation for '{label}' make sense?",
                ["Yes", "No", "Unsure"],
                key=f"makes_sense_{label}"
            )
            confidence = st.slider(
                f"🔍 Your confidence for '{label}'",
                1, 5, 3,
                key=f"confidence_{label}"
            )

            label_responses[label] = {
                "label_index": label_num,
                "total_labels": total_labels,
                "makes_sense": makes_sense,
                "confidence": confidence
            }

    return label_responses


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
        label_feedback = render_label_wise_questions(predicted_roles)
        submit = st.form_submit_button("Submit")

        if submit:
            timestamp = datetime.now().isoformat()
            for label, feedback in label_feedback.items():
                response = {
                    "session_name": session_name,
                    "timestamp": timestamp,
                    "segement": segment_id,
                    "article_id": article_id,
                    "lang": lang,
                    "entity_mention": mention,
                    "main_role": main_role,
                    "predicted_role": label,
                    "label_index": feedback["label_index"],
                    "total_labels": feedback["total_labels"],
                    "makes_sense": feedback["makes_sense"]
                }
                st.session_state.responses.append(response)

            st.session_state.last_response = response  # Last one from loop
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

