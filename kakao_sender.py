import os
import json
import requests
from dotenv import load_dotenv, set_key

ENV_FILE = ".env"

def refresh_token(rest_api_key, refresh_token):
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "refresh_token",
        "client_id": rest_api_key,
        "refresh_token": refresh_token
    }
    resp = requests.post(token_url, data=data)
    if resp.status_code == 200:
        return resp.json()
    return None

def _send_chunk(access_token, chunk):
    url = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    header = {"Authorization": f"Bearer {access_token}"}
    template_object = {
        "object_type": "text",
        "text": chunk,
        "link": {
            "web_url": "https://developers.kakao.com",
            "mobile_web_url": "https://developers.kakao.com"
        },
        "button_title": "원문 확인"
    }
    data = {"template_object": json.dumps(template_object)}
    resp = requests.post(url, headers=header, data=data)
    return resp

def send_to_kakao(text_message):
    load_dotenv()
    rest_api_key = os.environ.get("KAKAO_REST_API_KEY")
    access_token = os.environ.get("KAKAO_ACCESS_TOKEN")
    refresh_token_val = os.environ.get("KAKAO_REFRESH_TOKEN")

    if not rest_api_key:
        print("❌ [.env] KAKAO_REST_API_KEY 설정이 없습니다.")
        return False
        
    if not access_token:
        print("❌ [.env] KAKAO_ACCESS_TOKEN 설정이 없습니다. 처음 1회 kakao_auth.py를 실행하여 토큰을 발급받으세요.")
        return False
        
    success = True
    resp = _send_chunk(access_token, text_message)
        
    # 만료 시 1회만 리프레시 시도
    if resp.status_code == 401:
        print("💡 Access Token 재발급 시도 중...")
        new_tokens = refresh_token(rest_api_key, refresh_token_val)
        if new_tokens:
            access_token = new_tokens.get("access_token")
            set_key(ENV_FILE, "KAKAO_ACCESS_TOKEN", access_token)
                
            if "refresh_token" in new_tokens:
                refresh_token_val = new_tokens.get("refresh_token")
                set_key(ENV_FILE, "KAKAO_REFRESH_TOKEN", refresh_token_val)
                    
            # 재시도
            resp = _send_chunk(access_token, text_message)
        else:
            print("❌ 토큰 재발급 실패. kakao_auth.py로 재인증이 필요합니다.")
            return False
                
    if resp.status_code == 200:
        print(f"✅ 카카오톡 메시지 전송 성공 (1/1)")
    else:
        print(f"❌ 카카오톡 전송 실패: {resp.status_code} - {resp.text}")
        success = False
            
    return success

if __name__ == "__main__":
    send_to_kakao("카카오 연동 스크립트 테스트 메시지입니다.")
