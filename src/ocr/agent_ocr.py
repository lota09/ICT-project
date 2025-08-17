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
from src.ocr.tool_ocr import perform_ocr_on_url, perform_ocr_on_file

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
def ocr_url_image(url: str) -> str:
    """URL에서 이미지를 다운로드하고 OCR을 수행하여 텍스트를 추출합니다."""
    try:
        result = perform_ocr_on_url(url)
        if result:
            return f"OCR 성공: {len(result)}자 추출됨\n\n추출된 텍스트:\n{result}"
        else:
            return "OCR 실패: 텍스트를 추출할 수 없습니다."
    except Exception as e:
        return f"OCR 처리 중 오류 발생: {str(e)}"

def ocr_local_image(file_path: str) -> str:
    """로컬 이미지 파일에서 OCR을 수행하여 텍스트를 추출합니다."""
    try:
        result = perform_ocr_on_file(file_path)
        if result:
            return f"OCR 성공: {len(result)}자 추출됨\n\n추출된 텍스트:\n{result}"
        else:
            return "OCR 실패: 텍스트를 추출할 수 없습니다."
    except Exception as e:
        return f"OCR 처리 중 오류 발생: {str(e)}"

# Tool 객체로 래핑
ocr_url_tool = Tool(
    name="ocr_url_image",
    description="URL에서 이미지를 다운로드하고 OCR을 수행하여 한국어 텍스트를 추출합니다. 웹상의 이미지 파일의 URL을 입력하면 해당 이미지에 포함된 텍스트를 반환합니다.",
    func=ocr_url_image
)

ocr_local_tool = Tool(
    name="ocr_local_image", 
    description="로컬 이미지 파일에서 OCR을 수행하여 한국어 텍스트를 추출합니다. 로컬 파일 경로를 입력하면 해당 이미지에 포함된 텍스트를 반환합니다.",
    func=ocr_local_image
)

# 3개 도구: list_tool, write_tool, read_tool, ocr_url_tool, ocr_local_tool
tools = [list_tool, write_tool, read_tool, ocr_url_tool, ocr_local_tool]

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

# 6. 에이전트 실행 - 순수 도구 선택 능력 평가
print("=== qwen3:8b 모델의 OCR 도구 사용 능력 평가 ===")
print("테스트 목표: 힌트 없이 적절한 OCR 도구를 선택하고 체이닝하는 능력 평가")
print("-" * 60)

user_request = "src/img 디렉터리에서 이미지 파일을 찾아서 OCR로 텍스트를 추출하고, 추출한 내용을 요약해서 'ocr_summary.md' 파일로 저장해줘."

print(f"에이전트에게 요청: {user_request}")
print("-" * 60)

try:
    result = agent_executor.invoke({"input": user_request, "chat_history": [], "tools": tools})
    print("\n--- 에이전트 실행 결과 ---")
    print(result["output"])
except Exception as e:
    print(f"에이전트 실행 중 오류 발생: {e}")
