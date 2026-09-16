package com.uxight.api.run;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/runs")
public class RunController {
  private final RunRepository runs;
  private final AgentClient agent;

  public RunController(RunRepository runs, AgentClient agent) {
    this.runs = runs;
    this.agent = agent;
  }

  public record CreateRun(@NotBlank String targetUrl, @NotBlank String task) {}

  @PostMapping
  public ResponseEntity<Map<String, Object>> create(@Valid @RequestBody CreateRun body) {
    Run run = runs.save(new Run(body.targetUrl(), body.task()));
    boolean dispatched = agent.startRun(run);
    return ResponseEntity.status(HttpStatus.ACCEPTED)
        .body(Map.of("id", run.getId(), "status", run.getStatus(), "dispatched", dispatched));
  }

  @GetMapping("/{id}")
  public Run get(@PathVariable Long id) {
    return runs.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
  }
}
