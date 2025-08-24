from flask import Flask, render_template, redirect, url_for, session, request, jsonify
import os
from dotenv import load_dotenv
import sys
from datetime import datetime
from authlib.integrations.flask_client import OAuth
import json
import csv

# 웹사이트 전용 DB 모듈 import
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db.db import WebsiteDB as DB

# DB 파일 경로 설정
relative_path = "../db/notice.db"

current_file_path = os.path.abspath(__file__)
current_dir = os.path.dirname(current_file_path)
DB_PATH = os.path.abspath(os.path.join(current_dir, relative_path))
load_dotenv(os.path.abspath(os.path.join(current_dir, ".env")))
print(DB_PATH)

# DB 연결 관리 함수
def get_db():
    """새로운 DB 연결을 생성하고 사용 후 자동으로 닫힘"""
    return DB(path=DB_PATH)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-here')

# Google OAuth 설정
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv('GOOGLE_CLIENT_ID', 'your-google-client-id'),
    client_secret=os.getenv('GOOGLE_CLIENT_SECRET', 'your-google-client-secret'),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={
        'scope': 'openid email profile'
    }
)

# Jinja2 템플릿 필터 추가
@app.template_filter('tojsonfilter')
def to_json_filter(obj):
    return json.dumps(obj)

# 템플릿 함수들 추가
@app.template_global()
def get_category_icon(category):
    icons = {
        '학사공지': '📚',
        '일반공지': '📢', 
        '장학공지': '💰',
        '취업공지': '💼',
        '학술공지': '🔬',
        '국제공지': '🌍'
    }
    return icons.get(category, '📋')

@app.template_global()
def get_category_description(category):
    descriptions = {
        '학사공지': '수강신청, 시험일정, 학적 관련 중요 공지사항',
        '일반공지': '대학 생활 전반에 관한 일반적인 안내사항',
        '장학공지': '장학금 신청, 선발결과 등 장학 관련 정보',
        '취업공지': '채용정보, 취업박람회, 진로 관련 안내',
        '학술공지': '학술행사, 연구활동, 세미나 관련 정보',
        '국제공지': '교환학생, 해외연수, 국제프로그램 안내'
    }
    return descriptions.get(category, '관련 공지사항을 받아보세요')

@app.template_global()
def get_weekly_avg(notification_id):
    # 실제로는 데이터베이스에서 통계를 가져와야 하지만, 여기서는 더미 데이터 사용
    avg_data = {
        1: '3-5',
        2: '2-4',
        3: '1-2', 
        4: '5-7'
    }
    return avg_data.get(notification_id, '2-3')


@app.route('/')
def index():
    if 'user' not in session:
        return render_template('landing.html')
    
    try:
        # 새로운 DB 클래스 사용
        user_id = session['user']['sub']
        
        with DB(path=DB_PATH) as db:
            # 새로운 구독 시스템으로 구독 ID 조회
            subscribed_ids = db.get_user_subscription_ids(user_id)
            
            # 새로운 DB 클래스를 사용하여 공지사항 데이터 가져오기
            notifications = db.get_user_notifications(user_id, limit=20)
        
        return render_template('index.html', notifications=notifications)
    
    except Exception as e:
        print(f"메인 페이지 오류: {e}")
        return render_template('index.html', notifications=[])

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/google-login')
def google_login():
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
        user_info = token['userinfo']
        
        # 세션에 사용자 정보 저장
        session['user'] = user_info
        
        # 새로운 DB 클래스로 사용자 정보 저장
        with DB(path=DB_PATH) as db:
            print(user_info['sub'], user_info['email'])
            result = db.register_user(user_info['sub'], user_info['email'])
            print(f"User registration result: {result}")  # 디버깅용
        
        return redirect(url_for('index'))
    
    except Exception as e:
        print(f"OAuth 콜백 오류: {e}")
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')

@app.route('/subscribe')
def subscribe():
    if 'user' not in session:
        return redirect(url_for('login'))
    
    try:
        # 새로운 DB 클래스로 공지사항 데이터 가져오기
        user_id = session['user']['sub']
        
        with DB(path=DB_PATH) as db:
            button_notifications, dropdown_data = db.get_notification_categories()
            subscribed_ids = db.get_user_subscription_ids(user_id)
        
        # 문자열 형태로 변환 (템플릿 호환성)
        subscribed_ids = [str(id) for id in subscribed_ids]
        
        return render_template('subscribe.html', 
                             button_notifications=button_notifications,
                             dropdown_data=dropdown_data,
                             subscribed_ids=subscribed_ids)
    
    except Exception as e:
        print(f"구독 페이지 예상치 못한 오류: {e}")
        return render_template('subscribe.html', 
                             button_notifications=[], 
                             dropdown_data={}, 
                             subscribed_ids=[])

@app.route('/update-subscription', methods=['POST'])
def update_subscription():
    if 'user' not in session:
        from flask import abort
        abort(401)
    
    try:
        selected_ids = request.json.get('selected_notifications', [])
        print(selected_ids)
        user_id = session['user']['sub']
        
        print(f"Updating subscriptions for user {user_id}: {selected_ids}")  # 디버깅용
        
        # 새로운 DB 클래스 사용
        with DB(path=DB_PATH) as db:
            result = db.update_user_subscriptions(user_id, selected_ids)
        
        print(f"Update result: {result}")  # 디버깅용
        
        if result['code'] == 1:
            return jsonify({
                'success': True, 
                'message': result['message']
            })
        else:
            return jsonify({
                'success': False, 
                'message': result['message']
            }), 400
    
    except Exception as e:
        print(f"구독 업데이트 오류: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/notifications')
def api_notifications():
    if 'user' not in session:
        from flask import abort
        abort(401)
    
    page = int(request.args.get('page', 1))
    limit = int(request.args.get('limit', 20))
    offset = (page - 1) * limit
    
    try:
        # 새로운 DB 클래스 사용
        user_id = session['user']['sub']
        
        with DB(path=DB_PATH) as db:
            subscribed_ids = db.get_user_subscription_ids(user_id)
            
            # DB 클래스를 사용하여 공지사항 데이터 가져오기
            notifications = db.get_user_notifications(user_id, limit=limit, offset=offset)
        
        return jsonify({
            'notifications': notifications,
            'has_more': len(notifications) == limit
        })
        
    except Exception as e:
        print(f"API notifications 오류: {e}")
        return jsonify({'error': 'Server error'}), 500

@app.route('/api/subscription-count')
def api_subscription_count():
    if 'user' not in session:
        from flask import abort
        abort(401)
    
    try:
        # 새로운 DB 클래스 사용
        user_id = session['user']['sub']
        
        with DB(path=DB_PATH) as db:
            subscribed_ids = db.get_user_subscription_ids(user_id)
            count = len(subscribed_ids)
        
        return jsonify({'count': count})
        
    except Exception as e:
        print(f"구독 개수 API 오류: {e}")
        return jsonify({'count': 0})

# 에러 핸들러 추가
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(401)
def unauthorized_error(error):
    return render_template('401.html'), 401

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('403.html'), 403

# 정책 페이지 라우트들
@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        try:
            data = request.get_json()
            
            # 기본 검증
            required_fields = ['name', 'email', 'category', 'subject', 'message']
            for field in required_fields:
                if not data.get(field):
                    return jsonify({'success': False, 'message': f'{field} 필드가 필요합니다.'})
            
            # 이메일 형식 검증
            import re
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, data['email']):
                return jsonify({'success': False, 'message': '올바른 이메일 형식이 아닙니다.'})
            
            # 실제 구현에서는 여기서 이메일 전송이나 데이터베이스 저장
            # 현재는 로그만 출력
            print(f"새로운 문의 접수:")
            print(f"  이름: {data['name']}")
            print(f"  이메일: {data['email']}")
            print(f"  카테고리: {data['category']}")
            print(f"  제목: {data['subject']}")
            print(f"  내용: {data['message'][:100]}...")
            
            return jsonify({'success': True, 'message': '문의가 성공적으로 전송되었습니다.'})
            
        except Exception as e:
            print(f"문의 처리 오류: {e}")
            return jsonify({'success': False, 'message': '서버 오류가 발생했습니다.'}), 500
    
    return render_template('contact.html')

@app.route('/delete-account', methods=['GET', 'DELETE'])
def delete_account():
    # 로그인 필수
    if 'user' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'GET':
        return render_template('delete_account.html')
    
    elif request.method == 'DELETE':
        try:
            user_id = session['user']['sub']
            user_email = session['user']['email']
            
            # 새로운 DB 클래스로 사용자 삭제
            with DB(path=DB_PATH) as db:
                result = db.delete_user(user_id)
            
            if result['code'] != 1:
                return jsonify({'success': False, 'message': result['message']})
            
            print(f"Account deleted: {user_email} (ID: {user_id})")
            
            # 세션 종료
            session.clear()
            
            return jsonify({
                'success': True, 
                'message': '계정이 성공적으로 삭제되었습니다.'
            })
            
        except Exception as e:
            print(f"계정 삭제 예상치 못한 오류: {e}")
            return jsonify({
                'success': False, 
                'message': '서버 오류가 발생했습니다.'
            }), 500

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.errorhandler(400)
def bad_request_error(error):
    return render_template('400.html'), 400

@app.errorhandler(405)
def method_not_allowed_error(error):
    return render_template('405.html'), 405

# 일반적인 예외 처리
@app.errorhandler(Exception)
def handle_exception(e):
    # HTTP 예외는 그대로 두고, 다른 예외만 500으로 처리
    if hasattr(e, 'code'):
        return e
    
    # 로그 기록
    print(f"Unhandled exception: {str(e)}")
    return render_template('500.html'), 500

# 개발용 에러 테스트 라우트 (프로덕션에서는 제거 필요)
if app.debug:
    @app.route('/test-error/<int:code>')
    def test_error(code):
        """에러 페이지 테스트용 라우트"""
        from flask import abort
        abort(code)

# 개발 환경에서만 실행되는 코드
if __name__ == '__main__':
    print("Starting Soongsil University Notice Website...")
    
    try:
        # 새로운 DB 클래스로 초기화
        print("Initializing database with new DB class...")
        with DB(path=DB_PATH) as db:
            pass  # 초기화만 확인
        
        print("Database initialization completed!")
        print("Server address: http://localhost:5000")
        print("Please check Google OAuth settings!")
        
        # Flask 앱 실행
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"Server start error: {e}")
        print("Please check .env file and Google OAuth settings!")