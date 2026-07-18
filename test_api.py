import os
import base64
import httpx
from dotenv import load_dotenv

load_dotenv('.env')
key = os.getenv('OPENAI_API_KEY', '')
print(f"Key length: {len(key)}")
print(f"Key prefix: {key[:20]}...")

image_path = "backend/uploads/images_35.jpeg"
print(f"Image exists: {os.path.exists(image_path)}")
print(f"Image size: {os.path.getsize(image_path)} bytes")

with open(image_path, 'rb') as f:
    base64_image = base64.standard_b64encode(f.read()).decode('utf-8')

response = httpx.post(
    'https://api.openai.com/v1/chat/completions',
    headers={
        'Authorization': f'Bearer {key}',
        'Content-Type': 'application/json'
    },
    json={
        'model': 'gpt-4o',
        'messages': [
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': 'What brand is this sneaker?'},
                    {
                        'type': 'image_url',
                        'image_url': {
                            'url': f'data:image/jpeg;base64,{base64_image}'
                        }
                    }
                ]
            }
        ],
        'max_tokens': 200
    },
    timeout=30.0
)

print(f"\nStatus: {response.status_code}")
if response.status_code == 200:
    print(f"Success: {response.json()['choices'][0]['message']['content']}")
else:
    print(f"Error: {response.text}")
