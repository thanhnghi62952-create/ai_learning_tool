import os
import sys
import threading
import time

from flask import Flask, render_template, request
from services.openai_service import explain, generate_quiz, generate_image

app = Flask(__name__)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

@app.route("/", methods=["GET", "POST"])
def home():
    explanation = None
    quiz = None
    image_url = None

    if request.method == "POST":
        concept = request.form["concept"]
        explanation = explain(concept)
        quiz = generate_quiz(concept)
        image_url = generate_image(concept)

    return render_template(
        "index.html",
        explanation=explanation,
        quiz=quiz,
        image_url=image_url
    )

if __name__ == "__main__":
    # ÉP BẬC NGROK KHI CHẠY TRÊN COLAB
    # Kiểm tra nếu có thư mục /content (thư mục gốc đặc trưng của Colab)
    if os.path.exists('/content'):
        from pyngrok import ngrok
        
        print("1. Đang khởi chạy Flask ở luồng ngầm...")
        flask_thread = threading.Thread(target=run_flask)
        flask_thread.daemon = True
        flask_thread.start()
        
        print("2. Đang chờ 3 giây để Flask ổn định cổng kết nối...")
        time.sleep(3)
        
        print("3. Đang mở đường hầm kết nối Ngrok...")
        ngrok.set_auth_token("3DhVvUvlnwnA4E8eZVDNAb99FID_7CmT8sBCZELcoN7bPwNP9")
        
        try:
            ngrok.disconnect(ngrok.get_tunnels()[0].public_url)
        except:
            pass
            
        public_url = ngrok.connect(5000)
        print("\n" + "="*50)
        print(f"🚀 LINK SẢN PHẨM SỬ DỤNG ĐƯỢC CỦA BẠN ĐÂY:")
        print(f"{public_url}")
        print("="*50 + "\n")
        
        while True:
            time.sleep(1)
    else:
        # Khi deploy lên server thật (như Railway), hệ thống không có thư mục /content, Flask sẽ chạy thẳng ở đây
        run_flask()
