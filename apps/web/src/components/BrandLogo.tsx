import './BrandLogo.css';

type BrandLogoProps = {
	variant: 'dark-bg' | 'light-bg';
	size: 'hero' | 'form' | 'nav';
	className?: string;
	suffix?: string;
	showWordmark?: boolean;
};

export default function BrandLogo({
	variant,
	size,
	className = '',
	suffix = '',
	showWordmark = true,
}: BrandLogoProps) {
	return (
		<div className={`brand-logo brand-logo--${variant} brand-logo--${size} ${className}`.trim()}>
			<svg className="brand-logo__mark" viewBox="0 0 48 48" aria-hidden="true">
				<rect className="brand-logo__frame" x="3" y="3" width="42" height="42" rx="13" />
				<path className="brand-logo__u" d="M14 14v14a10 10 0 0 0 20 0V14" />
				<path className="brand-logo__cross" d="m16 16 16 16M32 16 16 32" />
			</svg>
			{showWordmark && (
				<span className="brand-logo__wordmark">
					<span className="brand-logo__accent">UX</span>ight{suffix}
				</span>
			)}
		</div>
	);
}