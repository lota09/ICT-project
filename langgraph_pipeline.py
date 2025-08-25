import os
from langchain.agents import Tool
from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableLambda
from typing import Any, Dict, List, Optional

# for OCR Node


# for Summary Node
from SummaryContent import GeminiSummarizer
from Parsers import NoticeOutput, parse_notice_output

class NotifyState(dict):
    title: str                      # from Crawl-Detect Engine
    content: str                    # from Crawl-Detect Engine
    image: List[dict]               # from Crawl-Detect Engine
    category: str                   # from Crawl-Detect Engine

    ocr_text: Optional[str]         # from OCR(optional) node
    json_summary: Dict[str, Any]    # from Summary node

def OCR(state):
    #===================================================================
    # TO DO: 분기 조건에서 image 존재여부를 확인하여 추출 후 OCR 작업 수행
    image = None
    # image to ocr_text
    ocr_text = None
    #===================================================================

    return {'ocr_text':ocr_text}

def Summary(state):
    title = state.get('title')
    ocr_text = state.get('ocr_text') or "" # ocr_text가 없다면 빈 문자열을 처리 예정
    content = state.get('content')

    summarizer = GeminiSummarizer()
    summary = summarizer.summarize(title, ocr_text, content)
    json_summary = parse_notice_output(summary)
    return {'json_summary':json_summary}

def OCR_branching_condition(state):
    # image 있으면 OCR_node로
    # image 없으면 Summary_node로
    #==============================================
    # TO DO: OCR 작업 수행 여부를 결정하는 분기 조건
    if True:
        return True
    else:
        return False
    #==============================================

graph = StateGraph(NotifyState)
graph.add_node("OCR_Node", RunnableLambda(OCR))
graph.add_node("Summary_Node", RunnableLambda(Summary))

graph.add_conditional_edges(
    "START",
    OCR_branching_condition,
    {True: "OCR_Node", False: "Summary_Node"}
)
graph.add_edge("OCR_Node", "Summary_Node")
graph.set_finish_point("Summary_Node")

llm_agent = graph.compile()


#==========================================================
# Crawl-Detect Engine으로부터 받은 json_input을
# llm agent(langgraph)로 처리하여 json_output을 반환합니다.
#==========================================================

# json_input = Crawl-Detect Engine으로부터 받은 dict 형태의 공지사항 1건이라고 가정
json_input = None

# from Crawl-Detect Engine
json_output = llm_agent.invoke(
    {'title':json_input['title']},
    {'content':json_input['content']},
    {'image':json_input['image']},
    {'category':json_input['category']},
)