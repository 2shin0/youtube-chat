import streamlit as st
import time
import json
import asyncio
from typing import List, Dict, Any
from fastmcp import Client
from google import genai

# --- 환경변수 ---
MCP_SERVER_URL = st.secrets.api.mcp_server_url
API_KEY = st.secrets.gemini_api_key

# --- FastMCP / Gemini 클라이언트 ---
mcp_client = Client(MCP_SERVER_URL)
gemini_client = genai.Client(api_key=API_KEY)

# --- FastMCP Tool 호출 비동기 함수 ---
async def async_tool_call(client: Client, tool_name: str, tool_args: Dict[str, Any]) -> Any:
    result = await client.call_tool(tool_name, tool_args)
    return result.data

# --- 세션 상태 초기화 ---
if "chat_sessions" not in st.session_state:
    st.session_state.chat_sessions = {}
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None

def new_chat_session():
    new_id = f"chat_{int(time.time() * 1000)}"
    st.session_state.chat_sessions[new_id] = {"title": "새 대화", "messages": []}
    st.session_state.current_session_id = new_id

if st.session_state.current_session_id is None or st.session_state.current_session_id not in st.session_state.chat_sessions:
    new_chat_session()

current_session = st.session_state.chat_sessions[st.session_state.current_session_id]
current_messages = current_session["messages"]

# --- 사이드바: 세션 관리 ---
st.sidebar.title("💬 대화 기록")
if st.sidebar.button("➕ 새 대화 시작"):
    new_chat_session()
    st.experimental_rerun()

for session_id, session_data in st.session_state.chat_sessions.items():
    if st.sidebar.button(session_data["title"], key=session_id, use_container_width=True):
        st.session_state.current_session_id = session_id
        st.experimental_rerun()
st.sidebar.caption("⚠️ 이 기록은 브라우저를 닫으면 사라집니다.")

# --- 비동기 챗봇 응답 ---
async def generate_chat_response_async(messages: List[Dict[str, str]], system_prompt: str, progress_placeholder):
    full_history = []
    for m in messages:
        role = "model" if m["role"] == "assistant" else m["role"]
        full_history.append(genai.types.Content(role=role, parts=[genai.types.Part.from_text(text=m["content"])]))

    async with mcp_client:
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-pro",
            contents=full_history,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0,
                tools=[mcp_client]  # Tool 객체 올바르게 전달
            )
        )

        tool_messages = []

        async def update_progress(msg):
            tool_messages.append(msg)
            # 동기 함수이므로 to_thread 사용
            await asyncio.to_thread(progress_placeholder.markdown, "\n".join(tool_messages))

        # function_calls 체크
        tool_calls = getattr(response.candidates[0], "function_calls", [])
        while tool_calls:
            await update_progress(f"🔎 AI가 MCP Tool 호출 중 ({len(tool_calls)}개)...")
            full_history.append(response.candidates[0].content)

            for call in tool_calls:
                tool_name = call.name
                tool_args = dict(call.args)

                try:
                    await update_progress(f"⏳ `{tool_name}` 호출 중...")
                    tool_output = await async_tool_call(mcp_client, tool_name, tool_args)
                    if not isinstance(tool_output, str):
                        tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)
                    await update_progress(f"✅ `{tool_name}` 완료")
                except Exception as e:
                    await update_progress(f"❌ `{tool_name}` 실패: {e}")
                    tool_output = f"Tool 실행 오류 ({tool_name}): {e}"

                full_history.append(genai.types.Content(
                    role="tool",
                    parts=[genai.types.Part.from_function_response(name=tool_name, response=tool_output)]
                ))

            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-pro",
                contents=full_history,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0,
                    tools=[mcp_client]
                )
            )

            tool_calls = getattr(response.candidates[0], "function_calls", [])

    return response.candidates[0].content

# --- Streamlit 동기 실행 래퍼 ---
def run_async(coro):
    try:
        loop = asyncio.get_running_loop()
        # 이미 루프 실행 중이면 Thread-safe 실행
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()
    except RuntimeError:
        return asyncio.run(coro)

def generate_chat_response(messages: List[Dict[str, str]], system_prompt: str, progress_placeholder):
    return run_async(generate_chat_response_async(messages, system_prompt, progress_placeholder))

# --- 메인 UI ---
st.set_page_config(page_title="유튜브 데이터 분석 챗봇", page_icon="📊")
st.title("📊 유튜브 데이터 분석 챗봇")
st.write(f"**{current_session['title']}**")

# 이전 메시지 표시
for message in current_messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# 시스템 프롬프트
system_prompt = """
당신은 유튜브 데이터 분석 전문가입니다.
데이터 출처: get_youtube_transcript, search_youtube_videos, get_channel_info, get_youtube_comments
분석 단계: 데이터 파악 → 요약/개요 → 인사이트 추출 → 보고서 작성
주의사항: 누락 데이터 명시, 욕설/인신공격 제외, 언어 유지
"""

# 사용자 입력
user_input = st.chat_input("메시지를 입력하세요...")
if user_input:
    current_messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 채팅창 위에 Tool 진행 상태 표시
    progress_placeholder = st.empty()
    with st.chat_message("assistant"):
        with st.spinner("AI가 응답을 생성 중입니다..."):
            full_response = generate_chat_response(current_messages, system_prompt, progress_placeholder)
        st.write(full_response)

    current_messages.append({"role": "assistant", "content": full_response})

    if current_session["title"] == "새 대화":
        current_session["title"] = user_input[:30] + "..." if len(user_input) > 30 else user_input
        st.rerun()










# # 필요한 라이브러리 불러오기
# import streamlit as st
# import time
# from fastmcp import Client
# from fastmcp.client.auth import BearerAuth
# import json
# import asyncio
# from typing import List, Dict, Any
# from google import genai


# # --- 환경변수 설정 ---
# # token = st.secrets.oauth.token
# MCP_SERVER_URL = st.secrets.api.mcp_server_url  
# api_key = st.secrets.gemini_api_key



# # --- FastMCP 서버 설정 ---
# mcp_client = Client(
#     MCP_SERVER_URL,
#     # auth=BearerAuth(token)
# )

# gemini_client = genai.Client(api_key=api_key)



# # --- FastMCP Tool 호출 함수 ---
# async def async_tool_call(client: Client, tool_name: str, tool_args: Dict[str, Any]) -> Any:
#     """FastMCP 클라이언트를 전달받아 특정 툴을 호출합니다."""
#     result = await client.call_tool(tool_name, tool_args)
#     return result.data



# # --- 대화 기록 관리 로직 ---

# # 대화 기록을 저장할 공간 만들기 (session_state 사용)
# if "chat_sessions" not in st.session_state:
#     # {세션ID: {"title": "제목", "messages": [...]}}
#     st.session_state.chat_sessions = {}
    
# if "current_session_id" not in st.session_state:
#     st.session_state.current_session_id = None
    
# def new_chat_session():
#     """새로운 채팅 세션을 생성하고 활성화합니다."""
#     # 고유한 세션 ID 생성
#     new_id = f"chat_{int(time.time() * 1000)}" 
#     st.session_state.chat_sessions[new_id] = {
#         "title": "새 대화", 
#         "messages": []
#     }
#     st.session_state.current_session_id = new_id

# # 앱 시작 시 또는 세션이 없을 경우 새 세션 생성
# if st.session_state.current_session_id is None or st.session_state.current_session_id not in st.session_state.chat_sessions:
#     new_chat_session()
    
# # 현재 활성 세션의 메시지 목록을 짧게 참조
# current_session = st.session_state.chat_sessions[st.session_state.current_session_id]
# current_messages = current_session["messages"]



# # --- 사이드바 ---

# # 사이드바 - 세션 관리
# st.sidebar.title("💬 대화 기록")
# if st.sidebar.button("➕ 새 대화 시작"):
#     new_chat_session()
#     st.rerun()

# st.sidebar.caption("⚠️ 이 기록은 브라우저를 닫으면 사라집니다.")

# # 대화 목록 표시 및 선택
# for session_id, session_data in st.session_state.chat_sessions.items():
#     if st.sidebar.button(
#         session_data["title"], 
#         key=session_id,
#         use_container_width=True,
#         # 현재 세션 강조 표시 (선택 사항)
#         # help="클릭하여 대화로 이동" 
#     ):
#         st.session_state.current_session_id = session_id
#         st.rerun()



# # --- 비동기 챗봇 응답 생성 함수 ---

# async def generate_chat_response_async(messages: List[Dict[str, str]], system_prompt: str, message_placeholder):
#     """
#     사용자 메시지를 기반으로 Gemini API와 FastMCP Tool Calling을 통합하여 응답을 생성합니다.
#     """
#     full_history = []
#     for m in messages:
#         role = "model" if m["role"] == "assistant" else m["role"]
#         full_history.append(genai.types.Content(role=role, parts=[genai.types.Part.from_text(text=m["content"])]))

#     async with mcp_client:
#         response = await gemini_client.aio.models.generate_content(
#             model="gemini-2.5-pro",
#             contents=full_history,
#             config=genai.types.GenerateContentConfig(
#                 system_instruction=system_prompt,
#                 temperature=0,
#                 tools=[mcp_client.session]  # MCP 세션을 Tool 정의로 전달
#             )
#         )

#         # Tool 호출 루프
#         while getattr(response, "function_calls", None):
#             tool_results = []

#             message_placeholder.write(f"🔎 AI가 MCP 서버를 통해 데이터를 가져오는 중입니다 ({len(response.function_calls)}개)...")
#             full_history.append(response.candidates[0].content)

#             for call in response.function_calls:
#                 tool_name = call.name
#                 tool_args = dict(call.args)

#                 try:
#                     tool_output = await async_tool_call(mcp_client, tool_name, tool_args)
#                     if not isinstance(tool_output, (str, bytes)):
#                         tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)
#                     message_placeholder.write(f"✅ Tool 호출 `{tool_name}` 완료")
#                 except Exception as e:
#                     tool_output = f"Tool 실행 오류 ({tool_name}): {e}"
#                     message_placeholder.write(f"❌ Tool 호출 실패: {tool_output}")

#                 tool_results.append(
#                     genai.types.Part.from_function_response(
#                         name=tool_name,
#                         response=tool_output
#                     )
#                 )

#             # Tool 결과를 Gemini에 재전달
#             full_history.append(genai.types.Content(role="tool", parts=tool_results))
#             response = await gemini_client.aio.models.generate_content(
#                 model="gemini-2.5-pro",
#                 contents=full_history,
#                 config=genai.types.GenerateContentConfig(
#                     system_instruction=system_prompt,
#                     temperature=0,
#                     tools=[mcp_client.session]
#                 )
#             )

#     message_placeholder.write(response.text)
#     return response.text


# # --- Streamlit용 동기 래퍼 함수 ---
# def run_async(coro):
#     """Streamlit 내에서 asyncio.run() 충돌 없이 실행"""
#     try:
#         loop = asyncio.get_running_loop()
#     except RuntimeError:
#         loop = None

#     if loop and loop.is_running():
#         return asyncio.ensure_future(coro)
#     else:
#         return asyncio.run(coro)


# def generate_chat_response(messages: List[Dict[str, str]], system_prompt: str, message_placeholder):
#     return run_async(generate_chat_response_async(messages, system_prompt, message_placeholder))



# # --- 메인 챗봇 인터페이스 ---

# # 페이지 설정
# st.set_page_config(page_title="유튜브 데이터 분석 챗봇", page_icon="📊")

# # 제목 표시
# st.title("📊 유튜브 데이터 분석 챗봇")
# st.write(f"**{current_session['title']}**")

# # 이전 대화 내용 화면에 표시하기
# for message in current_messages:
#     with st.chat_message(message["role"]):
#         st.write(message["content"])

# # 시스템 프롬프트 정의
# system_prompt = """
#         당신은 유튜브 데이터 분석 전문가입니다.
#         당신의 역할은 YouTube 데이터를 분석하여 인사이트를 도출하는 것입니다.

#         데이터는 다음 4가지 출처 중 하나 또는 여러 개가 포함될 수 있습니다:
#         1. get_youtube_transcript → 영상 자막 전체 텍스트
#         2. search_youtube_videos → 검색된 영상 리스트 (제목, 조회수, 채널명, 좋아요 수 등)
#         3. get_channel_info → 채널 기본 정보 및 최근 영상
#         4. get_youtube_comments → 댓글 내용, 좋아요 수, 작성자 등

#         ---

#         ### 분석 단계
#         1. 데이터 파악: 어떤 MCP Tool의 결과인지 식별하고, 필요시 여러 도구의 데이터를 결합해 문맥적으로 이해합니다.
#         2. 요약 / 개요 생성: 자막은 핵심 주제를, 영상 리스트는 특징을, 댓글은 감성/키워드를 요약합니다.
#         3. 인사이트 추출: 영상의 핵심 메시지, 타겟 시청자, 채널의 성장 방향 등을 분석합니다.
#         4. 최종 출력 형태: 분석 내용을 기반으로 구체적인 유튜브 데이터 분석 보고서를 작성합니다.

#         ---

#         ### 주의사항
#         - 데이터가 일부 누락되었을 경우, 가능한 정보만 활용하고 데이터 부족이라고 명시합니다.
#         - 댓글 분석 시 욕설, 인신공격 등은 제외하고 **주요 의견의 경향성**만 반영합니다.
#         - 언어는 입력 데이터의 언어(한국어/영어 등)에 맞게 동일하게 유지합니다.
#         """

# # 사용자 입력 받기
# user_input = st.chat_input("메시지를 입력하세요...")

# # 사용자가 메시지를 입력했을 때
# if user_input:
#     current_messages.append({"role": "user", "content": user_input})

#     with st.chat_message("user"):
#         st.write(user_input)

#     with st.chat_message("assistant"):
#         message_placeholder = st.empty()
#         full_response = generate_chat_response(current_messages, system_prompt, message_placeholder)
#         if asyncio.isfuture(full_response):
#             full_response = asyncio.run(full_response)
#         current_messages.append({"role": "assistant", "content": full_response})

#     if current_session["title"] == "새 대화":
#         current_session["title"] = user_input[:30] + "..." if len(user_input) > 30 else user_input
#         st.rerun()




