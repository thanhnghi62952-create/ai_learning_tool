import sys
import os
import base64
from openai import OpenAI

def get_client():
    if 'google.colab' in sys.modules:
        from google.colab import userdata
        return OpenAI(api_key=userdata.get('OPENAI_API_KEY'))
    else:
        return OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

# Khởi tạo biến client sát lề trái, chạy được ở cả Colab và Render
client = get_client()

def explain(concept):
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Explain clearly for beginners with simple examples"
                },
                {"role": "user", "content": concept}
            ]
        )
        return res.choices[0].message.content
    except Exception as e:
        return f"Lỗi kết nối OpenAI: {str(e)}"
