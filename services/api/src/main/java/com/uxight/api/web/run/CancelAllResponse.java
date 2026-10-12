package com.uxight.api.web.run;

/** cancelledCount — 취소 요청을 기록한 실험 수. 실제 중단은 AI 모듈이 나중에 한다. */
public record CancelAllResponse(int cancelledCount) {
}
