#!/usr/bin/env bash
# [P4] Smoke test toan bo API endpoint. Chay tren `p4-api` va tren main sau
# khi tich hop. Muc dich: 30 giay biet duoc pipeline con song hay khong.
#
# Cach dung:
#   ./scripts/smoke.sh               # tro vao http://localhost:8000
#   API=http://staging.foo scripts/smoke.sh
#
# Exit code:
#   0 = tat ca check pass
#   >0 = so luong check fail

set -u

API="${API:-http://127.0.0.1:8000}"
FAIL=0
PASS=0

CYAN=$'\033[36m'; GREEN=$'\033[32m'; RED=$'\033[31m'; RESET=$'\033[0m'
[[ -t 1 ]] || { CYAN=""; GREEN=""; RED=""; RESET=""; }

section() { echo; echo "${CYAN}== $1 ==${RESET}"; }
check() {
  local name="$1" expected_status="$2"; shift 2
  local status
  status=$(curl -s -o /tmp/lawgic_smoke_body -w "%{http_code}" "$@")
  if [[ "$status" == "$expected_status" ]]; then
    printf "  ${GREEN}%3s${RESET}  %s\n" "$status" "$name"
    PASS=$((PASS + 1))
  else
    printf "  ${RED}%3s${RESET}  %s  ${RED}(expected %s)${RESET}\n" "$status" "$name" "$expected_status"
    FAIL=$((FAIL + 1))
    [[ -s /tmp/lawgic_smoke_body ]] && head -c 200 /tmp/lawgic_smoke_body && echo
  fi
}

section "Basic"
check "/health"                       200 "$API/health"
check "/stats"                        200 "$API/stats"
check "/"                             200 "$API/"
check "/docs (Swagger)"               200 "$API/docs"

section "Documents"
check "/documents"                    200 "$API/documents"
check "/documents/qlt2025"            200 "$API/documents/qlt2025"
check "/documents/nope"               404 "$API/documents/nope"
check "/documents/qlt2025/file"       200 "$API/documents/qlt2025/file"
check "/documents/nope/file"          404 "$API/documents/nope/file"
check "path traversal blocked"        404 "$API/documents/..%2Fetc%2Fpasswd/file"

section "Trends & misconceptions"
check "/trends"                       200 "$API/trends"
check "/misconception/misc-001"       200 "$API/misconception/misc-001"
check "/misconception/misc-999"       404 "$API/misconception/misc-999"
check "/document/qlt2025/diff"        200 "$API/document/qlt2025/diff"
check "/document/nope/diff"           404 "$API/document/nope/diff"

section "Search — validation"
check "empty q rejected"              422 "$API/search?q="
check "limit=0 rejected"              422 "$API/search?q=abc&limit=0"
check "limit=99 rejected"             422 "$API/search?q=abc&limit=99"
check "bad as_of_date rejected"       422 "$API/search?q=abc&as_of_date=garbage"
check "valid search"                  200 "$API/search?q=nguong&limit=5"
check "diacritic search (URL-enc)"    200 "$API/search?q=500%20tri%E1%BB%87u"

section "Q&A — validation"
check "question too short"            422 -X POST "$API/qa" -H 'content-type: application/json' -d '{"question":"a"}'
check "bad as_of_date"                422 -X POST "$API/qa" -H 'content-type: application/json' -d '{"question":"nguong 500 trieu","as_of_date":"garbage"}'
check "valid question"                200 -X POST "$API/qa" -H 'content-type: application/json' -d '{"question":"nguong 500 trieu"}'
check "off-topic (refused mode)"      200 -X POST "$API/qa" -H 'content-type: application/json' -d '{"question":"cho toi biet tien ao gia bao nhieu"}'

section "Rate limit"
# /qa cho phep 10/60s. Ban 11 phat lien tuc -> phat cuoi phai 429.
for i in $(seq 1 11); do
  code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$API/qa" -H 'content-type: application/json' -d '{"question":"nguong 500 trieu"}')
done
if [[ "$code" == "429" ]]; then
  printf "  ${GREEN}429${RESET}  11th /qa hit rate-limited\n"
  PASS=$((PASS + 1))
else
  printf "  ${RED}%s${RESET}  11th /qa should be 429 (got %s)\n" "$code" "$code"
  FAIL=$((FAIL + 1))
fi

section "Summary"
echo "  ${GREEN}PASS: $PASS${RESET}"
echo "  ${RED}FAIL: $FAIL${RESET}"
exit "$FAIL"
