import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template, request, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from services.openai_service import explain, generate_quiz, generate_image

app = Flask(__name__)
# Chuỗi khóa bảo mật session bắt buộc phải cấu hình khi làm việc thương mại
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "b4f8d52361a9e8c4d7b2a5f1d9e3c6b8")

def get_db_connection():
    db_url = os.environ.get("DATABASE_URL")
    return psycopg2.connect(db_url, cursor_factory=RealDictCursor)

# ==================== LUỒNG XỬ LÝ ĐĂNG KÝ (REGISTER) ====================
@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template("auth.html", error="Vui lòng điền đầy đủ email và mật khẩu.")

    # Mã hóa mật khẩu thành chuỗi bảo mật an toàn cao
    password_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Thêm người dùng mới vào bảng users, tặng sẵn 5 lượt dùng miễn phí
        cur.execute(
            "INSERT INTO users (email, password_hash, role, credits_left) VALUES (%s, %s, 'free', 5) RETURNING id;",
            (email, password_hash)
        )
        user = cur.fetchone()
        conn.commit()

        # Đăng ký xong tự động đăng nhập luôn
        session['user_id'] = user['id']
        session['user_email'] = email

        cur.close()
        conn.close()
        return redirect(url_for("home"))
    except psycopg2.errors.UniqueViolation:
        return render_template("auth.html", error="Email này đã được đăng ký trên hệ thống.")
    except Exception as e:
        return render_template("auth.html", error=f"Lỗi hệ thống: {str(e)}")

# ==================== LUỒNG XỬ LÝ ĐĂNG NHẬP (LOGIN) ====================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("auth.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s;", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        # Kiểm tra sự tồn tại của user và đối chiếu chuỗi mật khẩu hash
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['user_email'] = user['email']
            return redirect(url_for("home"))
        else:return render_template("auth.html", error="Tài khoản hoặc mật khẩu không chính xác.")
    except Exception as e:
        return render_template("auth.html", error=f"Lỗi hệ thống: {str(e)}")

# ==================== LUỒNG ĐĂNG XUẤT (LOGOUT) ====================
@app.route("/logout")
def logout():
    session.clear() # Xóa sạch cookie phiên làm việc
    return redirect(url_for("login"))

# ==================== TRANG CHỦ ỨNG DỤNG (HOME) ====================
@app.route("/", methods=["GET", "POST"])
def home():
    # CHỐT CHẶN BẢO MẬT: Nếu chưa đăng nhập, bắt buộc đá về trang login
    if 'user_id' not in session:
        return redirect(url_for("login"))

    user_id = session['user_id']
    explanation = None
    quiz = None
    image_url = None
    selected_concept = None
    history_list = []

    conn = get_db_connection()
    cur = conn.cursor()

    # Lấy thông tin tài khoản thời gian thực của người dùng hiện tại
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
