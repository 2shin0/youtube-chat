# 필요한 라이브러리 불러오기
import streamlit as st
import google.generativeai as genai
import time
from fastmcp import Client
from fastmcp.client.auth import BearerAuth
import json
import asyncio
from typing import List, Dict, Any
from google import genai


# --- 환경변수 설정 ---
token = st.secrets.oauth.token
MCP_SERVER_URL = st.secrets.api.mcp_server_url  
api_key = st.secrets.gemini_api_key



# --- FastMCP 서버 설정 ---
mcp_client = Client(
    MCP_SERVER_URL,
    auth=BearerAuth(token)
)

# MCP 서버 연결 (비동기이므로 loop.run_until_complete 사용)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.run_until_complete(mcp_client.connect())

# Gemini 클라이언트
gemini_client = genai.Client(api_key=api_key)



# --- FastMCP Tool 호출 함수 ---
async def async_tool_call(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    """FastMCP 클라이언트를 이용해 특정 툴을 호출"""
    result = await mcp_client.call_tool(tool_name, tool_args)
    return result.data



# --- 대화 기록 관리 로직 ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
    
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

def new_chat_session():
    """새로운 채팅 세션 생성"""
    new_id = f"chat_{int(time.time() * 1000)}"
    st.session_state.chat_sessions[new_id] = {"title": "새 대화", "messages": []}
    st.session_state.current_session_id = new_id

if st.session_state.current_session_id is None or st.session_state.current_session_id not in st.session_state.chat_sessions:
    new_chat_session()

current_session = st.session_state.chat_sessions[st.session_state.current_session_id]
current_messages = current_session["messages"]



# --- 사이드바 ---
st.sidebar.title("💬 대화 기록")
if st.sidebar.button("➕ 새 대화 시작"):
    new_chat_session()
    st.rerun()

st.sidebar.caption("⚠️ 이 기록은 브라우저를 닫으면 사라집니다.")

for session_id, session_data in st.session_state.chat_sessions.items():
    if st.sidebar.button(session_data["title"], key=session_id, use_container_width=True):
        st.session_state.current_session_id = session_id
        st.rerun()



# --- 비동기 챗봇 응답 생성 함수 ---
async def generate_chat_response(messages: List[Dict[str, str]], system_prompt: str, message_placeholder):
    """
    사용자 메시지를 기반으로 Gemini API와 FastMCP Tool을 통합하여 응답 생성
    """
    full_history = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else m["role"]
        full_history.append(
            genai.types.Content(role=role, parts=[genai.types.Part.from_text(text=m["content"])])
        )

    response = gemini_client.models.generate_content(
        model="gemini-2.5-pro",
        contents=full_history,
        config=genai.types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0,
            tools=[mcp_client.session]
        )
    )

    while getattr(response, "function_calls", None):
        tool_results = []
        message_placeholder.write(f"🔎 AI가 MCP 서버에서 데이터 수집 중... ({len(response.function_calls)}개 요청)")

        full_history.append(response.candidates[0].content)

        for call in response.function_calls:
            tool_name = call.name
            tool_args = dict(call.args)

            try:
                tool_output = await async_tool_call(tool_name, tool_args)
                if not isinstance(tool_output, (str, bytes)):
                    tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)
                message_placeholder.write(f"✅ Tool 호출 성공: `{tool_name}`")
            except Exception as e:
                tool_output = f"Tool 실행 오류 ({tool_name}): {e}"
                message_placeholder.write(f"❌ Tool 오류: {tool_output}")

            tool_results.append(
                genai.types.Part.from_function_response(name=tool_name, response=tool_output)
            )

        full_history.append(genai.types.Content(role="tool", parts=tool_results))

        response = gemini_client.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_history,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                tools=[mcp_client.session]
            )
        )

    full_response = response.text
    message_placeholder.write(full_response)
    return full_response



# --- 메인 챗봇 인터페이스 ---
st.set_page_config(page_title="유튜브 데이터 분석 챗봇", page_icon="📊")

st.title("📊 유튜브 데이터 분석 챗봇")
st.write(f"**{current_session['title']}**")

# 기존 대화 표시
for message in current_messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

system_prompt = """
당신은 유튜브 데이터 분석 전문가입니다.
YouTube 데이터를 분석하여 인사이트를 도출하는 것이 목표입니다.

데이터는 다음 4가지 MCP Tool 결과 중 하나 또는 여러 개일 수 있습니다:
1. get_youtube_transcript → 영상 자막
2. search_youtube_videos → 검색된 영상 리스트
3. get_channel_info → 채널 기본 정보
4. get_youtube_comments → 댓글 정보

출력은 명확한 분석 보고서 형태로 작성하며, 데이터가 불충분하면 그 사실도 언급하세요.
"""

# 사용자 입력 처리
user_input = st.chat_input("메시지를 입력하세요...")

if user_input:
    current_messages.append({"role": "user", "content": user_input})

    with st.chat_message("user"):
        st.write(user_input)

    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        try:
            full_response = asyncio.run(
                generate_chat_response(current_messages, system_prompt, message_placeholder)
            )
            current_messages.append({"role": "assistant", "content": full_response})
        except Exception as e:
            error_message = f"⚠️ 실행 중 오류 발생: {e}"
            message_placeholder.error(error_message)
            current_messages.pop()
            print(error_message)

    if current_session["title"] == "새 대화":
        current_session["title"] = (
            user_input[:30] + "..." if len(user_input) > 30 else user_input
        )
        st.rerun()
