import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown_plus/flutter_markdown_plus.dart';

import '../../../core/theme/app_colors.dart';
import '../data/coach_context.dart';

abstract final class _CoachUi {
  /// 상담 탭 `INTERACTIVE` 줄 아이콘과 동일 틸.
  static const Color tealSync = Color(0xFF34D399);
}

/// 상담 탭 라이브 분석 오브와 동일 계열 — 펄스·바운스·리플·파동 + 월렛 아이콘.
class _CoachWalletOrb extends StatefulWidget {
  const _CoachWalletOrb({required this.onTap});

  final VoidCallback onTap;

  @override
  State<_CoachWalletOrb> createState() => _CoachWalletOrbState();
}

class _CoachWalletOrbState extends State<_CoachWalletOrb>
    with TickerProviderStateMixin {
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
      message: '맥락 및 Insight Wallet',
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
                final fade =
                    (1.0 - Curves.easeOutCubic.transform(v)).clamp(0.0, 1.0);
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
                        return Transform.scale(
                          scale: breath * bump,
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
                              Icons.account_balance_wallet_rounded,
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
                              '맥락',
                              style: TextStyle(
                                fontSize: 7.5,
                                fontWeight: FontWeight.w900,
                                height: 1,
                                letterSpacing: -0.2,
                                color: AppColors.indigo700,
                              ),
                            ),
                            Text(
                              '월렛',
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

/// AI 코치 — 웹 `CoachView` / `InsightWalletPanel` / `mockReply` 흐름에 맞춤.
class CoachPage extends StatefulWidget {
  const CoachPage({super.key});

  @override
  State<CoachPage> createState() => _CoachPageState();
}

class _CoachMessage {
  const _CoachMessage({
    required this.id,
    required this.role,
    required this.text,
    this.code,
    this.badge,
  });

  final String id;
  final String role; // user | assistant
  final String text;
  final String? code;
  final String? badge;
}

class _CoachPageState extends State<CoachPage> {
  static const _pythonSnippet = '''
from dataclasses import dataclass
from enum import Enum

class Factor(str, Enum):
    SCOPE1 = "scope1"
    SCOPE2 = "scope2"

@dataclass(frozen=True)
class ScoreInput:
    factor: Factor
    raw_value: float

class RuleCalculator:
    """룰만 바꿔 끼우기 쉬운 최소 점수기."""

    def total(self, rows: list[ScoreInput]) -> float:
        return sum(r.raw_value for r in rows)

# 가중치 정책은 별도 Policy 객체로 분리하면
# 전국 단위 확장 시에도 교체 범위가 명확합니다.''';

  final _input = TextEditingController();
  final _scroll = ScrollController();
  var _loading = false;
  CoachAttachedContext? _attached = demoAttachedContexts['roadmap'];
  final _messages = <_CoachMessage>[];
  var _wallet = <CoachWalletItem>[];

  String _uid() =>
      '${DateTime.now().millisecondsSinceEpoch}-${math.Random().nextInt(1 << 20)}';

  _CoachMessage _proactiveGreeting() {
    return _CoachMessage(
      id: 'm0',
      role: 'assistant',
      badge: '로드맵 연계 질문',
      text:
          '안녕하세요, Daily Mentor입니다. 지금 로드맵에서는 **탄소 배출 룰 기반 계산**과 **IFRS S1/S2 데이터 맵핑**이 한 묶로 보이고 있어요. "어떤 엔티티까지 공시 스키마에 넣을지"를 먼저 고정하면, 이후 파이프라인·감사 추적까지 덜 흔들립니다. 오늘은 그 경계부터 같이 짚어볼까요?',
    );
  }

  _CoachMessage _mockReply(String userText, CoachAttachedContext? ctx) {
    final t = userText.toLowerCase();
    final fromChance = (ctx?.source == 'chance') ||
        t.contains('지원') ||
        t.contains('강점') ||
        t.contains('부족');

    if (fromChance) {
      return _CoachMessage(
        id: _uid(),
        role: 'assistant',
        text:
            '좋은 공고예요. 지금 역량 스냅샷 기준으로 보면, **FastAPI + PostgreSQL**로 에너지·최적화 도메인 API를 설계해 본 경험과, **ESG 지표를 스키마에 매핑**해 본 흔적은 ‘파이프라인 구축’ 요구에 바로 연결됩니다. 포트폴리오에서는 IFRS S1/S2 흐름을 전면에 두세요.\n\n'
            '보완으로는 공고가 강조하는 **대용량·쿼리 성능**입니다. 로드맵의 ‘룰 기반 계산 엔진’에서 트래픽이 몰렸을 때 **인덱싱·배치·캐시**를 어떻게 잡았는지 로그로 남겨 두면 면접 때 강한 근거가 됩니다. 오늘 그 부분 리뷰할까요?',
      );
    }

    if ((ctx?.source == 'roadmap') ||
        t.contains('룰') ||
        t.contains('규칙') ||
        t.contains('합산') ||
        t.contains('계산')) {
      return _CoachMessage(
        id: _uid(),
        role: 'assistant',
        badge: '기술 스니펫',
        text:
            '추론 모델 대신 룰 기반을 택한 건 **의사결정 속도·감사 가능성** 측면에서 좋은 선택이에요. FastAPI에서는 ‘점수 계산기’를 독립 모듈로 두고, 정책(가중치·상한)만 바꿔 끼우는 구조가 깔끔합니다. 아래 스니펫을 우측 **Insight Wallet**에 저장해 두었다가 로드맵 아카이브에 옮겨 적어 보세요.',
        code: _pythonSnippet,
      );
    }

    return _CoachMessage(
      id: _uid(),
      role: 'assistant',
      text:
          '맥락(로드맵·공고)과 연결해서 답할게요. 구체적으로 어떤 출력(공시 필드, 내부 리포트, API 응답)까지를 목표로 하는지 한 줄만 더 알려주세요.',
    );
  }

  @override
  void initState() {
    super.initState();
    _messages.add(_proactiveGreeting());
    _input.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    super.dispose();
  }

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

  void _addToWallet(_CoachMessage msg) {
    final body = [
      msg.text,
      if (msg.code != null) '\n\n```python\n${msg.code}\n```',
    ].where((s) => s.isNotEmpty).join();
    setState(() {
      _wallet = [
        CoachWalletItem(
          id: _uid(),
          title: '코치 스니펫 · ${msg.badge ?? "응답"}',
          body: body,
          createdAt: DateTime.now().millisecondsSinceEpoch,
        ),
        ..._wallet,
      ];
    });
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Insight Wallet에 저장했습니다.')),
    );
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty || _loading) return;
    setState(() {
      _messages.add(_CoachMessage(id: _uid(), role: 'user', text: text));
      _input.clear();
      _loading = true;
    });
    _scrollBottom();
    await Future<void>.delayed(const Duration(milliseconds: 520));
    if (!mounted) return;
    setState(() {
      _messages.add(_mockReply(text, _attached));
      _loading = false;
    });
    _scrollBottom();
  }

  void _openWalletSheet() {
    final scheme = Theme.of(context).colorScheme;
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      backgroundColor: AppColors.slate900,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return DraggableScrollableSheet(
              expand: false,
              initialChildSize: 0.72,
              minChildSize: 0.35,
              maxChildSize: 0.92,
              builder: (context, scrollController) {
                return ListView(
                  controller: scrollController,
                  padding: const EdgeInsets.fromLTRB(20, 4, 20, 28),
                  children: [
                    Row(
                      children: [
                        Text(
                          '맥락 & 지갑',
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const Spacer(),
                        IconButton(
                          onPressed: () => Navigator.pop(context),
                          icon: const Icon(Icons.close),
                          color: scheme.onSurfaceVariant,
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    _InsightWalletPanelBody(
                      wallet: _wallet,
                      onCopy: (id) {
                        final item = _wallet.firstWhere((w) => w.id == id);
                        Clipboard.setData(ClipboardData(text: item.body));
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(content: Text('클립보드에 복사했습니다.')),
                        );
                      },
                      onRemove: (id) {
                        setState(() {
                          _wallet = _wallet.where((w) => w.id != id).toList();
                        });
                        setModalState(() {});
                      },
                    ),
                  ],
                );
              },
            );
          },
        );
      },
    );
  }

  int get _turnIndex => _messages.length;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final ctxKey = _attached?.source ?? 'none';

    return Scaffold(
      backgroundColor: AppColors.slate950,
      appBar: AppBar(
        backgroundColor: AppColors.slate950,
        surfaceTintColor: Colors.transparent,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'AI 코치',
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
            ),
            Text(
              'Daily Mentor · 맥락·지갑·실행',
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
              child: _CoachWalletOrb(onTap: _openWalletSheet),
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
                        Icon(
                          Icons.psychology_outlined,
                          size: 14,
                          color: AppColors.indigo600,
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'coach · ctx=$ctxKey · mock=on',
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
                    Icon(Icons.bolt, size: 16, color: _CoachUi.tealSync),
                    const SizedBox(width: 6),
                    Text(
                      'INTERACTIVE · 코치 메시지',
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
                        'turn_index≈$_turnIndex',
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
                SizedBox(
                  height: 40,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    children: [
                      ActionChip(
                        label: const Text('데모: 찬스 공고'),
                        onPressed: () => setState(
                          () => _attached = demoAttachedContexts['chance'],
                        ),
                        backgroundColor: AppColors.slate800,
                        side: BorderSide(
                          color: AppColors.indigo600.withValues(alpha: 0.45),
                        ),
                        labelStyle: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 8),
                      ActionChip(
                        label: const Text('데모: 로드맵 스프린트'),
                        onPressed: () => setState(
                          () => _attached = demoAttachedContexts['roadmap'],
                        ),
                        backgroundColor: AppColors.slate800,
                        side: BorderSide(
                          color: AppColors.indigo600.withValues(alpha: 0.45),
                        ),
                        labelStyle: const TextStyle(
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                ..._messages.map(
                  (m) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Align(
                      alignment: m.role == 'user'
                          ? Alignment.centerRight
                          : Alignment.centerLeft,
                      child: m.role == 'user'
                          ? _UserBubble(text: m.text)
                          : _AssistantBubble(
                              msg: m,
                              onSaveWallet: () => _addToWallet(m),
                            ),
                    ),
                  ),
                ),
                if (_loading)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.only(bottom: 10),
                      padding: const EdgeInsets.symmetric(
                        horizontal: 14,
                        vertical: 12,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.slate800,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.slate700),
                      ),
                      child: Text(
                        '응답 작성 중…',
                        style: Theme.of(context).textTheme.labelMedium?.copyWith(
                              color: scheme.onSurfaceVariant,
                            ),
                      ),
                    ),
                  ),
                const SizedBox(height: 80),
              ],
            ),
          ),
          Container(
            decoration: BoxDecoration(
              color: AppColors.slate900.withValues(alpha: 0.96),
              border: Border(
                top: BorderSide(
                  color: Colors.white.withValues(alpha: 0.06),
                ),
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
                    if (_attached != null) ...[
                      Material(
                        color: AppColors.slate800,
                        borderRadius: BorderRadius.circular(12),
                        child: Container(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(12),
                            border: Border(
                              left: BorderSide(
                                color: AppColors.indigo600,
                                width: 4,
                              ),
                            ),
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withValues(alpha: 0.08),
                                blurRadius: 4,
                              ),
                            ],
                          ),
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 8,
                          ),
                          child: Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Icon(
                                Icons.attach_file,
                                size: 18,
                                color: AppColors.indigo600,
                              ),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Text(
                                      '맥락 지시자',
                                      style: Theme.of(context)
                                          .textTheme
                                          .labelSmall
                                          ?.copyWith(
                                            fontWeight: FontWeight.w800,
                                            letterSpacing: 0.4,
                                            color: scheme.onSurfaceVariant,
                                            fontSize: 10,
                                          ),
                                    ),
                                    const SizedBox(height: 4),
                                    Text(
                                      _attached!.label,
                                      style: Theme.of(context)
                                          .textTheme
                                          .bodySmall
                                          ?.copyWith(
                                            fontWeight: FontWeight.w600,
                                            height: 1.35,
                                            color: Colors.white
                                                .withValues(alpha: 0.9),
                                          ),
                                    ),
                                  ],
                                ),
                              ),
                              IconButton(
                                onPressed: () =>
                                    setState(() => _attached = null),
                                icon: const Icon(Icons.close, size: 20),
                                color: scheme.onSurfaceVariant,
                                visualDensity: VisualDensity.compact,
                                tooltip: '맥락 닫기',
                              ),
                            ],
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                    ],
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _input,
                            minLines: 1,
                            maxLines: 4,
                            enabled: !_loading,
                            style: const TextStyle(color: Colors.white),
                            onSubmitted: (_) => _send(),
                            decoration: InputDecoration(
                              hintText:
                                  '예: 룰 기반으로 점수 합산 구조를 깔끔하게 잡고 싶어요',
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
                                  color: AppColors.indigo600
                                      .withValues(alpha: 0.8),
                                ),
                              ),
                              contentPadding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 12,
                              ),
                            ),
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
                          onPressed: _loading || _input.text.trim().isEmpty
                              ? null
                              : _send,
                          icon: const Icon(Icons.send_rounded),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      '목업 응답입니다. 키워드:「지원·강점」→ 찬스 / 「룰·합산·계산」→ 스니펫',
                      style: Theme.of(context).textTheme.labelSmall?.copyWith(
                            color: scheme.onSurfaceVariant,
                            height: 1.35,
                            fontSize: 11,
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

class _UserBubble extends StatelessWidget {
  const _UserBubble({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.sizeOf(context).width * 0.82,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: const BoxDecoration(
        color: AppColors.indigo600,
        borderRadius: BorderRadius.only(
          topLeft: Radius.circular(18),
          topRight: Radius.circular(6),
          bottomLeft: Radius.circular(18),
          bottomRight: Radius.circular(18),
        ),
      ),
      child: Text(
        text,
        style: const TextStyle(
          color: Colors.white,
          height: 1.4,
          fontSize: 14,
        ),
      ),
    );
  }
}

class _AssistantBubble extends StatelessWidget {
  const _AssistantBubble({
    required this.msg,
    required this.onSaveWallet,
  });

  final _CoachMessage msg;
  final VoidCallback onSaveWallet;

  @override
  Widget build(BuildContext context) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Container(
          constraints: BoxConstraints(
            maxWidth: MediaQuery.sizeOf(context).width * 0.88,
          ),
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 36),
          decoration: const BoxDecoration(
            color: AppColors.slate800,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(6),
              topRight: Radius.circular(18),
              bottomLeft: Radius.circular(18),
              bottomRight: Radius.circular(18),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (msg.badge != null) ...[
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppColors.indigo600.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(
                      color: AppColors.indigo600.withValues(alpha: 0.4),
                    ),
                  ),
                  child: Text(
                    msg.badge!,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                          fontSize: 10,
                          color: AppColors.indigo600,
                        ),
                  ),
                ),
                const SizedBox(height: 8),
              ],
              MarkdownBody(
                data: msg.text,
                selectable: true,
                styleSheet: MarkdownStyleSheet.fromTheme(Theme.of(context))
                    .copyWith(
                  p: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Colors.white.withValues(alpha: 0.92),
                        height: 1.45,
                      ),
                  strong: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
              if (msg.code != null) ...[
                const SizedBox(height: 10),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0F172A),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: AppColors.slate700),
                  ),
                  child: SelectableText(
                    msg.code!,
                    style: const TextStyle(
                      fontFamily: 'monospace',
                      fontSize: 11,
                      height: 1.4,
                      color: Color(0xFFA7F3D0),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
        Positioned(
          right: 6,
          bottom: 6,
          child: Material(
            color: AppColors.slate900.withValues(alpha: 0.92),
            borderRadius: BorderRadius.circular(8),
            child: InkWell(
              onTap: onSaveWallet,
              borderRadius: BorderRadius.circular(8),
              splashColor: AppColors.indigo600.withValues(alpha: 0.3),
              child: Padding(
                padding: const EdgeInsets.all(6),
                child: Icon(
                  Icons.account_balance_wallet_outlined,
                  size: 16,
                  color: Colors.white.withValues(alpha: 0.75),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// 웹 `InsightWalletPanel` 본문 (시트 내부)
class _InsightWalletPanelBody extends StatelessWidget {
  const _InsightWalletPanelBody({
    required this.wallet,
    required this.onCopy,
    required this.onRemove,
  });

  final List<CoachWalletItem> wallet;
  final void Function(String id) onCopy;
  final void Function(String id) onRemove;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final f = coachActiveFocus;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.slate800,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(
              color: AppColors.indigo600.withValues(alpha: 0.35),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'ACTIVE CONTEXT',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      fontWeight: FontWeight.w800,
                      letterSpacing: 0.5,
                      color: AppColors.indigo600,
                      fontSize: 11,
                    ),
              ),
              const SizedBox(height: 10),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: AppColors.indigo600.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Icon(
                      Icons.track_changes_rounded,
                      size: 18,
                      color: AppColors.indigo600,
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          f.title,
                          style: Theme.of(context).textTheme.labelSmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                                fontWeight: FontWeight.w600,
                              ),
                        ),
                        const SizedBox(height: 4),
                        Text(
                          f.subtitle,
                          style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                fontWeight: FontWeight.w800,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          f.body,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: scheme.onSurfaceVariant,
                                height: 1.45,
                              ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 6,
                          runSpacing: 6,
                          children: f.tags
                              .map(
                                (t) => Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  decoration: BoxDecoration(
                                    color: AppColors.slate900,
                                    borderRadius: BorderRadius.circular(999),
                                  ),
                                  child: Text(
                                    t,
                                    style: Theme.of(context)
                                        .textTheme
                                        .labelSmall
                                        ?.copyWith(
                                          fontWeight: FontWeight.w600,
                                        ),
                                  ),
                                ),
                              )
                              .toList(),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: AppColors.slate900,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppColors.slate700),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.wallet_outlined, size: 18, color: AppColors.indigo600),
                  const SizedBox(width: 8),
                  Text(
                    'Insight Wallet',
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                '대화 중 저장한 문장·코드를 모아 두었다가 로드맵 아카이브에 옮기기 좋습니다.',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                      height: 1.4,
                    ),
              ),
              const SizedBox(height: 12),
              if (wallet.isEmpty)
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  decoration: BoxDecoration(
                    color: AppColors.slate800.withValues(alpha: 0.8),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: AppColors.slate700,
                      style: BorderStyle.solid,
                    ),
                  ),
                  child: Text(
                    'AI 메시지 우측 하단의 지갑 아이콘으로 저장해 보세요.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: scheme.onSurfaceVariant,
                        ),
                  ),
                )
              else
                ...wallet.map(
                  (item) => Padding(
                    padding: const EdgeInsets.only(bottom: 10),
                    child: Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: AppColors.slate800,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: AppColors.slate700),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            item.title,
                            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                                  fontWeight: FontWeight.w700,
                                ),
                          ),
                          const SizedBox(height: 8),
                          Container(
                            constraints: const BoxConstraints(maxHeight: 140),
                            width: double.infinity,
                            padding: const EdgeInsets.all(8),
                            decoration: BoxDecoration(
                              color: AppColors.slate900,
                              borderRadius: BorderRadius.circular(8),
                              border: Border.all(color: AppColors.slate700),
                            ),
                            child: SingleChildScrollView(
                              child: SelectableText(
                                item.body,
                                style: const TextStyle(
                                  fontFamily: 'monospace',
                                  fontSize: 11,
                                  height: 1.4,
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 8),
                          Row(
                            mainAxisAlignment: MainAxisAlignment.end,
                            children: [
                              IconButton(
                                onPressed: () => onCopy(item.id),
                                icon: const Icon(Icons.copy_outlined, size: 18),
                                tooltip: '복사',
                              ),
                              IconButton(
                                onPressed: () => onRemove(item.id),
                                icon: const Icon(Icons.delete_outline, size: 18),
                                tooltip: '삭제',
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
