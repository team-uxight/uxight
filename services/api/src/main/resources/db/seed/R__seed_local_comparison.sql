-- 로컬 전용 결과 비교 예시 (GACA-215). local 프로필일 때만 Flyway 가 적용한다 (application-local.yml).
-- agent 없이는 승인한 다음 회차가 끝나지 않으므로, 결과(Before/After) 화면을 만들 수 있게 test@uxight.com(R__seed_local)의
-- loop 실험(최대 3회차) 하나 — 1회차 done(진단 1건 · 개선안 1안 승인) → 2회차 done(1안 패치 주입 성공) — 을 넣는다.
-- 2회차에 개선안이 없어 실험 상태는 '완료'다. step 로그 · 스크린샷 파일은 없어(Flyway 는 DB 만) screenshots 는 빈 목록이다.
-- 로그인 test@uxight.com / test1234 → 실험 목록의 '[seed] 결과 비교 예시 쇼핑몰' → 결과.
-- 다시 적용해도 같은 결과가 되도록 행이 없을 때만 넣고, ID 는 제목 · 이름으로 찾아 세션 변수로 잇는다(R__seed_local_improvements 와 같은 방식).

INSERT INTO projects (user_id, title, target_url, description, allowed_domains)
SELECT 1, '[seed] 결과 비교 예시 쇼핑몰', 'https://shop.example.com', '결과(Before/After) 비교 확인용 seed',
       JSON_ARRAY('shop.example.com')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM projects WHERE user_id = 1 AND title = '[seed] 결과 비교 예시 쇼핑몰');
SET @cmp_project = (SELECT MIN(project_id) FROM projects WHERE user_id = 1 AND title = '[seed] 결과 비교 예시 쇼핑몰');

INSERT INTO personas (user_id, name, profile)
SELECT 1, '[seed] 모바일 초보',
       JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low', 'background', '휴대폰으로만 쇼핑한다')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM personas WHERE user_id = 1 AND name = '[seed] 모바일 초보');
SET @cmp_persona = (SELECT MIN(persona_id) FROM personas WHERE user_id = 1 AND name = '[seed] 모바일 초보');

INSERT INTO tasks (project_id, goal, success_rule, success_url, is_one_shot)
SELECT @cmp_project, '쿠폰을 적용해 결제 페이지까지 간다', '[seed] 결제 페이지에 도달', 'https://shop.example.com/checkout', FALSE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE project_id = @cmp_project);
SET @cmp_task = (SELECT MIN(task_id) FROM tasks WHERE project_id = @cmp_project);

-- 1회차
INSERT INTO runs (project_id, task_id, mode, loop_max, target_url_snapshot, allowed_domains_snapshot, task_snapshot,
                  policy_snapshot, persona_snapshot, dispatch_state, cancel_requested, status, progress, tokens, cost_usd,
                  accepted_at, started_at, finished_at)
SELECT @cmp_project, @cmp_task, 'loop', 3, 'https://shop.example.com', JSON_ARRAY('shop.example.com'),
       JSON_OBJECT('task_id', @cmp_task, 'goal', '쿠폰을 적용해 결제 페이지까지 간다', 'success_rule', '[seed] 결제 페이지에 도달',
                   'success_url', 'https://shop.example.com/checkout', 'is_one_shot', FALSE),
       JSON_OBJECT('max_steps', 10, 'max_seconds', 120, 'max_tokens', 20000),
       JSON_ARRAY(JSON_OBJECT('persona_id', @cmp_persona, 'name', '[seed] 모바일 초보',
                              'profile', JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low',
                                                     'background', '휴대폰으로만 쇼핑한다'))),
       'sent', FALSE, 'done', 1, 3800, 0.0380,
       NOW() - INTERVAL 60 MINUTE, NOW() - INTERVAL 60 MINUTE, NOW() - INTERVAL 56 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM runs WHERE task_id = @cmp_task);
SET @cmp_run_1 = (SELECT MIN(run_id) FROM runs WHERE task_id = @cmp_task);
UPDATE runs SET first_run_id = run_id WHERE run_id = @cmp_run_1 AND first_run_id IS NULL;

INSERT INTO run_personas (run_id, persona_id, status, url_reached, steps, backtracks, tokens, cost_usd, log_path,
                          started_at, finished_at)
SELECT @cmp_run_1, @cmp_persona, 'max_steps', FALSE, 10, 2, 3800, 0.0380,
       CONCAT(@cmp_run_1, '/', @cmp_persona, '/steps.jsonl'), NOW() - INTERVAL 60 MINUTE, NOW() - INTERVAL 56 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_personas WHERE run_id = @cmp_run_1);

INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd)
SELECT @cmp_run_1, 0.00, 10.00, 2.00, 240.00, 3800, 0.0380
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_metrics WHERE run_id = @cmp_run_1);

INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @cmp_run_1, 'task_failure', 'high',
       JSON_ARRAY(JSON_OBJECT('persona_id', @cmp_persona, 'step_from', 6, 'step_to', 10,
                              'url', 'https://shop.example.com/cart')),
       '“적용” 버튼 문구가 모호해 쿠폰을 적용하지 못하고 결제로 넘어가지 못했다.'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM findings WHERE run_id = @cmp_run_1);
SET @cmp_finding = (SELECT MIN(finding_id) FROM findings WHERE run_id = @cmp_run_1);

INSERT INTO improvements (run_id, finding_ids, option_no, patch_kind, patch, rationale, expected_effect, fix_cost)
SELECT @cmp_run_1, JSON_ARRAY(@cmp_finding), 1, 'relabel',
       JSON_OBJECT('target', '#coupon-apply', 'new_text', '쿠폰 적용하기'),
       '버튼 문구 “적용”이 무엇을 적용하는지 드러나지 않는다.', '쿠폰 적용 단계의 망설임과 되돌아가기가 줄어든다.', 'low'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM improvements WHERE run_id = @cmp_run_1);
SET @cmp_improvement = (SELECT MIN(improvement_id) FROM improvements WHERE run_id = @cmp_run_1);

INSERT INTO approvals (improvement_id, user_id, decision, note, decided_at)
SELECT @cmp_improvement, 1, 'approve', NULL, NOW() - INTERVAL 50 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM approvals WHERE improvement_id = @cmp_improvement);

-- 2회차 — 1안을 적용한 다음 회차
INSERT INTO runs (project_id, task_id, mode, loop_max, parent_run_id, improvement_id, target_url_snapshot,
                  allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot, first_run_id, dispatch_state,
                  cancel_requested, status, progress, tokens, cost_usd, accepted_at, started_at, finished_at)
SELECT project_id, task_id, mode, loop_max, run_id, @cmp_improvement, target_url_snapshot,
       allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot, run_id, 'sent',
       FALSE, 'done', 1, 2600, 0.0260, NOW() - INTERVAL 50 MINUTE, NOW() - INTERVAL 50 MINUTE, NOW() - INTERVAL 47 MINUTE
  FROM runs
 WHERE run_id = @cmp_run_1
   AND (SELECT COUNT(*) FROM runs WHERE task_id = @cmp_task) = 1;
SET @cmp_run_2 = (SELECT MAX(run_id) FROM runs WHERE task_id = @cmp_task);

INSERT INTO run_personas (run_id, persona_id, status, url_reached, steps, backtracks, tokens, cost_usd, log_path,
                          started_at, finished_at)
SELECT @cmp_run_2, @cmp_persona, 'done', TRUE, 6, 0, 2600, 0.0260,
       CONCAT(@cmp_run_2, '/', @cmp_persona, '/steps.jsonl'), NOW() - INTERVAL 50 MINUTE, NOW() - INTERVAL 47 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_personas WHERE run_id = @cmp_run_2);

INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd)
SELECT @cmp_run_2, 100.00, 6.00, 0.00, 150.00, 2600, 0.0260
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_metrics WHERE run_id = @cmp_run_2);

INSERT INTO patch_versions (run_id, improvement_id, patch_kind, patch, applied)
SELECT @cmp_run_2, @cmp_improvement, 'relabel', JSON_OBJECT('target', '#coupon-apply', 'new_text', '쿠폰 적용하기'), TRUE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM patch_versions WHERE run_id = @cmp_run_2);
