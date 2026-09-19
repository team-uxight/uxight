package com.uxight.api.run;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import java.net.URI;
import java.net.URISyntaxException;
import java.util.Map;
import java.util.Set;
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
  /** agent 가 여는 것은 웹 페이지뿐 — file:/ · javascript: 같은 스킴은 막는다 (agent-safety §2.2). */
  private static final Set<String> ALLOWED_SCHEMES = Set.of("http", "https");

  private final RunRepository runs;
  private final AgentClient agent;

  public RunController(RunRepository runs, AgentClient agent) {
    this.runs = runs;
    this.agent = agent;
  }

  public record CreateRun(@NotBlank String targetUrl, @NotBlank String task) {}

  @PostMapping
  public ResponseEntity<Map<String, Object>> create(@Valid @RequestBody CreateRun body) {
    String targetUrl = requireHttpUrl(body.targetUrl());
    Run run = runs.save(new Run(targetUrl, body.task()));
    agent.startRun(run); // @Async — 응답을 기다리지 않는다
    return ResponseEntity.status(HttpStatus.ACCEPTED)
        .body(Map.of("id", run.getId(), "status", run.getStatus()));
  }

  @GetMapping("/{id}")
  public Run get(@PathVariable Long id) {
    return runs.findById(id).orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND));
  }

  private static String requireHttpUrl(String value) {
    try {
      URI uri = new URI(value);
      if (uri.getScheme() == null || !ALLOWED_SCHEMES.contains(uri.getScheme().toLowerCase()) || uri.getHost() == null) {
        throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "targetUrl 은 http/https 절대 URL 이어야 한다");
      }
      return value;
    } catch (URISyntaxException e) {
      throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "targetUrl 이 URL 형식이 아니다");
    }
  }
}
