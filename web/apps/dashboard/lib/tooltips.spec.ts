import { describe, it, expect } from 'vitest';
import { TOOLTIPS } from './tooltips';

describe('TOOLTIPS content', () => {
  describe('persona', () => {
    it('scalper has 전략 and 파라미터 sections', () => {
      expect(TOOLTIPS.persona.scalper).toContain('전략');
      expect(TOOLTIPS.persona.scalper).toContain('파라미터');
      expect(TOOLTIPS.persona.scalper.length).toBeGreaterThan(50);
    });
    it('day has 오버나이트 explanation', () => {
      expect(TOOLTIPS.persona.day).toContain('오버나이트');
    });
    it('swing is marked as default', () => {
      expect(TOOLTIPS.persona.swing).toContain('기본');
    });
    it('position mentions 거시 채널', () => {
      expect(TOOLTIPS.persona.position).toContain('거시 채널');
    });
  });

  describe('menu', () => {
    const keys = ['dashboard', 'portfolio', 'strategy', 'risk', 'backtest', 'agents'] as const;
    keys.forEach((k) => {
      it(`${k} is non-empty string`, () => {
        expect(typeof TOOLTIPS.menu[k]).toBe('string');
        expect(TOOLTIPS.menu[k].length).toBeGreaterThan(20);
      });
    });
  });

  describe('indicator', () => {
    it('rsi mentions 30 and 70 thresholds', () => {
      expect(TOOLTIPS.indicator.rsi).toContain('30');
      expect(TOOLTIPS.indicator.rsi).toContain('70');
    });
    it('macd mentions EMA', () => {
      expect(TOOLTIPS.indicator.macd).toContain('EMA');
    });
    it('bollinger mentions 표준편차', () => {
      expect(TOOLTIPS.indicator.bollinger).toContain('표준편차');
    });
    it('signal has BUY SELL HOLD', () => {
      expect(TOOLTIPS.indicator.signal).toContain('BUY');
      expect(TOOLTIPS.indicator.signal).toContain('SELL');
      expect(TOOLTIPS.indicator.signal).toContain('HOLD');
    });
    it('agentDecision lists all 4 agents', () => {
      expect(TOOLTIPS.indicator.agentDecision).toContain('Scraper');
      expect(TOOLTIPS.indicator.agentDecision).toContain('Analyst');
      expect(TOOLTIPS.indicator.agentDecision).toContain('Portfolio');
      expect(TOOLTIPS.indicator.agentDecision).toContain('Decision');
    });
  });

  describe('risk', () => {
    it('stopLoss mentions 손절 and 슬리피지', () => {
      expect(TOOLTIPS.risk.stopLoss).toContain('손절');
      expect(TOOLTIPS.risk.stopLoss).toContain('슬리피지');
    });
    it('positionLimit lists all persona limits', () => {
      expect(TOOLTIPS.risk.positionLimit).toContain('스캘퍼');
      expect(TOOLTIPS.risk.positionLimit).toContain('포지션');
    });
  });

  describe('panel', () => {
    it('candleChart explains OHLCV', () => {
      expect(TOOLTIPS.panel.candleChart).toContain('Open');
      expect(TOOLTIPS.panel.candleChart).toContain('Volume');
    });
    it('flow mentions KRX', () => {
      expect(TOOLTIPS.panel.flow).toContain('KRX');
    });
  });

  describe('flow', () => {
    it('institution mentions 기관', () => {
      expect(TOOLTIPS.flow.institution).toContain('기관');
    });
    it('foreign mentions 외국인', () => {
      expect(TOOLTIPS.flow.foreign).toContain('외국인');
    });
    it('individual mentions 개인', () => {
      expect(TOOLTIPS.flow.individual).toContain('개인');
    });
  });

  describe('service', () => {
    (['ingest', 'analysis', 'agents', 'risk'] as const).forEach((k) => {
      it(`${k} tooltip mentions port`, () => {
        expect(TOOLTIPS.service[k]).toContain('포트');
      });
    });
  });

  describe('misc', () => {
    it('kospi mentions KRX', () => {
      expect(TOOLTIPS.misc.kospi).toContain('KRX');
    });
    it('persona lists all 4 types', () => {
      expect(TOOLTIPS.misc.persona).toContain('스캘퍼');
      expect(TOOLTIPS.misc.persona).toContain('스윙');
    });
  });
});
