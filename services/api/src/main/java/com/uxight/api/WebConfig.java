package com.uxight.api;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/** 로컬 개발용 CORS — 웹(5173)에서 API 호출. 배포 시 origin 은 환경변수로. */
@Configuration
public class WebConfig implements WebMvcConfigurer {
  @Value("${uxight.web-origin}")
  private String webOrigin;

  @Override
  public void addCorsMappings(CorsRegistry registry) {
    registry.addMapping("/api/**").allowedOrigins(webOrigin).allowedMethods("GET", "POST", "PATCH", "DELETE");
  }
}
