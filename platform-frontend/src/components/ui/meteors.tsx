import { cn } from "@/lib/utils";
import React from "react";

const MeteorsInner = ({
    number = 10,
    className,
}: {
    number?: number;
    className?: string;
}) => {
    // You asked: "50% in numbers"
    // So we intentionally render half of whatever `number` is.
    const count = React.useMemo(() => Math.max(1, Math.round(number * 0.2)), [number]);

    const meteorStyles = React.useMemo(() => {
        return new Array(count).fill(true).map(() => {
            // Depth tiers (size/opacity/speed)
            const depth = Math.random();
            let size = depth > 0.8 ? 2 : depth > 0.4 ? 10 : 1;
            size = size * Math.random();

            // Make them stay longer (slower = longer duration)
            // (near = faster, far = slower)
            const duration = depth > 0.8 ? 5 : depth > 0.4 ? 8 : 12;

            const opacity = depth > 0.8 ? 1 : depth > 0.6 ? 0.95 : 0.55;

            // IMPORTANT: Spread them across the whole screen
            // Spawn either from TOP edge (any X) or RIGHT edge (any Y)
            // This prevents clustering in the top-right quadrant.
            const fromTop = Math.random() < 0.55; // slight bias to top so it feels "raining"

            const top = fromTop
                ? `${-(10 + Math.random() * 20)}%` // -10% .. -30% (offscreen)
                : `${Math.floor(Math.random() * 100)}%`; // 0% .. 99%

            const left = fromTop
                ? `${Math.floor(Math.random() * 100)}%` // 0% .. 99%
                : `${100 + Math.random() * 20}%`; // 100% .. 120% (offscreen to the right)

            return {
                top,
                left,
                // Spread start times so they don't "launch in a pack"
                animationDelay: `${Math.random() * 10}s`,
                animationDuration: `${duration}s`,
                width: `${size}px`,
                height: `${size}px`,
                opacity,
            } as React.CSSProperties;
        });
    }, [count]);

    return (
        <>
            <style>{`
        @keyframes amazing-meteor-left {
          0% {
            transform: rotate(135deg) translateX(0);
            opacity: 0;
          }
          8% {
            opacity: 1;
          }
          100% {
            /* Big travel distance so meteors reach (and pass) the far edge on any screen */
            transform: rotate(135deg) translateX(250vmax);
            opacity: 0;
          }
        }

        .animate-meteor-amazing-left {
          animation: amazing-meteor-left linear infinite;
          will-change: transform, opacity;
        }
      `}</style>

            {meteorStyles.map((style, idx) => (
                <span
                    key={"meteor" + idx}
                    className={cn(
                        "animate-meteor-amazing-left absolute rounded-full bg-white pointer-events-none",
                        // Glow around the head
                        "after:content-[''] after:absolute after:inset-[-4px] after:rounded-full after:bg-sky-500 after:blur-[4px] after:opacity-50",
                        // Tail (longer + a bit softer)
                        "before:content-[''] before:absolute before:top-1/2 before:transform before:-translate-y-[50%] before:w-[280px] before:h-[1px] before:bg-gradient-to-l before:from-transparent before:via-sky-400/35 before:to-white before:-left-[280px]",
                        className
                    )}
                    style={style}
                />
            ))}
        </>
    );
};

export const Meteors = React.memo(MeteorsInner);
