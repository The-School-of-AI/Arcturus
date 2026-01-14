import React, { useEffect, useState, useRef } from 'react';
import { PlusCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SelectionMenuProps {
    onAdd: (text: string) => void;
}

export const SelectionMenu: React.FC<SelectionMenuProps> = ({ onAdd }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [currentText, setCurrentText] = useState("");
    const [isAdded, setIsAdded] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const handleSelectionChange = () => {
            const selection = window.getSelection();
            const text = selection?.toString().trim();

            if (text && text.length > 0) {
                try {
                    const range = selection!.getRangeAt(0);
                    const rect = range.getBoundingClientRect();
                    // Basic bounds check to ensure we are visible
                    if (rect.width > 0 && rect.height > 0) {
                        setPosition({
                            x: rect.left + rect.width / 2,
                            y: rect.top - 40,
                        });
                        setCurrentText(text);
                        // Prevent jumping if already added
                        if (!isAdded) {
                            setIsVisible(true);
                        }
                    } else {
                        setIsVisible(false);
                    }
                } catch (e) {
                    setIsVisible(false);
                }
            } else if (!isAdded) {
                setIsVisible(false);
            }
        };

        // Debounce slightly to handle fast selection changes
        let timeoutId: any;
        const debouncedHandler = () => {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(handleSelectionChange, 100);
        };

        document.addEventListener('selectionchange', debouncedHandler);
        // Also listen for mouseup as backup for some contexts
        document.addEventListener('mouseup', debouncedHandler);

        return () => {
            document.removeEventListener('selectionchange', debouncedHandler);
            document.removeEventListener('mouseup', debouncedHandler);
            clearTimeout(timeoutId);
        };
    }, [isAdded]);

    const handleAddClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        e.preventDefault();

        // Final check for text
        const selection = window.getSelection();
        const text = selection?.toString().trim() || currentText;

        if (text) {
            onAdd(text);
            setIsAdded(true);
            setTimeout(() => {
                setIsVisible(false);
                setIsAdded(false);
                // Clear selection after adding? Optional.
            }, 800);
        }
    };

    if (!isVisible) return null;

    return (
        <div
            ref={menuRef}
            className="fixed z-[9999] flex items-center gap-2 p-1 bg-popover border border-border rounded-lg shadow-xl backdrop-blur-md animate-in fade-in zoom-in-95 duration-200"
            style={{ left: position.x, top: position.y, transform: 'translateX(-50%)' }}
            onMouseDown={(e) => e.stopPropagation()} // Prevent deselecting
        >
            <button
                onMouseDown={handleAddClick}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-md transition-all active:scale-95",
                    isAdded
                        ? "bg-green-500 text-foreground shadow-lg shadow-green-500/20"
                        : "bg-primary text-primary-foreground hover:shadow-lg hover:shadow-primary/20"
                )}
            >
                {isAdded ? (
                    <><PlusCircle className="w-3.5 h-3.5" /> Added!</>
                ) : (
                    <><PlusCircle className="w-3.5 h-3.5" /> Add to Context</>
                )}
            </button>
        </div>
    );
};
