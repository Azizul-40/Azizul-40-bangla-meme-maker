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
CREATOR = "Azizul & Habiba"        # <<< এখানে নিজের নাম বদলাতে পারো
MAX_RUNS_PER_SESSION = 10  # protects your free quota from abuse

FONT_URLS = [
    "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-Bold.ttf",
    "https://github.com/google/fonts/raw/main/ofl/hindsiliguri/HindSiliguri-SemiBold.ttf",
]

# style key -> (bangla label, english label, tone hint for the AI prompt)
STYLES = {
    "funny": ("😂 মজার", "😂 Funny", "funny and light-hearted"),
    "sarcastic": ("😏 Sarcastic", "😏 Sarcastic", "witty and sarcastic"),
    "cricket": ("🏏 ক্রিকেট ফ্যান", "🏏 Cricket fan", "like a Bangladeshi cricket fan reacting"),
    "student": ("📚 ছাত্রজীবন", "📚 Student life", "relatable to a Bangladeshi university student (exam, assignment, result)"),
    "mom": ("👩 দেশি আম্মু", "👩 Desi mom", "like a desi Bangladeshi mom commenting on it"),
    "sad": ("😢 স্যাড", "😢 Sad", "sad and melancholic, a bit dramatic, like a heartbroken Bangla status"),
    "depressed": ("😔 ডিপ্রেসড", "😔 Depressed", "exaggerated, meme-style mock-gloomy and dramatic, in a relatable, funny-sad way — never genuinely dark or self-harm related"),
    "emotional": ("🥹 ইমোশনাল", "🥹 Emotional", "heartfelt, sentimental and touching, like a nostalgic or sincere Bangla status"),
    "chill": ("😎 চিল", "😎 Chill", "super relaxed, laid-back, unbothered, nothing-matters chill vibe"),
    "dad": ("👨 দেশি বাবা", "👨 Desi dad", "like a strict but caring desi Bangladeshi dad making a dry, no-nonsense remark"),
    "auntie": ("👀 পাশের বাসার আন্টি", "👀 Next-door auntie", "like a nosy, gossiping Bangladeshi neighborhood auntie commenting with mock concern"),
}

# ---------------------------------------------------------------- UI text (bangla / english)
TEXT = {
    "bn": {
        "title": "😂 Khela Hobe",
        "subtitle": "ছবি দাও, AI বাংলায় মজার caption লিখে meme বানিয়ে দেবে।",
        "made_by": "👨‍💻 Made by",
        "tab_upload": "🖼️ ছবি upload",
        "tab_cam": "📷 Camera",
        "uploader_label": "ছবি বেছে নাও",
        "cam_label": "ছবি তোলো",
        "style_label": "Meme-এর ধরন",
        "extra_label": "ছবির আইডিয়া বা context (ঐচ্ছিক)",
        "extra_placeholder": "যেমন: রেজাল্ট দেওয়ার দিন আমি",
        "your_image": "তোমার ছবি",
        "make_meme_btn": "✨ Meme বানাও",
        "thinking": "AI caption ভাবছে...",
        "error_prefix": "কিছু একটা সমস্যা হয়েছে, একটু পরে আবার চেষ্টা করো।",
        "limit_warning": "এই session-এর limit শেষ। পেজ refresh করে আবার চেষ্টা করো।",
        "your_meme": "তোমার Meme",
        "pick_option": "পছন্দ বেছে নাও",
        "meme_label": "Meme",
        "top_text": "উপরের লেখা",
        "bottom_text": "নিচের লেখা",
        "download_btn": "⬇️ Meme download করো",
        "start_info": "শুরু করতে একটা ছবি upload করো বা camera দিয়ে তোলো।",
        "footer": "Khela Hobe 😂<br>Developed with ❤️ by",
        "font_error": (
            "বাংলা font পাওয়া যায়নি। GitHub repo-র `fonts/` folder-এ একটা বাংলা .ttf font "
            "(যেমন HindSiliguri-Bold.ttf বা NotoSansBengali-Bold.ttf) রাখো।"
        ),
        "secret_error": "Streamlit Secrets-এ `GEMINI_API_KEY` যোগ করা হয়নি। README দেখো।",
    },
    "en": {
        "title": "😂 Khela Hobe",
        "subtitle": "Give a photo, AI writes funny Bangla captions and makes a meme.",
        "made_by": "👨‍💻 Made by",
        "tab_upload": "🖼️ Upload photo",
        "tab_cam": "📷 Camera",
        "uploader_label": "Choose a photo",
        "cam_label": "Take a photo",
        "style_label": "Meme style",
        "extra_label": "Idea or context for the photo (optional)",
        "extra_placeholder": "e.g. me on result day",
        "your_image": "Your photo",
        "make_meme_btn": "✨ Make meme",
        "thinking": "AI is thinking of captions...",
        "error_prefix": "Something went wrong, try again in a bit.",
        "limit_warning": "This session's limit is over. Refresh the page and try again.",
        "your_meme": "Your meme",
        "pick_option": "Pick one",
        "meme_label": "Meme",
        "top_text": "Top text",
        "bottom_text": "Bottom text",
        "download_btn": "⬇️ Download meme",
        "start_info": "Upload a photo or take one with the camera to start.",
        "footer": "Khela Hobe 😂<br>Developed with ❤️ by",
        "font_error": (
            "Bangla font not found. Put a Bangla .ttf font (e.g. HindSiliguri-Bold.ttf or "
            "NotoSansBengali-Bold.ttf) in the `fonts/` folder of the GitHub repo."
        ),
        "secret_error": "`GEMINI_API_KEY` is not set in Streamlit Secrets. See the README.",
    },
}

st.set_page_config(page_title="Khela Hobe", page_icon="😂", layout="centered")

if "lang" not in st.session_state:
    st.session_state.lang = "bn"

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Hind+Siliguri:wght@400;600;700&display=swap');

      html, body, [class*="css"] {
        font-family: 'Hind Siliguri', sans-serif;
      }

      .block-container {
        padding-top: 1rem;
        padding-bottom: 3rem;
        max-width: 720px;
      }

      .khb-header {
        background: linear-gradient(135deg, #FF8A3D 0%, #FF5B2E 100%);
        border-radius: 18px;
        padding: 1.4rem 1.2rem;
        text-align: center;
        margin-bottom: 1.4rem;
        box-shadow: 0 6px 18px rgba(255, 91, 46, 0.25);
      }
      .khb-header h1 {
        color: white;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
      }
      .khb-header p {
        color: rgba(255,255,255,0.9);
        margin: .3rem 0 0;
        font-size: .95rem;
      }

      .stButton>button, .stDownloadButton>button {
        width: 100%;
        padding: .8rem 1rem;
        font-size: 1.05rem;
        font-weight: 600;
        border-radius: 12px;
        border: none;
        background: linear-gradient(135deg, #FF8A3D 0%, #FF5B2E 100%);
        color: white;
        transition: transform .15s ease, box-shadow .15s ease;
      }
      .stButton>button:hover, .stDownloadButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 14px rgba(255, 91, 46, 0.35);
        color: white;
      }

      img {
        border-radius: 14px;
        box-shadow: 0 4px 14px rgba(0,0,0,0.12);
      }

      .khb-card {
        background: var(--secondary-background-color, #fff7ef);
        border-radius: 16px;
        padding: 1.1rem 1.2rem;
        margin-top: 1rem;
        border: 1px solid rgba(255, 138, 61, 0.25);
      }

      .khb-footer {
        text-align: center;
        opacity: .7;
        padding: .6rem 0 1rem;
        font-size: .9rem;
      }

      .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        border-radius: 10px 10px 0 0;
      }
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
    # smaller image = faster upload and faster AI reply
    small = img.copy()
    small.thumbnail((640, 640))
    buf = io.BytesIO()
    small.save(buf, "JPEG", quality=80)

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
    # first try the fast setting (no long "thinking", JSON output), then a plain call
    configs = [
        types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=600,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
        types.GenerateContentConfig(response_mime_type="application/json", max_output_tokens=800),
        None,
    ]
    last_error = None
    for model in models:
        for cfg in configs:
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg"),
                        prompt,
                    ],
                    config=cfg,
                )
                match = re.search(r"\{.*\}", resp.text, re.S)
                data = json.loads(match.group(0))
                memes = [
                    {"top": str(m.get("top", "")).strip(), "bottom": str(m.get("bottom", "")).strip()}
                    for m in data["memes"]
                ]
                return memes[:5]
            except Exception as e:  # try the next setting / model
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
_lang_col1, _lang_col2 = st.columns([3, 1])
with _lang_col2:
    lang_choice = st.radio(
        "lang",
        options=["bn", "en"],
        format_func=lambda x: "বাং" if x == "bn" else "EN",
        horizontal=True,
        label_visibility="collapsed",
        index=0 if st.session_state.lang == "bn" else 1,
        key="lang_switch",
    )
    st.session_state.lang = lang_choice

T = TEXT[st.session_state.lang]

st.markdown(
    f"""
    <div class="khb-header">
      <h1>{T['title']}</h1>
      <p>{T['subtitle']}</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    f"<p style='text-align:center;opacity:.75;margin-top:-0.8rem'>{T['made_by']} <b>{CREATOR}</b></p>",
    unsafe_allow_html=True,
)

font_path = get_font_path()
if font_path is None:
    st.error(T["font_error"])
    st.stop()

if "GEMINI_API_KEY" not in st.secrets:
    st.error(T["secret_error"])
    st.stop()

if "runs" not in st.session_state:
    st.session_state.runs = 0

tab_up, tab_cam = st.tabs([T["tab_upload"], T["tab_cam"]])
with tab_up:
    uploaded = st.file_uploader(T["uploader_label"], type=["jpg", "jpeg", "png", "webp"])
with tab_cam:
    shot = st.camera_input(T["cam_label"])

source = uploaded or shot

style_keys = list(STYLES.keys())
lang_idx = 0 if st.session_state.lang == "bn" else 1
style_choice = st.selectbox(
    T["style_label"],
    style_keys,
    format_func=lambda k: STYLES[k][lang_idx],
)
style_hint = STYLES[style_choice][2]

extra = st.text_input(T["extra_label"], placeholder=T["extra_placeholder"])

if source is not None:
    file_id = f"{getattr(source, 'name', 'camera')}-{source.size}"
    if st.session_state.get("file_id") != file_id:
        st.session_state.file_id = file_id
        st.session_state.pop("memes", None)
    base_img = prepare_image(source.getvalue())
    st.image(base_img, caption=T["your_image"], use_container_width=True)

    left = MAX_RUNS_PER_SESSION - st.session_state.runs
    if st.button(T["make_meme_btn"], type="primary", disabled=left <= 0):
        with st.spinner(T["thinking"]):
            try:
                st.session_state.memes = get_captions(base_img, style_hint, extra)
                st.session_state.runs += 1
                for k in list(st.session_state.keys()):
                    if k.startswith(("top_", "bottom_")):
                        del st.session_state[k]
            except Exception as e:
                st.error(f"{T['error_prefix']} ({type(e).__name__}: {str(e)[:150]})")
    if left <= 0:
        st.warning(T["limit_warning"])

    memes = st.session_state.get("memes")
    if memes:
        st.markdown('<div class="khb-card">', unsafe_allow_html=True)
        st.subheader(T["your_meme"])
        idx = st.radio(
            T["pick_option"],
            range(len(memes)),
            format_func=lambda i: f"{T['meme_label']} {i + 1}",
            horizontal=True,
        )
        top = st.text_input(T["top_text"], value=memes[idx]["top"], key=f"top_{idx}")
        bottom = st.text_input(T["bottom_text"], value=memes[idx]["bottom"], key=f"bottom_{idx}")

        final = make_meme(base_img, top, bottom, font_path)
        st.image(final, use_container_width=True)

        out = io.BytesIO()
        final.save(out, "PNG")
        st.download_button(
            T["download_btn"],
            data=out.getvalue(),
            file_name="bangla_meme.png",
            mime="image/png",
        )
        st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info(T["start_info"])

st.markdown("---")
st.markdown(
    f"<div class='khb-footer'>{T['footer']} <b>{CREATOR}</b></div>",
    unsafe_allow_html=True,
)
