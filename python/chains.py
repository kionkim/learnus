import os, openai
from openai import OpenAI
from langchain.chains import SequentialChain, LLMChain
from langchain.chains.base import Chain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

from typing import Dict
from typing import Dict
from dotenv import load_dotenv
from chatgpt_ocr import is_pdf_by_signature, encode_image, pdf_to_image, extract_json_from_string

client = OpenAI(api_key=os.getenv("CHATGPT-RECEIPT"))

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
            # print(f'raw_response = {raw_response}')
            return {"ocr_response": raw_response}
        except Exception as e:
            
            return {"ocr_response": f"Error during OpenAI API call: {e}"}
        
        
# Custom Chain 정의
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
        # OpenAI API 호출
        thread_id = 'thread_Twa2ruyrfpBGhOqESAnAYn6W'
        assistant_id = 'asst_7J3TrQfqCaD5dWXZpu7665l5'
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
        # print(f'messages = {messages}')
        # 결과 출력
        for i, message in enumerate(messages):
            if message.role == "assistant":
                if i == 0:
                    response = message.content[0].text.value
        # print(f'i = {i}, response = {response}')
                
        return {"assistant_response": response}
    