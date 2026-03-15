import { useLayoutEffect, useRef, useState } from 'react';
import { cn } from '@/lib/utils';

export function ArtifactPromptBanner({ prompt }: { prompt?: string }) {
    const [expanded, setExpanded] = useState(false);
    const [isClamped, setIsClamped] = useState(false);
    const textRef = useRef<HTMLParagraphElement>(null);

    useLayoutEffect(() => {
        const el = textRef.current;
        if (el && !expanded) {
            setIsClamped(el.scrollHeight > el.clientHeight);
        }
    }, [prompt, expanded]);

    if (!prompt) return null;

    return (
        <div className="mx-4 mt-3 p-3 rounded-lg bg-muted/30 border border-border/30">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">Original Prompt</p>
            <p
                ref={textRef}
                className={cn("text-sm text-foreground/80", !expanded && "line-clamp-3")}
            >
                {prompt}
            </p>
            {!expanded && isClamped && (
                <button
                    onClick={() => setExpanded(true)}
                    className="text-[10px] text-primary hover:underline mt-1"
                >
                    Show more
                </button>
            )}
        </div>
    );
}
