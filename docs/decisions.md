# 결정 로그 — 지금까지 정해진 방향성 (2026-09-12 기준)

한 줄씩. 근거와 원본 문서를 함께. 뒤집으려면 여기에 새 줄을 추가한다 (기존 줄은 지우지 않는다).

## 제품

| # | 결정 | 근거 | 날짜 | 원본 |
| --- | --- | --- | --- | --- |
| D1 | 프로젝트명 **UXight** | 킥오프 합의 | 09/02 | `260901-kickoff.md` |
| D2 | 한 줄 정의: LLM 가상 사용자로 UT 를 대신 돌리고, 행동 로그에서 UX 문제를 진단해 개선안을 제안하며, **승인된 개선안을 자동 적용해 재실험으로 검증**하는 UX 리서처용 플랫폼 | UXAgent(시뮬레이션)의 다음 단계 = 진단·개선·검증 | 09/06 | `product-direction.md` §1 |
| D3 | **1차 타겟 UX 리서처/디자이너**. 모든 설계 결정의 기준. 2차(디자이너 없는 소규모 팀)는 기대효과에서만 | 타겟에 따라 갈리는 결정은 "근거를 얼마나 보여주나"와 "개선안 표현" 둘뿐 → 하나로 고정 | 09/06 | §2 |
| D4 | **사용자는 리서처 한 종류.** UT 는 전부 Agent 가 한다. UT 참가자라는 사용자는 제품에 없다 | "모든 사용자는 PC" 가정. 실사용자 5~10명 검증은 연구 검증용 1회성이지 제품 기능이 아님 | 09/10 | 이 세션 |
| D5 | **웹 = 작업대, 앱 = 호출기.** 설정·분석은 웹, 앱은 시뮬레이션이 도는 동안 PC 를 떠나도 알림·승인이 되게 하는 보조 단말 | 앱의 근거는 "리서처가 PC 를 떠나 있을 때" 뿐. 승인은 어디서든 | 09/10 | `proposal-draft.md` P2/P6 |
| D6 | 테스트 대상은 **웹, 임의 URL**. 동작 보장·데모는 1~2개 사이트(가천대 포털, 장학금 시나리오) | 범용 주장과 15주 구현 현실의 타협 | 09/06 | §3 In |
| D7 | 개선 화면은 **DOM 패치로 자동 생성, 4종만** (라벨 변경 · 요소 이동 · 요소 강조 · 도움말 삽입) | 사이트 구조와 무관하게 안정적인 범위. 카톡 outline 예시가 전부 포함 | 09/06 | §3 |
| D8 | **앱 테스트는 Phase 2. 10/25(S3 말) 게이트**, 진척 ≥ 50% 일 때만 착수. 진단까지만 | 앱 탐색 기술은 확립됨(AppAgent 등)이나 볼륨 +25~35%. 컴파일된 앱은 자동 적용 불가. 제안서는 성적 미반영, 최종 60% → 적게 약속 | 09/06 | §3 Phase 2, GACA-63 |
| D9 | Driver 추상화 (observe/act/로그). WebDriver=Playwright 지금, AppDriver=Appium 나중 | D8 의 전제. Friction 진단은 행동 기반이라 드라이버 무관 | 09/06 | §5 |
| D10 | 실사용자 실험은 **축소 포함**: 5~10명, 성공률·소요시간·SUS. AI 예측 방향과 비교 | 결과 30% 점수의 근거. 20명·NASA-TLX 는 Out | 09/06 | §3 |
| D11 | UX Friction Taxonomy 7종 고정. "LLM 에게 그냥 물어보지 않는다" — 행동 근거 → 분류 → 심각도 → 개선안 | 카톡 outline. 프로젝트 품질을 좌우하는 구조 | 09/01 | `KakaoTalk_Chat_*.txt` |
| D12 | Persona 3종: Novice / Expert / Mobile-viewport | 개인화 개선안은 Out | 09/06 | §3 |
| D5' | **(재검토 중)** 09/10 위클리에서 PM 이 팀에 "전부 웹으로 간다, 앱은 테스트가 힘들다" 고 안내. D5(앱=호출기)와 다르고 학과 요건 a 와 충돌 | 09/14 교수님 확인 결과로 D5 유지/폐기 결정 | 09/10 | `meetings/2026-09-10-weekly.md` §2 |

## 기술

| # | 결정 | 근거 | 날짜 | 원본 |
| --- | --- | --- | --- | --- |
| T1 | 스택 후보 6: **Flutter · React+TS(Vite) · FastAPI · Playwright(Python) · OpenRouter · SQLite+JSON 로그**. 확정은 S1 | 원칙 ① Python 으로 언어 하나 ② 서버 한 대·사용자 한두 명·수백 MB 이상을 위한 부품 안 넣음 | 09/10 | `proposal-draft.md` P9 |
| T2 | **PostgreSQL · Redis · Celery 넣지 않음.** 필요 신호(리서처 3명 동시, 재시작 넘기는 재실험, 로그 횡단 쿼리)가 보이면 그때 | overengineering 지양 | 09/10 | P9 |
| T3 | LLM 은 **OpenRouter** 경유, 역할별 분리: Agent step = flash 급(개발 DeepSeek V4 Flash / 시연 GPT-5 mini 급), Diagnosis·Improvement = Opus 5. 15주 약 $110, 예산 $150 | 토큰 95% 가 Agent step. 무료 모델은 rate limit 으로 배선용만 | 09/06 | `llm-cost.md` |
| T4 | Agent step 모델은 **S3 1주차 A/B** 로 확정 (후보 4 × Persona 3 × 3회, <$10) | flash 급 웹 에이전트 성능은 공개 벤치마크 없음 | 09/06 | `llm-cost.md` §5 |
| T5 | DOM pruning · step 상한 20 · Persona 상한 10 — 비용 3대 레버 | 원본 DOM 은 4배 | 09/06 | `llm-cost.md` §8 |
| T6 | **스택 확정 (BE 제외):** React+TS(Vite) · Playwright(Python) · LangChain(LLM 호출·구조화 출력 한정) · OpenAI-compatible 클라이언트 한 겹 · SQLite+JSON 로그 · asyncio 세마포어 · GH Actions+Compose+개인 서버 · **monorepo** | 팀 경험 1순위 + T1·T2 원칙. 세부 `tech-stack.md` §3 | 09/12 | `tech-stack.md` |
| T7 | **모바일은 Flutter 가 아니라 Expo(React Native), 그것도 09/14 앱 필수 확인 후.** T1 의 Flutter 는 경험자 없이 잡힌 것 | FE 둘 다 React. Flutter 경험자 0 | 09/12 | `tech-stack.md` §5 |
| T8 | **BE 언어 미결 — 한재완님과 상의 후 (기한 09/19).** PM 권장 FastAPI 단일 서비스. 근거: 한재완 AI 합류 + BE 책임 7개 중 4개가 Agent 코드 오케스트레이션 | 상의 포인트 4개 정리 | 09/12 | `tech-stack.md` §4 |
| T1' | **팀원 선호 수집:** FE React(이수훈·이유진 합의) / BE **Spring+MySQL 선호**(한재완, Python 가능) / AI Llama·**LangChain**(박소영). T1(FastAPI) 과 BE 가 다름 → PM 이 세부 안 정리 후 S1 확정 | 담당자 익숙한 스택 우선 원칙 | 09/10 | M-미결 |

## 운영

| # | 결정 | 근거 | 날짜 | 원본 |
| --- | --- | --- | --- | --- |
| O1 | Jira: `duedate`=soft(내부), `Hard due`=학사. **둘 다 필수** (의도) | 알림·필터는 duedate 기준. 마진은 PM 버퍼 | 09/01·09/06 | `jira.md` |
| O2 | soft due 티어: 발표·고배점 −4일(수) / 주간 진도표 −2일(금) / hwp·doc 는 내용 freeze −7일 | 성적 비중·되돌리기 비용·형식 변환·의존성 | 09/01 | `jira.md` |
| O3 | 2주 스프린트 7개(S0~S6), 월~일. 학사 마일스톤 정렬 | | 09/01 | `jira.md` |
| O4 | **담당자 hold** (PM 만). S1 에서 surface 별 확정 | 팀원 혼선 방지 | 09/06 | |
| O5 | 제안서 일정 재조정: 완성본 09/10(목) soft. 마진 4→3일. 더 못 민다 | 초안 공지 지연 | 09/06 | `proposal-plan.md` |
| O6 | P11 은 간트/WBS 대신 **Jira 타임라인 → SVG 렌더** | Jira 가 있는데 WBS 중복 | 09/07 | `render-timeline.py` |
| O7 | GitHub org 생성 완료, 팀원 초대 중. 저장소 구조·브랜치 전략은 S1 | 제안서 주간엔 안 건드림 | 09/06 | GACA-33/34 |
| O9 | 제안서 초안은 **HTML 슬라이드 덱**으로 (Figma DS 임시 적용). pptx 초안은 폐기. 제출(ppt 형식)은 PDF 출력 또는 변환으로 | HTML 이 DS·SVG 를 그대로 살림. 디자인 시스템은 아직 미확정이라 임시 | 09/10 | `docs/proposal/UXight-제안서.html` |
| O8 | Atlassian 회사/캡스톤 이원화 (project scope MCP + deny) | 회사 Jira 오염 방지 | 09/01 | `atlassian-mcp.md` |
| O10 | **위클리 목 20:00.** 예외 09/14(월, 발표 직후) · 09/22(화, 추석). 기술 미팅: AI 일요일 대면 정기 / FE 목 18:00 온라인 / BE 필요 시 | 팀원 일정 · 축제 · 추석 | 09/10 | `meetings/2026-09-10-weekly.md` M5·M6 |
| O11 | **브랜치 전략 초안:** main / develop / 파트별(fe·be·ai) → develop 으로 PR. 피처 단위. 가이드는 PM 문서 | 팀원 GitHub 협업 경험 적음 | 09/10 | M8 |
| O12 | 서버 = PM 개인 서버. API 는 초반 PM 회사 API → 기술 이슈 시 OpenRouter(T3) | 학과 예산 지원 없음 | 09/10 | M9·M10 |
| O13 | 발표자 = PM. 제안서 검수 토 22:00 → 일 최종·연습 → 월 발표 | | 09/10 | M2·M3 |
| O14 | 한재완 AI 파트 겸임. 기술 미팅 요약은 Slack, 위클리 녹취는 Confluence | AI 인력 부족 | 09/10 | M7·M11 |
| O15 | **코드 저장소 `team-uxight/uxight` 는 public.** 팀이 코드를 만들 때 필요한 md 만 올린다 (`scripts/sync-public.sh` allowlist). 회의록·비용·카톡·양식·MCP 설정은 PM 작업공간에만. 팀 공유가 필요하면 확인 후 **Confluence** 로 | 졸업작품 포트폴리오 공개 가치 vs 개인정보·내부 정보 노출 | 09/12 | `CLAUDE.md` 공개 저장소 규칙 |
| O16 | 저장소 설정: squash 머지만 · 머지 후 브랜치 삭제 · wiki 끔 · ~~Issues 끔~~ → O18 로 다시 켬 | 경로 하나 | 09/12 | GACA-34 |
| O17 | GitHub Teams `fe`(이수훈·이유진) `be`(한재완·PM) `ai`(박소영·한재완·PM), 저장소 push 권한. CODEOWNERS 는 팀 단위 | | 09/12 | GACA-33 |
| O18 | **Jira 유지** (GitHub-only 검토 후). Jira = 계획·추적 단일 진실. **GitHub Issues 는 코드 인용이 필요한 리뷰·결함 논의에만**, Jira 버그/하위작업에 링크로 짝을 만든다. GitHub Issues 다시 켬 | PM 이 회사에서 쓰던 도구라 운영 비용이 낮음. 팀 학습 부담은 인정하되 PM 이 감당 | 09/12 | `jira.md` 역할 분담 |

## 아직 안 정한 것

| 항목 | 언제 | 누가 |
| --- | --- | --- |
| 모바일 앱 필수 여부 (a+b+c) — **회의에선 '전부 웹' 방향** | 09/14 발표 후 교수님께 | PM |
| **BE 언어** Spring vs FastAPI — 한재완님 상의 (T8) | **09/19** | PM |
| 모바일 앱 스택 (Expo) — 앱 필수 여부에 종속 (T7) | 09/14 | PM |
| 회사 API 형식 확인 (OpenAI-compatible · 툴콜링 · JSON 모드) | S1 첫 주 | PM |
| 아키텍처 설계 문서 — BE 결정 후 | 09/19 이후 | PM |
| LLM 비용 팀 내부 상한 | S1 | PM·AI Lead |
| S1 산출물 합의 (화면·데이터·API·Taxonomy) — 09/10 미진행 | 09/14 위클리 | PM |
| surface 별 담당 (O4 해제) | S1 | PM |
| 저장소 구조 (mono vs multi) · 브랜치 전략 | S1 | PM |
| 배포 대상 | S2 (GACA-43) | PM |
| Agent step 모델 | S3 1주차 A/B | AI Lead |
| 앱 드라이버 착수 | 10/25 게이트 | PM |
