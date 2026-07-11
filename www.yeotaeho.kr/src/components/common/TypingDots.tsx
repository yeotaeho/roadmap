// 채팅 응답 대기 표시 — 점 3개 바운스 애니메이션(현재 텍스트 색 상속)
export function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1.5" aria-label="응답 작성 중">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-1.5 w-1.5 animate-bounce rounded-full bg-current opacity-50"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}
