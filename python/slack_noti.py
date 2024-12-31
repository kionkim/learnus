import os, requests
import logging
from pathlib import Path
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from chatgpt_ocr import extract_receipt_info

# 로깅 설정
logging.basicConfig(level=logging.INFO)
current_path = Path.cwd()

# App-Level Token 및 Bot Token 설정
load_dotenv('../.env')
SLACK_BOT_TOKEN = os.getenv("SLACK-BOT-RECEIPT")
CHANNEL_ID = 'C086KU2133M' # Channel ID
SLACK_APP_TOKEN = os.getenv("SLACK-APP-RECEIPT")

# Slack 앱을 초기화합니다
app = App(token=SLACK_BOT_TOKEN)

# 모든 이벤트를 로깅하는 미들웨어
@app.middleware
def log_request(logger, body, next):
    logger.info(f"이벤트 수신: {body['event']['type']}")
    # write_message(f"이벤트 수신: {body['event']['type']}")
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
    file_name = current_path / '../image' / file["name"]
    if download_file(file_url, file_name):
        say(f"파일 '{file_name}'을 성공적으로 다운로드했습니다.")
        # langchain으로 정보 처리
        
        receipt_info = extract_receipt_info(file_name)
        # 추출된 정보를 바탕으로 카테고리 판단
        
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


def download_file(file_url, file_name):   # 파일을 다운로드합니다
    response = requests.get(file_url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
    if response.status_code == 200:
        # 파일을 저장합니다
        with open(file_name, "wb") as f:
            f.write(response.content)
        return True
    else:
        return False


def write_message(msg):
    app.client.chat_postMessage(channel=CHANNEL_ID, text=msg)
    
    
# 메인 함수
if __name__ == "__main__":
    print("Slack 앱을 시작합니다")
    print(f"App Token: {SLACK_APP_TOKEN}")
    print(f'Bot Token: {SLACK_BOT_TOKEN}')
    handler = SocketModeHandler(app, SLACK_APP_TOKEN)
    handler.start()