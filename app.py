import streamlit as st
import fitz  # PyMuPDF
import anthropic
import base64
import json
import io
from datetime import datetime

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
STATUS_COLORS = {
    "ok": ("#F0FDF4", "#166534", "#BBF7D0"),
    "warn": ("#FFFBEB", "#92400E", "#FDE68A"),
    "fix": ("#FEF2F2", "#991B1B", "#FECACA"),
    "unchecked": ("#F3F4F6", "#6B7280", "#E5E7EB"),
}


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

.upload-screen { display:flex;flex-direction:column;align-items:center;padding:60px 40px;text-align:center; }
.upload-screen h1 { font-size:28px;font-weight:700;color:#111827;margin-bottom:6px; }
.upload-screen p { font-size:14px;color:#6B7280;line-height:1.7;margin-bottom:28px; }

.sb-brand { font-size:10px;font-weight:700;letter-spacing:0.12em;text-transform:uppercase;color:#4F46E5;margin-bottom:2px; }
.sb-sub { font-size:10px;color:#9CA3AF;margin-bottom:14px; }
.sb-count { font-size:11px;color:#6B7280;margin-bottom:6px; }
.sb-label { font-size:10px;font-weight:600;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px; }

.status-row { display:flex;gap:8px;flex-wrap:wrap;margin:8px 0; }
.status-chip { font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500;display:inline-flex;align-items:center;gap:4px; }
.chip-ok { background:#F0FDF4;color:#166534;border:1px solid #BBF7D0; }
.chip-warn { background:#FFFBEB;color:#92400E;border:1px solid #FDE68A; }
.chip-fix { background:#FEF2F2;color:#991B1B;border:1px solid #FECACA; }
.chip-unchecked { background:#F3F4F6;color:#6B7280;border:1px solid #E5E7EB; }

/* Review result card */
.rv-card {
    border:1px solid #E8EBF0; border-radius:10px; margin-bottom:16px;
    overflow:hidden; background:#fff;
}
.rv-header {
    display:flex; align-items:center; justify-content:space-between;
    padding:12px 16px; border-bottom:1px solid #F0F1F3; background:#F9FAFB;
}
.rv-page { font-size:14px; font-weight:600; color:#111827; }
.rv-verdict { font-size:12px; font-weight:600; padding:3px 12px; border-radius:20px; }
.rv-body { padding:14px 16px; }
.rv-summary { font-size:13px; color:#374151; margin-bottom:10px; line-height:1.6; }
.rv-issue { padding:8px 12px; margin:5px 0; border-radius:8px; font-size:12px; line-height:1.6; }
.rv-issue.error { background:#FEF2F2; border-left:3px solid #EF4444; color:#991B1B; }
.rv-issue.warn { background:#FFFBEB; border-left:3px solid #F59E0B; color:#92400E; }
.rv-issue.info { background:#EFF6FF; border-left:3px solid #3B82F6; color:#1E40AF; }
.rv-issue.ok { background:#F0FDF4; border-left:3px solid #22C55E; color:#166534; }
.rv-note { font-size:12px; color:#6B7280; margin-top:8px; font-style:italic; }
.rv-images { display:flex; gap:10px; margin-bottom:12px; }
.rv-images > div { flex:1; min-width:0; }
.rv-images img { width:100%; display:block; border-radius:4px; border:1px solid #E8EBF0; }
.rv-img-label { font-size:10px; font-weight:600; text-align:center; padding:3px 0 5px; }

div[data-testid="stFileUploader"] > div { border:2px dashed #E5E7EB!important;border-radius:12px!important;background:#FAFBFC!important; }
div[data-testid="stFileUploader"] > div:hover { border-color:#4F46E5!important;background:#F5F3FF!important; }
.stButton > button { border-radius:8px;font-weight:500;transition:all 0.15s; }
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Session State
# ──────────────────────────────────────────────
for k, v in {
    "pages_ko": [], "pages_en": [],
    "num_pages": 0, "aspect_ratio": 0.5625,
    "current_page": 0, "view_mode": "compare",
    "processed": False,
    "page_status": {}, "page_notes": {}, "ai_reviews": {},
}.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ──────────────────────────────────────────────
# PDF Processing
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
        pix = page.get_pixmap(matrix=fitz.Matrix(RENDER_SCALE, RENDER_SCALE), alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        img_b64 = base64.b64encode(buf.getvalue()).decode()
        thumb_b64 = ""
        if with_thumbs:
            tpix = page.get_pixmap(matrix=fitz.Matrix(THUMB_SCALE, THUMB_SCALE), alpha=False)
            timg = Image.frombytes("RGB", (tpix.width, tpix.height), tpix.samples)
            tbuf = io.BytesIO()
            timg.save(tbuf, format="JPEG", quality=THUMB_QUALITY, optimize=True)
            thumb_b64 = base64.b64encode(tbuf.getvalue()).decode()
        text = extract_page_text(page)
        pages.append({"image_b64": img_b64, "thumb_b64": thumb_b64, "text": text})
    doc.close()
    return pages, aspect


def extract_page_text(page):
    blocks = page.get_text("dict")["blocks"]
    lines = []
    for block in blocks:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            parts = [s["text"].strip() for s in line["spans"] if s["text"].strip()]
            if parts:
                lines.append(" ".join(parts))
    return "\n".join(lines)


# ──────────────────────────────────────────────
# AI Review
# ──────────────────────────────────────────────
def has_api_key():
    return bool(st.secrets.get("ANTHROPIC_API_KEY", ""))


def ai_review_page(client, ko_text, en_text, page_num):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system="""You are a QC reviewer for board of directors (이사회) meeting materials translation.
Compare the Korean original with the English translation.

Check for:
1. Mistranslations or meaning changes
2. Missing/added content
3. Proper noun errors (company names, person names, abbreviations should be unchanged)
4. Tone appropriateness for board-level communication
5. Number/date accuracy

Return a JSON object:
{
  "verdict": "ok" | "warn" | "fix",
  "summary": "한국어로 한줄 요약",
  "issues": [
    {"level": "error"|"warn"|"info", "detail": "한국어로 구체적 설명"}
  ]
}

- "ok": 문제 없음
- "warn": 경미한 확인 필요 사항
- "fix": 수정 필요한 오류

텍스트가 없는 슬라이드(이미지/차트만)는 "ok"로 처리.
Return ONLY JSON. No markdown fences.""",
        messages=[{
            "role": "user",
            "content": f"""슬라이드 {page_num}:

[한국어]
{ko_text if ko_text.strip() else "(텍스트 없음)"}

[English]
{en_text if en_text.strip() else "(No text)"}"""
        }],
    )
    raw = response.content[0].text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(raw)


def ai_review_all():
    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    reviews = {}
    total = st.session_state.num_pages
    progress = st.progress(0, text="AI 검토 중...")
    for i in range(total):
        ko_text = st.session_state.pages_ko[i]["text"]
        en_text = st.session_state.pages_en[i]["text"]
        try:
            result = ai_review_page(client, ko_text, en_text, i + 1)
            reviews[i] = result
            st.session_state.page_status[i] = result.get("verdict", "unchecked")
        except Exception as e:
            reviews[i] = {"verdict": "warn", "summary": f"검토 실패: {e}", "issues": []}
        progress.progress((i + 1) / total, text=f"검토 중... {i+1}/{total}")
    progress.empty()
    return reviews


# ──────────────────────────────────────────────
# Report Export
# ──────────────────────────────────────────────
def generate_report_csv():
    """Generate CSV report of all QC results."""
    lines = ["슬라이드,상태,AI 판정,AI 요약,이슈 수,이슈 상세,메모"]
    for i in range(st.session_state.num_pages):
        status = STATUS_LABELS.get(st.session_state.page_status.get(i, "unchecked"), "미확인")
        review = st.session_state.ai_reviews.get(i, {})
        verdict = review.get("verdict", "-")
        summary = review.get("summary", "-").replace(",", ";").replace("\n", " ")
        issues = review.get("issues", [])
        issue_count = len(issues)
        issue_details = " | ".join(
            f"[{iss.get('level','')}] {iss.get('detail','')}" for iss in issues
        ).replace(",", ";").replace("\n", " ")
        note = st.session_state.page_notes.get(i, "").replace(",", ";").replace("\n", " ")
        lines.append(f"{i+1},{status},{verdict},{summary},{issue_count},{issue_details},{note}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Rendering
# ──────────────────────────────────────────────
def slide_html(img_b64, border="#E8EBF0"):
    return f'<div style="border-radius:6px;overflow:hidden;border:1px solid {border};box-shadow:0 1px 4px rgba(0,0,0,0.06);"><img src="data:image/jpeg;base64,{img_b64}" style="width:100%;display:block;"/></div>'


def render_compare(idx):
    ko = st.session_state.pages_ko[idx]["image_b64"]
    en = st.session_state.pages_en[idx]["image_b64"]
    html = f'''<div style="display:flex;gap:14px;width:100%;">
        <div style="flex:1;min-width:0;"><div style="font-size:12px;font-weight:600;color:#374151;text-align:center;padding:4px 0 8px;">🇰🇷 한국어</div>{slide_html(ko)}</div>
        <div style="flex:1;min-width:0;"><div style="font-size:12px;font-weight:600;color:#4F46E5;text-align:center;padding:4px 0 8px;">🇺🇸 English</div>{slide_html(en,"#D1D5F0")}</div>
    </div>'''
    st.components.v1.html(html, height=int(520 * st.session_state.aspect_ratio) + 40, scrolling=False)


def render_single(idx, lang):
    pages = st.session_state.pages_ko if lang == "ko" else st.session_state.pages_en
    img = pages[idx]["image_b64"]
    border = "#E8EBF0" if lang == "ko" else "#D1D5F0"
    label = "🇰🇷 한국어" if lang == "ko" else "🇺🇸 English"
    color = "#374151" if lang == "ko" else "#4F46E5"
    html = f'<div style="max-width:1000px;margin:0 auto;"><div style="font-size:12px;font-weight:600;color:{color};text-align:center;padding:4px 0 8px;">{label}</div>{slide_html(img,border)}</div>'
    st.components.v1.html(html, height=int(960 * st.session_state.aspect_ratio) + 40, scrolling=False)


def render_review_results():
    """Scrollable view of ALL review results with mini slide previews."""
    total = st.session_state.num_pages
    reviews = st.session_state.ai_reviews
    has_reviews = len(reviews) > 0

    if not has_reviews:
        st.info("🤖 '전체 AI 검토' 버튼을 눌러 검토를 시작하세요.")
        return

    # Summary stats
    counts = {}
    for i in range(total):
        v = st.session_state.page_status.get(i, "unchecked")
        counts[v] = counts.get(v, 0) + 1

    chips = ""
    for key in ["fix", "warn", "ok", "unchecked"]:
        c = counts.get(key, 0)
        if c > 0:
            bg, fg, bd = STATUS_COLORS[key]
            chips += f'<span class="status-chip" style="background:{bg};color:{fg};border:1px solid {bd};">{STATUS_ICONS[key]} {STATUS_LABELS[key]}: {c}장</span>'
    st.markdown(f'<div class="status-row" style="margin-bottom:16px;">{chips}</div>', unsafe_allow_html=True)

    # Filter
    filter_opt = st.radio("필터", ["전체", "❌ 수정 필요", "⚠️ 확인 필요", "✅ OK"],
                           horizontal=True, label_visibility="collapsed")
    filter_map = {"전체": None, "❌ 수정 필요": "fix", "⚠️ 확인 필요": "warn", "✅ OK": "ok"}
    active_filter = filter_map[filter_opt]

    # Cards
    for i in range(total):
        status = st.session_state.page_status.get(i, "unchecked")
        if active_filter and status != active_filter:
            continue

        review = reviews.get(i, {})
        verdict = review.get("verdict", "unchecked")
        summary = review.get("summary", "검토 결과 없음")
        issues = review.get("issues", [])
        note = st.session_state.page_notes.get(i, "")

        bg, fg, bd = STATUS_COLORS.get(verdict, STATUS_COLORS["unchecked"])
        v_label = STATUS_LABELS.get(verdict, "미확인")
        v_icon = STATUS_ICONS.get(verdict, "⬜")

        # Build issues HTML
        issues_html = ""
        for iss in issues:
            level = iss.get("level", "info")
            detail = iss.get("detail", "")
            css = {"error": "error", "warn": "warn", "info": "info"}.get(level, "info")
            icon = {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(level, "ℹ️")
            issues_html += f'<div class="rv-issue {css}">{icon} {detail}</div>'

        if not issues and verdict == "ok":
            issues_html = '<div class="rv-issue ok">✅ 번역이 정확합니다.</div>'

        note_html = f'<div class="rv-note">📝 {note}</div>' if note else ""

        # Mini slide previews
        ko_thumb = st.session_state.pages_ko[i].get("thumb_b64", "")
        en_thumb = st.session_state.pages_en[i].get("thumb_b64", st.session_state.pages_en[i].get("image_b64", ""))

        # Use thumbnails for KO, but EN doesn't have thumbs — use small version
        images_html = ""
        if ko_thumb:
            images_html = f'''<div class="rv-images">
                <div><div class="rv-img-label" style="color:#374151;">🇰🇷 한국어</div><img src="data:image/jpeg;base64,{ko_thumb}"/></div>
                <div><div class="rv-img-label" style="color:#4F46E5;">🇺🇸 English</div><img src="data:image/jpeg;base64,{en_thumb}"/></div>
            </div>'''

        st.markdown(f'''
        <div class="rv-card">
            <div class="rv-header">
                <span class="rv-page">슬라이드 {i+1}</span>
                <span class="rv-verdict" style="background:{bg};color:{fg};border:1px solid {bd};">{v_icon} {v_label}</span>
            </div>
            <div class="rv-body">
                {images_html}
                <div class="rv-summary">{summary}</div>
                {issues_html}
                {note_html}
            </div>
        </div>''', unsafe_allow_html=True)

        # Inline note input
        new_note = st.text_input(f"📝 슬라이드 {i+1} 메모", value=note, key=f"note_{i}",
                                  placeholder="메모 입력...", label_visibility="collapsed")
        if new_note != note:
            st.session_state.page_notes[i] = new_note


# ──────────────────────────────────────────────
# Status Controls (for slide view modes)
# ──────────────────────────────────────────────
def render_status_controls(idx):
    status = st.session_state.page_status.get(idx, "unchecked")
    review = st.session_state.ai_reviews.get(idx)

    r1, r2 = st.columns([5, 6])
    with r1:
        st.markdown(f"**슬라이드 {idx+1} 상태**")
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            if st.button("✅ OK", key=f"s_ok_{idx}", use_container_width=True,
                         type="primary" if status == "ok" else "secondary"):
                st.session_state.page_status[idx] = "ok"; st.rerun()
        with s2:
            if st.button("⚠️ 확인", key=f"s_warn_{idx}", use_container_width=True,
                         type="primary" if status == "warn" else "secondary"):
                st.session_state.page_status[idx] = "warn"; st.rerun()
        with s3:
            if st.button("❌ 수정", key=f"s_fix_{idx}", use_container_width=True,
                         type="primary" if status == "fix" else "secondary"):
                st.session_state.page_status[idx] = "fix"; st.rerun()
        with s4:
            if st.button("⬜ 초기화", key=f"s_unc_{idx}", use_container_width=True,
                         type="secondary"):
                st.session_state.page_status[idx] = "unchecked"; st.rerun()

    with r2:
        note = st.session_state.page_notes.get(idx, "")
        new_note = st.text_input("📝 메모", value=note, key=f"snote_{idx}",
                                  placeholder="이 슬라이드에 대한 메모...", label_visibility="collapsed")
        if new_note != note:
            st.session_state.page_notes[idx] = new_note

    # Show AI review if exists
    if review:
        summary = review.get("summary", "")
        issues = review.get("issues", [])
        v = review.get("verdict", "")
        v_icon = STATUS_ICONS.get(v, "")

        st.markdown(f"**🤖 AI 검토:** {v_icon} {summary}")
        for iss in issues:
            level = iss.get("level", "info")
            detail = iss.get("detail", "")
            icon = {"error": "🔴", "warn": "🟡", "info": "🔵"}.get(level, "ℹ️")
            st.markdown(f'<div class="rv-issue {level}" style="margin:4px 0;">{icon} {detail}</div>',
                        unsafe_allow_html=True)


# ──────────────────────────────────────────────
# Upload Screen
# ──────────────────────────────────────────────
def render_upload():
    st.markdown("""
    <div class="upload-screen">
        <h1>🔍 BOD Slide QC</h1>
        <p>이사회 자료의 한국어·영문 PDF를 나란히 비교하고<br>
        AI가 번역 적절성을 자동으로 검토합니다.</p>
    </div>""", unsafe_allow_html=True)

    u1, u2 = st.columns(2, gap="large")
    with u1:
        st.markdown("**🇰🇷 한국어 원본 PDF**")
        pdf_ko = st.file_uploader("KO", type=["pdf"], key="up_ko", label_visibility="collapsed")
    with u2:
        st.markdown("**🇺🇸 영문 번역 PDF**")
        pdf_en = st.file_uploader("EN", type=["pdf"], key="up_en", label_visibility="collapsed")

    if pdf_ko and pdf_en:
        _, col_btn, _ = st.columns([1, 2, 1])
        with col_btn:
            if st.button("🔍  비교 시작", type="primary", use_container_width=True):
                progress = st.progress(0, text="한국어 PDF 처리 중...")
                ko_pages, aspect = process_pdf(pdf_ko.read(), with_thumbs=True)
                progress.progress(50, text="영문 PDF 처리 중...")
                en_pages, _ = process_pdf(pdf_en.read(), with_thumbs=False)
                progress.progress(100); progress.empty()
                if len(ko_pages) != len(en_pages):
                    st.error(f"⚠️ 페이지 수 불일치: KR {len(ko_pages)}p / EN {len(en_pages)}p")
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
# Main Viewer
# ──────────────────────────────────────────────
def render_viewer():
    total = st.session_state.num_pages
    cur = st.session_state.current_page
    mode = st.session_state.view_mode
    if cur >= total:
        cur = 0; st.session_state.current_page = 0

    # ── Sidebar ──
    with st.sidebar:
        st.markdown('<div class="sb-brand">BOD SLIDE QC</div><div class="sb-sub">Translation Review Tool</div>', unsafe_allow_html=True)

        # Status summary chips
        counts = {}
        for s in st.session_state.page_status.values():
            counts[s] = counts.get(s, 0) + 1
        chips = ""
        for key in ["fix", "warn", "ok", "unchecked"]:
            c = counts.get(key, 0)
            if c > 0:
                chips += f'<span class="status-chip chip-{key}">{STATUS_ICONS[key]} {c}</span>'
        st.markdown(f'<div class="sb-count">📑 {total}개 슬라이드</div>', unsafe_allow_html=True)
        if chips:
            st.markdown(f'<div class="status-row">{chips}</div>', unsafe_allow_html=True)

        st.markdown('<div class="sb-label" style="margin-top:12px;">Slides</div>', unsafe_allow_html=True)

        for i in range(total):
            is_cur = i == cur and mode != "review"
            status = st.session_state.page_status.get(i, "unchecked")
            icon = STATUS_ICONS[status]
            bdr = "#4F46E5" if is_cur else "#E8EBF0"
            bdr_w = "2px" if is_cur else "1px"
            opa = "1" if is_cur else "0.5"
            shd = "0 0 0 3px rgba(79,70,229,0.1)" if is_cur else "none"
            thumb = st.session_state.pages_ko[i].get("thumb_b64", "")
            if thumb:
                st.markdown(f'<div style="border-radius:6px;overflow:hidden;border:{bdr_w} solid {bdr};opacity:{opa};box-shadow:{shd};margin-bottom:4px;position:relative;"><img src="data:image/jpeg;base64,{thumb}" style="width:100%;display:block;"/><span style="position:absolute;bottom:3px;right:5px;font-size:9px;font-weight:600;color:#fff;background:rgba(0,0,0,0.5);padding:1px 5px;border-radius:3px;">{icon} {i+1}</span></div>', unsafe_allow_html=True)
            if st.button(f"{icon} 슬라이드 {i+1}", key=f"nav_{i}", use_container_width=True,
                         type="primary" if is_cur else "secondary"):
                st.session_state.current_page = i
                if mode == "review":
                    st.session_state.view_mode = "compare"
                st.rerun()

        st.divider()
        if st.button("↻ 새 파일로 교체", use_container_width=True):
            for k in list(st.session_state.keys()): del st.session_state[k]
            st.rerun()

    # ── Header ──
    h1, h2 = st.columns([8, 3])
    with h1:
        cols = st.columns([1, 1, 1, 1, 1])
        with cols[0]:
            if st.button("🔀 비교", use_container_width=True,
                         type="primary" if mode == "compare" else "secondary"):
                st.session_state.view_mode = "compare"; st.rerun()
        with cols[1]:
            if st.button("🇰🇷 한국어", use_container_width=True,
                         type="primary" if mode == "ko" else "secondary"):
                st.session_state.view_mode = "ko"; st.rerun()
        with cols[2]:
            if st.button("🇺🇸 English", use_container_width=True,
                         type="primary" if mode == "en" else "secondary"):
                st.session_state.view_mode = "en"; st.rerun()
        with cols[3]:
            if st.button("📋 검토 결과", use_container_width=True,
                         type="primary" if mode == "review" else "secondary"):
                st.session_state.view_mode = "review"; st.rerun()
        with cols[4]:
            if has_api_key():
                if st.button("🤖 전체 AI 검토", use_container_width=True, type="primary"):
                    st.session_state.ai_reviews = ai_review_all()
                    st.session_state.view_mode = "review"
                    st.rerun()

    with h2:
        # Report download
        if st.session_state.ai_reviews:
            csv = generate_report_csv()
            st.download_button("📥 QC 리포트 다운로드", csv,
                               file_name=f"BOD_QC_Report_{datetime.now().strftime('%Y%m%d')}.csv",
                               mime="text/csv", use_container_width=True)

    # ── Content ──
    if mode == "review":
        render_review_results()
    else:
        if mode == "compare":
            render_compare(cur)
        else:
            render_single(cur, mode)

        render_status_controls(cur)

        # Navigation
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        n1, n2, n3, n4, n5 = st.columns([3, 1, 1, 1, 3])
        with n2:
            if st.button("◀ 이전", disabled=(cur == 0), use_container_width=True):
                st.session_state.current_page = cur - 1; st.rerun()
        with n3:
            st.markdown(f'<div style="text-align:center;padding:8px 0;font-size:14px;color:#6B7280;font-weight:500;">{cur+1} / {total}</div>', unsafe_allow_html=True)
        with n4:
            if st.button("다음 ▶", disabled=(cur == total - 1), use_container_width=True):
                st.session_state.current_page = cur + 1; st.rerun()


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
if not st.session_state.get("processed"):
    render_upload()
else:
    render_viewer()
