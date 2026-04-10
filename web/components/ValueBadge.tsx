"use client";

import { Badge } from "@/components/ui/badge";

interface ValueBadgeProps {
  value: number;
  label: string;
}

export function ValueBadge({ value, label }: ValueBadgeProps) {
  const isPositive = value > 0;
  const isNegative = value < -5;

  if (!isPositive) return null;

  return (
    <div className="flex items-center gap-1.5 mt-3">
      <Badge
        variant="outline"
        className={`${
          isPositive
            ? "bg-green-50 text-green-700 border-green-200"
            : "bg-red-50 text-red-700 border-red-200"
        }`}
      >
        <span className="mr-1">🔥</span>
        Value
      </Badge>
      <span className="text-sm text-muted-foreground">
        <span className="text-green-600 font-medium">
          {label}: +{Math.abs(value).toFixed(0)}%
        </span>
      </span>
    </div>
  );
}
