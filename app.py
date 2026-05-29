import json
from pydantic import BaseModel
import os
from openai import OpenAI
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from services.openai_service import explain, generate_quiz, generate_image
from supabase import create_client, Client #fix 
#khoi tao client
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# khoi tao ung dung flask

app = Flask(__name__)
# Chuỗi khóa bảo mật session bắt buộc phải cấu hình khi làm việc thương mại
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4f8d52361a9e8c4d7b2a5f1d9e3c6b8")
#ket noi thanh toi supabase bang 2 bien vua nap tren Render (fix)
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# 1. ĐỊNH NGHĨA CẤU TRÚC JSON MONG MUỐN BẰNG PYDANTIC
class AIResponseSchema(BaseModel):
    vietnamese_explanation: str
    dalle_prompt: str


#def get_db_connection():
    #db_url = os.environ.get("DATABASE_URL")
   # return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# ==================== LUỒNG XỬ LÝ ĐĂNG KÝ (REGISTER) ====================
@app.route('/register', methods=['POST'])
def register():
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')

    if not email or not password:
        return render_template("auth.html", error="Vui lòng điền đầy đủ email và mật khẩu.")

    try:
        # 1. Gọi tính năng Auth tích hợp sẵn của Supabase để tạo tài khoản tài khoản bảo mật
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        
        # 2. Nếu đăng ký bên Supabase Auth thành công
        if response.user:
            # Lấy ID độc nhất mà Supabase vừa sinh ra cho user này
            supabase_user_id = response.user.id 
            
            # 3. Thay thế cho lệnh INSERT INTO cũ bằng lệnh API siêu sạch:
            # Chèn thông tin vào bảng 'users', tặng sẵn 5 lượt dùng miễn phí
            supabase.table("users").insert({
                "id": supabase_user_id, # Lưu ý: Nên lưu ID này để đồng bộ với Auth
                "email": email,
                "role": "free",
                "credits_left": 5
            }).execute()

            # 4. Lưu thông tin đăng nhập vào Session của Flask để giữ trạng thái đăng nhập
            session['user_id'] = supabase_user_id
            session['user_email'] = email
            
            # 5. Đăng ký xong xuôi, đưa người dùng thẳng vào trang chủ Dashboard
            return redirect(url_for('home'))
            
    except Exception as e:
        # Bắt mọi loại lỗi (trùng email, mật khẩu yếu, lỗi hệ thống) và hiển thị lên giao diện
        error_msg = str(e)
        if "already registered" in error_msg.lower() or "unique" in error_msg.lower():
            return render_template("auth.html", error="Email này đã được đăng ký trên hệ thống.")
        return render_template("auth.html", error=f"Lỗi hệ thống: {error_msg}")
# ==================== LUỒNG XỬ LÝ ĐĂNG NHẬP (LOGIN) ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("auth.html", error="Vui lòng điền đầy đủ email và mật khẩu.")

    try:
        # 1. Gọi API Supabase Auth để xác thực email và mật khẩu người dùng nhập vào
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        # 2. Nếu thông tin chính xác, Supabase sẽ trả về đối tượng user hợp lệ
        if response.user:
            # Lưu ID độc nhất của Supabase và Email vào Session của Flask để giữ trạng thái đăng nhập
            session['user_id'] = response.user.id
            session['user_email'] = response.user.email
            
            # 3. Đăng nhập thành công, đưa người dùng thẳng vào trang Dashboard (hoặc home tùy bạn cấu hình)
            return redirect(url_for("home"))
            
    except Exception as e:
        # Bộ máy Supabase Auth sẽ tự động ném ra lỗi nếu sai mật khẩu hoặc sai email
        error_msg = str(e)
        
        # Bắt các từ khóa lỗi phổ biến để hiển thị câu thông báo tiếng Việt thân thiện
        if "invalid login credentials" in error_msg.lower():
            return render_template("auth.html", error="Email hoặc mật khẩu không chính xác.")
        
        return render_template("auth.html", error=f"Lỗi hệ thống: {error_msg}")
# ==================== LUỒNG ĐĂNG XUẤT (LOGOUT) ====================
@app.route("/logout")
def logout():
    session.clear() # Xóa sạch cookie phiên làm việc
    return redirect(url_for("login"))


# =====================================================================
# TẦNG 1: ĐỊNH NGHĨA CẤU TRÚC DỮ LIỆU ĐẦU RA (DATA SCHEMA LAYER)
# =====================================================================
class AIResponseSchema(BaseModel):
    vietnamese_explanation: str
    dalle_prompt: str


# =====================================================================
# TẦNG 2: XỬ LÝ LOGIC AI ĐỘC LẬP (AI SERVICE LAYER)
# =====================================================================
def goi_openai_xu_ly(khai_niem: str) -> AIResponseSchema:
    """
    Hàm chuyên trách gọi GPT-4o để bóc tách lời giải thích chuyên sâu 
    và rèn Prompt nghệ thuật cho DALL-E 3.
    """
    # Nâng cấp kỹ thuật Prompt để AI giải thích bùng nổ, có chiều sâu chuyên gia
    system_instruction = (
        "You are an elite, world-class cross-disciplinary professor and master storyteller. "
        "The user will give you a concept from any specialized field (e.g., Quantum Computing, "
        "Machine Learning, Advanced Finance, Medicine, Psychology, or Philosophy).\n\n"
        "Your mission is to generate a JSON response with exactly two fields:\n\n"
        "1. 'vietnamese_explanation': Write a deep, captivating, and highly educational breakdown in Vietnamese. "
        "DO NOT give a dry, brief dictionary definition. Instead, structure your response beautifully:\n"
        "   - **Bản chất cốt lõi**: Explain the absolute foundation of the concept using a powerful, vivid real-world analogy "
        "that anyone can visualize instantly.\n"
        "   - **Cách thức vận hành & Ví dụ thực tế**: Give concrete, real-world practical scenarios or applications.\n"
        "   - **Tại sao nó quan trọng**: Highlight the ultimate significance of this concept in its field.\n"
        "Use engaging, sharp academic yet accessible tone with clear formatting (bullet points, bold text).\n\n"
        "2. 'dalle_prompt': Write a highly creative, cinematic, and ultra-precise English prompt for DALL-E 3. "
        "Instead of drawing a generic chart or abstract shapes, design a powerful visual metaphor, educational surreal concept art, "
        "or a clean architectural infographic that brings the concept to life. "
        "Strictly command NO unreadable, messy, or garbled text inside the generated image."
    )
    
    ai_completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Khái niệm cần tra cứu: {khai_niem}"}
        ],
        response_format=AIResponseSchema,
        temperature=0.7
    )
    return ai_completion.choices[0].message.parsed


# =====================================================================
# TẦNG 3: ĐIỀU HƯỚNG & KIỂM SOÁT ỨNG DỤNG (CONTROLLER LAYER)
# =====================================================================
@app.route("/", methods=["GET", "POST"])
@app.route("/home")
def home():
    if 'user_id' not in session:
        return redirect(url_for("login"))
        
    try:
        # 3.1. Truy vấn thông tin người dùng từ Supabase
        response = supabase.table("users").select("*").eq("id", session['user_id']).execute()
        user_profile = {'role': 'free', 'credits_left': 0}
        credits = 0
        
        if response.data and len(response.data) > 0:
            user_profile = response.data[0]
            credits = user_profile.get('credits_left', 0)

        # 3.2. Khởi tạo trạng thái dữ liệu hiển thị ban đầu
        explanation = None
        quiz = None
        image_url = None
        selected_concept = None

        # 3.3. Tiếp nhận hành động tìm kiếm (POST)
        if request.method == 'POST':
            selected_concept = request.form.get('concept', '').strip()
            
            if selected_concept:
                if credits <= 0:
                    explanation = "Bạn đã hết lượt tra cứu miễn phí. Vui lòng nâng cấp tài khoản!"
                else:
                    try:
                        # BƯỚC A: Gọi dịch vụ AI Service lấy lời giải thích sâu + Prompt ảnh
                        structured_data = goi_openai_xu_ly(selected_concept)
                        explanation = structured_data.vietnamese_explanation
                        dalle_prompt = structured_data.dalle_prompt

                        # BƯỚC B: Gọi DALL-E 3 sinh ảnh trực quan
                        image_response = client.images.generate(
                            model="dall-e-3",
                            prompt=dalle_prompt,
                            n=1,
                            size="1024x1024"
                        )
                        image_url = image_response.data[0].url
                        
                        # BƯỚC C: GHI LỊCH SỬ VÀO DATABASE SUPABASE
                        # Giả định bảng lưu lịch sử của bạn tên là 'history' hoặc 'searches'
                        # Lưu ý: Thay đổi tên bảng và trường cho khớp với Supabase của bạn
                        history_data = {
                            "user_id": session['user_id'],
                            "concept": selected_concept,
                            "explanation": explanation,
                            "image_url": image_url
                        }
                        supabase.table("history").insert(history_data).execute()

                    except Exception as ai_err:
                        print(f"Lỗi hệ thống AI Service hoặc Lưu lịch sử: {ai_err}")
                        explanation = "Hệ thống AI đang bận cấu trúc lại dữ liệu hoặc lỗi kết nối. Vui lòng thử lại!"
                        image_url = None

                    # BƯỚC D: Tạo câu hỏi ôn tập mẫu và trừ lượt dùng
                    quiz = f"Câu hỏi ôn tập nhanh cho khái niệm '{selected_concept}' đang được đồng bộ..."
                    new_credits = max(0, credits - 1)
                    supabase.table("users").update({"credits_left": new_credits}).eq("id", session['user_id']).execute()
                    
                    credits = new_credits
                    user_profile['credits_left'] = new_credits

        # =====================================================================
        # TẦNG 4: ĐỒNG BỘ HIỂN THỊ (PRESENTATION LAYER)
        # =====================================================================
        return render_template('index.html', 
                               credits=credits, 
                               user_profile=user_profile,
                               explanation=explanation, 
                               quiz=quiz, 
                               image_url=image_url, 
                               selected_concept=selected_concept)
        
    except Exception as e:
        print(f"Lỗi hệ thống nghiêm trọng tại home: {e}")
        fake_profile = {'role': 'free', 'credits_left': 0}
        return render_template('index.html', 
                               credits=0, 
                               user_profile=fake_profile, 
                               explanation="Hệ thống đang bảo trì core cấu trúc.", 
                               quiz=None, 
                               image_url=None)
    # lấy thông tin thật của người dùng hiện tại
    cur.execute("SELECT role, credits_left FROM users WHERE id = %s;", (user_id,))
    user_profile = cur.fetchone()

    # Lấy lịch sử 10 bài học gần nhất của riêng người dùng này
    cur.execute("SELECT id, concept FROM history WHERE user_id = %s ORDER BY created_at DESC LIMIT 10;", (user_id,))
    history_list = cur.fetchall()

    # Xem chi tiết bài học cũ từ lịch sử
    history_id = request.args.get("view")
    if history_id:
        cur.execute("SELECT * FROM history WHERE id = %s AND user_id = %s;", (history_id, user_id))
        item = cur.fetchone()
        if item:
            selected_concept = item["concept"]
            explanation = item["explanation"]
            quiz = item["quiz"]
            image_url = item["image_url"]

    # Xử lý khi tra cứu từ khóa mới
    if request.method == "POST":
        concept = request.form.get("concept", "").strip()
        if concept and user_profile:
            selected_concept = concept

            # 1. KIỂM TRA BỘ NHỚ ĐỆM TOÀN HỆ THỐNG (CACHE HIT)
            cur.execute("SELECT * FROM history WHERE LOWER(concept) = LOWER(%s) LIMIT 1;", (concept,))
            cached_item = cur.fetchone()

            if cached_item:
                explanation = cached_item["explanation"]
                quiz = cached_item["quiz"]
                if user_profile['role'] == 'pro':
                    image_url = cached_item["image_url"]
                else:
                    image_url = "https://placehold.co/1024x1024?text=Nang+Cap+Tai+Khoan+Pro+De+Xem+Anh"
            else:
                # 2. KIỂM TRA XEM TÀI KHOẢN FREE CÒN LƯỢT DÙNG KHÔNG (CACHE MISS)
                if user_profile['role'] == 'free' and user_profile['credits_left'] <= 0:
                    explanation = "Bạn đã tiêu hết 5 lượt tra cứu miễn phí của ngày hôm nay. Hãy nâng cấp lên gói Pro để mở khóa không giới hạn tài nguyên và tính năng sinh sơ đồ!"
                    cur.close()
                    conn.close()
                    return render_template("index.html", explanation=explanation, user_profile=user_profile, history=history_list)

                # Đủ điều kiện -> Gọi API AI sinh dữ liệu mới
                explanation = explain(concept)
                quiz = generate_quiz(concept)
                if user_profile['role'] == 'pro':
                    image_url = generate_image(concept)

                # Lưu vào lịch sử và gắn ID người dùng
                cur.execute(
                    "INSERT INTO history (concept, explanation, quiz, image_url, user_id) VALUES (%s, %s, %s, %s, %s);",
                    (concept, explanation, quiz, image_url, user_id)
                )

                # Trừ 1 credit của tài khoản free
                if user_profile['role'] == 'free':
                    cur.execute("UPDATE users SET credits_left = credits_left - 1 WHERE id = %s;", (user_id,))

                conn.commit()

                # Tải lại cấu hình hồ sơ mới nhất để in ra giao diện công khai
                cur.execute("SELECT role, credits_left FROM users WHERE id = %s;", (user_id,))
                user_profile = cur.fetchone()
                cur.execute("SELECT id, concept FROM history WHERE user_id = %s ORDER BY created_at DESC LIMIT 10;", (user_id,))
                history_list = cur.fetchall()

    cur.close()
    conn.close()
    return render_template("index.html", explanation=explanation, quiz=quiz, image_url=image_url, concept=selected_concept, user_profile=user_profile, history=history_list)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
