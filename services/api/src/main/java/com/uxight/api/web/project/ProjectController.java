package com.uxight.api.web.project;

import com.uxight.api.domain.project.ProjectForm;
import com.uxight.api.domain.project.ProjectService;
import com.uxight.api.domain.user.User;
import com.uxight.api.web.common.SessionConst;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.validation.BindingResult;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.SessionAttribute;

@Controller
public class ProjectController {

  private final ProjectService projectService;

  public ProjectController(ProjectService projectService) {
    this.projectService = projectService;
  }

  @GetMapping("/projects/new")
  public String addProjectForm(@ModelAttribute("projectForm") ProjectForm form) {
    return "addProjectForm";
  }

  @GetMapping("/projects/{projectId}")
  public String project(@PathVariable Long projectId, Model model) {
    model.addAttribute("project", projectService.getProject(projectId));
    model.addAttribute("personas", projectService.getPersonas(projectId));
    return "project";
  }

  @PostMapping("/projects")
  public String createProject(@Validated @ModelAttribute("projectForm") ProjectForm form, BindingResult bindingResult,
      @SessionAttribute(name = SessionConst.LOGIN_USER) User loginUser) {
    if (bindingResult.hasErrors()) {
      return "addProjectForm";
    }

    projectService.createProject(loginUser.userId(), form);

    return "redirect:/dashboard";
  }
}
