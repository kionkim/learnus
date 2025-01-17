from langchain.prompts import PromptTemplate

assistant_prompt = PromptTemplate(
    input_variables=["business_category"],
    template="""
                {business_category}를 제공한 PDF를 바탕으로 판단을 해줘.
                회의비, 식비, 교통비 중의 하나로 판단해 주고, 대답은 
                "판단": 대답, "근거": 판단한 근거 형식의 json으로 답해 줘.
                세개 카테고리 중의 하나로 판단해 주면 되는데, 중에 하나로 판단이 안되면, "판단할 수 없음"으로 답해줘.
    """,
    output_variables=["assistant_response"],
)

# Prompt 정의
analysis_prompt = PromptTemplate(
    input_variables=["business_name", "search_results"],
    template="""
    다음은 상호명 '{business_name}'에 대한 검색 결과입니다:
    {search_results}
    검색 결과를 기반으로 해당 상호의 업종을 추론하세요. 가능한 경우 단답형으로 업종만 답변하세요.
    예: "식당", "카페", "의류", "교통" 등. 
    """
)