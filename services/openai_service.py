import os
import sys
import base64
from openai import OpenAI
# khoi tao clinet thong minh linh hoat evironment 
def get_client():
  if 'google.colab' in sys.modules:
    from google.colab import userdata
    return OpenAI(api_key=userdata.get('OPENAI_API_KEY'))
  else:
    return OpenAI(api_key=os.environ.get['OPENAI_API_KEY'])
    client = get_client()

    # 1. Giải thích
def explain(concept):
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


# 2. Tạo câu hỏi
def generate_quiz(concept):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
                "content": "Create 1 simple question to test understanding"
            },
            {"role": "user", "content": concept}
        ]
    )
    return res.choices[0].message.content


# 3. TẠO VISUAL PLAN (QUAN TRỌNG)
def build_visual_plan(concept):
    res = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "Break concept into visual teaching plan"
            },
            {
                "role": "user",
                "content": f"""
                Concept: {concept}

                Create:
                - Main idea
                - Key parts
                - Relationships
                - How to visualize
                """
            }
        ]
    )
    return res.choices[0].message.content


# 4. Sinh ảnh thông minh
def generate_image(concept):
    plan = build_visual_plan(concept)

    prompt = f"""
    You are an expert educational illustrator.

    Use this plan:
    {plan}

    Create a clean diagram:
    - labeled parts
    - arrows showing relationships
    - minimal design
    - white background

    The image must help a beginner understand instantly.
    """

    res = client.images.generate(
        model="gpt-image-1",
        prompt=prompt,
        size="1024x1024"
    )
    return res.data[0].url # giu nguyen cau truc tra ve link URL cua openai (tiet kiem bang thong nhanh hon danh ke)
    
      
