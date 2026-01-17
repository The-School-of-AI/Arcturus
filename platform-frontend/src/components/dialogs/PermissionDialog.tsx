import React, { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, Shield, Check, X, Clock } from 'lucide-react';
import { cn } from '@/lib/utils';

// Permission storage - persists in localStorage per project
const PERMISSION_STORAGE_KEY = 'arcturus_agent_permissions';

export interface PermissionRequest {
    id: string;
    type: 'write' | 'delete' | 'execute' | 'read_sensitive';
    operation: string;  // Description of what's being done
    path?: string;      // File path if applicable
    command?: string;   // Command if applicable
    risk: 'low' | 'medium' | 'high';
    variant?: 'modal' | 'review';
}

export interface PermissionDecision {
    action: 'allow_once' | 'allow_always' | 'deny';
    timestamp: number;
}

interface StoredPermissions {
    [projectRoot: string]: {
        [operationType: string]: {
            [pathOrPattern: string]: PermissionDecision;
        };
    };
}

// Load stored permissions
function loadPermissions(): StoredPermissions {
    try {
        const stored = localStorage.getItem(PERMISSION_STORAGE_KEY);
        return stored ? JSON.parse(stored) : {};
    } catch {
        return {};
    }
}

// Save permissions
function savePermissions(permissions: StoredPermissions) {
    localStorage.setItem(PERMISSION_STORAGE_KEY, JSON.stringify(permissions));
}

// Check if operation is pre-approved
export function checkStoredPermission(
    projectRoot: string,
    operationType: string,
    pathOrPattern: string
): PermissionDecision | null {
    const permissions = loadPermissions();
    const projectPerms = permissions[projectRoot]?.[operationType]?.[pathOrPattern];

    if (projectPerms?.action === 'allow_always') {
        return projectPerms;
    }
    return null;
}

// Store a permission decision
export function storePermission(
    projectRoot: string,
    operationType: string,
    pathOrPattern: string,
    decision: PermissionDecision
) {
    const permissions = loadPermissions();

    if (!permissions[projectRoot]) permissions[projectRoot] = {};
    if (!permissions[projectRoot][operationType]) permissions[projectRoot][operationType] = {};

    permissions[projectRoot][operationType][pathOrPattern] = decision;
    savePermissions(permissions);
}

// Clear all permissions for a project
export function clearProjectPermissions(projectRoot: string) {
    const permissions = loadPermissions();
    delete permissions[projectRoot];
    savePermissions(permissions);
}

interface PermissionDialogProps {
    request: PermissionRequest | null;
    projectRoot: string;
    onDecision: (decision: 'allow_once' | 'allow_always' | 'deny') => void;
    variant?: 'modal' | 'review' | 'review_status';
}

export const PermissionDialog: React.FC<PermissionDialogProps> = ({
    request,
    projectRoot,
    onDecision,
    variant = 'modal'
}) => {
    const [isVisible, setIsVisible] = useState(false);
    const [shouldRemember, setShouldRemember] = useState(false);

    useEffect(() => {
        if (request) {
            setIsVisible(true);
        }
    }, [request]);

    const handleDecision = useCallback((action: PermissionDecision['action']) => {
        if (!request) return;

        // Store decision if "always allow"
        if (action === 'allow_always') {
            storePermission(
                projectRoot,
                request.type,
                request.path || request.command || '*',
                { action, timestamp: Date.now() }
            );
        }

        setIsVisible(false);
        onDecision(action);
    }, [request, projectRoot, onDecision]);

    if (!request || !isVisible) return null;

    const riskColors = {
        low: 'text-green-500',
        medium: 'text-yellow-500',
        high: 'text-red-500'
    };

    const riskBgColors = {
        low: 'bg-green-500/10 border-green-500/30',
        medium: 'bg-yellow-500/10 border-yellow-500/30',
        high: 'bg-red-500/10 border-red-500/30'
    };

    const containerClasses = variant === 'modal'
        ? "fixed inset-0 z-[9999] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200"
        : "absolute bottom-6 right-6 z-[50] w-[400px] animate-in slide-in-from-right duration-200 shadow-2xl"; // Floating panel

    const cardClasses = cn(
        "w-full bg-card border border-border rounded-xl shadow-2xl overflow-hidden",
        variant === 'modal' ? "max-w-md animate-in zoom-in-95 duration-200" : ""
    );

    return (
        <div className={containerClasses}>
            <div className={cardClasses}>
                {/* Header */}
                <div className={cn(
                    "px-5 py-4 flex items-center gap-3 border-b",
                    riskBgColors[request.risk]
                )}>
                    <div className={cn("p-2 rounded-lg", riskBgColors[request.risk])}>
                        {request.risk === 'high' ? (
                            <AlertTriangle className={cn("w-5 h-5", riskColors[request.risk])} />
                        ) : (
                            <Shield className={cn("w-5 h-5", riskColors[request.risk])} />
                        )}
                    </div>
                    <div>
                        <h3 className="font-semibold text-foreground">
                            {variant === 'review' ? 'Review Changes' : 'Agent Permission Request'}
                        </h3>
                        <p className={cn("text-xs font-medium", riskColors[request.risk])}>
                            {request.risk.toUpperCase()} RISK
                        </p>
                    </div>
                </div>

                {/* Content */}
                <div className="px-5 py-4 space-y-4">
                    {variant === 'modal' && (
                        <div>
                            <p className="text-sm text-foreground/90 font-medium mb-2">
                                The agent wants to:
                            </p>
                            <div className="bg-muted/50 rounded-lg p-3 border border-border/50">
                                <p className="text-sm font-mono text-foreground/80">
                                    {request.operation}
                                </p>
                            </div>
                        </div>
                    )}

                    {variant === 'review' && (
                        <div className="text-sm text-foreground/90">
                            The agent has proposed changes to <b>{request.path?.split('/').pop()}</b>.
                            <br />
                            Review the diff in the editor and accept or reject.
                        </div>
                    )}

                    {variant === 'modal' && request.path && (
                        <div>
                            <p className="text-xs text-muted-foreground mb-1">File:</p>
                            <p className="text-sm font-mono text-foreground/80 truncate bg-muted/30 px-2 py-1 rounded">
                                {request.path}
                            </p>
                        </div>
                    )}
                </div>

                {/* Actions */}
                <div className="px-5 py-4 border-t border-border/50 flex gap-2">
                    <button
                        onClick={() => handleDecision('deny')}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-destructive/10 hover:bg-destructive/20 text-destructive rounded-lg font-medium text-sm transition-colors"
                    >
                        <X className="w-4 h-4" />
                        {variant === 'review' ? 'Reject Changes' : 'Deny'}
                    </button>
                    {variant === 'modal' && (
                        <button
                            onClick={() => handleDecision('allow_once')}
                            className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-muted hover:bg-muted/80 text-foreground rounded-lg font-medium text-sm transition-colors"
                        >
                            <Clock className="w-4 h-4" />
                            Allow Once
                        </button>
                    )}
                    <button
                        onClick={() => handleDecision(variant === 'review' ? 'allow_once' : 'allow_always')}
                        className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-primary/10 hover:bg-primary/20 text-primary rounded-lg font-medium text-sm transition-colors"
                    >
                        <Check className="w-4 h-4" />
                        {variant === 'review' ? 'Accept Changes' : 'Always Allow'}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PermissionDialog;
