import { useEffect, useRef } from 'react';
import { useAppStore } from '@/store';
import type { UIMode } from '@/store';

/**
 * useUIMode — Auto-detects and switches UI modes based on system state.
 *
 * Mode behaviors:
 * - explore: Default calm view for browsing
 * - execute: Auto-activated when a run starts, shows live graph
 * - focus:   User-triggered to zoom into a single agent chain
 * - debug:   Shows deep logs, timings, model info per node
 *
 * Auto-detection rules:
 * - When a run starts → switch to execute mode
 * - When a run completes → return to explore mode (if was auto-switched)
 * - User manual overrides are respected (no auto-switching when user chose a mode)
 */
export function useUIMode() {
    const currentRun = useAppStore(state => state.currentRun);
    const uiMode = useAppStore(state => state.uiMode);
    const setUIMode = useAppStore(state => state.setUIMode);
    const nodes = useAppStore(state => state.nodes);

    // Track whether the current execute mode was auto-triggered
    const autoSwitchedRef = useRef(false);
    const prevRunStatusRef = useRef<string | null>(null);

    useEffect(() => {
        const runStatus = currentRun?.status ?? null;

        // Run just started
        if (runStatus === 'running' && prevRunStatusRef.current !== 'running') {
            if (uiMode === 'explore') {
                setUIMode('execute');
                autoSwitchedRef.current = true;
            }
        }

        // Run just completed/failed
        if (
            (runStatus === 'completed' || runStatus === 'failed' || runStatus === 'stopped') &&
            prevRunStatusRef.current === 'running'
        ) {
            if (autoSwitchedRef.current && uiMode === 'execute') {
                setUIMode('explore');
                autoSwitchedRef.current = false;
            }
        }

        prevRunStatusRef.current = runStatus;
    }, [currentRun?.status, uiMode, setUIMode]);

    // Reset auto-switch flag when user manually changes mode
    useEffect(() => {
        // If user manually changed to something other than what auto-switch set,
        // clear the auto flag so we don't interfere
        if (uiMode !== 'execute') {
            autoSwitchedRef.current = false;
        }
    }, [uiMode]);

    // Keyboard shortcuts for mode switching
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            // Alt+E/X/F/D for mode switching
            if (!e.altKey) return;
            const modeMap: Record<string, UIMode> = {
                'e': 'explore',
                'x': 'execute',
                'f': 'focus',
                'd': 'debug',
            };
            const mode = modeMap[e.key.toLowerCase()];
            if (mode) {
                e.preventDefault();
                setUIMode(mode);
                autoSwitchedRef.current = false;
            }
        };
        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [setUIMode]);

    return { uiMode, setUIMode };
}
