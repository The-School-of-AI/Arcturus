import React, { forwardRef, useEffect, useImperativeHandle, useState } from 'react';

export interface WikiLinkListProps {
    items: string[];
    command: (props: { id: string }) => void;
}

export const WikiLinkList = forwardRef((props: WikiLinkListProps, ref) => {
    const [selectedIndex, setSelectedIndex] = useState(0);

    const selectItem = (index: number) => {
        const item: any = props.items[index];
        if (item) {
            const isGrep = typeof item === 'object' && item.file;
            const path = isGrep ? (item.file.startsWith('Notes/') ? item.file : `Notes/${item.file}`) : item;
            const fileName = path.split('/').pop()?.replace('.md', '') || path;
            const content = isGrep ? item.content : null;
            const line = isGrep ? item.line : null;

            props.command({ id: path, label: fileName, targetLine: line, searchText: content } as any);
        }
    };

    const upHandler = () => {
        setSelectedIndex((selectedIndex + props.items.length - 1) % props.items.length);
    };

    const downHandler = () => {
        setSelectedIndex((selectedIndex + 1) % props.items.length);
    };

    const enterHandler = () => {
        selectItem(selectedIndex);
    };

    useEffect(() => setSelectedIndex(0), [props.items]);

    useImperativeHandle(ref, () => ({
        onKeyDown: ({ event }: { event: KeyboardEvent }) => {
            if (event.key === 'ArrowUp') {
                upHandler();
                return true;
            }

            if (event.key === 'ArrowDown') {
                downHandler();
                return true;
            }

            if (event.key === 'Enter') {
                enterHandler();
                return true;
            }

            return false;
        },
    }));

    return (
        <div className="bg-popover border border-border/50 rounded-lg shadow-xl overflow-hidden min-w-[280px] flex flex-col p-1.5 backdrop-blur-md animate-in fade-in zoom-in-95 duration-200">
            <div className="px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground/70 border-b border-border/30 mb-1">
                Notes
            </div>
            {props.items.length
                ? props.items.map((item: any, index) => {
                    const isGrep = typeof item === 'object' && item.file;
                    const path = isGrep ? (item.file.startsWith('Notes/') ? item.file : `Notes/${item.file}`) : item;
                    const fileName = path.split('/').pop()?.replace('.md', '') || path;
                    const folder = path.split('/').slice(0, -1).join('/') || 'Root';
                    const content = isGrep ? item.content : null;
                    const line = isGrep ? item.line : null;

                    return (
                        <button
                            className={`flex flex-col items-start px-3 py-2 text-sm rounded-md transition-all duration-200 border-l-2 ${index === selectedIndex
                                ? 'bg-blue-500/10 text-blue-500 border-blue-500 shadow-sm'
                                : 'hover:bg-muted/50 text-foreground/80 hover:text-foreground border-transparent'
                                }`}
                            key={index}
                            onClick={() => selectItem(index)}
                            onMouseDown={(e) => e.preventDefault()}
                        >
                            <div className="flex items-center justify-between w-full gap-2">
                                <span className="font-semibold truncate flex-1 text-left">{fileName}</span>
                                {line && <span className="text-[9px] font-mono opacity-40 bg-muted px-1 rounded shrink-0">L{line}</span>}
                            </div>
                            <span className="text-[10px] opacity-40 truncate w-full text-left font-mono">
                                {folder}
                            </span>
                            {content && (
                                <div className="text-[10px] opacity-70 line-clamp-1 w-full text-left mt-1 italic border-t border-border/20 pt-1">
                                    {content.trim()}
                                </div>
                            )}
                        </button>
                    );
                })
                : <div className="px-3 py-3 text-sm text-muted-foreground italic text-center">No matches found</div>
            }
        </div>
    );
});

WikiLinkList.displayName = 'WikiLinkList';
