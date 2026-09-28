package com.uxight.api.web.run;

import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.domain.run.RunService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class RunController {

  private static final Logger log = LoggerFactory.getLogger(RunController.class);

  private final RunService runService;
  private final ProjectService projectService;

  public RunController(RunService runService, ProjectService projectService) {
    this.runService = runService;
    this.projectService = projectService;
  }

  @PostMapping("/projects/{projectId}/runs")
  public String createRun(@PathVariable Long projectId, @RequestParam String goal, @RequestParam Long personaIds,
      Model model) {
    log.info("POST /projects/{}/runs goal={} personaIds={}", projectId, goal, personaIds);
    try {
      runService.createRun(projectId, goal, personaIds);
    } catch (RuntimeException e) {
      model.addAttribute("project", projectService.getProject(projectId));
      model.addAttribute("personas", projectService.getPersonas(projectId));
      model.addAttribute("errorMessage", "런 생성에 실패했습니다. 입력값을 확인해 주세요.");
      return "project";
    }

    return "redirect:/monitoring";
  }

  @PostMapping("/monitoring/{runId}/cancel")
  public String cancel(@PathVariable Long runId) {
    log.info("POST /monitoring/{}/cancel", runId);
    runService.requestCancel(runId);
    return "redirect:/history";
  }
}
