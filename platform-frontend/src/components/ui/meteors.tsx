import { cn } from "@/lib/utils";
import React from "react";

const MeteorsInner = ({ number, className }: { number?: number; className?: string }) => {
    const meteorStyles = React.useMemo(() => {
        return new Array(number || 20).fill(true).map(() => ({
            top: Math.random() > 0.5 ? 0 : Math.floor(Math.random() * 80) + "%",
            left: Math.random() > 0.5 ? Math.floor(Math.random() * 100) + "%" : "100%",
            animationDelay: Math.random() * (0.8 - 0.2) + 0.2 + "s",
            animationDuration: Math.floor(Math.random() * (15 - 5) + 5) + "s",
        }));
    }, [number]);

    return (
        <>
            {meteorStyles.map((style, idx) => (
                <span
                    key={"meteor" + idx}
                    className={cn(
                        "animate-meteor-effect absolute h-1 w-1 rounded-[9999px] bg-white shadow-[0_0_0_1px_#ffffff10] rotate-[135deg]",
                        "before:content-[''] before:absolute before:top-1/2 before:transform before:-translate-y-[50%] before:w-[120px] before:h-[1px] before:bg-gradient-to-l before:from-slate-300 before:to-transparent before:-left-[120px]",
                        className
                    )}


                    style={style}
                ></span>
            ))}
        </>
    );
};

export const Meteors = React.memo(MeteorsInner);

