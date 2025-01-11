from langchain.prompts import PromptTemplate

assistant_prompt = PromptTemplate(
    input_variables=["ocr_response"],
    template="""다음은 분석 지침입니다:
                1. JSON 데이터에서 '상호명' 값을 확인하세요.
                2. 상호명을 검색하여 업종을 추론해 보세요.
                3. '상호명'을 기반으로 아래 카테고리 중 하나를 정확히 선택하세요:
                    - 회의비
                    - 교통비
                    - 식대
                4. 가능한 경우 단답형으로 항목만 답변하세요. (예: "식대")
                5. 정확한 카테고리를 판단할 수 없는 경우:
                    - "판단 필요"라고 답변하세요.
                    - "판단 필요"인 이유를 1~2 문장으로 간단히 설명하세요.
                6. 결과는 다음 형식으로 반환하세요:
                    - 카테고리: [선택된 항목 또는 판단 필요]
                    - 이유: [간단한 설명, 없을 경우 "없음"]

                JSON 데이터:
                {ocr_response}

                답변:
    """,
)


# Prompt 정의
search_analyze_prompt = PromptTemplate(
    input_variables=["business_name", "search_results"],
    template="""
    다음은 상호명 '{business_name}'에 대한 검색 결과입니다:

    {search_results}

    검색 결과를 기반으로 해당 상호의 업종을 추론하세요. 가능한 경우 단답형으로 업종만 답변하세요.
    예: "식당", "카페", "의류", "교통" 등. 
    """
)