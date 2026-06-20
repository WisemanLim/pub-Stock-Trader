//! F5 가상체결 원장 영속화 — postgres(sqlx). DATABASE_URL 설정 시 활성.
//! append-only paper_fills 테이블. 미설정·연결실패 시 None(인메모리 전용 폴백).
//! 로컬 개발: DATABASE_URL 미설정 시 data/paper_book.json 스냅샷으로 영속화.

use crate::paper::{EquityPoint, Fill, PaperBookSnapshot};

const SNAPSHOT_PATH: &str = "data/paper_book.json";

/// 스냅샷을 파일로 저장 — postgres 없는 로컬 개발 환경 영속화.
pub fn save_snapshot(snap: &PaperBookSnapshot) {
    if let Err(e) = save_snapshot_inner(snap) {
        tracing::warn!("paper snapshot save failed: {e}");
    }
}

fn save_snapshot_inner(snap: &PaperBookSnapshot) -> std::io::Result<()> {
    std::fs::create_dir_all("data")?;
    let json = serde_json::to_string_pretty(snap)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::Other, e))?;
    // 원자적 쓰기: tmp 파일에 먼저 쓴 뒤 rename — 부분 쓰기로 인한 파일 손상 방지.
    let tmp = format!("{SNAPSHOT_PATH}.tmp");
    std::fs::write(&tmp, &json)?;
    std::fs::rename(&tmp, SNAPSHOT_PATH)?;
    Ok(())
}

/// 시작 시 스냅샷 로드 — 파일 없거나 파싱 실패 시 None(초기 상태).
pub fn load_snapshot() -> Option<PaperBookSnapshot> {
    let json = std::fs::read_to_string(SNAPSHOT_PATH).ok()?;
    match serde_json::from_str(&json) {
        Ok(snap) => {
            tracing::info!("paper book snapshot loaded from {SNAPSHOT_PATH}");
            Some(snap)
        }
        Err(e) => {
            tracing::warn!("paper snapshot parse error (무시, 초기화): {e}");
            None
        }
    }
}
use sqlx::postgres::PgPoolOptions;
use sqlx::{PgPool, Row};

/// 풀 생성 + 스키마 보장. 실패 시 None(인메모리 폴백).
pub async fn init(dsn: &str) -> Option<PgPool> {
    let pool = PgPoolOptions::new()
        .max_connections(4)
        .connect(dsn)
        .await
        .ok()?;
    let ddl = r#"
        CREATE TABLE IF NOT EXISTS paper_fills (
            id          bigserial PRIMARY KEY,
            ticker      text NOT NULL,
            side        text NOT NULL,
            quantity    double precision NOT NULL,
            fill_price  double precision NOT NULL,
            fee         double precision NOT NULL,
            realized_pnl double precision NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    "#;
    sqlx::query(ddl).execute(&pool).await.ok()?;
    // 멱등키 컬럼 + 부분 UNIQUE 인덱스(기존 테이블에도 적용). NULL 다중 허용 → 키 없는 체결은 무제약.
    sqlx::query("ALTER TABLE paper_fills ADD COLUMN IF NOT EXISTS client_order_id text")
        .execute(&pool)
        .await
        .ok()?;
    sqlx::query(
        "CREATE UNIQUE INDEX IF NOT EXISTS paper_fills_coid_uq \
         ON paper_fills (client_order_id) WHERE client_order_id IS NOT NULL",
    )
    .execute(&pool)
    .await
    .ok()?;
    let ddl_eq = r#"
        CREATE TABLE IF NOT EXISTS paper_equity (
            id         bigserial PRIMARY KEY,
            ts         bigint NOT NULL,
            realized   double precision NOT NULL,
            unrealized double precision NOT NULL,
            equity     double precision NOT NULL
        )
    "#;
    sqlx::query(ddl_eq).execute(&pool).await.ok()?;
    Some(pool)
}

/// 체결 1건 append (불변 기록). 반환 = 적재된 행 수(0 = 멱등키 충돌로 미적재).
pub async fn insert_fill(pool: &PgPool, f: &Fill) -> Result<u64, sqlx::Error> {
    // 멱등키 충돌 시 DO NOTHING — 재전송이 DB까지 도달해도 중복 적재 차단(COMPLIANCE §4.1).
    let res = sqlx::query(
        "INSERT INTO paper_fills (ticker, side, quantity, fill_price, fee, realized_pnl, client_order_id)
         VALUES ($1,$2,$3,$4,$5,$6,$7)
         ON CONFLICT (client_order_id) WHERE client_order_id IS NOT NULL DO NOTHING",
    )
    .bind(&f.ticker)
    .bind(&f.side)
    .bind(f.quantity)
    .bind(f.fill_price)
    .bind(f.fee)
    .bind(f.realized_pnl)
    .bind(&f.client_order_id)
    .execute(pool)
    .await?;
    Ok(res.rows_affected())
}

/// 전체 원장 로딩(시간순) — 시작 시 하이드레이션용.
pub async fn load_fills(pool: &PgPool) -> Result<Vec<Fill>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT ticker, side, quantity, fill_price, fee, realized_pnl, client_order_id
         FROM paper_fills ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| Fill {
            ticker: r.get("ticker"),
            side: r.get("side"),
            quantity: r.get("quantity"),
            fill_price: r.get("fill_price"),
            fee: r.get("fee"),
            realized_pnl: r.get("realized_pnl"),
            client_order_id: r.get("client_order_id"),
        })
        .collect())
}

/// 손익곡선 점 1건 append.
pub async fn insert_equity(pool: &PgPool, p: &EquityPoint) -> Result<(), sqlx::Error> {
    sqlx::query(
        "INSERT INTO paper_equity (ts, realized, unrealized, equity) VALUES ($1,$2,$3,$4)",
    )
    .bind(p.ts)
    .bind(p.realized)
    .bind(p.unrealized)
    .bind(p.equity)
    .execute(pool)
    .await?;
    Ok(())
}

/// 손익곡선 전체 로딩(시간순) — 시작 시 하이드레이션용.
pub async fn load_equity(pool: &PgPool) -> Result<Vec<EquityPoint>, sqlx::Error> {
    let rows = sqlx::query(
        "SELECT ts, realized, unrealized, equity FROM paper_equity ORDER BY id ASC",
    )
    .fetch_all(pool)
    .await?;
    Ok(rows
        .into_iter()
        .map(|r| EquityPoint {
            ts: r.get("ts"),
            realized: r.get("realized"),
            unrealized: r.get("unrealized"),
            equity: r.get("equity"),
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::paper::Fill;

    fn test_fill(coid: &str) -> Fill {
        Fill {
            ticker: "TEST".into(),
            side: "buy".into(),
            quantity: 1.0,
            fill_price: 100.0,
            fee: 0.1,
            realized_pnl: 0.0,
            client_order_id: Some(coid.into()),
        }
    }

    /// postgres 통합 — 멱등키 DB 중복 차단(부분 UNIQUE + ON CONFLICT). TEST_DATABASE_URL 미설정 시 skip.
    /// 실행: `make up` 후 `TEST_DATABASE_URL=postgresql://app:app@localhost:5432/stock_trader cargo test -- --ignored`
    #[tokio::test]
    #[ignore]
    async fn db_idempotency_blocks_duplicate() {
        let dsn = match std::env::var("TEST_DATABASE_URL") {
            Ok(v) => v,
            Err(_) => {
                eprintln!("TEST_DATABASE_URL 미설정 — skip");
                return;
            }
        };
        let pool = init(&dsn).await.expect("postgres 연결/스키마 실패");
        let coid = "it-idem-001";
        // 사전 정리(재실행 멱등).
        sqlx::query("DELETE FROM paper_fills WHERE client_order_id = $1")
            .bind(coid)
            .execute(&pool)
            .await
            .unwrap();

        let f = test_fill(coid);
        let n1 = insert_fill(&pool, &f).await.unwrap();
        let n2 = insert_fill(&pool, &f).await.unwrap(); // 동일 키 재전송
        assert_eq!(n1, 1, "최초 적재 1행");
        assert_eq!(n2, 0, "중복 키 → ON CONFLICT DO NOTHING(0행)");

        let cnt: i64 = sqlx::query_scalar("SELECT count(*) FROM paper_fills WHERE client_order_id = $1")
            .bind(coid)
            .fetch_one(&pool)
            .await
            .unwrap();
        assert_eq!(cnt, 1, "DB 에 멱등키당 단 1건");

        // 키 없는 체결은 무제약(다중 허용).
        let nokey = Fill { client_order_id: None, ..test_fill("x") };
        let a = insert_fill(&pool, &nokey).await.unwrap();
        let b = insert_fill(&pool, &nokey).await.unwrap();
        assert_eq!((a, b), (1, 1), "NULL 키는 부분인덱스 제외 — 둘 다 적재");

        // 정리.
        sqlx::query("DELETE FROM paper_fills WHERE client_order_id = $1 OR (client_order_id IS NULL AND ticker = 'TEST')")
            .bind(coid)
            .execute(&pool)
            .await
            .unwrap();
    }
}
