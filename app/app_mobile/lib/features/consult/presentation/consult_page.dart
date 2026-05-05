import 'dart:async';
import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:go_router/go_router.dart';

import '../../../core/theme/app_colors.dart';

/// Deep Discovery — 웹 `consult/page.tsx` IA·톤을 모바일에 맞게 재구성.
/// 상단: 세션 배지 + 라이브 진행 · 접을 수 있는 레이더/키워드/CTA · 메시지 피드 · 퀵리플라이 + 입력.
class ConsultPage extends StatefulWidget {
  const ConsultPage({super.key});

  @override
  State<ConsultPage> createState() => _ConsultPageState();
}

class _ConsultPageState extends State<ConsultPage> {
  static const _initialAi =
      '안녕하세요. Deep Discovery 세션입니다. 먼저 가치관을 살펴볼게요. 어떤 환경에서 일할 때 가장 에너지가 난다고 느끼나요?';

  static const _phase1Chips = [
    '안정적인 대기업',
    '성장하는 스타트업',
    '연구·학계',
    '아직 잘 모르겠어요',
  ];

  /// 웹 `INDIGO` / 차트 스트로크와 동일 계열.
  static const Color _chartIndigo = Color(0xFF4F46E5);

  final _input = TextEditingController();
  final _focus = FocusNode();
  final _scroll = ScrollController();

  final List<_ChatMsg> _messages = [
    _ChatMsg(id: 'm0', role: _MsgRole.ai, text: _initialAi),
  ];

  var _phase = 1;
  var _dialogStep = 0;
  List<String>? _quickReplies = List<String>.from(_phase1Chips);
  var _keywords = <String>['문제해결', '데이터 기반'];

  @override
  void dispose() {
    _input.dispose();
    _focus.dispose();
    _scroll.dispose();
    super.dispose();
  }

  String _uid() =>
      '${DateTime.now().millisecondsSinceEpoch}-${math.Random().nextInt(1 << 20)}';

  double get _progressPercent {
    if (_phase == 1) return 28 + _dialogStep * 12;
    if (_phase == 2) return 62 + math.min(_dialogStep * 8, 24);
    return 96;
  }

  List<double> get _radarValues {
    const base = [58.0, 62.0, 55.0, 60.0, 52.0];
    final bump = _dialogStep * 3.0 + (_phase - 1) * 8.0;
    return [
      math.min(98, base[0] + bump),
      math.min(98, base[1] + bump - 2),
      math.min(98, base[2] + bump + 4),
      math.min(98, base[3] + bump - 1),
      math.min(98, base[4] + bump + 6),
    ];
  }

  static const _radarLabels = ['구조화', '실행력', '탐구', '협업', '도메인싱크'];

  void _scrollBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOut,
      );
    });
  }

  void _pushKeywords(List<String> tags) {
    setState(() {
      for (final t in tags) {
        if (!_keywords.contains(t)) _keywords.insert(0, t);
      }
      if (_keywords.length > 12) {
        _keywords = _keywords.sublist(0, 12);
      }
    });
  }

  void _runAfterUserMessage(String text) {
    setState(() {
      _messages.add(_ChatMsg(id: _uid(), role: _MsgRole.user, text: text));
      _quickReplies = null;
      _input.clear();
    });
    _scrollBottom();

    Timer(const Duration(milliseconds: 380), () {
      if (!mounted) return;
      setState(() {
        if (_phase == 1 && _dialogStep == 0) {
          _dialogStep = 1;
          _pushKeywords(['가치클러스터', text.length > 10 ? text.substring(0, 10) : text]);
          _messages.add(
            _ChatMsg(
              id: _uid(),
              role: _MsgRole.ai,
              text:
                  '좋습니다. 그 선택과 연결된 최근 경험을 한 문장으로 남겨 주세요. 짧게라도 괜찮습니다.',
            ),
          );
          _scrollBottom();
          return;
        }
        if (_phase == 1 && _dialogStep == 1) {
          _phase = 2;
          _dialogStep = 0;
          _pushKeywords(['성향_요약', '#열정']);
          _messages.add(
            _ChatMsg(
              id: _uid(),
              role: _MsgRole.system,
              text: '가치관 분석이 완료되었습니다. 다음은 실무 역량 검증을 시작하겠습니다.',
            ),
          );
          _messages.add(
            _ChatMsg(
              id: _uid(),
              role: _MsgRole.ai,
              text:
                  'API 장애가 발생했습니다. 우선 어떤 신호를 먼저 확인하고, 롤백 vs 핫픽스 중 무엇을 기준으로 결정하시겠어요? 근거를 짧게 서술해 주세요.',
              cardTitle: '역량 시나리오',
            ),
          );
          _scrollBottom();
          return;
        }
        if (_phase == 2 && _dialogStep == 0) {
          _dialogStep = 1;
          _pushKeywords(['FastAPI_중급', '장애대응', '#성장중심']);
          _messages.add(
            _ChatMsg(
              id: _uid(),
              role: _MsgRole.ai,
              text:
                  '응답을 바탕으로 구조화·우선순위 역량이 확인되었습니다. 잠재력 리포트 초안을 라이브 패널에 반영했습니다.',
            ),
          );
          _phase = 3;
          _scrollBottom();
          return;
        }
        if (_phase == 3) {
          _messages.add(
            _ChatMsg(
              id: _uid(),
              role: _MsgRole.ai,
              text:
                  '추가로 다듬고 싶은 목표가 있으면 이어서 말씀해 주세요. 또는 하단 액션으로 로드맵·코치로 연결할 수 있습니다.',
            ),
          );
          _scrollBottom();
        }
      });
    });
  }

  void _sendInput() {
    final t = _input.text.trim();
    if (t.isEmpty) return;
    if (_phase == 1 && _dialogStep == 0) return;
    _runAfterUserMessage(t);
  }

  void _onChip(String label) {
    if (_phase != 1 || _dialogStep != 0) return;
    _runAfterUserMessage(label);
  }

  bool get _inputLocked => _phase == 1 && _dialogStep == 0;

  void _openLiveAnalysisSheet() {
    final scheme = Theme.of(context).colorScheme;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        final bottomInset = MediaQuery.viewInsetsOf(sheetContext).bottom;
        return Padding(
          padding: EdgeInsets.only(bottom: bottomInset),
          child: DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.78,
            minChildSize: 0.42,
            maxChildSize: 0.95,
            builder: (ctx, scrollController) {
              return Material(
                color: AppColors.slate900,
                borderRadius:
                    const BorderRadius.vertical(top: Radius.circular(20)),
                clipBehavior: Clip.antiAlias,
                child: Column(
                  children: [
                    const SizedBox(height: 10),
                    Container(
                      width: 40,
                      height: 4,
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.22),
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(20, 14, 12, 8),
                      child: Row(
                        children: [
                          Icon(Icons.radar, color: AppColors.indigo600),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '라이브 분석 패널',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(
                                        fontWeight: FontWeight.w800,
                                        color: Colors.white,
                                      ),
                                ),
                                Text(
                                  '역량 레이더 · 키워드 · 한 줄 요약',
                                  style: Theme.of(context)
                                      .textTheme
                                      .labelSmall
                                      ?.copyWith(color: scheme.onSurfaceVariant),
                                ),
                              ],
                            ),
                          ),
                          IconButton(
                            onPressed: () => Navigator.of(sheetContext).pop(),
                            icon: const Icon(Icons.keyboard_arrow_down_rounded),
                            tooltip: '닫기',
                            color: Colors.white70,
                          ),
                        ],
                      ),
                    ),
                    Expanded(
                      child: ListView(
                        controller: scrollController,
                        padding: const EdgeInsets.fromLTRB(16, 0, 16, 28),
                        children: [
                          SizedBox(
                            height: 220,
                            child: RadarChart(
                              _radarData(context),
                              duration: const Duration(milliseconds: 400),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.only(bottom: 8, top: 4),
                            child: Text(
                              '턴이 진행될 때마다 영역이 소폭 갱신됩니다 (목업).',
                              textAlign: TextAlign.center,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelSmall
                                  ?.copyWith(color: scheme.onSurfaceVariant),
                            ),
                          ),
                          Align(
                            alignment: Alignment.centerLeft,
                            child: Text(
                              '라이브 키워드',
                              style: Theme.of(context)
                                  .textTheme
                                  .labelLarge
                                  ?.copyWith(
                                    fontWeight: FontWeight.w700,
                                    color: Colors.white,
                                  ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Wrap(
                            spacing: 8,
                            runSpacing: 8,
                            children: _keywords
                                .map(
                                  (k) => Container(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 10,
                                      vertical: 6,
                                    ),
                                    decoration: BoxDecoration(
                                      borderRadius: BorderRadius.circular(999),
                                      gradient: LinearGradient(
                                        colors: [
                                          AppColors.indigo600
                                              .withValues(alpha: 0.35),
                                          AppColors.slate800,
                                        ],
                                      ),
                                      border: Border.all(
                                        color: AppColors.indigo600
                                            .withValues(alpha: 0.45),
                                      ),
                                    ),
                                    child: Text(
                                      '#$k',
                                      style: TextStyle(
                                        fontSize: 11,
                                        fontWeight: FontWeight.w700,
                                        color: Colors.white
                                            .withValues(alpha: 0.92),
                                      ),
                                    ),
                                  ),
                                )
                                .toList(),
                          ),
                          const SizedBox(height: 14),
                          Container(
                            width: double.infinity,
                            padding: const EdgeInsets.all(12),
                            decoration: BoxDecoration(
                              borderRadius: BorderRadius.circular(14),
                              color: AppColors.indigo600.withValues(alpha: 0.12),
                              border: Border.all(
                                color:
                                    AppColors.indigo600.withValues(alpha: 0.35),
                              ),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '성향 한 줄 (목업)',
                                  style: Theme.of(context)
                                      .textTheme
                                      .labelMedium
                                      ?.copyWith(
                                        fontWeight: FontWeight.w700,
                                        color: AppColors.indigo600,
                                      ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  '에너지 전환·데이터 교차점에서 구조화 실행력이 두드러지는 빌더형',
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodyMedium
                                      ?.copyWith(
                                        color: Colors.white,
                                        height: 1.35,
                                      ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                          FilledButton.icon(
                            onPressed: () {
                              Navigator.of(sheetContext).pop();
                              context.go('/roadmap');
                            },
                            style: FilledButton.styleFrom(
                              backgroundColor: AppColors.indigo600,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(vertical: 14),
                            ),
                            icon: const Icon(Icons.chevron_right_rounded),
                            label: const Text('분석 결과로 로드맵 만들기'),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Expanded(
                                child: OutlinedButton(
                                  onPressed: () {
                                    Navigator.of(sheetContext).pop();
                                    context.go('/');
                                  },
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: Colors.white70,
                                    side: const BorderSide(
                                      color: AppColors.slate700,
                                    ),
                                  ),
                                  child: const Text('Chance 보기'),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: OutlinedButton(
                                  onPressed: () {
                                    Navigator.of(sheetContext).pop();
                                    context.go('/coach');
                                  },
                                  style: OutlinedButton.styleFrom(
                                    foregroundColor: AppColors.indigo600,
                                    side: BorderSide(
                                      color: AppColors.indigo600
                                          .withValues(alpha: 0.5),
                                    ),
                                  ),
                                  child: const Text('AI 코치'),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
  }

  RadarChartData _radarData(BuildContext context) {
    final accent = _chartIndigo;
    return RadarChartData(
      radarTouchData: RadarTouchData(enabled: false),
      dataSets: [
        RadarDataSet(
          dataEntries: List.generate(
            5,
            (i) => RadarEntry(value: _radarValues[i]),
          ),
          fillColor: accent.withValues(alpha: 0.22),
          borderColor: accent,
          borderWidth: 2,
          entryRadius: 3,
        ),
      ],
      radarShape: RadarShape.polygon,
      radarBackgroundColor: Colors.transparent,
      borderData: FlBorderData(show: false),
      radarBorderData: BorderSide(color: Colors.white.withValues(alpha: 0.12)),
      titlePositionPercentageOffset: 0.12,
      titleTextStyle: TextStyle(
        color: Colors.white.withValues(alpha: 0.55),
        fontSize: 10,
        fontWeight: FontWeight.w600,
      ),
      getTitle: (index, angle) {
        if (index >= _radarLabels.length) {
          return RadarChartTitle(text: '', angle: angle);
        }
        return RadarChartTitle(text: _radarLabels[index], angle: angle);
      },
      tickCount: 4,
      ticksTextStyle: TextStyle(
        color: Colors.white.withValues(alpha: 0.25),
        fontSize: 8,
      ),
      tickBorderData: BorderSide(color: Colors.white.withValues(alpha: 0.08)),
      gridBorderData: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final turnIndex =
        _messages.where((m) => m.role != _MsgRole.system).length;

    return Scaffold(
      backgroundColor: AppColors.slate950,
      appBar: AppBar(
        backgroundColor: AppColors.slate950,
        surfaceTintColor: Colors.transparent,
        // actions에 긴 모노스페이스 배지를 두면 제목과 합쳐져 가로 overflow가 납니다.
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text.rich(
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              TextSpan(
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                children: [
                  const TextSpan(text: 'AI 상담실 '),
                  TextSpan(
                    text: 'Deep Discovery',
                    style: TextStyle(
                      color: AppColors.indigo600,
                      fontWeight: FontWeight.w800,
                      fontSize: Theme.of(context).textTheme.titleMedium?.fontSize,
                    ),
                  ),
                ],
              ),
            ),
            Text(
              '실시간 맥락 분석 · 단계별 역량 추출',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: scheme.onSurfaceVariant,
                  ),
            ),
          ],
        ),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 10),
            child: Center(
              child: _LiveAnalysisGoalOrb(onTap: _openLiveAnalysisSheet),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView(
              controller: _scroll,
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              children: [
                _LiveProgressCard(
                  phase: _phase,
                  progressPercent: _progressPercent,
                ),
                const SizedBox(height: 10),
                SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 6,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.slate900,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: AppColors.slate700),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.terminal, size: 14, color: AppColors.indigo600),
                        const SizedBox(width: 8),
                        Text(
                          'session · phase_$_phase · graph_node=live',
                          style: TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 10,
                            color: Colors.white.withValues(alpha: 0.65),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Icon(Icons.bolt, size: 16, color: _ConsultUi.tealSync),
                    const SizedBox(width: 6),
                    Text(
                      'INTERACTIVE · 메시지 피드',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.6,
                            color: scheme.onSurfaceVariant,
                          ),
                    ),
                    const Spacer(),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.slate900,
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Text(
                        'turn_index≈$turnIndex',
                        style: TextStyle(
                          fontFamily: 'monospace',
                          fontSize: 10,
                          color: Colors.white.withValues(alpha: 0.65),
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                ..._messages.map((m) => Padding(
                      padding: const EdgeInsets.only(bottom: 10),
                      child: _MessageBubble(msg: m),
                    )),
                const SizedBox(height: 80),
              ],
            ),
          ),
          Container(
            decoration: BoxDecoration(
              color: AppColors.slate900.withValues(alpha: 0.96),
              border: Border(
                top: BorderSide(color: Colors.white.withValues(alpha: 0.06)),
              ),
            ),
            child: SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (_quickReplies != null && _quickReplies!.isNotEmpty)
                      SizedBox(
                        height: 40,
                        child: ListView.separated(
                          scrollDirection: Axis.horizontal,
                          itemCount: _quickReplies!.length,
                          separatorBuilder: (context, index) =>
                              const SizedBox(width: 8),
                          itemBuilder: (context, i) {
                            final chip = _quickReplies![i];
                            return ActionChip(
                              label: Text(chip),
                              onPressed: () => _onChip(chip),
                              backgroundColor: AppColors.slate800,
                              side: BorderSide(
                                color:
                                    AppColors.indigo600.withValues(alpha: 0.45),
                              ),
                              labelStyle: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                                color: Colors.white.withValues(alpha: 0.9),
                              ),
                            );
                          },
                        ),
                      ),
                    if (_quickReplies != null && _quickReplies!.isNotEmpty)
                      const SizedBox(height: 10),
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _input,
                            focusNode: _focus,
                            enabled: !_inputLocked,
                            minLines: 1,
                            maxLines: 4,
                            style: const TextStyle(color: Colors.white),
                            decoration: InputDecoration(
                              hintText: _inputLocked
                                  ? '위 선택지를 먼저 눌러 주세요 (또는 칩 사용)'
                                  : '답변을 입력하고 전송…',
                              hintStyle: TextStyle(
                                color: Colors.white.withValues(alpha: 0.35),
                              ),
                              filled: true,
                              fillColor: AppColors.slate800,
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(
                                  color: AppColors.slate700,
                                ),
                              ),
                              enabledBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: const BorderSide(
                                  color: AppColors.slate700,
                                ),
                              ),
                              focusedBorder: OutlineInputBorder(
                                borderRadius: BorderRadius.circular(12),
                                borderSide: BorderSide(
                                  color: AppColors.indigo600.withValues(alpha: 0.8),
                                ),
                              ),
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 12,
                              ),
                            ),
                            onSubmitted: (_) => _sendInput(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        IconButton.filled(
                          style: IconButton.styleFrom(
                            backgroundColor: AppColors.indigo600,
                            foregroundColor: Colors.white,
                            disabledBackgroundColor:
                                AppColors.slate700.withValues(alpha: 0.5),
                          ),
                          onPressed: _inputLocked ? null : _sendInput,
                          icon: const Icon(Icons.send_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '가치관 단계는 Quick Reply로 빠르게, 역량 단계는 서술형 입력으로 받습니다.',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                            height: 1.35,
                          ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

abstract final class _ConsultUi {
  static const tealSync = Color(0xFF34D399);
}

enum _MsgRole { ai, user, system }

class _ChatMsg {
  const _ChatMsg({
    required this.id,
    required this.role,
    required this.text,
    this.cardTitle,
  });

  final String id;
  final _MsgRole role;
  final String text;
  final String? cardTitle;
}

class _LiveProgressCard extends StatelessWidget {
  const _LiveProgressCard({
    required this.phase,
    required this.progressPercent,
  });

  final int phase;
  final double progressPercent;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final p = (progressPercent.clamp(0, 100)) / 100.0;

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      decoration: BoxDecoration(
        color: AppColors.slate800,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppColors.slate700),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'LIVE RESULT',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.9,
                  fontSize: 10,
                  color: scheme.onSurfaceVariant,
                ),
          ),
              const SizedBox(height: 6),
              _SyncPulseBadge(),
              const SizedBox(height: 8),
              Text.rich(
                TextSpan(
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                      ),
                  children: [
                    TextSpan(text: '나의 발견 $phase / 3 · '),
                    TextSpan(
                      text: '${progressPercent.round()}%',
                      style: const TextStyle(color: AppColors.indigo600),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 8),
              ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: SizedBox(
                  height: 5,
                  child: Stack(
                    fit: StackFit.expand,
                    children: [
                      Container(color: AppColors.slate700),
                      FractionallySizedBox(
                        alignment: Alignment.centerLeft,
                        widthFactor: p,
                        child: Container(
                          decoration: const BoxDecoration(
                            gradient: LinearGradient(
                              colors: [
                                Color(0xFF4F46E5),
                                Color(0xFF10B981),
                              ],
                            ),
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
              Row(
                children: [
                  Expanded(
                    child: _StepLabel(active: phase >= 1, label: '① 가치관'),
                  ),
                  Expanded(
                    child: _StepLabel(active: phase >= 2, label: '② 역량'),
                  ),
                  Expanded(
                    child: _StepLabel(active: phase >= 3, label: '③ 리포트'),
                  ),
                ],
              ),
            ],
          ),
    );
  }
}

/// 상담탭 톤 — 흰 원 + 인디고 글로우 + idle 펄스 · 탭 바운스 · 리플 · 확장 파동.
class _LiveAnalysisGoalOrb extends StatefulWidget {
  const _LiveAnalysisGoalOrb({required this.onTap});

  final VoidCallback onTap;

  @override
  State<_LiveAnalysisGoalOrb> createState() => _LiveAnalysisGoalOrbState();
}

class _LiveAnalysisGoalOrbState extends State<_LiveAnalysisGoalOrb>
    with TickerProviderStateMixin {
  /// 흰 원 직경 (글로우는 그 밖으로만 퍼짐)
  static const double _orb = 40;

  late final AnimationController _idlePulse;
  late final AnimationController _pressBounce;
  late final AnimationController _waveRing;
  late final Animation<double> _idleBreath;
  late final Animation<double> _bounceScale;

  @override
  void initState() {
    super.initState();
    _idlePulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 2000),
    )..repeat(reverse: true);

    _idleBreath = Tween<double>(begin: 1.0, end: 1.045).animate(
      CurvedAnimation(parent: _idlePulse, curve: Curves.easeInOut),
    );

    _pressBounce = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 520),
    );

    _bounceScale = TweenSequence<double>([
      TweenSequenceItem(
        tween: Tween<double>(begin: 1.0, end: 1.14).chain(
          CurveTween(curve: Curves.easeOutCubic),
        ),
        weight: 32,
      ),
      TweenSequenceItem(
        tween: Tween<double>(begin: 1.14, end: 0.92).chain(
          CurveTween(curve: Curves.easeInOut),
        ),
        weight: 28,
      ),
      TweenSequenceItem(
        tween: Tween<double>(begin: 0.92, end: 1.0).chain(
          CurveTween(curve: Curves.elasticOut),
        ),
        weight: 40,
      ),
    ]).animate(_pressBounce);

    _pressBounce.addStatusListener((status) {
      if (status == AnimationStatus.completed && mounted) {
        _pressBounce.reset();
      }
    });

    _waveRing = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 700),
    );
    _waveRing.addStatusListener((status) {
      if (status == AnimationStatus.completed && mounted) {
        _waveRing.reset();
      }
    });
  }

  @override
  void dispose() {
    _idlePulse.dispose();
    _pressBounce.dispose();
    _waveRing.dispose();
    super.dispose();
  }

  void _handleTap() {
    HapticFeedback.lightImpact();
    _waveRing.forward(from: 0);
    _pressBounce.forward(from: 0);
    widget.onTap();
  }

  List<BoxShadow> _orbShadows(Color indigo, Color indigoSoft) {
    return [
      BoxShadow(
        color: indigoSoft.withValues(alpha: 0.5),
        blurRadius: 18,
        spreadRadius: 1,
      ),
      BoxShadow(
        color: indigo.withValues(alpha: 0.4),
        blurRadius: 12,
        spreadRadius: 0,
      ),
      BoxShadow(
        color: indigo.withValues(alpha: 0.22),
        blurRadius: 6,
        spreadRadius: 2,
      ),
      BoxShadow(
        color: Colors.black.withValues(alpha: 0.22),
        blurRadius: 8,
        offset: const Offset(0, 4),
      ),
    ];
  }

  @override
  Widget build(BuildContext context) {
    final indigo = AppColors.indigo600;
    final indigoSoft = AppColors.sectorMetricAccent;

    return Tooltip(
      message: '라이브 분석 패널',
      child: SizedBox(
        width: 72,
        height: 72,
        child: Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [
            AnimatedBuilder(
              animation: _waveRing,
              builder: (context, child) {
                final v = _waveRing.value;
                if (v <= 0) return const SizedBox.shrink();
                final fade = (1.0 - Curves.easeOutCubic.transform(v)).clamp(0.0, 1.0);
                return IgnorePointer(
                  child: Opacity(
                    opacity: fade * 0.55,
                    child: Transform.scale(
                      scale: 1.0 + v * 1.55,
                      child: Container(
                        width: _orb,
                        height: _orb,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            width: 1.6,
                            color: indigo.withValues(alpha: 0.5),
                          ),
                        ),
                      ),
                    ),
                  ),
                );
              },
            ),
            Material(
              color: Colors.transparent,
              clipBehavior: Clip.none,
              child: InkWell(
                onTap: _handleTap,
                customBorder: const CircleBorder(),
                splashColor: indigo.withValues(alpha: 0.42),
                highlightColor: indigoSoft.withValues(alpha: 0.22),
                splashFactory: InkRipple.splashFactory,
                radius: 34,
                child: SizedBox(
                  width: 72,
                  height: 72,
                  child: Center(
                    child: AnimatedBuilder(
                      animation: Listenable.merge([_idlePulse, _pressBounce]),
                      builder: (context, child) {
                        final breath = _idleBreath.value;
                        final bump = _pressBounce.isDismissed
                            ? 1.0
                            : _bounceScale.value;
                        final scale = breath * bump;
                        return Transform.scale(
                          scale: scale,
                          child: child,
                        );
                      },
                      child: Ink(
                        width: _orb,
                        height: _orb,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.white,
                          boxShadow: _orbShadows(indigo, indigoSoft),
                        ),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(
                              Icons.bolt_rounded,
                              size: 13,
                              color: indigo,
                              shadows: [
                                Shadow(
                                  color: indigo.withValues(alpha: 0.75),
                                  blurRadius: 8,
                                ),
                                Shadow(
                                  color: indigoSoft.withValues(alpha: 0.55),
                                  blurRadius: 12,
                                ),
                              ],
                            ),
                            const SizedBox(height: 1),
                            Text(
                              '라이브',
                              style: TextStyle(
                                fontSize: 7.5,
                                fontWeight: FontWeight.w900,
                                height: 1,
                                letterSpacing: -0.2,
                                color: AppColors.indigo700,
                              ),
                            ),
                            Text(
                              '분석',
                              style: TextStyle(
                                fontSize: 7.5,
                                fontWeight: FontWeight.w900,
                                height: 1,
                                letterSpacing: -0.2,
                                color: AppColors.indigo700,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SyncPulseBadge extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: _ConsultUi.tealSync.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: _ConsultUi.tealSync.withValues(alpha: 0.45),
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _ConsultUi.tealSync,
              boxShadow: [
                BoxShadow(
                  color: _ConsultUi.tealSync.withValues(alpha: 0.6),
                  blurRadius: 6,
                ),
              ],
            ),
          ),
          const SizedBox(width: 6),
          Text(
            'sync',
            style: TextStyle(
              fontSize: 10,
              fontWeight: FontWeight.w800,
              color: _ConsultUi.tealSync,
            ),
          ),
        ],
      ),
    );
  }
}

class _StepLabel extends StatelessWidget {
  const _StepLabel({required this.active, required this.label});

  final bool active;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Text(
      label,
      textAlign: TextAlign.center,
      style: Theme.of(context).textTheme.labelSmall?.copyWith(
            fontSize: 9.5,
            fontWeight: FontWeight.w600,
            color: active
                ? AppColors.indigo600
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.msg});

  final _ChatMsg msg;

  @override
  Widget build(BuildContext context) {
    switch (msg.role) {
      case _MsgRole.system:
        return Center(
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.92,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              color: AppColors.indigo600.withValues(alpha: 0.2),
              border: Border.all(
                color: AppColors.indigo600.withValues(alpha: 0.35),
              ),
            ),
            child: Text(
              msg.text,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: AppColors.indigo600.withValues(alpha: 0.95),
                  ),
            ),
          ),
        );
      case _MsgRole.user:
        return Align(
          alignment: Alignment.centerRight,
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.82,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.indigo600,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(18),
                topRight: Radius.circular(6),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: Text(
              msg.text,
              style: const TextStyle(
                color: Colors.white,
                height: 1.4,
                fontSize: 14,
              ),
            ),
          ),
        );
      case _MsgRole.ai:
        if (msg.cardTitle != null) {
          return Align(
            alignment: Alignment.centerLeft,
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.sizeOf(context).width * 0.9,
              ),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppColors.slate700),
                color: AppColors.slate900,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 8,
                    ),
                    decoration: BoxDecoration(
                      color: AppColors.slate800,
                      borderRadius: const BorderRadius.vertical(
                        top: Radius.circular(15),
                      ),
                      border: Border(
                        bottom: BorderSide(color: AppColors.slate700),
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(Icons.psychology_outlined,
                            size: 16, color: AppColors.indigo600),
                        const SizedBox(width: 6),
                        Text(
                          msg.cardTitle!,
                          style: Theme.of(context)
                              .textTheme
                              .labelLarge
                              ?.copyWith(
                                fontWeight: FontWeight.w700,
                                color: Colors.white,
                              ),
                        ),
                      ],
                    ),
                  ),
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      msg.text,
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                            color: Colors.white.withValues(alpha: 0.92),
                            height: 1.45,
                          ),
                    ),
                  ),
                ],
              ),
            ),
          );
        }
        return Align(
          alignment: Alignment.centerLeft,
          child: Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.88,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: AppColors.slate800,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(6),
                topRight: Radius.circular(18),
                bottomLeft: Radius.circular(18),
                bottomRight: Radius.circular(18),
              ),
            ),
            child: Text(
              msg.text,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    color: Colors.white.withValues(alpha: 0.95),
                    height: 1.45,
                  ),
            ),
          ),
        );
    }
  }
}
