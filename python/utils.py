import os, re, json, base64, openai, boto3, requests
from io import BytesIO
from dotenv import load_dotenv
from pdf2image import convert_from_path
from googleapiclient.discovery import build
from notion_client import Client
import urllib.parse


load_dotenv('../.env')
openai.api_key = os.getenv("OPEN-AI")
GOOGLE_API_KEY = os.getenv("GOOGLE-SEARCH-API-KEY")
SEARCH_ENGINE_ID = os.getenv("SEARCH-ENGINE-ID")
NOTION_DATABASE_ID = os.getenv("NOTION-DB")
NOTION_API_KEY = os.getenv("NOTION")
AWS_ACCESS_KEY = os.getenv("AWS-ACCESS-KEY")
AWS_SECRET_KEY = os.getenv("AWS-SECRET-KEY")
S3_BUCKET_NAME = os.getenv("S3-BUCKET-NAME")
S3_REGION = os.getenv("S3-BUCKET-REGION")


def download_file(file_url, file_name, SLACK_BOT_TOKEN):   # 파일을 다운로드합니다
    response = requests.get(file_url, headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"})
    if response.status_code == 200:
        # 파일을 저장합니다
        with open(file_name, "wb") as f:
            f.write(response.content)
        return True
    else:
        return False
    
    
def is_pdf_by_signature(file_path):
    """
    파일의 첫 4바이트를 읽어 PDF Signature('%PDF')인지 확인.
    """
    try:
        with open(file_path, 'rb') as file:
            header = file.read(4)  # 첫 4바이트 읽기
            return header == b'%PDF'
    except Exception as e:
        print(f"오류 발생: {e}")
        return False
    
    
def encode_image(image_path):
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode('utf-8')
    
    
def pdf_to_image(file_path):
    try:
        image = convert_from_path(file_path, first_page=0, last_page=1)[0]
        buffered = BytesIO()
        image.save(buffered, format="JPEG")  # JPEG 포맷으로 저장
        buffered.seek(0)

        # Base64 인코딩
        base64_image = base64.b64encode(buffered.read()).decode('utf-8')
        return base64_image
    except Exception as e:
        print(e)
        return None
    

def extract_json_from_string(input_string):
    """
    문자열에서 JSON 객체를 추출하여 Python dict로 변환.
    Args:
        input_string (str): 입력 문자열 (JSON 포함).
    Returns:
        dict: 추출된 JSON 객체.
    """
    try:
        # JSON 추출을 위한 정규식
        json_match = re.search(r'\{.*\}', input_string, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)  # JSON 부분만 추출
            json_obj = json.loads(json_str)  # JSON 문자열을 Python dict로 변환
            return json_obj
        else:
            raise ValueError("JSON 객체를 찾을 수 없습니다.")
    except Exception as e:
        print(f"오류 발생: {e}")
        return None
    
    
def extract_receipt_info(image_path):
    """
    영수증 이미지를 ChatGPT로 분석하여 정보를 추출합니다.
    
    Args:
        image_path (str): 영수증 이미지 파일 경로.
    
    Returns:
        dict: 추출된 영수증 정보 (상호명, 날짜, 항목, 총액).
    """
    try:
        # 이미지 파일 열기
        if is_pdf_by_signature(image_path):
            base64_image = pdf_to_image(image_path)
        else:
            base64_image = encode_image(image_path)
        response = openai.chat.completions.create(
            model="gpt-4o",  # GPT-4 Vision 모델 사용
            messages=[
                {"role": "system", "content": "You are an assistant that extracts information from receipt images."},
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
        # 응답 데이터 파싱
        result = extract_json_from_string(response.choices[0].message.content)
        return result
    
    except Exception as e:
        print(f"오류 발생: {e}")
        return None
    
    
def search_with_google_api(query, num_results=10):
    api_key = GOOGLE_API_KEY  # Google API 키
    cse_id = SEARCH_ENGINE_ID   # Custom Search Engine ID
    try:
        service = build("customsearch", "v1", developerKey=api_key)
        results = service.cse().list(q=query, cx=cse_id, num=num_results).execute()
        items = results.get("items", [])
        return [
            {
                "title": item["title"], "snippet": item.get("snippet")  # 본문 내용 추가
            } 
            for item in items
            if item.get("snippet") is not None
        ]
    except Exception as e:
        return f'Google Search API Error: {e}'
    
    
def upload_to_s3(file_path, file_name):
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=AWS_ACCESS_KEY,
        aws_secret_access_key=AWS_SECRET_KEY,
        region_name=S3_REGION,
    )
    try:
        encoded_file_name = urllib.parse.quote(file_name)
        # S3에 파일 업로드
        s3_client.upload_file(
            file_path, 
            S3_BUCKET_NAME, 
            file_name,
            # ExtraArgs={"ACL": "public-read"}
        )
        # S3 URL 생성
        file_url = f"https://{S3_BUCKET_NAME}.s3.{S3_REGION}.amazonaws.com/{encoded_file_name}"
        return file_url
    except Exception as e:
        print("S3 업로드 오류:", e)
        return None
    
def add_receipt_to_notion_no_assistant(data, file_url, business_category):
    notion = Client(auth=NOTION_API_KEY)
    try:
        file_name = file_url.split("/")[-1]  # URL의 마지막 부분을 파일 이름으로 사용
        encoded_file_name = urllib.parse.quote(file_name)
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "상호명": {"title": [{"text": {"content": data["상호명"]}}]},
                "날짜": {"date": {"start": data["날짜"]}},
                "총액": {"number": data["총액"]},
                "업종": {"rich_text": [{"text": {"content": business_category}}]},
                "비목": {"rich_text": [{"text": {"content": ""}}]},
                "영수증": {
                    "files": [
                        {
                            "type": "external", 
                            "external": {"url": file_url},
                            "name": encoded_file_name  # 파일 이름 설정
                        }
                    ]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "type": "text", 
                                "text": {"content": f"{item['이름']}: {item['가격']}원"}
                            }
                        ]
                    },
                }
                for item in data["항목"]
            ]
        )
        print("데이터가 성공적으로 Notion에 저장되었습니다:", response["id"])
    except Exception as e:
        print("Notion 저장 오류:", e)
        
        
    
def add_receipt_to_notion(data, file_url, business_category, account):
    notion = Client(auth=NOTION_API_KEY)
    try:
        file_name = file_url.split("/")[-1]  # URL의 마지막 부분을 파일 이름으로 사용
        encoded_file_name = urllib.parse.quote(file_name)
        response = notion.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "상호명": {"title": [{"text": {"content": data["상호명"]}}]},
                "날짜": {"date": {"start": data["날짜"]}},
                "총액": {"number": data["총액"]},
                "업종": {"rich_text": [{"text": {"content": business_category}}]},
                "비목": {"rich_text": [{"text": {"content": account}}]},
                "영수증": {
                    "files": [
                        {
                            "type": "external", 
                            "external": {"url": file_url},
                            "name": encoded_file_name  # 파일 이름 설정
                        }
                    ]
                }
            },
            children=[
                {
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [
                            {
                                "type": "text", 
                                "text": {"content": f"{item['이름']}: {item['가격']}원"}
                            }
                        ]
                    },
                }
                for item in data["항목"]
            ]
        )
        print("데이터가 성공적으로 Notion에 저장되었습니다:", response["id"])
    except Exception as e:
        print("Notion 저장 오류:", e)