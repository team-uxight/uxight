package com.uxight.api.domain.project;

import com.uxight.api.domain.persona.Persona;
import com.uxight.api.domain.persona.PersonaRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.NoSuchElementException;

@Service
public class ProjectService {

  private static final int MOCK_PERSONA_COUNT = 1;
  private static final String MOCK_PERSONA_NAME = "재완";
  private static final String MOCK_PERSONA_PROFILE =
      "{\"age_group\": 20, \"web_skill\": \"low\", \"device\": \"desktop\", "
      + "\"domain_knowledge\": \"low\", \"patience\": \"medium\", \"exploration_tendency\": \"low\", "
      + "\"behavior_instruction\": [\"메뉴 이름이 모호하면 쉽게 헤맨다.\", \"실패한 경로를 반복하지 않는다.\"]}";

  private final ProjectRepository projectRepository;
  private final PersonaRepository personaRepository;

  public ProjectService(ProjectRepository projectRepository, PersonaRepository personaRepository) {
    this.projectRepository = projectRepository;
    this.personaRepository = personaRepository;
  }

  public void createProject(Long userId, ProjectForm form) {
    Project project = Project.newProject(userId, form.getTitle(), form.getTargetUrl(),
        form.getDescription(), form.getAllowedDomains());
    Long projectId = projectRepository.save(project);

    for (int i = 0; i < MOCK_PERSONA_COUNT; i++) {
      personaRepository.save(Persona.newPersona(projectId, MOCK_PERSONA_NAME, MOCK_PERSONA_PROFILE));
    }
  }

  public Project getProject(Long projectId) {
    return projectRepository.findById(projectId)
        .orElseThrow(() -> new NoSuchElementException("project not found: " + projectId));
  }

  public List<Persona> getPersonas(Long projectId) {
    return personaRepository.findByProjectId(projectId);
  }

  public List<Project> getProjectsByUser(Long userId) {
    return projectRepository.findByUserId(userId);
  }
}
