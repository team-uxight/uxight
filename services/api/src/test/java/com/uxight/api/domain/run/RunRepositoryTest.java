package com.uxight.api.domain.run;

import static org.assertj.core.api.Assertions.assertThat;

import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import jakarta.persistence.EntityManager;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;

/**
 * Task · Run 엔티티 매핑과, Spring 이 Python 소유 컬럼을 덮어쓰지 않는지 본다. 실제 MySQL, 테스트마다 롤백.
 * Python 의 쓰기는 JdbcTemplate UPDATE 로 흉내 낸다.
 */
@SpringBootTest
@Transactional
class RunRepositoryTest {

  @Autowired
  private RunRepository runRepository;

  @Autowired
  private TaskRepository taskRepository;

  @Autowired
  private ProjectRepository projectRepository;

  @Autowired
  private JdbcTemplate jdbcTemplate;

  @Autowired
  private EntityManager entityManager;

  private Long userId;
  private Project project;
  private Task task;

  @BeforeEach
  void setUp() {
    jdbcTemplate.update("INSERT INTO users (email, password_hash, auth_provider, name, role, is_active) "
        + "VALUES ('run-repo@uxight.com', 'hash', 'local', '회차', 'researcher', TRUE)");
    userId = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);
    jdbcTemplate.update("INSERT INTO projects (user_id, title, target_url, allowed_domains) "
        + "VALUES (?, 'p', 'https://a.example.com', JSON_ARRAY('a.example.com'))", userId);
    project = projectRepository.getReferenceById(jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class));
    task = taskRepository.save(Task.create(project, "구매", "rule", "https://a.example.com/done"));
  }

  @Test
  void task_save_mapsColumns() {
    entityManager.flush();

    Map<String, Object> row = jdbcTemplate.queryForMap("SELECT * FROM tasks WHERE task_id = ?", task.getId());
    assertThat(row).containsEntry("project_id", project.getId())
        .containsEntry("goal", "구매")
        .containsEntry("success_rule", "rule")
        .containsEntry("success_url", "https://a.example.com/done")
        .containsEntry("is_one_shot", false);
    assertThat(row.get("created_at")).isNotNull();
  }

  @Test
  void firstRound_insertsQueued_andMarksItselfAsFirstRun() {
    Run run = saveFirstRound(RunMode.diagnose, 3);
    entityManager.flush();

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT status, mode, loop_max, first_run_id, cancel_requested, dispatch_state, "
            + "JSON_TYPE(allowed_domains_snapshot) ad, JSON_TYPE(task_snapshot) ts, JSON_TYPE(policy_snapshot) ps, "
            + "JSON_TYPE(persona_snapshot) pe, JSON_EXTRACT(persona_snapshot, '$[0].persona_id') pid "
            + "FROM runs WHERE run_id = ?", run.getId());
    assertThat(row).containsEntry("status", "queued")
        .containsEntry("mode", "diagnose")
        .containsEntry("first_run_id", run.getId())
        .containsEntry("cancel_requested", false)
        .containsEntry("ad", "ARRAY")
        .containsEntry("ts", "OBJECT")
        .containsEntry("ps", "OBJECT")
        .containsEntry("pe", "ARRAY");
    assertThat(row.get("loop_max")).isNull();         // loop 가 아니면 loopMax 를 버린다
    assertThat(row.get("dispatch_state")).isNull();   // 아직 POST /runs 전
    assertThat(row.get("pid")).hasToString("7");
  }

  @Test
  void firstRound_loop_keepsLoopMax() {
    Run run = saveFirstRound(RunMode.loop, 3);
    entityManager.flush();

    assertThat(jdbcTemplate.queryForObject("SELECT loop_max FROM runs WHERE run_id = ?", Integer.class, run.getId()))
        .isEqualTo(3);
  }

  @Test
  void springUpdate_doesNotOverwritePythonColumns() {
    Run run = runRepository.save(Run.firstRound(project, task, RunMode.diagnose, null, "https://a.example.com",
        List.of("a.example.com"), Map.of(), Map.of(), List.of()));
    entityManager.flush();   // INSERT — 엔티티는 status=queued 를 들고 있다

    // 그사이 Python 이 회차를 접수하고 실행을 시작했고, 다른 요청이 dispatch_state · 취소 요청을 한 줄 UPDATE 로 기록했다
    jdbcTemplate.update("UPDATE runs SET status = 'running', progress = 2, heartbeat_at = NOW(), tokens = 100, "
        + "dispatch_state = 'sent', cancel_requested = TRUE WHERE run_id = ?", run.getId());

    // Spring 이 옛 값을 든 같은 엔티티를 바꿔 커밋한다 — UPDATE 에는 first_run_id 만 들어가야 한다 (@DynamicUpdate)
    run.markAsFirstRound();
    entityManager.flush();

    Map<String, Object> row = jdbcTemplate.queryForMap(
        "SELECT status, progress, tokens, heartbeat_at, dispatch_state, cancel_requested, first_run_id "
            + "FROM runs WHERE run_id = ?", run.getId());
    assertThat(row).containsEntry("status", "running")
        .containsEntry("progress", 2)
        .containsEntry("tokens", 100L)
        .containsEntry("dispatch_state", "sent")
        .containsEntry("cancel_requested", true)
        .containsEntry("first_run_id", run.getId());
    assertThat(row.get("heartbeat_at")).isNotNull();
  }

  @Test
  void updateDispatchState_writesOnlyThatColumn() {
    Run run = saveFirstRound(RunMode.diagnose, null);
    entityManager.flush();
    jdbcTemplate.update("UPDATE runs SET status = 'accepted' WHERE run_id = ?", run.getId());

    assertThat(runRepository.updateDispatchState(run.getId(), DispatchState.timeout)).isEqualTo(1);

    assertThat(jdbcTemplate.queryForMap("SELECT status, dispatch_state FROM runs WHERE run_id = ?", run.getId()))
        .containsEntry("status", "accepted")
        .containsEntry("dispatch_state", "timeout");
  }

  @Test
  void requestCancel_writesOnlyCancelRequested() {
    // 취소할 수 있는지는 RunService 가 판정한다 — 승인 대기(done) 회차에도 기록할 수 있어야 한다
    Run done = saveFirstRound(RunMode.diagnose, null);
    entityManager.flush();
    jdbcTemplate.update("UPDATE runs SET status = 'done', progress = 3 WHERE run_id = ?", done.getId());

    assertThat(runRepository.requestCancel(done.getId())).isTrue();
    assertThat(runRepository.requestCancel(Long.MAX_VALUE)).isFalse();
    assertThat(jdbcTemplate.queryForMap("SELECT cancel_requested, status, progress FROM runs WHERE run_id = ?",
        done.getId()))
        .containsEntry("cancel_requested", true)
        .containsEntry("status", "done")
        .containsEntry("progress", 3);
  }

  @Test
  void findLastRound_returnsHighestRunOfOwnExperiment() {
    Run first = saveFirstRound(RunMode.loop, 3);
    entityManager.flush();
    // 다음 회차 — Spring 이 직전 회차의 first_run_id 를 복사해 INSERT 한다(아직 기능 전이라 SQL 로 만든다)
    jdbcTemplate.update("INSERT INTO runs (project_id, task_id, mode, loop_max, parent_run_id, first_run_id, "
        + "target_url_snapshot, allowed_domains_snapshot, task_snapshot, policy_snapshot, persona_snapshot, status) "
        + "VALUES (?, ?, 'loop', 3, ?, ?, 'https://a.example.com', JSON_ARRAY(), JSON_OBJECT(), JSON_OBJECT(), "
        + "JSON_ARRAY(), 'queued')", project.getId(), task.getId(), first.getId(), first.getId());
    Long second = jdbcTemplate.queryForObject("SELECT LAST_INSERT_ID()", Long.class);

    assertThat(runRepository.findLastRound(first.getId(), userId)).get().extracting(Run::getId).isEqualTo(second);
    assertThat(runRepository.findLastRound(first.getId(), Long.MAX_VALUE)).isEmpty();   // 남의 실험
  }

  @Test
  void existsInProgressByProjectId_followsStatus() {
    Run run = saveFirstRound(RunMode.diagnose, null);
    entityManager.flush();
    assertThat(runRepository.existsInProgressByProjectId(project.getId())).isTrue();   // queued

    jdbcTemplate.update("UPDATE runs SET status = 'failed' WHERE run_id = ?", run.getId());
    entityManager.clear();
    assertThat(runRepository.existsInProgressByProjectId(project.getId())).isFalse();
  }

  private Run saveFirstRound(RunMode mode, Integer loopMax) {
    Run run = runRepository.save(Run.firstRound(project, task, mode, loopMax, "https://a.example.com",
        List.of("a.example.com"), Map.of("task_id", task.getId(), "goal", "구매"), Map.of("max_steps", 10),
        List.of(Map.of("persona_id", 7, "name", "p", "profile", Map.of("webSkill", "low")))));
    run.markAsFirstRound();
    return run;
  }
}
