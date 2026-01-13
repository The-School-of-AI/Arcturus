import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type IdeSidebarTab = 'plan' | 'explorer' | 'search' | 'git';

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
}

export const useIdeStore = create<IdeState>()(
    persist(
        (set) => ({
            isLeftPanelVisible: true,
            isRightPanelVisible: true,
            isBottomPanelVisible: true,

            activeSidebarTab: 'explorer',

            setActiveSidebarTab: (tab) => set({ activeSidebarTab: tab }),
            toggleLeftPanel: () => set((state) => ({ isLeftPanelVisible: !state.isLeftPanelVisible })),
            toggleRightPanel: () => set((state) => ({ isRightPanelVisible: !state.isRightPanelVisible })),
            toggleBottomPanel: () => set((state) => ({ isBottomPanelVisible: !state.isBottomPanelVisible })),
        }),
        {
            name: 'ide-storage',
        }
    )
);
