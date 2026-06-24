# Market Insight Documents

market_insight 도메인은 Bronze를 섹터 인사이트(Pulse·Gap)로 정제하는 **Silver/Gold 계층**을 담당한다.

## Silver

- [SILVER_PULSE_STRATEGY.md](SILVER_PULSE_STRATEGY.md): Pulse Silver 파이프라인 전략·구현 — Bronze 4축 융합, 이종 단위 통약, 시장축(자본 흐름) 통화 중립화, 모멘텀·배지, 멱등성, 품질 한계와 차기.

## 메달리온 위치

```
raw_* (Bronze, domain/master)
   └─> refined_pulse_metric_silver (Silver, 이 도메인)
         └─> pulse_metrics_log (Gold) → GET /api/insight/pulse
```

- 구현 상태 스냅샷(메모리): `silver_pulse_status.md`
- 스키마 SSOT: [`backend/docs/erd.md`](../../../docs/erd.md) §5(Silver)·§6(Gold)
- 차기 Silver: Gap(`refined_gap_insights`)·Sync(`refined_sync_inputs`)는 동일 패턴(축 집계→통약→compute→멱등 replace)으로 확장.
