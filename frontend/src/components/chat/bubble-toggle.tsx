"use client";

type BubbleToggleProps = {
  onClick: () => void;
  isOpen: boolean;
};

export function BubbleToggle({ onClick, isOpen }: BubbleToggleProps) {
  if (isOpen) return null;

  return (
    <button
      type="button"
      onClick={onClick}
      className="fixed bottom-4 right-4 z-40 w-14 h-14 rounded-full bg-primary text-primary-foreground shadow-lg hover:shadow-xl hover:scale-105 transition-all flex items-center justify-center"
      title="Open chat"
    >
      <span
        className="material-symbols-outlined text-[24px]"
        style={{ fontVariationSettings: "'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24" }}
      >
        chat
      </span>
    </button>
  );
}
