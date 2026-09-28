package com.uxight.api.web.login;

import com.uxight.api.domain.user.LoginService;
import com.uxight.api.domain.user.User;
import com.uxight.api.web.common.SessionConst;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.stereotype.Controller;
import org.springframework.validation.BindingResult;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.ModelAttribute;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestParam;

@Controller
public class LoginController {

  private final LoginService loginService;

  public LoginController(LoginService loginService) {
    this.loginService = loginService;
  }

  @GetMapping("/login")
  public String loginForm(@ModelAttribute("loginForm") LoginForm form) {
    return "loginForm";
  }

  @PostMapping("/login")
  public String login(@Validated @ModelAttribute("loginForm") LoginForm form, BindingResult bindingResult,
      @RequestParam(defaultValue = "/dashboard") String redirectURL, HttpServletRequest request) {
    if (bindingResult.hasErrors()) {
      return "loginForm";
    }

    User loginUser = loginService.login(form.getEmail());
    if (loginUser == null) {
      bindingResult.reject("loginFail", "이메일 또는 비밀번호가 올바르지 않습니다.");
      return "loginForm";
    }

    HttpSession session = request.getSession();
    session.setAttribute(SessionConst.LOGIN_USER, loginUser);

    return "redirect:" + redirectURL;
  }
}
