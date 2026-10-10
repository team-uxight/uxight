package com.uxight.api.config;

import com.uxight.api.web.common.AdminCheckInterceptor;
import com.uxight.api.web.common.LoginCheckInterceptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class WebConfig implements WebMvcConfigurer {

  private final String webOrigin;
  private final LoginCheckInterceptor loginCheckInterceptor;

  @Autowired
  public WebConfig(@Value("${uxight.web-origin}") String webOrigin, LoginCheckInterceptor loginCheckInterceptor) {
    this.webOrigin = webOrigin;
    this.loginCheckInterceptor = loginCheckInterceptor;
  }

  @Override
  public void addInterceptors(InterceptorRegistry registry) {
    registry.addInterceptor(loginCheckInterceptor)
        .order(1)
        .addPathPatterns("/api/**")
        .excludePathPatterns("/api/health", "/api/auth/signup", "/api/auth/login", "/api/auth/google", "/api/auth/refresh", "/api/auth/logout");
    // 로그인 확인(order 1)이 역할을 요청 속성에 담은 뒤에 돈다
    registry.addInterceptor(new AdminCheckInterceptor())
        .order(2)
        .addPathPatterns("/api/admin/**");
  }

  /**
   * 로컬 개발용 CORS — 웹(5173)에서 API 호출. 배포 시 origin 은 환경변수로.
   * refresh 토큰 쿠키를 실어 보내야 하므로 allowCredentials — FE 는 fetch 에 credentials: 'include' 를 준다.
   */
  @Override
  public void addCorsMappings(CorsRegistry registry) {
    registry.addMapping("/api/**")
        .allowedOrigins(webOrigin)
        .allowedMethods("GET", "POST", "PATCH", "DELETE")
        .allowCredentials(true);
  }
}
