// 운영자 화면이 같이 쓰는 표시 형식. 원화 환산 기준을 한 곳에만 둔다.

export const KRW_PER_USD = 1400;

/** USD 비용을 원화로 환산해 '₩ 1,234' 로 쓴다. */
export const formatKrw = (usd: number) => `₩ ${Math.round(usd * KRW_PER_USD).toLocaleString('ko-KR')}`;

/** 서버 시각(ISO)을 '2026-11-10 09:30' 으로 쓴다. */
export const formatTime = (ts: string) => ts.replace('T', ' ').slice(0, 16);
