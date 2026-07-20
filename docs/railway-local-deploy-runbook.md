# Railway 로컬 배포 런북

이 프로젝트는 GitHub remote 가 없어도 Railway CLI로 바로 배포할 수 있습니다.

공식 문서 기준:

- `railway login --browserless` 는 브라우저 없이 pairing code 로그인 가능
- `railway init` 으로 새 프로젝트를 만들 수 있음
- `railway up` 은 현재 디렉터리의 로컬 코드를 압축해서 업로드/배포함

## 1. 로그인

```bash
npx -y @railway/cli login --browserless
```

## 2. 준비 상태 확인

```bash
source .venv/bin/activate
analyst check-railway-readiness \
  --public-base-url https://your-mcp-domain
```

## 3. Railway env 블록 생성

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref \
  --output .railway.env
```

민감정보 가린 미리보기:

```bash
source .venv/bin/activate
analyst export-railway-env \
  --public-base-url https://your-mcp-domain \
  --database-mode postgres-ref \
  --redact-secrets
```

## 4. 프로젝트 생성

```bash
npx -y @railway/cli init
```

권장 구성:

- Empty project 생성
- PostgreSQL 추가
- 앱 서비스는 현재 디렉터리 기준으로 연결

## 5. 서비스 변수 입력

Railway Variables 탭에서 Raw Editor를 열고 `.railway.env` 내용을 붙여넣습니다.

핵심 값:

- `APP_MODULE=app.mcp_app:app`
- `DATABASE_URL=${{Postgres.DATABASE_URL}}`
- `MCP_PUBLIC_BASE_URL=https://your-mcp-domain`
- `MCP_ALLOWED_HOSTS=your-mcp-domain,healthcheck.railway.app`
- `MCP_ALLOWED_ORIGINS=https://playmcp.kakao.com`

## 6. 로컬 코드 배포

```bash
npx -y @railway/cli up
```

이 저장소에는 이미 다음 파일이 준비되어 있습니다.

- `Dockerfile`
- `railway.json`
- `.dockerignore`

그래서 `railway up` 이 로컬 코드 기준으로 Dockerfile 빌드/배포를 수행할 수 있습니다.

## 7. 배포 후 확인

배포 URL이 나오면 아래를 확인합니다.

- `https://your-mcp-domain/healthz`
- `https://your-mcp-domain/readyz`

그리고:

```bash
source .venv/bin/activate
analyst verify-mcp-endpoint --url https://your-mcp-domain/
```

## 8. PlayMCP 등록

등록 endpoint 는 전용 MCP 앱 기준:

- `https://your-mcp-domain/`

최종 등록 체크리스트는 [playmcp-registration-checklist.md](/Users/sukhwan/Documents/주식애널리스트%20보고서/docs/playmcp-registration-checklist.md) 참고

## 9. 로그인 뒤 자동 실행

현재 저장소에는 로그인 이후 단계를 한 번에 처리하는 스크립트도 있습니다.

```bash
./scripts/railway_bootstrap_after_login.sh
```

이 스크립트는 다음을 순서대로 수행합니다.

1. Railway 로그인 상태 확인
2. 프로젝트 링크 확인/생성
3. 앱 서비스 생성 및 링크
4. Postgres 서비스 생성
5. Railway 제공 도메인 생성
6. `.env` 기반 Railway 변수 블록 생성
7. 서비스 변수 주입
8. 앱 재배포
9. `/readyz` 와 MCP endpoint 검증
