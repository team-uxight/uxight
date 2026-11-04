package com.uxight.api.domain.runlog;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * agent 가 쓰는 회차 로그 파일을 읽는다 — 리서처용 · 운영자용 조회가 함께 쓰고, 권한 확인은 RunLogService 가 한다.
 * 파일은 Python 만 쓰고 api 는 읽기 전용 마운트로 읽는다. 경로는 runId · personaId · step 숫자로만 만든다 —
 * 로그 안의 경로(observation.screenshot)나 run_personas.log_path 를 쓰지 않는다(행동 로그 명세 2절, 경로 조작 방지).
 */
@Component
@Slf4j
public class RunLogReader {

  private static final String STEP_LOG_FILE = "steps.jsonl";

  private final Path root;
  private final ObjectMapper objectMapper;

  @Autowired
  public RunLogReader(@Value("${uxight.run-log-dir}") String runLogDir, ObjectMapper objectMapper) {
    this.root = Path.of(runLogDir);
    this.objectMapper = objectMapper;
  }

  /**
   * Persona 실행의 step 로그 — 기록 순. 파일이 없으면 빈 Optional.
   * 줄바꿈으로 끝나지 않은 마지막 줄은 agent 가 쓰는 중인 줄이라 건너뛴다. JSON 으로 읽히지 않는 줄도 건너뛴다.
   */
  public Optional<List<StepLog>> readSteps(long runId, long personaId) {
    Path file = personaDir(runId, personaId).resolve(STEP_LOG_FILE);
    if (!Files.isRegularFile(file)) {
      return Optional.empty();
    }
    String content;
    try {
      content = Files.readString(file, StandardCharsets.UTF_8);
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }

    String[] lines = content.split("\n", -1);
    List<StepLog> steps = new ArrayList<>();
    // 마지막 조각은 줄바꿈 뒤의 빈 문자열이거나 아직 다 쓰지 않은 줄이다
    for (int i = 0; i < lines.length - 1; i++) {
      String line = lines[i].strip();
      if (line.isEmpty()) {
        continue;
      }
      try {
        steps.add(toStepLog(objectMapper.readTree(line)));
      } catch (JsonProcessingException e) {
        log.warn("skip unreadable step log line run_id={} persona_id={} line={}", runId, personaId, i + 1);
      }
    }
    return Optional.of(steps);
  }

  /** step 의 스크린샷(PNG). 파일이 없거나 step 이 1보다 작으면 빈 Optional. */
  public Optional<byte[]> readScreenshot(long runId, long personaId, int step) {
    if (step < 1) {
      return Optional.empty();
    }
    // agent 는 임시 이름으로 쓴 뒤 이름을 바꾸므로 이 이름의 파일은 다 쓴 파일이다
    Path file = personaDir(runId, personaId).resolve("step-" + step + ".png");
    if (!Files.isRegularFile(file)) {
      return Optional.empty();
    }
    try {
      return Optional.of(Files.readAllBytes(file));
    } catch (IOException e) {
      throw new UncheckedIOException(e);
    }
  }

  private Path personaDir(long runId, long personaId) {
    return root.resolve(Long.toString(runId)).resolve(Long.toString(personaId));
  }

  // 행동 로그 명세 3절의 snake_case → 화면에 필요한 키만 camelCase. 없는 키는 null(불리언은 false)
  private static StepLog toStepLog(JsonNode node) {
    JsonNode action = node.get("action");
    JsonNode result = node.path("result");
    JsonNode blocked = node.path("blocked");
    JsonNode urlReached = node.path("task").path("url_reached");
    return new StepLog(
        node.path("step").asInt(),
        text(node, "ts"),
        text(node, "url"),
        text(node, "reasoning"),
        action == null || !action.isObject() ? null : new StepLog.StepAction(
            text(action, "kind"), integer(action, "target"), text(action, "text"), text(action, "direction")),
        new StepLog.StepResult(result.path("ok").asBoolean(false), text(result, "url_after"), text(result, "error"),
            text(result, "error_code")),
        blocked.path("is").asBoolean(false),
        text(blocked, "reason"),
        urlReached.isBoolean() ? urlReached.booleanValue() : null,
        text(node.path("observation"), "screenshot") != null);
  }

  private static String text(JsonNode node, String field) {
    JsonNode value = node.get(field);
    return value == null || value.isNull() ? null : value.asText();
  }

  private static Integer integer(JsonNode node, String field) {
    JsonNode value = node.get(field);
    return value == null || !value.canConvertToInt() ? null : value.intValue();
  }
}
