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
    const measuringRef = useRef<HTMLDivElement>(null);
    const [lastUpdatedH, setLastUpdatedH] = useState<number>(0);
    const { appLayout, setAppLayout } = useAppStore();

    const updateHeight = useCallback(() => {
        if (!enabled || !measuringRef.current) return;

        // Use the measuring div which has auto height to get true content height
        const contentHeight = measuringRef.current.scrollHeight;

        // Calculate required grid units (h)
        // Formula: (contentHeight + header ~44px + padding ~16px) / rowHeight, rounded up
        const headerAndPadding = 60; // Approximate header + padding
        const minH = 2; // Minimum height of 2 units
        const requiredH = Math.max(minH, Math.ceil((contentHeight + headerAndPadding) / rowHeight));

        // Find current layout item
        const currentItem = appLayout.find((item: any) => item.i === cardId);
        if (!currentItem) return;

        // Update if height differs (both expand AND collapse)
        if (requiredH !== currentItem.h && requiredH !== lastUpdatedH) {
            console.log(`AutoHeight: ${cardId} adjusting h from ${currentItem.h} to ${requiredH}`);
            setLastUpdatedH(requiredH);

            // Update layout with new height
            const newLayout = appLayout.map((item: any) =>
                item.i === cardId ? { ...item, h: requiredH } : item
            );
            setAppLayout(newLayout);
        }
    }, [enabled, cardId, appLayout, setAppLayout, rowHeight, lastUpdatedH]);

    useEffect(() => {
        if (!enabled) return;

        // Small delay to ensure content is rendered
        const timer = setTimeout(() => {
            updateHeight();
        }, 150);

        return () => clearTimeout(timer);
    }, [enabled, updateHeight]);

    // Also observe for content changes using ResizeObserver
    useEffect(() => {
        if (!enabled || !measuringRef.current) return;

        const resizeObserver = new ResizeObserver(() => {
            // Debounce
            requestAnimationFrame(updateHeight);
        });

        resizeObserver.observe(measuringRef.current);

        return () => resizeObserver.disconnect();
    }, [enabled, updateHeight]);

    return (
        <div className="w-full h-full overflow-hidden relative flex-1">
            {/* Hidden measuring div to get true content height */}
            <div
                ref={measuringRef}
                className="absolute top-0 left-0 w-full pointer-events-none"
                style={{ height: 'auto', visibility: 'hidden', zIndex: -1 }}
            >
                {children}
            </div>
            {/* Visible content */}
            <div className="w-full h-full overflow-auto">
                {children}
            </div>
        </div>
    );
};
