import streamlit as st
import fitz  # PyMuPDF
import base64
import io

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="BOD Slide Translator QC",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

RENDER_SCALE = 2.5
THUMB_SCALE = 0.35
JPEG_QUALITY = 90
THUMB_QUALITY = 55


# ──────────────────────────────────────────────
# CSS
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
    padding: 1rem 1.5rem 1rem !important;
    max-width: 100%;
}

section[data-testid="stSidebar"] {
    background: #F7F8FA !important;
    border-right: 1px solid #E8EBF0;
}

/* Upload screen */
.upload-screen {
    display: flex; flex-direction: column;
    align-items: center; padding: 60px 40px; text-align: center;
}
.upload-screen h1 {
    font-size: 28px; font-weight: 700; color: #111827;
    margin-bottom: 6px; letter-spacing: -0.02em;
}
.upload-screen p {
    font-size: 14px; color: #6B7280; line-height: 1.7; margin-bottom: 28px;
}
.upload-cards {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 20px; width: 100%; max-width: 640px; margin-bottom: 28px;
}
.upload-card {
    background: #F9FAFB; border: 1px solid #F0F1F3;
    border-radius: 12px; padding: 20px; text-align: center;
}
.upload-card .label {
    font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 4px;
}
.upload-card .desc { font-size: 11px; color: #9CA3AF; }

/* Sidebar */
.sb-brand {
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: #4F46E5; margin-bottom: 2px;
}
.sb-sub { font-size: 10px; color: #9CA3AF; margin-bottom: 14px; }
.sb-count { font-size: 11px; color: #6B7280; margin-bottom: 10px; }
.sb-label {
    font-size: 10px; font-weight: 600; color: #9CA3AF;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;
}

/* View mode labels */
.lang-label {
    font-size: 12px; font-weight: 600; text-align: center;
    padding: 5px 0 8px; border-radius: 6px;
}
.lang-label.ko { color: #374151; }
.lang-label.en { color: #4F46E5; }

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
    "pages_ko": [],       # [{image_b64, thumb_b64}]
    "pages_en": [],
    "num_pages": 0,
    "aspect_ratio": 0.5625,
    "current_page": 0,
    "view_mode": "compare",  # compare | ko | en
    "processed": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────
# PDF Processing
# ──────────────────────────────────────────────
def process_pdf(file_bytes, with_thumbs=False):
    """Convert PDF to list of {image_b64, thumb_b64}. Returns (pages, aspect_ratio)."""
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    aspect = 0.5625

    for i in range(len(doc)):
        page = doc[i]
        if i == 0:
            aspect = page.rect.height / page.rect.width

        # Slide image
        pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        img_b64 = base64.b64encode(buf.getvalue()).decode()

        # Thumbnail
        thumb_b64 = ""
        if with_thumbs:
            tpix = page.get_pixmap(matrix=fitz.Matrix(THUMB_SCALE, THUMB_SCALE), alpha=False)
            timg = Image.frombytes("RGB", (tpix.width, tpix.height), tpix.samples)
            tbuf = io.BytesIO()
            timg.save(tbuf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
            thumb_b64 = base64.b64encode(tbuf.getvalue()).decode()

        pages.append({"image_b64": img_b64, "thumb_b64": thumb_b64})

    doc.close()
    return pages, aspect


# ──────────────────────────────────────────────
# Slide Rendering
# ──────────────────────────────────────────────
def slide_html(img_b64, border_color="#E8EBF0"):
    return f"""
    <div style="border-radius:6px; overflow:hidden;
         border:1px solid {border_color}; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <img src="data:image/jpeg;base64,{img_b64}"
             style="width:100%; display:block;" />
    </div>"""


def render_compare(page_idx):
    """Side-by-side Korean / English."""
    ko = st.session_state.pages_ko[page_idx]["image_b64"]
    en = st.session_state.pages_en[page_idx]["image_b64"]

    html = f"""
    <div style="display:flex; gap:14px; width:100%;">
        <div style="flex:1; min-width:0;">
            <div style="font-size:12px; font-weight:600; color:#374151;
                 text-align:center; padding:4px 0 8px;">🇰🇷 한국어</div>
            {slide_html(ko)}
        </div>
        <div style="flex:1; min-width:0;">
            <div style="font-size:12px; font-weight:600; color:#4F46E5;
                 text-align:center; padding:4px 0 8px;">🇺🇸 English</div>
            {slide_html(en, "#D1D5F0")}
        </div>
    </div>"""

    aspect = st.session_state.aspect_ratio
    height = int(520 * aspect) + 40
    st.components.v1.html(html, height=height, scrolling=False)


def render_single(page_idx, lang):
    """Full-width single slide (enlarged)."""
    pages = st.session_state.pages_ko if lang == "ko" else st.session_state.pages_en
    img_b64 = pages[page_idx]["image_b64"]
    border = "#E8EBF0" if lang == "ko" else "#D1D5F0"

    label_text = "🇰🇷 한국어" if lang == "ko" else "🇺🇸 English"
    label_color = "#374151" if lang == "ko" else "#4F46E5"

    html = f"""
    <div style="max-width:1000px; margin:0 auto;">
        <div style="font-size:12px; font-weight:600; color:{label_color};
             text-align:center; padding:4px 0 8px;">{label_text}</div>
        {slide_html(img_b64, border)}
    </div>"""

    aspect = st.session_state.aspect_ratio
    height = int(960 * aspect) + 40
    st.components.v1.html(html, height=height, scrolling=False)


# ──────────────────────────────────────────────
# UI: Upload Screen
# ──────────────────────────────────────────────
def render_upload():
    st.markdown("""
    <div class="upload-screen">
        <h1>🔍 BOD Slide QC</h1>
        <p>이사회 자료의 한국어·영문 PDF를 나란히 비교하여<br>
        페이지별 번역 적절성을 최종 확인합니다.</p>
    </div>
    """, unsafe_allow_html=True)

    u1, u2 = st.columns(2, gap="large")

    with u1:
        st.markdown("**🇰🇷 한국어 원본 PDF**")
        pdf_ko = st.file_uploader("한국어 PDF", type=["pdf"], key="up_ko",
                                   label_visibility="collapsed")

    with u2:
        st.markdown("**🇺🇸 영문 번역 PDF**")
        pdf_en = st.file_uploader("영문 PDF", type=["pdf"], key="up_en",
                                   label_visibility="collapsed")

    if pdf_ko and pdf_en:
        _, col_btn, _ = st.columns([1, 2, 1])
        with col_btn:
            if st.button("🔍  비교 시작", type="primary", use_container_width=True):
                progress = st.progress(0, text="한국어 PDF 처리 중...")

                ko_pages, aspect = process_pdf(pdf_ko.read(), with_thumbs=True)
                progress.progress(50, text="영문 PDF 처리 중...")

                en_pages, _ = process_pdf(pdf_en.read(), with_thumbs=False)
                progress.progress(100, text="완료!")
                progress.empty()

                if len(ko_pages) != len(en_pages):
                    st.error(f"⚠️ 페이지 수가 다릅니다: 한국어 {len(ko_pages)}페이지 / "
                             f"영문 {len(en_pages)}페이지. 동일한 자료를 올려주세요.")
                    return

                st.session_state.pages_ko = ko_pages
                st.session_state.pages_en = en_pages
                st.session_state.num_pages = len(ko_pages)
                st.session_state.aspect_ratio = aspect
                st.session_state.current_page = 0
                st.session_state.view_mode = "compare"
                st.session_state.processed = True
                st.rerun()

    elif pdf_ko or pdf_en:
        st.caption("한국어 PDF와 영문 PDF를 모두 올려주세요.")


# ──────────────────────────────────────────────
# UI: QC Viewer
# ──────────────────────────────────────────────
def render_viewer():
    total = st.session_state.num_pages
    cur = st.session_state.current_page
    mode = st.session_state.view_mode

    if cur >= total:
        cur = 0
        st.session_state.current_page = 0

    # ── Sidebar: Thumbnails ──
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">BOD SLIDE QC</div>
        <div class="sb-sub">Translation Review Tool</div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>',
                    unsafe_allow_html=True)
        st.markdown('<div class="sb-label">Slides</div>', unsafe_allow_html=True)

        for i in range(total):
            is_cur = i == cur
            bdr = "#4F46E5" if is_cur else "#E8EBF0"
            bdr_w = "2px" if is_cur else "1px"
            opa = "1" if is_cur else "0.5"
            shd = "0 0 0 3px rgba(79,70,229,0.1)" if is_cur else "none"

            thumb = st.session_state.pages_ko[i].get("thumb_b64", "")
            if thumb:
                st.markdown(f"""
                <div style="border-radius:6px; overflow:hidden;
                     border:{bdr_w} solid {bdr}; opacity:{opa};
                     box-shadow:{shd}; margin-bottom:4px; position:relative;">
                    <img src="data:image/jpeg;base64,{thumb}"
                         style="width:100%; display:block;" />
                    <span style="position:absolute; bottom:3px; right:5px;
                          font-size:9px; font-weight:600; color:#fff;
                          background:rgba(0,0,0,0.5); padding:1px 5px;
                          border-radius:3px;">{i+1}</span>
                </div>""", unsafe_allow_html=True)

            if st.button(f"슬라이드 {i+1}", key=f"nav_{i}",
                         use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i
                st.rerun()

        st.divider()
        if st.button("↻ 새 파일로 교체", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ── Header: View Mode Toggle ──
    h1, h2 = st.columns([7, 4])

    with h1:
        c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
        with c1:
            if st.button("🔀 비교", use_container_width=True,
                         type="primary" if mode == "compare" else "secondary"):
                st.session_state.view_mode = "compare"
                st.rerun()
        with c2:
            if st.button("🇰🇷 한국어 확대", use_container_width=True,
                         type="primary" if mode == "ko" else "secondary"):
                st.session_state.view_mode = "ko"
                st.rerun()
        with c3:
            if st.button("🇺🇸 English 확대", use_container_width=True,
                         type="primary" if mode == "en" else "secondary"):
                st.session_state.view_mode = "en"
                st.rerun()

    with h2:
        labels = {"compare": "한국어 / English 나란히 비교",
                  "ko": "한국어 확대 보기", "en": "English 확대 보기"}
        st.markdown(
            f'<div style="text-align:right; padding-top:6px;">'
            f'<span style="font-size:12px; color:#9CA3AF;">{labels[mode]}</span></div>',
            unsafe_allow_html=True)

    # ── Slide ──
    if mode == "compare":
        render_compare(cur)
    else:
        render_single(cur, mode)

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
