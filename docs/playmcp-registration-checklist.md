# PlayMCP 등록 체크리스트

이 문서는 `한국증시 비밀노트` MCP 서버를 `PlayMCP` 개발자 콘솔에 등록할 때 바로 복사해 쓸 수 있는 기준값을 정리한 것입니다.

## 1. 등록 전에 확인할 것

- 공개 HTTPS endpoint 가 실제로 열려 있어야 함
- endpoint 응답이 `initialize`, `tools/list`, `tools/call` 을 정상 처리해야 함
- `MCP_ALLOWED_HOSTS` 에 실제 도메인이 들어 있어야 함
- `MCP_ALLOWED_ORIGINS` 에 `https://playmcp.kakao.com` 이 포함되어 있어야 함

권장 사전 점검:

```bash
source .venv/bin/activate
analyst verify-mcp-endpoint --url https://your-mcp-domain/
```

## 2. 권장 등록 형태

가장 깔끔한 형태는 전용 MCP 앱입니다.

- 배포 앱: `app.mcp_app:app`
- 등록 endpoint: `https://your-mcp-domain/`
- 헬스체크:
  - `https://your-mcp-domain/health`
  - `https://your-mcp-domain/healthz`
  - `https://your-mcp-domain/readyz`

메인 웹앱과 같이 배포할 때는 아래도 가능:

- 배포 앱: `app.main:app`
- 등록 endpoint: `https://your-domain/mcp/`

## 3. 콘솔 입력값 초안

### 서비스명

`한국증시 비밀노트`

### 한 줄 설명

`국내 주식 리포트, 공시, 뉴스, 종목 브리핑을 읽기 전용으로 조회하는 MCP 서버`

### 상세 설명

`한국증시 비밀노트는 증권사 리포트, DART 공시·IR, 뉴스, 종목 브리핑, 시장 영향도를 하나의 읽기 전용 MCP 서버로 제공합니다. 종목명 또는 종목코드 검색, 최신 시장 브리핑, 종목별 대시보드, 시장 랭킹, 추천 흐름을 구조화된 데이터로 조회할 수 있습니다.`

### Endpoint

`https://your-mcp-domain/`

또는

`https://your-domain/mcp/`

## 4. 추천 프롬프트 예시

- `오늘 한국증시에서 중요한 종목과 이벤트를 요약해줘`
- `삼성전자 최신 리포트, 공시, 뉴스 근거를 묶어서 보여줘`
- `최근 공시와 리포트가 함께 나온 종목을 우선순위로 정리해줘`
- `시장 영향도가 큰 외부 변수와 관련 종목을 설명해줘`

## 5. 주요 제공 도구

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

## 6. 배포 환경 변수 예시

```dotenv
APP_MODULE=app.mcp_app:app
MCP_PUBLIC_BASE_URL=https://your-mcp-domain
MCP_ALLOWED_HOSTS=your-mcp-domain
MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com
BOOTSTRAP_ON_START=true
BRIEFING_REALTIME_ENABLED=true
RESEARCH_ENABLED=true
DISCLOSURE_ENABLED=true
NEWS_ENABLED=true
KIS_APP_KEY=...
KIS_APP_SECRET=...
DART_API_KEY=...
```

Railway Raw Editor에 넣을 env 블록은 아래 명령으로 자동 생성할 수 있습니다.

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref
```

## 7. 제출 직전 최소 검증

1. `GET /healthz` 가 `status=ok` 를 반환하는지 확인
2. `GET /readyz` 가 `database_ok=true`, `mcp_server_available=true` 를 반환하는지 확인
3. `analyst verify-mcp-endpoint --url ...` 가 성공하는지 확인
4. `search_korea_stocks` 로 `삼성전자` 검색이 되는지 확인
5. `get_market_briefing` 결과에 리포트/공시/뉴스 묶음이 나오는지 확인
6. 공개 도메인이 바뀌었으면 `MCP_ALLOWED_HOSTS` 를 같이 갱신

## 8. Railway 메모

Railway 공식 문서 기준으로:

- `railway.json` 또는 `railway.toml` 로 배포 설정을 코드에 둘 수 있음
- healthcheck 는 `200` 응답을 받을 때까지 새 배포를 활성화하지 않음
- 서비스는 Railway 가 주입하는 `PORT` 를 리슨해야 함
- 변수는 서비스 변수 또는 shared variable 로 넣을 수 있음

이 저장소에는 아래 파일을 이미 포함했습니다.

- [railway.json](/Users/sukhwan/Documents/주식애널리스트%20보고서/railway.json)
- [.dockerignore](/Users/sukhwan/Documents/주식애널리스트%20보고서/.dockerignore)
