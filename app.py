import json
from pydantic import BaseModel
import os
import base64
import requests
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

# Khởi tạo API Key của Stability từ môi trường Render bảo mật
STABILITY_API_KEY = os.environ.get("STABILITY_API_KEY")

# =====================================================================
# TẦNG 2: XỬ LÝ LOGIC AI ĐỘC LẬP (AI SERVICE LAYER) - STABILITY AI SD3
# =====================================================================
def goi_openai_xu_ly(khai_niem: str) -> dict:
    """
    Hàm gọi GPT-4o lấy lời giải thích tiếng Việt và rèn Prompt khoa học 
    đặc tả cấu trúc thiết kế dành riêng cho mô hình cao cấp Stable Diffusion 3.
    """
    system_instruction = (
        "You are an elite cross-disciplinary professor and master storyteller.\n"
        "Your mission is to explain the user's concept in Vietnamese and design an ultra-precise prompt.\n\n"
        "CRITICAL INSTRUCTION FOR 'dalle_prompt':\n"
        "- Think like a professional professional infographic designer.\n"
        "- Use the formula: 'A clean modern 3D vector illustration of [Main Subject], isometric style, corporate tech colors, white solid background, sharp focus, textbook diagram aesthetic.'\n"
        "- Keep it clean, minimal, and highly professional.\n\n"
        "You MUST respond with a strictly valid JSON object containing exactly two keys:\n"
        "1. 'vietnamese_explanation': A deep, captivating breakdown in Vietnamese using clean markdown.\n"
        "2. 'dalle_prompt': The highly specific, descriptive English prompt following the rules above.\n\n"
        "Format your JSON output exactly like this:\n"
        "{\n"
        "  \"vietnamese_explanation\": \"...\",\n"
        "  \"dalle_prompt\": \"...\"\n"
        "}"
    )
    
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"Khái niệm cần tra cứu: {khai_niem}"}
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    content_string = response.choices[0].message.content
    return json.loads(content_string)


def goi_stability_sinh_anh(prompt_text: str, so_lan_thu_lai: int = 2) -> str:
    """
    Hàm gọi API Stability AI thế hệ mới (Mô hình Stable Diffusion 3 - SD3) 
    Tích hợp cơ chế tự động thử lại (Retry) bảo vệ hệ thống khỏi lỗi nghẽn mạng 504.
    """
    if not STABILITY_API_KEY:
        print("Lỗi: Chưa cấu hình biến môi trường STABILITY_API_KEY trên Render!")
        return None

    # Đổi sang Endpoint Core dịch vụ mới nhất của Stability AI (Hỗ trợ SD3 / SD3 Medium)
    url = "https://api.stability.ai/v2beta/stable-image/generate/sd3"
    
    headers = {
        "Authorization": f"Bearer {STABILITY_API_KEY}",
        "Accept": "application/json"  # Nhận kết quả trả về trực tiếp dưới dạng JSON chứa Base64
    }
    
    # Cấu hình form dữ liệu chuẩn cho API v2beta
    payload = {
        "prompt": prompt_text,
        "output_format": "png",
        "model": "sd3-medium", # Sử dụng dòng mô hình SD3 cân bằng tuyệt vời giữa tốc độ và trí thông minh
        "aspect_ratio": "1:1"
    }

    for i in range(so_lan_thu_lai + 1):
        try:
            print(f"--> [Lần thử {i+1}] Đang gửi yêu cầu vẽ ảnh SD3 tới Stability AI...")
            # Sử dụng files thay vì json cho endpoint v2beta của Stability
            response = requests.post(url, headers=headers, files={"none": (None, "")}, data=payload, timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                base64_string = data.get("image")
                if base64_string:
                    print("--> Sinh ảnh bằng Stability AI SD3 thành công xuất sắc!")
                    return f"data:image/png;base64,{base64_string}"
            
            elif response.status_code in [502, 503, 504]:
                print(f"Máy chủ Stability nghẽn mạch ({response.status_code}). Đang chờ dữ liệu...")
                time.sleep(3)
            else:
                print(f"Lỗi API Stability ({response.status_code}): {response.text}")
                break
        except requests.exceptions.Timeout:
            print("--> Yêu cầu xử lý ảnh bị Timeout hành trình. Đang thử lại...")
            time.sleep(2)
        except Exception as e:
            print(f"Trục trặc đường truyền kết nối: {e}")
            break
            
    print("❌ Sự cố nghẽn mạng diện rộng từ phía đối tác. Kích hoạt sơ đồ cứu hộ.")
    return None


# =====================================================================
# TẦNG 3: ĐIỀU HƯỚNG & KIỂM SOÁT ỨNG DỤNG (CONTROLLER LAYER)
# =====================================================================
@app.route("/", methods=["GET", "POST"])
@app.route("/home")
def home():
    if 'user_id' not in session:
        return redirect(url_for("login"))
        
    try:
        # Lấy thông tin người dùng từ Supabase
        res = supabase.table("users").select("*").eq("id", session['user_id']).execute()
        user_profile = {'role': 'free', 'credits_left': 0}
        credits = 0
        
        if res.data and len(res.data) > 0:
            user_profile = res.data[0]
            credits = user_profile.get('credits_left', 0)

        explanation = None
        quiz = None
        image_url = None
        selected_concept = None

        if request.method == 'POST':
            selected_concept = request.form.get('concept', '').strip()
            
            if selected_concept:
                if credits <= 0:
                    explanation = "Bạn đã hết lượt tra cứu miễn phí. Vui lòng nâng cấp tài khoản!"
                else:
                    # BƯỚC 1: Gọi GPT-4o phân tích (ĐÃ SỬA LỖI DÍNH DÒNG SYNTAX ERROR)
                    try:
                        data_dict = goi_openai_xu_ly(selected_concept)
                        explanation = data_dict.get('vietnamese_explanation', '')
                        dalle_prompt = data_dict.get('dalle_prompt', '')
                    except Exception as ai_err:
                        print(f"Lỗi hệ thống Core GPT-4o: {ai_err}")
                        explanation = "Không thể kết nối với dịch vụ trí tuệ nhân tạo. Vui lòng thử lại!"
                        dalle_prompt = None

                    # BƯỚC 2: Gọi Stability AI SD3 sinh ảnh thông minh
                    if dalle_prompt:
                        image_url = goi_stability_sinh_anh(dalle_prompt)
                        
                        # Hàng rào bảo vệ: Nếu API bên thứ ba lỗi sập, tự động cấp ảnh minh họa sơ đồ thay thế để giữ giao diện đẹp
                        if not image_url:
                            clean_keyword = selected_concept.lower().replace(' ', ',')
                            image_url = f"https://image.pollinations.ai/p/{clean_keyword}?width=1024&height=1024&nologo=true"

                    # BƯỚC 3: Đồng bộ lịch sử dữ liệu xuống Supabase
                    if explanation and ("Không thể kết nối" not in explanation) and ("hết lượt tra cứu" not in explanation):
                        try:
                            history_data = {
                                "user_id": session['user_id'], 
                                "concept": selected_concept,
                                "explanation": explanation,
                                "image_url": image_url
                            }
                            supabase.table("history").insert(history_data).execute()
                        except Exception as db_err:
                            print(f"Lỗi ghi lịch sử vào Supabase: {db_err}")

                        quiz = f"Câu hỏi ôn tập nhanh cho khái niệm '{selected_concept}' đã sẵn sàng."
                        new_credits = max(0, credits - 1)
                        supabase.table("users").update({"credits_left": new_credits}).eq("id", session['user_id']).execute()
                        
                        credits = new_credits
                        user_profile['credits_left'] = new_credits

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
        return render_template('index.html', credits=0, user_profile=fake_profile, explanation="Hệ thống đang gặp sự cố kết nối dữ liệu.", quiz=None, image_url=None)


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
