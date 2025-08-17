import os
import requests
from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools.file_management import ListDirectoryTool, WriteFileTool, ReadFileTool
from langchain_community.tools.requests.tool import RequestsGetTool
from langchain_community.utilities.requests import TextRequestsWrapper
from langchain.tools import Tool
"""
LLM 모델 종합 도구 사용능력 평가 설계

"qwen3:8b"의 종합 도구 사용능력을 보기위해 agent_basictools.py에서 5개의 서로다른 툴을 사용하여 작업을 수행하는 코드를 만들어보려고한다. 
전체적인 절차는 다음과 같다.
1. urls_for_basictools_test.txt 에 특정 사이트 URL을 미리 기록해 놓는다.
2. 5가지 도구를 준비한다 [list_tool, write_tool, read_tool, requests_get_tool, fetch_webpage_tool] 여기서 requests_get_tool과 fetch_webpage_tool 두개를 사용하는 이유는, 더 적합한 도구를 선택하는지 보기 위함이다.
3. "qwen3:8b" 에게 url로 시작하는 파일을 읽고 거기에 적힌 url주소에서 내용을 가져와서 해당 내용을 요약한 다음, 그것을 url_summary.md 에 저장하라고 지시한다.

이 작업을 수행하기 위해 최소 4개의 도구(list_tool - read_tool - requests_get_tool - read_tool)를 사용해야한다.
우리가 지켜볼 부분은
1. 결과가 의도한대로 나오는지
2. requests_get_tool과 fetch_webpage_tool 중 더 유리한 도구를 사용하는지 (웹페이지는 HTML 태그들로 각 내용이 구분되므로 requests_get_tool 이 더 유리함 - 이것을 선택할 것을 기대)
"""

# 1. LLM 설정
llm = ChatOllama(model="qwen3:8b", temperature=0)

# 2. 도구 설정
# 기본 도구들은 상대 경로에서 실행될 수 있으므로, 작업 디렉토리를 명확히 해주는 것이 좋습니다.
working_directory = os.getcwd()

# 파일 시스템 도구
list_tool = ListDirectoryTool(root_dir=working_directory)
write_tool = WriteFileTool(root_dir=working_directory)
read_tool = ReadFileTool(root_dir=working_directory)

# 웹 요청 도구
requests_wrapper = TextRequestsWrapper()
requests_get_tool = RequestsGetTool(requests_wrapper=requests_wrapper, allow_dangerous_requests=True)

# 커스텀 웹 페이지 내용 추출 도구
def fetch_webpage_content(url: str) -> str:
    """웹 페이지의 내용을 가져오고 텍스트만 추출합니다."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # 간단한 HTML 태그 제거 (BeautifulSoup 없이)
        content = response.text
        # 기본적인 HTML 태그들 제거
        import re
        content = re.sub(r'<script.*?</script>', '', content, flags=re.DOTALL)
        content = re.sub(r'<style.*?</style>', '', content, flags=re.DOTALL)
        content = re.sub(r'<[^>]+>', '', content)
        content = re.sub(r'\s+', ' ', content).strip()
        
        return f"웹페이지 내용 (URL: {url}):\n{content[:2000]}..."  # 처음 2000자만
    except Exception as e:
        return f"웹페이지 가져오기 실패: {str(e)}"

# Tool 객체로 래핑
fetch_webpage_tool = Tool(
    name="fetch_webpage",
    description="HTML 태그들을 제거한 웹 페이지의 내용을 가져옵니다. URL을 입력하면 해당 페이지의 텍스트 내용을 반환합니다.",
    func=fetch_webpage_content
)

# 5개 도구: list_tool, write_tool, read_tool, requests_get_tool, fetch_webpage_tool
tools = [list_tool, write_tool, read_tool, requests_get_tool, fetch_webpage_tool]

# 3. 프롬프트 설정 - 순수 테스트 (힌트 없음)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful AI assistant that can interact with the file system and web. You have access to the following tools: {tools}. Use them to answer the user's request."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# 4. 에이전트 생성
agent = create_tool_calling_agent(llm, tools, prompt)

# 5. AgentExecutor 생성
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 6. 에이전트 실행 - 순수 도구 선택 능력 평가
print("=== qwen3:8b 모델의 자연스러운 도구 사용 능력 평가 ===")
print("테스트 목표: 힌트 없이 적절한 도구를 선택하고 체이닝하는 능력 평가")
print("-" * 60)

user_request = "현재 디렉터리에서 'urls'로 시작하는 .txt 파일을 찾아서 읽고, 그 파일에 있는 URL의 웹페이지 내용을 가져온 다음, 핵심 내용을 정리해서 'url_summary.md' 파일로 저장해줘."

print(f"에이전트에게 요청: {user_request}")
print("-" * 60)

try:
    result = agent_executor.invoke({"input": user_request, "chat_history": [], "tools": tools})
    print("\n--- 에이전트 실행 결과 ---")
    print(result["output"])
except Exception as e:
    print(f"에이전트 실행 중 오류 발생: {e}")
