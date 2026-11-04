-- 로컬 전용 진단 예시 (GACA-190). local 프로필일 때만 Flyway 가 적용한다 (application-local.yml).
-- agent 가 진단을 저장(GACA-165)하기 전에도 진단 목록 · 상세 화면을 만들 수 있게, test@uxight.com(R__seed_local)의
-- done 회차 하나와 진단 3건을 넣는다. 로그인 test@uxight.com / test1234 → 실험 목록의 '[seed] 진단 예시 쇼핑몰'.
-- 다시 적용해도 같은 결과가 되도록 행이 없을 때만 넣는다. ID 는 고정하지 않는다 — 다른 로컬 데이터와 겹치지 않게
-- 제목 · 이름으로 찾아 세션 변수로 잇는다. 이 파일은 행을 지우지 않는다(초기화는 `docker compose down -v`).

INSERT INTO projects (user_id, title, target_url, description, allowed_domains)
SELECT 1, '[seed] 진단 예시 쇼핑몰', 'https://shop.example.com', '진단 목록 · 상세 화면 확인용 seed',
       JSON_ARRAY('shop.example.com')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM projects WHERE user_id = 1 AND title = '[seed] 진단 예시 쇼핑몰');
SET @seed_project = (SELECT MIN(project_id) FROM projects WHERE user_id = 1 AND title = '[seed] 진단 예시 쇼핑몰');

INSERT INTO personas (user_id, name, profile)
SELECT 1, '[seed] 쇼핑 초보',
       JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low', 'background', '온라인 쇼핑 경험이 적음')
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM personas WHERE user_id = 1 AND name = '[seed] 쇼핑 초보');
SET @seed_persona = (SELECT MIN(persona_id) FROM personas WHERE user_id = 1 AND name = '[seed] 쇼핑 초보');

INSERT INTO tasks (project_id, goal, success_rule, success_url, is_one_shot)
SELECT @seed_project, '상품을 장바구니에 담는다', '[seed] 장바구니 페이지에 도달', 'https://shop.example.com/cart', FALSE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE project_id = @seed_project);
SET @seed_task = (SELECT MIN(task_id) FROM tasks WHERE project_id = @seed_project);

INSERT INTO runs (project_id, task_id, mode, target_url_snapshot, allowed_domains_snapshot, task_snapshot,
                  policy_snapshot, persona_snapshot, dispatch_state, cancel_requested, status, progress, tokens, cost_usd,
                  accepted_at, started_at, finished_at)
SELECT @seed_project, @seed_task, 'diagnose', 'https://shop.example.com', JSON_ARRAY('shop.example.com'),
       JSON_OBJECT('task_id', @seed_task, 'goal', '상품을 장바구니에 담는다', 'success_rule', '[seed] 장바구니 페이지에 도달',
                   'success_url', 'https://shop.example.com/cart', 'is_one_shot', FALSE),
       JSON_OBJECT('max_steps', 10, 'max_seconds', 120, 'max_tokens', 20000),
       JSON_ARRAY(JSON_OBJECT('persona_id', @seed_persona, 'name', '[seed] 쇼핑 초보',
                              'profile', JSON_OBJECT('webSkill', 'low', 'device', 'mobile', 'domainKnowledge', 'low',
                                                     'background', '온라인 쇼핑 경험이 적음'))),
       'sent', FALSE, 'done', 1, 4200, 0.0420,
       NOW() - INTERVAL 10 MINUTE, NOW() - INTERVAL 10 MINUTE, NOW() - INTERVAL 7 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM runs WHERE task_id = @seed_task);
SET @seed_run = (SELECT MIN(run_id) FROM runs WHERE task_id = @seed_task);
UPDATE runs SET first_run_id = run_id WHERE run_id = @seed_run AND first_run_id IS NULL;

INSERT INTO run_personas (run_id, persona_id, status, url_reached, steps, backtracks, tokens, cost_usd, log_path,
                          started_at, finished_at)
SELECT @seed_run, @seed_persona, 'max_steps', FALSE, 10, 3, 4200, 0.0420,
       CONCAT(@seed_run, '/', @seed_persona, '/steps.jsonl'), NOW() - INTERVAL 10 MINUTE, NOW() - INTERVAL 7 MINUTE
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_personas WHERE run_id = @seed_run);

INSERT INTO run_metrics (run_id, success_rate, avg_steps, avg_backtracks, avg_seconds, tokens, cost_usd)
SELECT @seed_run, 0.00, 10.00, 3.00, 180.00, 4200, 0.0420
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM run_metrics WHERE run_id = @seed_run);

-- 진단 3건 — 4종 중 3가지. 하나는 요약 단계 전이라 summary 가 NULL 이다.
INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @seed_run, 'navigation_confusion', 'high',
       JSON_ARRAY(JSON_OBJECT('persona_id', @seed_persona, 'step_from', 2, 'step_to', 5,
                              'url', 'https://shop.example.com/category')),
       '카테고리 메뉴에서 같은 페이지를 네 번 오가며 장바구니로 가는 길을 찾지 못했다.'
  FROM DUAL
 WHERE NOT EXISTS (SELECT 1 FROM findings WHERE run_id = @seed_run);
INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @seed_run, 'interaction_failure', 'medium',
       JSON_ARRAY(JSON_OBJECT('persona_id', @seed_persona, 'step_from', 6, 'step_to', 7,
                              'url', 'https://shop.example.com/products/1')),
       '“장바구니 담기” 버튼이 화면 밖에 있어 두 번 눌러도 반응이 없었다.'
  FROM DUAL
 WHERE (SELECT COUNT(*) FROM findings WHERE run_id = @seed_run) = 1;
INSERT INTO findings (run_id, taxonomy, severity, evidence, summary)
SELECT @seed_run, 'task_failure', 'high',
       JSON_ARRAY(JSON_OBJECT('persona_id', @seed_persona, 'step_from', 8, 'step_to', 10,
                              'url', 'https://shop.example.com/products/1')),
       NULL
  FROM DUAL
 WHERE (SELECT COUNT(*) FROM findings WHERE run_id = @seed_run) = 2;
