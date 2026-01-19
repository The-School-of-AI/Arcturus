import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type IdeSidebarTab = 'plan' | 'explorer' | 'tests' | 'search' | 'git';

// Timer backoff tiers in seconds
const TIMER_TIERS = [15, 30, 60, 120, 240];

interface ArcturusTimerState {
    countdown: number | null;      // Current countdown in seconds
    tier: number;                  // Current tier index (0-4)
    isPaused: boolean;             // Is timer paused by user
    lastSaveTime: number | null;   // Timestamp of last save
}

interface IdeState {
    // --- Layout State ---
    isLeftPanelVisible: boolean;
    isRightPanelVisible: boolean;
    isBottomPanelVisible: boolean;

    // --- Sidebar State ---
    activeSidebarTab: IdeSidebarTab;
    setActiveSidebarTab: (tab: IdeSidebarTab) => void;
    toggleLeftPanel: () => void;
    toggleRightPanel: () => void;
    toggleBottomPanel: () => void;

    // --- Arcturus Timer State ---
    arcturusTimer: ArcturusTimerState;
    startArcturusTimer: () => void;
    resetArcturusTimer: () => void;       // Reset countdown
    advanceArcturusTier: () => void;      // Bump to next tier
    pauseArcturusTimer: () => void;
    resumeArcturusTimer: () => void;
    tickArcturusTimer: () => void;        // Called every second
    clearArcturusTimer: () => void;       // Clear after commit

    // --- Git View State ---
    activeGitView: 'arcturus' | 'user';
    setActiveGitView: (view: 'arcturus' | 'user') => void;

    // --- Tests State ---
    selectedTestFile: string | null;
    activeTests: Record<string, string[]>;  // file path -> activated test IDs
    testFiles: string[];
    setTestFiles: (files: string[]) => void;
    setSelectedTestFile: (file: string | null) => void;
    toggleTest: (file: string, testId: string) => void;
    toggleAllTests: (file: string, enabled: boolean, testIds: string[]) => void;
}

export const useIdeStore = create<IdeState>()(
    persist(
        (set, get) => ({
            // Layout
            isLeftPanelVisible: true,
            isRightPanelVisible: true,
            isBottomPanelVisible: true,

            // Sidebar
            activeSidebarTab: 'explorer',
            setActiveSidebarTab: (tab) => set({ activeSidebarTab: tab }),
            toggleLeftPanel: () => set((state) => ({ isLeftPanelVisible: !state.isLeftPanelVisible })),
            toggleRightPanel: () => set((state) => ({ isRightPanelVisible: !state.isRightPanelVisible })),
            toggleBottomPanel: () => set((state) => ({ isBottomPanelVisible: !state.isBottomPanelVisible })),

            // Arcturus Timer
            arcturusTimer: {
                countdown: null,
                tier: 0,
                isPaused: false,
                lastSaveTime: null,
            },

            testFiles: [], // List of files that have tests
            setTestFiles: (files: string[]) => set({ testFiles: files }),

            startArcturusTimer: () => set((state) => ({
                arcturusTimer: {
                    ...state.arcturusTimer,
                    countdown: TIMER_TIERS[state.arcturusTimer.tier], // Use current tier
                    isPaused: false,
                    lastSaveTime: Date.now(),
                }
            })),

            // Called on activity - reset countdown but keep tier
            resetArcturusTimer: () => set((state) => ({
                arcturusTimer: {
                    ...state.arcturusTimer,
                    countdown: TIMER_TIERS[state.arcturusTimer.tier],
                    lastSaveTime: Date.now(),
                }
            })),

            // Called after commit - bump tier
            advanceArcturusTier: () => set((state) => {
                const nextTier = Math.min(state.arcturusTimer.tier + 1, TIMER_TIERS.length - 1);
                return {
                    arcturusTimer: {
                        ...state.arcturusTimer,
                        tier: nextTier,
                        // Don't auto-start next timer, wait for edit
                        countdown: null
                    }
                };
            }),

            pauseArcturusTimer: () => set((state) => ({
                arcturusTimer: {
                    ...state.arcturusTimer,
                    isPaused: true,
                }
            })),

            resumeArcturusTimer: () => set((state) => ({
                arcturusTimer: {
                    ...state.arcturusTimer,
                    countdown: TIMER_TIERS[0],  // Reset to 15s on resume
                    tier: 0,
                    isPaused: false,
                }
            })),

            tickArcturusTimer: () => set((state) => {
                if (state.arcturusTimer.isPaused || state.arcturusTimer.countdown === null) {
                    return state;
                }
                const newCountdown = state.arcturusTimer.countdown - 1;
                // Stick at 0 so the controller can react to it.
                // The controller calls advanceArcturusTier which sets it to null.
                return {
                    arcturusTimer: {
                        ...state.arcturusTimer,
                        countdown: newCountdown < 0 ? 0 : newCountdown,
                    }
                };
            }),

            clearArcturusTimer: () => set(() => ({
                arcturusTimer: {
                    countdown: null,
                    tier: 0,
                    isPaused: false,
                    lastSaveTime: null,
                }
            })),

            // Git View
            activeGitView: 'arcturus',
            setActiveGitView: (view) => set({ activeGitView: view }),

            // Tests
            selectedTestFile: null,
            activeTests: {},
            setSelectedTestFile: (file) => set({ selectedTestFile: file }),

            toggleTest: (file, testId) => set((state) => {
                const currentTests = state.activeTests[file] || [];
                const isActive = currentTests.includes(testId);
                return {
                    activeTests: {
                        ...state.activeTests,
                        [file]: isActive
                            ? currentTests.filter(id => id !== testId)
                            : [...currentTests, testId]
                    }
                };
            }),

            toggleAllTests: (file, enabled, testIds) => set((state) => ({
                activeTests: {
                    ...state.activeTests,
                    [file]: enabled ? testIds : []
                }
            })),
        }),
        {
            name: 'ide-storage',
            partialize: (state) => ({
                // Only persist layout and sidebar state, not timer
                isLeftPanelVisible: state.isLeftPanelVisible,
                isRightPanelVisible: state.isRightPanelVisible,
                isBottomPanelVisible: state.isBottomPanelVisible,
                activeSidebarTab: state.activeSidebarTab,
                activeGitView: state.activeGitView,
                activeTests: state.activeTests,
            }),
        }
    )
);
