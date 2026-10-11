package com.uxight.api.domain.project;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.List;
import java.util.Optional;

/**
 * 바꿀 항목만 보낸다. "보내지 않음"과 "null 을 보냄"을 구분하려고 Optional 필드로 받는다 —
 * 키가 없으면 필드가 null(그대로 둠), 값이 null 이면 Optional.empty().
 * record 가 아닌 이유: Jackson 은 생성자로 만드는 record 의 빠진 키에도 Optional.empty() 를 넣어 둘을 구분할 수 없다.
 * null 로 지울 수 있는 항목은 description 뿐이다. 나머지는 Optional 안의 @NotNull 이 null 을 400 으로 막는다.
 * 검증 규칙은 ProjectCreateRequest 와 같다.
 */
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ProjectUpdateRequest {

  private Optional<@NotNull @Size(max = 100)
      @Pattern(regexp = "^\\S(.*\\S)?$", message = "비어 있거나 앞뒤에 공백이 있으면 안 됩니다") String> title;

  private Optional<@NotBlank @Size(max = 2048)
      @Pattern(regexp = "^https?://.+", message = "http:// 또는 https://로 시작하는 URL이어야 합니다") String> targetUrl;

  private Optional<@Size(max = 1000) String> description;

  private Optional<@NotNull List<@NotBlank String>> allowedDomains;
}
