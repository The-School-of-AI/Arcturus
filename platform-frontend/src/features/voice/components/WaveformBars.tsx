import React, { useEffect, useState } from 'react';
import { cn } from '@/lib/utils';

const BAR_COUNT = 11;
const DURATION_MS = 120;

export const WaveformBars: React.FC<{ active: boolean; className?: string }> = ({ active, className }) => {
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setTick((t) => t + 1), DURATION_MS);
    return () => clearInterval(id);
  }, [active]);

  return (
    <div
      className={cn('flex items-end justify-center gap-0.5 h-8', className)}
      role="img"
      aria-label={active ? 'Audio activity' : undefined}
    >
      {Array.from({ length: BAR_COUNT }).map((_, i) => {
        const seed = (tick + i * 3) % 100;
        const height = active ? 20 + (seed % 60) : 4;
        return (
          <div
            key={i}
            className="w-1 rounded-full bg-cyan-400/80 transition-all duration-75"
            style={{ height: `${height}%`, minHeight: 4 }}
          />
        );
      })}
    </div>
  );
};
