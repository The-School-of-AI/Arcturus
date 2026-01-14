import React, { useEffect, useState, useRef } from 'react';
import { PlusCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface SelectionMenuProps {
    onAdd: (text: string) => void;
    // Optional props for controlled usage (e.g. Monaco/Xterm)
    manualVisible?: boolean;
    manualPosition?: { x: number; y: number };
    manualText?: string;
}

export const SelectionMenu: React.FC<SelectionMenuProps> = ({ onAdd, manualVisible, manualPosition, manualText }) => {
    const [isVisible, setIsVisible] = useState(false);
    const [position, setPosition] = useState({ x: 0, y: 0 });
    const [currentText, setCurrentText] = useState("");
    const [isAdded, setIsAdded] = useState(false);
    const menuRef = useRef<HTMLDivElement>(null);

    // Controlled mode: sync local state with props
    useEffect(() => {
        if (manualVisible !== undefined) {
            setIsVisible(manualVisible);
        }
    }, [manualVisible]);

    useEffect(() => {
        if (manualPosition) {
            setPosition(manualPosition);
        }
    }, [manualPosition]);

    useEffect(() => {
        if (manualText) {
            setCurrentText(manualText);
        }
    }, [manualText]);


    // Auto mode effect (only runs if manual props are NOT provided)
    useEffect(() => {
        if (manualVisible !== undefined) return;

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
    }, [isAdded, manualVisible]);

    const handleAddClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        e.preventDefault();

        // Use manual text if provided, otherwise standard selection
        const text = manualText || window.getSelection()?.toString().trim() || currentText;

        if (text) {
            onAdd(text);
            setIsAdded(true);
            setTimeout(() => {
                // If it's controlled (manualVisible is set), let the parent handle hiding via prop update or timeout
                // But for visual feedback we reset isAdded
                if (manualVisible === undefined) setIsVisible(false);
                setIsAdded(false);
            }, 800);
        }
    };

    if (!isVisible && !isAdded) return null;

    return (
        <div
            ref={menuRef}
            className="fixed z-[9999] flex items-center bg-popover rounded-md shadow-xl animate-in fade-in zoom-in-95 duration-200"
            style={{ left: position.x, top: position.y, transform: 'translateX(-50%)' }}
            onMouseDown={(e) => e.stopPropagation()} // Prevent deselecting
        >
            <button
                onMouseDown={handleAddClick}
                className={cn(
                    "flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-sm transition-all active:scale-95 shadow-lg",
                    isAdded
                        ? "bg-green-500 text-white shadow-lg shadow-green-500/20"
                        : "bg-primary text-white hover:shadow-lg hover:shadow-primary/20"
                )}
            >
                {isAdded ? (
                    <><PlusCircle className="w-3.5 h-3.5 text-white" /> Added!</>
                ) : (
                    <><PlusCircle className="w-3.5 h-3.5 text-white" /> Add to Context</>
                )}
            </button>
        </div>
    );
};
