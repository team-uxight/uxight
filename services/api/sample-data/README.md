# 샘플 데이터 · 제출용 DB 백업 (GACA-196)

완료보고서 안내의 "DB 모든 표에 진짜 같은 샘플 데이터 30건 이상, 모든 표를 .sql 로 백업해 제출"을 맞추는 파일이다.
dev 서버 DB 에 PM 이 한 번 돌린다. Flyway 경로(`src/main/resources/db`) 밖이라 앱이 기동할 때는 적용되지 않는다.

| 파일 | 하는 일 |
| --- | --- |
| `seed-sample.sql` | 계정 · 프로젝트 · Task · 테스트 계정 30건씩 + 나머지 표는 30건에 모자란 만큼만 샘플을 넣는다. 다시 돌려도 같다 |
| `sanitize-submission.sql` | 제출용 사본에서 비밀번호 해시 · 토큰 · 테스트 계정 암호문 · Google 식별자 · 실제 계정의 이메일 · 이름을 지운다 |
| `export-submission.sh` | dev DB → 임시 스키마 복사 → 정리 → `.sql` 로 내보내기 → 임시 스키마 삭제. 끝에 표마다 건수와 남은 해시 · 이메일을 확인한다 |

## 순서 (dev 서버, docker-compose.yml 이 있는 폴더에서)

1. **V11 적용** — 이 PR 이 배포되면 Flyway 가 `test_accounts` 표를 만든다.
2. **실제 실험** — dev 화면에서 loop 실험을 돌리고 개선안을 승인 · 반려한다. 많이 돌릴수록 샘플이 적게 들어간다.
3. **샘플 넣기**

   ```sh
   docker compose exec -T mysql sh -c 'exec mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" "$MYSQL_DATABASE"' \
     < services/api/sample-data/seed-sample.sql
   ```

   끝에 표마다 건수가 나온다. policies · flyway_schema_history 말고는 모두 30 이상이어야 한다.
4. **제출용 .sql 만들기**

   ```sh
   sh services/api/sample-data/export-submission.sh            # uxight-sample-<날짜>.sql
   ```

   compose 명령이나 mysql 서비스 이름이 다르면 `COMPOSE="docker compose -f <파일>"` · `MYSQL_SERVICE=<이름>` 을 앞에 붙인다.
   만든 파일은 PM 이 보관해 제출한다. 원본 덤프는 만들지 않으므로 서버에 개인정보가 담긴 파일이 남지 않는다.

## 샘플이 지키는 것

- 샘플 계정 이메일은 모두 예약 도메인 `@sample.uxight.example`, 대상 사이트는 `.example` 이다. 실존 인물 · 주소가 아니다.
- 샘플 계정은 **로그인할 수 없다.** password_hash 가 BCrypt 꼴이 아니라 항상 불일치이고, refresh 토큰은 무작위 값의 해시이며 이미 만료됐다.
- 샘플 회차는 모두 `done` 이다. AI 모듈이 집어 가 실행하지 않는다. step 로그 · 스크린샷 파일은 없다(`log_path` NULL).
- 테스트 계정은 로그인이 필요한 샘플 프로젝트(10개)에만 3개씩 있다. 암호문은 무작위 바이트라 복호화되지 않는다.
- 샘플 실험은 샘플 계정(1~10번)의 프로젝트에만 있어, 팀원 화면의 실험 목록에는 나오지 않는다. 운영자 화면(계정 · 회차 · 감사 로그 · 사용량)에는 나온다.

## 제출 메모에 붙일 문장

- `policies` 는 1행이다 — 관리자가 정하는 전역 정책 한 행만 두는 설계다(정책은 실험마다 회차의 policy_snapshot 으로 복사된다).
- `flyway_schema_history` 는 마이그레이션 이력 표다 — 스키마 버전 수(V1~V11)만큼 행이 있다.
- 제출본의 비밀번호 해시 · 토큰 · 테스트 계정 비밀번호는 지웠고, 실제 팀원 계정의 이메일 · 이름은 `user<번호>@example.com` · `사용자<번호>` 로 바꿨다.
