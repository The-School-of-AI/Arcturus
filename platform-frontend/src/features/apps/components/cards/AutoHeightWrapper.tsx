import React, { useRef, useEffect, useCallback, useState } from 'react';
import { useAppStore } from '@/store';

interface AutoHeightWrapperProps {
    cardId: string;
    children: React.ReactNode;
    enabled?: boolean;
    rowHeight?: number;
}

/**
 * Wrapper component that automatically adjusts the parent grid item's height
 * to fit its content - both expanding AND collapsing as needed.
 */
export const AutoHeightWrapper: React.FC<AutoHeightWrapperProps> = ({
    cardId,
    children,
    enabled = true,
    rowHeight = 40
}) => {
    const wrapperRef = useRef<HTMLDivElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const [hasUpdated, setHasUpdated] = useState(false);
    const { appLayout, setAppLayout } = useAppStore();

    const updateHeight = useCallback(() => {
        if (!enabled || !wrapperRef.current || !contentRef.current) return;

        const contentEl = contentRef.current;
        const contentScrollHeight = contentEl.scrollHeight;

        // Also measure all direct children to handle cases where scrollHeight might be misleading
        // if consistent CSS overflow handling isn't perfect
        let totalChildHeight = 0;
        Array.from(contentEl.children).forEach((child) => {
            const childRect = child.getBoundingClientRect();
            totalChildHeight += childRect.height;
        });

        // Find current layout item
        const currentItem = appLayout.find((item: any) => item.i === cardId);
        if (!currentItem) return;

        // The actual content height we want is the scrollHeight of the content div
        const actualContentHeight = Math.max(contentScrollHeight, totalChildHeight);

        // Calculate required grid units (h)
        // using formula: pixels = h * (rowHeight + margin) - margin
        // h = (pixels + margin) / (rowHeight + margin)

        // Match constants from AppGrid.tsx
        const RGL_MARGIN = 16;

        // We add a tiny buffer (4px) to avoid precision issues where it effectively fits 
        // but floats point math pushes it slightly over
        const buffer = 4;

        const requiredH = Math.max(2, Math.ceil((actualContentHeight + RGL_MARGIN + buffer) / (rowHeight + RGL_MARGIN)));

        // Update if height differs
        if (requiredH !== currentItem.h && !hasUpdated) {
            setHasUpdated(true);

            const newLayout = appLayout.map((item: any) =>
                item.i === cardId ? { ...item, h: requiredH } : item
            );
            setAppLayout(newLayout);
        }
    }, [enabled, cardId, appLayout, setAppLayout, rowHeight, hasUpdated]);

    // Reset when enabled changes
    useEffect(() => {
        if (enabled) {
            setHasUpdated(false);
        }
    }, [enabled, cardId]);

    // Measure after mount
    useEffect(() => {
        if (!enabled || hasUpdated) return;

        const timers = [
            setTimeout(() => updateHeight(), 100),
            setTimeout(() => updateHeight(), 300),
            setTimeout(() => updateHeight(), 500),
        ];

        return () => timers.forEach(t => clearTimeout(t));
    }, [enabled, hasUpdated, updateHeight, cardId]);

    return (
        <div
            ref={wrapperRef}
            className="w-full h-full overflow-hidden"
        >
            <div
                ref={contentRef}
                className="w-full"
                style={{ height: 'auto', minHeight: 0 }}
            >
                {children}
            </div>
        </div>
    );
};
