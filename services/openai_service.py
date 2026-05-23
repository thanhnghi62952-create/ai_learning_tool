import sys
import os
from openai import OpenAI

def get_client():
    if 'google.colab' in sys.modules:
        from google.colab import userdata
        return OpenAI(api_key=userdata.get('OPENAI_API_KEY'))
    else:
        return OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

client = get_client()

def explain(concept):
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Explain clearly for beginners with simple examples"},
                {"role": "user", "content": concept}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"Lỗi: {str(e)}"

def generate_quiz(concept):
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Create a multiple choice quiz about the concept"},
                {"role": "user", "content": concept}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"Lỗi: {str(e)}"

def generate_image(concept):
    # Khai báo sẵn cấu trúc hàm để app.py import không bị lỗi sập server
    return "Tính năng tạo ảnh đang được phát triển"
