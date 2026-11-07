import { useEffect, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';
import type { ProjectDraft } from './researcherTypes';

type LocationState = {
	project?: ProjectDraft;
};

type Persona = {
	personaId: number;
	name: string;
	isCommon: boolean;
};

function isPersona(value: unknown): value is Persona {
	return typeof value === 'object' &&
		value !== null &&
		'personaId' in value &&
		typeof value.personaId === 'number' &&
		Number.isFinite(value.personaId) &&
		'name' in value &&
		typeof value.name === 'string' &&
		'isCommon' in value &&
		typeof value.isCommon === 'boolean';
}

export default function RRunSetting() {
	const location = useLocation();
	const navigate = useNavigate();
	const project = (location.state as LocationState | null)?.project;
	const [personas, setPersonas] = useState<Persona[]>([]);
	const [selectedPersonaIds, setSelectedPersonaIds] = useState<number[]>([]);
	const [goal, setGoal] = useState('');
	const [successUrl, setSuccessUrl] = useState(project?.url ?? '');
	const [mode, setMode] = useState<'diagnose' | 'improve' | 'loop'>('diagnose');
	const [loopMax, setLoopMax] = useState(2);
	const [isLoadingPersonas, setIsLoadingPersonas] = useState(true);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [error, setError] = useState('');

	useEffect(() => {
		let active = true;

		authenticatedFetch(`${API_BASE_URL}/api/personas`)
			.then(async (response) => {
				if (!response.ok) {
					throw new Error(await apiErrorMessage(response, 'Persona 목록을 불러오지 못했습니다.'));
				}
				const body: unknown = await response.json();
				if (
					typeof body !== 'object' ||
					body === null ||
					!('personas' in body) ||
					!Array.isArray(body.personas) ||
					!body.personas.every(isPersona)
				) {
					throw new Error('서버에서 올바르지 않은 Persona 목록을 받지 못했습니다.');
				}
				if (active) {
					setPersonas(body.personas);
					setSelectedPersonaIds(body.personas.map((persona) => persona.personaId));
				}
			})
			.catch((loadError: unknown) => {
				if (active) {
					setError(loadError instanceof Error ? loadError.message : 'Persona 목록을 불러오지 못했습니다.');
				}
			})
			.finally(() => {
				if (active) setIsLoadingPersonas(false);
			});

		return () => {
			active = false;
		};
	}, []);

	const togglePersona = (personaId: number) => {
		setSelectedPersonaIds((current) =>
			current.includes(personaId)
				? current.filter((id) => id !== personaId)
				: [...current, personaId],
		);
	};

	const createExperiment = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setError('');
		if (!project) {
			setError('프로젝트를 먼저 선택해 주세요.');
			return;
		}
		if (selectedPersonaIds.length === 0) {
			setError('실험에 참여할 Persona를 하나 이상 선택해 주세요.');
			return;
		}

		setIsSubmitting(true);
		try {
			const response = await authenticatedFetch(`${API_BASE_URL}/api/projects/${project.projectId}/runs`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					goal: goal.trim(),
					successUrl: new URL(successUrl).toString(),
					personaIds: selectedPersonaIds,
					mode,
					loopMax: mode === 'loop' ? loopMax : null,
				}),
			});
			if (!response.ok) {
				throw new Error(await apiErrorMessage(response, '실험 생성에 실패했습니다.'));
			}

			const body: unknown = await response.json();
			if (
				typeof body !== 'object' ||
				body === null ||
				!('runId' in body) ||
				typeof body.runId !== 'number' ||
				!Number.isFinite(body.runId)
			) {
				throw new Error('서버에서 올바르지 않은 실험 생성 응답을 받지 못했습니다.');
			}
			navigate('/monitor', { state: { createdRunId: body.runId }, replace: true });
		} catch (submitError: unknown) {
			setError(submitError instanceof Error ? submitError.message : '실험 생성 중 오류가 발생했습니다.');
		} finally {
			setIsSubmitting(false);
		}
	};

	if (!project) {
		return (
			<section className="rd-experiment" aria-labelledby="experiment-title">
				<div className="rd-page-heading">
					<h1 id="experiment-title">실험 설정</h1>
				</div>
				<div className="rd-empty-state" role="alert">
					<p>실험을 시작하려면 대시보드에서 프로젝트를 선택해 주세요.</p>
					<button type="button" onClick={() => navigate('/dashboard')}>대시보드로 돌아가기</button>
				</div>
			</section>
		);
	}

	return (
		<section className="rd-experiment" aria-labelledby="experiment-title">
			<div className="rd-page-heading">
				<div>
					<button type="button" className="rd-back-button" onClick={() => navigate('/dashboard')}>← 대시보드</button>
					<h1 id="experiment-title">실험 설정</h1>
					<p className="rd-setting-project">{project.name}</p>
				</div>
				<span className="rd-demo-label">R2 · Run Setting</span>
			</div>

			<form className="rd-experiment-form" onSubmit={createExperiment}>
				<div className="rd-field-grid">
					<label className="rd-form-field">
						<span>대상 URL</span>
						<input type="url" readOnly value={project.url} />
					</label>
					<label className="rd-form-field">
						<span>Task 목표</span>
						<input
							type="text"
							required
							maxLength={200}
							value={goal}
							onChange={(event) => setGoal(event.target.value)}
							placeholder="예: 장학금 신청 방법을 찾아라"
						/>
					</label>
					<label className="rd-form-field">
						<span>성공 URL</span>
						<input
							type="url"
							required
							maxLength={2048}
							value={successUrl}
							onChange={(event) => setSuccessUrl(event.target.value)}
							placeholder="https://www.example.com/success"
						/>
					</label>
				</div>

				<section className="rd-settings-card" aria-labelledby="persona-title">
					<div className="rd-settings-card-heading">
						<div>
							<h2 id="persona-title">Persona</h2>
							<p>실험에 참여할 가상 사용자를 선택합니다.</p>
						</div>
						<span className="rd-project-count">{selectedPersonaIds.length}명 선택</span>
					</div>
					{isLoadingPersonas ? (
						<p role="status">Persona 목록을 불러오는 중입니다.</p>
					) : personas.length > 0 ? (
						<fieldset className="rd-choice-group">
							<legend>참여 Persona</legend>
							{personas.map((persona) => (
								<label className="rd-check-choice" key={persona.personaId}>
									<input
										type="checkbox"
										checked={selectedPersonaIds.includes(persona.personaId)}
										onChange={() => togglePersona(persona.personaId)}
									/>
									<span>{persona.name}{persona.isCommon ? ' · 공용' : ''}</span>
								</label>
							))}
						</fieldset>
					) : !error ? (
						<p>선택할 수 있는 Persona가 없습니다.</p>
					) : null}
				</section>

				<section className="rd-settings-card" aria-labelledby="options-title">
					<div className="rd-settings-card-heading">
						<div>
							<h2 id="options-title">실험 범위</h2>
							<p>실험 요청에 포함할 파이프라인 단계를 선택합니다.</p>
						</div>
					</div>
					<div className="rd-option-row">
						<span className="rd-option-label">파이프라인 범위</span>
						<div className="rd-segmented-control">
							{([
								['diagnose', '진단까지'],
								['improve', '개선안까지'],
								['loop', '루프까지'],
							] as const).map(([value, label]) => (
								<button
									className={mode === value ? 'is-selected' : ''}
									key={value}
									type="button"
									onClick={() => setMode(value)}
								>
									{label}
								</button>
							))}
							{mode === 'loop' && (
								<label className="rd-repeat-control">
									<input
										type="number"
										min="1"
										max="5"
										value={loopMax}
										onChange={(event) => setLoopMax(Math.min(5, Math.max(1, Number(event.target.value))))}
										aria-label="최대 회차"
									/>
									회
								</label>
							)}
						</div>
					</div>
				</section>

				{error && <p className="rd-form-error" role="alert">{error}</p>}
				<div className="rd-experiment-actions">
					<button type="button" className="rd-start-button" onClick={() => navigate('/monitor')}>
						모니터로 이동
					</button>
					<button type="submit" className="rd-save-button" disabled={isSubmitting || isLoadingPersonas}>
						{isSubmitting ? '실험 생성 중…' : '실험 시작'}
					</button>
				</div>
			</form>
		</section>
	);
}
