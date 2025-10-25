# app.py
import streamlit as st
import time
import asyncio
import json
from typing import List, Dict, Any
from fastmcp import Client
from google import genai

# --- 환경변수 설정 ---
MCP_SERVER_URL = st.secrets.api.mcp_server_url
api_key = st.secrets.gemini_api_key

# --- FastMCP, Gemini 클라이언트 초기화 ---
mcp_client = Client(MCP_SERVER_URL)
gemini_client = genai.Client(api_key=api_key)

# --- 세션 및 메시지 초기화 ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}

if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

def new_chat_session():
    session_id = f"chat_{int(time.time()*1000)}"
    st.session_state.chat_sessions[session_id] = {"title": "새 대화", "messages": []}
    st.session_state.current_session_id = session_id

if st.session_state.current_session_id is None or st.session_state.current_session_id not in st.session_state.chat_sessions:
    new_chat_session()

current_session = st.session_state.chat_sessions[st.session_state.current_session_id]
current_messages = current_session["messages"]

# --- FastMCP Tool 호출 ---
async def async_tool_call(client: Client, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    result = await client.call_tool(tool_name, tool_args)
    return result.data

# --- 비동기 챗봇 응답 생성 ---
async def generate_chat_response_async(messages: List[Dict[str, str]], system_prompt: str, placeholder):
    # messages 기반 full_history 누적
    full_history = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else m["role"]
        content_text = str(m.get("content", ""))  # 안전하게 문자열 변환
        full_history.append(genai.types.Content(
            role=role,
            parts=[genai.types.Part.from_text(content_text)]
        ))

    async with mcp_client:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_history,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                tools=[mcp_client.session]
            )
        )

        # Tool 호출 루프
        while getattr(response, "function_calls", None):
            placeholder.write(f"🔎 MCP Tool 호출 중 ({len(response.function_calls)}개)...")
            for call in response.function_calls:
                tool_name = call.name
                tool_args = dict(call.args)
                try:
                    tool_output = await async_tool_call(mcp_client, tool_name, tool_args)
                    if not isinstance(tool_output, (str, bytes)):
                        tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)
                    tool_output = str(tool_output)
                    placeholder.write(f"✅ Tool `{tool_name}` 완료")
                except Exception as e:
                    tool_output = f"Tool 오류 ({tool_name}): {e}"
                    placeholder.write(f"❌ Tool `{tool_name}` 실패")

                # Tool 결과를 full_history와 current_messages에 기록
                tool_content = genai.types.Content(
                    role="tool",
                    parts=[genai.types.Part.from_function_response(name=tool_name, response=tool_output)]
                )
                full_history.append(tool_content)
                current_messages.append({"role": "assistant", "content": tool_output})

            # Tool 결과 반영해 다시 GPT 응답 생성
            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=full_history,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0,
                    tools=[mcp_client.session]
                )
            )

    # 최종 GPT 응답
    placeholder.write(response.text)
    current_messages.append({"role": "assistant", "content": response.text})
    return response.text

# --- Streamlit용 async 실행 래퍼 ---
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
        return asyncio.ensure_future(coro)
    except RuntimeError:
        return asyncio.run(coro)

def generate_chat_response(messages: List[Dict[str, str]], system_prompt: str, placeholder):
    return run_async(generate_chat_response_async(messages, system_prompt, placeholder))

# --- 사이드바 ---
st.sidebar.title("💬 대화 기록")
if st.sidebar.button("➕ 새 대화 시작"):
    new_chat_session()
    st.rerun()

for sid, sdata in st.session_state.chat_sessions.items():
    if st.sidebar.button(sdata["title"], key=sid, use_container_width=True):
        st.session_state.current_session_id = sid
        st.rerun()

st.sidebar.caption("⚠️ 이 기록은 브라우저를 닫으면 사라집니다.")

# --- 메인 페이지 ---
st.set_page_config(page_title="유튜브 데이터 분석 챗봇", page_icon="📊")
st.title("📊 유튜브 데이터 분석 챗봇")
st.write(f"**{current_session['title']}**")

for message in current_messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 시스템 프롬프트 (예시)
system_prompt = """
당신은 유튜브 데이터 분석 전문가입니다.
데이터 분석, 댓글 요약, 인사이트 추출 등을 수행합니다.
"""

user_input = st.chat_input("메시지를 입력하세요...")
if user_input:
    current_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_response = generate_chat_response(current_messages, system_prompt, placeholder)
        if asyncio.isfuture(full_response):
            full_response = asyncio.run(full_response)
    if current_session["title"] == "새 대화":
        current_session["title"] = user_input[:30] + "..." if len(user_input) > 30 else user_input
        st.rerun()
