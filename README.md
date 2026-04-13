# 🌐 BOD Slide Translator

이사회 미팅 자료 PDF를 업로드하면, 그래픽은 원본 그대로 유지하면서 AI가 텍스트만 한↔영 번역하는 Streamlit 웹앱입니다.

## Features

| 기능 | 설명 |
|------|------|
| 📄 **PDF 슬라이드 인식** | 취합된 PDF를 업로드하면 슬라이드별로 분리, 텍스트 위치 자동 추출 |
| 🌐 **AI 번역** | Claude가 이사회 문체로 번역. 인명·약어 자동 유지 |
| 🎨 **레이아웃 보존** | 차트·그래픽 원본 유지, 텍스트만 같은 위치에서 언어 전환 |
| ⚡ **번역 캐싱** | 한번 번역한 슬라이드는 즉시 한↔영 전환 |
| 📑 **전체 번역** | 버튼 한번에 전체 슬라이드 일괄 번역 |

## Quick Start (로컬)

```bash
# 1. Clone
git clone https://github.com/your-org/bod-slide-translator.git
cd bod-slide-translator

# 2. Install
pip install -r requirements.txt

# 3. Secrets 설정
mkdir -p .streamlit
echo 'ANTHROPIC_API_KEY = "sk-ant-..."' > .streamlit/secrets.toml

# 4. Run
streamlit run app.py
```

## Streamlit Cloud 배포

1. GitHub에 push
2. [share.streamlit.io](https://share.streamlit.io)에서 앱 연결
3. **Settings → Secrets**에 아래 입력:

```toml
ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxxx"
```

4. Deploy 완료!

## Project Structure

```
bod-slide-translator/
├── app.py                  # 메인 앱
├── requirements.txt        # Python 의존성
├── secrets.toml.example    # Secrets 템플릿
├── .streamlit/
│   └── config.toml         # Streamlit 테마 설정
├── .gitignore
└── README.md
```

## Tech Stack

- **Frontend**: Streamlit + Custom CSS
- **PDF 처리**: PyMuPDF (fitz)
- **번역 AI**: Claude Sonnet (Anthropic API)
- **배포**: Streamlit Cloud
