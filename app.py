import streamlit as st
import fitz  # PyMuPDF
import anthropic
import base64
import json
import io

# ──────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="BOD Slide QC",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

RENDER_SCALE = 2.5
THUMB_SCALE = 0.35
JPEG_QUALITY = 90
THUMB_QUALITY = 55

STATUS_ICONS = {"unchecked": "⬜", "ok": "✅", "warn": "⚠️", "fix": "❌"}
STATUS_LABELS = {"unchecked": "미확인", "ok": "OK", "warn": "확인 필요", "fix": "수정 필요"}


# ──────────────────────────────────────────────
# CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+KR:wght@300;400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', 'Noto Sans KR', -apple-system, sans-serif; }
#MainMenu, header, footer { visibility: hidden; }
header { display: none; }
.stApp { background: #FFFFFF; }
.block-container { padding: 1rem 1.5rem 1rem !important; max-width: 100%; }
section[data-testid="stSidebar"] { background: #F7F8FA !important; border-right: 1px solid #E8EBF0; }

.upload-screen {
    display: flex; flex-direction: column;
    align-items: center; padding: 60px 40px; text-align: center;
}
.upload-screen h1 { font-size: 28px; font-weight: 700; color: #111827; margin-bottom: 6px; }
.upload-screen p { font-size: 14px; color: #6B7280; line-height: 1.7; margin-bottom: 28px; }

.sb-brand { font-size: 10px; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #4F46E5; margin-bottom: 2px; }
.sb-sub { font-size: 10px; color: #9CA3AF; margin-bottom: 14px; }
.sb-count { font-size: 11px; color: #6B7280; margin-bottom: 6px; }
.sb-label { font-size: 10px; font-weight: 600; color: #9CA3AF; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 8px; }

/* Review panel */
.review-box {
    background: #F9FAFB; border: 1px solid #E8EBF0;
    border-radius: 10px; padding: 16px 18px; margin-top: 12px;
    font-size: 13px; line-height: 1.7; color: #374151;
}
.review-box h4 {
    font-size: 13px; font-weight: 600; color: #111827;
    margin: 0 0 8px; padding: 0;
}
.review-issue {
    padding: 8px 12px; margin: 6px 0; border-radius: 8px;
    font-size: 12px; line-height: 1.6;
}
.review-issue.error { background: #FEF2F2; border-left: 3px solid #EF4444; color: #991B1B; }
.review-issue.warn { background: #FFFBEB; border-left: 3px solid #F59E0B; color: #92400E; }
.review-issue.info { background: #EFF6FF; border-left: 3px solid #3B82F6; color: #1E40AF; }
.review-issue.ok { background: #F0FDF4; border-left: 3px solid #22C55E; color: #166534; }

/* Status summary */
.status-row {
    display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0;
}
.status-chip {
    font-size: 11px; padding: 3px 10px; border-radius: 20px;
    font-weight: 500; display: inline-flex; align-items: center; gap: 4px;
}
.chip-ok { background: #F0FDF4; color: #166534; border: 1px solid #BBF7D0; }
.chip-warn { background: #FFFBEB; color: #92400E; border: 1px solid #FDE68A; }
.chip-fix { background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; }
.chip-unchecked { background: #F3F4F6; color: #6B7280; border: 1px solid #E5E7EB; }

/* Streamlit overrides */
div[data-testid="stFileUploader"] > div {
    border: 2px dashed #E5E7EB !important; border-radius: 12px !important; background: #FAFBFC !important;
}
div[data-testid="stFileUploader"] > div:hover { border-color: #4F46E5 !important; background: #F5F3FF !important; }
.stButton > button { border-radius: 8px; font-weight: 500; transition: all 0.15s; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Session State
# ──────────────────────────────────────────────
for k, v in {
    "pages_ko": [],
    "pages_en": [],
    "num_pages": 0,
    "aspect_ratio": 0.5625,
    "current_page": 0,
    "view_mode": "compare",
    "processed": False,
    "page_status": {},      # {page_idx: "ok"|"warn"|"fix"|"unchecked"}
    "page_notes": {},       # {page_idx: "note text"}
    "ai_reviews": {},       # {page_idx: "review markdown"}
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────
# PDF Processing (with text extraction)
# ──────────────────────────────────────────────
def process_pdf(file_bytes, with_thumbs=False):
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

        # Text extraction
        text = extract_page_text(page)

        pages.append({"image_b64": img_b64, "thumb_b64": thumb_b64, "text": text})

    doc.close()
    return pages, aspect


def extract_page_text(page):
    """Extract readable text from a PDF page."""
    blocks = page.get_text("dict")["blocks"]
    lines = []
    for block in blocks:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            parts = []
            for s in line["spans"]:
                t = s["text"].strip()
                if t:
                    parts.append(t)
            if parts:
                lines.append(" ".join(parts))
    return "\n".join(lines)


# ──────────────────────────────────────────────
# AI Review
# ──────────────────────────────────────────────
def ai_review_page(ko_text, en_text, page_num):
    """Use Claude to compare KR/EN and flag issues."""
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system="""You are a QC reviewer for board of directors (이사회) meeting materials translation.
Compare the Korean original and English translation, then provide a structured review.

Rules:
1. Check for mistranslations or meaning changes.
2. Check for missing content (text in Korean but absent in English, or vice versa).
3. Check proper nouns, company names, abbreviations — they should be kept as-is.
4. Check if the tone is formal enough for board-level communication.
5. Check number/date accuracy.
6. If everything looks good, say so briefly.

Format your response as a JSON object:
{
  "verdict": "ok" | "warn" | "fix",
  "summary": "one-line overall assessment in Korean",
  "issues": [
    {"level": "error"|"warn"|"info", "detail": "description in Korean"}
  ]
}

verdict meanings:
- "ok": No issues found, translation is accurate
- "warn": Minor issues that should be double-checked
- "fix": Significant issues that need correction

Return ONLY the JSON. No markdown fences.""",
        messages=[{
            "role": "user",
            "content": f"""슬라이드 {page_num} 검토:

[한국어 원본]
{ko_text if ko_text.strip() else "(텍스트 없음 — 이미지/차트 슬라이드)"}

[영문 번역]
{en_text if en_text.strip() else "(텍스트 없음 — 이미지/차트 슬라이드)"}"""
        }],
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def ai_review_all():
    """Review all pages at once."""
    reviews = {}
    total = st.session_state.num_pages
    progress = st.progress(0, text="AI 검토 중...")

    for i in range(total):
        ko_text = st.session_state.pages_ko[i]["text"]
        en_text = st.session_state.pages_en[i]["text"]
        try:
            result = ai_review_page(ko_text, en_text, i + 1)
            reviews[i] = result
            # Auto-set status from verdict
            st.session_state.page_status[i] = result.get("verdict", "unchecked")
        except Exception as e:
            reviews[i] = {
                "verdict": "warn",
                "summary": f"AI 검토 실패: {e}",
                "issues": [{"level": "warn", "detail": f"API 오류로 검토 불가: {e}"}]
            }
        progress.progress((i + 1) / total, text=f"검토 중... {i+1}/{total}")

    progress.empty()
    return reviews


# ──────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────
def slide_html(img_b64, border_color="#E8EBF0"):
    return f"""
    <div style="border-radius:6px; overflow:hidden;
         border:1px solid {border_color}; box-shadow:0 1px 4px rgba(0,0,0,0.06);">
        <img src="data:image/jpeg;base64,{img_b64}" style="width:100%; display:block;" />
    </div>"""


def render_compare(idx):
    ko = st.session_state.pages_ko[idx]["image_b64"]
    en = st.session_state.pages_en[idx]["image_b64"]
    html = f"""
    <div style="display:flex; gap:14px; width:100%;">
        <div style="flex:1; min-width:0;">
            <div style="font-size:12px;font-weight:600;color:#374151;text-align:center;padding:4px 0 8px;">🇰🇷 한국어</div>
            {slide_html(ko)}
        </div>
        <div style="flex:1; min-width:0;">
            <div style="font-size:12px;font-weight:600;color:#4F46E5;text-align:center;padding:4px 0 8px;">🇺🇸 English</div>
            {slide_html(en, "#D1D5F0")}
        </div>
    </div>"""
    aspect = st.session_state.aspect_ratio
    st.components.v1.html(html, height=int(520 * aspect) + 40, scrolling=False)


def render_single(idx, lang):
    pages = st.session_state.pages_ko if lang == "ko" else st.session_state.pages_en
    img_b64 = pages[idx]["image_b64"]
    border = "#E8EBF0" if lang == "ko" else "#D1D5F0"
    label = "🇰🇷 한국어" if lang == "ko" else "🇺🇸 English"
    color = "#374151" if lang == "ko" else "#4F46E5"
    html = f"""
    <div style="max-width:1000px; margin:0 auto;">
        <div style="font-size:12px;font-weight:600;color:{color};text-align:center;padding:4px 0 8px;">{label}</div>
        {slide_html(img_b64, border)}
    </div>"""
    aspect = st.session_state.aspect_ratio
    st.components.v1.html(html, height=int(960 * aspect) + 40, scrolling=False)


def render_review_panel(idx):
    """Show AI review results + status controls + notes for current page."""
    review = st.session_state.ai_reviews.get(idx)
    status = st.session_state.page_status.get(idx, "unchecked")
    note = st.session_state.page_notes.get(idx, "")

    # ── Status toggle ──
    r1, r2 = st.columns([5, 6])

    with r1:
        st.markdown(f"**슬라이드 {idx+1} 상태**")
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            if st.button("✅ OK", key=f"s_ok_{idx}", use_container_width=True,
                         type="primary" if status == "ok" else "secondary"):
                st.session_state.page_status[idx] = "ok"
                st.rerun()
        with s2:
            if st.button("⚠️ 확인", key=f"s_warn_{idx}", use_container_width=True,
                         type="primary" if status == "warn" else "secondary"):
                st.session_state.page_status[idx] = "warn"
                st.rerun()
        with s3:
            if st.button("❌ 수정", key=f"s_fix_{idx}", use_container_width=True,
                         type="primary" if status == "fix" else "secondary"):
                st.session_state.page_status[idx] = "fix"
                st.rerun()
        with s4:
            if st.button("⬜ 초기화", key=f"s_unc_{idx}", use_container_width=True,
                         type="secondary"):
                st.session_state.page_status[idx] = "unchecked"
                st.rerun()

    with r2:
        new_note = st.text_input("📝 메모", value=note, key=f"note_{idx}",
                                  placeholder="이 슬라이드에 대한 메모...",
                                  label_visibility="collapsed")
        if new_note != note:
            st.session_state.page_notes[idx] = new_note

    # ── AI Review Result ──
    if review:
        verdict = review.get("verdict", "unchecked")
        summary = review.get("summary", "")
        issues = review.get("issues", [])

        v_icon = {"ok": "✅", "warn": "⚠️", "fix": "❌"}.get(verdict, "⬜")

        st.markdown(f"""<div class="review-box">
            <h4>🤖 AI 검토 결과 — {v_icon} {summary}</h4>
        </div>""", unsafe_allow_html=True)

        if issues:
            for issue in issues:
                level = issue.get("level", "info")
                detail = issue.get("detail", "")
                css_cls = {"error": "error", "warn": "warn", "info": "info"}.get(level, "info")
                level_label = {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(level, "ℹ️")
                st.markdown(f'<div class="review-issue {css_cls}">{level_label} {detail}</div>',
                            unsafe_allow_html=True)
        elif verdict == "ok":
            st.markdown('<div class="review-issue ok">✅ 이 슬라이드는 번역이 정확합니다.</div>',
                        unsafe_allow_html=True)


# ──────────────────────────────────────────────
# UI: Upload Screen
# ──────────────────────────────────────────────
def render_upload():
    st.markdown("""
    <div class="upload-screen">
        <h1>🔍 BOD Slide QC</h1>
        <p>이사회 자료의 한국어·영문 PDF를 나란히 비교하고<br>
        AI가 번역 적절성을 자동으로 검토합니다.</p>
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
                progress.progress(100)
                progress.empty()

                if len(ko_pages) != len(en_pages):
                    st.error(f"⚠️ 페이지 수가 다릅니다: 한국어 {len(ko_pages)}p / 영문 {len(en_pages)}p")
                    return

                st.session_state.pages_ko = ko_pages
                st.session_state.pages_en = en_pages
                st.session_state.num_pages = len(ko_pages)
                st.session_state.aspect_ratio = aspect
                st.session_state.current_page = 0
                st.session_state.view_mode = "compare"
                st.session_state.processed = True
                st.session_state.page_status = {i: "unchecked" for i in range(len(ko_pages))}
                st.session_state.page_notes = {}
                st.session_state.ai_reviews = {}
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

    # ── Sidebar ──
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">BOD SLIDE QC</div>
        <div class="sb-sub">Translation Review Tool</div>
        """, unsafe_allow_html=True)

        # Status summary
        statuses = st.session_state.page_status
        counts = {}
        for s in statuses.values():
            counts[s] = counts.get(s, 0) + 1

        chips = ""
        for key in ["ok", "warn", "fix", "unchecked"]:
            c = counts.get(key, 0)
            if c > 0:
                chips += f'<span class="status-chip chip-{key}">{STATUS_ICONS[key]} {c}</span>'

        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>', unsafe_allow_html=True)
        if chips:
            st.markdown(f'<div class="status-row">{chips}</div>', unsafe_allow_html=True)

        # AI Review all button
        has_api = bool(st.secrets.get("ANTHROPIC_API_KEY", ""))
        if has_api:
            if st.button("🤖 전체 AI 검토", use_container_width=True, type="primary"):
                st.session_state.ai_reviews = ai_review_all()
                st.rerun()

        st.markdown('<div class="sb-label" style="margin-top:12px;">Slides</div>',
                    unsafe_allow_html=True)

        # Thumbnails with status
        for i in range(total):
            is_cur = i == cur
            status = statuses.get(i, "unchecked")
            icon = STATUS_ICONS[status]
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
                    <img src="data:image/jpeg;base64,{thumb}" style="width:100%;display:block;" />
                    <span style="position:absolute;bottom:3px;right:5px;
                          font-size:9px;font-weight:600;color:#fff;
                          background:rgba(0,0,0,0.5);padding:1px 5px;
                          border-radius:3px;">{icon} {i+1}</span>
                </div>""", unsafe_allow_html=True)

            if st.button(f"{icon} 슬라이드 {i+1}", key=f"nav_{i}",
                         use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i
                st.rerun()

        st.divider()
        if st.button("↻ 새 파일로 교체", use_container_width=True):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

    # ── Header: View Mode ──
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
        cur_status = st.session_state.page_status.get(cur, "unchecked")
        s_icon = STATUS_ICONS[cur_status]
        s_label = STATUS_LABELS[cur_status]
        st.markdown(
            f'<div style="text-align:right;padding-top:6px;">'
            f'<span style="font-size:13px;font-weight:500;color:#374151;">'
            f'{s_icon} 슬라이드 {cur+1} — {s_label}</span></div>',
            unsafe_allow_html=True)

    # ── Slide ──
    if mode == "compare":
        render_compare(cur)
    else:
        render_single(cur, mode)

    # ── Review Panel ──
    render_review_panel(cur)

    # ── AI review for single page ──
    if has_api and cur not in st.session_state.ai_reviews:
        if st.button(f"🤖 이 슬라이드 AI 검토", key=f"ai_{cur}"):
            with st.spinner("AI 검토 중..."):
                ko_text = st.session_state.pages_ko[cur]["text"]
                en_text = st.session_state.pages_en[cur]["text"]
                try:
                    result = ai_review_page(ko_text, en_text, cur + 1)
                    st.session_state.ai_reviews[cur] = result
                    st.session_state.page_status[cur] = result.get("verdict", "unchecked")
                except Exception as e:
                    st.error(f"AI 검토 실패: {e}")
                st.rerun()

    # ── Navigation ──
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
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
