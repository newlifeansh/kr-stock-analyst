# 토스증권 실계좌 자동매매 운영

이 프로세스는 총 100만원을 국내 30만원과 미국 70만원의 독립 예산으로 운용한다. 한 시장에서 남은 돈을 다른 시장에 쓰지 않는다. 기본 설정은 시장별 최대 두 종목, 하루 손실 중단선은 전체 1만원을 30:70으로 나눈 3천원과 7천원이다. 손실 중단선은 신규 매수만 막고 보유 포지션의 매도는 허용한다.

토스증권 WTS의 Open API 설정에서 키와 고정 허용 IP를 등록한다. 키는 배포 환경의 비밀 저장소를 우선하고, 로컬에서는 Git이 무시하며 소유자만 읽을 수 있는 `.env`에 `TOSS_OPENAPI_CLIENT_ID`, `TOSS_OPENAPI_CLIENT_SECRET`으로 넣는다. 비밀값은 로그와 명령 출력에 남기지 않는다. 계좌 목록에서 사용할 종합매매 계좌의 `accountSeq`를 `TOSS_OPENAPI_ACCOUNT_SEQ`로 지정한다. 계좌번호 전체는 명령 출력에 나타나지 않는다.

먼저 실주문 스위치를 끈 상태로 읽기 전용 사전 점검을 실행한다.

```bash
TOSS_AUTOTRADE_LIVE_ENABLED=false analyst autotrade preflight
```

사전 점검은 토큰, 선택 계좌, 원화·달러 매수가능금액, USD/KRW 환율만 조회한다. 주문 생성·취소·정정은 호출하지 않는다. 보유 자산과 미체결 매수 예약액까지 포함해 국내 슬리브가 30만원, 미국 슬리브가 70만원 상당으로 모두 충전되지 않으면 어느 시장에도 신규 매수를 내지 않는다. 선택한 계좌와 자금이 맞으면 런타임 비밀 설정에서 `TOSS_AUTOTRADE_LIVE_ENABLED=true`로 바꾸고 전용 단일 프로세스를 시작한다.

```bash
analyst autotrade run --interval-seconds 30
```

macOS 상시 운영은 `~/Library/LaunchAgents/com.secretnote.toss-autotrade.plist`에서 전용 프로세스를 하나만 기동한다. `WorkingDirectory`는 비밀 `.env`와 같은 체크아웃을 가리켜야 하고 `KeepAlive=true`, `RunAtLoad=true`로 설정한다. 운영 상태와 중지 명령은 다음과 같다.

```bash
launchctl print gui/$(id -u)/com.secretnote.toss-autotrade
tail -f ~/Library/Logs/secret-note-toss-autotrade.log
launchctl bootout gui/$(id -u)/com.secretnote.toss-autotrade
```

운영 프로세스는 국내·미국 시그널 API의 `ready` 스냅샷 중 각 시장의 당일 이벤트이며 180초 안에 갱신된 분봉 검증 이벤트만 처리한다. 국내 매수는 정수 수량 시장가, 미국 매수는 달러 금액 시장가를 사용한다. Open API의 `orderAmount`는 달러 단위이며 원화 자동환전을 계약으로 보장하지 않으므로, 실행 전에 미국 예산 상당의 달러 매수가능금액을 준비한다. 미국 금액 주문은 토스가 허용하는 정규장 시작부터 종료 1시간 전까지만 접수된다.

주문 전에 `signal_event_id`, `clientOrderId`, 요청 본문을 데이터베이스에 커밋한다. 같은 이벤트는 다시 주문하지 않는다. 응답을 받지 못한 요청은 토스의 10분 멱등성 보장보다 짧은 8분 안에서 같은 본문으로만 복구한다. 8분이 지나면 `AMBIGUOUS_BLOCKED`로 남기며 자동 재전송하지 않는다. 이 상태는 토스 주문 내역과 장부를 사람이 대조한 뒤 해결해야 한다.

재시작할 때 주문 상세를 다시 읽고 새로 늘어난 체결 수량만 포지션에 반영한다. 부분매도는 현재 잔량의 절반이 아니라 최초 매수 체결 수량의 모델 비율을 사용한다. 모든 계좌 보유 종목과 미체결 매수 예약액을 예산에 포함하므로 수동 보유가 이미 한도를 채우면 신규 매수를 건너뛴다.

현재 구현을 검증하는 명령은 다음과 같다.

```bash
pytest -q tests/test_toss_autotrade.py
analyst qa render-catalog
analyst qa data-signal --mode gate
```

`live` QA는 반드시 읽기 전용 사전 점검만 수행해야 한다. 실제 주문을 시험 목적으로 생성하거나 즉시 취소하는 방식으로 검증하지 않는다.
