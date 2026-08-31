# 인사이트 백엔드 운영 기준

기준 스레드: `019ed577-3961-7f30-b9da-05112758804a`

이 문서는 현재 백엔드가 어떤 주기로 데이터를 모으고, 어떤 종류의 인사이트를 만들며, 무료 리포트 소스를 어떻게 관리하는지 정리한 설계 메모다.

## 1. 인사이트를 얻는 주기와 방식

핵심 원칙은 `조회 주기`와 `판단 주기`를 분리하는 것이다.

- 조회는 빠르게: 1분~5분
- 판단은 느리게: 5분 이상 묶어서
- 장중 알림은 실시간에 가깝게
- 투자 아이디어 재평가는 일간, 주간, 월간, 분기 단위로

### 판단 시간축

1. 단기 상대수익 판단: `2~8주`
2. 실적 기대 변화 판단: `6~18개월`
3. 장기 가치 판단: `3~5년`

### 운영 루프

- `1분`: 관심 종목, 급등락, 거래대금 상위, 공시/뉴스 이벤트
- `5분`: 관심 종목 묶음 스캔, 랭킹 재정렬
- `일간`: 장 마감 후 무엇이 달라졌는지 요약
- `주간`: 모멘텀, 수급, 이벤트 신호 리프레시
- `월간`: 거시/업종/컨센서스 방향 점검
- `분기`: 실적 시즌 기준으로 투자 논리 재검증

이 기준은 `/meta/insight-cadence`에서 API로도 그대로 노출한다.

## 2. 무료 리포트 받는 곳

현재 백엔드의 실제 수집기는 `네이버 금융 리서치`를 기준으로 동작한다. 이 경로는 종목명, 증권사, 작성일, PDF 링크, 목표주가, 투자의견 같은 메타데이터를 쌓기에 적합하다.

실제 운영에서는 소스를 아래처럼 구분한다.

### 현재 활성 수집 소스

- `Naver Finance Research`

### 공개 후보 소스

- `Hankyung Korea Market Consensus`
- `Hana Securities Research`
- `Korea Investment Securities Research`
- `Samsung Securities Research`
- `Mirae Asset Securities Research`
- `Kiwoom Securities Research`
- `Daishin Securities Research`
- `Eugene Investment Research`
- `Hanwha Investment Research`
- `IBK Securities Research`
- `Hyundai Motor Securities Research`
- `iM Securities Research`

중요한 점은 `무료 공개 페이지`와 `안정적으로 수집 가능한 소스`가 같지 않다는 것이다. 그래서 백엔드에는 소스 레지스트리를 따로 두고, 실제 수집기 연결 여부는 `is_active_collector`로 분리한다.

이 기준은 `/meta/research-sources`에서 API로 확인할 수 있다.

## 3. 지금 구조에서의 우선순위

1. `리포트 + 공시·IR + 뉴스` 적재 안정화
2. `관심 종목` 기준의 인사이트 루프 고정
3. 모바일/PC 화면에서 같은 이벤트를 다른 밀도로 표시
4. AI 시그널의 워크포워드 검증과 데이터 품질 경고 강화
