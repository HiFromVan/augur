"use client";

interface ProbBarProps {
  label: string;
  value: number;
  color?: "red" | "gray" | "blue";
  showValue?: boolean;
}

export function ProbBar({
  label,
  value,
  color = "blue",
  showValue = true,
}: ProbBarProps) {
  const colors = {
    red: "bg-gradient-to-r from-red-500 to-red-400",
    gray: "bg-gradient-to-r from-gray-500 to-gray-400",
    blue: "bg-gradient-to-r from-blue-600 to-blue-400",
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        {showValue && (
          <span className="font-mono font-medium">{value.toFixed(1)}%</span>
        )}
      </div>
      <div className="h-2 rounded-full bg-secondary overflow-hidden">
        <div
          className={`h-full rounded-full ${colors[color]} transition-all duration-500`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}
