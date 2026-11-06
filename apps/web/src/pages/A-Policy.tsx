import { useState } from 'react';
import { AlertTriangle, Bot, Gauge, Globe2, History, Plus, RefreshCw, ShieldCheck, X } from 'lucide-react';
import AdminStopModal from '../components/AdminStopModal';

type Role = 'researcher' | 'maintainer' | 'admin';

type RolePolicy = {
	model: string;
	budget: number;
};

type NumberField = 'monthlyBudget' | 'dailyTokens' | 'maxConcurrent' | 'maxPersonas' | 'maxSteps' | 'maxMinutes';

type PolicyData = {
	roles: Record<Role, RolePolicy>;
	domains: string[];
} & Record<NumberField, number>;

const INITIAL_POLICY: PolicyData = {
	roles: {
		researcher: { model: 'GPT-4o mini', budget: 5 },
		maintainer: { model: 'GPT-4o', budget: 10 },
		admin: { model: 'GPT-4o', budget: 20 },
	},
	monthlyBudget: 300,
	dailyTokens: 2000000,
	domains: ['gachon.ac.kr', 'example.com', 'uxight.ai'],
	maxConcurrent: 3,
	maxPersonas: 5,
	maxSteps: 60,
	maxMinutes: 30,
};

const ROLES: { key: Role; name: string; title: string }[] = [
	{ key: 'researcher', name: 'Researcher', title: '리서처' },
	{ key: 'maintainer', name: 'Maintainer', title: '메인테이너' },
	{ key: 'admin', name: 'Admin', title: '관리자' },
];

const MODEL_OPTIONS = ['GPT-4o mini', 'GPT-4o'];

const LIMIT_FIELDS: { key: NumberField; label: string }[] = [
	{ key: 'maxConcurrent', label: '최대 동시 실행 수 (건)' },
	{ key: 'maxPersonas', label: '실험당 Persona 상한 (명)' },
	{ key: 'maxSteps', label: 'Persona당 Step 상한 (steps)' },
	{ key: 'maxMinutes', label: '실행 시간 상한 (분)' },
];

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

export default function AdminPolicy() {
	const [policy, setPolicy] = useState<PolicyData>(() => clonePolicy(INITIAL_POLICY));
	const [savedPolicy, setSavedPolicy] = useState<PolicyData>(() => clonePolicy(INITIAL_POLICY));
	const [domainInput, setDomainInput] = useState('');
	const [notice, setNotice] = useState('');
	const [isError, setIsError] = useState(false);
	const [showStopDialog, setShowStopDialog] = useState(false);

	const hasChanges = JSON.stringify(policy) !== JSON.stringify(savedPolicy);

	function showNotice(message: string, error = false) {
		setNotice(message);
		setIsError(error);
	}

	function updateRole(role: Role, field: keyof RolePolicy, value: string | number) {
		setPolicy((prev) => ({ ...prev, roles: { ...prev.roles, [role]: { ...prev.roles[role], [field]: value } } }));
	}

	function updateNumber(field: NumberField, value: number) {
		setPolicy((prev) => ({ ...prev, [field]: value }));
	}

	function addDomain() {
		const domain = domainInput.trim().toLowerCase();
		if (!/^(?:[a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z]{2,}$/i.test(domain)) {
			showNotice('올바른 도메인을 입력해 주세요. 예: example.com', true);
			return;
		}
		if (policy.domains.includes(domain)) {
			showNotice('이미 등록된 도메인입니다.', true);
			return;
		}
		setPolicy((prev) => ({ ...prev, domains: [...prev.domains, domain] }));
		setDomainInput('');
		setNotice('');
	}

	function removeDomain(domain: string) {
		setPolicy((prev) => ({ ...prev, domains: prev.domains.filter((item) => item !== domain) }));
	}

	function cancelChanges() {
		setPolicy(clonePolicy(savedPolicy));
		setDomainInput('');
		showNotice('저장 전 변경 내용을 취소했습니다.');
	}

	function saveChanges() {
		const invalid =
			Object.values(policy.roles).some((role) => !Number.isFinite(role.budget) || role.budget < 0) ||
			!Number.isFinite(policy.monthlyBudget) ||
			policy.monthlyBudget < 0 ||
			!Number.isInteger(policy.dailyTokens) ||
			policy.dailyTokens < 0 ||
			[policy.maxConcurrent, policy.maxPersonas, policy.maxSteps, policy.maxMinutes].some((value) => !Number.isInteger(value) || value < 1);

		if (invalid) {
			showNotice('예산 및 실행 제한값을 확인해 주세요.', true);
			return;
		}

		setSavedPolicy(clonePolicy(policy));
		showNotice('화면에만 변경 내용을 저장했습니다. 정책 API는 아직 연결되지 않아 서버에는 반영되지 않았습니다.');
	}

	return (
		<section className="admin-page" aria-labelledby="admin-policy-title">
			<header className="admin-page-header admin-page-header--actions">
				<div>
					<p className="admin-eyebrow">A2 · POLICY & RESOURCES</p>
					<h1 id="admin-policy-title">정책·자원</h1>
					<p>AI 실험에 적용되는 운영 정책과 자원 한도를 설정할 수 있습니다.</p>
				</div>
				<div className="admin-page-actions">
					<button className="admin-button admin-button--secondary admin-button--accounts-refresh" type="button" onClick={cancelChanges}>
						<RefreshCw size={13} aria-hidden="true" />변경 취소
					</button>
					<button className="admin-button admin-button--primary" type="button" onClick={saveChanges} disabled={!hasChanges}>변경 저장</button>
				</div>
			</header>

			{notice && <p className={`admin-inline-feedback${isError ? ' is-error' : ''}`} role={isError ? 'alert' : 'status'}>{notice}</p>}

			<div className="admin-policy-grid">
				<div className="admin-policy-column">
					<section className="admin-panel admin-form-panel admin-policy-panel">
						<div className="admin-section-title"><span className="admin-section-icon is-purple"><Bot size={17} aria-hidden="true" /></span><div><h2>역할별 AI 모델 · 예산</h2><p>역할별 모델을 지정하고 비용 사용 상한을 설정하세요.</p></div></div>
						<div className="admin-role-model-grid">
							{ROLES.map(({ key, name, title }) => (
								<article className="admin-role-model-card" key={key}>
									<span>{name}</span><small>{title} 계정</small>
									<label>AI 모델
										<select value={policy.roles[key].model} onChange={(event) => updateRole(key, 'model', event.target.value)}>
											{MODEL_OPTIONS.map((model) => <option key={model} value={model}>{model}</option>)}
										</select>
									</label>
									<label>실행당 예산 (USD)
										<input type="number" min="0" step="0.5" value={policy.roles[key].budget} onChange={(event) => updateRole(key, 'budget', event.target.valueAsNumber)} />
									</label>
								</article>
							))}
						</div>
						<div className="admin-policy-subgrid">
							<label>월 예산 상한 (USD)<input type="number" min="0" value={policy.monthlyBudget} onChange={(event) => updateNumber('monthlyBudget', event.target.valueAsNumber)} /></label>
							<label>일일 토큰 예산 (tokens)<input type="number" min="0" step="1" value={policy.dailyTokens} onChange={(event) => updateNumber('dailyTokens', event.target.valueAsNumber)} /></label>
						</div>
						<div className="admin-policy-callout"><Gauge size={15} aria-hidden="true" /><span>화면의 모델명·예산 숫자는 데모 예시입니다. 실제 저장 가능한 값은 API 명세에 맞춰 확정합니다.</span></div>
					</section>

					<section className="admin-panel admin-form-panel admin-policy-panel">
						<div className="admin-section-title"><span className="admin-section-icon is-green"><Globe2 size={17} aria-hidden="true" /></span><div><h2>허용 사이트 목록</h2><p>실험 에이전트가 접근할 수 있는 도메인만 등록하세요.</p></div></div>
						<div className="admin-domain-row">
							<label className="admin-full-field admin-domain-field">허용 도메인 입력
								<input
									type="text"
									placeholder="예: example.com"
									value={domainInput}
									onChange={(event) => setDomainInput(event.target.value)}
									onKeyDown={(event) => {
										if (event.key === 'Enter') {
											event.preventDefault();
											addDomain();
										}
									}}
								/>
							</label>
							<button className="admin-button admin-button--primary" type="button" onClick={addDomain}><Plus size={13} aria-hidden="true" />추가</button>
						</div>
						<div className="admin-domain-chips">
							{policy.domains.map((domain) => (
								<span className="admin-domain-chip" key={domain}>
									{domain}
									<button type="button" aria-label={`${domain} 삭제`} onClick={() => removeDomain(domain)}><X size={11} aria-hidden="true" /></button>
								</span>
							))}
						</div>
						<div className="admin-policy-callout"><ShieldCheck size={15} aria-hidden="true" /><span>서브도메인·와일드카드 허용 범위는 백엔드 정책에 맞춰 확인해야 합니다.</span></div>
					</section>
				</div>

				<div className="admin-policy-column">
					<section className="admin-panel admin-form-panel admin-policy-panel">
						<div className="admin-section-title"><span className="admin-section-icon is-blue"><Gauge size={17} aria-hidden="true" /></span><div><h2>실험 실행 제한</h2><p>시스템 안정성을 위한 전역 제한값을 관리하세요.</p></div></div>
						<div className="admin-form-grid">
							{LIMIT_FIELDS.map(({ key, label }) => (
								<label key={key}>{label}
									<input type="number" min="1" step="1" value={policy[key]} onChange={(event) => updateNumber(key, event.target.valueAsNumber)} />
								</label>
							))}
						</div>
						<div className="admin-policy-callout"><ShieldCheck size={15} aria-hidden="true" /><span>정책 변경은 운영 중인 실험에 영향을 줄 수 있습니다. 실제 적용 시점과 제한 방식은 백엔드 정책에 따릅니다.</span></div>
					</section>

					<section className="admin-panel admin-form-panel admin-policy-panel">
						<div className="admin-section-title"><span className="admin-section-icon is-rose"><AlertTriangle size={17} aria-hidden="true" /></span><div><h2>긴급 운영 제어</h2><p>실행 중인 모든 실험을 안전하게 중단할 수 있습니다.</p></div></div>
						<p className="admin-policy-text">실행 중인 실험 전체에 중단을 요청합니다. 실험 데이터와 이력은 삭제되지 않으며, 중단 요청은 감사 로그에 기록되는 운영 동작입니다.</p>
						<div className="admin-kill-actions admin-policy-kill">
							<button className="admin-button admin-button--danger" type="button" onClick={() => setShowStopDialog(true)}>전체 중단 요청</button>
						</div>
						<div className="admin-policy-callout"><Gauge size={15} aria-hidden="true" /><span>중단 요청 후 최대 10초 내 상태 변화 확인이 목표입니다.</span></div>
					</section>

					<section className="admin-panel admin-form-panel admin-policy-panel">
						<div className="admin-section-title"><span className="admin-section-icon is-purple"><History size={17} aria-hidden="true" /></span><div><h2>정책 변경 이력</h2><p>변경 및 중단 요청은 감사 로그 화면에서 추적합니다.</p></div></div>
						<div className="admin-policy-callout"><ShieldCheck size={15} aria-hidden="true" /><span>최근 기록은 A3 사용량·감사 로그에서 조회하세요. 이 화면에서는 실제 로그 API를 호출하지 않습니다.</span></div>
					</section>
				</div>
			</div>

			{showStopDialog && (
				<AdminStopModal
					onClose={() => setShowStopDialog(false)}
					onConfirm={() => {
						setShowStopDialog(false);
						showNotice('전체 중단 API는 아직 연결되지 않아 실제 중단 요청은 전송되지 않았습니다.');
					}}
				/>
			)}
		</section>
	);
}
