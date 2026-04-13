import streamlit as st
import fitz  # PyMuPDF
import anthropic
import json
import base64
from io import BytesIO

# ──────────────────────────────────────────────
# Page Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="BOD Slide Translator",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────
# Custom CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', 'Noto Sans KR', sans-serif;
}
.stApp { background: #0a0d12; }

/* Hide default header & footer */
#MainMenu, header, footer { visibility: hidden; }
header { display: none; }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #0f1218 !important;
    border-right: 1px solid #1a1f2e;
    width: 240px !important;
}
section[data-testid="stSidebar"] .stMarkdown p {
    font-size: 13px;
}

/* Remove default padding */
.block-container {
    padding-top: 1.5rem !important;
    padding-bottom: 0 !important;
}

/* ── Custom Components ── */

/* Hero / Upload area */
.upload-hero {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; text-align: center;
    padding: 60px 40px; margin: 40px auto;
    max-width: 640px;
    border: 2px dashed #1e2536;
    border-radius: 20px;
    transition: all 0.3s;
}
.upload-hero:hover { border-color: #7c6df5; background: rgba(124,109,245,0.03); }
.upload-hero h1 {
    font-size: 28px; font-weight: 700;
    background: linear-gradient(135deg, #e6edf3 0%, #7c6df5 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
}
.upload-hero p { color: #6b7b8d; font-size: 14px; line-height: 1.6; }

/* Feature cards */
.features-grid {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 14px; margin: 28px 0 32px; width: 100%;
}
.feature-card {
    background: #111720; border: 1px solid #1a2030;
    border-radius: 12px; padding: 18px 16px;
    text-align: left; transition: all 0.25s;
}
.feature-card:hover {
    border-color: #2a3555; background: #131b28;
    transform: translateY(-2px);
}
.feature-card .icon { font-size: 22px; margin-bottom: 8px; }
.feature-card .title {
    font-size: 13px; font-weight: 600; color: #e6edf3;
    margin-bottom: 4px;
}
.feature-card .desc { font-size: 11px; color: #5a6a7d; line-height: 1.5; }

/* Language toggle */
.lang-toggle-container {
    display: flex; align-items: center; gap: 12px;
    margin-bottom: 12px;
}
.lang-toggle {
    display: inline-flex; background: #111720;
    border: 1px solid #1a2030; border-radius: 10px;
    padding: 4px; gap: 3px;
}
.lang-btn {
    padding: 8px 24px; border-radius: 8px; border: none;
    font-size: 13px; font-weight: 600; cursor: pointer;
    transition: all 0.25s; font-family: inherit;
    text-decoration: none; display: inline-block; text-align: center;
}
.lang-btn.active {
    background: #7c6df5; color: #fff;
    box-shadow: 0 2px 12px rgba(124,109,245,0.3);
}
.lang-btn.inactive { background: transparent; color: #5a6a7d; }
.lang-btn.inactive:hover { color: #8a9ab0; }

/* Status pill */
.status-pill {
    display: inline-flex; align-items: center; gap: 6px;
    font-size: 12px; font-weight: 500; padding: 4px 14px;
    border-radius: 20px;
}
.status-pill.translating { color: #7c6df5; background: rgba(124,109,245,0.1); }
.status-pill.done { color: #4ade80; background: rgba(74,222,128,0.1); }

/* Slide viewer */
.slide-viewer {
    position: relative; background: #0d1017;
    border: 1px solid #1a2030; border-radius: 12px;
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
}
.slide-viewer img { width: 100%; display: block; }
.text-overlay {
    position: absolute; pointer-events: none;
    line-height: 1.3; white-space: pre-wrap;
    word-break: keep-all; overflow: hidden;
    border-radius: 2px; padding: 1px 3px;
    transition: all 0.3s;
}
.text-overlay.original { background: rgba(255,255,255,0.85); color: #111; }
.text-overlay.translated {
    background: rgba(255,255,255,0.9); color: #111;
    border-left: 2.5px solid #7c6df5;
}

/* Slide nav */
.slide-nav {
    display: flex; align-items: center; justify-content: center;
    gap: 16px; padding: 14px 0 4px;
}
.slide-nav .page-info {
    font-size: 13px; color: #5a6a7d;
    font-variant-numeric: tabular-nums;
}

/* Thumbnail in sidebar */
.thumb-item {
    border-radius: 6px; overflow: hidden;
    border: 2px solid transparent; opacity: 0.5;
    transition: all 0.2s; cursor: pointer;
    margin-bottom: 6px;
}
.thumb-item:hover { opacity: 0.75; }
.thumb-item.active {
    border-color: #7c6df5; opacity: 1;
    box-shadow: 0 0 10px rgba(124,109,245,0.2);
}
.thumb-item img { width: 100%; display: block; }

/* Sidebar header */
.sidebar-brand {
    font-size: 10px; font-weight: 700;
    letter-spacing: 0.14em; text-transform: uppercase;
    color: #7c6df5; margin-bottom: 2px;
}
.sidebar-sub {
    font-size: 10px; color: #3d4a5c; margin-bottom: 12px;
}
.sidebar-filename {
    font-size: 11px; color: #8a9ab0;
    background: #111720; padding: 6px 10px;
    border-radius: 6px; margin-bottom: 16px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    border: 1px solid #1a2030;
}

/* Info bar */
.info-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 8px 0; margin-bottom: 8px;
}
.info-badge {
    font-size: 11px; color: #4a5568;
    background: #111720; padding: 4px 10px;
    border-radius: 16px; border: 1px solid #1a2030;
}

/* Stramlit button overrides */
.stButton > button {
    border-radius: 8px; font-weight: 500;
    border: 1px solid #1a2030;
    transition: all 0.2s;
}
div[data-testid="stFileUploader"] {
    border: none !important;
}
div[data-testid="stFileUploader"] > div {
    border: 2px dashed #1e2536 !important;
    border-radius: 12px !important;
    background: #0d1017 !important;
}
div[data-testid="stFileUploader"] > div:hover {
    border-color: #7c6df5 !important;
}

/* Spinner override */
.stSpinner > div { border-color: #7c6df5 transparent transparent transparent !important; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Session State
# ──────────────────────────────────────────────
def init_state():
    defaults = {
        "pages": [],           # [{image_b64, thumb_b64, text_blocks, w, h}]
        "current_page": 0,
        "lang": "ko",
        "translations": {},    # {page_idx: [translated strings]}
        "file_name": "",
        "processed": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()


# ──────────────────────────────────────────────
# PDF Processing
# ──────────────────────────────────────────────
def process_pdf(file_bytes):
    """Extract pages as images + text blocks with positions."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        pw, ph = page.rect.width, page.rect.height

        # High-res render
        mat = fitz.Matrix(2.5, 2.5)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        img_b64 = base64.b64encode(img_bytes).decode()

        # Thumbnail
        tmat = fitz.Matrix(0.3, 0.3)
        tpix = page.get_pixmap(matrix=tmat, alpha=False)
        thumb_b64 = base64.b64encode(tpix.tobytes("png")).decode()

        # Text extraction with positions
        blocks = page.get_text("dict")["blocks"]
        text_items = []
        for block in blocks:
            if block["type"] != 0:  # text blocks only
                continue
            for line in block["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                text = " ".join(s["text"] for s in spans if s["text"].strip())
                if not text.strip():
                    continue
                bbox = line["bbox"]  # (x0, y0, x1, y1)
                font_size = spans[0]["size"]
                text_items.append({
                    "str": text,
                    "x_pct": (bbox[0] / pw) * 100,
                    "y_pct": (bbox[1] / ph) * 100,
                    "w_pct": ((bbox[2] - bbox[0]) / pw) * 100,
                    "h_pct": ((bbox[3] - bbox[1]) / ph) * 100,
                    "font_size": font_size,
                })

        # Group nearby text items into blocks
        grouped = group_text_blocks(text_items)

        pages.append({
            "image_b64": img_b64,
            "thumb_b64": thumb_b64,
            "text_blocks": grouped,
            "w": pw,
            "h": ph,
        })

    doc.close()
    return pages


def group_text_blocks(items):
    """Group lines that are vertically close and horizontally aligned."""
    if not items:
        return []

    items_sorted = sorted(items, key=lambda t: (t["y_pct"], t["x_pct"]))
    blocks = []
    used = set()

    for i, item in enumerate(items_sorted):
        if i in used:
            continue
        block = [item]
        used.add(i)

        for j in range(i + 1, len(items_sorted)):
            if j in used:
                continue
            last = block[-1]
            gap_y = items_sorted[j]["y_pct"] - (last["y_pct"] + last["h_pct"])
            x_close = abs(items_sorted[j]["x_pct"] - block[0]["x_pct"]) < 3

            if x_close and -0.5 < gap_y < last["h_pct"] * 1.2:
                block.append(items_sorted[j])
                used.add(j)

        combined_str = "\n".join(b["str"] for b in block)
        x_pct = min(b["x_pct"] for b in block)
        y_pct = min(b["y_pct"] for b in block)
        w_pct = max(b["x_pct"] + b["w_pct"] for b in block) - x_pct
        h_pct = max(b["y_pct"] + b["h_pct"] for b in block) - y_pct
        font_size = block[0]["font_size"]

        blocks.append({
            "str": combined_str,
            "x_pct": x_pct,
            "y_pct": y_pct,
            "w_pct": w_pct,
            "h_pct": h_pct,
            "font_size": font_size,
        })

    return blocks


# ──────────────────────────────────────────────
# Translation
# ──────────────────────────────────────────────
def translate_texts(texts, direction="ko2en"):
    """Call Claude API to translate text blocks."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    system = """You are a professional Korean-to-English translator for board of directors (이사회) meeting materials at a major Korean corporation.
Rules:
1. Use formal, concise business English suitable for board-level communication.
2. Keep proper nouns, company names, abbreviations, numbers as-is (e.g., KRAFTON, ADK, 3Q24).
3. Be concise — board slides have limited space. Match the brevity of the original.
4. If text is already in English or is a number/symbol, return it unchanged.
5. Translate naturally, not word-for-word.
6. Return ONLY a JSON array of translated strings in the exact same order. No markdown, no explanation."""

    if direction == "en2ko":
        system = system.replace("Korean-to-English", "English-to-Korean").replace("business English", "격식체 한국어")

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system,
        messages=[{
            "role": "user",
            "content": f"Translate each text. Return a JSON array:\n{json.dumps(texts, ensure_ascii=False)}"
        }],
    )
    raw = response.content[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


# ──────────────────────────────────────────────
# Slide Viewer (HTML Component)
# ──────────────────────────────────────────────
def render_slide_viewer(page_data, translated_texts=None, lang="ko"):
    """Render slide with text overlays using custom HTML."""
    img_b64 = page_data["image_b64"]
    blocks = page_data["text_blocks"]

    overlays_html = ""
    for i, block in enumerate(blocks):
        text = block["str"]
        if lang == "en" and translated_texts and i < len(translated_texts):
            text = translated_texts[i]

        css_class = "translated" if (lang == "en" and translated_texts) else "original"
        font_size = max(block["font_size"] * 0.75, 7)
        font_weight = 600 if block["font_size"] > 14 else 400

        escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")

        overlays_html += f"""
        <div class="text-overlay {css_class}" style="
            left: {block['x_pct']:.2f}%;
            top: {block['y_pct']:.2f}%;
            width: {block['w_pct'] + 1:.2f}%;
            min-height: {block['h_pct']:.2f}%;
            font-size: clamp(7px, {font_size * 0.12:.2f}vw, {font_size * 1.1:.0f}px);
            font-weight: {font_weight};
        ">{escaped}</div>"""

    html = f"""
    <div class="slide-viewer" style="position:relative; border-radius:10px; overflow:hidden;
         box-shadow: 0 8px 32px rgba(0,0,0,0.5); background:#0d1017;">
        <img src="data:image/png;base64,{img_b64}"
             style="width:100%; display:block; border-radius:10px;" />
        {overlays_html}
    </div>
    <style>
        .text-overlay {{
            position: absolute; pointer-events: none;
            line-height: 1.3; white-space: pre-wrap;
            word-break: keep-all; overflow: hidden;
            border-radius: 2px; padding: 1px 4px;
            font-family: 'IBM Plex Sans', 'Noto Sans KR', sans-serif;
        }}
        .text-overlay.original {{ background: rgba(255,255,255,0.88); color: #111; }}
        .text-overlay.translated {{
            background: rgba(255,255,255,0.92); color: #111;
            border-left: 2.5px solid #7c6df5;
        }}
    </style>
    """

    # Calculate height based on aspect ratio
    aspect = page_data["h"] / page_data["w"]
    estimated_height = int(800 * aspect) + 20

    st.components.v1.html(html, height=estimated_height, scrolling=False)


# ──────────────────────────────────────────────
# UI: Upload Screen
# ──────────────────────────────────────────────
def render_upload_screen():
    st.markdown("""
    <div class="upload-hero">
        <h1>BOD Slide Translator</h1>
        <p>이사회 미팅 자료를 업로드하면, 그래픽은 그대로 유지하면서<br>
        AI가 텍스트만 정확하게 한↔영 번역합니다.</p>
        <div class="features-grid">
            <div class="feature-card">
                <div class="icon">📄</div>
                <div class="title">PDF 슬라이드 인식</div>
                <div class="desc">취합된 PPT/PDF를 업로드하면 각 슬라이드를 자동으로 분리하고 텍스트 위치를 정밀하게 추출합니다.</div>
            </div>
            <div class="feature-card">
                <div class="icon">🌐</div>
                <div class="title">AI 번역 (한↔영)</div>
                <div class="desc">Claude AI가 이사회 문체에 맞게 번역합니다. 인명·약어는 자동 유지되고, 공간에 맞게 간결하게 번역됩니다.</div>
            </div>
            <div class="feature-card">
                <div class="icon">🎨</div>
                <div class="title">레이아웃 100% 보존</div>
                <div class="desc">차트, 그래픽, 도형 등 시각 요소는 원본 그대로 유지합니다. 텍스트만 같은 위치에서 언어가 전환됩니다.</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        uploaded = st.file_uploader(
            "PDF 파일을 선택하세요",
            type=["pdf"],
            label_visibility="collapsed",
        )
        if uploaded:
            st.session_state.file_name = uploaded.name
            with st.spinner("📄 슬라이드 분석 중..."):
                pages = process_pdf(uploaded.read())
                st.session_state.pages = pages
                st.session_state.processed = True
                st.session_state.current_page = 0
                st.session_state.translations = {}
                st.session_state.lang = "ko"
            st.rerun()


# ──────────────────────────────────────────────
# UI: Slide Viewer
# ──────────────────────────────────────────────
def render_viewer():
    pages = st.session_state.pages
    cur = st.session_state.current_page
    lang = st.session_state.lang
    total = len(pages)

    # ── Sidebar ──
    with st.sidebar:
        st.markdown(f"""
        <div class="sidebar-brand">BOD TRANSLATOR</div>
        <div class="sidebar-sub">Slide Translation Tool</div>
        """, unsafe_allow_html=True)

        if st.session_state.file_name:
            st.markdown(f'<div class="sidebar-filename" title="{st.session_state.file_name}">{st.session_state.file_name}</div>', unsafe_allow_html=True)

        st.markdown(f"<p style='font-size:11px; color:#4a5568; margin-bottom:8px;'>📑 {total}개 슬라이드</p>", unsafe_allow_html=True)

        # Thumbnail navigation
        for i, page in enumerate(pages):
            is_active = i == cur
            translated_mark = "✓ EN" if i in st.session_state.translations else ""
            border_color = "#7c6df5" if is_active else "transparent"
            opacity = "1" if is_active else "0.45"
            shadow = "0 0 8px rgba(124,109,245,0.25)" if is_active else "none"

            col_t, col_n = st.columns([5, 1])
            with col_t:
                if st.button(
                    f"Slide {i+1}",
                    key=f"thumb_{i}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state.current_page = i
                    st.rerun()
            with col_n:
                if translated_mark:
                    st.markdown(f"<span style='font-size:9px; color:#4ade80;'>{translated_mark}</span>", unsafe_allow_html=True)

        st.divider()
        if st.button("↻ 새 파일 업로드", use_container_width=True):
            for key in ["pages", "current_page", "lang", "translations", "file_name", "processed"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    # ── Main: Language Toggle ──
    tcol1, tcol2, tcol3 = st.columns([3, 5, 3])
    with tcol1:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🇰🇷  한국어", use_container_width=True,
                         type="primary" if lang == "ko" else "secondary"):
                st.session_state.lang = "ko"
                st.rerun()
        with c2:
            if st.button("🇺🇸  English", use_container_width=True,
                         type="primary" if lang == "en" else "secondary"):
                st.session_state.lang = "en"
                # Translate if needed
                if cur not in st.session_state.translations:
                    texts = [b["str"] for b in pages[cur]["text_blocks"]]
                    if texts:
                        with st.spinner("🌐 AI 번역 중..."):
                            try:
                                translated = translate_texts(texts)
                                st.session_state.translations[cur] = translated
                            except Exception as e:
                                st.error(f"번역 오류: {e}")
                st.rerun()

    with tcol2:
        block_count = len(pages[cur]["text_blocks"])
        status = ""
        if lang == "en" and cur in st.session_state.translations:
            status = '<span class="status-pill done">✓ 번역 완료</span>'
        st.markdown(f"""
        <div class="info-bar">
            <span class="info-badge">📝 {block_count}개 텍스트 블록 감지</span>
            {status}
        </div>
        """, unsafe_allow_html=True)

    # ── Main: Slide Display ──
    page_data = pages[cur]
    translated = st.session_state.translations.get(cur, None)

    render_slide_viewer(page_data, translated, lang)

    # ── Slide Navigation ──
    nav1, nav2, nav3, nav4, nav5 = st.columns([3, 1, 1, 1, 3])
    with nav2:
        if st.button("◀ 이전", disabled=(cur == 0), use_container_width=True):
            st.session_state.current_page = cur - 1
            st.rerun()
    with nav3:
        st.markdown(f"<div style='text-align:center; padding:8px 0; font-size:13px; color:#5a6a7d;'>{cur+1} / {total}</div>", unsafe_allow_html=True)
    with nav4:
        if st.button("다음 ▶", disabled=(cur == total - 1), use_container_width=True):
            st.session_state.current_page = cur + 1
            st.rerun()

    # ── Batch translate all (optional) ──
    with tcol3:
        untranslated = [i for i in range(total) if i not in st.session_state.translations]
        if untranslated and lang == "en":
            if st.button(f"🌐 전체 번역 ({len(untranslated)}장 남음)", use_container_width=True):
                progress = st.progress(0)
                for idx, page_idx in enumerate(untranslated):
                    texts = [b["str"] for b in pages[page_idx]["text_blocks"]]
                    if texts:
                        try:
                            translated = translate_texts(texts)
                            st.session_state.translations[page_idx] = translated
                        except Exception as e:
                            st.warning(f"슬라이드 {page_idx+1} 번역 실패: {e}")
                    progress.progress((idx + 1) / len(untranslated))
                st.rerun()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    if not st.session_state.get("processed") or not st.session_state.pages:
        render_upload_screen()
    else:
        render_viewer()

main()
