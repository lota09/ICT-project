"""
LLM Agent를 위한 OCR 도구 시스템
reference/agent_basictools.py의 구조를 완전히 따라 구현됨

OCR 기능 테스트:
1. src/img 폴더에서 이미지 파일을 찾는다
2. 찾은 이미지 파일에서 OCR로 텍스트를 추출한다
3. 추출한 텍스트를 요약하여 ocr_summary.md 파일로 저장한다

이 작업을 수행하기 위해 최소 3개의 도구(list_tool - ocr_local_tool - write_tool)를 사용해야 한다.
우리가 지켜볼 부분은:
1. 결과가 의도한대로 나오는지
2. OCR 도구를 적절히 선택하고 사용하는지
3. 파일 시스템 도구들과 OCR 도구를 체이닝하여 사용하는지
"""

import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_community.tools.file_management import ListDirectoryTool, WriteFileTool, ReadFileTool
from langchain.tools import Tool

# OCR 함수들 임포트
from tool_ocr import count_html_images, ocr_html_images

# 1. LLM 설정
llm = ChatOllama(model="qwen3:8b", temperature=0)

# 2. 도구 설정
# 기본 도구들은 상대 경로에서 실행될 수 있으므로, 작업 디렉토리를 명확히 해주는 것이 좋습니다.
working_directory = os.getcwd()

# 파일 시스템 도구
list_tool = ListDirectoryTool(root_dir=working_directory)
write_tool = WriteFileTool(root_dir=working_directory)
read_tool = ReadFileTool(root_dir=working_directory)

# OCR 도구들
# HTML 분석 도구들
def count_html_img_tool_func(html_content: str) -> str:
    """HTML 콘텐츠에서 이미지 개수를 카운팅합니다."""
    try:
        count = count_html_images(html_content)
        return f"HTML에서 발견된 이미지 개수: {count}개"
    except Exception as e:
        return f"HTML 이미지 카운팅 중 오류 발생: {str(e)}"

def ocr_html_tool_func(html_content: str) -> str:
    """HTML 콘텐츠의 이미지들에서 OCR을 수행하여 텍스트를 추출합니다."""
    try:
        results = ocr_html_images(html_content, grouped=False)
        if results:
            total_text = "\n\n".join(results)
            return f"HTML 이미지 OCR 성공: {len(results)}개 이미지에서 텍스트 추출됨\n\n추출된 텍스트:\n{total_text}"
        else:
            return "HTML 이미지 OCR 실패: 텍스트를 추출할 수 없습니다."
    except Exception as e:
        return f"HTML 이미지 OCR 처리 중 오류 발생: {str(e)}"

ocr_html_tool = Tool(
    name="ocr_html_tool",
    description="HTML 콘텐츠에 포함된 이미지들에서 OCR을 수행하여 텍스트를 추출합니다. HTML 문자열을 입력하면 포함된 모든 이미지에서 텍스트를 추출하여 반환합니다.",
    func=ocr_html_tool_func
)

count_html_img_tool = Tool(
    name="count_html_img_tool",
    description="HTML 콘텐츠에서 이미지 개수를 카운팅합니다. HTML 문자열을 입력하면 포함된 이미지의 개수를 반환합니다.",
    func=count_html_img_tool_func
)

# 5개 도구: list_tool, write_tool, read_tool, ocr_html_tool, count_html_img_tool
tools = [list_tool, write_tool, read_tool, ocr_html_tool, count_html_img_tool]

# 3. 프롬프트 설정 - 순수 테스트 (힌트 없음)
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful AI assistant that can interact with the file system and perform OCR on images. You have access to the following tools: {tools}. Use them to answer the user's request."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ]
)

# 4. 에이전트 생성
agent = create_tool_calling_agent(llm, tools, prompt)

# 5. AgentExecutor 생성
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 6. 에이전트 실행 - HTML 이미지 OCR 도구 테스트
print("=== qwen3:8b 모델의 HTML 이미지 OCR 도구 사용 능력 평가 ===")
print("테스트 목표: HTML 파일의 이미지 포함 콘텐츠를 분석하고 요약하는 능력 평가")
print("-" * 60)

user_request = "src/assets 디렉터리에서 HTML 파일을 찾아서 읽고, 그 내용을 분석해서 요약해줘. 만약 HTML 내용에 이미지가 포함되어 있다면 OCR을 사용해서 이미지의 텍스트도 함께 포함해서 종합적으로 요약한 다음 'content_summary.md' 파일로 저장해줘."

print(f"에이전트에게 요청: {user_request}")
print("-" * 60)

try:
    result = agent_executor.invoke({"input": user_request, "chat_history": [], "tools": tools})
    print("\n--- 에이전트 실행 결과 ---")
    print(result["output"])
except Exception as e:
    print(f"에이전트 실행 중 오류 발생: {e}")
