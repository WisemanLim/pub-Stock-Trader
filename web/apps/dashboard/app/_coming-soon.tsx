export default function ComingSoon({
  title,
  icon,
  phase,
  items,
}: {
  title: string;
  icon: string;
  phase: string;
  items: string[];
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 24 }}>{icon}</span>
        <h1 style={{ margin: 0, fontSize: 20, fontWeight: 700, color: 'var(--color-text)' }}>
          {title}
        </h1>
        <span
          style={{
            padding: '2px 8px',
            borderRadius: 4,
            fontSize: 11,
            fontWeight: 700,
            backgroundColor: 'rgba(88,166,255,0.1)',
            color: 'var(--color-accent)',
            border: '1px solid rgba(88,166,255,0.2)',
          }}
        >
          {phase}
        </span>
      </div>

      <div
        style={{
          backgroundColor: 'var(--color-card)',
          border: '1px solid var(--color-border)',
          borderRadius: 8,
          padding: 24,
          maxWidth: 560,
        }}
      >
        <div style={{ fontSize: 13, color: 'var(--color-muted)', marginBottom: 16 }}>
          구현 예정 기능
        </div>
        <ul style={{ margin: 0, padding: '0 0 0 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {items.map((item) => (
            <li key={item} style={{ fontSize: 13, color: 'var(--color-text)', lineHeight: 1.5 }}>
              {item}
            </li>
          ))}
        </ul>
        <div
          style={{
            marginTop: 20,
            padding: '8px 12px',
            backgroundColor: 'rgba(88,166,255,0.06)',
            borderRadius: 4,
            fontSize: 11,
            color: 'var(--color-muted)',
          }}
        >
          PRD v2 → <a href="/.docs/Stock-Trader-PRD.v2.md" style={{ color: 'var(--color-accent)' }}>
            .docs/Stock-Trader-PRD.v2.md
          </a>
        </div>
      </div>
    </div>
  );
}
