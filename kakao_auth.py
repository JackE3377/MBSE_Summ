import os
import requests
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv, set_key

# --- Settings ---
PORT = 3000
REDIRECT_URI = f"http://localhost:{PORT}/kakao-login"
ENV_FILE = ".env"

load_dotenv()
KAKAO_REST_API_KEY = os.environ.get("KAKAO_REST_API_KEY")

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urlparse(self.path)
        
        # Check if it's our callback URL
        if parsed_path.path == "/kakao-login":
            query = parse_qs(parsed_path.query)
            if 'code' in query:
                auth_code = query['code'][0]
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                html_res = "<h1>성공!</h1><p>카카오 인증이 완료되었습니다. 이 창을 닫고 터미널을 확인해주세요.</p>"
                self.wfile.write(html_res.encode("utf-8"))
                
                # We got the code, save it to server context
                self.server.auth_code = auth_code
                return
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write("<h1>실패</h1><p>code 파라미터를 찾을 수 없습니다.</p>".encode("utf-8"))
                return
                
        self.send_response(404)
        self.end_headers()

def get_kakao_token():
    if not KAKAO_REST_API_KEY or KAKAO_REST_API_KEY == "여기에_발급받으신_카카오_REST_API_키를_입력하세요":
        print("❌ [.env] 파일에 KAKAO_REST_API_KEY를 먼저 설정해주세요!")
        return

    auth_url = (
        f"https://kauth.kakao.com/oauth/authorize?client_id={KAKAO_REST_API_KEY}"
        f"&redirect_uri={REDIRECT_URI}&response_type=code"
    )

    print("========================================")
    print("🚀 [카카오톡 자동 연동 및 토큰 발급]")
    print(f"1. 잠시 후 브라우저가 열리면 카카오 로그인 및 메시지 전송 권한을 승인해주세요.")
    print("========================================")
    print(f"\n🌐 브라우저를 엽니다... {auth_url}")
    
    # 브라우저 자동 오픈
    webbrowser.open(auth_url)

    # 로컬 서버 띄워두고 콜백 대기
    print(f"⏳ 인증 완료를 대기 중입니다... 브라우저에서 동의를 마쳐주세요.")
    server_address = ('', PORT)
    try:
        httpd = HTTPServer(server_address, OAuthHandler)
    except OSError as e:
        print(f"\n❌ 포트 {PORT}번이 이미 사용 중입니다. 잠시 후 다시 실행하거나 PC를 재부팅해주세요.")
        return

    httpd.auth_code = None
    
    # 1회 요청만 처리하고 종료
    while not httpd.auth_code:
        httpd.handle_request()

    auth_code = httpd.auth_code
    print(f"\n✅ 인가 코드 획득 완료!")

    # 토큰 요청
    token_url = "https://kauth.kakao.com/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": KAKAO_REST_API_KEY,
        "redirect_uri": REDIRECT_URI,
        "code": auth_code
    }

    try:
        response = requests.post(token_url, data=data)
        tokens = response.json()
        
        if "access_token" not in tokens:
            print("❌ 토큰 발급 실패:", tokens)
            print(tokens)
            return
            
        # .env 에 저장
        set_key(ENV_FILE, "KAKAO_ACCESS_TOKEN", tokens.get("access_token"))
        if "refresh_token" in tokens:
            set_key(ENV_FILE, "KAKAO_REFRESH_TOKEN", tokens.get("refresh_token"))
            
        print("✅ 토큰이 '.env' 파일에 성공적으로 저장되었습니다!")
        print("이제 자동 브리핑 스크립트가 카카오톡으로 메시지를 전송할 수 있습니다.")
        
    except Exception as e:
        print(f"❌ 토큰 발급 중 오류 발생: {e}")
    finally:
        httpd.server_close()

if __name__ == "__main__":
    get_kakao_token()
