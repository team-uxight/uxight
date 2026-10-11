package com.uxight.api.domain.project;

import com.uxight.api.common.ApiException;
import com.uxight.api.domain.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AccessLevel;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.net.URI;
import java.net.URISyntaxException;
import java.time.LocalDateTime;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

/** 대상 사이트 단위. 실험(Task · 회차)은 프로젝트 아래에 생긴다. */
@Entity
@Table(name = "projects")
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class Project {

  @Id
  @GeneratedValue(strategy = GenerationType.IDENTITY)
  @Column(name = "project_id")
  private Long id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "user_id")
  private User user;   // 소유 리서처

  private String title;

  private String targetUrl;   // 시작 URL

  private String description;

  @JdbcTypeCode(SqlTypes.JSON)
  private List<String> allowedDomains;   // 가드 허용 도메인 목록

  private LocalDateTime deletedAt;   // 삭제 시각. null 이면 사용 중 (삭제 표시)

  // 두 시각은 DB 기본값(CURRENT_TIMESTAMP · ON UPDATE)이 채운다. JPA 가 null 로 덮지 않게 쓰기에서 뺀다.
  @Column(insertable = false, updatable = false)
  private LocalDateTime createdAt;

  @Column(insertable = false, updatable = false)
  private LocalDateTime updatedAt;

  private Project(User user, String title, String targetUrl, String description, List<String> allowedDomains) {
    this.user = user;
    this.title = title;
    this.targetUrl = targetUrl;
    this.description = description;
    this.allowedDomains = allowedDomains;
  }

  /**
   * 허용 도메인은 호스트(도메인)만 저장한다 — 가드는 이동할 페이지의 호스트를 이 목록과 비교한다.
   * 시작 URL 의 호스트는 항상 들어간다 — 리서처가 빠뜨려도 Agent 가 시작 페이지에서 막히지 않는다.
   */
  public static Project create(User user, String title, String targetUrl, String description,
      List<String> allowedDomains) {
    return new Project(user, title, targetUrl, description, toAllowedHosts(targetUrl, allowedDomains));
  }

  /**
   * 행을 지우지 않고 삭제 시각만 기록한다 — 지난 실험의 Task · 회차가 이 행을 참조한다.
   * 진행 중인 실험이 없는지는 서비스가 프로젝트 행을 잠근 뒤 확인한다.
   */
  public void delete() {
    this.deletedAt = LocalDateTime.now();
  }

  public void changeTitle(String title) {
    this.title = title;
  }

  /** 빈 문자열(공백뿐 포함)을 보내면 설명을 지운다 — 설명이 없는 프로젝트와 같이 NULL 로 둔다. */
  public void changeDescription(String description) {
    this.description = description.isBlank() ? null : description;
  }

  /**
   * 새 시작 URL 의 호스트를 허용 도메인 맨 앞에 넣는다. 이전 시작 URL 의 호스트는 리서처가 넣은 값과 구분할 수 없어 남긴다.
   * 이미 만든 회차는 시작 시점의 URL · 허용 도메인을 스냅샷으로 가지므로 영향이 없다.
   */
  public void changeTargetUrl(String targetUrl) {
    this.allowedDomains = toAllowedHosts(targetUrl, allowedDomains);
    this.targetUrl = targetUrl;
  }

  /** 목록을 통째로 바꾼다. 생성과 같이 호스트만 남기고, 현재 시작 URL 의 호스트를 맨 앞에 넣는다. */
  public void changeAllowedDomains(List<String> allowedDomains) {
    this.allowedDomains = toAllowedHosts(targetUrl, allowedDomains);
  }

  /**
   * 시작 URL 의 호스트를 맨 앞에 두고, 입력 순서를 지키며 중복을 지운다.
   * 주소를 넣어도 호스트만 남긴다 (https://pay.example.com/checkout → pay.example.com).
   * 도메인은 대소문자를 구분하지 않으므로 소문자로 맞춘 뒤 비교한다 (Shop.com 과 shop.com 은 같은 값).
   */
  private static List<String> toAllowedHosts(String targetUrl, List<String> allowedDomains) {
    Set<String> hosts = new LinkedHashSet<>();
    // targetUrl 은 http(s):// 로 시작함을 Bean Validation 이 확인했다. 그래도 호스트를 읽을 수 없는 값(공백 포함 등)은 여기서 막는다.
    hosts.add(hostOf(targetUrl)
        .orElseThrow(() -> ApiException.invalidField("targetUrl", "도메인을 읽을 수 없는 URL입니다")));
    for (int i = 0; i < allowedDomains.size(); i++) {
      String field = "allowedDomains[" + i + "]";   // Bean Validation 의 필드 이름과 같은 모양
      hosts.add(hostOf(allowedDomains.get(i))
          .orElseThrow(() -> ApiException.invalidField(field, "도메인을 읽을 수 없는 값입니다")));
    }
    return List.copyOf(hosts);
  }

  /** URL 이든 도메인이든 호스트만 소문자로 뽑는다. 스킴이 없으면 http:// 를 붙여 읽는다 (pay.example.com/checkout). */
  private static Optional<String> hostOf(String value) {
    String url = value.strip();
    if (!url.contains("://")) {
      url = "http://" + url;
    }
    try {
      return Optional.ofNullable(new URI(url).getHost()).map(host -> host.toLowerCase(Locale.ROOT));
    } catch (URISyntaxException e) {
      return Optional.empty();
    }
  }
}
