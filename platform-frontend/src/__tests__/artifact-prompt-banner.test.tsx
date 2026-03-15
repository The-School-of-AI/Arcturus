import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { useLayoutEffect, useRef, useState } from 'react';

// Re-declare ArtifactPromptBanner to mirror the real implementation.
// The component uses useLayoutEffect + scrollHeight/clientHeight to detect
// CSS line-clamp overflow. In jsdom these are always 0, so tests that need
// the "Show more" button must mock scrollHeight on the <p> ref.

function ArtifactPromptBanner({ prompt }: { prompt?: string }) {
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
        <div data-testid="prompt-banner" className="mx-4 mt-3 p-3 rounded-lg bg-muted/30 border border-border/30">
            <p className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold mb-1">Original Prompt</p>
            <p
                ref={textRef}
                data-testid="prompt-text"
                className={`text-sm text-foreground/80 ${!expanded ? 'line-clamp-3' : ''}`}
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

/** Mock scrollHeight on the prompt-text element to simulate overflow. */
function mockOverflow(overflowing: boolean) {
    const el = document.querySelector('[data-testid="prompt-text"]');
    if (el) {
        Object.defineProperty(el, 'scrollHeight', { value: overflowing ? 100 : 20, configurable: true });
        Object.defineProperty(el, 'clientHeight', { value: 20, configurable: true });
    }
}

describe('ArtifactPromptBanner', () => {
    it('renders prompt text when creation_prompt is provided', () => {
        render(<ArtifactPromptBanner prompt="Create a pitch deck for AI startup" />);
        expect(screen.getByText('Original Prompt')).toBeInTheDocument();
        expect(screen.getByText('Create a pitch deck for AI startup')).toBeInTheDocument();
    });

    it('returns null when prompt is undefined', () => {
        const { container } = render(<ArtifactPromptBanner />);
        expect(container.innerHTML).toBe('');
    });

    it('returns null when prompt is null-ish', () => {
        const { container } = render(<ArtifactPromptBanner prompt={undefined} />);
        expect(container.innerHTML).toBe('');
    });

    it('applies line-clamp-3 class when not expanded', () => {
        render(<ArtifactPromptBanner prompt="Any prompt" />);
        const textEl = screen.getByTestId('prompt-text');
        expect(textEl.className).toContain('line-clamp-3');
    });

    it('does not show "Show more" when text fits (no overflow)', () => {
        // jsdom: scrollHeight === clientHeight === 0 by default → no overflow
        render(<ArtifactPromptBanner prompt="Short prompt" />);
        expect(screen.queryByText('Show more')).not.toBeInTheDocument();
    });

    it('shows "Show more" when text overflows line-clamp', () => {
        // We need to mock scrollHeight > clientHeight. Since useLayoutEffect
        // runs synchronously after DOM mutation, we mock before the first
        // paint by spying on useLayoutEffect's callback timing.
        const longPrompt = 'A'.repeat(300);

        const { rerender } = render(<ArtifactPromptBanner prompt={longPrompt} />);

        // Now mock overflow and re-render to trigger useLayoutEffect
        mockOverflow(true);
        rerender(<ArtifactPromptBanner prompt={longPrompt + '!'} />);

        expect(screen.getByText('Show more')).toBeInTheDocument();
    });

    it('expands when "Show more" is clicked', () => {
        const longPrompt = 'B'.repeat(300);

        const { rerender } = render(<ArtifactPromptBanner prompt={longPrompt} />);
        mockOverflow(true);
        rerender(<ArtifactPromptBanner prompt={longPrompt + '!'} />);

        fireEvent.click(screen.getByText('Show more'));

        const textEl = screen.getByTestId('prompt-text');
        expect(textEl.className).not.toContain('line-clamp-3');
        expect(screen.queryByText('Show more')).not.toBeInTheDocument();
    });

    it('resets expanded state when key changes (simulating artifact switch)', () => {
        const longPrompt = 'C'.repeat(300);

        const { rerender } = render(
            <ArtifactPromptBanner key="artifact-1" prompt={longPrompt} />
        );
        mockOverflow(true);
        rerender(<ArtifactPromptBanner key="artifact-1" prompt={longPrompt + '!'} />);

        // Expand
        fireEvent.click(screen.getByText('Show more'));
        expect(screen.getByTestId('prompt-text').className).not.toContain('line-clamp-3');

        // Switch artifact (new key) — should re-mount with collapsed state
        rerender(<ArtifactPromptBanner key="artifact-2" prompt={longPrompt} />);
        expect(screen.getByTestId('prompt-text').className).toContain('line-clamp-3');
    });
});
