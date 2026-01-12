import { cn } from "@/lib/utils";
import React from "react";

const MeteorsInner = ({
    number = 40,
    className,
}: {
    number?: number;
    className?: string;
}) => {
    const meteorStyles = React.useMemo(() => {
        return new Array(number).fill(0).map(() => {
            const isWarm = Math.random() > 0.3; // Matches your warm/blue mix
            const color = isWarm ? "#fbbf24" : "#22d3ee";
            const glow = isWarm ? "#f59e0b" : "#0891b2";

            // WIDE SPAWNING LOGIC:
            // Randomly decide if it starts from the Top edge or the Right edge
            const spawnFromTop = Math.random() > 0.5;

            const top = spawnFromTop
                ? `${-10 - Math.random() * 20}%` // Spawn above the screen
                : `${Math.random() * 80}%`;      // Spawn along the right side

            const left = spawnFromTop
                ? `${Math.random() * 120}%`      // Any X position if from top
                : `${100 + Math.random() * 20}%`; // Off-screen to the right

            return {
                top,
                left,
                "--duration": `${3 + Math.random() * 5}s`,
                "--delay": `${Math.random() * 10}s`,
                "--color": color,
                "--glow": glow,
                "--size": `${1 + Math.random() * 1.5}px`,
            } as React.CSSProperties;
        });
    }, [number]);

    return (
        <>
            <style>{`
        @keyframes meteor-to-left {
          0% {
            /* 135deg points the element's 'forward' axis toward Bottom-Left */
            transform: rotate(135deg) translateX(0);
            opacity: 0;
          }
          10% {
            opacity: 1;
          }
          100% {
            /* TranslateX moves it along that 135deg path */
            transform: rotate(135deg) translateX(150vmax);
            opacity: 0;
          }
        }

        .animate-meteor-precision {
          animation: meteor-to-left var(--duration) linear infinite;
          animation-delay: var(--delay);
          will-change: transform;
        }
      `}</style>

            {meteorStyles.map((style, idx) => (
                <span
                    key={idx}
                    className={cn(
                        "animate-meteor-precision absolute rounded-full pointer-events-none",
                        className
                    )}
                    style={{
                        ...style,
                        backgroundColor: "var(--color)",
                        boxShadow: `0 0 8px 1px var(--glow)`,
                        width: "var(--size)",
                        height: "var(--size)",
                    }}
                >
                    {/* Tail: anchored to the left of the meteor head since it moves 'forward' at 135deg */}
                    <div
                        className="absolute top-1/2 -translate-y-1/2 right-full h-[1px] w-[220px] opacity-70"
                        style={{
                            background: `linear-gradient(to left, var(--color), transparent)`
                        }}
                    />

                    {/* Subtle Leading Glow */}
                    <div
                        className="absolute inset-[-4px] rounded-full blur-[2px] opacity-20"
                        style={{ backgroundColor: "var(--glow)" }}
                    />
                </span>
            ))}
        </>
    );
};

export const Meteors = React.memo(MeteorsInner);