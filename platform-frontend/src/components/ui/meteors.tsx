import { cn } from "@/lib/utils";
import React from "react";
import { useTheme } from "@/components/theme/ThemeProvider";

const MeteorsInner = ({
    number = 10,
    className,
}: {
    number?: number;
    className?: string;
}) => {
    const { theme } = useTheme();
    const isDarkMode = theme === 'dark';

    const meteorStyles = React.useMemo(() => {
        const neons = [
            { c: "#00f3ff", g: "#0891b2" },
            { c: "#ff00c1", g: "#db2777" },
            { c: "#bcff00", g: "#65a30d" },
            { c: "#7000ff", g: "#7c3aed" }
        ];

        // Muted Nordic palette for light mode
        const nordics = [
            { c: "#5e81ac", g: "#88c0d0" }, // Blue
            { c: "#bf616a", g: "#d08770" }, // Red/Orange
            { c: "#8fbcbb", g: "#a3be8c" }, // Teal/Green
            { c: "#b48ead", g: "#5e81ac" }  // Purple
        ];

        return new Array(number).fill(0).map(() => {
            const palette = isDarkMode ? neons : nordics;
            const selection = palette[Math.floor(Math.random() * palette.length)];

            const color = selection.c;
            const glow = selection.g;
            const scale = 0.5 + Math.random() * 1.5;

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
                "--duration": `${1.5 + Math.random() * 5}s`,
                "--delay": `${0.6 + Math.random() * 5}s`, // Keep the startup delay fix
                "--color": color,
                "--glow": glow,
                "--size": `${1 + Math.random() * 1.5}px`,
                "--scale": scale,
                "--is-dark": isDarkMode,
            } as React.CSSProperties;
        });
    }, [number, isDarkMode]);

    return (
        <>
            <style>{`
        @keyframes meteor-to-left {
          0% {
            transform: rotate(135deg) translateX(0);
            opacity: 0;
          }
          10% {
            opacity: 1;
          }
          100% {
            transform: rotate(135deg) translateX(150vmax);
            opacity: 0;
          }
        }

        @keyframes tail-pulse {
            0%, 100% { opacity: 0.3; width: 150px; }
            50% { opacity: 0.8; width: 280px; }
        }

        @keyframes spark {
            0% { transform: scale(1) translateX(0); opacity: 1; }
            100% { transform: scale(0) translateX(-40px); opacity: 0; }
        }

        .meteor-spark {
            position: absolute;
            width: 2px;
            height: 2px;
            border-radius: 50%;
            background-color: var(--color);
            animation: spark 0.6s ease-out infinite;
        }

        .animate-meteor-precision {
            animation: meteor-to-left var(--duration) linear infinite;
            animation-delay: var(--delay);
            animation-fill-mode: both;
            will-change: transform;
        }
      `}</style>

            {meteorStyles.map((style, idx) => {
                const isDark = style["--is-dark"] as boolean;
                return (
                    <span
                        key={idx}
                        className={cn(
                            "animate-meteor-precision absolute rounded-full pointer-events-none",
                            className
                        )}
                        style={{
                            ...style,
                            backgroundColor: "var(--color)",
                            boxShadow: isDark
                                ? `0 0 10px 2px var(--color), 0 0 20px 4px var(--glow)`
                                : `0 0 8px 1px var(--glow)`,
                            mixBlendMode: isDark ? "screen" : "multiply",
                            width: "var(--size)",
                            height: "var(--size)",
                            transform: `scale(var(--scale))`,
                        }}
                    >
                        <div
                            className="absolute top-1/2 -translate-y-1/2 right-full h-[1.5px] opacity-80"
                            style={{
                                width: "250px",
                                background: `linear-gradient(to left, var(--color), var(--glow), transparent)`,
                                filter: isDark ? "blur(0.5px)" : "blur(1px)",
                                opacity: isDark ? 0.8 : 0.4,
                                animation: "tail-pulse 2s ease-in-out infinite"
                            }}
                        />

                        <div
                            className="absolute -left-2 top-0 meteor-spark"
                            style={{ animationDelay: "0.2s" }}
                        />
                        <div
                            className="absolute -left-6 top-1 meteor-spark"
                            style={{ animationDelay: "0.5s" }}
                        />
                    </span>
                )
            })}
        </>
    );
};

export const Meteors = React.memo(MeteorsInner);