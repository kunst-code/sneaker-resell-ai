"""
비전 모델 서비스 - OpenAI GPT-4o 또는 Claude를 사용한 스니커즈 이미지 인식
"""
import os
import base64
import json
import httpx

def get_openai_key():
    return os.getenv('OPENAI_API_KEY', '')

def get_anthropic_key():
    return os.getenv('ANTHROPIC_API_KEY', '')


def encode_image_to_base64(image_path: str) -> str:
    """이미지 파일을 base64로 인코딩"""
    with open(image_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')


def get_image_media_type(image_path: str) -> str:
    """파일 확장자에서 미디어 타입 추출"""
    ext = os.path.splitext(image_path)[1].lower()
    media_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    return media_types.get(ext, 'image/jpeg')


def identify_sneaker_openai(image_path: str) -> dict:
    """OpenAI GPT-4o를 사용하여 스니커즈 식별"""
    api_key = get_openai_key()
    if not api_key:
        return {"error": "OPENAI_API_KEY가 설정되지 않았습니다."}

    base64_image = encode_image_to_base64(image_path)
    media_type = get_image_media_type(image_path)

    prompt = """이 스니커즈 사진을 분석해 주세요. 반드시 아래 JSON 형식으로만 응답해 주세요:

{
    "brand": "브랜드명 (Nike, Adidas, New Balance 등)",
    "model_name": "정식 모델명 (예: Air Jordan 1 Retro High OG)",
    "style_code": "품번/스타일 코드 (예: DD1391-100)",
    "colorway": "컬러웨이 (예: White/Black-University Red)",
    "nickname": "별명이 있다면 (예: Chicago, Travis Scott 등)",
    "release_year": "출시 연도",
    "confidence": "인식 확신도 (high/medium/low)"
}

품번을 모르겠으면 가장 가능성 높은 품번을 적어주세요. JSON만 출력하세요."""

    response = httpx.post(
        'https://api.openai.com/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        json={
            'model': 'gpt-4o',
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {
                            'type': 'image_url',
                            'image_url': {
                                'url': f'data:{media_type};base64,{base64_image}'
                            }
                        }
                    ]
                }
            ],
            'max_tokens': 500,
            'temperature': 0.1
        },
        timeout=30.0
    )

    if response.status_code != 200:
        return {"error": f"OpenAI API 오류: {response.status_code} - {response.text}"}

    result_text = response.json()['choices'][0]['message']['content']
    # JSON 파싱
    try:
        # 코드 블록 안에 있을 수 있으니 정리
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "error": "JSON 파싱 실패"}


def identify_sneaker_anthropic(image_path: str) -> dict:
    """Anthropic Claude를 사용하여 스니커즈 식별"""
    api_key = get_anthropic_key()
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY가 설정되지 않았습니다."}

    base64_image = encode_image_to_base64(image_path)
    media_type = get_image_media_type(image_path)

    prompt = """이 스니커즈 사진을 분석해 주세요. 반드시 아래 JSON 형식으로만 응답해 주세요:

{
    "brand": "브랜드명 (Nike, Adidas, New Balance 등)",
    "model_name": "정식 모델명 (예: Air Jordan 1 Retro High OG)",
    "style_code": "품번/스타일 코드 (예: DD1391-100)",
    "colorway": "컬러웨이 (예: White/Black-University Red)",
    "nickname": "별명이 있다면 (예: Chicago, Travis Scott 등)",
    "release_year": "출시 연도",
    "confidence": "인식 확신도 (high/medium/low)"
}

품번을 모르겠으면 가장 가능성 높은 품번을 적어주세요. JSON만 출력하세요."""

    response = httpx.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01'
        },
        json={
            'model': 'claude-sonnet-4-20250514',
            'max_tokens': 500,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'image',
                            'source': {
                                'type': 'base64',
                                'media_type': media_type,
                                'data': base64_image
                            }
                        },
                        {'type': 'text', 'text': prompt}
                    ]
                }
            ]
        },
        timeout=30.0
    )

    if response.status_code != 200:
        return {"error": f"Anthropic API 오류: {response.status_code} - {response.text}"}

    result_text = response.json()['content'][0]['text']
    try:
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw_response": result_text, "error": "JSON 파싱 실패"}


def identify_sneaker(image_path: str) -> dict:
    """메인 식별 함수 - 설정된 API 키에 따라 적절한 모델 선택"""
    if get_openai_key():
        return identify_sneaker_openai(image_path)
    elif get_anthropic_key():
        return identify_sneaker_anthropic(image_path)
    else:
        # 데모용 목업 응답
        return {
            "brand": "Nike",
            "model_name": "Air Jordan 1 Retro High OG",
            "style_code": "DD1391-100",
            "colorway": "White/Black-University Red",
            "nickname": "Chicago",
            "release_year": "2015",
            "confidence": "demo_mode",
            "note": "API 키 미설정 - 데모 데이터 반환"
        }


def lookup_sneaker_by_code(style_code: str) -> dict:
    """
    OpenAI GPT-4o를 사용하여 품번으로 스니커즈 정보 조회
    DB에 없는 품번을 AI 지식으로 식별
    """
    api_key = get_openai_key()
    if not api_key:
        return {"error": "OPENAI_API_KEY가 설정되지 않았습니다."}

    prompt = f"""스니커즈 품번(스타일코드) "{style_code}"에 대해 알려주세요.
반드시 아래 JSON 형식으로만 응답해 주세요:

{{
    "brand": "브랜드명",
    "model_name": "정식 모델명",
    "style_code": "{style_code}",
    "colorway": "컬러웨이",
    "nickname": "별명 (있다면)",
    "release_year": "출시 연도",
    "retail_price": 출시가(USD 숫자),
    "confidence": "인식 확신도 (high/medium/low)"
}}

이 품번을 모르겠으면 {{"error": "알 수 없는 품번입니다"}}로 응답해주세요.
JSON만 출력하세요."""

    try:
        response = httpx.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'model': 'gpt-4o',
                'messages': [
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 300,
                'temperature': 0.1
            },
            timeout=15.0
        )

        if response.status_code != 200:
            return {"error": f"OpenAI API 오류: {response.status_code}"}

        result_text = response.json()['choices'][0]['message']['content']
        cleaned = result_text.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1]
            cleaned = cleaned.rsplit('```', 1)[0]

        result = json.loads(cleaned)
        return result

    except (json.JSONDecodeError, Exception) as e:
        return {"error": f"품번 조회 실패: {str(e)}"}
