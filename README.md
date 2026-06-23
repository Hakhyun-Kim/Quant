# 📈 KOSDAQ Quant Screener & Backtester
> 한국 주식 시장(코스닥)의 종목 데이터를 사용하여 사용자가 임의로 지정한 재무/밸류에이션 조건으로 종목을 스크리닝하고, 과거 성과를 정밀하게 시뮬레이션할 수 있는 분석용 퀀트 백테스터(Quant Backtester)입니다.

---

## ✨ 주요 기능 (Key Features)

1. **📊 조건별 종목 스크리너 (Screener)**
   - 주가매출비율(PSR), 부채비율, 연속 흑자 분기 수 등 사용자가 정의한 필터 규칙을 적용하여 실시간으로 조건을 충족하는 코스닥 종목 목록 탐색.
   - 선별된 종목 목록 테이블 시각화 및 데이터 추출(CSV 다운로드) 기능 지원.

2. **📈 성과 분석 백테스터 (Backtester)**
   - 리밸런싱 주기(월별, 분기별, 반기별, 연도별), 포트폴리오 편입 종목 수, 투자 기간 및 투자 원금 설정 기능 제공.
   - 사용자가 정의한 조건으로 리밸런싱을 시뮬레이션한 가상의 수익률 곡선과 코스닥 지수(Benchmark) 수익률을 **Plotly 대화형 차트**로 비교 시각화.
   - 시뮬레이션 기간 동안 발생한 과거 포트폴리오 매수/매도 세부 거래 기록(로그) 및 최종 평가 가치 정보 산출.
   - 연평균 복리수익률(CAGR), 최대 낙폭(MDD), 샤프 지수(Sharpe Ratio) 등 과거 성과 지표 자동 연산.

3. **⚙️ 데이터 캐시 관리 엔진 (Data Manager)**
   - FinanceDataReader 및 네이버 금융 기반의 전 종목 종가 및 재무제표 수집 엔진.
   - 비동기 멀티스레드(ThreadPoolExecutor) 병렬 수집에 비차단 셧다운 방식(`shutdown(wait=False)`)과 타임아웃을 적용하여 안정적으로 금융 데이터를 로컬 파일(`data/`)에 압축 캐싱.
   - 데이터 수집 진척률을 대시보드 화면상에 실시간 프로그레스 바(Progress Bar)로 연동 시각화.

---

## 🛠️ 설치 및 실행 방법 (Installation & Run)

### 1. Repository Clone
```bash
git clone https://github.com/Hakhyun-Kim/Quant.git
cd Quant
```

### 2. 패키지 설치 (Install Dependencies)
```bash
pip install -r requirements.txt
```

### 3. 대시보드 애플리케이션 실행 (Run App)
```bash
python -m streamlit run app.py
```
실행이 완료되면 자동으로 웹 브라우저 창(`http://localhost:8501`)이 열리며 분석을 시작할 수 있습니다.

---

## 📂 프로젝트 구조 (Project Structure)
```directory
Quant/
│
├── app.py             # Streamlit 기반 대시보드 UI 및 조건 설정 화면
├── backtester.py      # 포트폴리오 스크리닝 및 백테스트 실행 시뮬레이터 핵심 로직
├── data_collector.py  # 금융 정보 수집, 멀티스레드 웹 크롤러 및 로컬 캐싱 모듈
├── requirements.txt   # 라이브러리 의존성 파일
├── .gitignore         # 용량이 큰 캐시 데이터(data/) 및 가상환경 제외 설정
└── README.md          # 프로젝트 설명서 (현재 파일)
```
