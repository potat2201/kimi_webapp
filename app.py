#!/usr/bin/env python3
"""
Kimi Web App - Simple web interface to ask Kimi K2.5 questions
With User Authentication
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import json
import os
import datetime
import base64
import io
import logging
import fitz  # PyMuPDF for PDF handling
from PIL import Image  # PIL Image for image processing

app = Flask(__name__)

# Use absolute path for database to avoid working directory issues
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ensure instance directory exists (for Railway deployment)
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
os.makedirs(INSTANCE_DIR, exist_ok=True)

# Setup logging
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'ocr_debug.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

# Session configuration for multi-host access (IP, localhost, internal DNS)
app.config['SESSION_COOKIE_NAME'] = 'session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True if using HTTPS
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Database config - Support both Railway PostgreSQL and local SQLite
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    # Production: Railway PostgreSQL
    # SQLAlchemy requires 'postgresql://' instead of 'postgres://'
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    logger.info("Using PostgreSQL database (Railway)")
else:
    # Development: Local SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(INSTANCE_DIR, "users.db")}'
    logger.info("Using SQLite database (Local)")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '請先登入以使用此功能。'

# Log requests for debugging
@app.before_request
def log_request():
    """Log all requests for debugging"""
    print(f"[{datetime.datetime.now()}] {request.method} {request.url} from {request.remote_addr}")
    print(f"  Host: {request.host}, Referrer: {request.referrer}")

# User Model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    credits = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def use_credit(self):
        """Use one credit, returns True if successful"""
        if self.credits > 0:
            self.credits -= 1
            db.session.commit()
            return True
        return False

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Configuration
API_KEY = os.environ.get('KIMI_API_KEY', 'sk-HGVKBnPGIpCkOWvVj6HouQxp4ostkX5W1IV5yot6OQUitDbj')
BASE_URL = "https://api.moonshot.ai/v1"
MODEL = "kimi-k2.5"

# Pre-defined question - HK Education Bureau style
DEFAULT_QUESTION = "請為香港中一數學科（教育局課程指引）出一份關於代數的練習題，只出5道題目（2題選擇題、2題短答題、1題長答題），並附上答案及評分標準"


def ask_kimi(question, temperature=1.0, max_tokens=8000):
    """Send question to Kimi and return response"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": """你是一位資深的香港學校教師，熟悉教育局課程發展議會制定的各科課程指引。

出題時請遵從以下原則：
1. 符合香港教育局課程指引的要求
2. 配合學生的認知發展階段
3. 涵蓋不同認知層次（記憶、理解、應用、分析、評鑑、創造）
4. 題目用語清晰，符合香港學生慣用中文
5. 提供詳細答案及評分標準
6. 使用繁體中文（香港標準）

數學符號顯示要求（非常重要）：
- 切勿使用 LaTeX 格式（例如 $3a$），因為「$」符號在香港代表港幣，會令學生誤會
- 數學式請用純文字顯示，例如：3a、5x + 2y、(a + b)²
- 分數請用「/」表示，例如：1/2、3/4
- 指數請用「^」表示，例如：x^2、a^3
- 開方請用文字描述，例如：開方25、√16
- 方程式請用一般格式，例如：2x + 3 = 7

題目數量限制（非常重要）：
- 每次練習只出 5 道題目，避免內容過長被截斷
- 建議組合：2題選擇題 + 2題短答題 + 1題長答題
- 如用戶要求更多題目，請說明「每次只出5題，建議分多次生成」

題目格式建議：
- 選擇題：4個選項，干擾項要有合理性
- 短答題：答案簡潔明確
- 長答題：需展示思考過程
- 每題標明分數及建議作答時間

請以專業、友善的語氣協助教師準備優質的教學資源。"""
            },
            {
                "role": "user",
                "content": question
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        print(f"[{datetime.datetime.now()}] Calling Kimi API for quiz generation...")
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=120  # Increased timeout for slower connections
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"[{datetime.datetime.now()}] Kimi API response received successfully")
        return result["choices"][0]["message"]["content"]
        
    except requests.exceptions.Timeout:
        error_msg = "Error: API request timed out. Please try again."
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API timeout")
        return error_msg
    except requests.exceptions.ConnectionError as e:
        error_msg = f"Error: Connection failed. Check internet connection."
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API connection error: {e}")
        return error_msg
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API error: {e}")
        return error_msg


# Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            flash(f'歡迎回來，{username}！', 'success')
            return redirect(next_page if next_page else url_for('index'))
        else:
            flash('用戶名稱或密碼不正確', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('你已成功登出。', 'info')
    return redirect(url_for('login'))


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page (optional - you can disable this after creating your account)"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        # Validation
        if not username or not password:
            flash('請輸入用戶名稱及密碼', 'error')
            return render_template('register.html')

        if password != confirm_password:
            flash('兩次輸入的密碼不一致', 'error')
            return render_template('register.html')

        if len(password) < 6:
            flash('密碼最少需要 6 個字元', 'error')
            return render_template('register.html')

        # Check if user exists
        if User.query.filter_by(username=username).first():
            flash('此用戶名稱已被使用', 'error')
            return render_template('register.html')

        # Create new user
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('帳戶建立成功！請登入。', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/')
@login_required
def index():
    """Render the dashboard with function blocks (protected)"""
    return render_template('dashboard.html')


@app.route('/quiz')
@login_required
def quiz_generator():
    """Render the quiz generator page (protected)"""
    return render_template('quiz.html', default_question=DEFAULT_QUESTION, credits=current_user.credits)


# Default topic for lesson plan
DEFAULT_LESSON_TOPIC = "科目：中一數學\n課題：畢氏定理\n課時：40分鐘\n學生人數：30人\n特別要求：需要互動活動，配合 PowerPoint 教學"


@app.route('/lesson_plan')
@login_required
def lesson_plan_generator():
    """Render the lesson plan generator page (protected)"""
    return render_template('lesson_plan.html', default_topic=DEFAULT_LESSON_TOPIC, credits=current_user.credits)


@app.route('/composition')
@login_required
def composition_checker():
    """Render the composition correction page (protected)"""
    return render_template('composition.html', credits=current_user.credits, current_user=current_user)


@app.route('/test-ocr-page')
@login_required
def test_ocr_page():
    """Render the OCR test page (protected)"""
    return render_template('test_ocr.html')


@app.route('/test-kimi-vision', methods=['GET'])
@login_required
def test_kimi_vision():
    """Test if Kimi API supports vision with a simple request"""
    logger.info("========== TEST KIMI VISION ==========")
    
    # Create a simple 1x1 pixel red image
    try:
        from PIL import Image
        import io
        import base64
        
        # Create a simple image
        img = Image.new('RGB', (100, 100), color='red')
        output = io.BytesIO()
        img.save(output, format='PNG')
        img_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
        data_url = f"data:image/png;base64,{img_base64}"
        
        logger.info(f"Created test image: {len(data_url)} chars")
        
        # Test Kimi API with vision
        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What color is this image? Answer in one word."},
                        {"type": "image_url", "image_url": {"url": data_url}}
                    ]
                }
            ],
            "max_tokens": 50
        }
        
        logger.info(f"Sending request to {BASE_URL} with model {MODEL}")
        
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=30
        )
        
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            logger.info(f"SUCCESS! Answer: {answer}")
            return jsonify({
                'success': True,
                'message': 'Kimi Vision is working!',
                'answer': answer,
                'model': MODEL
            })
        else:
            error_text = response.text[:500]
            logger.error(f"API Error: {error_text}")
            return jsonify({
                'success': False,
                'error': f'API returned {response.status_code}',
                'details': error_text,
                'model': MODEL
            }), 500
            
    except ImportError as e:
        logger.error(f"PIL not available: {e}")
        return jsonify({
            'success': False,
            'error': 'PIL not available',
            'details': str(e)
        }), 500
    except Exception as e:
        logger.error(f"Exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


def ask_kimi_for_composition(subject, grade, composition_type, word_count, title, text, image_base64=None, temperature=1, max_tokens=4000):
    """Send composition to Kimi and return correction feedback. Supports both text and image input."""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    subject_text = "中文" if subject == "chinese" else "英文"
    
    system_prompt = f"""你是一位資深的香港{subject_text}科教師，擁有多年批改作文的經驗。請以專業、鼓勵性的語氣批改學生作文。

批改原則：
1. 符合香港教育局課程指引及該年級的寫作要求
2. 評估維度包括：內容意念、組織結構、語言運用、創意表達
3. 提供具體改善建議，而非僅僅指出錯誤
4. 使用繁體中文（香港標準）
5. 語氣友善鼓勵，同時保持專業性

批改格式請包括：
1. 【總評】整體評語（約100字）
2. 【評分】各維度評分（滿分100分）
3. 【優點】值得讚賞的地方（2-3點）
4. 【改善建議】具體改進方向（2-3點）
5. 【錯誤修正】錯別字/語法錯誤列表（如有）
6. 【參考範例】示範如何改寫某個段落（約50字）"""

    # Build user message content
    if image_base64:
        # Image mode - use vision capabilities
        # Ensure image_base64 is a data URL format
        if not image_base64.startswith('data:'):
            image_base64 = f"data:image/jpeg;base64,{image_base64}"
        
        user_content = [
            {
                "type": "text",
                "text": f"請批改以下{grade}{subject_text}作文。作文題目：{title if title else '（未提供）'}，作文類型：{composition_type}，字數要求：約{word_count}字。以下是學生手寫的作文圖片，請仔細識別圖片中的文字內容，然後按照系統提示的格式提供詳細批改。"
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_base64
                }
            }
        ]
    else:
        # Text mode
        user_content = f"""請批改以下{grade}{subject_text}作文：

作文題目：{title if title else '（未提供）'}
作文類型：{composition_type}
字數要求：約{word_count}字

【學生作文內容】
{text}

請按照上述格式提供詳細批改。"""

    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_content
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        print(f"[{datetime.datetime.now()}] Calling Kimi API for composition correction...")
        print(f"[{datetime.datetime.now()}] Mode: {'image' if image_base64 else 'text'}")
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=180
        )
        
        # Debug: print response status
        print(f"[{datetime.datetime.now()}] API Response status: {response.status_code}")
        
        response.raise_for_status()

        result = response.json()
        print(f"[{datetime.datetime.now()}] Kimi API composition correction response received")
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.HTTPError as e:
        error_msg = f"批改作文時出現錯誤：API 請求失敗 ({e.response.status_code})。請檢查圖片格式或稍後再試。"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API HTTP error: {e}")
        print(f"[{datetime.datetime.now()}] Response: {e.response.text if hasattr(e.response, 'text') else 'No response text'}")
        return error_msg
    except requests.exceptions.Timeout:
        error_msg = "批改作文時出現錯誤：API 請求超時，請稍後再試。"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API timeout (composition)")
        return error_msg
    except requests.exceptions.ConnectionError as e:
        error_msg = "批改作文時出現錯誤：連線失敗，請檢查網絡連接。"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API connection error (composition): {e}")
        return error_msg
    except Exception as e:
        error_msg = f"批改作文時出現錯誤：{str(e)}"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API error (composition): {e}")
        return error_msg


def convert_pdf_to_images(pdf_base64):
    """Convert PDF base64 to list of image base64 strings (one per page)
    
    Returns:
        List of base64 encoded image strings
    """
    try:
        logger.info("Converting PDF to images...")
        
        # Decode base64 PDF
        if ',' in pdf_base64:
            header, base64_data = pdf_base64.split(',', 1)
        else:
            base64_data = pdf_base64
        
        pdf_bytes = base64.b64decode(base64_data)
        
        # Open PDF with PyMuPDF
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        images = []
        
        logger.info(f"PDF has {len(doc)} pages")
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Render page to image (at 150 DPI for good quality)
            mat = fitz.Matrix(2, 2)  # 2x zoom for better quality
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Save to base64
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=90, optimize=True)
            img_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
            data_url = f"data:image/jpeg;base64,{img_base64}"
            
            images.append(data_url)
            logger.info(f"Converted page {page_num + 1} to image ({len(data_url)} chars)")
        
        doc.close()
        logger.info(f"PDF conversion complete: {len(images)} pages")
        return images
        
    except Exception as e:
        logger.error(f"PDF conversion failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def compress_image_base64(image_base64, max_size_kb=1000, max_dimension=1500):
    """Compress image to reduce size for API upload"""
    try:
        # Parse base64 data
        if ',' in image_base64:
            header, base64_data = image_base64.split(',', 1)
        else:
            base64_data = image_base64
            header = "data:image/jpeg;base64"
        
        # Check if compression needed
        data_size_kb = len(base64_data) * 3 / 4 / 1024
        logger.info(f"Image compression: original size {data_size_kb:.1f} KB")
        
        if data_size_kb <= max_size_kb:
            logger.info("Image compression: not needed")
            return image_base64  # No compression needed
        
        logger.info(f"Compressing image from {data_size_kb:.1f} KB to target {max_size_kb} KB...")
        
        # Try to use PIL if available
        try:
            from PIL import Image
            logger.info("PIL Image library available")
            
            img_data = base64.b64decode(base64_data)
            img = Image.open(io.BytesIO(img_data))
            logger.info(f"Image opened: mode={img.mode}, size={img.size}")
            
            # Resize if too large
            width, height = img.size
            if width > max_dimension or height > max_dimension:
                ratio = min(max_dimension / width, max_dimension / height)
                new_size = (int(width * ratio), int(height * ratio))
                img = img.resize(new_size, Image.LANCZOS)
                logger.info(f"Resized image to {new_size[0]}x{new_size[1]}")
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
                logger.info("Converted to RGB")
            
            # Compress with reduced quality
            output = io.BytesIO()
            quality = 85
            while quality > 30:
                output.seek(0)
                output.truncate()
                img.save(output, format='JPEG', quality=quality, optimize=True)
                compressed_size_kb = len(output.getvalue()) / 1024
                if compressed_size_kb <= max_size_kb:
                    break
                quality -= 10
            
            compressed_base64 = base64.b64encode(output.getvalue()).decode('utf-8')
            logger.info(f"Compressed to {compressed_size_kb:.1f} KB (quality={quality})")
            return f"{header},{compressed_base64}"
            
        except ImportError as e:
            logger.warning(f"PIL not available: {e}")
            return image_base64
            
    except Exception as e:
        logger.error(f"Image compression failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return image_base64  # Return original on error


def extract_text_from_images_kimi(image_base64_list):
    """Use Kimi API to extract text from multiple images (OCR)
    
    Args:
        image_base64_list: List of base64 encoded image strings
        
    Returns:
        Combined extracted text from all images
    """
    
    if not isinstance(image_base64_list, list):
        image_base64_list = [image_base64_list]
    
    logger.info(f"========== OCR FUNCTION START - {len(image_base64_list)} IMAGES ==========")
    
    all_texts = []
    
    for idx, image_base64 in enumerate(image_base64_list, 1):
        logger.info(f"OCR: Processing image {idx}/{len(image_base64_list)}")
        
        text = extract_single_image_text(image_base64)
        
        if text and not text.startswith("ERROR"):
            all_texts.append(f"【第 {idx} 頁】\n{text}")
            logger.info(f"OCR: Image {idx} extracted {len(text)} chars")
        else:
            logger.error(f"OCR: Image {idx} failed - {text}")
            all_texts.append(f"【第 {idx} 頁】\n[無法識別]")
    
    combined_text = "\n\n".join(all_texts)
    logger.info(f"OCR: Total extracted {len(combined_text)} chars from {len(image_base64_list)} images")
    logger.info("========== OCR FUNCTION END ==========")
    
    return combined_text


def extract_single_image_text(image_base64):
    """Extract text from a single image using Kimi API"""
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Validate image_base64 format
    if not image_base64.startswith('data:image/'):
        logger.error("OCR ERROR: Invalid image data format")
        return "ERROR: Invalid image format"
    
    # Compress image if too large
    image_base64 = compress_image_base64(image_base64)
    
    # Check data size
    base64_data = image_base64.split(',')[1] if ',' in image_base64 else image_base64
    data_size_kb = len(base64_data) * 3 / 4 / 1024
    logger.info(f"OCR: Single image size: {data_size_kb:.1f} KB")
    
    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一個OCR文字識別助手。請仔細識別圖片中的所有文字內容，並將識別結果以純文字形式返回。不要添加任何解釋或評論，只返回圖片中的文字內容。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "請識別這張圖片中的所有文字內容，並以純文字形式返回："
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_base64
                        }
                    }
                ]
            }
        ],
        "temperature": 1,
        "max_tokens": 2000
    }
    
    logger.info(f"OCR: Preparing API call to {BASE_URL}")
    logger.info(f"OCR: Using model {MODEL}")
    logger.info(f"OCR: API Key starts with: {API_KEY[:10]}...")
    
    try:
        logger.info("OCR: Sending request to Kimi API...")
        
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        # Debug logging
        logger.info(f"OCR: API Response status: {response.status_code}")
        
        if response.status_code != 200:
            error_text = response.text[:1000] if response.text else 'No response text'
            logger.error(f"OCR: API Error response: {error_text}")
            return f"API_ERROR: Status {response.status_code} - {error_text}"
            
        response.raise_for_status()
        
        result = response.json()
        logger.info(f"OCR: Response JSON keys: {list(result.keys())}")
        
        if 'choices' not in result:
            logger.error(f"OCR: No 'choices' in response: {result}")
            return f"API_ERROR: No choices in response - {str(result)[:500]}"
            
        message = result["choices"][0]["message"]
        extracted_text = message.get("content", "")
        
        # kimi-k2.5 may put content in reasoning_content
        if not extracted_text and "reasoning_content" in message:
            extracted_text = message.get("reasoning_content", "")
            logger.info("OCR: Using reasoning_content instead of content")
        
        if not extracted_text:
            logger.error(f"OCR: No content extracted. Message: {message}")
            return f"API_ERROR: No content in response - {str(message)[:500]}"
        
        logger.info(f"OCR: SUCCESS! Extracted {len(extracted_text)} characters")
        logger.info("========== OCR FUNCTION END ==========")
        return extracted_text
        
    except requests.exceptions.HTTPError as e:
        error_detail = e.response.text[:1000] if hasattr(e.response, 'text') else 'N/A'
        logger.error(f"OCR: HTTP Error: {e}")
        logger.error(f"OCR: Response: {error_detail}")
        return f"HTTP_ERROR: {str(e)} - {error_detail}"
        
    except Exception as e:
        logger.error(f"OCR: Exception {type(e).__name__}: {e}")
        import traceback
        traceback_str = traceback.format_exc()
        logger.error(f"OCR: Traceback: {traceback_str}")
        return f"EXCEPTION: {type(e).__name__}: {str(e)}"


@app.route('/check_composition', methods=['POST'])
@login_required
def check_composition():
    """API endpoint to check composition (protected). Supports both text and image input."""
    # Check if user has credits (skip for admin)
    is_admin = current_user.username == 'admin'
    if not is_admin and current_user.credits <= 0:
        return jsonify({
            'status': 'error',
            'message': '您的積分已用完，請聯絡管理員充值',
            'credits': 0
        }), 403

    # Deduct credit (skip for admin)
    if not is_admin:
        current_user.use_credit()

    data = request.get_json()
    subject = data.get('subject', 'chinese')
    grade = data.get('grade', '中一')
    composition_type = data.get('composition_type', '記敘文')
    word_count = data.get('word_count', '300-400')
    title = data.get('title', '')
    mode = data.get('mode', 'text')

    extracted_text = None
    
    try:
        if mode == 'image':
            # Image mode - extract text from images using Kimi OCR
            # Support both 'images' array (new) and 'image_data' (legacy)
            images = data.get('images', [])
            image_data = data.get('image_data', '')
            
            if images and isinstance(images, list):
                # New format: array of images
                image_data = images
                logger.info(f"Received {len(images)} files for processing")
            elif image_data:
                # Legacy format: single image
                image_data = [image_data]
                logger.info("Received single file (legacy format)")
            else:
                return jsonify({
                    'result': '請上傳圖片或 PDF',
                    'status': 'error',
                    'credits_remaining': current_user.credits,
                    'message': '未收到檔案數據'
                }), 400
            
            # Process files: convert PDFs to images
            processed_images = []
            for idx, file_data in enumerate(image_data):
                if file_data.startswith('data:application/pdf') or file_data.startswith('data:pdf'):
                    # Convert PDF to images
                    logger.info(f"File {idx+1} is PDF, converting to images...")
                    pdf_images = convert_pdf_to_images(file_data)
                    if pdf_images:
                        processed_images.extend(pdf_images)
                        logger.info(f"PDF converted to {len(pdf_images)} images")
                    else:
                        return jsonify({
                            'result': f'第 {idx+1} 個 PDF 檔案轉換失敗',
                            'status': 'error',
                            'credits_remaining': current_user.credits,
                            'message': f'PDF {idx+1} 轉換失敗'
                        }), 500
                elif file_data.startswith('data:image/'):
                    # Regular image
                    processed_images.append(file_data)
                else:
                    return jsonify({
                        'result': f'第 {idx+1} 個檔案格式不正確',
                        'status': 'error',
                        'credits_remaining': current_user.credits,
                        'message': f'檔案 {idx+1} 格式錯誤'
                    }), 400
            
            logger.info(f"[{datetime.datetime.now()}] Processing {len(processed_images)} image(s) for composition correction...")
            
            # Step 1: Extract text from images using Kimi OCR
            extracted_text = extract_text_from_images_kimi(processed_images)
            
            if extracted_text is None:
                return jsonify({
                    'result': '無法識別圖片中的文字。請嘗試：\n1. 上傳更清晰的圖片\n2. 確保圖片中的文字清晰可讀\n3. 或直接輸入文字模式',
                    'status': 'error',
                    'credits_remaining': current_user.credits,
                    'message': 'OCR 識別失敗'
                }), 500
            
            if len(extracted_text) < 30:
                return jsonify({
                    'result': f'圖片識別出的文字太短（僅 {len(extracted_text)} 字），請上傳包含更多文字的圖片，或直接輸入文字。\n\n識別結果：{extracted_text}',
                    'status': 'error',
                    'credits_remaining': current_user.credits,
                    'message': '識別文字太短'
                }), 400
            
            # Step 2: Use extracted text for composition correction
            text = extracted_text
        else:
            # Text mode
            text = data.get('text', '')
        
        if not text or len(text) < 50:
            return jsonify({
                'result': '作文內容太短，請輸入至少 50 字以上。',
                'status': 'error',
                'credits_remaining': current_user.credits,
                'message': '作文內容太短'
            }), 400
        
        # Call composition correction
        result = ask_kimi_for_composition(subject, grade, composition_type, word_count, title, text)
        
        # Prepend OCR info if image mode
        if mode == 'image' and extracted_text:
            result = f"📄 **圖片文字識別結果**（已自動提取並批改）：\n\n---\n\n{result}"
        
        # Check if there was an error
        if result.startswith("批改作文時出現錯誤") or result.startswith("Error:"):
            print(f"[{datetime.datetime.now()}] Composition correction returned error: {result}")
            return jsonify({
                'result': result,
                'status': 'error',
                'credits_remaining': current_user.credits,
                'message': result
            }), 500
        
        return jsonify({
            'result': result,
            'status': 'success',
            'credits_remaining': current_user.credits
        })
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Exception in check_composition: {e}")
        return jsonify({
            'result': f'伺服器錯誤：{str(e)}',
            'status': 'error',
            'credits_remaining': current_user.credits
        }), 500


@app.route('/generate_lesson_plan', methods=['POST'])
@login_required
def generate_lesson_plan():
    """API endpoint to generate lesson plan (protected)"""
    # Check if user has credits
    if current_user.credits <= 0:
        return jsonify({
            'status': 'error',
            'message': '您的積分已用完，請聯絡管理員充值',
            'credits': 0
        }), 403

    # Deduct credit
    current_user.use_credit()

    data = request.get_json()
    topic = data.get('topic', DEFAULT_LESSON_TOPIC)

    # Generate lesson plan using Kimi
    try:
        lesson_plan = ask_kimi_for_lesson_plan(topic)
        
        # Check if there was an error
        if lesson_plan.startswith("生成教案時出現錯誤") or lesson_plan.startswith("Error:"):
            print(f"[{datetime.datetime.now()}] Lesson plan generation returned error: {lesson_plan}")
            return jsonify({
                'lesson_plan': lesson_plan,
                'status': 'error',
                'credits_remaining': current_user.credits,
                'message': lesson_plan
            }), 500
        
        return jsonify({
            'lesson_plan': lesson_plan,
            'status': 'success',
            'credits_remaining': current_user.credits
        })
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Exception in generate_lesson_plan: {e}")
        return jsonify({
            'lesson_plan': f'伺服器錯誤：{str(e)}',
            'status': 'error',
            'credits_remaining': current_user.credits
        }), 500


def ask_kimi_for_lesson_plan(topic, temperature=1.0, max_tokens=4000):
    """Send topic to Kimi and return lesson plan"""
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是一位資深的香港學校教師。請為以下教學主題生成詳細教案大綱，幫助教師準備教學材料。教案應包括：1.課題名稱 2.學習目標(2-3個) 3.教學重點 4.教學難點 5.教學準備 6.教學流程(含時間分配) 7.投影片內容建議 8.課後反思。使用繁體中文，語氣專業友善。"
            },
            {
                "role": "user",
                "content": f"請為以下教學主題生成詳細教案大綱：\n\n{topic}"
            }
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }

    try:
        print(f"[{datetime.datetime.now()}] Calling Kimi API for lesson plan...")
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=data,
            timeout=180  # Increased timeout for lesson plans (larger content)
        )
        response.raise_for_status()

        result = response.json()
        print(f"[{datetime.datetime.now()}] Kimi API lesson plan response received")
        return result["choices"][0]["message"]["content"]

    except requests.exceptions.Timeout:
        error_msg = "生成教案時出現錯誤：API 請求超時，請稍後再試。"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API timeout (lesson plan)")
        return error_msg
    except requests.exceptions.ConnectionError as e:
        error_msg = "生成教案時出現錯誤：連線失敗，請檢查網絡連接。"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API connection error (lesson plan): {e}")
        return error_msg
    except Exception as e:
        error_msg = f"生成教案時出現錯誤：{str(e)}"
        print(f"[{datetime.datetime.now()}] ERROR: Kimi API error (lesson plan): {e}")
        return error_msg


def admin_required(f):
    """Decorator to require admin access"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.username != 'admin':
            flash('您沒有權限訪問此頁面', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    """Admin dashboard for managing users (admin only)"""
    users = User.query.all()
    return render_template('admin.html', users=users)


@app.route('/admin/add_credits/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def add_credits(user_id):
    """Add credits to a user (admin only)"""
    user = User.query.get_or_404(user_id)

    if user.username == 'admin':
        flash('不能為管理員充值', 'error')
        return redirect(url_for('admin_dashboard'))

    try:
        credits_to_add = int(request.form.get('credits', 0))
        if credits_to_add < 1 or credits_to_add > 100:
            flash('充值數量必須在 1-100 之間', 'error')
            return redirect(url_for('admin_dashboard'))

        user.credits += credits_to_add
        db.session.commit()
        flash(f'成功為 {user.username} 充值 {credits_to_add} 積分！現有積分：{user.credits}', 'success')
    except ValueError:
        flash('請輸入有效的數字', 'error')

    return redirect(url_for('admin_dashboard'))


@app.route('/ask', methods=['POST'])
@login_required
def ask():
    """API endpoint to ask Kimi (protected)"""
    # Check if user has credits
    if current_user.credits <= 0:
        return jsonify({
            'status': 'error',
            'message': '您的積分已用完，請聯絡管理員充值',
            'credits': 0
        }), 403

    # Deduct credit
    current_user.use_credit()

    data = request.get_json()
    question = data.get('question', DEFAULT_QUESTION)

    try:
        answer = ask_kimi(question)
        
        # Check if there was an error
        if answer.startswith("Error:"):
            print(f"[{datetime.datetime.now()}] Quiz generation returned error: {answer}")
            return jsonify({
                'question': question,
                'answer': answer,
                'status': 'error',
                'credits_remaining': current_user.credits,
                'message': answer
            }), 500
        
        return jsonify({
            'question': question,
            'answer': answer,
            'status': 'success',
            'credits_remaining': current_user.credits
        })
    except Exception as e:
        print(f"[{datetime.datetime.now()}] Exception in ask: {e}")
        return jsonify({
            'question': question,
            'answer': f'伺服器錯誤：{str(e)}',
            'status': 'error',
            'credits_remaining': current_user.credits
        }), 500


def init_db():
    """Initialize database with default user"""
    with app.app_context():
        db.create_all()

        # Create default admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin')
            admin.set_password('Kimi2026')  # Change this!
            admin.credits = 999  # Admin has unlimited credits
            db.session.add(admin)
            db.session.commit()
            print("✅ 預設帳戶已建立：admin / kimi2024")
            print("⚠️  首次登入後請立即更改預設密碼！")

        # Create userA if not exists
        userA = User.query.filter_by(username='userA').first()
        if not userA:
            userA = User(username='userA')
            userA.set_password('Coolwalk_123')
            userA.credits = 5
            db.session.add(userA)
            db.session.commit()
            print("✅ 用戶已建立：userA / Coolwalk_123 (5積分)")

        # Create userB if not exists
        userB = User.query.filter_by(username='userB').first()
        if not userB:
            userB = User(username='userB')
            userB.set_password('Coolwalk_123')
            userB.credits = 15
            db.session.add(userB)
            db.session.commit()
            print("✅ 用戶已建立：userB / Coolwalk_123 (5積分)")


@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Test database connection
        user_count = User.query.count()
        db_status = f"OK ({user_count} users)"
        status = "healthy"
    except Exception as e:
        db_status = f"ERROR: {str(e)}"
        status = "unhealthy"
    
    return jsonify({
        'status': status,
        'database': db_status,
        'server': 'running',
        'timestamp': str(datetime.datetime.now())
    })


@app.route('/test-ocr', methods=['POST'])
@login_required
def test_ocr():
    """Test OCR functionality with detailed debugging"""
    data = request.get_json()
    image_data = data.get('image_data', '')
    
    debug_info = []
    
    # Step 1: Validate input
    if not image_data:
        return jsonify({'error': 'No image data provided', 'step': 1}), 400
    
    debug_info.append(f"✓ Received image data ({len(image_data)} chars)")
    
    # Step 2: Check format
    if not image_data.startswith('data:image/'):
        return jsonify({
            'error': 'Invalid image format', 
            'step': 2,
            'starts_with': image_data[:50] if image_data else 'empty'
        }), 400
    
    debug_info.append("✓ Image format looks correct")
    
    # Step 3: Try to extract text
    try:
        result = extract_text_from_image_kimi(image_data)
        
        # Check if result is an error message
        if result and (result.startswith("API_ERROR:") or result.startswith("HTTP_ERROR:") or result.startswith("EXCEPTION:")):
            debug_info.append(f"✗ OCR returned error: {result[:200]}")
            return jsonify({
                'success': False,
                'error': result,
                'debug_info': debug_info
            }), 500
        elif result:
            debug_info.append(f"✓ OCR successful ({len(result)} chars extracted)")
            return jsonify({
                'success': True,
                'extracted_text': result,
                'debug_info': debug_info
            })
        else:
            debug_info.append("✗ OCR returned None")
            return jsonify({
                'success': False,
                'error': 'OCR returned None - check server logs',
                'debug_info': debug_info
            }), 500
    except Exception as e:
        debug_info.append(f"✗ Exception: {str(e)}")
        import traceback
        debug_info.append(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'debug_info': debug_info
        }), 500


@app.route('/debug')
def debug_info():
    """Debug endpoint to show request info"""
    return jsonify({
        'request_host': request.host,
        'request_url': request.url,
        'request_base_url': request.base_url,
        'remote_addr': request.remote_addr,
        'user_agent': str(request.user_agent),
        'headers': dict(request.headers),
        'timestamp': str(datetime.datetime.now())
    })


# Initialize database on startup (runs for both Gunicorn and python app.py)
with app.app_context():
    init_db()

if __name__ == '__main__':
    # Production mode (Railway) - use PORT env var
    port = int(os.environ.get('PORT', 5000))
    is_production = os.environ.get('RAILWAY_ENVIRONMENT') is not None
    
    if is_production:
        print("🚀 啟動 Cool School AI (Production Mode)")
        app.run(host='0.0.0.0', port=port, debug=False)
    else:
        # Development mode (Mac Mini local)
        print("🚀 啟動 Cool School AI...")
        print("📱 請開啟瀏覽器並前往：http://localhost:5000")
        print("🔐 預設登入資料：admin / kimi2024")
        print("🎓 Cool School AI - 專為香港學校設計")
        app.run(host='0.0.0.0', port=port, debug=True)
