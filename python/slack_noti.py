import os, requests
import logging
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from langchain.tools import Tool
from langchain.chains import SequentialChain, LLMChain
from langchain.chains.base import Chain
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

from utils import is_pdf_by_signature, encode_image, pdf_to_image, search_with_google_api, add_receipt_to_notion, upload_to_s3, download_file
from chains import OCRChain, SearchChain, CategoryAssistantChain
from prompts import assistant_prompt, analysis_prompt

# 로깅 설정
logging.basicConfig(level=logging.INFO)
current_path = Path.cwd()

# App-Level Token 및 Bot Token 설정
load_dotenv('../.env')
SLACK_BOT_TOKEN = os.getenv("SLACK-BOT")
CHANNEL_ID = 'C086KU2133M' # Channel ID
SLACK_APP_TOKEN = os.getenv("SLACK-APP")
OPEN_AI_KEY = os.getenv("OPEN-AI")

# Slack 앱을 초기화합니다
app = App(token=SLACK_BOT_TOKEN)

# 모든 이벤트를 로깅하는 미들웨어
@app.middleware
def log_request(logger, body, next):
    logger.info(f"이벤트 수신: {body['event']['type']}")
    next()
        
# 파일이 공유될 때 실행되는 이벤트 리스너
@app.event("file_shared")
def handle_file_shared(event, say, logger, client):
    # 이미지 파일인지 확인합니다
    file_id = event["file_id"]
    logger.info(f"새로운 이미지가 공유되었습니다. 파일 ID: {file_id}")
    # 파일 정보를 가져옵니다
    file_info = client.files_info(file=file_id)
    file = file_info["file"]
    file_url = file["url_private_download"]
    image_path = current_path / '../image' / file["name"]
    if download_file(file_url, image_path, SLACK_BOT_TOKEN):
        say(f"파일 '{image_path}'을 성공적으로 다운로드했습니다.")
        #####################################
        # langchain으로 정보 처리
        # OCRChain 초기화
        ocr_chain = OCRChain()
        # SearchChain 초기화
        # Tool로 검색 기능 정의
        search_tool = Tool(
            name = "SearchBusinessCategory",
            func = lambda query: "\n".join(
                list([x['snippet'] for x in search_with_google_api(query)])
            ),
            description="상호명을 검색하여 관련 업종 정보를 제공합니다."
        )
        search_chain = SearchChain(search_tool)
        # Analysis Chain (검색결과로부터 업종 판단) 초기화
        analysis_chain = LLMChain(
            llm = ChatOpenAI(
                model="gpt-4", 
                temperature=0,
                openai_api_key = OPEN_AI_KEY
            ),
            prompt=analysis_prompt,
            output_key="business_category",  # 출력 키를 명시적으로 설정
        )
        # Assistant Chain 초기화
        assistant_chain = CategoryAssistantChain(prompt=assistant_prompt)
        sequential_chain = SequentialChain(
            chains=[ocr_chain, search_chain, analysis_chain, assistant_chain],
            input_variables=["image_path"],
            output_variables=["assistant_response", "business_category", "ocr_response"],
            verbose=True
        )

        # 실행
        result = sequential_chain.invoke({"image_path": image_path})
        logger.info("\n최종 결과:")
        logger.info(result['assistant_response'])
        #####################################
        # Notion DB에 정보 추가
        try:
            s3_file_url = upload_to_s3(image_path, image_path.name)
            add_receipt_to_notion(result['ocr_response'], s3_file_url, result['business_category'], result['assistant_response'])
            app.client.chat_postMessage(channel=CHANNEL_ID, text= f"데이터가 성공적으로 Notion에 저장되었습니다.")
            app.client.chat_postMessage(channel=CHANNEL_ID, text= result['assistant_response'])
        except Exception as e:
            logger.error(f"Notion에 데이터를 추가하는 중 오류 발생: {e}")
    else:
        say(f"파일 다운로드에 실패했습니다.")
        

# message에 대한 처리는 필요 없음
@app.event("message")
def handle_message_events(event, logger, say):
    # 메시지 텍스트 추출
    message_text = event["text"]
    # 메시지 발신자 ID 추출
    user_id = event["user"]
    # 채널 ID 추출
    channel_id = event["channel"]
    # 추출한 정보 사용 예시
    say(f"<@{user_id}>님이 '{message_text}' 메시지를 보냈습니다.")
    logger.info(f"메시지 수신: {message_text}")


# 메시지 이벤트를 처리하는 리스너
# @app.message()
# def handle_message(message, logger, say):
#     # 메시지 내용을 가져옵니다
#     text = message['text']
#     logger.info(f"메시지를 받았습니다: {text}")
#     # 메시지에 대한 응답을 보냅니다
#     say(f"메시지를 받았습니다: {text}", channel=CHANNEL_ID)

# 리액션 추가 이벤트 핸들러
@app.event("reaction_added")
def handle_reaction_added(body, logger):
    logger.info(f"리액션 추가 이벤트 수신: {body['event']}")
    
# 에러 핸들러
@app.error
def custom_error_handler(error, body, logger):
    logger.exception(f"에러 발생: {error}")
    logger.info(f"에러 발생 이벤트 바디: {body}")

   
    
    
# 메인 함수
if __name__ == "__main__":
    print("Slack 앱을 시작합니다")
    print(f"App Token: {SLACK_APP_TOKEN}")
    print(f'Bot Token: {SLACK_BOT_TOKEN}')
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()