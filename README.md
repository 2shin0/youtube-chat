# 유튜브 데이터 분석 챗봇

이 레포지토리는 **Streamlit**과 **Google Gemini**, 그리고 **FastMCP**를 결합하여 구축한 **유튜브 데이터 분석 챗봇**의 프론트엔드/클라이언트 애플리케이션입니다.

사용자가 자연어로 질문하면, 챗봇이 별도로 배포된 MCP 서버와 통신하여 필요한 YouTube 데이터(자막, 댓글, 채널 정보 등)를 가져오고, Gemini 2.5 Pro 모델이 이를 분석하여 인사이트를 제공합니다.

MCP Server는 [이 레포지토리](https://github.com/2shin0/youtube-mcp-server) 를 참고해 주세요.

## 주요 기능

- **대화형 분석**: 사용자와의 대화 맥락을 유지하며 유튜브 데이터를 심층 분석합니다.
- **MCP 도구 연동**: FastMCP 프로토콜을 통해 원격 서버의 도구(자막 추출, 검색, 댓글 수집)를 호출합니다.
- **비동기 처리**: 데이터 수집 및 분석 중에도 UI가 멈추지 않도록 `asyncio`를 활용하여 쾌적한 경험을 제공합니다.
- **세션 관리**: 사이드바를 통해 여러 분석 세션을 생성하고 기록을 관리할 수 있습니다.

## 기술 스택

- **Frontend**: Streamlit
- **AI Model**: Google Gemini (via `google-genai` SDK)
- **Tool Protocol**: FastMCP (Client)
- **Language**: Python 3.10+

## 설정 및 배포

이 프로젝트를 실행하기 위해서는 **Streamlit Secrets** 설정이 필수적입니다. Streamlit Cloud 대시보드에서 앱 설정(Settings) -> Secrets 메뉴에 다음 내용을 추가해야 합니다. 
*주의: 코드에서 st.secrets.api.mcp_server_url로 접근하므로, 반드시 [api] 섹션을 구분해야 합니다.

```Ini, TOML
# Google AI Studio에서 발급받은 Gemini API Key
gemini_api_key = "AIzaSy..."

# 배포된 FastMCP 서버의 URL (예: fastmcp cloud url)
[api]
mcp_server_url = "https://your-mcp-server-url..."
```

## 사용 예시
챗봇에게 다음과 같은 질문을 할 수 있습니다.

1. 영상 내용 요약 (Transcript)
"이 영상(URL)의 내용을 요약해주고, 핵심 주장이 뭔지 3줄로 정리해줘."

2. 댓글 여론 분석 (Comments)
"이 영상의 댓글 반응은 어때? 사람들이 주로 어떤 점을 칭찬하거나 비판하고 있어?"

3. 트렌드 파악 (Search)
"요즘 'AI 에이전트' 관련해서 조회수가 가장 높은 영상 5개를 찾아주고, 공통적인 특징을 알려줘."

4. 채널 분석 (Channel Info)
"이 채널은 주로 어떤 영상을 올리고 성장세는 어때?"

---

# YouTube Data Analysis Chatbot

This repository is the frontend/client application for a **YouTube Data Analysis Chatbot**, built by combining **Streamlit**, **Google Gemini**, and **FastMCP**.

When a user asks a question in natural language, the chatbot communicates with a separately deployed MCP server to fetch necessary YouTube data (transcripts, comments, channel info, etc.), which is then analyzed by the Gemini 2.5 Pro model to provide insights.

Please refer to [this repository](https://github.com/2shin0/youtube-mcp-server) for the MCP Server.

## Key Features

- **Interactive Analysis**: Performs in-depth analysis of YouTube data while maintaining conversational context with the user.
- **MCP Tool Integration**: Calls tools from a remote server (transcript extraction, search, comment collection) via the FastMCP protocol.
- **Asynchronous Processing**: Utilizes `asyncio` to ensure a smooth user experience where the UI does not freeze during data collection and analysis.
- **Session Management**: Allows creating multiple analysis sessions and managing history via the sidebar.

## Tech Stack

- **Frontend**: Streamlit
- **AI Model**: Google Gemini (via `google-genai` SDK)
- **Tool Protocol**: FastMCP (Client)
- **Language**: Python 3.10+

## Configuration & Deployment

To run this project, configuring **Streamlit Secrets** is essential. You must add the following content to the app **Settings -> Secrets** menu in the Streamlit Cloud dashboard.

*Note: Since the code accesses `st.secrets.api.mcp_server_url`, you must strictly separate the `[api]` section.*

```toml
# Gemini API Key issued from Google AI Studio
gemini_api_key = "AIzaSy..."

# URL of the deployed FastMCP server (e.g., FastMCP Cloud URL)
[api]
mcp_server_url = "https://your-mcp-server-url..."

## Usage Examples

You can ask the chatbot questions like the following:

1. Video Content Summarization (Transcript)
"Summarize the content of this video (URL) and outline the core arguments in 3 lines."

2. Comment Sentiment Analysis (Comments)
"How are the reactions in the comments for this video? What points are people mainly praising or criticizing?"

3. Trend Identification (Search)
"Find the top 5 most-viewed videos related to 'AI Agents' lately and tell me their common characteristics."

4. Channel Analysis (Channel Info)
"What kind of videos does this channel mainly upload, and how is its growth trend?"
