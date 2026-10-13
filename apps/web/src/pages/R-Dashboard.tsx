import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import { API_BASE_URL, apiErrorMessage, authenticatedFetch } from '../auth';

type Project = {
	projectId: number;
	title: string;
	targetUrl: string;
	description: string | null;
};

type LayoutContext = {
	userName: string;
	query: string;
};

async function getProjects(): Promise<Project[]> {
	const response = await authenticatedFetch(`${API_BASE_URL}/api/projects`);
	if (!response.ok) {
		throw new Error(await apiErrorMessage(response, '프로젝트 목록을 불러오지 못했습니다.'));
	}

	const body: unknown = await response.json();
	if (
		typeof body !== 'object' ||
		body === null ||
		!('projects' in body) ||
		!Array.isArray(body.projects) ||
		!body.projects.every(isProject)
	) {
		throw new Error('서버에서 올바르지 않은 프로젝트 목록을 받았습니다.');
	}
	return body.projects;
}

function Icon({ name, size = 18 }: { name: 'plus' | 'arrow' | 'clock' | 'search' | 'settings'; size?: number }) {
	const paths = {
		plus: 'M12 5v14M5 12h14',
		arrow: 'M7 17 17 7M7 7h10v10',
		clock: 'M12 8v4l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
		search: 'm20 20-4.5-4.5M18 10.5a7.5 7.5 0 1 1-15 0 7.5 7.5 0 0 1 15 0Z',
		settings: 'M19.14 12.94a7.3 7.3 0 0 0 0-1.88l2.03-1.58-2-3.46-2.4.97a7.2 7.2 0 0 0-1.63-.94L14.78 3.5h-4l-.36 2.55c-.58.22-1.12.54-1.63.94l-2.4-.97-2 3.46 2.03 1.58a7.3 7.3 0 0 0 0 1.88l-2.03 1.58 2 3.46 2.4-.97c.5.4 1.05.72 1.63.94l.36 2.55h4l.36-2.55a7.2 7.2 0 0 0 1.63-.94l2.4.97 2-3.46-2.03-1.58Z',
	};

	return (
		<svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
			<path d={paths[name]} />
			{name === 'settings' && <circle cx="12.78" cy="12" r="2.5" />}
		</svg>
	);
}

export default function RDashboard() {
	const navigate = useNavigate();
	const { userName, query } = useOutletContext<LayoutContext>();
	const [projects, setProjects] = useState<Project[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [loadError, setLoadError] = useState('');
	const [isCreateOpen, setIsCreateOpen] = useState(false);
	const [editingProject, setEditingProject] = useState<Project | null>(null);
	const [deletingProject, setDeletingProject] = useState<Project | null>(null);
	const [isSubmitting, setIsSubmitting] = useState(false);
	const [isDeleting, setIsDeleting] = useState(false);
	const [formError, setFormError] = useState('');
	const [deleteError, setDeleteError] = useState('');
	const [statusMessage, setStatusMessage] = useState('');
	const [title, setTitle] = useState('');
	const [targetUrl, setTargetUrl] = useState('');
	const [description, setDescription] = useState('');
	const [allowedDomains, setAllowedDomains] = useState('');

	useEffect(() => {
		let active = true;

		getProjects()
			.then((items) => {
				if (active) setProjects(items);
			})
			.catch((error: unknown) => {
				if (active) {
					setLoadError(error instanceof Error ? error.message : '프로젝트 목록을 불러오지 못했습니다.');
				}
			})
			.finally(() => {
				if (active) setIsLoading(false);
			});

		return () => {
			active = false;
		};
	}, []);

	const retryLoadProjects = async () => {
		setIsLoading(true);
		setLoadError('');
		try {
			setProjects(await getProjects());
		} catch (error: unknown) {
			setLoadError(error instanceof Error ? error.message : '프로젝트 목록을 불러오지 못했습니다.');
		} finally {
			setIsLoading(false);
		}
	};

	const filteredProjects = useMemo(
		() => projects.filter((project) =>
			`${project.title} ${project.targetUrl} ${project.description ?? ''}`.toLowerCase().includes(query.toLowerCase()),
		),
		[projects, query],
	);

	const openRunSetting = (project?: Project) => {
		navigate('/run-setting', {
			state: project ? {
				project: { projectId: project.projectId, name: project.title, url: project.targetUrl },
			} : null,
		});
	};

	const openCreateForm = () => {
		setEditingProject(null);
		setTitle('');
		setTargetUrl('');
		setDescription('');
		setAllowedDomains('');
		setFormError('');
		setIsCreateOpen(true);
	};

	const openEditForm = (project: Project) => {
		setEditingProject(project);
		setTitle(project.title);
		setTargetUrl(project.targetUrl);
		setDescription(project.description ?? '');
		setAllowedDomains('');
		setFormError('');
		setIsCreateOpen(true);
	};

	const updateTargetUrl = (value: string) => {
		setTargetUrl(value);
		try {
			setAllowedDomains(new URL(value).hostname);
		} catch {
			setAllowedDomains('');
		}
	};

	const saveProject = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		setFormError('');
		setIsSubmitting(true);

		if (editingProject) {
			try {
				const response = await authenticatedFetch(`${API_BASE_URL}/api/projects/${editingProject.projectId}`, {
					method: 'PATCH',
					headers: { 'Content-Type': 'application/json' },
					body: JSON.stringify({
						title: title.trim(),
						description: description.trim(),
					}),
				});
				if (!response.ok) {
					throw new Error(await apiErrorMessage(response, '프로젝트 수정에 실패했습니다.'));
				}

				setProjects((current) => current.map((project) =>
					project.projectId === editingProject.projectId
						? { ...project, title: title.trim(), description: description.trim() || null }
						: project,
				));
				setIsCreateOpen(false);
				setEditingProject(null);
				setStatusMessage('프로젝트를 수정했습니다.');
			} catch (error: unknown) {
				setFormError(error instanceof Error ? error.message : '프로젝트 수정 중 오류가 발생했습니다.');
			} finally {
				setIsSubmitting(false);
			}
			return;
		}

		let parsedUrl: URL;
		try {
			parsedUrl = new URL(targetUrl);
			if (parsedUrl.protocol !== 'http:' && parsedUrl.protocol !== 'https:') {
				throw new Error('http 또는 https 주소를 입력해 주세요.');
			}
		} catch (error: unknown) {
			setFormError(error instanceof Error ? error.message : '올바른 대상 URL을 입력해 주세요.');
			setIsSubmitting(false);
			return;
		}

		const domains = allowedDomains.split(/[\n,]/).map((domain) => domain.trim()).filter(Boolean);
		if (domains.length === 0) {
			setFormError('허용 도메인을 하나 이상 입력해 주세요.');
			setIsSubmitting(false);
			return;
		}

		try {
			const response = await authenticatedFetch(`${API_BASE_URL}/api/projects`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					title: title.trim(),
					targetUrl: parsedUrl.toString(),
					description: description.trim() || null,
					allowedDomains: domains,
				}),
			});
			if (!response.ok) {
				throw new Error(await apiErrorMessage(response, '프로젝트 생성에 실패했습니다.'));
			}

			const body: unknown = await response.json();
			if (
				typeof body !== 'object' ||
				body === null ||
				!('projectId' in body) ||
				typeof body.projectId !== 'number' ||
				!Number.isFinite(body.projectId)
			) {
				throw new Error('서버에서 올바르지 않은 프로젝트 생성 응답을 받았습니다.');
			}

			const projectId = body.projectId;
			setProjects((current) => [{
				projectId,
				title: title.trim(),
				targetUrl: parsedUrl.toString(),
				description: description.trim() || null,
			}, ...current]);
			setIsCreateOpen(false);
			setStatusMessage('프로젝트를 생성했습니다.');
		} catch (error: unknown) {
			setFormError(error instanceof Error ? error.message : '프로젝트 생성 중 오류가 발생했습니다.');
		} finally {
			setIsSubmitting(false);
		}
	};

	const deleteProject = async () => {
		if (!deletingProject) return;
		setDeleteError('');
		setIsDeleting(true);
		try {
			const response = await authenticatedFetch(`${API_BASE_URL}/api/projects/${deletingProject.projectId}`, {
				method: 'DELETE',
			});
			if (!response.ok) {
				if (response.status === 409) {
					throw new Error('진행 중인 실험이 있어 프로젝트를 삭제할 수 없습니다. 실험이 끝난 뒤 다시 시도해 주세요.');
				}
				throw new Error(await apiErrorMessage(response, '프로젝트 삭제에 실패했습니다.'));
			}

			setProjects((current) => current.filter((project) => project.projectId !== deletingProject.projectId));
			setDeletingProject(null);
			setStatusMessage('프로젝트를 삭제했습니다.');
		} catch (error: unknown) {
			setDeleteError(error instanceof Error ? error.message : '프로젝트 삭제 중 오류가 발생했습니다.');
		} finally {
			setIsDeleting(false);
		}
	};

	return (
		<>
			<div className="rd-welcome-row">
				<h1>안녕하세요, {userName}님<span aria-hidden="true"> 👋</span></h1>
				<button type="button" className="rd-create-button" onClick={openCreateForm}>
					<Icon name="plus" /> 새 프로젝트 생성
				</button>
			</div>
			{statusMessage && <div className="rd-notice" role="status">{statusMessage}</div>}

			<div className="rd-section-heading">
				<div>
					<h2>내 프로젝트</h2>
					<span className="rd-demo-label">실제 프로젝트</span>
				</div>
				<span className="rd-project-count">{filteredProjects.length}개</span>
			</div>

			{isLoading ? (
				<div className="rd-empty-state" role="status"><p>프로젝트를 불러오는 중입니다.</p></div>
			) : loadError ? (
				<div className="rd-empty-state" role="alert">
					<p>{loadError}</p>
					<button type="button" onClick={retryLoadProjects}>다시 시도</button>
				</div>
			) : filteredProjects.length > 0 ? (
				<div className="rd-project-grid">
					{filteredProjects.map((project) => (
						<article className="rd-project-card" key={project.projectId}>
							<div className="rd-project-card-top">
								<span className="rd-project-avatar">{project.title.slice(0, 1)}</span>
								<div className="rd-project-title">
									<h3>{project.title}</h3>
									<a href={project.targetUrl} target="_blank" rel="noreferrer">{project.targetUrl.replace(/^https?:\/\//, '')}</a>
								</div>
								<button type="button" className="rd-open-project" aria-label={`${project.title} 열기`} onClick={() => openRunSetting(project)}>
									<Icon name="arrow" />
								</button>
							</div>
							<p className="rd-project-description">{project.description || '설명이 없습니다.'}</p>
							<div className="rd-project-stats">
								<div><span>프로젝트 ID</span><strong>{project.projectId}</strong></div>
								<div><span>대상 도메인</span><strong>{new URL(project.targetUrl).hostname}</strong></div>
								<div><span>실험 이력</span><strong>실험 연결 단계에서 표시</strong></div>
							</div>
							<footer className="rd-project-footer">
								<button type="button" onClick={() => navigate('/monitor')}><Icon name="clock" size={14} /> History</button>
								<div className="rd-project-actions">
									<button type="button" onClick={() => openEditForm(project)}>수정</button>
									<button type="button" className="rd-project-delete-button" onClick={() => {
										setDeletingProject(project);
										setDeleteError('');
									}}>삭제</button>
									<button type="button" className="rd-config-button" onClick={() => openRunSetting(project)}><Icon name="settings" size={15} /> 실험 설정</button>
								</div>
							</footer>
						</article>
					))}
				</div>
			) : projects.length > 0 ? (
				<div className="rd-empty-state">
					<Icon name="search" size={26} />
					<p>검색 결과가 없습니다.</p>
				</div>
			) : (
				<div className="rd-empty-state">
					<p>아직 등록된 프로젝트가 없습니다.</p>
					<button type="button" onClick={openCreateForm}>첫 프로젝트 만들기</button>
				</div>
			)}

			{isCreateOpen && (
				<div className="rd-modal-backdrop" onMouseDown={(event) => {
					if (event.target === event.currentTarget && !isSubmitting) setIsCreateOpen(false);
				}}>
					<section className="rd-modal" role="dialog" aria-modal="true" aria-labelledby="project-create-title">
						<button className="rd-modal-close" type="button" aria-label="닫기" disabled={isSubmitting} onClick={() => setIsCreateOpen(false)}>×</button>
						<h2 id="project-create-title">{editingProject ? '프로젝트 수정' : '새 프로젝트'}</h2>
						<p>{editingProject ? '프로젝트 이름과 설명을 수정할 수 있습니다.' : '분석할 웹사이트와 Agent가 탐색할 수 있는 도메인을 등록합니다.'}</p>
						<form onSubmit={saveProject}>
							<label>
								프로젝트 이름
								<input autoFocus required maxLength={100} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="예: 가천대 포털" />
							</label>
							{editingProject ? (
								<label>
									대상 URL <span className="rd-form-optional">수정 불가</span>
									<input type="url" readOnly value={targetUrl} />
								</label>
							) : (
								<label>
									대상 URL
									<input type="url" required maxLength={2048} value={targetUrl} onChange={(event) => updateTargetUrl(event.target.value)} placeholder="https://www.example.com" />
								</label>
							)}
							<label>
								설명 <span className="rd-form-optional">선택</span>
								<textarea maxLength={1000} value={description} onChange={(event) => setDescription(event.target.value)} placeholder="프로젝트에 대한 설명" />
							</label>
							{!editingProject && (
								<label>
									허용 도메인
									<textarea required value={allowedDomains} onChange={(event) => setAllowedDomains(event.target.value)} placeholder="example.com" />
									<span className="rd-form-help">쉼표 또는 줄바꿈으로 여러 도메인을 입력할 수 있습니다. 대상 URL의 도메인을 기본으로 사용합니다.</span>
								</label>
							)}
							{formError && <p className="rd-form-error" role="alert">{formError}</p>}
							<div className="rd-modal-actions">
								<button className="rd-cancel-button" type="button" disabled={isSubmitting} onClick={() => setIsCreateOpen(false)}>취소</button>
								<button className="rd-create-button" type="submit" disabled={isSubmitting}>{isSubmitting ? '저장 중…' : editingProject ? '변경사항 저장' : '프로젝트 생성'}</button>
							</div>
						</form>
					</section>
				</div>
			)}
			{deletingProject && (
				<div className="rd-modal-backdrop" onMouseDown={(event) => {
					if (event.target === event.currentTarget && !isDeleting) setDeletingProject(null);
				}}>
					<section className="rd-modal rd-delete-modal" role="alertdialog" aria-modal="true" aria-labelledby="project-delete-title" aria-describedby="project-delete-description">
						<button className="rd-modal-close" type="button" aria-label="닫기" disabled={isDeleting} onClick={() => setDeletingProject(null)}>×</button>
						<h2 id="project-delete-title">프로젝트 삭제</h2>
						<p id="project-delete-description"><strong>{deletingProject.title}</strong> 프로젝트를 삭제할까요? 프로젝트 데이터는 목록에서 숨겨지며, 기존 실험 기록은 보존됩니다.</p>
						{deleteError && <p className="rd-form-error" role="alert">{deleteError}</p>}
						<div className="rd-modal-actions">
							<button className="rd-cancel-button" type="button" disabled={isDeleting} onClick={() => setDeletingProject(null)}>취소</button>
							<button className="rd-project-delete-confirm" type="button" disabled={isDeleting} onClick={() => void deleteProject()}>
								{isDeleting ? '삭제 중…' : '프로젝트 삭제'}
							</button>
						</div>
					</section>
				</div>
			)}
		</>
	);
}

function isProject(value: unknown): value is Project {
	if (typeof value !== 'object' || value === null) return false;
	if (!('projectId' in value &&
		typeof value.projectId === 'number' &&
		Number.isFinite(value.projectId) &&
		'title' in value &&
		typeof value.title === 'string' &&
		'targetUrl' in value &&
		typeof value.targetUrl === 'string' &&
		'description' in value &&
		(value.description === null || typeof value.description === 'string'))) {
		return false;
	}
	try {
		const url = new URL(value.targetUrl);
		return url.protocol === 'http:' || url.protocol === 'https:';
	} catch {
		return false;
	}
}
