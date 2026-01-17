import { useState, useCallback, useRef } from 'react';
import type { PermissionRequest, PermissionDecision } from '@/components/dialogs/PermissionDialog';
import { checkStoredPermission } from '@/components/dialogs/PermissionDialog';

interface UsePermissionDialogReturn {
    currentRequest: PermissionRequest | null;
    requestPermission: (request: PermissionRequest, projectRoot: string) => Promise<PermissionDecision['action']>;
    handleDecision: (decision: PermissionDecision['action']) => void;
    projectRoot: string;
}

/**
 * Hook to manage permission dialogs for agent operations
 * 
 * Usage:
 * const { currentRequest, requestPermission, handleDecision, projectRoot } = usePermissionDialog();
 * 
 * // In tool execution:
 * const decision = await requestPermission({
 *   id: 'unique-id',
 *   type: 'write',
 *   operation: 'Write to config.json',
 *   path: '/path/to/config.json',
 *   risk: 'medium'
 * }, explorerRootPath);
 * 
 * if (decision === 'deny') return 'Operation denied by user';
 * 
 * // Render the dialog:
 * <PermissionDialog 
 *   request={currentRequest} 
 *   projectRoot={projectRoot}
 *   onDecision={handleDecision} 
 * />
 */
export function usePermissionDialog(): UsePermissionDialogReturn {
    const [currentRequest, setCurrentRequest] = useState<PermissionRequest | null>(null);
    const [projectRoot, setProjectRoot] = useState<string>('');

    // Use a ref to store the resolve function for the current promise
    const resolveRef = useRef<((value: PermissionDecision['action']) => void) | null>(null);

    const requestPermission = useCallback(async (
        request: PermissionRequest,
        root: string
    ): Promise<PermissionDecision['action']> => {
        // Check if we have a stored "always allow" permission
        const storedDecision = checkStoredPermission(
            root,
            request.type,
            request.path || request.command || '*'
        );

        if (storedDecision?.action === 'allow_always') {
            console.log('[Permission] Using stored "always allow" for', request.type, request.path);
            return 'allow_always';
        }

        // Show dialog and wait for user decision
        return new Promise((resolve) => {
            resolveRef.current = resolve;
            setProjectRoot(root);
            setCurrentRequest(request);
        });
    }, []);

    const handleDecision = useCallback((decision: PermissionDecision['action']) => {
        if (resolveRef.current) {
            resolveRef.current(decision);
            resolveRef.current = null;
        }
        setCurrentRequest(null);
    }, []);

    return {
        currentRequest,
        requestPermission,
        handleDecision,
        projectRoot
    };
}

/**
 * Helper to determine risk level based on operation type
 */
export function determineRiskLevel(
    operationType: 'write' | 'delete' | 'execute' | 'read_sensitive',
    path?: string,
    command?: string
): 'low' | 'medium' | 'high' {
    // High risk operations
    if (operationType === 'delete') return 'high';
    if (operationType === 'execute' && command) {
        const dangerousPatterns = [/sudo/i, /rm/i, /mv/i, /chmod/i, /chown/i];
        if (dangerousPatterns.some(p => p.test(command))) return 'high';
    }

    // Medium risk
    if (operationType === 'write') {
        const sensitivePatterns = [/config/i, /\.json$/i, /\.env/i, /\.yaml$/i, /\.yml$/i];
        if (path && sensitivePatterns.some(p => p.test(path))) return 'medium';
        return 'low';
    }

    if (operationType === 'execute') return 'medium';
    if (operationType === 'read_sensitive') return 'medium';

    return 'low';
}

export default usePermissionDialog;
