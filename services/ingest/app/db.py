"""SQLAlchemy DB 엔진 + 세션 팩토리 + 테이블 초기화."""
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


class OhlcvDaily(Base):
    """일별 OHLCV (KRX OPEN API 수집분)."""

    __tablename__ = "ohlcv_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_ohlcv_ticker_date"),)

    id: int = Column(Integer, primary_key=True)
    ticker: str = Column(String(12), nullable=False, index=True)
    date: date = Column(Date, nullable=False, index=True)
    open: float = Column(Float)
    high: float = Column(Float)
    low: float = Column(Float)
    close: float = Column(Float)
    volume: int = Column(BigInteger)
    change_pct: float = Column(Float)
    source: str = Column(String(32), default="krx")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class InvestorFlowDaily(Base):
    """일별 투자자별 순매수 (기관/외인/개인)."""

    __tablename__ = "investor_flow_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_flow_ticker_date"),)

    id: int = Column(Integer, primary_key=True)
    ticker: str = Column(String(12), nullable=False, index=True)
    date: date = Column(Date, nullable=False, index=True)
    institution_net: float = Column(Float)
    foreign_net: float = Column(Float)
    individual_net: float = Column(Float)
    source: str = Column(String(32), default="krx")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class MarketAlertDaily(Base):
    """KRX 시장경보 종목 (투자주의/경고/위험/정리매매)."""

    __tablename__ = "market_alert_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", "level", name="uq_alert_ticker_date_level"),)

    id: int = Column(Integer, primary_key=True)
    ticker: str = Column(String(12), nullable=False, index=True)
    date: date = Column(Date, nullable=False, index=True)
    level: str = Column(String(16), nullable=False)  # 투자주의|투자경고|투자위험|정리매매
    name: str = Column(String(64))
    source: str = Column(String(32), default="krx_kind")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


class ShortSellingDaily(Base):
    """일별 공매도 거래 통계."""

    __tablename__ = "short_selling_daily"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_shortsell_ticker_date"),)

    id: int = Column(Integer, primary_key=True)
    ticker: str = Column(String(12), nullable=False, index=True)
    date: date = Column(Date, nullable=False, index=True)
    short_vol: int = Column(BigInteger)      # 공매도 거래량
    short_val: int = Column(BigInteger)      # 공매도 거래대금
    short_ratio: float = Column(Float)       # 공매도 비율 (%)
    source: str = Column(String(32), default="krx_openapi")
    created_at: datetime = Column(DateTime, default=datetime.utcnow)


def _make_engine():
    url = settings.database_url
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    # asyncpg is async-only; sync engine requires psycopg2
    sync_url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return create_engine(sync_url)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """테이블이 없으면 생성 (멱등)."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    """독립 세션 반환 (with 문으로 닫을 것)."""
    return SessionLocal()
