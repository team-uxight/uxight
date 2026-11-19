-- GACA-196 샘플 데이터 — dev 서버 DB 에 한 번 넣는다. Flyway 경로 밖이라 앱이 기동할 때는 적용되지 않는다.
-- 실행: mysql --default-character-set=utf8mb4 -u root -p uxight < seed-sample.sql   (README.md 참고)
--
-- 무엇을 넣나
--   설정 계층(users · projects · tasks · test_accounts)은 30건씩 고정으로 넣는다.
--   실행 계층(runs · run_personas · run_metrics · findings · improvements · approvals · patch_versions)과
--   personas · refresh_tokens · audit_log 는 30건에 모자란 만큼만 넣는다 — 실제 실험을 먼저 돌리고 이 파일을 실행한다.
--   policies(전역 정책 1행)와 flyway_schema_history 는 건드리지 않는다.
--
-- 지키는 것
--   - 샘플 계정은 모두 예약 도메인 sample.uxight.example 의 이메일이다. 실존 인물 · 주소가 아니다.
--   - 샘플 계정은 로그인할 수 없다. password_hash 가 BCrypt 꼴이 아니라 BCryptPasswordEncoder 가 항상 불일치로 본다.
--     refresh 토큰도 무작위 값의 해시이고 이미 만료됐다.
--   - 샘플 회차는 모두 status='done' 이다. queued · accepted · running 을 넣으면 AI 모듈이 집어 가 실행한다.
--     step 로그 · 스크린샷 파일은 없어 log_path 는 NULL 이다.
--   - 테스트 계정은 샘플 프로젝트(21~30번)에만 단다. secret_enc 는 앱 키로 암호화한 값이 아니라 무작위 바이트라 복호화되지 않는다.
--   - 다시 실행해도 결과가 같다. 이미 있는 샘플 행은 건너뛰고, 모자란 건수가 0 이면 아무것도 넣지 않는다.

SET NAMES utf8mb4;
SET @sample_domain = 'sample.uxight.example';
SET @target = 30;

-- ───────── 재료 (이 세션에서만 쓰는 임시 표) ─────────

DROP TEMPORARY TABLE IF EXISTS sample_users;
CREATE TEMPORARY TABLE sample_users (
  n            INT PRIMARY KEY,   -- 1~20: 로그인 없는 사이트(샘플 실험은 1~10번 프로젝트에서), 21~30: 로그인이 필요한 사이트(테스트 계정 3개씩)
  local_part   VARCHAR(50)  NOT NULL,
  name         VARCHAR(50)  NOT NULL,
  role         VARCHAR(20)  NOT NULL,
  provider     VARCHAR(10)  NOT NULL,
  is_active    BOOLEAN      NOT NULL,
  title        VARCHAR(100) NOT NULL,
  host         VARCHAR(100) NOT NULL,
  description  VARCHAR(255) NOT NULL,
  goal         VARCHAR(200) NOT NULL,
  success_path VARCHAR(100) NOT NULL
);
INSERT INTO sample_users VALUES
  ( 1, 'minji.kim',      '김민지', 'researcher', 'local',  TRUE,  '하늘마트 온라인몰',       'www.haneulmart.example',       '장보기 쇼핑몰의 쿠폰 · 주문 흐름 점검',       '할인 쿠폰을 적용할 수 있는 주문서 화면까지 간다',     '/order/checkout'),
  ( 2, 'seojun.lee',     '이서준', 'researcher', 'local',  TRUE,  '바로배송 장보기',         'www.barobaesong.example',      '새벽 배송 안내 페이지 점검',                  '우리 동네가 새벽 배송 가능 지역인지 확인한다',        '/delivery/area'),
  ( 3, 'jiwoo.park',     '박지우', 'researcher', 'local',  TRUE,  '오늘의집수리 예약',       'www.repairtoday.example',      '가전 청소 예약 화면의 날짜 선택 점검',        '에어컨 청소를 예약할 수 있는 날짜를 찾는다',          '/booking/calendar'),
  ( 4, 'hayoon.choi',    '최하윤', 'researcher', 'local',  TRUE,  '한빛시립도서관',          'lib.hanbitcity.example',       '도서관 이용 안내 메뉴 구조 점검',             '열람실 운영 시간을 찾는다',                           '/guide/reading-room'),
  ( 5, 'doyoon.jung',    '정도윤', 'researcher', 'google', TRUE,  '새봄치과',                'www.saebomdental.example',     '병원 진료 시간 안내 점검',                    '토요일 진료 시간을 확인한다',                         '/info/hours'),
  ( 6, 'seoyeon.kang',   '강서연', 'researcher', 'local',  TRUE,  '푸른숲캠핑 예약',         'www.pureunsup-camp.example',   '캠핑장 빈자리 조회 흐름 점검',                '8월 둘째 주에 비어 있는 캠핑 사이트를 찾는다',        '/reserve/availability'),
  ( 7, 'yejun.cho',      '조예준', 'researcher', 'local',  TRUE,  '다온구청 민원 안내',      'www.daon-gu.example',          '구청 민원 안내 메뉴 점검',                    '전입신고에 필요한 서류를 찾는다',                     '/civil/move-in'),
  ( 8, 'jimin.yoon',     '윤지민', 'researcher', 'local',  TRUE,  '별빛영화관',              'www.byeolbit-cinema.example',  '영화관 할인 이벤트 안내 점검',                '조조 영화 할인 조건을 찾는다',                        '/event/morning'),
  ( 9, 'sua.jang',       '장수아', 'researcher', 'local',  TRUE,  '모아카드 고객센터',       'www.moacard.example',          '카드사 고객센터 안내 점검',                   '카드 분실 신고 전화번호를 찾는다',                    '/support/lost'),
  (10, 'siwoo.lim',      '임시우', 'researcher', 'local',  TRUE,  '누리항공',                'www.nuriair.example',          '항공사 수하물 규정 안내 점검',                '기내 수하물 무게 제한을 찾는다',                      '/travel/baggage'),
  (11, 'chaewon.oh',     '오채원', 'researcher', 'local',  TRUE,  '마음편한보험',            'www.maeumins.example',         '보험 상품 비교 화면 점검',                    '여행자 보험의 보장 내용을 찾는다',                    '/products/travel'),
  (12, 'gunwoo.seo',     '서건우', 'researcher', 'google', TRUE,  '가람대학교 입학처',       'admission.garam.example',      '대학 입학처 모집 일정 안내 점검',             '수시 모집 원서 접수 기간을 찾는다',                   '/susi/schedule'),
  (13, 'yuna.shin',      '신유나', 'researcher', 'local',  TRUE,  '온새미 중고거래',         'www.onsaemi.example',          '중고거래 도움말 메뉴 점검',                   '안전결제 수수료를 확인한다',                          '/help/safe-pay'),
  (14, 'hyunwoo.kwon',   '권현우', 'researcher', 'local',  TRUE,  '해솔헬스장',              'www.haesolfit.example',        '헬스장 가격 안내 점검',                       'PT 체험권 가격을 찾는다',                             '/price/pt'),
  (15, 'daeun.hwang',    '황다은', 'researcher', 'local',  TRUE,  '한결부동산',              'www.hangyeol-realty.example',  '부동산 매물 검색 흐름 점검',                  '역세권 원룸 매물 목록을 연다',                        '/search/oneroom'),
  (16, 'junseo.ahn',     '안준서', 'researcher', 'local',  TRUE,  '꿈나무어린이집',          'www.kkumnamu.example',         '어린이집 입소 안내 점검',                     '입소 대기 신청 방법을 찾는다',                        '/admission/waitlist'),
  (17, 'haeun.song',     '송하은', 'researcher', 'local',  FALSE, '바다여행사',              'www.badatour.example',         '여행 패키지 가격 안내 점검',                  '제주 2박 3일 패키지 가격을 찾는다',                   '/package/jeju'),
  (18, 'eunwoo.ryu',     '류은우', 'researcher', 'local',  TRUE,  '미소동물병원',            'www.misovet.example',          '동물병원 진료비 안내 점검',                   '고양이 예방접종 비용을 찾는다',                       '/price/vaccine'),
  (19, 'soyul.jeon',     '전소율', 'researcher', 'google', TRUE,  '청년일자리센터',          'www.youthjob.example',         '청년 지원 사업 안내 점검',                    '청년 구직 지원금 신청 자격을 찾는다',                 '/support/eligibility'),
  (20, 'minjae.hong',    '홍민재', 'researcher', 'local',  TRUE,  '우리동네 체육센터',       'www.sports-center.example',    '체육센터 강습 안내 점검',                     '수영 강습 시간표를 찾는다',                           '/program/swim'),
  (21, 'nayeon.ko',      '고나연', 'researcher', 'local',  TRUE,  '하늘마트 판매자센터',     'seller.haneulmart.example',    '판매자 로그인 뒤 정산 메뉴 점검',             '로그인한 뒤 이번 달 정산 예정 금액을 찾는다',         '/settlement/summary'),
  (22, 'taeyoon.moon',   '문태윤', 'researcher', 'local',  TRUE,  '가람대학교 학생포털',     'portal.garam.example',         '학생 포털 수강 메뉴 점검',                    '로그인한 뒤 이번 학기 수강 신청 내역을 연다',         '/course/registered'),
  (23, 'seoa.yang',      '양서아', 'researcher', 'local',  TRUE,  '모아카드 마이페이지',     'my.moacard.example',           '카드 명세서 조회 흐름 점검',                  '로그인한 뒤 이번 달 결제 예정 금액을 찾는다',         '/bill/upcoming'),
  (24, 'jian.son',       '손지안', 'researcher', 'google', TRUE,  '누리항공 마이페이지',     'my.nuriair.example',           '항공 마일리지 조회 흐름 점검',                '로그인한 뒤 마일리지 잔액을 확인한다',                '/mileage'),
  (25, 'seunghyun.bae',  '배승현', 'researcher', 'local',  TRUE,  '한빛도서관 내 서재',      'my.lib.hanbitcity.example',    '도서관 대출 현황 화면 점검',                  '로그인한 뒤 대출 중인 책의 반납일을 찾는다',          '/loans'),
  (26, 'yoonseo.baek',   '백윤서', 'researcher', 'local',  TRUE,  '바로배송 내 주문',        'my.barobaesong.example',       '주문 배송 조회 흐름 점검',                    '로그인한 뒤 최근 주문의 배송 상태를 확인한다',        '/orders/recent'),
  (27, 'dohyun.heo',     '허도현', 'researcher', 'local',  FALSE, '해솔헬스장 회원센터',     'member.haesolfit.example',     '헬스장 회원권 조회 화면 점검',                '로그인한 뒤 남은 PT 횟수를 확인한다',                 '/membership'),
  (28, 'gaeun.nam',      '남가은', 'researcher', 'local',  TRUE,  '마음편한보험 내 계약',    'my.maeumins.example',          '보험 계약 조회 화면 점검',                    '로그인한 뒤 가입한 보험의 만기일을 찾는다',           '/contracts'),
  (29, 'jaemin.noh',     '노재민', 'maintainer', 'local',  TRUE,  '청년일자리센터 내 신청',  'my.youthjob.example',          '지원금 신청 현황 화면 점검',                  '로그인한 뒤 지원금 신청 진행 상태를 확인한다',        '/applications'),
  (30, 'yerin.choi',     '최예린', 'maintainer', 'local',  TRUE,  '별빛영화관 내 예매',      'my.byeolbit-cinema.example',   '영화 예매 내역 화면 점검',                    '로그인한 뒤 예매 내역에서 좌석 번호를 찾는다',        '/tickets');

DROP TEMPORARY TABLE IF EXISTS sample_personas;
CREATE TEMPORARY TABLE sample_personas (
  i          INT PRIMARY KEY,
  owner_n    INT          NOT NULL,   -- sample_users.n — 1~10번 계정이 3명씩 가진다
  name       VARCHAR(100) NOT NULL,
  web_skill  VARCHAR(10)  NOT NULL,
  device     VARCHAR(10)  NOT NULL,
  domain     VARCHAR(10)  NOT NULL,
  patience   VARCHAR(10)  NOT NULL,
  background VARCHAR(255) NOT NULL
);
INSERT INTO sample_personas VALUES
  ( 1,  1, '퇴근길 모바일 장보기',     'medium', 'mobile',  'mid',  'low',    '퇴근길 지하철에서 휴대폰으로 장을 본다. 쿠폰은 챙기지만 오래 찾지는 않는다.'),
  ( 2,  1, '처음 온라인 장보기',       'low',    'mobile',  'low',  'medium', '마트에서만 장을 보다 처음 앱으로 주문해 본다.'),
  ( 3,  1, '알뜰 비교 쇼핑',           'high',   'desktop', 'high', 'high',   '여러 쇼핑몰의 가격과 쿠폰을 비교한 뒤에 주문한다.'),
  ( 4,  2, '새벽 배송 첫 이용',        'medium', 'mobile',  'low',  'medium', '맞벌이라 새벽 배송을 처음 알아본다.'),
  ( 5,  2, '부모님 대신 주문',         'low',    'desktop', 'low',  'high',   '부모님 집으로 보낼 장보기를 대신 주문하려 한다.'),
  ( 6,  2, '배송 지역 확인만',         'high',   'mobile',  'mid',  'low',    '이사 갈 동네에서 새벽 배송이 되는지만 빠르게 확인하려 한다.'),
  ( 7,  3, '가전 관리 무관심',         'low',    'mobile',  'low',  'low',    '에어컨 청소를 해 본 적이 없어 무엇을 골라야 할지 모른다.'),
  ( 8,  3, '주말만 되는 직장인',       'medium', 'desktop', 'mid',  'medium', '평일에는 집에 없어 주말 예약 가능 날짜만 찾는다.'),
  ( 9,  3, '예약 앱 능숙자',           'high',   'mobile',  'high', 'medium', '여러 예약 앱을 써 봐서 달력 화면에 익숙하다.'),
  (10,  4, '시험 준비 대학생',         'medium', 'mobile',  'mid',  'low',    '시험 기간에 열람실 자리를 찾는다.'),
  (11,  4, '은퇴 후 독서가',           'low',    'desktop', 'mid',  'high',   '은퇴 뒤 도서관을 자주 찾지만 홈페이지는 낯설다.'),
  (12,  4, '사서 경험자',              'high',   'desktop', 'high', 'high',   '다른 도서관에서 일해 봐서 메뉴 이름에 익숙하다.'),
  (13,  5, '치과 공포 직장인',         'medium', 'mobile',  'low',  'low',    '점심시간에 짧게 진료 시간만 확인하려 한다.'),
  (14,  5, '아이 진료 보호자',         'medium', 'desktop', 'low',  'medium', '아이 치과 진료를 토요일에 받을 수 있는지 알아본다.'),
  (15,  5, '고령 환자',                'low',    'mobile',  'low',  'high',   '글자가 작으면 읽기 힘들어 큰 버튼만 누른다.'),
  (16,  6, '초보 캠퍼',                'low',    'mobile',  'low',  'medium', '캠핑을 처음 가 보려고 빈자리를 알아본다.'),
  (17,  6, '주말 캠핑 마니아',         'high',   'desktop', 'high', 'low',    '매달 캠핑을 가서 빈자리가 나면 바로 예약한다.'),
  (18,  6, '가족 여행 계획자',         'medium', 'desktop', 'mid',  'high',   '여름휴가 일정에 맞춰 가족이 묵을 자리를 찾는다.'),
  (19,  7, '이사 온 청년',             'medium', 'mobile',  'low',  'medium', '처음 이사해 전입신고를 해 본 적이 없다.'),
  (20,  7, '민원 대행 경험자',         'high',   'desktop', 'high', 'medium', '회사 일로 민원 서류를 자주 떼 봤다.'),
  (21,  7, '어르신 민원인',            'low',    'desktop', 'low',  'high',   '구청에 가기 전에 필요한 서류를 미리 알아 두려 한다.'),
  (22,  8, '조조 영화 애호가',         'medium', 'mobile',  'high', 'low',    '아침 영화를 자주 봐서 할인 조건만 확인한다.'),
  (23,  8, '데이트 준비 대학생',       'medium', 'mobile',  'mid',  'medium', '주말 데이트로 영화를 싸게 볼 방법을 찾는다.'),
  (24,  8, '영화관 앱 미사용자',       'low',    'desktop', 'low',  'high',   '영화관 홈페이지를 처음 써 본다.'),
  (25,  9, '카드 분실 직후',           'medium', 'mobile',  'low',  'low',    '방금 카드를 잃어버려 급하게 신고 번호를 찾는다.'),
  (26,  9, '해외 출장 중',             'high',   'mobile',  'mid',  'low',    '해외에서 카드를 잃어버려 해외 신고 번호가 필요하다.'),
  (27,  9, '전화 문의 선호',           'low',    'desktop', 'low',  'medium', '인터넷보다 전화로 처리하는 게 편하다.'),
  (28, 10, '첫 해외여행',              'low',    'mobile',  'low',  'medium', '처음 비행기를 타서 수하물 규정을 모른다.'),
  (29, 10, '출장 잦은 직장인',         'high',   'desktop', 'high', 'low',    '출장이 잦아 규정이 바뀌었는지만 빠르게 확인한다.'),
  (30, 10, '유모차 동반 여행객',       'medium', 'mobile',  'mid',  'high',   '아이와 함께 타서 유모차 · 기내 수하물 규정을 꼼꼼히 본다.');

DROP TEMPORARY TABLE IF EXISTS sample_finding_templates;
CREATE TEMPORARY TABLE sample_finding_templates (
  id       INT PRIMARY KEY,
  taxonomy VARCHAR(30)  NOT NULL,
  severity VARCHAR(10)  NOT NULL,
  summary  VARCHAR(255) NOT NULL
);
INSERT INTO sample_finding_templates VALUES
  (1, 'navigation_confusion', 'high',   '상단 메뉴에서 같은 하위 메뉴를 세 번 오가며 목표 화면으로 가는 길을 찾지 못했다.'),
  (2, 'interaction_failure',  'medium', '‘자세히 보기’ 버튼이 배너에 가려 두 번 눌렀지만 화면이 바뀌지 않았다.'),
  (3, 'task_failure',         'high',   '목표 정보가 있는 탭을 지나쳐 정해진 단계 안에 과업을 끝내지 못했다.'),
  (4, 'excessive_steps',      'medium', '목표 화면에는 도달했지만 사이트맵과 검색을 거치느라 다른 Persona 보다 여섯 단계를 더 썼다.'),
  (5, 'navigation_confusion', 'medium', '‘이용 안내’와 ‘고객 지원’ 메뉴의 차이가 분명하지 않아 두 메뉴를 번갈아 열었다.'),
  (6, 'interaction_failure',  'low',    '모바일 화면에서 접힌 메뉴 버튼을 찾는 데 두 단계가 더 걸렸다.'),
  (7, 'excessive_steps',      'low',    '검색 결과 첫 화면에 목표 항목이 없어 다음 쪽으로 두 번 넘겼다.'),
  (8, 'task_failure',         'medium', '안내 팝업을 닫는 버튼을 찾지 못해 목표 화면으로 넘어가지 못했다.');

DROP TEMPORARY TABLE IF EXISTS sample_improvement_templates;
CREATE TEMPORARY TABLE sample_improvement_templates (
  id              INT PRIMARY KEY,
  patch_kind      VARCHAR(20)  NOT NULL,
  patch           JSON         NOT NULL,   -- AI 모듈이 저장하는 모양(snake_case). page_url 은 넣을 때 붙인다
  rationale       VARCHAR(255) NOT NULL,
  expected_effect VARCHAR(255) NOT NULL    -- AI 모듈의 EFFECT_TEMPLATES 문장
);
INSERT INTO sample_improvement_templates VALUES
  (1, 'relabel',   '{"target": "#gnb .menu-guide", "new_text": "이용 안내 · 운영 시간"}',
      '메뉴 이름만으로 어떤 정보가 있는지 짐작하기 어려워 Persona 가 다른 메뉴를 먼저 열었다.',
      '탐색 중 이전 페이지나 단계로 되돌아가는 행동이 줄어들 것으로 기대된다.'),
  (2, 'highlight', '{"target": "#main .quick-link", "style": "outline"}',
      '목표 화면으로 가는 바로가기가 배너 사이에 묻혀 눈에 띄지 않았다.',
      '해당 과제를 완료하는 데 필요한 탐색 단계가 줄어들 것으로 기대된다.'),
  (3, 'help_text', '{"target": "#search-box", "text": "찾는 내용을 두 낱말 이내로 넣어 보세요"}',
      '검색어를 길게 넣은 Persona 가 결과를 찾지 못하고 검색을 되풀이했다.',
      '해당 과제를 성공적으로 완료하는 사용자 비율이 높아질 것으로 기대된다.'),
  (4, 'move',      '{"target": "#content .tab-detail", "destination": "#content .tab-list", "position": "first"}',
      '목표 정보가 있는 탭이 맨 뒤에 있어 Persona 가 다른 탭을 먼저 확인했다.',
      '해당 과제를 완료하는 데 필요한 탐색 단계가 줄어들 것으로 기대된다.'),
  (5, 'relabel',   '{"target": ".btn-more", "new_text": "운영 시간 자세히 보기"}',
      '‘자세히 보기’ 버튼이 무엇을 여는지 드러나지 않아 Persona 가 누르지 않고 지나쳤다.',
      '탐색 중 이전 페이지나 단계로 되돌아가는 행동이 줄어들 것으로 기대된다.'),
  (6, 'highlight', '{"target": ".popup .btn-close", "style": "background"}',
      '팝업 닫기 버튼이 배경과 비슷한 색이라 Persona 가 찾지 못했다.',
      '해당 과제를 성공적으로 완료하는 사용자 비율이 높아질 것으로 기대된다.');

-- ───────── 샘플 실험 1개를 넣는 프로시저 (끝에서 지운다) ─────────
-- 샘플 실험 1개 = loop 실험(최대 3회차) — 1 · 2회차는 진단 2건 · 개선안 3안 · 3안과 2안을 반려한 뒤 1안 승인,
-- 3회차는 진단 1건이고 개선안이 없어 실험이 완료된다. 2 · 3회차는 그때까지 승인한 패치를 누적해 주입한 기록(patch_versions)을 가진다.
-- 실험 1개가 만드는 행: runs 3 · run_personas 9 · run_metrics 3 · findings 5 · improvements 6 · approvals 6 · patch_versions 3 · audit_log 6

DROP PROCEDURE IF EXISTS uxight_seed_sample_experiments;
DELIMITER //
CREATE PROCEDURE uxight_seed_sample_experiments(IN p_count INT)
BEGIN
  DECLARE k INT DEFAULT 1;
  DECLARE r INT;
  DECLARE p INT;
  DECLARE j INT;
  DECLARE v_n INT;
  DECLARE v_owner, v_project, v_task, v_run, v_first, v_prev, v_approved, v_imp_r1, v_imp_r2 BIGINT;
  DECLARE v_p1, v_p2, v_p3, v_persona, v_f1, v_f2, v_i1, v_i2, v_i3 BIGINT;
  DECLARE v_host, v_success_path VARCHAR(100);
  DECLARE v_target_url VARCHAR(2048);
  DECLARE v_domains, v_task_snap, v_policy_snap, v_persona_snap JSON;
  DECLARE v_max_steps INT;
  DECLARE v_t, v_started, v_done, v_decide DATETIME;
  DECLARE v_status VARCHAR(20);
  DECLARE v_reached BOOLEAN;
  DECLARE v_steps, v_back INT;
  DECLARE v_tokens BIGINT;
  DECLARE v_cost DECIMAL(10,4);
  DECLARE v_note_reject, v_note_approve VARCHAR(255);

  -- 정책 스냅샷 — Policy.toSnapshot 과 같은 키(daily_token_budget 은 넣지 않는다)
  SELECT COALESCE(max_steps, 20),
         IF(model_map IS NULL,
            JSON_OBJECT('max_steps', max_steps, 'max_seconds', max_seconds, 'max_tokens', max_tokens,
                        'run_concurrency', run_concurrency, 'persona_concurrency', persona_concurrency,
                        'rate_limit_per_domain', rate_limit_per_domain),
            JSON_OBJECT('max_steps', max_steps, 'max_seconds', max_seconds, 'max_tokens', max_tokens,
                        'run_concurrency', run_concurrency, 'persona_concurrency', persona_concurrency,
                        'rate_limit_per_domain', rate_limit_per_domain, 'model_map', model_map))
    INTO v_max_steps, v_policy_snap
    FROM policies ORDER BY policy_id LIMIT 1;

  experiments: WHILE k <= p_count DO
    -- 아직 회차가 없는 샘플 프로젝트(1~10번) 중 가장 앞 번호
    SET v_n = NULL;
    SELECT s.n, u.user_id, pr.project_id, s.host, s.success_path, pr.target_url, pr.allowed_domains
      INTO v_n, v_owner, v_project, v_host, v_success_path, v_target_url, v_domains
      FROM sample_users s
      JOIN users u ON u.email = CONCAT(s.local_part, '@', @sample_domain)
      JOIN projects pr ON pr.user_id = u.user_id AND pr.title = s.title
     WHERE s.n <= 10
       AND NOT EXISTS (SELECT 1 FROM runs x WHERE x.project_id = pr.project_id)
     ORDER BY s.n LIMIT 1;
    IF v_n IS NULL THEN
      LEAVE experiments;
    END IF;

    SELECT task_id, JSON_OBJECT('task_id', task_id, 'goal', goal, 'success_rule', success_rule,
                                'success_url', success_url, 'is_one_shot', CAST('false' AS JSON))
      INTO v_task, v_task_snap
      FROM tasks WHERE project_id = v_project ORDER BY task_id LIMIT 1;

    -- 이 계정의 샘플 Persona 3명 (없으면 만든다)
    INSERT INTO personas (user_id, name, profile, created_at, updated_at)
    SELECT v_owner, ps.name,
           JSON_OBJECT('webSkill', ps.web_skill, 'device', ps.device, 'domainKnowledge', ps.domain,
                       'patience', ps.patience, 'background', ps.background),
           NOW() - INTERVAL 28 DAY + INTERVAL ps.i HOUR, NOW() - INTERVAL 28 DAY + INTERVAL ps.i HOUR
      FROM sample_personas ps
     WHERE ps.owner_n = v_n
       AND NOT EXISTS (SELECT 1 FROM personas x WHERE x.user_id = v_owner AND x.name = ps.name);
    SELECT persona_id INTO v_p1 FROM personas
     WHERE user_id = v_owner AND deleted_at IS NULL ORDER BY persona_id LIMIT 1 OFFSET 0;
    SELECT persona_id INTO v_p2 FROM personas
     WHERE user_id = v_owner AND deleted_at IS NULL ORDER BY persona_id LIMIT 1 OFFSET 1;
    SELECT persona_id INTO v_p3 FROM personas
     WHERE user_id = v_owner AND deleted_at IS NULL ORDER BY persona_id LIMIT 1 OFFSET 2;
    SELECT JSON_ARRAYAGG(JSON_OBJECT('persona_id', persona_id, 'name', name, 'profile', profile))
      INTO v_persona_snap
      FROM personas WHERE persona_id IN (v_p1, v_p2, v_p3);

    -- 실험 k 는 (2 + 2k)일 전 오전에 시작한다
    SET v_t = TIMESTAMP(CURDATE() - INTERVAL (2 + 2 * k) DAY, MAKETIME(9 + k % 7, (k * 17) % 60, 0));
    SET v_first = NULL, v_prev = NULL, v_approved = NULL, v_imp_r1 = NULL, v_imp_r2 = NULL;

    SET r = 1;
    WHILE r <= 3 DO
      INSERT INTO runs (project_id, task_id, mode, loop_max, parent_run_id, first_run_id, improvement_id,
                        target_url_snapshot, allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot,
                        dispatch_state, cancel_requested, status, progress, accepted_at, started_at, created_at)
      VALUES (v_project, v_task, 'loop', 3, v_prev, v_first, v_approved,
              v_target_url, v_domains, v_task_snap, v_policy_snap, v_persona_snap,
              'sent', FALSE, 'done', 3, v_t - INTERVAL 2 SECOND, v_t, v_t - INTERVAL 5 SECOND);
      SET v_run = LAST_INSERT_ID();
      IF r = 1 THEN
        SET v_first = v_run;
        UPDATE runs SET first_run_id = v_run WHERE run_id = v_run;
      ELSE
        -- 직전 회차의 승인 감사 로그 — nextRunId 가 이 회차다 (ImprovementService 와 같은 detail)
        INSERT INTO audit_log (actor, action, target, detail, ts)
        VALUES (CONCAT('user:', v_owner), 'run.approve', CONCAT('improvement:', v_approved),
                JSON_OBJECT('runId', v_prev, 'nextRunId', v_run, 'note', v_note_approve), v_decide);
        -- 그때까지 승인한 패치를 누적해 주입한 기록
        INSERT INTO patch_versions (run_id, improvement_id, patch_kind, patch, applied, fail_reason, created_at)
        SELECT v_run, improvement_id, patch_kind, patch,
               IF(r = 3 AND improvement_id = v_imp_r2 AND k % 3 = 0, FALSE, TRUE),
               IF(r = 3 AND improvement_id = v_imp_r2 AND k % 3 = 0, '대상 요소를 찾지 못했다', NULL),
               v_t + INTERVAL 3 SECOND
          FROM improvements WHERE improvement_id IN (v_imp_r1, v_imp_r2);
      END IF;

      -- Persona 3명의 결과 — 회차가 지날수록 나아진다
      SET p = 1;
      WHILE p <= 3 DO
        SET v_persona = ELT(p, v_p1, v_p2, v_p3);
        CASE r * 10 + p
          WHEN 11 THEN SET v_status = 'max_steps', v_reached = FALSE, v_steps = v_max_steps, v_back = 3;
          WHEN 12 THEN SET v_status = 'done', v_reached = TRUE, v_steps = 7, v_back = 2;
          WHEN 13 THEN SET v_status = IF(k % 2 = 0, 'stuck', 'fail'), v_reached = FALSE, v_steps = 5, v_back = 1;
          WHEN 21 THEN SET v_status = 'done', v_reached = TRUE, v_steps = 8, v_back = 2;
          WHEN 22 THEN SET v_status = 'done', v_reached = TRUE, v_steps = 6, v_back = 1;
          WHEN 23 THEN SET v_status = 'max_steps', v_reached = FALSE, v_steps = v_max_steps, v_back = 2;
          WHEN 31 THEN SET v_status = 'done', v_reached = TRUE, v_steps = 6, v_back = 1;
          WHEN 32 THEN SET v_status = 'done', v_reached = TRUE, v_steps = 5, v_back = 0;
          ELSE SET v_status = IF(k % 2 = 1, 'timeout', 'done'), v_reached = (k % 2 = 0), v_steps = 7, v_back = 1;
        END CASE;
        SET v_steps = LEAST(v_steps, v_max_steps);
        SET v_tokens = 3500 + v_steps * 1200 + p * 131 + k * 47;
        SET v_cost = ROUND(v_tokens * 0.00000013, 4);
        SET v_started = v_t + INTERVAL ((p - 1) * 15) SECOND;
        INSERT INTO run_personas (run_id, persona_id, status, url_reached, steps, backtracks, tokens, cost_usd, log_path,
                                  started_at, finished_at)
        VALUES (v_run, v_persona, v_status, v_reached, v_steps, v_back, v_tokens, v_cost, NULL,
                v_started, v_started + INTERVAL (v_steps * 22 + 18 + p * 3) SECOND);
        SET p = p + 1;
      END WHILE;

      SELECT SUM(tokens), SUM(cost_usd), MAX(finished_at) INTO v_tokens, v_cost, v_done
        FROM run_personas WHERE run_id = v_run;
      UPDATE runs SET tokens = v_tokens, cost_usd = v_cost, heartbeat_at = v_done, finished_at = v_done
       WHERE run_id = v_run;
      -- 성공률은 성공(done 이면서 도달)만 센다 (T42)
      INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd, created_at)
      SELECT v_run, ROUND(100 * SUM(status = 'done' AND url_reached) / COUNT(*), 2), ROUND(AVG(steps), 2),
             ROUND(AVG(backtracks), 2), ROUND(AVG(TIMESTAMPDIFF(SECOND, started_at, finished_at)), 2),
             SUM(tokens), SUM(cost_usd), v_done
        FROM run_personas WHERE run_id = v_run;

      -- 진단 — 1 · 2회차 2건, 3회차 1건. 근거는 결과가 나빴던 Persona
      SET j = 1;
      WHILE j <= IF(r < 3, 2, 1) DO
        INSERT INTO findings (run_id, taxonomy, severity, evidence, summary, created_at)
        SELECT v_run, ft.taxonomy, ft.severity,
               JSON_ARRAY(JSON_OBJECT('persona_id', IF(j = 1, v_p3, v_p1), 'step_from', 2, 'step_to', 4 + j,
                                      'url', CONCAT('https://', v_host, IF(j = 1, '/', v_success_path)))),
               ft.summary, v_done + INTERVAL j MINUTE
          FROM sample_finding_templates ft
         WHERE ft.id = (k + r * 3 + j) % 8 + 1;
        IF j = 1 THEN SET v_f1 = LAST_INSERT_ID(); ELSE SET v_f2 = LAST_INSERT_ID(); END IF;
        SET j = j + 1;
      END WHILE;

      IF r < 3 THEN
        -- 개선안 3안
        SET j = 1;
        WHILE j <= 3 DO
          INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, rationale, expected_effect,
                                    fix_cost, created_at)
          SELECT v_run, CASE j WHEN 1 THEN JSON_ARRAY(v_f1) WHEN 2 THEN JSON_ARRAY(v_f1, v_f2) ELSE JSON_ARRAY(v_f2) END,
                 j, it.patch_kind, JSON_SET(it.patch, '$.page_url', CONCAT('https://', v_host, v_success_path)),
                 it.rationale, it.expected_effect, NULL, v_done + INTERVAL 5 MINUTE
            FROM sample_improvement_templates it
           WHERE it.id = (k + r + j) % 6 + 1;
          CASE j WHEN 1 THEN SET v_i1 = LAST_INSERT_ID(); WHEN 2 THEN SET v_i2 = LAST_INSERT_ID();
                 ELSE SET v_i3 = LAST_INSERT_ID(); END CASE;
          SET j = j + 1;
        END WHILE;

        -- 3안 · 2안을 반려하고 1안을 승인한다 (승인하면 다음 회차가 생겨 더 결정할 수 없다)
        SET v_decide = v_done + INTERVAL (40 + k * 3) MINUTE;
        SET v_note_reject = ELT(k % 3 + 1, '1안과 같은 문제를 다뤄 효과가 큰 쪽만 보기로 함',
                                '다음 달 메뉴 개편 때 함께 바꿀 예정', '이번 과업과 관계가 적음');
        INSERT INTO approvals (improvement_id, user_id, decision, note, decided_at)
        VALUES (v_i3, v_owner, 'reject', v_note_reject, v_decide);
        INSERT INTO audit_log (actor, action, target, detail, ts)
        VALUES (CONCAT('user:', v_owner), 'run.reject', CONCAT('improvement:', v_i3),
                JSON_OBJECT('runId', v_run, 'nextRunId', NULL, 'note', v_note_reject), v_decide);
        SET v_decide = v_decide + INTERVAL 4 MINUTE;
        INSERT INTO approvals (improvement_id, user_id, decision, note, decided_at)
        VALUES (v_i2, v_owner, 'reject', NULL, v_decide);
        INSERT INTO audit_log (actor, action, target, detail, ts)
        VALUES (CONCAT('user:', v_owner), 'run.reject', CONCAT('improvement:', v_i2),
                JSON_OBJECT('runId', v_run, 'nextRunId', NULL, 'note', NULL), v_decide);
        SET v_decide = v_decide + INTERVAL 3 MINUTE;
        SET v_note_approve = IF(k % 2 = 0, NULL, '가장 적은 수정으로 확인할 수 있는 안');
        INSERT INTO approvals (improvement_id, user_id, decision, note, decided_at)
        VALUES (v_i1, v_owner, 'approve', v_note_approve, v_decide);

        IF r = 1 THEN SET v_imp_r1 = v_i1; ELSE SET v_imp_r2 = v_i1; END IF;
        SET v_approved = v_i1, v_prev = v_run, v_t = v_decide + INTERVAL 20 SECOND;
      END IF;
      SET r = r + 1;
    END WHILE;

    SET k = k + 1;
  END WHILE experiments;
END //
DELIMITER ;

START TRANSACTION;

-- ───────── 설정 계층 — 30건 고정 ─────────

-- 계정 — 로그인할 수 없는 값('!sample-no-login')을 password_hash 에 넣는다. google 계정의 google_sub 도 가짜 값이다.
INSERT INTO users (email, password_hash, auth_provider, google_sub, name, role, is_active, last_login_at, created_at, updated_at)
SELECT CONCAT(s.local_part, '@', @sample_domain),
       IF(s.provider = 'local', '!sample-no-login', NULL),
       s.provider,
       IF(s.provider = 'google', CONCAT('1048', LPAD(s.n * 7919, 17, '0')), NULL),
       s.name, s.role, s.is_active,
       IF(s.is_active, NOW() - INTERVAL (s.n % 9) DAY - INTERVAL (s.n * 37 % 600) MINUTE,
                       TIMESTAMP(CURDATE() - INTERVAL 15 DAY, MAKETIME(14, s.n, 0))),
       s.created, s.created
  FROM (SELECT su.*, TIMESTAMP(CURDATE() - INTERVAL IF(su.role = 'maintainer', 62 - su.n % 2, 58 - su.n) DAY,
                               MAKETIME(9 + su.n % 8, su.n * 13 % 60, 0)) AS created
          FROM sample_users su) s
 WHERE NOT EXISTS (SELECT 1 FROM users x WHERE x.email = CONCAT(s.local_part, '@', @sample_domain));

-- 프로젝트 — 계정당 1개, 대상은 예약 최상위 도메인(.example)
INSERT INTO projects (user_id, title, target_url, description, allowed_domains, created_at, updated_at)
SELECT u.user_id, s.title, CONCAT('https://', s.host, '/'), s.description, JSON_ARRAY(s.host),
       u.created_at + INTERVAL 1 DAY, u.created_at + INTERVAL 1 DAY
  FROM sample_users s
  JOIN users u ON u.email = CONCAT(s.local_part, '@', @sample_domain)
 WHERE NOT EXISTS (SELECT 1 FROM projects x WHERE x.user_id = u.user_id AND x.title = s.title);

-- Task — 프로젝트당 1개
INSERT INTO tasks (project_id, goal, success_rule, success_url, is_one_shot, created_at, updated_at)
SELECT pr.project_id, s.goal,
       CONCAT('주소가 ', s.success_path, ' 인 화면에 도달하고, 그 화면에 과업이 찾는 정보가 보이면 성공으로 본다.'),
       CONCAT('https://', s.host, s.success_path), FALSE,
       pr.created_at + INTERVAL 2 HOUR, pr.created_at + INTERVAL 2 HOUR
  FROM sample_users s
  JOIN users u ON u.email = CONCAT(s.local_part, '@', @sample_domain)
  JOIN projects pr ON pr.user_id = u.user_id AND pr.title = s.title
 WHERE NOT EXISTS (SELECT 1 FROM tasks x WHERE x.project_id = pr.project_id);

-- 테스트 계정 — 로그인이 필요한 샘플 프로젝트(21~30번)에 3개씩. secret_enc 는 복호화되지 않는 무작위 바이트
INSERT INTO test_accounts (project_id, login_id, secret_enc, assigned_run_id, created_at)
SELECT pr.project_id, CONCAT('qa_tester', LPAD(a.i, 2, '0')), RANDOM_BYTES(44), NULL,
       pr.created_at + INTERVAL (3 + a.i) HOUR
  FROM sample_users s
  JOIN users u ON u.email = CONCAT(s.local_part, '@', @sample_domain)
  JOIN projects pr ON pr.user_id = u.user_id AND pr.title = s.title
 CROSS JOIN (SELECT 1 AS i UNION ALL SELECT 2 UNION ALL SELECT 3) a
 WHERE s.n > 20
   AND NOT EXISTS (SELECT 1 FROM test_accounts x
                    WHERE x.project_id = pr.project_id AND x.login_id = CONCAT('qa_tester', LPAD(a.i, 2, '0')));

-- ───────── 실행 계층 — 모자란 만큼만 ─────────

-- 샘플 실험 수 = 표마다 (모자란 건수 ÷ 실험 1개가 만드는 행 수) 를 올림한 값 중 가장 큰 값. 최대 10개(1~10번 프로젝트)
SET @experiments = LEAST(10, GREATEST(0,
  CEIL((@target - (SELECT COUNT(*) FROM runs)) / 3),
  CEIL((@target - (SELECT COUNT(*) FROM run_personas)) / 9),
  CEIL((@target - (SELECT COUNT(*) FROM run_metrics)) / 3),
  CEIL((@target - (SELECT COUNT(*) FROM findings)) / 5),
  CEIL((@target - (SELECT COUNT(*) FROM improvements)) / 6),
  CEIL((@target - (SELECT COUNT(*) FROM approvals)) / 6),
  CEIL((@target - (SELECT COUNT(*) FROM patch_versions)) / 3)));
CALL uxight_seed_sample_experiments(@experiments);

-- Persona — 모자란 만큼 (샘플 실험에 쓴 Persona 가 먼저 들어가 있다)
SET @persona_gap = GREATEST(0, @target - (SELECT COUNT(*) FROM personas));
INSERT INTO personas (user_id, name, profile, created_at, updated_at)
SELECT c.user_id, c.name,
       JSON_OBJECT('webSkill', c.web_skill, 'device', c.device, 'domainKnowledge', c.domain,
                   'patience', c.patience, 'background', c.background),
       NOW() - INTERVAL 28 DAY + INTERVAL c.i HOUR, NOW() - INTERVAL 28 DAY + INTERVAL c.i HOUR
  FROM (SELECT ps.*, u.user_id, ROW_NUMBER() OVER (ORDER BY ps.i) AS rn
          FROM sample_personas ps
          JOIN sample_users s ON s.n = ps.owner_n
          JOIN users u ON u.email = CONCAT(s.local_part, '@', @sample_domain)
         WHERE NOT EXISTS (SELECT 1 FROM personas x WHERE x.user_id = u.user_id AND x.name = ps.name)) c
 WHERE c.rn <= @persona_gap;

-- refresh 토큰 — 모자란 만큼. 샘플 이메일 계정의 지난 로그인 기록이다. 무작위 값의 해시이고 모두 만료됐다(일부는 로그아웃으로 무효화)
SET @token_gap = GREATEST(0, @target - (SELECT COUNT(*) FROM refresh_tokens));
INSERT INTO refresh_tokens (user_id, token_hash, expires_at, revoked_at, created_at)
SELECT c.user_id, SHA2(HEX(RANDOM_BYTES(32)), 256), c.created_at + INTERVAL 14 DAY,
       IF(c.rn % 2 = 0, c.created_at + INTERVAL (2 + c.rn % 5) HOUR, NULL), c.created_at
  FROM (SELECT u.user_id,
               TIMESTAMP(CURDATE() - INTERVAL (16 + (u.user_id * 3 + a.i * 5) % 12) DAY,
                         MAKETIME(8 + u.user_id % 10, (u.user_id * 11 + a.i) % 60, 0)) AS created_at,
               ROW_NUMBER() OVER (ORDER BY a.i, u.user_id) AS rn
          FROM users u
         CROSS JOIN (SELECT 1 AS i UNION ALL SELECT 2) a
         WHERE u.email LIKE CONCAT('%@', @sample_domain) AND u.auth_provider = 'local') c
 WHERE c.rn <= @token_gap;

-- 감사 로그 — 모자란 만큼. 샘플 메인테이너가 샘플 리서처 계정을 만들고(user.create) 둘을 비활성화한(user.active_update) 기록
SELECT user_id INTO @maintainer_a FROM users WHERE email = CONCAT('jaemin.noh@', @sample_domain);
SELECT user_id INTO @maintainer_b FROM users WHERE email = CONCAT('yerin.choi@', @sample_domain);
SET @audit_gap = GREATEST(0, @target - (SELECT COUNT(*) FROM audit_log));
INSERT INTO audit_log (actor, action, target, detail, ts)
SELECT c.actor, c.action, c.target, c.detail, c.ts
  FROM (SELECT a.*, ROW_NUMBER() OVER (ORDER BY a.ts) AS rn
          FROM (SELECT CONCAT('user:', IF(u.user_id % 2 = 0, @maintainer_a, @maintainer_b)) AS actor,
                       'user.create' AS action, CONCAT('user:', u.user_id) AS target,
                       JSON_OBJECT('email', u.email, 'name', u.name, 'role', u.role) AS detail, u.created_at AS ts
                  FROM users u
                 WHERE u.email LIKE CONCAT('%@', @sample_domain) AND u.role = 'researcher'
                UNION ALL
                SELECT CONCAT('user:', @maintainer_a), 'user.active_update', CONCAT('user:', u.user_id),
                       JSON_OBJECT('before', CAST('true' AS JSON), 'after', CAST('false' AS JSON)),
                       TIMESTAMP(CURDATE() - INTERVAL 15 DAY, MAKETIME(17, u.user_id % 60, 0))
                  FROM users u
                 WHERE u.email LIKE CONCAT('%@', @sample_domain) AND u.is_active = FALSE) a
         WHERE NOT EXISTS (SELECT 1 FROM audit_log x WHERE x.action = a.action AND x.target = a.target)) c
 WHERE c.rn <= @audit_gap;

COMMIT;

DROP PROCEDURE IF EXISTS uxight_seed_sample_experiments;

-- ───────── 결과 — 표마다 건수 ─────────
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
UNION ALL SELECT 'policies (1행 설계)', COUNT(*) FROM policies
UNION ALL SELECT 'flyway_schema_history', COUNT(*) FROM flyway_schema_history;
