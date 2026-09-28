package com.uxight.api.domain.run;

import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectRepository;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Service;

import java.io.UncheckedIOException;
import java.util.List;
import java.util.Map;
import java.util.NoSuchElementException;

@Service
public class RunService {

  private static final String MOCK_TASK_SUCCESS_CRITERIA = "{\"mock\": \"test\"}";
  private static final boolean MOCK_TASK_IS_ONE_SHOT = false;

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;
  private final TaskRepository taskRepository;
  private final RunRepository runRepository;
  private final AgentClient agentClient;
  private final ObjectMapper objectMapper;

  public RunService(ProjectRepository projectRepository, PersonaRepository personaRepository,
      TaskRepository taskRepository, RunRepository runRepository, AgentClient agentClient,
      ObjectMapper objectMapper) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
    this.taskRepository = taskRepository;
    this.runRepository = runRepository;
    this.agentClient = agentClient;
    this.objectMapper = objectMapper;
  }

  // The runs INSERT (via RunRepository.save) auto-commits on its own JdbcTemplate call since
  // this method is not @Transactional. That commit must land before dispatchToPython runs,
  // otherwise Python's idempotency check (UPDATE ... WHERE status='queued') would not see the row.
  public void createRun(Long projectId, String goal, Long personaId) {
    Project project = projectRepository.findById(projectId)
        .orElseThrow(() -> new NoSuchElementException("project not found: " + projectId));
    Persona persona = personaRepository.findById(personaId)
        .orElseThrow(() -> new NoSuchElementException("persona not found: " + personaId));

    Long taskId = taskRepository.save(Task.newTask(projectId, goal, MOCK_TASK_SUCCESS_CRITERIA, MOCK_TASK_IS_ONE_SHOT));
    Task task = taskRepository.findById(taskId)
        .orElseThrow(() -> new NoSuchElementException("task not found: " + taskId));

    Map<String, Object> taskSnapshotData = Map.of(
        "task_id", task.taskId(),
        "goal", task.goal(),
        "success_criteria", Map.of("mock", "test"),
        "is_one_shot", task.isOneShot()
    );
    List<Map<String, Object>> personaSnapshotData = List.of(
        Map.of(
            "persona_id", persona.personaId(),
            "name", persona.name(),
            "profile", readJson(persona.profile())
        )
    );
    Map<String, Object> policySnapshotData = Map.of("max_steps", 3);

    Run newRun = Run.newRun(projectId, taskId, project.targetUrl(),
        writeJson(taskSnapshotData),
        writeJson(policySnapshotData),
        writeJson(personaSnapshotData));
    Long runId = runRepository.save(newRun);

    Object allowedDomainsData = readJson(project.allowedDomains());
    // fire-and-forget: Python 응답을 기다리지 않고 돌아간다. dispatch_state 는 응답이 오면 비동기 스레드에서 기록된다.
    agentClient.dispatch(runId, taskSnapshotData, personaSnapshotData, policySnapshotData, allowedDomainsData)
        .thenAccept(dispatchState -> dispatchState.ifPresent(state -> runRepository.updateDispatchState(runId, state)));
  }

  public List<Run> getActiveRuns(Long userId) {
    return runRepository.findActiveByUserId(userId);
  }

  public List<Run> getEndedRuns(Long userId) {
    return runRepository.findEndedByUserId(userId);
  }

  public void requestCancel(Long runId) {
    runRepository.requestCancel(runId);
  }

  // Jackson 2 의 checked 예외를 unchecked 로 감싼다 — RunController 의 RuntimeException 처리로 이어진다.
  private Object readJson(String json) {
    try {
      return objectMapper.readValue(json, Object.class);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }

  private String writeJson(Object value) {
    try {
      return objectMapper.writeValueAsString(value);
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }
}
