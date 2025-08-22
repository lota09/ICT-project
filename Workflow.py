from typing import TypedDict, Optional, List
from langgraph.graph import StateGraph, END

from SummaryContent import GeminiSummarizer
from Parsers import NoticeOutput, parse_notice_output
# ocr, email 등 추가 import 필요

MAX_RETRIES = 3 # 최대 3번까지 재시도

# LangGraph의 상태
class WorkflowState(TypedDict):
    # 입력 데이터
    original_content: str
    recipient_email: str # 이메일 주소
    image_path: Optional[str]

    # 중간 처리 데이터
    ocr_content: Optional[str]
    full_content: str # ocr 결과와 합친 내용
    retry_count: int # 요약 재시도 횟수

    # 최종 결과 데이터
    json_summary: Optional[NoticeOutput] # 요약 결과
    email_status: str # 이메일 전송 결과

def start_node(state: WorkflowState) -> WorkflowState:
    print(">> 노드 1: 시작 노드")
    return state

def run_ocr(state: WorkflowState) -> WorkflowState:
    print(">> 노드 2: OCR 실행")
    state['ocr_content'] = run_ocr_tool(state["image_path"]) # ocr 실행 함수로 수정 필요
    return state

def prepare_content(state: WorkflowState) -> WorkflowState:
    print(">> 노드 3: 텍스트 통합")
    full_text = state["original_content"]
    if state.get("ocr_content"):
        full_text += f"\n\n--- 이미지 추출 텍스트 ---\n{state['ocr_content']}"
    state['full_content'] = full_text
    return state

def summarize_and_validate(state: WorkflowState) -> WorkflowState:
    print(">> 노드 4: 요약 실행 및 품질 검사")
    summarizer = GeminiSummarizer()
    raw_json_string = summarizer.summarize(state["full_content"])

    validated_summary = parse_notice_output(raw_json_string)
    
    state['json_summary'] = validated_summary
    return state

def send_email(state: WorkflowState) -> WorkflowState:
    print(">> 노드 5: 이메일 전송")
    summary_obj = state.get('json_summary')
    
    if summary_obj:
        status = send_email_tool(summary_obj=summary_obj, receiver_email=state["recipient_email"]) # 이메일 전송 함수로 수정 필요
        state['email_status'] = status
    else:
        state['email_status'] = "이메일 전송 실패"
        
    return state

# 조건부 라우팅 함수 정의
def should_run_ocr(state: WorkflowState) -> str:
    print("OCR 필요 여부 판단")
    if has_image(state): # ocr 판단 함수로 수정필요
        return "run_ocr"
    else:
        return "prepare_content"

def check_summary_quality(state: WorkflowState) -> str:
    print("품질 검사를 통해 요약이 제대로 되었는지 결과 확인")
    
    # retry_count 초기화
    if "retry_count" not in state:
        state['retry_count'] = 0

    if state.get("json_summary"):
        # Pydantic 객체가 있으면 성공
        print("품질 검사 통과.")
        return "send_email"
    else:
        # Pydantic 객체가 None이면 실패
        print("품질 검사 실패")
        if state['retry_count'] < MAX_RETRIES:
            print(f"재시도 합니다. ({state['retry_count'] + 1}/{MAX_RETRIES})")
            # 재시도 횟수를 1 증가시키고 다시 summarize로 돌아감
            state['retry_count'] += 1
            return "summarize"
        else:
            # 최대 재시도 횟수를 초과하면 워크플로우를 종료
            print("최대 재시도 횟수 초과")
            return END

# 그래프 조립 및 컴파일
workflow = StateGraph(WorkflowState)

# 노드 추가
workflow.add_node("start_node", start_node)
workflow.add_node("run_ocr", run_ocr)
workflow.add_node("prepare_content", prepare_content)
workflow.add_node("summarize", summarize_and_validate)
workflow.add_node("send_email", send_email)

# [입력 분석] → (선택: OCR 실행) → [텍스트 통합] → [요약 & 검사 ⇄] → (성공 시) → [이메일 전송] → (종료)
workflow.set_entry_point("start_node")
workflow.add_conditional_edges(
    "start_node",
    should_run_ocr,
    {"run_ocr": "run_ocr", "prepare_content": "prepare_content"}
)
workflow.add_edge("run_ocr", "prepare_content")
workflow.add_edge("prepare_content", "summarize")
workflow.add_conditional_edges(
    "summarize",
    check_summary_quality,
    {
        "send_email": "send_email", 
        "summarize": "summarize",   
        END: END                    
    }
)
workflow.add_edge("send_email", END)

# 최종 실행 가능한 앱으로 컴파일
app = workflow.compile()