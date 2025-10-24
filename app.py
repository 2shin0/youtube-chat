# 3data/data_analysis.py에 기능 추가된 버전
# 1. gemini_api_key 환경변수 설정 필요
# 2. mcp_server_url 환경변수 설정 필요
# 3. 세션 기반 대화 기록 관리 추가됨

# 배포를 위해 파일명을 app.py로 변경



# 필요한 라이브러리 불러오기
import streamlit as st
import google.generativeai as genai
import time
from fastmcp import Client
import json
import asyncio


# --- FastMCP 서버 설정 ---
MCP_SERVER_URL = st.secrets.api.mcp_server_url  # streamlit cloud secrets에 url 추가 필요

def convert_fastmcp_tools_to_gemini_tools(fastmcp_tools):
    gemini_tools = []
    for t in fastmcp_tools:
        func_decl = FunctionDeclaration(
            name=t.name,
            description=getattr(t, 'description', ''),
            parameters=Schema(type="object", properties=t.inputSchema.get('properties', {}) if t.inputSchema else {})
        )
        tool = Tool(function_declarations=[func_decl])
        gemini_tools.append(tool)
    return gemini_tools

async def async_get_tools(url):
    async with Client(url) as client:
        tool_list = await client.list_tools()
        return convert_fastmcp_tools_to_gemini_tools(tool_list)
        
try:
    available_tools = asyncio.run(async_get_tools(MCP_SERVER_URL))
    
except Exception as e:
    st.error(f"MCP 서버 연결 실패 또는 Tool 목록 로딩 실패: {e}")
    st.stop()

async def async_tool_call(url, tool_name, tool_args):
    """FastMCP 클라이언트를 연결하고 특정 툴을 호출합니다."""
    async with Client(url) as client:
        result = await client.call_tool(tool_name, tool_args)
        return result.data



# --- 대화 기록 관리 로직 ---

# 대화 기록을 저장할 공간 만들기 (session_state 사용)
if "chat_sessions" not in st.session_state:
    # {세션ID: {"title": "제목", "messages": [...]}}
    st.session_state.chat_sessions = {}
    
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = None
    
def new_chat_session():
    """새로운 채팅 세션을 생성하고 활성화합니다."""
    # 고유한 세션 ID 생성
    new_id = f"chat_{int(time.time() * 1000)}" 
    st.session_state.chat_sessions[new_id] = {
        "title": "새 대화", 
        "messages": []
    }
    st.session_state.current_session_id = new_id

# 앱 시작 시 또는 세션이 없을 경우 새 세션 생성
if st.session_state.current_session_id is None or st.session_state.current_session_id not in st.session_state.chat_sessions:
    new_chat_session()
    
# 현재 활성 세션의 메시지 목록을 짧게 참조
current_session = st.session_state.chat_sessions[st.session_state.current_session_id]
current_messages = current_session["messages"]



# --- 사이드바 ---

# 사이드바 - 세션 관리
st.sidebar.title("💬 대화 기록")
if st.sidebar.button("➕ 새 대화 시작"):
    new_chat_session()
    st.rerun()

st.sidebar.caption("⚠️ 이 기록은 브라우저를 닫으면 사라집니다.")

# 대화 목록 표시 및 선택
for session_id, session_data in st.session_state.chat_sessions.items():
    if st.sidebar.button(
        session_data["title"], 
        key=session_id,
        use_container_width=True,
        # 현재 세션 강조 표시 (선택 사항)
        # help="클릭하여 대화로 이동" 
    ):
        st.session_state.current_session_id = session_id
        st.rerun()



# --- 메인 챗봇 인터페이스 ---

# 페이지 설정
st.set_page_config(page_title="유튜브 데이터 분석 챗봇", page_icon="📊")

# 제목 표시
st.title("📊 유튜브 데이터 분석 챗봇")
st.write(f"**{current_session['title']}**")

# 이전 대화 내용 화면에 표시하기
for message in current_messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# Gemini API 키 설정 
api_key = st.secrets.gemini_api_key

# Gemini 클라이언트 생성
genai.configure(api_key=api_key)

# 사용자 입력 받기
user_input = st.chat_input("메시지를 입력하세요...")

# 사용자가 메시지를 입력했을 때
if user_input:        
    # 사용자 메시지를 현재 세션의 기록에 추가
    current_messages.append({"role": "user", "content": user_input})

    # 사용자 메시지를 화면에 표시
    with st.chat_message("user"):
        st.write(user_input)

    # AI의 응답을 화면에 표시
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""

        # 시스템 프롬프트 정의 
        system_prompt = """
        당신은 유튜브 데이터 분석 전문가입니다.
        당신의 역할은 YouTube 데이터를 분석하여 인사이트를 도출하는 것입니다.

        데이터는 다음 4가지 출처 중 하나 또는 여러 개가 포함될 수 있습니다:
        1. get_youtube_transcript → 영상 자막 전체 텍스트
        2. search_youtube_videos → 검색된 영상 리스트 (제목, 조회수, 채널명, 좋아요 수 등)
        3. get_channel_info → 채널 기본 정보 및 최근 영상
        4. get_youtube_comments → 댓글 내용, 좋아요 수, 작성자 등

        ---

        ### 분석 단계
        1. 데이터 파악: 어떤 MCP Tool의 결과인지 식별하고, 필요시 여러 도구의 데이터를 결합해 문맥적으로 이해합니다.
        2. 요약 / 개요 생성: 자막은 핵심 주제를, 영상 리스트는 특징을, 댓글은 감성/키워드를 요약합니다.
        3. 인사이트 추출: 영상의 핵심 메시지, 타겟 시청자, 채널의 성장 방향 등을 분석합니다.
        4. 최종 출력 형태: 분석 내용을 기반으로 구체적인 유튜브 데이터 분석 보고서를 작성합니다.

        ---

        ### 주의사항
        - 데이터가 일부 누락되었을 경우, 가능한 정보만 활용하고 데이터 부족이라고 명시합니다.
        - 댓글 분석 시 욕설, 인신공격 등은 제외하고 **주요 의견의 경향성**만 반영합니다.
        - 언어는 입력 데이터의 언어(한국어/영어 등)에 맞게 동일하게 유지합니다.
        """

        # Gemini API 호출
        model = genai.GenerativeModel(
            "gemini-2.5-pro",
            system_instruction=system_prompt,
            tools = available_tools
        )
        
        gemini_history = [
            {"role": m["role"], "parts": [m["content"]]}
            for m in current_messages[:-1]
        ]

        chat = model.start_chat(history=gemini_history)

        # 첫 메시지 전송 및 tool calling 반복 시작
        response = chat.send_message(current_messages[-1]["content"]) # 마지막 사용자 메시지 전송

        # Tool Calling이 끝날 때까지 반복
        while response.function_calls:
            tool_results = []
            
            # 응답 요약 표시 (사용자에게 작업 중임을 알림)
            message_placeholder.write(f"🔎 AI가 필요한 데이터를 **MCP 서버**를 통해 수집 중입니다 ({len(response.function_calls)}개 요청)...") 
            
            for call in response.function_calls:
                tool_name = call.name
                tool_args = dict(call.args)
                
                # FastMCP 클라이언트를 이용해 실제 서버에 요청 및 Tool 실행
                try:
                    tool_output = asyncio.run(
                        async_tool_call(MCP_SERVER_URL, tool_name, tool_args)
                    )
                    
                    # 결과를 JSON 문자열로 변환 (모델에 전달하기 위함)
                    if not isinstance(tool_output, str):
                        tool_output = json.dumps(tool_output, ensure_ascii=False, indent=2)
                        
                    message_placeholder.write(
                        f"✅ Tool 호출: `{tool_name}` 실행 완료."
                    )
                    
                except Exception as e:
                    tool_output = f"Tool 실행 오류 ({tool_name}): {e}"
                    message_placeholder.write(
                        f"❌ Tool 호출: `{tool_name}` 실행 실패. 오류: {tool_output}"
                    )

                # Tool 실행 결과를 Gemini에 다시 전달할 형태로 준비
                tool_results.append(
                    {
                        "function_response": {
                            "name": tool_name,
                            "response": tool_output,
                        }
                    }
                )
            # Tool 실행 결과를 포함하여 다시 Gemini에 요청 
            response = chat.send_message(tool_results)

        # 최종 분석 결과 출력
        full_response = ""
        if hasattr(response, 'stream') and callable(response.stream):
            for chunk in response.stream():
                if chunk.text:
                    full_response += chunk.text
                    message_placeholder.write(full_response + "▌")
        else: 
             full_response = response.text
             
        message_placeholder.write(full_response)

    # AI 응답을 대화 기록에 추가

    current_messages.append({"role": "assistant", "content": full_response})










