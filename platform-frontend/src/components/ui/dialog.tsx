import * as React from "react"
import { cn } from "@/lib/utils"
import { X } from "lucide-react"

// Simplified Dialog components without Radix UI dependency to avoid install errors
// This mimics the Shadcn/Radix structure lightly

interface DialogProps {
    open?: boolean;
    onOpenChange?: (open: boolean) => void;
    children: React.ReactNode;
}

export const Dialog: React.FC<DialogProps> = ({ open, onOpenChange, children }) => {
    // We can't easily control the trigger vs content separation without context or direct props
    // This is a naive implementation where we assume children[0] is trigger and children[1] is content
    // BUT Sidebar.tsx uses it structurally: Dialog -> Trigger -> Content

    // To make this work without complex Context, we'll use a simple Context
    return (
        <DialogContext.Provider value={{ open: !!open, onOpenChange: onOpenChange || (() => { }) }}>
            {children}
        </DialogContext.Provider>
    );
};

interface DialogContextType {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}
const DialogContext = React.createContext<DialogContextType>({ open: false, onOpenChange: () => { } });

export const DialogTrigger: React.FC<{ asChild?: boolean; children: React.ReactNode; onClick?: () => void }> = ({ asChild, children, onClick }) => {
    const { onOpenChange } = React.useContext(DialogContext);

    // Clone element to attach onClick if asChild
    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement<any>, {
            onClick: (e: any) => {
                children.props.onClick?.(e);
                onOpenChange(true);
            }
        });
    }

    return (
        <div onClick={() => onOpenChange(true)}>
            {children}
        </div>
    );
};

export const DialogContent: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => {
    const { open, onOpenChange } = React.useContext(DialogContext);

    if (!open) return null;

    return createPortal(
        <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/80 backdrop-blur-sm">
            <div className={cn(
                "relative z-[9999] grid w-full max-w-lg gap-4 border bg-background p-6 shadow-lg duration-200 sm:rounded-lg border-white/10",
                className
            )}>
                <div onClick={() => onOpenChange(false)} className="absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity hover:opacity-100 focus:outline-none disabled:pointer-events-none data-[state=open]:bg-accent data-[state=open]:text-muted-foreground cursor-pointer text-white">
                    <X className="h-4 w-4" />
                    <span className="sr-only">Close</span>
                </div>
                {children}
            </div>
        </div>,
        document.body
    );
};

export const DialogHeader: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
    <div className={cn("flex flex-col space-y-1.5 text-center sm:text-left", className)}>
        {children}
    </div>
);

export const DialogTitle: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
    <div className={cn("text-lg font-semibold leading-none tracking-tight", className)}>
        {children}
    </div>
);

export const DialogFooter: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className }) => (
    <div className={cn("flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2", className)}>
        {children}
    </div>
);
