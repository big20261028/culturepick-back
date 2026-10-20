# 격리 점검 실행

백엔드 폴더에서 실행한다. Docker Desktop의 Linux 엔진이 필요하다.
최초 빌드는 이미지/패키지 다운로드를 위해 인터넷을 사용한다.
테스트 네트워크는 internal이며 외부 API에 연결하지 않는다.

```powershell
docker build -f docker/Dockerfile -t culturepick-audit:local .
docker compose -p culturepick-audit -f docs/audit/compose.yml run --rm test python manage.py test --noinput --verbosity 1
docker compose -p culturepick-audit -f docs/audit/compose.yml run --rm test python manage.py test docs.audit.probes --noinput --verbosity 2
docker compose -p culturepick-audit -f docs/audit/compose.yml down
```

DB는 이 점검 프로젝트 전용이며 tmpfs를 사용한다. 컨테이너 종료 시 데이터가 사라진다.
호스트 포트는 열지 않고, 운영 자격증명을 전달하지 않는다. 저장소는 읽기 전용으로 마운트한다.
기존 `.env`는 이번 점검 시 존재하지 않았다. 다른 환경에서 실행하기 전 `.env` 로딩 여부와
환경변수 우선순위를 확인한다. 실제 운영 환경설정을 이 Compose에 추가하지 않는다.

기본 테스트와 `probes.py`는 목적이 다르다.

- 기본 테스트: 기존 기능에 대한 회귀 테스트.
- probes.py: 발견한 문제를 재현하는 진단. **통과는 결함이 재현됐다는 뜻**이다.
  수정 완료 후에는 정상 기대값의 회귀 테스트로 옮겨야 한다.
- 동시성 진단은 두 요청이 같은 시점에 상태를 확인하도록 barrier만 삽입한다.
  실제 ORM 쓰기와 API 응답은 그대로 사용한다. 일반 트래픽 부하 측정은 아니다.
- AI 통신은 mock이며 모델 품질, GPU 성능, 유료 API 호출 성공을 검증하지 않는다.

점검 결과와 패키지 버전은 `../AUDIT_2026-10-20.md`에 기록한다.
이미지와 빌드 캐시는 재사용을 위해 남겨둔다. 다른 앱의 컨테이너·볼륨은 정리하지 않는다.
