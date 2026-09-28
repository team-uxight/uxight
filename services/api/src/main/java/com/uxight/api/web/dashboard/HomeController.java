package com.uxight.api.web.dashboard;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.uxight.api.domain.project.Project;
import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.domain.run.Run;
import com.uxight.api.domain.run.RunPersona;
import com.uxight.api.domain.run.RunPersonaRepository;
import com.uxight.api.domain.run.RunService;
import com.uxight.api.domain.task.Task;
import com.uxight.api.domain.task.TaskRepository;
import com.uxight.api.domain.user.User;
import com.uxight.api.web.common.SessionConst;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.SessionAttribute;

import java.io.UncheckedIOException;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import java.util.NoSuchElementException;
import java.util.Objects;
import java.util.Set;

@Controller
public class HomeController {

  private static final Logger log = LoggerFactory.getLogger(HomeController.class);
  private static final Set<String> TERMINAL_STATUSES = Set.of("done", "failed", "cancelled");

  private final ProjectService projectService;
  private final RunService runService;
  private final TaskRepository taskRepository;
  private final RunPersonaRepository runPersonaRepository;
  private final ObjectMapper objectMapper;

  public HomeController(ProjectService projectService, RunService runService,
      TaskRepository taskRepository, RunPersonaRepository runPersonaRepository, ObjectMapper objectMapper) {
    this.projectService = projectService;
    this.runService = runService;
    this.taskRepository = taskRepository;
    this.runPersonaRepository = runPersonaRepository;
    this.objectMapper = objectMapper;
  }

  @GetMapping("/")
  public String index() {
    return "redirect:/dashboard";
  }

  @GetMapping("/dashboard")
  public String home(@SessionAttribute(name = SessionConst.LOGIN_USER, required = false) User loginUser, Model model) {
    if (loginUser == null) {
      return "dashboardGuest";
    }

    model.addAttribute("loginUser", loginUser);
    model.addAttribute("projects", projectService.getProjectsByUser(loginUser.userId()));
    return "dashboardMember";
  }

  @GetMapping("/monitoring")
  public String monitoring(@SessionAttribute(name = SessionConst.LOGIN_USER) User loginUser, Model model) {
    log.info("GET /monitoring userId={}", loginUser.userId());
    List<MonitoringRun> runs = runService.getActiveRuns(loginUser.userId()).stream()
        .map(this::toMonitoringRun)
        .toList();

    model.addAttribute("runs", runs);
    return "monitoring";
  }

  private MonitoringRun toMonitoringRun(Run run) {
    Project project = projectService.getProject(run.projectId());
    Task task = taskRepository.findById(run.taskId())
        .orElseThrow(() -> new NoSuchElementException("task not found: " + run.taskId()));

    int totalPersonas = countPersonas(run);
    int completedPersonas = run.progress() != null ? run.progress() : 0;

    LocalDateTime start = run.startedAt() != null ? run.startedAt() : run.createdAt();
    long totalSeconds = Duration.between(start, LocalDateTime.now()).getSeconds();
    String elapsedDisplay = String.format("%02d:%02d", totalSeconds / 60, totalSeconds % 60);

    return new MonitoringRun(run.runId(), project.title(), task.goal(), completedPersonas, totalPersonas, elapsedDisplay);
  }

  @GetMapping("/history")
  public String history(@SessionAttribute(name = SessionConst.LOGIN_USER) User loginUser, Model model) {
    List<HistoryRun> history = runService.getEndedRuns(loginUser.userId()).stream()
        .map(this::toHistoryRun)
        .toList();

    model.addAttribute("history", history);
    return "history";
  }

  private HistoryRun toHistoryRun(Run run) {
    Project project = projectService.getProject(run.projectId());
    Task task = taskRepository.findById(run.taskId())
        .orElseThrow(() -> new NoSuchElementException("task not found: " + run.taskId()));

    int totalPersonas = countPersonas(run);
    int completedPersonas = run.progress() != null ? run.progress() : 0;

    String endType = switch (run.status()) {
      case "done" -> "수행 완료";
      case "failed" -> "실패";
      case "cancelled" -> "취소";
      default -> "취소 진행 중";
    };

    LocalDateTime start = run.startedAt() != null ? run.startedAt() : run.createdAt();
    LocalDateTime end;
    if (TERMINAL_STATUSES.contains(run.status())) {
      end = runPersonaRepository.findByRunId(run.runId()).stream()
          .map(RunPersona::finishedAt)
          .filter(Objects::nonNull)
          .max(LocalDateTime::compareTo)
          .orElse(LocalDateTime.now());
    } else {
      end = LocalDateTime.now();
    }
    long totalSeconds = Duration.between(start, end).getSeconds();
    String elapsedDisplay = String.format("%02d:%02d", totalSeconds / 60, totalSeconds % 60);

    return new HistoryRun(run.runId(), endType, project.title(), task.goal(), elapsedDisplay, completedPersonas, totalPersonas);
  }

  // Jackson 2 의 checked 예외를 unchecked 로 감싼다 (원본 Jackson 3 과 같은 전파).
  private int countPersonas(Run run) {
    try {
      return objectMapper.readValue(run.personaSnapshot(), List.class).size();
    } catch (JsonProcessingException e) {
      throw new UncheckedIOException(e);
    }
  }
}
