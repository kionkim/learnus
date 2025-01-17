import os, openai
from openai import OpenAI
from langchain.chains.base import Chain
from langchain.prompts import PromptTemplate

from typing import Dict
from typing import Dict
from dotenv import load_dotenv
from utils import is_pdf_by_signature, encode_image, pdf_to_image, extract_json_from_string

load_dotenv('../.env')

client = OpenAI(api_key=os.getenv("OPEN-AI"))

class OCRChain(Chain):
    """
    OpenAI를 이용해서 OCR을 진행하는 사용자 정의 체인.
    """
    def __init__(self):
        super().__init__()

    @property
    def input_keys(self):
        return ["image_path"]

    @property
    def output_keys(self):
        return ["ocr_response"]  # 출력값으로 Assistant의 응답을 반환

    def _call(self, inputs: Dict[str, str]) -> Dict[str, str]:
        image_path = inputs["image_path"]
        # print(f"Image path: {image_path}")
        try:
            # 이미지 파일 열기
            if is_pdf_by_signature(image_path):
                base64_image = pdf_to_image(image_path)
            else:
                base64_image = encode_image(image_path)
            response = openai.chat.completions.create(
                model="gpt-4o",  # GPT-4 Vision 모델 사용
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an assistant that extracts information from receipt images."
                    },
                    {
                        "role": "user", 
                        "content": [
                            {
                                "type": "text",
                                "text": '''다음 텍스트는 영수증의 정보입니다. 이 텍스트에서 가게 이름, 날짜, 항목, 총액을 분석하고, 아래의 JSON형식으로 결과를 반환해 주세요.
                                JSON 형식:
                                {
                                    "상호명": "가게 이름",
                                    "날짜": "YYYY-MM-DD",
                                    "항목": [
                                        {"이름": "상품1", "가격": 상품1 가격},
                                        {"이름": "상품2", "가격": 상품2 가격}
                                    ],
                                    "총액": 총액
                                }
                                반환할 JSON 형식은 반드시 위의 구조와 일치해야 하며, 불필요한 설명은 포함하지 마세요.
                                영수증 텍스트:
                                """
                                [여기에 영수증의 텍스트 또는 OCR로 추출한 내용이 들어갑니다]
                                """
                                결과:''' 
                            },{
                                "type": "image_url",
                                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                            }
                        ],
                    },
                ],
            )
            
            # 응답 파싱
            raw_response = extract_json_from_string(response.choices[0].message.content)
            print(f'raw_response = {raw_response}')
            return {"ocr_response": raw_response}
        except Exception as e:
            
            return {"ocr_response": f"Error during OpenAI API call: {e}"}
        

class SearchChain(Chain):
    def __init__(self, tool):
        super().__init__()
        self._tool = tool

    @property
    def input_keys(self):
        return ["ocr_response"]

    @property
    def output_keys(self):
        return ["search_results", "business_name"]

    def _call(self, inputs, **kwargs):
        business_name = inputs['ocr_response']["상호명"]
        item = ','.join([x["이름"] for x in inputs['ocr_response']['항목']])
        print('business_name = ', business_name)
        print('item = ', item)
        if len(item) > 0:
            query = ','.join([business_name, item])
        else:
            query = business_name
        print('query = ', query)
        search_results = self._tool.func(query)
        return {"search_results": search_results, "business_name": business_name}
    
    
class CategoryAssistantChain(Chain):
    """
    OpenAI Assistant에 질의하는 사용자 정의 체인.
    """
    def __init__(self, prompt: PromptTemplate):
        super().__init__()
        self._prompt = prompt


    @property
    def input_keys(self):
        # PromptTemplate에서 정의된 입력 변수 사용
        return self._prompt.input_variables

    @property
    def output_keys(self):
        return ["assistant_response"]
    

    def _call(self, inputs: Dict[str, str]) -> Dict[str, str]:
        formatted_prompt = self._prompt.format(**inputs)
        print('ocr_response = ', inputs['ocr_response'])
        print('business_category = ', inputs['business_category'])
        # OpenAI API 호출
        thread_id = 'thread_tN3lfcgGLhP56xQuwpTPS11L'
        assistant_id = 'asst_az9m2hNBZWYkpNZiiFELc4Dc'
        message = client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content= formatted_prompt
        )
        # Run 생성 및 실행
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )
        # Run 완료 대기
        while run.status != "completed":
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        # 결과 메시지 가져오기
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        # 결과 출력
        for i, message in enumerate(messages):
            if message.role == "assistant":
                if i == 0:
                    response = message.content[0].text.value
        response = response.strip().replace('```','').replace('json','').replace('\n','')
        return {"assistant_response": response, "business_category": inputs['business_category'], "ocr_response": inputs['ocr_response']}
    