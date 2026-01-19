// @ts-nocheck
import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock window.electronAPI for tests
const mockElectronAPI = {
    invoke: vi.fn(),
    send: vi.fn(),
    receive: vi.fn(),
    removeListener: vi.fn(),
    confirm: vi.fn(),
};

if (typeof window !== 'undefined') {
    Object.defineProperty(window, 'electronAPI', {
        value: mockElectronAPI,
        writable: true,
    });
}

// Export for use in tests
export { mockElectronAPI };
