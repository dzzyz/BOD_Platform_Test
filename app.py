import streamlit as st
import fitz  # PyMuPDF
import anthropic
import json
import base64
import html as html_lib
import io

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

#MainMenu, header, footer { visibility: hidden; }
header { display: none; }
.stApp { background: #FFFFFF; }

.block-container {
    padding: 1.2rem 2rem 1rem !important;
    max-width: 1200px;
}

section[data-testid="stSidebar"] {
    background: #F7F8FA !important;
    border-right: 1px solid #E8EBF0;
}

/* Upload */
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
    font-size: 15px; color: #6B7280; line-height: 1.7; margin-bottom: 32px;
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
.feat:hover { border-color: #D1D5DB; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
.feat .ic { font-size: 20px; margin-bottom: 8px; }
.feat .tt { font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 3px; }
.feat .dd { font-size: 11px; color: #9CA3AF; line-height: 1.5; }

/* Status */
.status { font-size: 12px; font-weight: 500; }
.status.done { color: #059669; }
.status.info { color: #6B7280; }

/* Sidebar */
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
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;
}
.sb-count { font-size: 11px; color: #6B7280; margin-bottom: 14px; }

/* Streamlit overrides */
div[data-testid="stFileUploader"] > div {
    border: 2px dashed #E5E7EB !important;
    border-radius: 12px !important; background: #FAFBFC !important;
}
div[data-testid="stFileUploader"] > div:hover {
    border-color: #4F46E5 !important; background: #F5F3FF !important;
}
.stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.15s; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Session State
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
# PDF Processing — Memory Optimized
# ──────────────────────────────────────────────
RENDER_SCALE = 2.5   # 180 DPI — sharp, lighter than 3x
THUMB_SCALE = 0.35
JPEG_QUALITY = 88


def pixmap_to_jpeg_b64(pixmap, quality=JPEG_QUALITY):
    """Convert pixmap → JPEG base64. ~70% smaller than PNG."""
    from PIL import Image
    img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def process_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    progress = st.progress(0, text="슬라이드 분석 중...")

    for i in range(len(doc)):
        page = doc[i]
        pw, ph = page.rect.width, page.rect.height

        # ── Slide image (JPEG compressed) ──
        pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
        try:
            img_b64 = pixmap_to_jpeg_b64(pix, JPEG_QUALITY)
            img_fmt = "jpeg"
        except ImportError:
            img_b64 = base64.b64encode(pix.tobytes("png")).decode()
            img_fmt = "png"

        # ── Thumbnail (low-quality JPEG) ──
        tpix = page.get_pixmap(matrix=fitz.Matrix(THUMB_SCALE, THUMB_SCALE), alpha=False)
        try:
            thumb_b64 = pixmap_to_jpeg_b64(tpix, 55)
        except ImportError:
            thumb_b64 = base64.b64encode(tpix.tobytes("png")).decode()

        # ── Text extraction ──
        text_blocks = extract_text_blocks(page, pw, ph)

        pages.append({
            "image_b64": img_b64,
            "image_fmt": img_fmt,
            "thumb_b64": thumb_b64,
            "text_blocks": text_blocks,
            "w": pw, "h": ph,
        })
        progress.progress((i + 1) / len(doc), text=f"슬라이드 {i+1}/{len(doc)} 처리 중...")

    doc.close()
    progress.empty()
    return pages


# ──────────────────────────────────────────────
# Text Extraction — Improved Accuracy
# ──────────────────────────────────────────────
def extract_text_blocks(page, pw, ph):
    blocks_raw = page.get_text("dict")["blocks"]
    lines_out = []

    for block in blocks_raw:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            spans = line["spans"]
            if not spans:
                continue

            # [FIX #3] Proper span joining with spaces
            parts = []
            for s in spans:
                t = s["text"]
                if t.strip():
                    parts.append(t.strip())
            if not parts:
                continue
            text = " ".join(parts)
            # Collapse multiple spaces
            while "  " in text:
                text = text.replace("  ", " ")

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

    return group_into_blocks(lines_out)


def group_into_blocks(items):
    """Group text lines into logical blocks with adaptive thresholds."""
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

            # [FIX #3] Adaptive x-alignment threshold
            # Wider text blocks → more tolerance
            x_tol = max(2.0, min(block[0]["w_pct"] * 0.08, 5.0))
            x_ok = abs(items[j]["x_pct"] - block[0]["x_pct"]) < x_tol

            # [FIX #3] Tighter gap threshold to avoid cross-section merging
            gap_ok = -0.3 < gap < last["h_pct"] * 0.8

            if x_ok and gap_ok:
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
# Translation — Robust Batch with Retry
# ──────────────────────────────────────────────
MAX_RETRIES = 2


def translate_all_pages(pages):
    """Translate ALL slides at once with progress bar."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    translations = {}
    total = len(pages)
    progress = st.progress(0, text="전체 슬라이드 번역 중...")

    for idx, page in enumerate(pages):
        texts = [b["str"] for b in page["text_blocks"]]
        if not texts:
            translations[idx] = []
        else:
            translations[idx] = translate_with_retry(client, texts)
        progress.progress((idx + 1) / total, text=f"번역 중... {idx+1}/{total}")

    progress.empty()
    return translations


def translate_with_retry(client, texts):
    """Translate with retry logic + array length validation."""
    n = len(texts)

    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=8192,
                system=f"""You are a professional Korean→English translator for board of directors (이사회) meeting materials at a major Korean corporation.

Rules:
1. Formal, concise business English for board-level readers.
2. Keep proper nouns, company names, abbreviations, numbers unchanged (KRAFTON, ADK, 3Q24, etc.).
3. Be concise — slides have limited space. Match the original brevity.
4. If text is already English or is a number/symbol, return it unchanged.
5. Translate naturally, not word-for-word. Clarity over literalness.
6. Return EXACTLY {n} items in the JSON array — one per input, same order.
7. Return ONLY a valid JSON array. No markdown, no explanation.""",
                messages=[{
                    "role": "user",
                    "content": f"Translate {n} text blocks Korean→English. Return JSON array with exactly {n} strings:\n{json.dumps(texts, ensure_ascii=False)}"
                }],
            )
            raw = response.content[0].text.strip()
            raw = raw.replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)

            if not isinstance(result, list):
                raise ValueError("Not a JSON array")

            # [FIX #2] Validate & fix length mismatch
            if len(result) < n:
                result.extend(texts[len(result):])  # pad with originals
            elif len(result) > n:
                result = result[:n]  # trim excess

            return result

        except Exception as e:
            if attempt < MAX_RETRIES:
                continue
            st.warning(f"번역 실패 ({MAX_RETRIES}회 재시도 후): {e}")
            return list(texts)  # fallback to originals


# ──────────────────────────────────────────────
# Slide Renderer
# ──────────────────────────────────────────────
def render_slide(page_data, translated_texts=None, lang="ko"):
    img_b64 = page_data["image_b64"]
    img_fmt = page_data.get("image_fmt", "png")
    aspect = page_data["h"] / page_data["w"]

    if lang == "ko" or not translated_texts:
        # Korean: pure original image — zero overlay
        html = f"""
        <div style="position:relative; border-radius:6px; overflow:hidden;
             border:1px solid #E8EBF0; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <img src="data:image/{img_fmt};base64,{img_b64}"
                 style="width:100%; display:block;" />
        </div>"""
    else:
        # English: image + translated overlays
        overlays = ""
        blocks = page_data["text_blocks"]
        for i, block in enumerate(blocks):
            if i >= len(translated_texts):
                break

            text = translated_texts[i]
            escaped = html_lib.escape(text).replace("\n", "<br>")
            fs = max(block["font_size"] * 0.72, 7)
            fw = 600 if block["font_size"] > 13 else 400

            # [FIX #2] Auto-expand width for English text
            kr_chars = len(block["str"].replace("\n", ""))
            en_chars = len(text.replace("\n", ""))
            ratio = max(en_chars / max(kr_chars, 1), 1.0)
            expanded_w = block["w_pct"] * max(ratio * 0.85, 1.05)
            # Clamp: don't overflow past right edge (leave 3% margin)
            max_w = 97 - block["x_pct"]
            expanded_w = min(expanded_w, max_w)

            overlays += f"""
            <div style="position:absolute;
                left:{block['x_pct']:.2f}%; top:{block['y_pct']:.2f}%;
                width:{expanded_w:.2f}%; min-height:{block['h_pct']:.2f}%;
                background:rgba(255,255,255,0.93);
                border-left:2.5px solid #4F46E5;
                padding:2px 6px 2px 5px;
                font-size:clamp(6px, {fs*0.11:.2f}vw, {fs*1.1:.0f}px);
                font-weight:{fw};
                line-height:1.30;
                font-family:'Inter','Noto Sans KR',sans-serif;
                color:#111827;
                white-space:pre-wrap;
                word-break:break-word;
                overflow-wrap:break-word;
                border-radius:2px;
                pointer-events:none;
            ">{escaped}</div>"""

        html = f"""
        <div style="position:relative; border-radius:6px; overflow:hidden;
             border:1px solid #E8EBF0; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <img src="data:image/{img_fmt};base64,{img_b64}"
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

        safe_name = html_lib.escape(st.session_state.file_name)
        if safe_name:
            st.markdown(f'<div class="sb-file" title="{safe_name}">{safe_name}</div>',
                        unsafe_allow_html=True)

        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>', unsafe_allow_html=True)
        st.markdown('<div class="sb-label">Slides</div>', unsafe_allow_html=True)

        # [FIX #5] Actual thumbnail images in sidebar
        for i in range(total):
            is_cur = i == cur
            bdr = "#4F46E5" if is_cur else "#E8EBF0"
            bdr_w = "2px" if is_cur else "1px"
            opa = "1" if is_cur else "0.5"
            shd = "0 0 0 3px rgba(79,70,229,0.1)" if is_cur else "none"

            st.markdown(f"""
            <div style="border-radius:6px; overflow:hidden;
                 border:{bdr_w} solid {bdr}; opacity:{opa};
                 box-shadow:{shd}; margin-bottom:4px; position:relative;">
                <img src="data:image/jpeg;base64,{pages[i]['thumb_b64']}"
                     style="width:100%; display:block;" />
                <span style="position:absolute; bottom:3px; right:5px;
                      font-size:9px; font-weight:600; color:#fff;
                      background:rgba(0,0,0,0.5); padding:1px 5px;
                      border-radius:3px;">{i+1}</span>
            </div>
            """, unsafe_allow_html=True)

            if st.button(f"슬라이드 {i+1}", key=f"nav_{i}",
                         use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i
                st.rerun()

        st.divider()
        if st.button("↻ 새 파일 업로드", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ── Header ──
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
                    st.session_state.translations = translate_all_pages(pages)
                    st.session_state.all_translated = True
                st.session_state.lang = "en"
                st.rerun()

    with h2:
        if lang == "en" and is_translated:
            st.markdown('<span class="status done">✓ 전체 번역 완료</span>',
                        unsafe_allow_html=True)
        elif lang == "ko":
            st.markdown('<span class="status info">원본 (한국어)</span>',
                        unsafe_allow_html=True)

    with h3:
        bc = len(pages[cur]["text_blocks"])
        st.markdown(
            f'<div style="text-align:right;">'
            f'<span style="font-size:12px;color:#9CA3AF;">텍스트 블록: {bc}개</span></div>',
            unsafe_allow_html=True)

    # ── Slide ──
    translated = st.session_state.translations.get(cur) if lang == "en" else None
    render_slide(pages[cur], translated, lang)

    # ── Navigation ──
    n1, n2, n3, n4, n5 = st.columns([3, 1, 1, 1, 3])
    with n2:
        if st.button("◀ 이전", disabled=(cur == 0), use_container_width=True):
            st.session_state.current_page = cur - 1
            st.rerun()
    with n3:
        st.markdown(
            f'<div style="text-align:center;padding:8px 0;font-size:14px;'
            f'color:#6B7280;font-weight:500;">{cur+1} / {total}</div>',
            unsafe_allow_html=True)
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
