import { useState } from "react";
import {
  Sparkles,
  List,
  SlidersHorizontal,
  AlertTriangle,
  History,
  RefreshCw,
  Plus,
  X,
  Info,
  CheckCircle2,
} from "lucide-react";
import AdminStopModal from "../components/AdminStopModal";

import "./AdminResources.css";

type Role = "researcher" | "maintainer" | "admin";

type RolePolicy = {
  model: string;
  budget: number;
};

type PolicyData = {
  roles: Record<Role, RolePolicy>;
  monthlyBudget: number;
  dailyTokens: number;
  domains: string[];
  maxConcurrent: number;
  maxPersonas: number;
  maxSteps: number;
  maxMinutes: number;
};

const INITIAL_POLICY: PolicyData = {
  roles: {
    researcher: {
      model: "GPT-4o mini",
      budget: 5,
    },
    maintainer: {
      model: "GPT-4o",
      budget: 10,
    },
    admin: {
      model: "GPT-4o",
      budget: 20,
    },
  },
  monthlyBudget: 300,
  dailyTokens: 2000000,
  domains: ["gachon.ac.kr", "example.com", "uxight.ai"],
  maxConcurrent: 3,
  maxPersonas: 5,
  maxSteps: 60,
  maxMinutes: 30,
};

const ROLES: {
  key: Role;
  name: string;
}[] = [
  { key: "researcher", name: "Researcher" },
  { key: "maintainer", name: "Maintainer" },
  { key: "admin", name: "Admin" },
];

const MODEL_OPTIONS = ["GPT-4o mini", "GPT-4o"];

function clonePolicy(data: PolicyData): PolicyData {
  return {
    ...data,
    roles: {
      researcher: { ...data.roles.researcher },
      maintainer: { ...data.roles.maintainer },
      admin: { ...data.roles.admin },
    },
    domains: [...data.domains],
  };
}

export default function AdminResources() {
  const [policy, setPolicy] = useState<PolicyData>(() =>
    clonePolicy(INITIAL_POLICY),
  );

  const [savedPolicy, setSavedPolicy] = useState<PolicyData>(() =>
    clonePolicy(INITIAL_POLICY),
  );

  const [domainInput, setDomainInput] = useState("");
  const [notice, setNotice] = useState("");
  const [showStopDialog, setShowStopDialog] = useState(false);

  const hasChanges = JSON.stringify(policy) !== JSON.stringify(savedPolicy);

  function updateRole(
    role: Role,
    field: keyof RolePolicy,
    value: string | number,
  ) {
    setPolicy((prev) => ({
      ...prev,
      roles: {
        ...prev.roles,
        [role]: {
          ...prev.roles[role],
          [field]: value,
        },
      },
    }));
  }

  function updateNumber(
    field: keyof Pick<
      PolicyData,
      | "monthlyBudget"
      | "dailyTokens"
      | "maxConcurrent"
      | "maxPersonas"
      | "maxSteps"
      | "maxMinutes"
    >,
    value: number,
  ) {
    setPolicy((prev) => ({
      ...prev,
      [field]: value,
    }));
  }

  function addDomain() {
    const domain = domainInput.trim().toLowerCase();

    const validDomain =
      /^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(domain);

    if (!validDomain) {
      setNotice("올바른 도메인을 입력해 주세요. 예: example.com");
      return;
    }

    if (policy.domains.includes(domain)) {
      setNotice("이미 등록된 도메인입니다.");
      return;
    }

    setPolicy((prev) => ({
      ...prev,
      domains: [...prev.domains, domain],
    }));

    setDomainInput("");
    setNotice("");
  }

  function removeDomain(domain: string) {
    setPolicy((prev) => ({
      ...prev,
      domains: prev.domains.filter((item) => item !== domain),
    }));
  }

  function cancelChanges() {
    setPolicy(clonePolicy(savedPolicy));
    setDomainInput("");
    setNotice("저장 전 변경 내용을 취소했습니다.");
  }

  function saveChanges() {
    const invalid =
      Object.values(policy.roles).some(
        (role) => !Number.isFinite(role.budget) || role.budget < 0,
      ) ||
      !Number.isFinite(policy.monthlyBudget) ||
      policy.monthlyBudget < 0 ||
      !Number.isInteger(policy.dailyTokens) ||
      policy.dailyTokens < 0 ||
      [
        policy.maxConcurrent,
        policy.maxPersonas,
        policy.maxSteps,
        policy.maxMinutes,
      ].some((value) => !Number.isInteger(value) || value < 1);

    if (invalid) {
      setNotice("예산 및 실행 제한값을 확인해 주세요.");
      return;
    }

    setSavedPolicy(clonePolicy(policy));
    setNotice(
      "미리보기 화면에만 변경 내용을 저장했습니다. 서버에는 반영되지 않았습니다.",
    );
  }

  return (
    <div className="admin-resources">
      {/* 페이지 제목 */}
      <div className="admin-resources-heading">
        <div>
          <h1>정책·자원</h1>
          <p>AI 실험에 적용되는 운영 정책과 자원 한도를 설정할 수 있습니다.</p>
        </div>

        <div className="admin-resources-header-actions">
          <button
            type="button"
            className="admin-resources-btn-secondary"
            onClick={cancelChanges}
          >
            <RefreshCw size={15} />
            변경 취소
          </button>

          <button
            type="button"
            className="admin-resources-btn-primary"
            onClick={saveChanges}
            disabled={!hasChanges}
          >
            변경 저장
          </button>
        </div>
      </div>

      {notice && (
        <div className="admin-resources-notice" role="status">
          <CheckCircle2 size={16} />
          <span>{notice}</span>
          <button
            type="button"
            aria-label="알림 닫기"
            onClick={() => setNotice("")}
          >
            <X size={16} />
          </button>
        </div>
      )}

      <div className="admin-resources-columns">
        {/* ================================
            왼쪽 열
        ================================ */}
        <div className="admin-resources-column">
          {/* 역할별 AI 모델 / 예산 */}
          <section className="admin-resources-card">
            <div className="admin-resources-card-heading">
              <div className="admin-resources-card-icon purple">
                <Sparkles size={20} />
              </div>
              <div>
                <h2>역할별 AI 모델 · 예산</h2>
                <p>역할별 모델을 지정하고 비용 사용 상한을 설정하세요.</p>
              </div>
            </div>

            <div className="admin-resources-role-grid">
              {ROLES.map(({ key, name }) => (
                <div key={key} className="admin-resources-role-card">
                  <div className={`admin-resources-role-name role-${key}`}>
                    <span className="admin-resources-role-dot" />
                    {name}
                  </div>

                  <label className="admin-resources-field">
                    <span>AI 모델</span>
                    <select
                      value={policy.roles[key].model}
                      onChange={(event) =>
                        updateRole(key, "model", event.target.value)
                      }
                    >
                      {MODEL_OPTIONS.map((model) => (
                        <option key={model} value={model}>
                          {model}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="admin-resources-field">
                    <span>실행당 예산 (USD)</span>
                    <input
                      type="number"
                      min="0"
                      step="0.5"
                      value={policy.roles[key].budget}
                      onChange={(event) =>
                        updateRole(key, "budget", event.target.valueAsNumber)
                      }
                    />
                  </label>
                </div>
              ))}
            </div>

            <div className="admin-resources-divider" />

            <div className="admin-resources-field-grid">
              <label className="admin-resources-field">
                <span>월 예산 상한</span>
                <div className="admin-resources-unit-field">
                  <input
                    type="number"
                    min="0"
                    value={policy.monthlyBudget}
                    onChange={(event) =>
                      updateNumber("monthlyBudget", event.target.valueAsNumber)
                    }
                  />
                  <span>USD</span>
                </div>
              </label>

              <label className="admin-resources-field">
                <span>일일 토큰 예산</span>
                <div className="admin-resources-unit-field">
                  <input
                    type="number"
                    min="0"
                    step="1"
                    value={policy.dailyTokens}
                    onChange={(event) =>
                      updateNumber("dailyTokens", event.target.valueAsNumber)
                    }
                  />
                  <span>tokens</span>
                </div>
              </label>
            </div>

            <p className="admin-resources-footnote">
              ※ 화면의 모델명·예산 숫자는 데모 예시입니다. 실제 저장 가능한 값은
              API 명세에 맞춰 확정합니다.
            </p>
          </section>

          {/* 허용 사이트 목록 */}
          <section className="admin-resources-card">
            <div className="admin-resources-card-heading">
              <div className="admin-resources-card-icon mint">
                <List size={21} />
              </div>
              <div>
                <h2>허용 사이트 목록</h2>
                <p>실험 에이전트가 접근할 수 있는 도메인만 등록하세요.</p>
              </div>
            </div>

            <div className="admin-resources-field">
              <label htmlFor="admin-domain-input">허용 도메인 입력</label>
              <div className="admin-resources-domain-input-row">
                <input
                  id="admin-domain-input"
                  type="text"
                  placeholder="예: example.com"
                  value={domainInput}
                  onChange={(event) => setDomainInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addDomain();
                    }
                  }}
                />
                <button type="button" onClick={addDomain}>
                  <Plus size={14} />
                  추가
                </button>
              </div>
            </div>

            <div className="admin-resources-domains">
              {policy.domains.map((domain) => (
                <span key={domain} className="admin-resources-domain-chip">
                  {domain}
                  <button
                    type="button"
                    aria-label={`${domain} 삭제`}
                    onClick={() => removeDomain(domain)}
                  >
                    <X size={13} />
                  </button>
                </span>
              ))}
            </div>

            <p className="admin-resources-footnote">
              서브도메인·와일드카드 허용 범위는 백엔드 정책에 맞춰 확인해야
              합니다.
            </p>
          </section>
        </div>

        {/* ================================
            오른쪽 열
        ================================ */}
        <div className="admin-resources-column">
          {/* 실험 실행 제한 */}
          <section className="admin-resources-card">
            <div className="admin-resources-card-heading">
              <div className="admin-resources-card-icon blue">
                <SlidersHorizontal size={21} />
              </div>
              <div>
                <h2>실험 실행 제한</h2>
                <p>시스템 안정성을 위한 전역 제한값을 관리하세요.</p>
              </div>
            </div>

            <div className="admin-resources-field-grid">
              <NumberField
                label="최대 동시 실행 수"
                unit="건"
                value={policy.maxConcurrent}
                onChange={(value) => updateNumber("maxConcurrent", value)}
              />
              <NumberField
                label="실험당 Persona 상한"
                unit="명"
                value={policy.maxPersonas}
                onChange={(value) => updateNumber("maxPersonas", value)}
              />
              <NumberField
                label="Persona당 Step 상한"
                unit="steps"
                value={policy.maxSteps}
                onChange={(value) => updateNumber("maxSteps", value)}
              />
              <NumberField
                label="실행 시간 상한"
                unit="분"
                value={policy.maxMinutes}
                onChange={(value) => updateNumber("maxMinutes", value)}
              />
            </div>

            <div className="admin-resources-info">
              <Info size={16} />
              <div>
                <strong>정책 적용 안내</strong>
                <p>
                  정책 변경은 운영 중인 실험에 영향을 줄 수 있습니다. 실제 적용
                  시점과 제한 방식은 백엔드 정책에 따릅니다.
                </p>
              </div>
            </div>
          </section>

          {/* 긴급 운영 제어 */}
          <section className="admin-resources-card">
            <div className="admin-resources-card-heading">
              <div className="admin-resources-card-icon rose">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h2>긴급 운영 제어</h2>
                <p>실행 중인 모든 실험을 안전하게 중단할 수 있습니다.</p>
              </div>
            </div>

            <p className="admin-resources-emergency-text">
              실행 중인 실험 전체에 중단을 요청합니다. 실험 데이터와 이력은
              삭제되지 않으며, 중단 요청은 감사 로그에 기록되는 운영 동작입니다.
            </p>

            <div className="admin-resources-emergency-actions">
              <strong>⚠ 전체 실험 중단</strong>
              <button type="button" onClick={() => setShowStopDialog(true)}>
                전체 중단 요청
                <span aria-hidden="true">→</span>
              </button>
            </div>

            <p className="admin-resources-footnote">
              ※ 중단 요청 후 최대 10초 내 상태 변화 확인이 목표입니다.
            </p>
          </section>

          {/* 정책 변경 이력 */}
          <section className="admin-resources-card">
            <div className="admin-resources-card-heading">
              <div className="admin-resources-card-icon gray">
                <History size={20} />
              </div>
              <div>
                <h2>정책 변경 이력</h2>
                <p>변경 및 중단 요청은 감사 로그 화면에서 추적합니다.</p>
              </div>
            </div>

            <p className="admin-resources-footnote">
              최근 기록은 A3 사용량·감사 로그에서 조회하세요. 이 화면에서는 실제
              로그 API를 호출하지 않습니다.
            </p>
          </section>
        </div>
      </div>

      {/* 전체 실험 중단 2단계 팝업 */}
      {showStopDialog && (
        <AdminStopModal
          onClose={() => setShowStopDialog(false)}
          onConfirm={() => {
            setShowStopDialog(false);
            setNotice(
              "디자인 미리보기입니다. 실제 실험 중단 요청은 전송되지 않았습니다.",
            );
          }}
        />
      )}
    </div>
  );
}

// 숫자 입력 공통 컴포넌트
function NumberField({
  label,
  unit,
  value,
  onChange,
}: {
  label: string;
  unit: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="admin-resources-field">
      <span>{label}</span>
      <div className="admin-resources-unit-field">
        <input
          type="number"
          min="1"
          step="1"
          value={value}
          onChange={(event) => onChange(event.target.valueAsNumber)}
        />
        <span>{unit}</span>
      </div>
    </label>
  );
}
