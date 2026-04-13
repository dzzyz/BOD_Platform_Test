# BOD Slide Translator

이사회 미팅 자료 PDF를 업로드하면, 슬라이드를 원본 그대로 렌더링하고 AI가 텍스트만 한↔영 번역하는 웹앱.

## Features

- **원본 그대로 렌더링** — PDF를 고해상도(216 DPI)로 렌더링하여 원본과 동일한 화면 제공
- **AI 번역** — Claude가 이사회 문체로 번역. 인명·약어 자동 유지
- **전체 일괄 번역** — English 버튼 한 번에 전체 슬라이드 번역 완료, 자유롭게 넘기며 확인
- **즉시 전환** — 번역 후 한국어↔English 즉시 전환 (재번역 없음)

## Deploy (Streamlit Cloud)

1. GitHub에 push
2. [share.streamlit.io](https://share.streamlit.io) → New app → repo 연결
3. Settings → Secrets:
```toml
ANTHROPIC_API_KEY = "sk-ant-xxxxxxxxxxxxx"
```
4. Deploy

## Local

```bash
pip install -r requirements.txt
mkdir -p .streamlit
echo 'ANTHROPIC_API_KEY = "sk-ant-..."' > .streamlit/secrets.toml
streamlit run app.py
```
