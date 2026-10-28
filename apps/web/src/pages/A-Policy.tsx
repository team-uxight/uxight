import { useState } from 'react';
import { AlertTriangle, Bot, Gauge, Globe2, Layers3, ShieldCheck } from 'lucide-react';

export default function AdminPolicy() {
	const [saved, setSaved] = useState(false);
	const [killNotice, setKillNotice] = useState('');

	return (
		<section className="admin-page" aria-labelledby="admin-policy-title">
			<header className="admin-page-header admin-page-header--actions">
				<div>
					<p className="admin-eyebrow">A2 · POLICY & RESOURCES</p>
					<h1 id="admin-policy-title">정책·자원</h1>
					<p>실험 운영 정책과 자원 한도를 관리합니다.</p>
					<p className="admin-header-caption">필드 목록 및 정책값 구성 · R2 입력 폼은 이 필드의 부분집합</p>
				</div>
				<div className="admin-page-actions">
					<button className="admin-button admin-button--secondary" type="button" onClick={() => setSaved(false)}>취소</button>
					<button className="admin-button admin-button--primary" type="button" onClick={() => setSaved(true)}>저장</button>
				</div>
			</header>

			{saved && <p className="admin-inline-feedback" role="status">화면 시안입니다. 정책 저장은 아직 연결되지 않았습니다.</p>}

			<div className="admin-policy-grid">
				<section className="admin-panel admin-form-panel admin-policy-panel">
					<div className="admin-section-title"><span className="admin-section-icon is-purple"><Bot size={17} aria-hidden="true" /></span><div><h2>역할별 AI 모델 · 예산</h2><p>역할에 따라 사용할 모델과 예산을 설정합니다.</p></div></div>
					<div className="admin-role-model-grid">
						{[
							{ role: 'Researcher', title: '리서처', model: 'GPT-4o mini', budget: '₩ 50,000' },
							{ role: 'Maintainer', title: '메인테이너', model: 'GPT-5', budget: '₩ 200,000' },
							{ role: 'Admin', title: '관리자', model: 'GPT-4o', budget: '₩ 500,000' },
						].map(({ role, title, model, budget }) => (
							<article className="admin-role-model-card" key={role}>
								<span>{role}</span><small>{title} 계정</small>
								<label>사용 모델<select defaultValue={model}><option>{model}</option></select></label>
								<label>월 예산<input defaultValue={budget} /></label>
							</article>
						))}
					</div>
					<div className="admin-policy-subgrid">
						<label>월 총 비용 상한<input defaultValue="₩ 5,000,000" /></label>
						<label>run 당 비용 상한<input defaultValue="₩ 50,000" /></label>
					</div>
				</section>

				<section className="admin-panel admin-form-panel admin-policy-panel">
					<div className="admin-section-title"><span className="admin-section-icon is-green"><Layers3 size={17} aria-hidden="true" /></span><div><h2>실험 실행 제한</h2><p>안정적인 실행을 위한 상한을 설정합니다.</p></div></div>
					<div className="admin-form-grid">
						<label>동시 실행 수<input defaultValue="3" inputMode="numeric" /></label>
						<label>실행당 Persona 수<input defaultValue="5" inputMode="numeric" /></label>
						<label>Persona step 상한<input defaultValue="50" inputMode="numeric" /></label>
						<label>실행 시간 상한 (분)<input defaultValue="120" inputMode="numeric" /></label>
					</div>
					<div className="admin-policy-callout"><Gauge size={15} aria-hidden="true" /><span>상한에 도달하면 새 실행은 대기 상태로 유지됩니다.</span></div>
				</section>

				<section className="admin-panel admin-form-panel admin-policy-panel">
					<div className="admin-section-title"><span className="admin-section-icon is-blue"><Globe2 size={17} aria-hidden="true" /></span><div><h2>도메인 허용 목록</h2><p>Agent가 접근할 수 있는 도메인을 제한합니다.</p></div></div>
					<label className="admin-full-field">허용 도메인 · 한 줄에 하나<textarea defaultValue={'example.com\nresearch.example.org'} rows={4} /></label>
					<div className="admin-policy-callout"><ShieldCheck size={15} aria-hidden="true" /><span>허용 목록 밖의 도메인 접근은 Agent 안전 정책에 따라 차단됩니다.</span></div>
				</section>

				<section className="admin-panel admin-form-panel admin-policy-panel admin-resource-panel">
					<div className="admin-section-title"><span className="admin-section-icon is-rose"><ShieldCheck size={17} aria-hidden="true" /></span><div><h2>테스트 계정 풀</h2><p>실험에 사용할 계정 자격 증명 풀을 관리합니다.</p></div></div>
					<div className="admin-resource-empty"><ShieldCheck size={20} aria-hidden="true" /><strong>테스트 계정 관리 API 준비 중</strong><span>자격 증명은 안전하게 보관되며 이 화면에서는 아직 관리할 수 없습니다.</span></div>
				</section>
			</div>

			<section className="admin-panel admin-kill-panel">
				<div>
					<h2><AlertTriangle size={17} aria-hidden="true" />전체 Kill Switch</h2>
					<p>모든 run 즉시 중단</p>
					<small>○ 모든 run 중단 영향 확인<br />○ 최종 확인 후 모든 run 즉시 중단</small>
				</div>
				<div className="admin-kill-actions">
					<button className="admin-button admin-button--danger-soft" type="button" onClick={() => setKillNotice('영향 확인 · 현재는 실제 중단 요청이 전송되지 않습니다.')}>영향 확인</button>
					<button className="admin-button admin-button--danger" type="button" onClick={() => setKillNotice('전체 중단은 API 연결 후 사용할 수 있습니다.')}>전체 중단</button>
				</div>
			</section>
			{killNotice && <p className="admin-inline-feedback" role="status">{killNotice}</p>}
			<p className="admin-demo-note">정책 저장 및 Kill Switch API는 아직 연결되지 않았습니다. 입력값은 저장되지 않습니다.</p>
		</section>
	);
}
