import streamlit as st
from gtts import gTTS
import os
import pipeline
import database
import requests

st.set_page_config(page_title="Receipt IoT System", layout="wide")
database.init_db()

AUDIO_DIR = "static_audio"
os.makedirs(AUDIO_DIR, exist_ok=True)

st.title("🧾 Smart Receipt Classifier & Audio Digest")

def ensure_hindi_translation(english_text: str) -> str:
    if not english_text or not english_text.strip():
        return "विवरण उपलब्ध नहीं है।"
    
    prompt = f"""Translate this single sentence into natural Hindi using Devanagari script.
Return ONLY the Hindi translation and nothing else.

Sentence: {english_text}"""
    try:
        res = requests.post(
            pipeline.OLLAMA_ENDPOINT,
            json={"model": pipeline.MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=30
        )
        res.raise_for_status()
        translated = res.json().get("response", "").strip()
        return translated if translated else "विवरण उपलब्ध नहीं है।"
    except Exception:
        return "विवरण उपलब्ध नहीं है।"

# Sidebar Controls
with st.sidebar:
    st.header("Upload New Receipt")
    uploaded = st.file_uploader("Select Receipt Image", type=["jpg", "jpeg", "png"])
    
    if uploaded and st.button("Process & Classify"):
        temp_img = os.path.join("temp_" + uploaded.name)
        with open(temp_img, "wb") as f:
            f.write(uploaded.getbuffer())

        with st.spinner("Enhancing image with OpenCV & Running OCR..."):
            processed = pipeline.preprocess_image(temp_img)
            ocr_text = pipeline.run_ocr(processed)

        with st.spinner("Extracting metadata, line items, and summaries..."):
            extracted = pipeline.extract_and_summarize(ocr_text)
            
            if not extracted.get("hindi_summary") or not extracted["hindi_summary"].strip():
                extracted["hindi_summary"] = ensure_hindi_translation(extracted.get("english_summary", ""))

            extracted["filename"] = uploaded.name
            extracted["raw_text"] = ocr_text
            database.insert_receipt(extracted)

        st.success("Successfully processed and saved to database!")
        if os.path.exists(temp_img):
            os.remove(temp_img)

    st.divider()
    if st.button("🗑️ Clear All Saved Receipts"):
        database.clear_all_records()
        st.success("Database cleared!")
        st.rerun()

# Main Dashboard View
st.subheader("Receipt Database")

filter_col1, filter_col2 = st.columns([3, 1])
with filter_col1:
    search = st.text_input("Search merchant or raw text:")
with filter_col2:
    selected_cat = st.selectbox(
        "Category Filter",
        ["All", "Food & Beverage", "Retail & Groceries", "Fuel & Transport", "Utilities & Services", "Healthcare", "Other"]
    )

records = database.fetch_records(search, selected_cat)

if not records:
    st.info("No receipts found. Upload an image from the sidebar to begin.")
else:
    for rec in records:
        rec_id, filename, merchant, r_date, total, cat, en_sum, hi_sum, contact_info, return_policy, raw_text = rec
        
        if not hi_sum or not str(hi_sum).strip():
            hi_sum = ensure_hindi_translation(en_sum)

        with st.expander(f"📌 {merchant} | Total: {total} | Category: {cat} | Date: {r_date}"):
            st.write(f"**Source File:** `{filename}`")
            
            st.markdown("### Bill Summary")
            col_meta1, col_meta2 = st.columns(2)
            with col_meta1:
                st.write(f"**📞 Contact / Address:** {contact_info}")
            with col_meta2:
                st.write(f"**🔄 Return / Exchange Policy:** {return_policy}")
            
            st.markdown(f"**English Summary:** {en_sum}")
            st.markdown(f"**Hindi Summary:** {hi_sum}")
            
            # Audio Section
            c_audio1, c_audio2 = st.columns(2)
            
            # English Audio
            with c_audio1:
                en_path = os.path.join(AUDIO_DIR, f"en_{rec_id}.mp3")
                if not os.path.exists(en_path):
                    if st.button("Generate English Audio", key=f"gen_en_{rec_id}"):
                        text_to_speak = en_sum.strip() if (en_sum and en_sum.strip()) else "No summary available."
                        tts = gTTS(text=text_to_speak, lang='en')
                        tts.save(en_path)
                        st.rerun()
                else:
                    st.write("English Playback:")
                    st.audio(en_path)

            # Hindi Audio
            with c_audio2:
                hi_path = os.path.join(AUDIO_DIR, f"hi_{rec_id}.mp3")
                if not os.path.exists(hi_path):
                    if st.button("Generate Hindi Audio", key=f"gen_hi_{rec_id}"):
                        text_to_speak = hi_sum.strip() if (hi_sum and hi_sum.strip()) else "विवरण उपलब्ध नहीं है।"
                        tts = gTTS(text=text_to_speak, lang='hi')
                        tts.save(hi_path)
                        st.rerun()
                else:
                    st.write("Hindi Playback:")
                    st.audio(hi_path)

            st.divider()

            # Interactive Receipt Q&A
            st.markdown("### 💬 Ask Questions About This Receipt")
            q_col1, q_col2 = st.columns([4, 1])
            with q_col1:
                user_query = st.text_input(
                    "e.g., Is this item returnable? What items were ordered?", 
                    key=f"input_q_{rec_id}"
                )
            with q_col2:
                ask_btn = st.button("Ask AI", key=f"btn_q_{rec_id}")

            if ask_btn and user_query:
                with st.spinner("Analyzing receipt text..."):
                    answer = pipeline.ask_receipt_question(raw_text, user_query)
                    st.info(f"**Answer:** {answer}")

            # Debug Expander
            with st.expander("🔍 View Raw OCR Text"):
                st.code(raw_text)