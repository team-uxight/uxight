# 기술 스택 (v1, 2026-09-12)

**상태:** FE · Agent · LLM · DB · 인프라 확정. **BE 언어는 한재완님과 상의 후 확정 (기한 09/19).** 모바일은 09/14 교수님 답 후.
아키텍처 설계(`docs/architecture.md`)는 BE 결정 뒤에 쓴다.

## 1. 결정 원칙 (우선순위)

| 순위 | 원칙 | 출처 |
| --- | --- | --- |
| 1 | **팀원이 써본 기술 우선** | 09/10 위클리 합의 |
| 2 | 언어 하나 · overengineering 지양 · 서버 한 대·사용자 한두 명·수백 MB 를 넘는 부품 안 넣음 | `decisions.md` T1·T2 |
| 3 | 15주 · 5명 · GitHub 협업 경험 적음 → **운영 부담(서비스 수·배포 수·계약 수)을 최소로** | 09/10 위클리 M8 |

1 과 2 가 충돌하면 **"그 사람이 실제로 이 프로젝트에서 뭘 만드는가"** 로 판단한다 (§4).

## 2. 팀 경험 인벤토리 (09/10 위클리)

| 팀원 | 파트 | 써본 것 | 비고 |
| --- | --- | --- | --- |
| 이수훈 | FE Lead | **React**, 부족한 부분 Python | |
| 이유진 | FE · BE | **React**, 프론트–백 연결 | |
| 한재완 | BE Lead + **AI 합류** | **Java/Spring, MySQL**. Python "가능" | |
| 박소영 | AI Lead | **Llama 계열, LangChain** | 한국인 페르소나 데이터셋 제안 |
| 안준석 | PM · 전 파트 | 인프라, 회사 API 보유 | BE·AI 개입 |

**Flutter 경험자 없음.** (제안서 T1 의 "Flutter 확정" 은 경험 확인 없이 잡힌 것)

## 3. 확정

| 영역 | 확정 | 근거 (원칙) | 기각한 대안 · 이유 |
| --- | --- | --- | --- |
| 관리자 웹 | **React + TypeScript, Vite** | ①둘 다 React ②SPA 로 충분 | Next.js — SSR 필요 없음 |
| Agent 런타임 | **Playwright (Python)** | UXAgent 계열, 디바이스 에뮬레이션으로 Mobile Persona | Selenium — 느리고 API 구식 |
| LLM 오케스트레이션 | **LangChain** — LLM 호출 · 구조화 출력(진단·개선안 JSON)에 한정 | ①박소영 경험 | LangGraph 로 Persona 루프 — 루프는 UXAgent 식 커스텀이 더 얇음 |
| LLM 접근 | **OpenAI-compatible 클라이언트 한 겹** (`base_url` · `api_key` · `model` 환경변수) | 회사 API(M10) → OpenRouter(T3) → OpenAI 교체가 설정값 | 제공자별 SDK 직접 — 교체 비용 |
| DB | **SQLite + SQLAlchemy**, 행동 로그는 run 당 JSON 파일 | ②T2. 한재완 MySQL 경험은 SQL 이라 그대로 | PostgreSQL · MySQL 서버 — 다중 쓰기·외부 접속 없음 |
| 병렬 실행 | **asyncio + 세마포어** (동시 Persona 상한) | ②서버 하나 | Redis/Celery — 서비스만 늘어남 |
| 인프라 | **GitHub Actions · Docker Compose · PM 개인 서버** | M9, 학과 지원 없음 | k8s · 매니지드 |
| 저장소 | **monorepo** (`apps/web` · `apps/mobile` · `services/api`) | ③PR 하나로 web+api 변경, Git 경험 적은 팀 | multi-repo — 계약 동기화 부담 |

LangChain 은 `ChatOpenAI(base_url=…)` 로 위 클라이언트 한 겹과 그대로 맞물린다.
**회사 API 가 툴 콜링을 지원하지 않으면** 구조화 출력은 JSON 모드 + 스키마 검증(pydantic)으로 우회한다 — 클라이언트 한 겹이 그 분기를 감춘다.

## 4. 미결 ① BE 언어 — 한재완님과 상의 (기한 09/19 금)

### BE 가 이 프로젝트에서 실제로 만드는 것

| 책임 | 성격 | Python 코드와의 거리 |
| --- | --- | --- |
| 프로젝트 · 실행 · 진단 · 개선안 CRUD API | 전형적 BE | 멀다 |
| 인증 (리서처 로그인, 단순) | 전형적 BE | 멀다 |
| **Persona 병렬 실행 오케스트레이션** (세마포어 · 재시도 · 상한) | 오케스트레이션 | **Agent 코드를 직접 호출** |
| **행동 로그 수집 · 저장 · 지표 계산** | 데이터 파이프라인 | Agent 가 뱉는 로그 스키마와 결합 |
| **승인 → DOM 패치 → 재실험 트리거** | 이벤트 | Agent 코드 호출 |
| 푸시 발송 (앱이 있으면) | 전형적 BE | 멀다 |

**7개 중 3개만 "전형적 BE" 고, 무거운 4개는 Python Agent 코드에 붙어 있다.** 이게 언어 결정의 핵심이다.

### 두 안

| | **A. Spring API + Python AI 서비스** | **B. FastAPI 단일 서비스** |
| --- | --- | --- |
| 한재완 초반 속도 | 빠름 (익숙) | FastAPI 램프 약 1주. PM 페어링 |
| 서비스 · 배포 | 2 · 2 | 1 · 1 |
| Agent 호출 | HTTP 계약 (JSON 스키마 유지·버전) | 함수 호출 |
| 오케스트레이션 위치 | Spring 이 Python 서비스에 "실행해" 요청 → 상태 폴링/콜백 필요 | 같은 프로세스, asyncio |
| 한재완의 하루 | BE 는 Java, AI 는 Python — **두 언어** | 한 언어 |
| Git 경험 적은 팀의 운영 | 계약 어긋남 · 배포 순서 문제가 자주 남 | 기준 |
| PM 개입 (BE·AI) | 두 언어 | 한 언어 |
| Spring 이 이기는 조건 | 한재완이 AI 를 안 하고, BE 가 CRUD 위주일 때 | — |

**PM 권장: B.** 한재완님이 AI 에 합류하고, BE 역할이 CRUD 가 아니라 오케스트레이션이라는 두 사실 때문이다.
Spring 이 틀린 게 아니라 **이 프로젝트의 BE 모양이 Spring 이 유리한 모양이 아니다.**

### 상의 포인트 (한재완님께)

1. **Python 으로 BE 를 하는 부담이 어느 정도인가** — "가능" 의 온도
2. **AI 파트 비중** — AI 를 반 이상 할 거면 B 가 자연스럽다. AI 는 보조만이면 A 도 열림
3. **A 로 간다면 경계** — 오케스트레이션(병렬 실행·재실험 트리거)을 Spring 에 둘지 Python 에 둘지. Python 에 두면 Spring 은 CRUD 만 남아 "얇은 API" 가 된다 — 그럼 그걸 위해 서비스를 하나 더 둘 가치가 있는가
4. **B 로 간다면 지원** — PM 이 FastAPI 골격(라우터 · SQLAlchemy 모델 · 첫 엔드포인트) 을 만들어 두고 한재완님은 그 위에서 시작. 첫 주 페어링

결정이 나면: `decisions.md` T-항목 추가 → `docs/architecture.md` 작성 → 저장소 구조(GACA-34) · CI(GACA-41) 착수.

## 5. 미결 ② 모바일 — 09/14 교수님 답 후

| 답 | 스택 |
| --- | --- |
| 앱 필수 | **Expo (React Native)** — FE 둘 다 React. APK 는 EAS Build 또는 로컬 gradle. 푸시는 Expo Notifications (FCM 직접 설정보다 단순) |
| 앱 불필요 | `apps/mobile` 제거. 웹 하나 |

Flutter 는 경험자가 없어 기각. T1 의 "Flutter 확정" 은 이 문서로 대체한다.

## 6. 미결 ③ LLM 제공자 — 회사 API 형식 (S1 첫 주, PM)

확인할 것: ①OpenAI-compatible 엔드포인트인가 ②툴 콜링 지원 ③JSON 모드 지원 ④rate limit ⑤모델 목록(Llama 계열 포함 여부).
①이 아니면 어댑터 한 겹 추가. ②③ 둘 다 없으면 구조화 출력은 프롬프트 + 파서 + 재시도로 — 진단·개선안 품질 리스크라 **그땐 OpenRouter 로 전환**.

## 7. 아키텍처 문서에 담을 것 (BE 결정 후)

컴포넌트 경계 · 데이터 흐름(실행 → 로그 → 진단 → 승인 → 재실험) · Driver 인터페이스 · LLM 클라이언트 · 로그 스키마(드라이버 중립) · DB 스키마 초안 · API 표면 초안 · monorepo 디렉터리 · 로컬 실행(compose) · 배포 토폴로지 · A/B 선택 시 서비스 경계.
