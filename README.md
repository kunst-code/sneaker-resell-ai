# 👟 SneakerAI - 스니커즈 리셀 AI 투자 분석 플랫폼

스니커즈 사진 한 장으로 리셀 투자 가치를 분석하는 AI 기반 MVP 데모 프로그램입니다.

## 🏗️ 아키텍처

```
[이미지 업로드] → [비전 AI 인식] → [시세 DB 조회] → [시계열 예측] → [LLM 추천 리포트]
```

## 📂 프로젝트 구조

```
sneaker-resell-ai/
├── frontend/               # HTML/CSS/JS 프론트엔드
│   ├── index.html         # 메인 페이지
│   ├── css/style.css      # 스타일
│   └── js/app.js          # 프론트엔드 로직
├── backend/               # Python Flask 백엔드
│   ├── app.py            # 메인 서버
│   ├── routes/           # API 라우트
│   │   ├── vision.py    # 이미지 인식 API
│   │   ├── price.py     # 가격 조회 API
│   │   ├── forecast.py  # 가격 예측 API
│   │   └── recommend.py # 종합 추천 API
│   ├── services/         # 비즈니스 로직
│   │   ├── vision_service.py    # GPT-4o/Claude 비전
│   │   ├── price_service.py     # 시세 조회
│   │   ├── forecast_service.py  # Prophet 예측
│   │   └── recommend_service.py # LLM 추천
│   ├── db/
│   │   └── database.py   # SQLite 스키마/초기화
│   └── uploads/           # 업로드 이미지 저장
├── data/                  # SQLite DB 파일 (자동 생성)
├── .env.example           # 환경변수 템플릿
├── requirements.txt       # Python 패키지
└── README.md
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
cd sneaker-resell-ai

# 가상환경 생성 (권장)
python3 -m venv venv
source venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에 API 키 입력 (선택사항 - 없어도 데모 모드 동작)
```

### 2. 서버 실행

```bash
cd backend
python app.py
```

### 3. 브라우저에서 접속

```
http://localhost:5000
```

## 🔑 API 키 (선택사항)

| 서비스 | 용도 | 없을 때 |
|--------|------|---------|
| OpenAI API | 스니커즈 이미지 인식 (GPT-4o) | 데모 데이터 반환 |
| Anthropic API | Claude 비전 + 추천 리포트 | 데모 데이터 반환 |
| RapidAPI | StockX 실시간 시세 조회 | 로컬 DB 샘플 데이터 |

> ⚡ **API 키 없이도 모든 기능이 데모 모드로 동작합니다!**

## 🛠️ 기술 스택

- **Frontend**: HTML5 + CSS3 + Vanilla JavaScript + Chart.js
- **Backend**: Python Flask
- **Database**: SQLite (로컬)
- **AI/ML**: OpenAI GPT-4o, Anthropic Claude, Prophet (시계열 예측)
- **API**: RapidAPI (Sneaker Database)

## 📡 API 엔드포인트

| Method | Endpoint | 설명 |
|--------|----------|------|
| POST | `/api/vision/identify` | 이미지 업로드 → 스니커즈 식별 |
| GET | `/api/price/search?style_code=XX` | 품번으로 시세 조회 |
| GET | `/api/forecast/predict?style_code=XX` | 가격 예측 |
| POST | `/api/recommend/analyze` | 이미지 → 전체 파이프라인 분석 |
| POST | `/api/recommend/analyze-by-code` | 품번 → 전체 파이프라인 분석 |

## 🎯 핵심 기능

1. **비전 AI 인식** - 사진에서 브랜드, 모델명, 품번 자동 식별
2. **실시간 시세** - KREAM/StockX 가격 비교 및 차액 분석
3. **가격 예측** - Prophet 시계열 모델로 30일 후 가격 예측
4. **AI 추천** - LLM이 BUY/SELL/HOLD 투자 리포트 자동 생성
5. **차익 거래** - 해외-국내 플랫폼 간 마진 기회 분석
