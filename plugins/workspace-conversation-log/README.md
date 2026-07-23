# Workspace Conversation Log

CulturePick의 Codex 대화를 프로젝트 안에 보존해 다른 PC에서도 작업 맥락을 이어가기 위한 로컬 플러그인입니다.

## 동작 방식

- 저장 시점: Codex가 한 번의 응답을 끝낼 때 실행되는 `Stop` 훅
- 저장 위치: `.codex/conversations/<session-id>.jsonl`
- 저장 내용: 사용자 메시지, 에이전트의 진행 메시지와 최종 응답
- 제외 내용: 시스템/개발자 지침, 추론, 도구 호출과 출력, 세션 메타데이터
- 안전장치: 대표적인 API 키·토큰·DB URL 자격증명 마스킹, 100 MiB 입력 제한, 원자적 파일 교체 우선, 오류 시 원문 복사 금지
- 보존기간: 세션 JSONL은 기본 90일이며 다음 Stop 훅 실행 시 만료 파일만 정리
- 인수인계 요약: `.codex/conversation-log.md`

JSONL은 현재 세션 전체를 매 응답 종료 시 다시 정규화하므로 중복 줄이 누적되지 않습니다. 과거 세션은 각각 별도 파일로 남습니다.
보존기간은 `CODEX_CONVERSATION_LOG_RETENTION_DAYS` 환경 변수로 1~3650일 범위에서
조정할 수 있습니다. `.codex/conversation-log.md`는 장기 인수인계 문서이므로 이
자동 정리 대상에 포함되지 않습니다.

Windows에서 검색기나 파일 감시기가 기존 JSONL을 delete-sharing 없이 잠가 원자적
교체만 거부하는 경우에는, 완전히 작성하고 `fsync`한 임시 파일을 원본으로 사용해
제자리 갱신합니다. 이 fallback은 자동 기록 누락을 피하기 위한 Windows 전용
호환 경로입니다.

## 이 저장소에서 사용

1. Python 3가 설치되어 있는지 확인합니다. Windows에서는 `py`, `python3`, `python`과 Codex Desktop 번들 런타임을 순서대로 찾고, 그 밖의 환경에서는 `python3` 또는 `python`을 자동 탐색합니다.
2. `culturepick-back` 폴더 자체를 Codex 작업 루트로 엽니다.
3. ChatGPT Desktop을 다시 시작하고 플러그인 목록의 `Culturepick Local`에서 이 플러그인이 활성화됐는지 확인합니다. 이 저장소에서는 기본 설치 정책으로 등록되어 있습니다.
4. Codex에서 새 작업을 시작한 뒤 `/hooks`에서 새 Stop 훅의 내용을 검토하고 신뢰합니다. 이미 열린 작업은 새 플러그인과 훅을 즉시 다시 읽지 않을 수 있습니다.
5. 한 번 대화한 뒤 `.codex/conversations/`에 JSONL이 생겼는지 확인합니다.

플러그인의 `hooks/hooks.json`이 자동 기록을 연결합니다. 설치된 플러그인의 위치와 관계없이 훅이 전달한 작업 경로에서 가장 가까운 Git 루트를 찾아 로그를 저장합니다. 플러그인의 skill은 새 환경에서 요약과 최신 로그를 먼저 확인하고, 작업 종료 시 인수인계 요약을 갱신하는 절차를 제공합니다.

팀 마켓플레이스로 등록하려면 저장소 루트에서 다음 명령을 실행합니다.

```text
codex plugin marketplace add .
```

로컬 marketplace의 플러그인 설치와 활성화는 ChatGPT Desktop의 플러그인 목록에서 확인합니다. 훅 정의가 바뀌면 안전을 위해 신뢰 승인을 다시 해야 합니다.

## 테스트

```text
py -m unittest discover plugins/workspace-conversation-log/tests -v
```

Linux/macOS에서는 `py` 대신 `python3`을 사용합니다.

## 다른 PC로 전달할 때

대화 파일은 일반 프로젝트 파일이므로 Git으로 전달하려면 명시적으로 검토하고 커밋해야 합니다. 비공개 저장소에서만 사용하고, 외부 공유 전에 반드시 내용을 확인하세요. 자동 마스킹은 방어 수단이지 모든 비밀값과 개인정보를 완벽히 판별하는 보증이 아닙니다.

대화 원문을 곧바로 파인튜닝 데이터로 사용하지 마세요. 동의·보유기간·삭제 정책을 먼저 정하고, 개인정보 제거·중복 제거·품질 검토를 거친 승인 데이터셋을 별도로 버전 관리해야 합니다.
