package com.uxight.api.web.run;

import com.uxight.api.domain.runlog.StepLog;

import java.util.List;

/** Persona 실행의 step 로그 전체(페이지 없음). 리서처용 · 운영자용이 같은 형식이다. */
public record StepLogListResponse(List<StepLog> steps) {
}
