#!/usr/bin/env sh
# GACA-196 제출용 .sql 만들기 — dev 서버에서 docker-compose.yml 이 있는 폴더에서 실행한다 (README.md 참고).
#   sh services/api/sample-data/export-submission.sh [출력 파일]
# 1) dev DB 를 mysql 컨테이너 안에서 임시 스키마(uxight_submit)로 바로 복사한다 — 원본 덤프 파일을 만들지 않는다
# 2) 임시 스키마에서 sanitize-submission.sql 을 돌려 비밀번호 해시 · 토큰 · 실제 계정의 이메일 · 이름을 지운다
# 3) 임시 스키마를 덤프해 출력 파일로 쓰고, 임시 스키마를 지운다
# 바꿀 수 있는 값: COMPOSE(기본 "docker compose") · MYSQL_SERVICE(기본 mysql)
set -eu

OUT="${1:-uxight-sample-$(date +%Y%m%d).sql}"
DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="${COMPOSE:-docker compose}"
MYSQL_SERVICE="${MYSQL_SERVICE:-mysql}"
TMP_DB=uxight_submit

# 컨테이너 안의 root 비밀번호 · DB 이름(MYSQL_ROOT_PASSWORD · MYSQL_DATABASE)을 쓴다. 비밀번호는 이 셸에 오지 않는다
in_mysql() {
  $COMPOSE exec -T "$MYSQL_SERVICE" sh -c "$1"
}
MYSQL='mysql --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD"'
DUMP='mysqldump --default-character-set=utf8mb4 -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction --no-tablespaces --set-gtid-purged=OFF'

cleanup() {
  in_mysql "$MYSQL -e 'DROP DATABASE IF EXISTS $TMP_DB'" 2>/dev/null || true
}
trap cleanup EXIT

echo "1/3 dev DB 를 임시 스키마 $TMP_DB 로 복사"
in_mysql "$MYSQL -e 'DROP DATABASE IF EXISTS $TMP_DB; CREATE DATABASE $TMP_DB CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci'"
in_mysql "$DUMP \"\$MYSQL_DATABASE\" | $MYSQL $TMP_DB"

echo "2/3 임시 스키마에서 비밀번호 해시 · 토큰 · 실제 계정 정보 지우기"
in_mysql "$MYSQL $TMP_DB" < "$DIR/sanitize-submission.sql"

echo "3/3 $OUT 로 내보내기"
in_mysql "$DUMP --skip-dump-date $TMP_DB" > "$OUT"

echo
echo "표마다 건수 (policies 는 전역 정책 1행 설계, flyway_schema_history 는 마이그레이션 이력)"
in_mysql "$MYSQL -t $TMP_DB" <<'SQL'
SELECT 'users' AS table_name, COUNT(*) AS row_count FROM users
UNION ALL SELECT 'projects', COUNT(*) FROM projects
UNION ALL SELECT 'tasks', COUNT(*) FROM tasks
UNION ALL SELECT 'test_accounts', COUNT(*) FROM test_accounts
UNION ALL SELECT 'personas', COUNT(*) FROM personas
UNION ALL SELECT 'runs', COUNT(*) FROM runs
UNION ALL SELECT 'run_personas', COUNT(*) FROM run_personas
UNION ALL SELECT 'run_metrics', COUNT(*) FROM run_metrics
UNION ALL SELECT 'findings', COUNT(*) FROM findings
UNION ALL SELECT 'improvements', COUNT(*) FROM improvements
UNION ALL SELECT 'approvals', COUNT(*) FROM approvals
UNION ALL SELECT 'patch_versions', COUNT(*) FROM patch_versions
UNION ALL SELECT 'refresh_tokens', COUNT(*) FROM refresh_tokens
UNION ALL SELECT 'audit_log', COUNT(*) FROM audit_log
UNION ALL SELECT 'policies', COUNT(*) FROM policies
UNION ALL SELECT 'flyway_schema_history', COUNT(*) FROM flyway_schema_history;
SQL

echo
# BCrypt 해시가 하나라도 남았으면 실패로 끝낸다
if grep -q '\$2[aby]\$' "$OUT"; then
  echo "실패: $OUT 에 BCrypt 해시가 남아 있다" >&2
  rm -f "$OUT"
  exit 1
fi
echo "확인: BCrypt 해시 없음"
# 샘플 · 가린 주소가 아닌 이메일 모양 글자 — 있으면 제출 전에 눈으로 본다
OTHER_EMAILS="$(grep -oE '[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' "$OUT" \
  | grep -vE '@(sample\.uxight\.example|example\.com)$' | sort -u || true)"
if [ -n "$OTHER_EMAILS" ]; then
  echo "확인 필요: 아래 이메일 모양 글자가 남아 있다 (제출 전에 어디서 나왔는지 본다)"
  echo "$OTHER_EMAILS"
else
  echo "확인: 샘플 · 가린 주소 말고는 이메일 없음"
fi
echo "완료: $OUT"
