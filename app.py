import streamlit as st
import fitz  # PyMuPDF
import base64
import json
import os
import io
from datetime import datetime
from pathlib import Path

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="BOD Slide Translator",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATA_DIR = Path("data")
SLIDES_KO = DATA_DIR / "ko"
SLIDES_EN = DATA_DIR / "en"
SLIDES_THUMB = DATA_DIR / "thumbs"
META_FILE = DATA_DIR / "metadata.json"

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
    padding: 1.2rem 2rem 1rem !important;
    max-width: 1200px;
}

section[data-testid="stSidebar"] {
    background: #F7F8FA !important;
    border-right: 1px solid #E8EBF0;
}

/* Branding */
.sb-brand {
    font-size: 10px; font-weight: 700; letter-spacing: 0.12em;
    text-transform: uppercase; color: #4F46E5; margin-bottom: 2px;
}
.sb-sub { font-size: 10px; color: #9CA3AF; margin-bottom: 14px; }
.sb-label {
    font-size: 10px; font-weight: 600; color: #9CA3AF;
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px;
}
.sb-count { font-size: 11px; color: #6B7280; margin-bottom: 14px; }
.sb-meta {
    font-size: 10px; color: #9CA3AF; margin-top: 8px; line-height: 1.5;
}

/* Status */
.status { font-size: 12px; font-weight: 500; }
.status.done { color: #059669; }
.status.info { color: #6B7280; }

/* Welcome */
.welcome {
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    padding: 100px 40px; text-align: center;
}
.welcome h1 {
    font-size: 32px; font-weight: 700; color: #111827;
    margin-bottom: 8px; letter-spacing: -0.02em;
}
.welcome p { font-size: 15px; color: #6B7280; line-height: 1.7; }
.welcome .empty-msg {
    margin-top: 32px; padding: 20px 32px;
    background: #F9FAFB; border: 1px solid #F0F1F3;
    border-radius: 12px; font-size: 14px; color: #6B7280;
}

/* Admin panel */
.admin-header {
    font-size: 14px; font-weight: 600; color: #111827;
    margin-bottom: 12px; padding-bottom: 8px;
    border-bottom: 1px solid #F0F1F3;
}
.admin-success {
    padding: 16px; background: #F0FDF4; border: 1px solid #BBF7D0;
    border-radius: 10px; margin: 16px 0;
    font-size: 13px; color: #166534;
}

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
    "current_page": 0,
    "lang": "ko",
    "is_admin": False,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────
# Storage Utils
# ──────────────────────────────────────────────
def ensure_dirs():
    for d in [DATA_DIR, SLIDES_KO, SLIDES_EN, SLIDES_THUMB]:
        d.mkdir(parents=True, exist_ok=True)


def save_metadata(title_ko, title_en, num_pages, aspect_ratio=0.5625):
    meta = {
        "title_ko": title_ko,
        "title_en": title_en,
        "num_pages": num_pages,
        "aspect_ratio": aspect_ratio,
        "updated_at": datetime.now().isoformat(),
    }
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def load_metadata():
    if not META_FILE.exists():
        return None
    return json.loads(META_FILE.read_text())


def has_data():
    meta = load_metadata()
    return meta is not None and meta.get("num_pages", 0) > 0


# ──────────────────────────────────────────────
# PDF → Images
# ──────────────────────────────────────────────
def pdf_to_images(file_bytes, output_dir, make_thumbs=False):
    """Convert PDF pages to JPEG images. Returns (page_count, aspect_ratio)."""
    from PIL import Image

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    num = len(doc)
    aspect = 0.5625  # default 16:9

    for i in range(num):
        page = doc[i]

        # Capture aspect ratio from first page
        if i == 0:
            aspect = page.rect.height / page.rect.width

        # High-res slide image
        pix = page.get_pixmap(
            matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False
        )
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        (output_dir / f"page_{i+1:03d}.jpg").write_bytes(buf.getvalue())

        # Thumbnail (only for Korean version)
        if make_thumbs:
            tpix = page.get_pixmap(
                matrix=fitz.Matrix(THUMB_SCALE, THUMB_SCALE), alpha=False
            )
            timg = Image.frombytes("RGB", (tpix.width, tpix.height), tpix.samples)
            tbuf = io.BytesIO()
            timg.save(tbuf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
            (SLIDES_THUMB / f"page_{i+1:03d}.jpg").write_bytes(tbuf.getvalue())

    doc.close()
    return num, aspect


def get_slide_b64(lang, page_num):
    """Read a slide image as base64."""
    folder = SLIDES_KO if lang == "ko" else SLIDES_EN
    path = folder / f"page_{page_num:03d}.jpg"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode()


def get_thumb_b64(page_num):
    """Read a thumbnail as base64."""
    path = SLIDES_THUMB / f"page_{page_num:03d}.jpg"
    if not path.exists():
        return None
    return base64.b64encode(path.read_bytes()).decode()


# ──────────────────────────────────────────────
# UI: Slide Viewer (for everyone)
# ──────────────────────────────────────────────
def render_slide(page_num, lang):
    img_b64 = get_slide_b64(lang, page_num)
    if not img_b64:
        st.error(f"슬라이드 {page_num} 이미지를 찾을 수 없습니다.")
        return

    html = f"""
    <div style="position:relative; border-radius:6px; overflow:hidden;
         border:1px solid #E8EBF0; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <img src="data:image/jpeg;base64,{img_b64}"
             style="width:100%; display:block;" />
    </div>"""

    # Dynamic height from actual slide aspect ratio
    meta = load_metadata()
    aspect = meta.get("aspect_ratio", 0.5625) if meta else 0.5625
    # Content area is ~900px wide, calculate proportional height + padding
    height = int(900 * aspect) + 16
    st.components.v1.html(html, height=height, scrolling=False)


def render_slide_compare(page_num):
    """Show Korean and English slides side by side."""
    ko_b64 = get_slide_b64("ko", page_num)
    en_b64 = get_slide_b64("en", page_num)

    if not ko_b64 or not en_b64:
        st.error(f"슬라이드 {page_num} 이미지를 찾을 수 없습니다.")
        return

    html = f"""
    <div style="display:flex; gap:12px; width:100%;">
        <div style="flex:1; min-width:0;">
            <div style="font-size:11px; font-weight:600; color:#6B7280;
                 margin-bottom:6px; text-align:center;">🇰🇷 한국어</div>
            <div style="border-radius:6px; overflow:hidden;
                 border:1px solid #E8EBF0; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
                <img src="data:image/jpeg;base64,{ko_b64}"
                     style="width:100%; display:block;" />
            </div>
        </div>
        <div style="flex:1; min-width:0;">
            <div style="font-size:11px; font-weight:600; color:#4F46E5;
                 margin-bottom:6px; text-align:center;">🇺🇸 English</div>
            <div style="border-radius:6px; overflow:hidden;
                 border:1px solid #D1D5F0; box-shadow:0 1px 4px rgba(79,70,229,0.08);">
                <img src="data:image/jpeg;base64,{en_b64}"
                     style="width:100%; display:block;" />
            </div>
        </div>
    </div>"""

    meta = load_metadata()
    aspect = meta.get("aspect_ratio", 0.5625) if meta else 0.5625
    # Side by side: each image is ~half width, so height is roughly half
    height = int(480 * aspect) + 36
    st.components.v1.html(html, height=height, scrolling=False)


def render_viewer():
    meta = load_metadata()
    total = meta["num_pages"]
    cur = st.session_state.current_page
    lang = st.session_state.lang

    # Clamp current page
    if cur >= total:
        cur = 0
        st.session_state.current_page = 0

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">BOD TRANSLATOR</div>
        <div class="sb-sub">Board Meeting Materials</div>
        """, unsafe_allow_html=True)

        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>',
                    unsafe_allow_html=True)

        updated = meta.get("updated_at", "")[:10]
        st.markdown(f'<div class="sb-meta">최종 업데이트: {updated}</div>',
                    unsafe_allow_html=True)

        st.markdown('<div class="sb-label" style="margin-top:16px;">Slides</div>',
                    unsafe_allow_html=True)

        # Thumbnails
        for i in range(1, total + 1):
            is_cur = (i - 1) == cur
            bdr = "#4F46E5" if is_cur else "#E8EBF0"
            bdr_w = "2px" if is_cur else "1px"
            opa = "1" if is_cur else "0.5"
            shd = "0 0 0 3px rgba(79,70,229,0.1)" if is_cur else "none"

            thumb = get_thumb_b64(i)
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
                          border-radius:3px;">{i}</span>
                </div>
                """, unsafe_allow_html=True)

            if st.button(f"슬라이드 {i}", key=f"nav_{i}",
                         use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i - 1
                st.rerun()

    # ── Header: Language Toggle ──
    h1, h2 = st.columns([6, 5])

    with h1:
        c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
        with c1:
            if st.button("🇰🇷  한국어", use_container_width=True,
                         type="primary" if lang == "ko" else "secondary"):
                st.session_state.lang = "ko"
                st.rerun()
        with c2:
            if st.button("🇺🇸  English", use_container_width=True,
                         type="primary" if lang == "en" else "secondary"):
                st.session_state.lang = "en"
                st.rerun()
        with c3:
            if st.button("🔀  비교", use_container_width=True,
                         type="primary" if lang == "compare" else "secondary"):
                st.session_state.lang = "compare"
                st.rerun()

    with h2:
        labels = {"ko": "원본 (한국어)", "en": "English Version", "compare": "한국어 / English 비교"}
        cls = "info" if lang == "ko" else "done"
        st.markdown(f'<span class="status {cls}">{labels.get(lang, "")}</span>',
                    unsafe_allow_html=True)

    # ── Slide ──
    if lang == "compare":
        render_slide_compare(cur + 1)
    else:
        render_slide(cur + 1, lang)

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
# UI: Welcome (no data yet)
# ──────────────────────────────────────────────
def render_welcome():
    st.markdown("""
    <div class="welcome">
        <h1>BOD Slide Translator</h1>
        <p>이사회 미팅 자료를 한↔영 즉시 전환하여 확인할 수 있습니다.</p>
        <div class="empty-msg">
            📭 아직 등록된 자료가 없습니다.<br>
            사무국에서 자료를 업로드하면 이곳에서 바로 확인할 수 있습니다.
        </div>
    </div>
    """, unsafe_allow_html=True)


# ──────────────────────────────────────────────
# UI: Admin Panel
# ──────────────────────────────────────────────
def render_admin():
    st.markdown('<div class="admin-header">📤 이사회 자료 업로드 (사무국 전용)</div>',
                unsafe_allow_html=True)

    meta = load_metadata()
    if meta:
        st.info(f"현재 등록된 자료: {meta['num_pages']}페이지 (업데이트: {meta['updated_at'][:10]})")

    st.markdown("**한국어 원본 PDF**")
    pdf_ko = st.file_uploader("한국어 PDF", type=["pdf"], key="pdf_ko",
                               label_visibility="collapsed")

    st.markdown("**영문 번역본 PDF**")
    pdf_en = st.file_uploader("영문 PDF", type=["pdf"], key="pdf_en",
                               label_visibility="collapsed")

    if pdf_ko and pdf_en:
        if st.button("✅ 자료 저장", type="primary", use_container_width=True):
            ensure_dirs()

            # Clear old files
            for d in [SLIDES_KO, SLIDES_EN, SLIDES_THUMB]:
                for f in d.glob("*.jpg"):
                    f.unlink()

            progress = st.progress(0, text="한국어 PDF 처리 중...")

            # Process Korean PDF (with thumbnails)
            ko_bytes = pdf_ko.read()
            num_ko, aspect = pdf_to_images(ko_bytes, SLIDES_KO, make_thumbs=True)
            progress.progress(50, text="영문 PDF 처리 중...")

            # Process English PDF
            en_bytes = pdf_en.read()
            num_en, _ = pdf_to_images(en_bytes, SLIDES_EN, make_thumbs=False)
            progress.progress(100, text="완료!")
            progress.empty()

            # Validate page count
            if num_ko != num_en:
                st.error(f"⚠️ 페이지 수가 다릅니다: 한국어 {num_ko}페이지 / 영문 {num_en}페이지. "
                         f"동일한 자료의 한국어·영문 버전을 올려주세요.")
                return

            # Save metadata
            save_metadata(pdf_ko.name, pdf_en.name, num_ko, aspect)

            # Reset viewer state
            st.session_state.current_page = 0
            st.session_state.lang = "ko"

            st.markdown(f"""
            <div class="admin-success">
                ✅ 저장 완료! {num_ko}개 슬라이드가 등록되었습니다.<br>
                이사님들은 이 앱 URL로 접속하면 바로 확인할 수 있습니다.
            </div>
            """, unsafe_allow_html=True)

            st.rerun()

    elif pdf_ko or pdf_en:
        st.caption("한국어 PDF와 영문 PDF를 모두 업로드해주세요.")


# ──────────────────────────────────────────────
# Sidebar: Admin Login
# ──────────────────────────────────────────────
def render_sidebar_admin():
    with st.sidebar:
        st.divider()
        st.markdown('<div class="sb-label">관리자</div>', unsafe_allow_html=True)

        if st.session_state.is_admin:
            st.markdown("🔓 사무국 모드", unsafe_allow_html=True)
            if st.button("🔒 잠금", use_container_width=True):
                st.session_state.is_admin = False
                st.rerun()
        else:
            pw = st.text_input("비밀번호", type="password", label_visibility="collapsed",
                               placeholder="사무국 비밀번호")
            if pw:
                if pw == st.secrets.get("ADMIN_PASSWORD", ""):
                    st.session_state.is_admin = True
                    st.rerun()
                else:
                    st.caption("❌ 비밀번호가 틀립니다.")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    data_exists = has_data()

    if data_exists:
        render_viewer()
    else:
        render_welcome()

    # Admin panel (sidebar login + upload section)
    render_sidebar_admin()

    if st.session_state.is_admin:
        st.divider()
        render_admin()


main()
