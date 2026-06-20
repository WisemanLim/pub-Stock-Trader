// BFF — 백엔드 서비스 URL (env 주입, 직접실행/컨테이너 호스트 차이 흡수).
export const SERVICES = {
  ingest: process.env.INGEST_URL ?? 'http://localhost:8003',
  analysis: process.env.ANALYSIS_URL ?? 'http://localhost:8001',
  agents: process.env.AGENTS_URL ?? 'http://localhost:8004',
  rag: process.env.RAG_URL ?? 'http://localhost:8002',
  risk: process.env.RISK_ENGINE_URL ?? 'http://localhost:3001',
} as const;

export type ServiceKey = keyof typeof SERVICES;

export function serviceUrl(key: ServiceKey, path: string): string {
  const base = SERVICES[key];
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}
