import 'dart:async';

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../data/dashboard_mock_data.dart';
import '../../../../core/theme/app_colors.dart';

/// 실시간 펄스 — 웹 대시보드 IA에 맞춘 다크 톤·티커·인과·브리핑·크로스오버·차트·키워드 클라우드.
class PulseTab extends StatelessWidget {
  const PulseTab({super.key});

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 32),
      children: [
        const _PulseHero(),
        const SizedBox(height: 14),
        const _LiveKeywordTicker(),
        const SizedBox(height: 20),
        Text(
          '분야별 트렌드 속도',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 6),
        Text(
          '세로 목록(1×6)으로 분야별 속도를 순서대로 확인하고, 카드를 탭하면 상세로 이동합니다.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 14),
        ...DashboardMockData.pulseSectors.map(
          (s) => Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: _RichSectorCard(
              compact: false,
              sector: s,
              onTap: () => context.push('/pulse/sectors/${s.slug}'),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          '인과관계 체인',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 12),
        const _CausalChainCards(),
        const SizedBox(height: 20),
        Text(
          '3줄 경제 브리핑',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        const _BriefingThreeLines(),
        const SizedBox(height: 12),
        const _BriefingCarousel(),
        const SizedBox(height: 20),
        Text(
          '세대교체 · 크로스오버',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 6),
        Text(
          '기존 수요 vs 신규 수요 — 교차 시점 이후 신규 수요 우위.',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 12),
        const _CrossoverSection(),
        const SizedBox(height: 20),
        Text(
          '모멘텀 · 관심 비중',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        const _PulseChartDeck(),
        const SizedBox(height: 20),
        Text(
          '급상승 키워드 클라우드',
          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w800,
              ),
        ),
        const SizedBox(height: 10),
        const _RisingKeywordCloud(),
        const SizedBox(height: 16),
        const _LiveKeywordTicker(),
        const SizedBox(height: 16),
        FilledButton.tonalIcon(
          onPressed: () => context.go('/coach'),
          icon: const Icon(Icons.auto_awesome_outlined, size: 20),
          label: const Text('AI 코치에게 이 흐름 물어보기'),
        ),
      ],
    );
  }
}

class _PulseHero extends StatelessWidget {
  const _PulseHero();

  @override
  Widget build(BuildContext context) {
    const hero = DashboardMockData.pulseHero;
    final weekProgress = hero.weekIndex / hero.weekMax;

    return Container(
      width: double.infinity,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(18),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color(0xFF4F46E5),
            Color(0xFF7C3AED),
            Color(0xFF5B21B6),
          ],
        ),
        boxShadow: [
          BoxShadow(
            color: AppColors.indigo600.withValues(alpha: 0.35),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.18),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Text(
                    'GLOBAL PULSE',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Colors.white.withValues(alpha: 0.95),
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1.2,
                        ),
                  ),
                ),
                const Spacer(),
                Icon(Icons.speed_rounded, color: Colors.white.withValues(alpha: 0.85)),
              ],
            ),
            const SizedBox(height: 18),
            Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  '${hero.speedKmh}',
                  style: Theme.of(context).textTheme.displayMedium?.copyWith(
                        fontWeight: FontWeight.w900,
                        color: Colors.white,
                        height: 1,
                        letterSpacing: -1,
                      ),
                ),
                const SizedBox(width: 6),
                Text(
                  hero.unitLabel,
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.85),
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              hero.speedContextLine,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.92),
                    fontWeight: FontWeight.w700,
                  ),
            ),
            const SizedBox(height: 4),
            Text(
              '트렌드 속도계 · 주간 지표 연동',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Colors.white.withValues(alpha: 0.75),
                  ),
            ),
            const SizedBox(height: 18),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '주간 지수 ${hero.weekIndex} / ${hero.weekMax}',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: Colors.white.withValues(alpha: 0.95),
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: weekProgress,
                minHeight: 8,
                backgroundColor: Colors.white.withValues(alpha: 0.22),
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 14),
            Row(
              children: [
                Icon(Icons.trending_up, size: 18, color: Colors.greenAccent.shade200),
                const SizedBox(width: 6),
                Text(
                  hero.deltaShort,
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w600,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(
              hero.insightLine,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white.withValues(alpha: 0.88),
                    height: 1.45,
                  ),
            ),
          ],
        ),
      ),
    );
  }
}

/// 실시간 키워드 티커 — 가로 자동 스크롤.
class _LiveKeywordTicker extends StatefulWidget {
  const _LiveKeywordTicker();

  @override
  State<_LiveKeywordTicker> createState() => _LiveKeywordTickerState();
}

class _LiveKeywordTickerState extends State<_LiveKeywordTicker> {
  final ScrollController _sc = ScrollController();
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _tick());
  }

  void _tick() {
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 40), (_) {
      if (!mounted || !_sc.hasClients) return;
      final max = _sc.position.maxScrollExtent;
      if (max <= 8) return;
      final next = _sc.offset + 0.9;
      _sc.jumpTo(next >= max - 0.5 ? 0 : next);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _sc.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final items = DashboardMockData.pulseTickerItems;
    final doubled = [...items, ...items, ...items];

    return ClipRRect(
      borderRadius: BorderRadius.circular(10),
      child: Container(
        height: 40,
        decoration: BoxDecoration(
          color: scheme.surfaceContainerLow.withValues(alpha: 0.95),
          border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.45)),
        ),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10),
              color: AppColors.indigo600.withValues(alpha: 0.35),
              alignment: Alignment.center,
              child: Text(
                'LIVE',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: Colors.white,
                      fontWeight: FontWeight.w900,
                      letterSpacing: 0.8,
                    ),
              ),
            ),
            Expanded(
              child: ListView.separated(
                controller: _sc,
                scrollDirection: Axis.horizontal,
                physics: const NeverScrollableScrollPhysics(),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                itemCount: doubled.length,
                separatorBuilder: (context, index) => Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 10),
                  child: Icon(Icons.fiber_manual_record, size: 6, color: scheme.outline),
                ),
                itemBuilder: (context, i) {
                  return Center(
                    child: Text(
                      doubled[i],
                      style: Theme.of(context).textTheme.labelMedium?.copyWith(
                            color: scheme.onSurfaceVariant,
                          ),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RichSectorCard extends StatelessWidget {
  const _RichSectorCard({
    required this.sector,
    required this.onTap,
    this.compact = false,
  });

  final PulseSectorCard sector;
  final VoidCallback onTap;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final t = scoreNorm(sector.score);
    final pad = compact ? 8.0 : 14.0;
    final titleStyle = compact
        ? TextStyle(
            fontSize: 11,
            height: 1.18,
            fontWeight: FontWeight.w700,
            color: Theme.of(context).colorScheme.onSurface,
          )
        : Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w800);
    final scoreStyle = compact
        ? TextStyle(
            fontSize: 17,
            height: 1,
            fontWeight: FontWeight.w900,
            color: sector.accent,
          )
        : Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900, color: sector.accent);
    final gapSm = compact ? 3.0 : 6.0;
    final gapMd = compact ? 5.0 : 12.0;
    final gapFoot = compact ? 4.0 : 8.0;
    final progressH = compact ? 3.5 : 7.0;
    final chipPadH = compact ? 5.0 : 8.0;

    return Material(
      color: scheme.surfaceContainerLow.withValues(alpha: 0.9),
      borderRadius: BorderRadius.circular(compact ? 10 : 16),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: EdgeInsets.all(pad),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Text(
                      sector.title,
                      maxLines: compact ? 2 : 4,
                      overflow: TextOverflow.ellipsis,
                      style: titleStyle,
                    ),
                  ),
                  const SizedBox(width: 4),
                  Text('${sector.score}', style: scoreStyle),
                ],
              ),
              SizedBox(height: gapSm),
              Row(
                children: [
                  Flexible(
                    child: Container(
                      padding: EdgeInsets.symmetric(horizontal: chipPadH, vertical: compact ? 1 : 3),
                      decoration: BoxDecoration(
                        color: sector.accent.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(color: sector.accent.withValues(alpha: 0.45)),
                      ),
                      child: Text(
                        sector.status,
                        style: TextStyle(
                          color: sector.accent,
                          fontWeight: FontWeight.w700,
                          fontSize: compact ? 9 : 12,
                        ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ),
                  const Spacer(),
                  Text.rich(
                    TextSpan(
                      style: TextStyle(
                        color: scheme.onSurfaceVariant,
                        fontSize: compact ? 9 : 12,
                      ),
                      children: [
                        const TextSpan(text: '모멘텀 '),
                        TextSpan(
                          text: '${(t * 100).round()}%',
                          style: TextStyle(
                            color: sector.accent,
                            fontWeight: FontWeight.w700,
                            fontSize: compact ? 9 : 12,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              SizedBox(height: gapMd),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: t,
                  minHeight: progressH,
                  backgroundColor:
                      AppColors.gaugeTrackForAccent(sector.accent),
                  color: sector.accent,
                ),
              ),
              SizedBox(height: gapFoot),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      compact ? '상세 · 근거' : '상세 · 근거 · 키워드',
                      style: TextStyle(
                        color: scheme.primary,
                        fontWeight: FontWeight.w600,
                        fontSize: compact ? 9 : 12,
                      ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(Icons.chevron_right, size: compact ? 15 : 20, color: scheme.outline),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  static double scoreNorm(int score) => (score.clamp(0, 100)) / 100.0;
}

/// 인과관계 — 카드 사이 하향 화살표.
class _CausalChainCards extends StatelessWidget {
  const _CausalChainCards();

  @override
  Widget build(BuildContext context) {
    final steps = DashboardMockData.pulseCausalChain;
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: List.generate(steps.length, (i) {
        final s = steps[i];
        final last = i == steps.length - 1;
        return Column(
          children: [
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(14),
                color: scheme.surfaceContainerLow.withValues(alpha: 0.9),
                border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    s.badge,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: AppColors.indigo600,
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    s.title,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    s.detail,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          height: 1.45,
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ),
            if (!last)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Icon(
                  Icons.arrow_downward_rounded,
                  color: scheme.primary.withValues(alpha: 0.85),
                  size: 28,
                ),
              ),
          ],
        );
      }),
    );
  }
}

class _BriefingThreeLines extends StatelessWidget {
  const _BriefingThreeLines();

  @override
  Widget build(BuildContext context) {
    final lines = DashboardMockData.pulseBriefingThreeLines;
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: lines.map((l) {
        final (icon, iconColor) = switch (l.visual) {
          PulseBriefingVisual.fxUp => (Icons.trending_up_rounded, Colors.greenAccent.shade200),
          PulseBriefingVisual.rateHold => (Icons.east_rounded, Colors.lightBlueAccent.shade100),
          PulseBriefingVisual.topicPulse => (Icons.show_chart_rounded, AppColors.indigo600),
        };
        return Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              color: scheme.surfaceContainerLow.withValues(alpha: 0.85),
              border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.35)),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: iconColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Icon(icon, color: iconColor, size: 22),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        l.headline,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        l.body,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              height: 1.45,
                              color: scheme.onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}

class _BriefingCarousel extends StatelessWidget {
  const _BriefingCarousel();

  @override
  Widget build(BuildContext context) {
    final slides = DashboardMockData.pulseBriefingSlides;
    final h = 128.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          '브리핑 카드 (가로 스와이프)',
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: h,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: slides.length,
            separatorBuilder: (context, index) => const SizedBox(width: 12),
            itemBuilder: (context, i) {
              final s = slides[i];
              final scheme = Theme.of(context).colorScheme;
              return SizedBox(
                width: MediaQuery.sizeOf(context).width * 0.72,
                child: Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [
                        scheme.surfaceContainerHigh.withValues(alpha: 0.55),
                        scheme.surfaceContainerLow.withValues(alpha: 0.95),
                      ],
                    ),
                    border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.4)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: AppColors.indigo600.withValues(alpha: 0.25),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          s.tag,
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: AppColors.indigo600,
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        s.headline,
                        style: Theme.of(context).textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w800,
                            ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const Spacer(),
                      Text(
                        s.body,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              height: 1.4,
                              color: scheme.onSurfaceVariant,
                            ),
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _CrossoverLineChart extends StatelessWidget {
  const _CrossoverLineChart();

  @override
  Widget build(BuildContext context) {
    final legacy = DashboardMockData.pulseCrossoverLegacy;
    final neu = DashboardMockData.pulseCrossoverNew;
    final markX = DashboardMockData.pulseCrossoverAtX;
    final scheme = Theme.of(context).colorScheme;

    final spotsL = List<FlSpot>.generate(legacy.length, (i) => FlSpot(i.toDouble(), legacy[i]));
    final spotsN = List<FlSpot>.generate(neu.length, (i) => FlSpot(i.toDouble(), neu[i]));

    return Padding(
      padding: const EdgeInsets.only(right: 6, top: 4),
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: 6,
          minY: 30,
          maxY: 100,
          gridData: FlGridData(
            show: true,
            drawVerticalLine: true,
            verticalInterval: 1,
            horizontalInterval: 15,
            getDrawingHorizontalLine: (v) => FlLine(
              color: scheme.outlineVariant.withValues(alpha: 0.25),
              strokeWidth: 1,
            ),
            getDrawingVerticalLine: (v) => FlLine(
              color: scheme.outlineVariant.withValues(alpha: 0.2),
              strokeWidth: 1,
            ),
          ),
          extraLinesData: ExtraLinesData(
            verticalLines: [
              VerticalLine(
                x: markX,
                color: Colors.white54,
                strokeWidth: 1.2,
                dashArray: [6, 4],
              ),
            ],
          ),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 30,
                interval: 15,
                getTitlesWidget: (v, m) => Text(
                  '${v.toInt()}',
                  style: TextStyle(fontSize: 10, color: scheme.onSurfaceVariant),
                ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: 1,
                getTitlesWidget: (v, m) {
                  final i = v.toInt();
                  if (i < 0 || i > 6) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      'M${i + 1}',
                      style: TextStyle(fontSize: 10, color: scheme.onSurfaceVariant),
                    ),
                  );
                },
              ),
            ),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spotsL,
              isCurved: true,
              barWidth: 2.5,
              color: const Color(0xFF94A3B8),
              dotData: const FlDotData(show: false),
            ),
            LineChartBarData(
              spots: spotsN,
              isCurved: true,
              barWidth: 2.5,
              color: AppColors.indigo600,
              dotData: FlDotData(
                show: true,
                getDotPainter: (s, p, b, i) => FlDotCirclePainter(
                  radius: 3,
                  color: AppColors.indigo600,
                  strokeWidth: 0,
                ),
              ),
            ),
          ],
        ),
        duration: Duration.zero,
      ),
    );
  }
}

class _PulseChartDeck extends StatefulWidget {
  const _PulseChartDeck();

  @override
  State<_PulseChartDeck> createState() => _PulseChartDeckState();
}

class _PulseChartDeckState extends State<_PulseChartDeck>
    with SingleTickerProviderStateMixin {
  late final TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: scheme.surfaceContainerLow.withValues(alpha: 0.75),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: scheme.outlineVariant.withValues(alpha: 0.35)),
          ),
          child: TabBar(
            controller: _tabController,
            labelStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13),
            tabs: const [
              Tab(text: '연간 글로벌 모멘텀'),
              Tab(text: '관심 점유율'),
            ],
          ),
        ),
        const SizedBox(height: 12),
        AnimatedBuilder(
          animation: _tabController,
          builder: (context, _) {
            return IndexedStack(
              index: _tabController.index,
              children: const [
                SizedBox(height: 220, child: _AnnualLineChart()),
                SizedBox(height: 240, child: _ShareDonutChart()),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _CrossoverSection extends StatelessWidget {
  const _CrossoverSection();

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 228, child: _CrossoverLineChart()),
        const SizedBox(height: 8),
        Row(
          children: [
            _LegendDot(color: const Color(0xFF94A3B8), label: '기존 수요'),
            const SizedBox(width: 16),
            _LegendDot(color: AppColors.indigo600, label: '신규 수요'),
            const Spacer(),
            Text(
              '교차 시점',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
      ],
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.labelSmall),
      ],
    );
  }
}

class _AnnualLineChart extends StatelessWidget {
  const _AnnualLineChart();

  @override
  Widget build(BuildContext context) {
    final series = DashboardMockData.pulseAnnualTrendSeries;
    final scheme = Theme.of(context).colorScheme;
    final spots = List<FlSpot>.generate(
      series.length,
      (i) => FlSpot(i.toDouble(), series[i]),
    );

    return Padding(
      padding: const EdgeInsets.only(right: 8, top: 8),
      child: LineChart(
        LineChartData(
          minY: 40,
          maxY: 100,
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: 15,
            getDrawingHorizontalLine: (v) => FlLine(
              color: scheme.outlineVariant.withValues(alpha: 0.35),
              strokeWidth: 1,
            ),
          ),
          titlesData: FlTitlesData(
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 28,
                interval: 15,
                getTitlesWidget: (v, m) => Text(
                  '${v.toInt()}',
                  style: TextStyle(fontSize: 10, color: scheme.onSurfaceVariant),
                ),
              ),
            ),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                interval: 1,
                getTitlesWidget: (v, m) {
                  final i = v.toInt();
                  if (i < 0 || i >= series.length) return const SizedBox.shrink();
                  return Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      'Q${i + 1}',
                      style: TextStyle(fontSize: 10, color: scheme.onSurfaceVariant),
                    ),
                  );
                },
              ),
            ),
            topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
            rightTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          ),
          borderData: FlBorderData(show: false),
          lineBarsData: [
            LineChartBarData(
              spots: spots,
              isCurved: true,
              barWidth: 3,
              color: AppColors.indigo600,
              belowBarData: BarAreaData(
                show: true,
                gradient: LinearGradient(
                  colors: [
                    AppColors.indigo600.withValues(alpha: 0.35),
                    AppColors.indigo600.withValues(alpha: 0.02),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
              ),
              dotData: FlDotData(
                show: true,
                getDotPainter: (s, p, b, i) => FlDotCirclePainter(
                  radius: 4,
                  color: Colors.white,
                  strokeWidth: 2,
                  strokeColor: AppColors.indigo600,
                ),
              ),
            ),
          ],
        ),
        duration: Duration.zero,
      ),
    );
  }
}

class _ShareDonutChart extends StatelessWidget {
  const _ShareDonutChart();

  /// 도넛 조각 구분용 — 모두 첫 번째 분야 카드와 같은 인디고 계열.
  static const _palette = [
    AppColors.sectorMetricAccent,
    Color(0xFF818CF8),
    Color(0xFF4F46E5),
    Color(0xFFA5B4FC),
    Color(0xFF4338CA),
  ];

  @override
  Widget build(BuildContext context) {
    final slices = DashboardMockData.pulseSectorShares;
    final scheme = Theme.of(context).colorScheme;

    return Row(
      children: [
        Expanded(
          flex: 3,
          child: PieChart(
            PieChartData(
              sectionsSpace: 2,
              centerSpaceRadius: 52,
              sections: List.generate(slices.length, (i) {
                final s = slices[i];
                return PieChartSectionData(
                  color: _palette[i % _palette.length],
                  value: s.fraction * 100,
                  title: '${(s.fraction * 100).round()}%',
                  radius: 44,
                  titleStyle: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                );
              }),
            ),
            duration: Duration.zero,
          ),
        ),
        Expanded(
          flex: 2,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: List.generate(slices.length, (i) {
              final s = slices[i];
              return Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(
                  children: [
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        color: _palette[i % _palette.length],
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        s.label,
                        style: Theme.of(context).textTheme.labelSmall?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              );
            }),
          ),
        ),
      ],
    );
  }
}

class _RisingKeywordCloud extends StatelessWidget {
  const _RisingKeywordCloud();

  @override
  Widget build(BuildContext context) {
    final words = DashboardMockData.pulseRisingKeywords;

    return Wrap(
      spacing: 8,
      runSpacing: 10,
      children: words.map((w) {
        return Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            color: AppColors.indigo700.withValues(alpha: 0.45),
            border: Border.all(color: AppColors.indigo600.withValues(alpha: 0.55)),
          ),
          child: Text(
            w,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  color: Colors.white.withValues(alpha: 0.92),
                  fontWeight: FontWeight.w600,
                ),
          ),
        );
      }).toList(),
    );
  }
}
