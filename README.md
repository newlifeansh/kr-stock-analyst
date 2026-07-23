# 국내주식 애널리스트 백엔드

국내주식 분석용 데이터를 먼저 쌓고, `증권사 리포트 + 공시·IR + 뉴스`를 한 화면에서 보는 1차 인사이트 앱까지 붙인 프로젝트입니다.

## 현재 포함된 것

- `FastAPI` API 서버
- 반응형 인사이트 화면 (`/insight`, `/insight/desktop`, `/insight/mobile`)
- `SQLAlchemy` 기반 DB 모델
- 기본 `SQLite` 저장소, 추후 PostgreSQL 전환 가능
- 홈 브리핑 스냅샷 저장 구조
- 실시간 브리핑 폴러 (`KIS REST polling`)
- KRX/pykrx 기반 종목, 일별 가격, 투자자별 수급 수집 CLI
- DART 공시·IR 수집기
- 네이버 금융 뉴스 수집기
- 네이버 금융 리서치 리포트 수집기
- Open DART 재무제표 수집 뼈대
- 한국은행 ECOS 시계열 수집 뼈대

## 빠른 시작

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
analyst init-db
uvicorn app.main:app --reload
```

API 확인:

- `GET http://127.0.0.1:8000/health`
- `GET http://127.0.0.1:8000/briefings/status`
- `GET http://127.0.0.1:8000/briefings/latest`
- `GET http://127.0.0.1:8000/insight`
- `GET http://127.0.0.1:8000/insight/feed`
- `GET http://127.0.0.1:8000/meta/insight-cadence`
- `GET http://127.0.0.1:8000/meta/research-sources`
- `GET http://127.0.0.1:8000/meta/integrations`
- `GET http://127.0.0.1:8000/toss/status`
- `GET http://127.0.0.1:8000/toss/accounts`
- `GET http://127.0.0.1:8000/toss/holdings`
- `GET http://127.0.0.1:8000/toss/orders`
- `GET http://127.0.0.1:8000/research-reports`
- `GET http://127.0.0.1:8000/disclosures`
- `GET http://127.0.0.1:8000/news-items`
- `GET http://127.0.0.1:8000/stocks`
- `GET http://127.0.0.1:8000/ingestions`
- `POST/GET http://127.0.0.1:8000/mcp/`

## 로컬 AI 분석

종목 상세의 핵심 요약은 Ollama를 통해 Mac 안에서 생성할 수 있습니다. 가격 기준, 매매 전략, 위험 판단은 기존 데이터 계산 엔진이 유지하고, 로컬 모델은 검증된 근거를 초보자가 읽기 쉬운 한 문장으로 정리합니다. 모델이 만들지 않은 숫자를 추가하면 해당 결과를 버리고 데이터 분석으로 자동 전환합니다.

M1 8GB 기준 권장 모델:

```bash
brew install ollama
ollama pull qwen3:0.6b
```

`.env` 설정:

```dotenv
STOCK_AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:0.6b
OLLAMA_TIMEOUT_SECONDS=60
OLLAMA_CACHE_SECONDS=900
```

서버 실행 후 `GET /stocks/005930/ai-analysis` 응답의 `generation_mode`가 `local_llm`이면 로컬 AI가 적용된 상태입니다. Ollama가 꺼져 있거나 시간 제한을 넘기면 API는 실패하지 않고 기존 데이터 분석 결과를 반환합니다. Railway 같은 원격 서버에서는 로컬 Mac의 Ollama에 접근할 수 없으므로 `STOCK_AI_PROVIDER=rules`를 사용합니다.

## PlayMCP / Remote MCP

이 프로젝트는 이제 `PlayMCP`에 등록할 수 있는 read-only Remote MCP 엔드포인트를 함께 제공합니다.

- 메인 앱 endpoint: `https://your-domain/mcp/`
- 전용 MCP 앱 endpoint: `https://your-mcp-domain/`
- 기본 transport: `Streamable HTTP`
- 주요 도구:
  - `get_market_briefing`
  - `search_korea_stocks`
  - `get_korea_stock_dashboard`
  - `list_research_reports`
  - `list_disclosures`
  - `list_news_items`
  - `get_company_briefs`
  - `get_market_rankings`
  - `get_market_recommendations`
  - `get_market_impact`

로컬 검증:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[mcp]"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

PlayMCP 등록 전 체크:

1. 공개 HTTPS 주소 준비
2. `MCP_PUBLIC_BASE_URL`에 서비스 주소 설정
3. `MCP_ALLOWED_HOSTS`에 실제 배포 도메인 추가
4. `MCP_ALLOWED_ORIGINS`에 `https://playmcp.kakao.com` 유지
5. 등록 endpoint를 하나로 고정
   - 메인 앱을 쓸 때: `https://your-domain/mcp/`
   - 전용 MCP 앱을 쓸 때: `https://your-mcp-domain/`
6. 등록 직전 `analyst verify-mcp-endpoint --url ...` 로 응답 검증

참고:

- 현재 기본값은 로컬 테스트를 위해 `127.0.0.1:*`, `localhost:*`를 허용합니다.
- 운영 배포에서는 `MCP_ALLOWED_HOSTS`를 실제 도메인으로 바꾸는 것이 좋습니다.
- `BOOTSTRAP_ON_START=true`이면 빈 DB에서도 종목 마스터와 브리핑을 자동으로 채우려고 시도합니다.
- `analyst bootstrap-runtime --force-refresh`로 수동 초기 적재도 가능합니다.

PlayMCP 제출용으로는 전용 루트 MCP 앱을 따로 띄우는 편이 더 깔끔합니다.

```bash
source .venv/bin/activate
uvicorn app.mcp_app:app --host 0.0.0.0 --port 8002
```

이 경우 등록 endpoint는 `https://your-mcp-domain/` 입니다.  
메인 대시보드와 같은 앱에 붙일 때는 `https://your-domain/mcp/` 도 사용할 수 있지만, 제출용은 전용 루트 앱이 더 안전합니다.

전용 MCP 앱에는 배포 확인용 헬스체크가 함께 있습니다.

- `GET https://your-mcp-domain/health`
- `GET https://your-mcp-domain/healthz`
- `GET https://your-mcp-domain/readyz`

배포 전용 Docker 예시:

```bash
docker build -t kr-stock-analyst .
docker run --rm -p 8002:8000 \
  -e APP_MODULE=app.mcp_app:app \
  -e MCP_PUBLIC_BASE_URL=https://your-mcp-domain \
  -e MCP_ALLOWED_HOSTS=your-mcp-domain \
  -e MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com \
  kr-stock-analyst
```

배포 후 PlayMCP 등록 전에 smoke test:

```bash
source .venv/bin/activate
analyst verify-mcp-endpoint --url https://your-mcp-domain/
```

등록할 때 바로 넣을 문구와 체크리스트는 [docs/playmcp-registration-checklist.md](/Users/sukhwan/Documents/주식애널리스트%20보고서/docs/playmcp-registration-checklist.md) 에 정리해두었습니다.

Railway에 바로 올릴 계획이면 저장소 루트의 [railway.json](/Users/sukhwan/Documents/주식애널리스트%20보고서/railway.json) 을 그대로 사용할 수 있습니다.

- healthcheck: `/healthz`
- Docker builder: `Dockerfile`
- 재시작 정책: `ON_FAILURE`
- 권장 DB: Railway Postgres (`DATABASE_URL=${{Postgres.DATABASE_URL}}`)

또한 원격 Docker 빌드에 로컬 DB와 스크린샷 파일이 섞이지 않도록 [.dockerignore](/Users/sukhwan/Documents/주식애널리스트%20보고서/.dockerignore) 도 포함했습니다.

Railway 변수 붙여넣기용 env 블록은 현재 `.env` 를 바탕으로 바로 생성할 수 있습니다.

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref
```

민감정보를 가린 미리보기:

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref \
  --redact-secrets
```

파일로 저장하려면:

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref \
  --output .railway.env
```

배포 준비 상태를 한 번에 점검하려면:

```bash
source .venv/bin/activate
analyst check-railway-readiness \
  --public-base-url https://your-mcp-domain
```

Git remote 가 없어도 Railway CLI는 현재 디렉터리의 로컬 소스를 바로 배포할 수 있습니다.  
로컬 배포 흐름은 [docs/railway-local-deploy-runbook.md](/Users/sukhwan/Documents/주식애널리스트%20보고서/docs/railway-local-deploy-runbook.md) 에 정리해두었습니다.

`railway up` 업로드를 가볍게 유지하려고 [.railwayignore](/Users/sukhwan/Documents/주식애널리스트%20보고서/.railwayignore) 도 포함했습니다.  
로컬 DB, 테스트 파일, 임시 스크린샷은 Railway 업로드 대상에서 제외됩니다.

로그인 뒤 앱 서비스 생성, Postgres 추가, 도메인 생성, 변수 주입, 재배포까지 한 번에 돌리려면:

```bash
./scripts/railway_bootstrap_after_login.sh
```

기본값:

- `PROJECT_NAME=kr-stock-analyst`
- `APP_SERVICE=insight-mcp`
- `SOURCE_ENV=.env`

예시:

```bash
PROJECT_NAME=kr-stock-analyst \
APP_SERVICE=insight-mcp \
./scripts/railway_bootstrap_after_login.sh
```

## 데이터 수집 예시

```bash
# 기준일 종목 마스터 수집
analyst collect-stocks --date 20260617 --markets KOSPI,KOSDAQ

# 특정일 전종목 가격/시총 수집
analyst collect-prices --date 20260617 --market KOSPI

# 특정일 투자자별 수급 수집
analyst collect-investor-flows --date 20260617 --market KOSPI

# 특정 종목 기간 가격 수집
analyst collect-stock-prices --code 005930 --from-date 20260101 --to-date 20260617

# 홈 브리핑 스냅샷 수집
analyst collect-home-briefing

# 증권사 리포트 메타데이터 수집
analyst collect-research-reports --max-pages 2 --days-back 3

# 공시·IR 수집
analyst collect-disclosures --days-back 7 --page-count 100

# 뉴스 수집
analyst collect-news-items --categories breaking,market,company --max-pages 2 --days-back 3

# 토스 계좌/보유/주문 캐시 동기화
analyst toss-sync-accounts
analyst toss-sync-holdings
analyst toss-sync-orders --status OPEN
```

## API 키

Open DART와 ECOS는 API 키가 필요합니다. `.env`에 값을 넣으면 수집기에서 사용합니다.

공시는 `DART_API_KEY`가 없어도 DART 공식 웹의 `오늘의 공시`를 fallback으로 수집합니다. API 키가 있으면 Open DART API를 우선 사용하고, 키가 비어 있거나 아직 활성화되지 않아 API가 실패하면 웹 fallback으로 최신 공시를 계속 누적합니다.

실시간 홈 브리핑은 한국투자 Open API 키가 있으면 현재가/상승하락/거래대금 브리핑을 폴링으로 수집합니다.

```dotenv
DART_API_KEY=...
ECOS_API_KEY=...
KIS_APP_KEY=...
KIS_APP_SECRET=...
BRIEFING_REALTIME_ENABLED=true
BRIEFING_POLL_SECONDS=30
RESEARCH_ENABLED=true
RESEARCH_POLL_SECONDS=600
DISCLOSURE_ENABLED=true
DISCLOSURE_POLL_SECONDS=300
NEWS_ENABLED=true
NEWS_POLL_SECONDS=300
BOOTSTRAP_ON_START=true
MCP_ENABLED=true
MCP_PUBLIC_BASE_URL=https://your-domain
MCP_ALLOWED_HOSTS=your-domain,127.0.0.1:*,localhost:*
MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com
TOSS_ENABLED=false
TOSS_BASE_URL=https://openapi.tossinvest.com
TOSS_CLIENT_ID=...
TOSS_CLIENT_SECRET=...
TOSS_ACCOUNT_NO=...
TOSS_ACCOUNT_SEQ=...
TOSS_POLL_SECONDS=60
TOSS_ORDER_POLL_SECONDS=300
```

## 1차 인사이트 구조

리포트, 공시·IR, 뉴스, 홈 브리핑을 아래 단위로 저장합니다.

- `briefing_snapshot`: 한 시점의 브리핑 헤더
- `briefing_metric`: 장 상태 같은 상단 카드성 정보
- `briefing_quote`: 브리핑 대상 주요 종목 현재가
- `briefing_mover`: 상승, 하락, 거래대금 상위
- `briefing_event`: 리포트, 공시, 뉴스 요약 이벤트
- `research_report`: 증권사 리포트 메타데이터 원장
- `disclosure_item`: DART 공시·IR 원장
- `news_item`: 뉴스 원장

현재는 실시간 공급자를 `KIS REST polling`으로 두었고, 공시·IR은 `DART`, 리포트와 뉴스는 `네이버 금융` 공개 페이지를 기준으로 누적합니다.

이와 별도로, `/meta/*` 엔드포인트에는 현재 백엔드가 따르는 인사이트 운영 기준과 소스 레지스트리를 담았습니다.

- `/meta/insight-cadence`: 단기/중기/장기 인사이트 시간축과 장중/일간/주간/월간/분기 루프
- `/meta/research-sources`: 무료 공개 리포트 소스와 현재 수집기 연결 여부
- `/meta/integrations`: KIS, DART, Naver Finance, Toss Securities 연동 역할과 설정 상태

토스증권 연동은 이제 단순 메타 정보가 아니라 실제 백엔드 기능으로 연결되어 있습니다.

- OAuth2 client credentials 인증
- 계좌 목록 조회 및 캐시
- 보유 종목 조회 및 캐시
- OPEN 주문 목록 조회 및 캐시
- 주문 상세 조회
- 주문 생성 / 정정 / 취소
- 매수 가능 금액 조회
- 매도 가능 수량 조회
- 종목 기본 정보 조회

## 증권사 리포트

증권사 리포트는 공식 오픈 API가 드물어서, 현재는 네이버 금융 리서치 공개 페이지에서 메타데이터를 수집합니다.

- 저장 항목: 카테고리, 제목, 종목명, 종목코드, 증권사, 작성일, 조회수, 상세 링크, PDF 링크
- 회사 리포트(`company`)는 상세 페이지에서 `목표가`, `투자의견`도 추가 수집
- 원문 전문 텍스트는 저장하지 않고, 메타데이터와 링크 중심으로 관리

수집된 리포트는 `/research-reports`에서 바로 조회할 수 있고, 홈 브리핑 스냅샷과 `/insight` 화면에도 최신 리포트가 같이 포함됩니다.

## 공시·IR

공시·IR은 Open DART `list.json`을 이용해 최근 공시를 적재합니다.

- 저장 항목: 회사명, 종목코드, 공시명, 접수번호, 제출자, 비고, 공시 URL, 접수일
- 분류: 공시목록, 실적속보, 기업설명회, 내부자거래, 대량보유자거래, 배당, 자사주, 공급계약, 시설투자, 유상증자, 사업보고서

수집된 공시는 `/disclosures`에서 조회할 수 있습니다.

## 뉴스

뉴스는 네이버 금융 뉴스 공개 리스트를 기준으로 적재합니다.

- 저장 항목: 카테고리, 제목, 요약, 언론사, 이미지 링크, 기사 링크, 작성시각
- 카테고리: 실시간속보, 시황, 기업·종목, 해외증시, 채권·선물, 공시메모, 환율

수집된 뉴스는 `/news-items`에서 조회할 수 있습니다.

## 인사이트를 얻는 주기와 방식

이번 구조에서는 `조회 주기`와 `판단 주기`를 분리해서 운용합니다.

- `1분`: 보유 종목, 급등락, 거래대금 상위, 공시/뉴스 경보
- `5분`: 관심 종목 묶음 스캔과 재정렬
- `일간`: 장 마감 후 요약
- `주간`: 단기 시그널 재계산
- `월간`: 거시/업종/컨센서스 점검
- `분기`: 실적 시즌 기준 투자 논리 재검증

예측 시간축은 아래처럼 나눕니다.

- `2~8주`: 단기 상대수익과 이벤트 추적
- `6~18개월`: 실적 기대 변화와 업황 방향
- `3~5년`: 장기 가치와 사업 구조

상세 기준은 [docs/insight_foundation.md](/Users/sukhwan/Documents/주식애널리스트%20보고서/docs/insight_foundation.md)와 `/meta/insight-cadence`에 정리되어 있습니다.

## 무료 리포트 받는 곳

현재 실제 수집기는 `네이버 금융 리서치`를 사용합니다. 다만 무료 공개 리포트 소스 후보는 이보다 넓게 관리합니다.

- 활성 수집 소스: `Naver Finance Research`
- 후보 소스: `Hankyung Korea Market Consensus`, `Hana`, `Korea Investment`, `Samsung`, `Mirae Asset`, `Kiwoom`, `Daishin`, `Eugene`, `Hanwha`, `IBK`, `Hyundai Motor`, `iM Securities`

핵심은 `공개 페이지`와 `안정적인 수집기`를 같은 것으로 보지 않는 것입니다. 그래서 소스 레지스트리에는 `is_active_collector`를 따로 두었습니다.

## 토스증권 연동 방향

토스증권은 이 프로젝트에서 `리포트/뉴스/공시 수집원`이 아니라 `브로커 연동 레이어`입니다.

- 잘 맞는 역할: 계좌, 보유 종목, 주문 가능 수량, 주문, 주문 상태, 시세, 환율, 시장 캘린더
- 잘 맞지 않는 역할: 증권사 리포트, 뉴스, 컨센서스 히스토리, DART 공시 대체

현재 구현 범위는 `계좌/보유/주문/매수가능금액/매도가능수량/종목조회`까지입니다. 다만 실거래 호출 검증은 실제 `TOSS_CLIENT_ID`, `TOSS_CLIENT_SECRET`, 그리고 계좌 식별용 `TOSS_ACCOUNT_SEQ` 또는 `TOSS_ACCOUNT_NO`가 있어야 합니다.

자주 쓰는 엔드포인트 예시는 이렇습니다.

- `GET /toss/accounts/live`
- `POST /toss/sync/accounts`
- `GET /toss/holdings/live?account_seq=1`
- `POST /toss/sync/holdings?account_seq=1`
- `GET /toss/orders/live?account_seq=1&status=OPEN`
- `POST /toss/orders`
- `POST /toss/orders/{order_id}/modify`
- `POST /toss/orders/{order_id}/cancel`
- `GET /toss/buying-power?account_seq=1&currency=KRW`
- `GET /toss/sellable-quantity?account_seq=1&symbol=005930`
- `GET /toss/stocks?symbols=005930,000660`

## 데이터 설계 방향

첫 단계는 아래 데이터를 안정적으로 누적하는 것입니다.

- 종목 마스터: 종목코드, 이름, 시장, 기준일
- 가격/거래: OHLCV, 거래대금, 시가총액, 상장주식수
- 수급: 개인/외국인/기관 등 투자자별 매수, 매도, 순매수
- 재무: DART 계정별 금액
- 매크로: 금리, 환율, 수출, 물가 등 시계열

이후 컨센서스, 산업 KPI, 뉴스/공시 텍스트, 리포트 데이터를 추가하면 됩니다.
