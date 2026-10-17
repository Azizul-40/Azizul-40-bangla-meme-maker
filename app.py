import base64
import glob
import io
import json
import os
import re
import urllib.request

import streamlit as st
from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ---------------------------------------------------------------- settings
DEFAULT_MODELS = ["gemini-flash-latest", "gemini-3.6-flash", "gemini-2.5-flash"]
MAX_SIDE = 1024            # image is resized so it loads fast on mobile
MAX_RUNS_PER_SESSION = 10  # protects your free quota from abuse

FONT_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-SemiBold.ttf",
]

STYLES = {
    "😂 মজার": "funny and light-hearted",
    "😏 Sarcastic": "witty and sarcastic",
    "🏏 ক্রিকেট ফ্যান": "like a Bangladeshi cricket fan reacting",
    "📚 ছাত্রজীবন": "relatable to a Bangladeshi university student (exam, assignment, result)",
    "👩 দেশি আম্মু": "like a desi Bangladeshi mom commenting on it",
}

st.set_page_config(page_title="বাংলা Meme Maker", page_icon="😂", layout="centered")

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.5rem; padding-bottom: 3rem; max-width: 720px;}
      .stButton>button, .stDownloadButton>button {width: 100%; padding: .7rem 1rem; font-size: 1.05rem;}
      img {border-radius: 10px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------- font
@st.cache_resource(show_spinner=False)
def get_font_path():
    """Find a Bengali font: repo fonts/ folder, system fonts, or download."""
    patterns = [
        "fonts/*.ttf",
        "fonts/*.otf",
        "/usr/share/fonts/**/NotoSansBengali*Bold*.ttf",
        "/usr/share/fonts/**/NotoSansBengali*.ttf",
        "/usr/share/fonts/**/*Bengali*.ttf",
        "/usr/share/fonts/**/*Beng*.ttf",
    ]
    for pattern in patterns:
        hits = sorted(glob.glob(pattern, recursive=True))
        if hits:
            return hits[0]

    os.makedirs("fonts", exist_ok=True)
    for url in FONT_URLS:
        try:
            dest = os.path.join("fonts", os.path.basename(url))
            urllib.request.urlretrieve(url, dest)
            return dest
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- image + AI
def prepare_image(file_bytes: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(file_bytes))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def get_captions(img: Image.Image, style_hint: str, extra: str):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)

    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])
    prompt = f"""Look at this image and write 5 different meme captions in Bangla (Bengali script).
Tone: {style_hint}.
{"Extra context from the user: " + extra if extra.strip() else ""}

Rules:
- Each meme has a "top" line and a "bottom" line. Each line max 8 words.
- Natural, modern spoken Bangla, with a punchline at the bottom.
- Be funny, but do not attack real people, religions, or groups.
- Reply with ONLY valid JSON, no extra text, in this shape:
{{"memes": [{{"top": "...", "bottom": "..."}}]}}"""

    models = [st.secrets["GEMINI_MODEL"]] if "GEMINI_MODEL" in st.secrets else DEFAULT_MODELS
    last_error = None
    for model in models:
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                    prompt,
                ],
            )
            match = re.search(r"\{.*\}", resp.text, re.S)
            data = json.loads(match.group(0))
            memes = [
                {"top": str(m.get("top", "")).strip(), "bottom": str(m.get("bottom", "")).strip()}
                for m in data["memes"]
            ]
            return memes[:5]
        except Exception as e:  # try the next model name
            last_error = e
    raise last_error


# ---------------------------------------------------------------- meme drawing
def wrap_text(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_block(img, text, font_path, at_top):
    if not text.strip():
        return
    draw = ImageDraw.Draw(img)
    width, height = img.size
    size = max(28, width // 9)
    max_width = width * 0.92

    while True:
        font = ImageFont.truetype(font_path, size)
        lines = wrap_text(draw, text, font, max_width)
        line_h = size * 1.3
        if len(lines) * line_h <= height * 0.30 or size <= 18:
            break
        size -= 2

    block_h = len(lines) * line_h
    y = 10 if at_top else height - block_h - 14
    stroke = max(2, size // 9)
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(
            ((width - w) / 2, y),
            line,
            font=font,
            fill="white",
            stroke_width=stroke,
            stroke_fill="black",
        )
        y += line_h


def make_meme(base_img, top, bottom, font_path):
    img = base_img.copy()
    draw_block(img, top, font_path, at_top=True)
    draw_block(img, bottom, font_path, at_top=False)
    return img


# ---------------------------------------------------------------- UI
st.title("😂 বাংলা Meme Maker")
st.caption("ছবি দাও, AI বাংলায় মজার caption লিখে meme বানিয়ে দেবে।")

font_path = get_font_path()
if font_path is None:
    st.error(
        "বাংলা font পাওয়া যায়নি। GitHub repo-র `fonts/` folder-এ একটা বাংলা .ttf font "
        "(যেমন HindSiliguri-Bold.ttf বা NotoSansBengali-Bold.ttf) রাখো।"
    )
    st.stop()

if "GEMINI_API_KEY" not in st.secrets:
    st.error("Streamlit Secrets-এ `GEMINI_API_KEY` যোগ করা হয়নি। README দেখো।")
    st.stop()

if "runs" not in st.session_state:
    st.session_state.runs = 0

tab_up, tab_cam = st.tabs(["🖼️ ছবি upload", "📷 Camera"])
with tab_up:
    uploaded = st.file_uploader("ছবি বেছে নাও", type=["jpg", "jpeg", "png", "webp"])
with tab_cam:
    shot = st.camera_input("ছবি তোলো")

source = uploaded or shot
style_label = st.selectbox("Meme-এর ধরন", list(STYLES.keys()))
extra = st.text_input("ছবির আইডিয়া বা context (ঐচ্ছিক)", placeholder="যেমন: রেজাল্ট দেওয়ার দিন আমি")

if source is not None:
    file_id = f"{getattr(source, 'name', 'camera')}-{source.size}"
    if st.session_state.get("file_id") != file_id:
        st.session_state.file_id = file_id
        st.session_state.pop("memes", None)
    base_img = prepare_image(source.getvalue())
    st.image(base_img, caption="তোমার ছবি", use_container_width=True)

    left = MAX_RUNS_PER_SESSION - st.session_state.runs
    if st.button("✨ Meme বানাও", type="primary", disabled=left <= 0):
        with st.spinner("AI caption ভাবছে..."):
            try:
                st.session_state.memes = get_captions(base_img, STYLES[style_label], extra)
                st.session_state.runs += 1
                for k in list(st.session_state.keys()):
                    if k.startswith(("top_", "bottom_")):
                        del st.session_state[k]
            except Exception as e:
                st.error(f"কিছু একটা সমস্যা হয়েছে, একটু পরে আবার চেষ্টা করো। ({type(e).__name__}: {str(e)[:150]})")
    if left <= 0:
        st.warning("এই session-এর limit শেষ। পেজ refresh করে আবার চেষ্টা করো।")

    memes = st.session_state.get("memes")
    if memes:
        st.subheader("তোমার Meme")
        idx = st.radio(
            "পছন্দ বেছে নাও",
            range(len(memes)),
            format_func=lambda i: f"Meme {i + 1}",
            horizontal=True,
        )
        top = st.text_input("উপরের লেখা", value=memes[idx]["top"], key=f"top_{idx}")
        bottom = st.text_input("নিচের লেখা", value=memes[idx]["bottom"], key=f"bottom_{idx}")

        final = make_meme(base_img, top, bottom, font_path)
        st.image(final, use_container_width=True)

        out = io.BytesIO()
        final.save(out, "PNG")
        st.download_button(
            "⬇️ Meme download করো",
            data=out.getvalue(),
            file_name="bangla_meme.png",
            mime="image/png",
        )
else:
    st.info("শুরু করতে একটা ছবি upload করো বা camera দিয়ে তোলো।")
