"use client";

interface Props {
  level: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT";
  score: number;
}

const STYLES: Record<Props["level"], string> = {
  HIGH: "bg-emerald-100 text-emerald-800",
  MEDIUM: "bg-amber-100 text-amber-800",
  LOW: "bg-orange-100 text-orange-800",
  INSUFFICIENT: "bg-red-100 text-red-800",
};

export default function ConfidenceBadge({ level, score }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${STYLES[level]}`}
      title={`confidence score ${score.toFixed(3)}`}
    >
      {level}
      <span className="font-normal opacity-70">{score.toFixed(2)}</span>
    </span>
  );
}
