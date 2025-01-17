from langchain.tools import Tool
from utils import search_with_google_api

search_tool = Tool(
    name = "SearchBusinessCategory",
    func = lambda query: "\n".join(
        list([x['snippet'] for x in search_with_google_api(query)])
    ),
    description="상호명을 검색하여 관련 업종 정보를 제공합니다."
)