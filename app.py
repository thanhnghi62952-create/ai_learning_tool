import os
import json
import base64
import requests
import time
import uuid
from flask import Flask, render_template, request, session, redirect, url_for
from openai import OpenAI
from supabase import create_client, Client

# =====================================================================
# CẤU HÌNH HỆ THỐNG & BIẾN MÔI TRƯỜNG
# =====================================================================
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "super-secret-dev-key")

# Khởi tạo OpenAI Client
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Khởi tạo Supabase Client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Khởi tạo Stability AI API Key
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")


# =====================================================================
# TẦNG 2: XỬ LÝ LOGIC AI ĐỘC LẬP (AI SERVICE LAYER)
# =====================================================================
def goi_openai_xu_ly(khai_niem: str, user_level: str = "beginner") -> dict:
    """
    Hàm xử lý trí tuệ nhân tạo nâng cao áp dụng Prompt Taxonomy.
    """
    system_instruction = f"""
    You are an AI Educational Architect and Master Graphic Designer. Your job is to create a personalized teaching plan and design the perfect visual prompt for an image generation AI (Stable Diffusion 3).

    CONTEXT:
    - User Learning Level: {user_level}
    - Concept to explain: {khai_niem}

    --- TAXONOMY STEP 1: USER EMPATHY ANALYSIS ---
    Analyze where the user might struggle with this concept based on their level ({user_level}). 
    - If Beginner: They struggle with technical jargon, abstract mathematics, and 'the big picture'.
    - If Advanced: They struggle with edge cases, architectural trade-offs, and deep system mechanics.

    --- TAXONOMY STEP 2: PEDAGOGICAL TEACHING PLAN ---
    Create a structured 3-step teaching plan tailored to their level:
    1. Intuitive Analogy (For beginners) or Core Principle (For advanced).
    2. Deep Technical Breakdown (Clean Markdown).
    3. Quick Retention Quiz question.

    --- TAXONOMY STEP 3: VISUAL CLASSIFICATION & DECISION ---
    Analyze the nature of the concept to choose the correct image style:
    - STYLE A: SYSTEM DIAGRAM (For structural, multi-step, or architectural concepts like Neural Networks, Databases, Protocols).
      * Aesthetic: Modern 3D isometric blueprint, clean vector flowchart, connective nodes, corporate tech colors, white background.
    - STYLE B: VISUAL METAPHOR / ABSTRACT CONCEPTUAL (For invisible, psychological, or non-physical concepts like Inflation, Deep Work, Recursion).
      * Aesthetic: A concrete physical object acting as a metaphor, high-concept 3D rendering, surreal yet clean art style, corporate tech colors, white background.

    CRITICAL IMAGE RULE: Absolutely NO text, letters, or labels inside the image.

    YOUR OUTPUT MUST BE A STRICT JSON OBJECT WITH THESE EXACT KEYS:
    {{
      "user_struggle_analysis": "Brief analysis of what the user finds difficult about this concept",
      "visual_style_chosen": "SYSTEM_DIAGRAM or VISUAL_METAPHOR based on the concept nature",
      "teaching_plan": {{
        "analogy": "A relatable real-world comparison",
        "detailed_explanation": "The core textbook explanation in Vietnamese with clean markdown",
        "quiz": "A dynamic multiple choice question to test understanding"
      }},
      "stability_prompt": "The exact English prompt following the chosen visual style (A or B), forced on a solid white background, ultra-clear educational asset look."
    }}
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Khái niệm: {khai_niem}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.4
    )
    
    return json.loads(response.choices[0].message.content)


def goi_stability_sinh_anh(prompt_text: str, so_lan_thu_lai: int = 2) -> str:
    """
    Hàm gọi API Stability AI thế hệ mới (Mô hình Stable Diffusion 3 - SD3 Medium)
    """
    if not STABILITY_API_KEY:
        print("Lỗi: Chưa cấu hình biến môi trường STABILITY_API_KEY trên Render!")
        return None

    url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "application/json"
    }
    
    payload = {
        "prompt": prompt_text,
        "output_format": "png",
        "model": "sd3-medium",
        "aspect_ratio": "1:1"
    }

    for i in range(so_lan_thu_lai + 1):
        try:
            print(f"--> [Lần thử {i+1}] Đang gửi yêu cầu vẽ ảnh SD3 tới Stability AI...")
            response = requests.post(url, headers=headers, files={"none": (None, "")}, data=payload, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                base64_string = data.get("image")
                if base64_string:
                    print("--> Sinh ảnh bằng Stability AI SD3 thành công xuất sắc!")
                    return f"data:image/png;base64,{base64_string}"
            
            elif response.status_code in [502, 503, 504]:
                print(f"Máy chủ Stability nghẽn mạch ({response.status_code}). Đang chờ dữ liệu để thử lại...")
                time.sleep(3)
            else:
                print(f"Lỗi API Stability ({response.status_code}): {response.text}")
                break
        except requests.exceptions.Timeout:
            print("--> Yêu cầu xử lý ảnh bị Timeout. Đang kích hoạt thử lại...")
            time.sleep(2)
        except Exception as e:
            print(f"Trục trặc kết nối hệ thống Stability: {e}")
            break
            
    print("❌ Quá số lần thử lại. Sử dụng ảnh sơ đồ cứu hộ Pollinations AI.")
    return None


# =====================================================================
# TẦNG 3: ĐIỀU HƯỚNG & KIỂM SOÁT ỨNG DỤNG (CONTROLLER LAYER)
# =====================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Bạn có thể thay chuỗi ID mẫu này bằng cơ chế xác thực người dùng thực tế từ Supabase Auth
        session['user_id'] = "41199175-edc1-4f28-afb5-645597e5a949" 
        session['user_email'] = "user@example.com"
        return redirect(url_for('home'))
        
    return render_template('login.html', error=None)


@app.route("/", methods=["GET", "POST"])
@app.route("/home")
def home():
    if 'user_id' not in session:
        return redirect(url_for("login"))
        
    user_id = session['user_id']
    explanation = None
    quiz = None
    image_url = None
    concept = None
    user_struggle_analysis = None
    history_list = []

    # Khởi tạo thông tin hồ sơ mặc định đề phòng lỗi kết nối DB ban đầu
    user_profile = {'role': 'free', 'credits_left': 0}
    credits = 0
        
    try:
        # Lấy thông tin người dùng từ Supabase
        res = supabase.table("users").select("*").eq("id", user_id).execute()
        if res.data and len(res.data) > 0:
            user_profile = res.data[0]
            credits = user_profile.get('credits_left', 0)

        # Xử lý khi nhận yêu cầu tra cứu từ Form (POST)
        if request.method == 'POST':
            concept = request.form.get('concept', '').strip()
            
            if concept:
                if credits <= 0:
                    explanation = "⚠️ Bạn đã hết lượt tra cứu miễn phí. Vui lòng nâng cấp tài khoản thương mại để tiếp tục tăng hiệu suất học tập!"
                else:
                    # BƯỚC 1: Gọi gpt-4o phân tích dữ liệu văn bản theo cấu trúc Prompt Taxonomy
                    try:
                        data_dict = goi_openai_xu_ly(concept)
                        
                        # Phân rã dữ liệu từ JSON trả về của OpenAI để truyền sang index.html
                        user_struggle_analysis = data_dict.get('user_struggle_analysis', '')
                        
                        teaching_plan = data_dict.get('teaching_plan', {})
                        # Tổ hợp lời giải thích sinh động bao gồm Analogy + Detailed Explanation
                        analogy = teaching_plan.get('analogy', '')
                        detailed = teaching_plan.get('detailed_explanation', '')
                        
                        explanation = f"### 💡 Ẩn dụ thực tế:\n{analogy}\n\n### 🔍 Phân tích chuyên sâu:\n{detailed}"
                        quiz = teaching_plan.get('quiz', '')
                        
                        stability_prompt = data_dict.get('stability_prompt', '')
                    except Exception as ai_err:
                        print(f"❌ Lỗi hệ thống Core GPT-4o: {ai_err}")
                        explanation = "Không thể kết nối với dịch vụ trí tuệ nhân tạo. Vui lòng thử lại!"
                        stability_prompt = None

                    # BƯỚC 2: Gọi Stability AI SD3 sinh ảnh thông minh
                    if stability_prompt:
                        image_url = goi_stability_sinh_anh(stability_prompt)
                        
                        # Hàng rào bảo vệ: Nếu Stability lỗi, tự động cấp ảnh dự phòng thay thế từ Pollinations
                        if not image_url:
                            clean_keyword = concept.lower().replace(' ', ',')
                            image_url = f"https://image.pollinations.ai/p/{clean_keyword}?width=1024&height=1024&nologo=true"

                    # BƯỚC 3: Lưu lịch sử vào Supabase và thực hiện trừ Lượt dùng (Credits)
                    if explanation and ("Không thể kết nối" not in explanation) and ("hết lượt tra cứu" not in explanation):
                        try:
                            # Tự sinh UUID ngẫu nhiên dạng text cho cột ID phòng lỗi Bigint
                            history_id = str(uuid.uuid4())
                            history_data = {
                                "id": history_id,
                                "user_id": user_id, 
                                "concept": concept,
                                "explanation": explanation,
                                "image_url": image_url
                            }
                            supabase.table("history").insert(history_data).execute()
                        except Exception as db_err:
                            print(f"⚠️ Cảnh báo lỗi cấu trúc lịch sử bảng history: {db_err}")

                        # Tính toán và cập nhật lại số lượt dùng mới của người dùng
                        new_credits = max(0, credits - 1)
                        supabase.table("users").update({"credits_left": new_credits}).eq("id", user_id).execute()
                        
                        credits = new_credits
                        user_profile['credits_left'] = new_credits

        # Đồng bộ lấy danh sách lịch sử tra cứu của user để hiển thị lên sidebar giao diện
        try:
            history_res = supabase.table("history").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
            history_list = history_res.data if history_res.data else []
        except Exception as history_err:
            print(f"⚠️ Không thể tải danh mục lịch sử (Vui lòng kiểm tra lại kiểu dữ liệu cột id): {history_err}")
            history_list = []

        # Trả toàn bộ dữ liệu sạch về file index.html để hiển thị đồng bộ cấu trúc Tailwind
        return render_template('index.html', 
                               credits=credits, 
                               user_profile=user_profile,
                               explanation=explanation, 
                               quiz=quiz, 
                               image_url=image_url, 
                               concept=concept, 
                               user_struggle_analysis=user_struggle_analysis,
                               history=history_list)
        
    except Exception as e:
        print(f"❌ Lỗi hệ thống nghiêm trọng tại home: {e}")
        fake_profile = {'role': 'free', 'credits_left': 0}
        return render_template('index.html', credits=0, user_profile=fake_profile, explanation="Hệ thống đang gặp sự cố kết nối dữ liệu.", quiz=None, image_url=None, concept=concept, history=[])


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)
