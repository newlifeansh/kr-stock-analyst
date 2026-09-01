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

## 스테이징 GPT 문구 정리

`app.staging_app:app`으로 실행하는 스테이징에서는 종목 대응 상세와 종목 추천 상세의 제목·요약·다음 확인 문구만 GPT-4o mini로 정리할 수 있습니다. 점수, 가격, 추천 순위, AI 매매 시그널과 중대 위험 차단은 기존 규칙 엔진이 계속 결정합니다. Structured Outputs 스키마 검증, 원문에 없는 숫자 검사, 직접 매수·매도 지시 차단 중 하나라도 실패하면 현재 데이터 문구를 그대로 표시합니다. 프로덕션 엔트리포인트인 `app.main:app`에는 이 API와 UI가 주입되지 않습니다.

Railway staging 환경 변수:

```dotenv
OPENAI_API_KEY=...
STAGING_OPENAI_SUMMARY_ENABLED=true
STAGING_OPENAI_MODEL=gpt-4o-mini-2024-07-18
STAGING_OPENAI_TIMEOUT_SECONDS=8
STAGING_OPENAI_CACHE_SECONDS=1800
```

키가 없거나 기능을 끄면 `/staging-ai/page-summary`는 HTTP 오류 대신 `generation_mode=rules`와 검증된 폴백 문구를 반환합니다. 동일한 입력은 브라우저와 서버에서 30분간 재사용하며, 공개 엔드포인트는 클라이언트당 분당 15회·전체 분당 120회로 제한합니다.

GPT-4o mini 공식 단가는 입력 100만 토큰당 `$0.15`, 캐시 입력 `$0.075`, 출력 `$0.60`입니다. 한 화면당 입력 1,200토큰·출력 180토큰을 보수적으로 잡으면 약 `$0.000288`, 캐시되지 않은 1만 화면은 약 `$2.88`입니다. 실제 비용은 응답의 `input_tokens`, `output_tokens`, `estimated_cost_usd`로 확인합니다.

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

대시보드 요청과 외부 데이터 수집을 분리하려면 같은 소스와 같은 Postgres를 쓰는 서비스 두 개를 둡니다.

- 두 서비스 공통: `APP_MODULE=app.main:app`
- 공개 웹 서비스: `PROCESS_ROLE=web` (도메인과 healthcheck 연결)
- 비공개 수집 서비스: `PROCESS_ROLE=collector` (외부 수집, 완성 스냅샷 갱신, 알림 담당)
- 로컬 단일 프로세스: `PROCESS_ROLE=all` (기존 동작 유지)

두 서비스를 전환하기 전에 조회 순서 인덱스를 한 번 적용합니다. 명령은 재실행해도 안전합니다.

```bash
analyst migrate-performance-indexes --dry-run
analyst migrate-performance-indexes
```

웹 프로세스는 마지막으로 검증된 완성 스냅샷을 우선 읽고, 오래된 스냅샷은 DB 큐에 갱신 요청을 남깁니다. 단, 처음 보는 종목의 안정 상세 요청(`include_profile=0&include_live=0`)은 외부 호출 없이 DB 자료로 화면을 먼저 만들고 완성본 수집을 큐에 맡깁니다. 이 준비 중 응답은 캐시하지 않으며 클라이언트가 완성본을 백그라운드에서 다시 받아 화면을 갱신합니다. 수집 프로세스가 갱신에 실패해도 기존 완전본은 지워지지 않습니다.

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

# 알파스퀘어 종목 로고를 운영 DB에 캐싱
analyst sync-stock-logos --markets KOSPI,KOSDAQ

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

```

## 데이터 연동·시그널 QA

기계 판독 가능한 원본은 `app/qa/data_signal_cases.json`, 사람이 읽는 생성 문서는
`docs/qa/data-signal-qa-matrix.md`입니다. 현재 기준 전략은
`position-lifecycle-v7.3`입니다.

```bash
# PR/배포용 고정 픽스처·계약·경계값 검사
pytest -q --junitxml=artifacts/qa-data-signal/pytest.xml
analyst qa data-signal --mode gate \
  --pytest-junit artifacts/qa-data-signal/pytest.xml \
  --output artifacts/qa-data-signal/gate.json

# 스테이징 API와 외부 원천의 읽기 전용 실연동 검사
analyst qa data-signal --mode live \
  --base-url https://dark-theme-preview-staging.up.railway.app \
  --output artifacts/qa-data-signal/live.json

# KIS 자격증명이 있는 환경에서 원천 REST/OAuth도 직접 검사
analyst qa data-signal --mode live --direct-kis \
  --base-url https://dark-theme-preview-staging.up.railway.app

# 모바일 다크·라이트 브라우저 검사와 실패 스크린샷
playwright install chromium
analyst qa data-signal --mode e2e \
  --base-url https://dark-theme-preview-staging.up.railway.app \
  --output artifacts/qa-data-signal/e2e.json

# 카탈로그에서 Markdown 명세 재생성
analyst qa render-catalog --output docs/qa/data-signal-qa-matrix.md
```

보고서에는 실행 환경·장 상태·기준 시각, 각 QA ID의 상태와 증거, P0 실패 및
`deployment_blocked`가 포함됩니다. 인증정보는 보고서에 기록하지 않습니다. GitHub
Actions는 PR마다 `gate`, 평일 KST 08:20·10:00·16:20에 `live`, 스테이징
배포 성공 뒤 `e2e`를 실행합니다.

### Railway 스테이징 → 프로덕션 승격

`main` 푸시 또는 수동 실행은 `.github/workflows/deploy-staging-production.yml`의
단일 파이프라인을 사용합니다. 실행 순서는 `gate → staging 배포 → staging
release-parity/live/e2e → production 승인·배포 → staging-production parity`이며,
어느 단계든 실패하면 뒤 단계는 실행되지 않습니다. 모든 배포 job은 명시적으로
`${{ github.sha }}`를 checkout하므로 같은 커밋만 승격합니다.

GitHub 저장소에는 다음 설정이 필요합니다.

- Repository variables: `STAGING_RAILWAY_PROJECT_ID`, `STAGING_RAILWAY_SERVICE`,
  `PRODUCTION_RAILWAY_PROJECT_ID`, `PRODUCTION_RAILWAY_SERVICE`,
  `STAGING_BASE_URL`, `PRODUCTION_BASE_URL`
- GitHub environments: `staging`, `production`
- 각 environment secret: 해당 Railway 환경에 제한된 `RAILWAY_TOKEN`
- `production` environment: required reviewer를 지정해 사람 승인 후에만 승격
- 선택적 staging QA secret: `DASHBOARD_INVITE_CODE`, `KIS_APP_KEY`,
  `KIS_APP_SECRET`, `DART_API_KEY`

프로덕션 배포 전에는 현재 체크아웃과 스테이징의 `/dashboard-version` 및 버전 지정
CSS·JavaScript URL이 일치해야 합니다. 배포 후에는 같은 검사를 스테이징과
프로덕션에 다시 적용합니다.

## API 키

Open DART와 ECOS는 API 키가 필요합니다. `.env`에 값을 넣으면 수집기에서 사용합니다.

공시는 `DART_API_KEY`가 없어도 DART 공식 웹의 `오늘의 공시`를 fallback으로 수집합니다. API 키가 있으면 Open DART API를 우선 사용하고, 키가 비어 있거나 아직 활성화되지 않아 API가 실패하면 웹 fallback으로 최신 공시를 계속 누적합니다.

실시간 시세는 한국투자 Open API 키가 있으면 통합 WebSocket으로 수신합니다. NXT 대상 종목은 오전 8시부터 프리마켓 체결가가 현재가·관심종목·랭킹·1일 차트에 반영되며, AI 시그널 확정 기준은 기존 KRX 정규장을 유지합니다.

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
FUNDAMENTAL_SNAPSHOT_ENABLED=true
FUNDAMENTAL_SNAPSHOT_REFRESH_DAYS=2
MACRO_ENABLED=true
MACRO_POLL_SECONDS=1800
MACRO_RANGE=1y
NEWS_ENABLED=true
NEWS_POLL_SECONDS=300
THREADS_FEED_ENABLED=true
THREADS_ACCESS_TOKEN=...
THREADS_API_BASE_URL=https://graph.threads.net
THREADS_FEED_CACHE_SECONDS=300
THREADS_FEED_TIMEOUT_SECONDS=12
THREADS_FEED_MAX_RESULTS=20
THREADS_FEED_SEARCH_TYPE=RECENT
BOOTSTRAP_ON_START=true
MCP_ENABLED=true
MCP_PUBLIC_BASE_URL=https://your-domain
MCP_ALLOWED_HOSTS=your-domain,127.0.0.1:*,localhost:*
MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com
```

Threads 종목 검색은 Meta 앱의 Threads 사용 사례와 `threads_basic`,
`threads_keyword_search` 권한이 승인된 사용자 액세스 토큰을 사용합니다. 토큰이 없거나
권한 승인이 끝나지 않은 환경에서는 종목별 Threads 공개 검색 링크로 자동 전환됩니다.

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

현재 실시간 공급자는 `KIS 통합 WebSocket(H0UNCNT0)`이고 REST 조회를 장애 시 보조 경로로 사용합니다. 공시·IR은 `DART`, 리포트와 뉴스는 `네이버 금융` 공개 페이지를 기준으로 누적합니다.

이와 별도로, `/meta/*` 엔드포인트에는 현재 백엔드가 따르는 인사이트 운영 기준과 소스 레지스트리를 담았습니다.

- `/meta/insight-cadence`: 단기/중기/장기 인사이트 시간축과 장중/일간/주간/월간/분기 루프
- `/meta/research-sources`: 무료 공개 리포트 소스와 현재 수집기 연결 여부
- `/meta/integrations`: KIS, DART, Naver Finance 연동 역할과 설정 상태
- `/meta/signal-data-quality`: v7 매수 판단에 쓰는 가격·수급·시장지수·실적·리포트·공시의 기준일, 커버리지, 시점 일관성. `probe=true`로 원천 API 읽기 전용 상태 점검을 추가

AI 시그널 매수 판단은 `position-lifecycle-v7.0`부터 가격 조건 뒤에 실적·컨센서스, 시장·섹터 상대강도, 거래대금 정규화 수급을 독립 확인합니다. `position-lifecycle-v7.2`는 2026-08-25부터 1R·1.6R·2.5R에서 30%·25%·15%를 수익확정하고, 0.75R부터 손익분기 보호를 시작하며, 잔여 30%만 추세를 추적합니다. 기존 보유 종목의 전환 매도는 하루 최대 30%로 제한하고, 부분매도 예정 다음 시가가 보호선 아래면 잔여비중을 전량 매도합니다. 한국 시장지수는 Yahoo 종가가 늦을 때 네이버 확정 종가를 출처 구분하여 보완하며, OpenDART 중대 위험 공시와 시장 패닉은 신규매수 차단 조건입니다. 자세한 계약은 `docs/ai-signal-strategy-audit.md`를 참고하세요.

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

- `1분`: 관심 종목, 급등락, 거래대금 상위, 공시/뉴스 경보
- `5분`: 관심 종목 묶음 스캔과 재정렬
- `일간`: 장 마감 후 요약
- `주간`: 단기 시그널 재계산
- `월간`: 거시/업종/컨센서스 점검
- `분기`: 실적 시즌 기준 투자 논리 재검증

웹 푸시의 `추천 업데이트`를 켜면 `WEB_PUSH_RECOMMENDATION_POLL_SECONDS` 주기(기본 600초)로 상위 10 추천을 확인합니다. 최초 확인은 현재 목록을 기준선으로만 저장하고, 이후 상위 10에 새 종목이 들어오거나 기존 추천 종목의 AI 판단이 예비 매수·매수 확정·수익확정·전량 매도 단계로 바뀔 때만 알립니다. 점수와 순위만 달라진 경우에는 알리지 않으며, 알림을 누르면 해당 추천 종목 상세 화면으로 이동합니다.

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

## 데이터 설계 방향

첫 단계는 아래 데이터를 안정적으로 누적하는 것입니다.

- 종목 마스터: 종목코드, 이름, 시장, 기준일
- 가격/거래: OHLCV, 거래대금, 시가총액, 상장주식수
- 수급: 개인/외국인/기관 등 투자자별 매수, 매도, 순매수
- 재무: DART 계정별 금액
- 매크로: 금리, 환율, 수출, 물가 등 시계열

이후 컨센서스, 산업 KPI, 뉴스/공시 텍스트, 리포트 데이터를 추가하면 됩니다.
