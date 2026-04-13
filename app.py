import streamlit as st
import fitz  # PyMuPDF
import anthropic
import json
import base64
import time

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
# Custom CSS — Clean White Theme
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', 'Noto Sans KR', -apple-system, sans-serif;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, header, footer { visibility: hidden; }
header { display: none; }

/* ── App background ── */
.stApp { background: #FFFFFF; }

/* ── Main content area ── */
.block-container {
    padding: 1.2rem 2rem 1rem !important;
    max-width: 1200px;
}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {
    background: #F7F8FA !important;
    border-right: 1px solid #E8EBF0;
}

/* ── Upload area ── */
.upload-area {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 80px 40px; text-align: center;
}
.upload-area h1 {
    font-size: 32px; font-weight: 700; color: #111827;
    margin-bottom: 8px; letter-spacing: -0.02em;
}
.upload-area .sub {
    font-size: 15px; color: #6B7280; line-height: 1.7;
    margin-bottom: 32px;
}
.features {
    display: grid; grid-template-columns: repeat(3, 1fr);
    gap: 16px; margin-bottom: 40px; width: 100%; max-width: 620px;
}
.feat {
    background: #F9FAFB; border: 1px solid #F0F1F3;
    border-radius: 12px; padding: 20px 16px; text-align: left;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.feat:hover {
    border-color: #D1D5DB; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.feat .ic { font-size: 20px; margin-bottom: 8px; }
.feat .tt { font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 3px; }
.feat .dd { font-size: 11px; color: #9CA3AF; line-height: 1.5; }

/* ── Header bar ── */
.header-bar {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 0 16px; margin-bottom: 16px;
    border-bottom: 1px solid #F0F1F3;
}
.header-left { display: flex; align-items: center; gap: 14px; }
.header-right { display: flex; align-items: center; gap: 10px; }

/* ── Language toggle ── */
.lang-toggle {
    display: inline-flex; background: #F3F4F6;
    border-radius: 10px; padding: 3px; gap: 2px;
}
.lang-btn {
    padding: 7px 22px; border-radius: 8px; border: none;
    font-size: 13px; font-weight: 600; cursor: pointer;
    transition: all 0.2s; font-family: inherit;
    text-decoration: none; display: inline-block;
}
.lang-btn.active {
    background: #4F46E5; color: #fff;
    box-shadow: 0 1px 4px rgba(79,70,229,0.3);
}
.lang-btn.inactive {
    background: transparent; color: #9CA3AF;
}

/* ── Status ── */
.status { font-size: 12px; font-weight: 500; }
.status.done { color: #059669; }
.status.info { color: #6B7280; }

/* ── Slide container ── */
.slide-container {
    border: 1px solid #E8EBF0;
    border-radius: 8px;
    overflow: hidden;
    background: #FAFBFC;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.slide-container img {
    width: 100%; display: block;
}

/* ── Text overlay (English mode) ── */
.txt-overlay {
    position: absolute; pointer-events: none;
    background: rgba(255,255,255,0.93);
    border-left: 2.5px solid #4F46E5;
    padding: 1px 5px 1px 4px;
    line-height: 1.25;
    font-family: 'Inter', 'Noto Sans KR', sans-serif;
    color: #111827;
    white-space: pre-wrap;
    word-break: keep-all;
    overflow: hidden;
    border-radius: 1px;
}

/* ── Navigation ── */
.slide-nav {
    display: flex; align-items: center; justify-content: center;
    gap: 20px; padding: 14px 0 4px;
}
.nav-btn {
    padding: 6px 20px; border-radius: 8px;
    border: 1px solid #E5E7EB; background: #fff;
    color: #374151; font-size: 13px; font-weight: 500;
    cursor: pointer; transition: all 0.15s;
    font-family: inherit;
}
.nav-btn:hover { background: #F9FAFB; border-color: #D1D5DB; }
.nav-btn:disabled { color: #D1D5DB; cursor: default; }
.nav-info {
    font-size: 14px; color: #6B7280; font-weight: 500;
    font-variant-numeric: tabular-nums; min-width: 70px; text-align: center;
}

/* ── Sidebar elements ── */
.sb-brand {
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: #4F46E5; margin-bottom: 2px;
}
.sb-sub { font-size: 10px; color: #9CA3AF; margin-bottom: 14px; }
.sb-file {
    font-size: 11px; color: #374151; background: #fff;
    border: 1px solid #E8EBF0; padding: 7px 10px;
    border-radius: 6px; margin-bottom: 14px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.sb-label {
    font-size: 10px; font-weight: 600; color: #9CA3AF;
    text-transform: uppercase; letter-spacing: 0.06em;
    margin-bottom: 8px;
}
.sb-count {
    font-size: 11px; color: #6B7280; margin-bottom: 14px;
}

/* ── Streamlit overrides ── */
div[data-testid="stFileUploader"] > div {
    border: 2px dashed #E5E7EB !important;
    border-radius: 12px !important;
    background: #FAFBFC !important;
}
div[data-testid="stFileUploader"] > div:hover {
    border-color: #4F46E5 !important;
    background: #F5F3FF !important;
}
.stButton > button {
    border-radius: 8px; font-weight: 500;
    transition: all 0.15s;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Session State Init
# ──────────────────────────────────────────────
for k, v in {
    "pages": [],
    "current_page": 0,
    "lang": "ko",
    "translations": {},
    "all_translated": False,
    "file_name": "",
    "processed": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────
# PDF Processing — High Fidelity
# ──────────────────────────────────────────────
RENDER_SCALE = 3.0   # 216 DPI — crisp, screenshot-quality
THUMB_SCALE = 0.35

def process_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    progress = st.progress(0, text="슬라이드 분석 중...")

    for i in range(len(doc)):
        page = doc[i]
        pw, ph = page.rect.width, page.rect.height

        # ── High-res render (screenshot quality) ──
        mat = fitz.Matrix(RENDER_SCALE, RENDER_SCALE)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()

        # ── Thumbnail ──
        tmat = fitz.Matrix(THUMB_SCALE, THUMB_SCALE)
        tpix = page.get_pixmap(matrix=tmat, alpha=False)
        thumb_b64 = base64.b64encode(tpix.tobytes("png")).decode()

        # ── Text extraction with precise positions ──
        text_blocks = extract_text_blocks(page, pw, ph)

        pages.append({
            "image_b64": img_b64,
            "thumb_b64": thumb_b64,
            "text_blocks": text_blocks,
            "w": pw, "h": ph,
            "img_w": pix.width, "img_h": pix.height,
        })
        progress.progress((i + 1) / len(doc), text=f"슬라이드 {i+1}/{len(doc)} 처리 중...")

    doc.close()
    progress.empty()
    return pages


def extract_text_blocks(page, pw, ph):
    """Extract text lines with precise percentage-based coordinates."""
    blocks_raw = page.get_text("dict")["blocks"]
    lines_out = []

    for block in blocks_raw:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            spans = line["spans"]
            if not spans:
                continue
            text = ""
            for s in spans:
                t = s["text"]
                if t.strip():
                    text += t
            if not text.strip():
                continue

            bbox = line["bbox"]
            font_size = max(s["size"] for s in spans)

            lines_out.append({
                "str": text,
                "x_pct": (bbox[0] / pw) * 100,
                "y_pct": (bbox[1] / ph) * 100,
                "w_pct": ((bbox[2] - bbox[0]) / pw) * 100,
                "h_pct": ((bbox[3] - bbox[1]) / ph) * 100,
                "font_size": font_size,
            })

    # Group lines into logical blocks
    return group_into_blocks(lines_out)


def group_into_blocks(items):
    if not items:
        return []

    items.sort(key=lambda t: (t["y_pct"], t["x_pct"]))
    blocks = []
    used = set()

    for i, item in enumerate(items):
        if i in used:
            continue
        block = [item]
        used.add(i)

        for j in range(i + 1, len(items)):
            if j in used:
                continue
            last = block[-1]
            gap = items[j]["y_pct"] - (last["y_pct"] + last["h_pct"])
            x_aligned = abs(items[j]["x_pct"] - block[0]["x_pct"]) < 2.5

            if x_aligned and -0.3 < gap < last["h_pct"] * 1.0:
                block.append(items[j])
                used.add(j)

        text = "\n".join(b["str"] for b in block)
        x = min(b["x_pct"] for b in block)
        y = min(b["y_pct"] for b in block)
        w = max(b["x_pct"] + b["w_pct"] for b in block) - x
        h = max(b["y_pct"] + b["h_pct"] for b in block) - y
        fs = block[0]["font_size"]

        blocks.append({
            "str": text, "x_pct": x, "y_pct": y,
            "w_pct": w, "h_pct": h, "font_size": fs,
        })

    return blocks


# ──────────────────────────────────────────────
# Translation — Batch (All Pages at Once)
# ──────────────────────────────────────────────
def translate_all_pages(pages):
    """Translate ALL slides at once, with progress."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    translations = {}
    total = len(pages)
    progress = st.progress(0, text="전체 슬라이드 번역 중...")

    for idx, page in enumerate(pages):
        texts = [b["str"] for b in page["text_blocks"]]
        if not texts:
            translations[idx] = []
            progress.progress((idx + 1) / total, text=f"번역 중... {idx+1}/{total}")
            continue

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system="""You are a professional Korean→English translator for board of directors (이사회) meeting materials at a major Korean corporation.

Rules:
1. Formal, concise business English for board-level readers.
2. Keep proper nouns, company names, abbreviations, numbers unchanged (KRAFTON, ADK, 3Q24, etc.).
3. Be concise — slides have limited space. Match the original brevity.
4. If text is already English or is a number/symbol, return it unchanged.
5. Translate naturally, not word-for-word. Clarity over literalness.
6. Return ONLY a JSON array of translated strings in exact input order. No markdown, no explanation.""",
                messages=[{
                    "role": "user",
                    "content": f"Translate each text block Korean→English. Return JSON array:\n{json.dumps(texts, ensure_ascii=False)}"
                }],
            )
            raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
            translations[idx] = json.loads(raw)
        except Exception as e:
            st.warning(f"슬라이드 {idx+1} 번역 실패: {e}")
            translations[idx] = texts  # fallback to original

        progress.progress((idx + 1) / total, text=f"번역 중... {idx+1}/{total}")

    progress.empty()
    return translations


# ──────────────────────────────────────────────
# Slide Renderer (HTML)
# ──────────────────────────────────────────────
def render_slide(page_data, translated_texts=None, lang="ko"):
    """Render slide as high-fidelity image. In EN mode, overlay translated text."""
    img_b64 = page_data["image_b64"]
    aspect = page_data["h"] / page_data["w"]

    if lang == "ko" or not translated_texts:
        # ── Korean: pure image, no overlay ──
        html = f"""
        <div class="slide-container" style="position:relative; border-radius:6px;
             overflow:hidden; border:1px solid #E8EBF0;
             box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
            <img src="data:image/png;base64,{img_b64}"
                 style="width:100%; display:block;" />
        </div>"""
    else:
        # ── English: image + translated overlays ──
        overlays = ""
        blocks = page_data["text_blocks"]
        for i, block in enumerate(blocks):
            if i >= len(translated_texts):
                break
            text = translated_texts[i]
            escaped = (text.replace("&", "&amp;").replace("<", "&lt;")
                          .replace(">", "&gt;").replace("\n", "<br>"))
            fs = max(block["font_size"] * 0.72, 7)
            fw = 600 if block["font_size"] > 13 else 400

            overlays += f"""
            <div style="position:absolute;
                left:{block['x_pct']:.2f}%; top:{block['y_pct']:.2f}%;
                width:{block['w_pct'] + 0.8:.2f}%; min-height:{block['h_pct']:.2f}%;
                background:rgba(255,255,255,0.92);
                border-left:2.5px solid #4F46E5;
                padding:1px 5px 1px 4px;
                font-size:clamp(6px, {fs * 0.11:.2f}vw, {fs * 1.1:.0f}px);
                font-weight:{fw};
                line-height:1.28;
                font-family:'Inter','Noto Sans KR',sans-serif;
                color:#111827;
                white-space:pre-wrap;
                word-break:keep-all;
                overflow:hidden;
                border-radius:1px;
                pointer-events:none;
            ">{escaped}</div>"""

        html = f"""
        <div class="slide-container" style="position:relative; border-radius:6px;
             overflow:hidden; border:1px solid #E8EBF0;
             box-shadow: 0 1px 4px rgba(0,0,0,0.06);">
            <img src="data:image/png;base64,{img_b64}"
                 style="width:100%; display:block;" />
            {overlays}
        </div>"""

    height = int(760 * aspect) + 10
    st.components.v1.html(html, height=height, scrolling=False)


# ──────────────────────────────────────────────
# UI: Upload Screen
# ──────────────────────────────────────────────
def render_upload():
    st.markdown("""
    <div class="upload-area">
        <h1>BOD Slide Translator</h1>
        <p class="sub">
            이사회 미팅 자료 PDF를 업로드하면, 슬라이드를 원본 그대로 보여주면서<br>
            AI가 텍스트만 한↔영 번역합니다.
        </p>
        <div class="features">
            <div class="feat">
                <div class="ic">📄</div>
                <div class="tt">원본 그대로 렌더링</div>
                <div class="dd">PDF 슬라이드를 고해상도로 렌더링하여 원본과 동일한 화면을 보여줍니다.</div>
            </div>
            <div class="feat">
                <div class="ic">🌐</div>
                <div class="tt">AI 한↔영 번역</div>
                <div class="dd">Claude AI가 이사회 문체로 번역합니다. 인명·약어는 자동 유지됩니다.</div>
            </div>
            <div class="feat">
                <div class="ic">⚡</div>
                <div class="tt">전체 일괄 번역</div>
                <div class="dd">버튼 한 번에 모든 슬라이드를 번역하고, 자유롭게 넘기며 확인합니다.</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        uploaded = st.file_uploader("PDF 파일 업로드", type=["pdf"], label_visibility="collapsed")
        if uploaded:
            st.session_state.file_name = uploaded.name
            pages = process_pdf(uploaded.read())
            st.session_state.pages = pages
            st.session_state.processed = True
            st.session_state.current_page = 0
            st.session_state.translations = {}
            st.session_state.all_translated = False
            st.session_state.lang = "ko"
            st.rerun()


# ──────────────────────────────────────────────
# UI: Viewer
# ──────────────────────────────────────────────
def render_viewer():
    pages = st.session_state.pages
    cur = st.session_state.current_page
    lang = st.session_state.lang
    total = len(pages)
    is_translated = st.session_state.all_translated

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">BOD TRANSLATOR</div>
        <div class="sb-sub">Slide Translation Tool</div>
        """, unsafe_allow_html=True)

        if st.session_state.file_name:
            st.markdown(f'<div class="sb-file">{st.session_state.file_name}</div>', unsafe_allow_html=True)

        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-label">Slides</div>', unsafe_allow_html=True)

        for i in range(total):
            is_cur = i == cur
            border = "2px solid #4F46E5" if is_cur else "1px solid #E8EBF0"
            opacity = "1" if is_cur else "0.5"
            shadow = "0 0 0 3px rgba(79,70,229,0.12)" if is_cur else "none"

            thumb_html = f"""
            <div style="border-radius:6px; overflow:hidden; border:{border};
                 opacity:{opacity}; box-shadow:{shadow}; margin-bottom:8px;
                 cursor:pointer; transition:all 0.15s; position:relative;">
                <img src="data:image/png;base64,{pages[i]['thumb_b64']}"
                     style="width:100%; display:block;" />
                <span style="position:absolute; bottom:3px; right:5px;
                      font-size:9px; font-weight:600; color:#fff;
                      background:rgba(0,0,0,0.55); padding:1px 5px;
                      border-radius:3px;">{i+1}</span>
            </div>
            """
            if st.button(f"　Slide {i+1}　", key=f"nav_{i}",
                         use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i
                st.rerun()

        st.divider()
        if st.button("↻ 새 파일 업로드", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ── Header: Language toggle ──
    h1, h2, h3 = st.columns([4, 4, 3])

    with h1:
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            if st.button("🇰🇷  한국어", use_container_width=True,
                         type="primary" if lang == "ko" else "secondary"):
                st.session_state.lang = "ko"
                st.rerun()
        with c2:
            if st.button("🇺🇸  English", use_container_width=True,
                         type="primary" if lang == "en" else "secondary"):
                if not is_translated:
                    # Translate ALL pages at once
                    st.session_state.translations = translate_all_pages(pages)
                    st.session_state.all_translated = True
                st.session_state.lang = "en"
                st.rerun()

    with h2:
        if lang == "en" and is_translated:
            st.markdown('<span class="status done">✓ 전체 번역 완료</span>', unsafe_allow_html=True)
        elif lang == "ko":
            st.markdown(f'<span class="status info">원본 (한국어)</span>', unsafe_allow_html=True)

    with h3:
        block_count = len(pages[cur]["text_blocks"])
        st.markdown(f'<div style="text-align:right;"><span style="font-size:12px; color:#9CA3AF;">텍스트 블록: {block_count}개</span></div>', unsafe_allow_html=True)

    # ── Slide Display ──
    page_data = pages[cur]
    translated = st.session_state.translations.get(cur) if lang == "en" else None

    render_slide(page_data, translated, lang)

    # ── Navigation ──
    n1, n2, n3, n4, n5 = st.columns([3, 1, 1, 1, 3])
    with n2:
        if st.button("◀ 이전", disabled=(cur == 0), use_container_width=True):
            st.session_state.current_page = cur - 1
            st.rerun()
    with n3:
        st.markdown(f'<div style="text-align:center; padding:8px 0; font-size:14px; color:#6B7280; font-weight:500;">{cur+1} / {total}</div>', unsafe_allow_html=True)
    with n4:
        if st.button("다음 ▶", disabled=(cur == total - 1), use_container_width=True):
            st.session_state.current_page = cur + 1
            st.rerun()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if not st.session_state.get("processed"):
    render_upload()
else:
    render_viewer()
