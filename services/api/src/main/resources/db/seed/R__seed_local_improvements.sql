-- 로컬 전용 개선안 예시 (GACA-192). local 프로필일 때만 Flyway 가 적용한다 (application-local.yml).
-- agent 가 개선안을 저장하기 전에도 개선안 목록 · 상세 · 다음 회차 승인 화면을 만들 수 있게, test@uxight.com(R__seed_local)의
-- loop 실험(최대 3회차) 하나 — done 1회차 · 진단 2건 · 개선안 3안 — 을 넣는다. 실험 상태는 '승인 대기'다.
-- 로그인 test@uxight.com / test1234 → 실험 목록의 '[seed] 개선안 예시 쇼핑몰'.
-- 한 번 승인하면 다음 회차가 생겨 이 seed 는 더 승인할 수 없다(이 파일은 행을 지우지 않는다 — 초기화는 `docker compose down -v`).
-- 다시 적용해도 같은 결과가 되도록 행이 없을 때만 넣고, ID 는 제목 · 이름으로 찾아 세션 변수로 잇는다(R__seed_local_findings 와 같은 방식).

INSERT INTO projects (user_id, title, target_url, description, allowed_domains)
SELECT 1, '[seed] 개선안 예시 쇼핑몰', 'https://shop.example.com', '개선안 목록 · 상세 · 다음 회차 승인 확인용 seed',
       JSON_ARRAY('shop.example.com')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM projects WHERE user_id = 1 AND title = '[seed] 개선안 예시 쇼핑몰');
SET @imp_project = (SELECT MIN(project_id) FROM projects WHERE user_id = 1 AND title = '[seed] 개선안 예시 쇼핑몰');

INSERT INTO personas (user_id, name, profile)
SELECT 1, '[seed] 모바일 초보',
       JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low', 'background', '휴대폰으로만 쇼핑한다')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM personas WHERE user_id = 1 AND name = '[seed] 모바일 초보');
SET @imp_persona = (SELECT MIN(persona_id) FROM personas WHERE user_id = 1 AND name = '[seed] 모바일 초보');

INSERT INTO tasks (project_id, goal, success_rule, success_url, is_one_shot)
SELECT @imp_project, '쿠폰을 적용해 결제 페이지까지 간다', '[seed] 결제 페이지에 도달', 'https://shop.example.com/checkout', FALSE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE project_id = @imp_project);
SET @imp_task = (SELECT MIN(task_id) FROM tasks WHERE project_id = @imp_project);

INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, task_snapshot,
                  policy_snapshot, persona_snapshot, dispatch_state, cancel_requested, status, progress, tokens, cost_usd,
                  accepted_at, started_at, finished_at)
SELECT @imp_project, @imp_task, 'loop', 3, 'https://shop.example.com', JSON_ARRAY('shop.example.com'),
       JSON_OBJECT('task_id', @imp_task, 'goal', '쿠폰을 적용해 결제 페이지까지 간다', 'success_rule', '[seed] 결제 페이지에 도달',
                   'success_url', 'https://shop.example.com/checkout', 'is_one_shot', FALSE),
       JSON_OBJECT('max_steps', 10, 'max_seconds', 120, 'max_tokens', 20000),
       JSON_ARRAY(JSON_OBJECT('persona_id', @imp_persona, 'name', '[seed] 모바일 초보',
                              'profile', JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low',
                                                     'background', '휴대폰으로만 쇼핑한다'))),
       'sent', FALSE, 'done', 1, 3800, 0.0380,
       NOW() - INTERVAL 20 MINUTE, NOW() - INTERVAL 20 MINUTE, NOW() - INTERVAL 16 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM runs WHERE task_id = @imp_task);
SET @imp_run = (SELECT MIN(run_id) FROM runs WHERE task_id = @imp_task);
UPDATE runs SET first_run_id = run_id WHERE run_id = @imp_run AND first_run_id IS NULL;

INSERT INTO run_personas (run_id, persona_id, status, url_reached, steps, backtracks, tokens, cost_usd, log_path,
                          started_at, finished_at)
SELECT @imp_run, @imp_persona, 'max_steps', FALSE, 10, 2, 3800, 0.0380,
       CONCAT(@imp_run, '/', @imp_persona, '/steps.jsonl'), NOW() - INTERVAL 20 MINUTE, NOW() - INTERVAL 16 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_personas WHERE run_id = @imp_run);

INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd)
SELECT @imp_run, 0.00, 10.00, 2.00, 240.00, 3800, 0.0380
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_metrics WHERE run_id = @imp_run);

-- 진단 2건
INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @imp_run, 'interaction_failure', 'high',
       JSON_ARRAY(JSON_OBJECT('persona_id', @imp_persona, 'step_from', 3, 'step_to', 5,
                              'url', 'https://shop.example.com/cart')),
       '쿠폰 입력칸이 접힌 메뉴 안에 있어 세 번 만에 찾았다.'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM findings WHERE run_id = @imp_run);
INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @imp_run, 'task_failure', 'high',
       JSON_ARRAY(JSON_OBJECT('persona_id', @imp_persona, 'step_from', 6, 'step_to', 10,
                              'url', 'https://shop.example.com/cart')),
       '“적용” 버튼 문구가 모호해 쿠폰을 적용하지 못하고 결제로 넘어가지 못했다.'
  FROM DUAL
 WHERE (SELECT COUNT(*) FROM findings WHERE run_id = @imp_run) = 1;
SET @imp_finding_1 = (SELECT MIN(finding_id) FROM findings WHERE run_id = @imp_run);
SET @imp_finding_2 = (SELECT MAX(finding_id) FROM findings WHERE run_id = @imp_run);

-- 개선안 3안 — 패치 키는 snake_case
INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, rationale, expected_effect, fix_cost)
SELECT @imp_run, JSON_ARRAY(@imp_finding_2), 1, 'relabel',
       JSON_OBJECT('target', '#coupon-apply', 'new_text', '쿠폰 적용하기'),
       '버튼 문구 “적용”이 무엇을 적용하는지 드러나지 않는다.', '쿠폰 적용 단계의 망설임과 되돌아가기가 줄어든다.', 'low'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM improvements WHERE run_id = @imp_run AND option_no = 1);
INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, rationale, expected_effect, fix_cost)
SELECT @imp_run, JSON_ARRAY(@imp_finding_1, @imp_finding_2), 2, 'highlight',
       JSON_OBJECT('target', '#coupon-input', 'style', 'primary'),
       '쿠폰 입력칸이 다른 요소에 묻혀 눈에 띄지 않는다.', '쿠폰 입력칸을 찾는 시간이 줄어든다.', 'low'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM improvements WHERE run_id = @imp_run AND option_no = 2);
INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, rationale, expected_effect, fix_cost)
SELECT @imp_run, JSON_ARRAY(@imp_finding_1), 3, 'help_text',
       JSON_OBJECT('target', '#coupon-menu', 'text', '쿠폰은 여기에서 입력할 수 있어요'),
       '쿠폰 입력 위치를 알려 주는 안내가 없다.', '처음 쓰는 사용자도 쿠폰 메뉴를 바로 연다.', 'medium'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM improvements WHERE run_id = @imp_run AND option_no = 3);
