package com.uxight.api.web.improvement;

import com.uxight.api.domain.improvement.ApprovalCreateRequest;
import com.uxight.api.domain.improvement.ApprovalResult;
import com.uxight.api.domain.improvement.ImprovementDetail;
import com.uxight.api.domain.improvement.ImprovementList;
import com.uxight.api.domain.improvement.ImprovementService;
import com.uxight.api.web.common.AuthConst;
import jakarta.validation.Valid;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestAttribute;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

/**
 * 리서처의 개선안과 다음 회차 결정. 진단 결과의 '개선안 확인' → 개선안 목록 → 개선안 상세 → 승인 · 반려.
 * 본인 프로젝트의 done 회차만 — 남의 회차 · 삭제한 프로젝트 · 아직 끝나지 않은 회차는 없는 것과 같은 404.
 */
@RestController
public class ImprovementController {

  private final ImprovementService improvementService;

  @Autowired
  public ImprovementController(ImprovementService improvementService) {
    this.improvementService = improvementService;
  }

  /** 회차 정보(승인 대기 여부 포함)와 개선안 목록(안 번호 · 패치 종류 · 구현 비용 · 결정). 개선안이 없으면 빈 목록. */
  @GetMapping("/api/runs/{runId}/improvements")
  public ImprovementList improvements(@PathVariable Long runId, @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return improvementService.getImprovements(userId, runId);
  }

  /** 개선안의 패치 · 근거 · 예상 효과 · 다루는 진단 · 결정과 승인 대기 여부. */
  @GetMapping("/api/improvements/{improvementId}")
  public ImprovementDetail improvement(@PathVariable Long improvementId,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return improvementService.getImprovement(userId, improvementId);
  }

  /**
   * 그 개선안으로 다음 회차를 진행할지 승인 · 반려. 승인이면 패치를 적용한 다음 회차가 queued 로 생기고 AI 모듈을 부른다(runId 에 담는다).
   * 반려면 그 개선안만 후보에서 빠진다(runId null). 승인 가능 조건이 어긋나면 409 IMP-ERR-002, 승인인데 진행 중인 실험이 있으면 409 EXP-ERR-004.
   */
  @PostMapping("/api/runs/{runId}/approvals")
  @ResponseStatus(HttpStatus.CREATED)
  public ApprovalResult decide(@PathVariable Long runId, @Valid @RequestBody ApprovalCreateRequest request,
      @RequestAttribute(AuthConst.LOGIN_USER_ID) Long userId) {
    return improvementService.decide(userId, runId, request);
  }
}
