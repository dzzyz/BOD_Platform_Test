import { useState, useEffect, useRef, useCallback } from 'react'

// ─── PDF Text Grouping Utils ───

function groupTextItems(items, pageHeight, scale) {
  const processed = items
    .filter(it => it.str.trim().length > 0)
    .map(it => {
      const fontSize = Math.abs(it.transform[0])
      const x = it.transform[4]
      const y = pageHeight / scale - it.transform[5] - fontSize
      return {
        str: it.str,
        x: x * scale,
        y: y * scale,
        w: it.width * scale,
        h: fontSize * scale * 1.35,
        fontSize: fontSize * scale,
      }
    })

  // Group items on same line (similar y)
  const lines = []
  const used = new Set()
  for (let i = 0; i < processed.length; i++) {
    if (used.has(i)) continue
    const line = [processed[i]]
    used.add(i)
    for (let j = i + 1; j < processed.length; j++) {
      if (used.has(j)) continue
      if (Math.abs(processed[j].y - processed[i].y) < processed[i].h * 0.5) {
        line.push(processed[j])
        used.add(j)
      }
    }
    line.sort((a, b) => a.x - b.x)
    const merged = {
      str: line.map(l => l.str).join(' '),
      x: Math.min(...line.map(l => l.x)),
      y: line[0].y,
      w: Math.max(...line.map(l => l.x + l.w)) - Math.min(...line.map(l => l.x)),
      h: Math.max(...line.map(l => l.h)),
      fontSize: line[0].fontSize,
    }
    if (merged.str.trim()) lines.push(merged)
  }

  // Group consecutive close lines into blocks
  lines.sort((a, b) => a.y - b.y || a.x - b.x)
  const blocks = []
  const lineUsed = new Set()
  for (let i = 0; i < lines.length; i++) {
    if (lineUsed.has(i)) continue
    const block = [lines[i]]
    lineUsed.add(i)
    for (let j = i + 1; j < lines.length; j++) {
      if (lineUsed.has(j)) continue
      const last = block[block.length - 1]
      const gap = lines[j].y - (last.y + last.h)
      if (Math.abs(lines[j].x - block[0].x) < 40 && gap < last.h * 1.5 && gap > -last.h * 0.3) {
        block.push(lines[j])
        lineUsed.add(j)
      }
    }
    blocks.push({
      str: block.map(b => b.str).join('\n'),
      x: Math.min(...block.map(b => b.x)),
      y: Math.min(...block.map(b => b.y)),
      w: Math.max(...block.map(b => b.x + b.w)) - Math.min(...block.map(b => b.x)),
      h: Math.max(...block.map(b => b.y + b.h)) - Math.min(...block.map(b => b.y)),
      fontSize: block[0].fontSize,
    })
  }
  return blocks
}


// ─── Main App ───

export default function App() {
  const [pages, setPages] = useState([])
  const [currentPage, setCurrentPage] = useState(0)
  const [lang, setLang] = useState('ko')
  const [processing, setProcessing] = useState(false)
  const [translating, setTranslating] = useState(false)
  const [translations, setTranslations] = useState({})
  const [fileName, setFileName] = useState('')
  const [showOverlay, setShowOverlay] = useState(true)
  const [dragOver, setDragOver] = useState(false)
  const [progress, setProgress] = useState({ cur: 0, total: 0 })
  const [error, setError] = useState(null)
  const [containerSize, setContainerSize] = useState({ w: 0, h: 0 })

  const fileRef = useRef(null)
  const slideAreaRef = useRef(null)

  // Responsive container
  useEffect(() => {
    const el = slideAreaRef.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => {
      setContainerSize({ w: e.contentRect.width, h: e.contentRect.height })
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [pages.length])

  // Keyboard navigation
  useEffect(() => {
    const handler = (e) => {
      if (!pages.length) return
      if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault()
        goToPage(Math.max(0, currentPage - 1))
      } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault()
        goToPage(Math.min(pages.length - 1, currentPage + 1))
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [pages.length, currentPage, lang])

  // ─── PDF Processing ───
  const processPDF = async (buf) => {
    setProcessing(true)
    setPages([])
    setTranslations({})
    setLang('ko')
    setCurrentPage(0)
    setError(null)

    try {
      const pdf = await window.pdfjsLib.getDocument({ data: buf }).promise
      setProgress({ cur: 0, total: pdf.numPages })
      const result = []

      for (let i = 1; i <= pdf.numPages; i++) {
        setProgress({ cur: i, total: pdf.numPages })
        const page = await pdf.getPage(i)
        const scale = 2
        const vp = page.getViewport({ scale })

        // High-res render
        const canvas = document.createElement('canvas')
        canvas.width = vp.width
        canvas.height = vp.height
        await page.render({ canvasContext: canvas.getContext('2d'), viewport: vp }).promise
        const imageUrl = canvas.toDataURL('image/png', 0.92)

        // Thumbnail
        const ts = 0.3
        const tvp = page.getViewport({ scale: ts })
        const tc = document.createElement('canvas')
        tc.width = tvp.width; tc.height = tvp.height
        await page.render({ canvasContext: tc.getContext('2d'), viewport: tvp }).promise
        const thumbUrl = tc.toDataURL('image/jpeg', 0.6)

        // Text extraction
        const textContent = await page.getTextContent()
        const textBlocks = groupTextItems(textContent.items, vp.height, scale)

        result.push({ imageUrl, thumbUrl, textBlocks, width: vp.width, height: vp.height })
      }
      setPages(result)
    } catch (e) {
      console.error('PDF error:', e)
      setError('PDF 처리 중 오류가 발생했습니다.')
    }
    setProcessing(false)
  }

  const handleFile = (f) => {
    if (!f) return
    const name = f.name.toLowerCase()
    if (!name.endsWith('.pdf')) {
      setError('PDF 파일만 지원합니다.')
      return
    }
    setFileName(f.name)
    setError(null)
    const r = new FileReader()
    r.onload = (e) => processPDF(e.target.result)
    r.readAsArrayBuffer(f)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  // ─── Translation ───
  const translatePage = useCallback(async (idx) => {
    if (translations[idx]) return
    const page = pages[idx]
    if (!page || !page.textBlocks.length) return

    setTranslating(true)
    setError(null)
    const texts = page.textBlocks.map(b => b.str)

    try {
      const res = await fetch('/api/translate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texts, direction: 'ko2en' }),
      })
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      setTranslations(prev => ({ ...prev, [idx]: data.translated }))
    } catch (e) {
      console.error('Translation error:', e)
      setError('번역 중 오류 발생. 서버 연결을 확인해주세요.')
    }
    setTranslating(false)
  }, [pages, translations])

  const switchLang = async (l) => {
    setLang(l)
    if (l === 'en') await translatePage(currentPage)
  }

  const goToPage = async (idx) => {
    setCurrentPage(idx)
    if (lang === 'en') await translatePage(idx)
  }

  const resetApp = () => {
    setPages([]); setTranslations({}); setFileName(''); setLang('ko')
    setCurrentPage(0); setError(null)
    if (fileRef.current) fileRef.current.value = ''
  }

  // ─── Display dimensions ───
  const getDisplayDims = () => {
    if (!pages.length || !containerSize.w) return { dw: 0, dh: 0, s: 1 }
    const p = pages[currentPage]
    const maxW = containerSize.w - 48
    const maxH = containerSize.h - 48
    const s = Math.min(maxW / p.width, maxH / p.height, 1)
    return { dw: p.width * s, dh: p.height * s, s }
  }
  const { dw, dh, s: displayScale } = getDisplayDims()
  const curBlocks = pages[currentPage]?.textBlocks || []
  const curTranslated = translations[currentPage] || []
  const hasTranslation = curTranslated.length > 0

  // ──────── RENDER: Upload Screen ────────
  if (!pages.length) {
    return (
      <div className="app">
        <div className="main">
          <div className="upload-screen">
            {processing ? (
              <div className="processing">
                <div className="processing-icon">⚙️</div>
                <div className="processing-title">슬라이드 분석 중...</div>
                <div className="processing-sub">{progress.cur} / {progress.total} 페이지</div>
                <div className="progress-bar">
                  <div className="progress-fill"
                    style={{ width: `${(progress.cur / Math.max(progress.total, 1)) * 100}%` }} />
                </div>
              </div>
            ) : (
              <div
                className={`upload-zone ${dragOver ? 'dragover' : ''}`}
                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                onDragLeave={() => setDragOver(false)}
                onDrop={handleDrop}
                onClick={() => fileRef.current?.click()}
              >
                <input ref={fileRef} type="file" accept=".pdf"
                  onChange={e => handleFile(e.target.files[0])} style={{ display: 'none' }} />
                <div className="upload-icon">📄</div>
                <div>
                  <div className="upload-title">이사회 자료 PDF를 업로드하세요</div>
                  <div className="upload-desc" style={{ marginTop: 6 }}>
                    드래그 앤 드롭 또는 클릭하여 파일 선택
                  </div>
                </div>
                <div className="upload-badges">
                  <span className="upload-badge">🔍 텍스트 자동 추출</span>
                  <span className="upload-badge">🌐 AI 한↔영 번역</span>
                  <span className="upload-badge">📐 레이아웃 유지</span>
                </div>
                <div className={`upload-engine ${window.pdfjsLib ? 'ready' : ''}`}>
                  {window.pdfjsLib ? '✓ PDF 엔진 준비 완료' : '⏳ PDF 엔진 로딩 중...'}
                </div>
                {error && <div style={{ color: 'var(--error)', fontSize: 12, marginTop: 8 }}>{error}</div>}
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ──────── RENDER: Slide Viewer ────────
  return (
    <div className="app">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo">BOD Translator</div>
          <div className="sidebar-subtitle">Slide Translation Prototype</div>
          {fileName && <div className="sidebar-filename" title={fileName}>{fileName}</div>}
        </div>
        <div className="thumb-list">
          {pages.map((p, i) => (
            <div key={i}
              className={`thumb-item ${i === currentPage ? 'active' : ''}`}
              onClick={() => goToPage(i)}
            >
              <img src={p.thumbUrl} alt={`Slide ${i + 1}`} />
              <span className="thumb-num">{i + 1}</span>
              {translations[i] && (
                <span style={{
                  position: 'absolute', top: 4, right: 6,
                  fontSize: 8, color: 'var(--success)',
                }}>EN ✓</span>
              )}
            </div>
          ))}
        </div>
        <div className="sidebar-footer">
          <button className="sidebar-btn" onClick={resetApp}>↻ 새 파일 업로드</button>
        </div>
      </div>

      {/* Main */}
      <div className="main">
        {/* Top bar */}
        <div className="topbar">
          <div className="topbar-left">
            <div className="lang-toggle">
              <button className={`lang-btn ${lang === 'ko' ? 'active' : ''}`}
                onClick={() => switchLang('ko')}>한국어</button>
              <button className={`lang-btn ${lang === 'en' ? 'active' : ''}`}
                onClick={() => switchLang('en')}>English</button>
            </div>
            {translating && (
              <span className="status-badge translating">
                <span className="spinner">⟳</span> 번역 중...
              </span>
            )}
            {lang === 'en' && hasTranslation && !translating && (
              <span className="status-badge done">✓ 번역 완료</span>
            )}
            {error && <span className="status-badge error">{error}</span>}
          </div>
          <div className="topbar-right">
            <label className="overlay-toggle" onClick={() => setShowOverlay(!showOverlay)}>
              <div className={`checkbox ${showOverlay ? 'on' : ''}`}>
                {showOverlay && '✓'}
              </div>
              텍스트 오버레이
            </label>
            <span className="info-badge">{curBlocks.length} 텍스트 블록</span>
          </div>
        </div>

        {/* Slide */}
        <div className="slide-area" ref={slideAreaRef}>
          {pages[currentPage] && (
            <div className="slide-wrapper" style={{ width: dw, height: dh }}>
              <img src={pages[currentPage].imageUrl} alt={`Slide ${currentPage + 1}`} />

              {showOverlay && curBlocks.map((block, i) => {
                const text = (lang === 'en' && hasTranslation)
                  ? (curTranslated[i] || block.str)
                  : block.str
                const isTranslated = lang === 'en' && hasTranslation
                return (
                  <div key={i}
                    className={`text-block ${isTranslated ? 'translated' : 'highlight'}`}
                    style={{
                      left: block.x * displayScale,
                      top: block.y * displayScale,
                      width: block.w * displayScale + 10,
                      minHeight: block.h * displayScale,
                      fontSize: Math.max(block.fontSize * displayScale * 0.85, 7),
                      fontWeight: block.fontSize > 20 ? 600 : 400,
                    }}
                  >
                    {text}
                  </div>
                )
              })}
            </div>
          )}

          <div className="key-hint">
            <span><kbd>←</kbd> <kbd>→</kbd> 슬라이드 이동</span>
          </div>
        </div>

        {/* Bottom bar */}
        <div className="bottombar">
          <button className="page-btn"
            disabled={currentPage === 0}
            onClick={() => goToPage(currentPage - 1)}>
            ← 이전
          </button>
          <span className="page-info">{currentPage + 1} / {pages.length}</span>
          <button className="page-btn"
            disabled={currentPage === pages.length - 1}
            onClick={() => goToPage(currentPage + 1)}>
            다음 →
          </button>
        </div>
      </div>
    </div>
  )
}
