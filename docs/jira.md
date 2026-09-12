# Jira 운영 규칙 (GACA)

사이트 `proj-uxight.atlassian.net` / 프로젝트 `GACA` (team-managed, Scrum, board id 1)

## 날짜 필드 — soft due / hard due 이원화

일정은 교수님이 제시한 학사 마감(hard)보다 **당겨서** 운영해 마진을 확보한다.
팀원이 전부 학생이라 개인 일정 이슈가 생길 것을 전제로 한다.

| 용도 | 필드 | 설명 |
| --- | --- | --- |
| **soft due** (내부 목표) | `마감일` (`duedate`, 기본 필드) | 팀이 실제로 지킬 날짜 |
| **hard due** (학사 마감) | `Hard due` (`customfield_10079`, Date) | 교수님 제시 마감. 변경 금지 |

**soft due 를 기본 `duedate` 에 두는 이유:** Jira 의 알림, 보드 마감 경고, 기본 필터
(`duedate <= endOfWeek()`), 자동화가 전부 `duedate` 를 본다. 여기에 hard due 를 넣으면
"아직 여유 있음" 으로 판정해 **마진 확보라는 목적과 정반대로 동작**한다.

### soft due 산정 원칙

**마진은 누구 것인가.** soft due 는 팀이 지키는 "진짜 마감"이고, soft→hard 사이 마진은 **PM 의 버퍼**다.
팀원에게는 soft due 만 마감으로 안내한다. 마진이 팀원 것이 되는 순간 마진은 사라진다.

**얼마나 당길지는 네 가지로 결정한다.**

| 요인 | 마진을 키우는 조건 |
| --- | --- |
| ① 성적 비중 | 60% > 20% > 10% > 미반영 |
| ② 되돌리기 비용 | 발표(리허설 필요) > 문서 > 반복 보고 |
| ③ 형식 변환 비용 | hwp/doc 변환은 하루가 든다 → "내용 freeze" 와 "형식 완료" 를 분리 |
| ④ 의존성 | 시연영상은 동작하는 코드가 선행 → 코드 freeze 가 문서보다 앞 |

**티어별 규칙**

| 티어 | 대상 | soft due | 근거 |
| --- | --- | --- | --- |
| **A** 발표 + 고배점 | 중간발표(10%) · 최종 일괄(60%) | hard −4일 = **수** + 리허설 1회 | ①② |
| **B** 문서 + 배점/방향 확정 | 제안서 · 진도표 1차(20%) | hard −4일 = **수** | ① |
| **C** 주간 반복 보고 | 구현진도표 W07~W11 | hard −2일 = **금** | 그 주 작업 요약이라 더 당기면 내용이 빈다 |
| **D** 무거운 형식 변환 | 설계서(hwp) · 완료보고서(doc) | 내용 freeze hard −7일, 형식 완료 hard −3일 | ③ |

**최종 제출(W13, 60%)은 단일 soft due 로는 부족하다.** 체크포인트를 하위 작업으로 둔다:
`11/11(수) 코드 freeze` → `11/13(금) 진도표 1차` → `11/16(월) 시연영상` → `11/18(수) 문서 최종(soft)` → `11/22(일) hard`

**스프린트 경계와의 관계.** 스프린트는 월~일이고 hard due 도 일요일이므로, soft due(수/금)는 항상
스프린트 안에 들어온다. 스프린트 리뷰(일) 시점엔 이미 제출이 끝나 있어야 정상이다.

### hard due 원본

`docs/schedule.md` 의 "사캠 업로드 마감" 열이 단일 진실 소스다. 전부 **일요일 18:00**.

### 두 필드 모두 **필수**다 (의도된 설정)

일정을 타이트하게 관리하려고 팀장이 일부러 필수로 걸어뒀다. `시작 날짜`만 선택으로 해제돼 있다.

**학사 마감이 없는 내부 이슈의 `Hard due` 규칙:**
그 이슈가 기여하는 마일스톤의 hard due 를 넣는다 ("이 선은 못 넘긴다"의 의미).
개발 에픽은 대부분 `2026-11-22`(최종 자료 제출)이 된다.

## 레이블 어휘 (고정)

레이블은 자유 입력이라 `mobile-app`/`mobileapp`/`Mobile` 로 갈라진다. 아래 외에는 쓰지 않는다.

| 축 | 값 |
| --- | --- |
| 영역 | `ai-agent` · `backend` · `admin-web` · `mobile-app` · `infra` |
| 성격 | `submission`(학사 제출물) · `research` · `docs` |

## 에픽 구성

| 키 | 에픽 | soft / hard |
| --- | --- | --- |
| GACA-5 | Project Pre-Planning (기존) | - |
| GACA-6 | Project Infra Setting (기존) | - |
| GACA-7 | 학사 제출물 & 마일스톤 | 11/27 / 11/29 |
| GACA-8 | 요구분석 & 설계 | 10/02 / 10/05 |
| GACA-9 | AI Agent 시뮬레이션 | 11/18 / 11/22 |
| GACA-10 | UX Friction 진단 | 11/18 / 11/22 |
| GACA-11 | UX 개선안 & Human-in-the-loop | 11/18 / 11/22 |
| GACA-12 | 관리자 웹 (b) | 11/18 / 11/22 |
| GACA-13 | 모바일 앱 (a) | 11/18 / 11/22 |
| GACA-14 | 백엔드 & 데이터 | 11/18 / 11/22 |
| GACA-15 | 실험 & 검증 | 11/18 / 11/22 |

학사 제출물 11건은 전부 `GACA-7` 아래에 `submission` 레이블로 들어가 있다 (GACA-16~26).
체크포인트 하위 작업: 설계서 `GACA-27~28`, 최종 제출 `GACA-29~32`. 제안서 과업 `GACA-45~62` (`docs/proposal-plan.md`).

## 인프라 이슈 맵 (GACA-6, 전부 PM)

구현 시작(S3, 10/12) 전 완료가 목표. hard due 는 전부 10/11 (W07 진도표), `@claude` 만 10/25.

| 키 | 항목 | soft | 스프린트 |
| --- | --- | --- | --- |
| GACA-33 | GitHub Organization + 팀원 초대 + Team | 09/05 | S0 |
| GACA-34 | 저장소 구조 결정 (monorepo vs multi) + 생성 | 09/12 | S0 |
| GACA-35 | 브랜치 전략 + branch protection | 09/19 | S1 |
| GACA-36 | PR/Issue 템플릿 + CODEOWNERS + .editorconfig | 09/19 | S1 |
| GACA-37 | GitHub for Jira 앱 (브랜치/PR 자동 링크) | 09/19 | S1 |
| GACA-38 | Slack ↔ GitHub 알림 | 09/25 | S1 |
| GACA-39 | Jira ↔ Slack 알림 | 09/25 | S1 |
| GACA-40 | Secrets 관리 규약 | 09/25 | S1 |
| GACA-41 | CI 파이프라인 (surface 별) | 10/02 | S2 |
| GACA-42 | 개발환경 표준화 (docker-compose, pre-commit) | 10/02 | S2 |
| GACA-43 | CD / staging 배포 | 10/09 | S2 |
| GACA-44 | GitHub `@claude` (Claude Pro 구독 토큰) | 10/16 | S3 |

순서에 의존성이 있다: 저장소 구조(34) → 브랜치 전략(35) → 템플릿(36) → CI(41). 기술스택 확정(S1)이 CI 의 선행조건.

## 커스텀 필드 추가 시 주의

team-managed 프로젝트는 **스크린을 REST API 로 조작할 수 없다.** 확인된 사실:

- `GET /rest/api/3/screens` 는 `SCRUM - Epic` 등을 목록에 보여주지만
- `GET /rest/api/3/screens/{id}/tabs` 는 `"ID가 {id}인 화면이 존재하지 않습니다"` 로 실패
- `/rest/internal/simplified/1.0/projects/{pid}/issuetypes/{itid}/{layout,fieldconfiguration}` 는 404

`POST /rest/api/3/field` 로 필드를 만들 수는 있으나 레이아웃에 안 붙어서
`"Field 'customfield_XXXXX' cannot be set. It is not on the appropriate screen"` 이 난다.

→ **필드 추가는 UI 에서 한다.** 프로젝트 설정 → 이슈 유형 → 유형 선택 →
오른쪽 패널에서 드래그 → 저장. 에픽 · 스토리 · 작업 세 유형에 붙이면 충분하다.
붙인 뒤 값 입력·조회는 REST/MCP 로 정상 동작한다.

## 스프린트

월~일 2주 단위, 학사 마일스톤에 정렬.

| 스프린트 | 기간 | 목표 |
| --- | --- | --- |
| S0 킥오프 & 제안서 | 09/01~09/13 | 개념도(hard 09/06), 제안서(hard 09/13) |
| S1 요구분석 | 09/14~09/27 | 학사 제출물 없음 — **버퍼 구간** |
| S2 설계 | 09/28~10/11 | 설계서 완료, 전체개발 10% |
| S3 구현 1 | 10/12~10/25 | 중간발표(10/20, 10%), ~50% |
| S4 구현 2 | 10/26~11/08 | ~90% |
| S5 완료 & 최종제출 | 11/09~11/22 | 100%, 진도표 1차(20%), 최종 일괄(60%) |
| S6 보완 & 마무리 | 11/23~12/08 | 최종발표, 미비자료 보완, 성적평가 |

## Jira ↔ GitHub Issues 역할 분담 (09/12 결정)

**Jira 가 계획·추적의 단일 진실이다.** 모든 작업·버그·제출물은 Jira 이슈로 존재한다.

**GitHub Issues 는 코드를 직접 인용해야 할 때만 쓴다:**
- PR 리뷰 중 발견했지만 그 PR 에서 안 고칠 결함 (라인·커밋 링크가 필요한 것)
- 재현 절차·스택트레이스·코드 스니펫이 본문인 논의
- 특정 파일/함수를 두고 이어지는 기술 토론

**연결 규칙:**
1. GitHub Issue 를 만들면 **Jira 에 짝을 만든다** — 결함이면 `버그`, 할 일이면 해당 작업의 `하위 작업`. Jira 이슈 설명 첫 줄에 GitHub Issue URL
2. GitHub Issue 본문 첫 줄에 Jira 키 (`GACA-123`). 제목에도 넣으면 검색이 편하다
3. GitHub Issue 는 PR 머지로 닫힌다 (`Closes #12`). **Jira 상태는 사람이 옮긴다** — 자동 연동 안 함
4. Jira 에 짝이 없는 GitHub Issue 는 만들지 않는다. 있으면 PM 이 Jira 로 옮기고 닫는다

GitHub Issues 만 보고 있으면 계획이 안 보이고, Jira 만 보고 있으면 코드 맥락이 없다 — 그래서 둘을 링크로 묶는다.

## 도구

이 저장소에서는 **`mcp__atlassian-capstone__*` 만** 사용한다 (`docs/atlassian-mcp.md` 참고).
MCP 로 안 되는 조작은 `./scripts/jira.sh <METHOD> <PATH> [BODY]` 로 REST 를 직접 호출한다.
```sh
./scripts/jira.sh GET  /rest/api/3/project/GACA
./scripts/jira.sh POST /rest/api/3/issue '{"fields":{...}}'
```
