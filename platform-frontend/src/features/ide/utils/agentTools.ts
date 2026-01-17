
import type { RAGDocument } from '../../../types';

export interface ToolContext {
    projectRoot: string;
    permissions: any;
    // Callbacks to interact with the UI/Store
    startReview: (request: any, onResolve: (decision: 'allow_once' | 'allow_always' | 'deny') => void) => void;
    openIdeDocument: (doc: RAGDocument) => void;
    closeIdeDocument: (id: string) => void;
    refreshExplorerFiles: () => void;
    checkContentSafety: (content: string, type: any) => { safe: boolean; violations: string[] };
    checkPathSafety: (path: string) => { safe: boolean; violation?: string };
    getContentTypeFromPath: (path: string) => string | null;
    API_BASE: string;
}

export const executeAgentTool = async (
    toolCall: { name: string; arguments: any },
    context: ToolContext
): Promise<string> => {
    const {
        projectRoot, permissions, startReview, openIdeDocument,
        closeIdeDocument, refreshExplorerFiles, checkContentSafety,
        checkPathSafety, getContentTypeFromPath, API_BASE
    } = context;

    console.log(`[IDE Agent] Executing tool: ${toolCall.name}`, toolCall.arguments);

    // --- Permission Check ---
    if (toolCall.name === 'run_command') {
        const cmdName = toolCall.arguments.command?.split(' ')[0];
        if (permissions.blocked_commands.includes(cmdName)) {
            return `Error: Command '${cmdName}' is BLOCKED by security policy.`;
        }
        // Check shell command patterns
        const shellCheck = checkContentSafety(toolCall.arguments.command || '', 'shell');
        if (!shellCheck.safe) {
            return `Error: Command blocked by security policy. Reason: ${shellCheck.violations.join(', ')}`;
        }
    }

    const validatePath = (path: string) => {
        if (!projectRoot) return { valid: true, path };
        let fullPath = path;
        if (!path.startsWith('/') && !path.startsWith('C:') && !path.startsWith('file://')) {
            fullPath = `${projectRoot}/${path}`.replace(/\/+/g, '/');
        }
        // Simple security checks
        if (fullPath.includes('/../') || fullPath.endsWith('/..')) return { valid: false, error: "Access denied (..)" };
        if (!fullPath.startsWith(projectRoot)) return { valid: false, error: "Access denied (Outside Project)" };
        return { valid: true, path: fullPath };
    };

    // Helper to check if a path is gitignored
    const checkGitignore = async (filePath: string): Promise<{ ignored: boolean; error?: string }> => {
        if (!projectRoot || !window.electronAPI) return { ignored: false };
        try {
            const result = await window.electronAPI.invoke('fs:isGitignored', { filePath, projectRoot });
            return { ignored: result?.ignored || false };
        } catch (e) {
            console.warn('[IDE Agent] Gitignore check failed:', e);
            return { ignored: false };
        }
    };

    try {
        switch (toolCall.name) {
            case 'read_file': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                // Check if file is gitignored
                const gitCheck = await checkGitignore(validation.path!);
                if (gitCheck.ignored) {
                    return `Error: Cannot read gitignored file. File is excluded by .gitignore.`;
                }

                const res = await window.electronAPI?.invoke('fs:readFile', validation.path!);
                if (res?.success) {
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        content: res.content,
                        type: 'file'
                    });
                    return res.content;
                }
                return `Error: ${res?.error || 'Unknown error'}`;
            }

            case 'run_script': {
                const validation = validatePath(projectRoot || '');
                if (!validation.valid) return `Error: ${validation.error}`;

                // 1. PERMISSION CHECK
                const permDecision = await new Promise<'allow_once' | 'allow_always' | 'deny'>((resolve) => {
                    startReview({
                        id: crypto.randomUUID(),
                        type: 'command',
                        operation: `Run Script: ${toolCall.arguments.command}`,
                        path: 'terminal',
                        risk: 'medium',
                        variant: 'review_status'
                    }, resolve);
                });

                if (permDecision === 'deny') return "User denied script execution.";

                // 2. EXECUTE SYNCHRONOUSLY
                try {
                    const result = await window.electronAPI.invoke('shell:exec', {
                        cmd: toolCall.arguments.command,
                        cwd: projectRoot || '',
                        projectRoot: projectRoot || ''
                    });

                    if (!result.success) {
                        return `Error: ${result.error}\nSTDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`;
                    }
                    return `STDOUT:\n${result.stdout}\nSTDERR:\n${result.stderr}`;

                } catch (e: any) {
                    return `System Error: ${e.message}`;
                }
            }

            case 'apply_diff': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                // 1. PERMISSION CHECK
                const permDecision = await new Promise<'allow_once' | 'allow_always' | 'deny'>((resolve) => {
                    startReview({
                        id: crypto.randomUUID(),
                        type: 'write',
                        operation: `Apply Diff to ${validation.path}`,
                        path: validation.path!,
                        risk: 'high',
                        variant: 'review'
                    }, resolve);
                });

                if (permDecision === 'deny') return "User denied diff application.";

                const diffFile = `/tmp/patch_${Date.now()}.diff`;
                try {
                    // Write patch file
                    await window.electronAPI.invoke('fs:writeFile', { path: diffFile, content: toolCall.arguments.diff });

                    // Apply patch
                    const res = await window.electronAPI.invoke('shell:exec', {
                        cmd: `git apply --reject --whitespace=fix ${diffFile}`,
                        cwd: projectRoot || '',
                        projectRoot: projectRoot || ''
                    });

                    // Cleanup
                    await window.electronAPI.invoke('fs:delete', diffFile);

                    if (!res.success) {
                        return `Failed to apply diff: ${res.stderr}. \nHint: Ensure the diff format is correct (unified diff) and context matches.`;
                    }

                    // Refresh
                    refreshExplorerFiles();
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        type: 'file'
                    });

                    return "Success: Diff applied.";

                } catch (e: any) {
                    return `Error applying diff: ${e.message}`;
                }
            }

            case 'replace_symbol': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                const { symbol, content } = toolCall.arguments;

                // 1. PERMISSION CHECK
                const permDecision = await new Promise<'allow_once' | 'allow_always' | 'deny'>((resolve) => {
                    startReview({
                        id: crypto.randomUUID(),
                        type: 'write',
                        operation: `Replace symbol '${symbol}' in ${validation.path}`,
                        path: validation.path!,
                        risk: 'high',
                        variant: 'review'
                    }, resolve);
                });

                if (permDecision === 'deny') return "User denied symbol replacement.";

                const tempContentFile = `/tmp/symbol_${Date.now()}.txt`;
                // Assumes script exists. IdeAgentPanel logic ensures this prompt-side or user ensures it.
                // In a perfect world we bundle this script. 
                const scriptPath = `${projectRoot}/scripts/replace_symbol.py`;

                try {
                    await window.electronAPI.invoke('fs:writeFile', { path: tempContentFile, content: content });

                    const res = await window.electronAPI.invoke('shell:exec', {
                        cmd: `python3 ${scriptPath} "${validation.path}" "${symbol}" "${tempContentFile}"`,
                        cwd: projectRoot || '',
                        projectRoot: projectRoot || ''
                    });

                    // Cleanup
                    await window.electronAPI.invoke('fs:delete', tempContentFile);

                    if (!res.success) {
                        return `Failed to replace symbol: ${res.stderr || res.stdout}`;
                    }

                    refreshExplorerFiles();
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        type: 'file'
                    });

                    return `Success: Replaced symbol '${symbol}'.`;

                } catch (e: any) {
                    return `Error replacing symbol: ${e.message}`;
                }
            }

            case 'write_file': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                const pathCheck = checkPathSafety(validation.path!);
                if (!pathCheck.safe) return `Error: Cannot write to sensitive file. Reason: ${pathCheck.violation}`;

                const contentType = getContentTypeFromPath(validation.path!);
                if (contentType) {
                    const contentCheck = checkContentSafety(toolCall.arguments.content || '', contentType);
                    if (!contentCheck.safe) return `Error: Content blocked by security policy. Patterns detected: ${contentCheck.violations.join(', ')}`;
                }

                // 1. BACKUP
                let originalContent = '';
                const readRes = await window.electronAPI.invoke('fs:readFile', validation.path!);
                if (readRes && readRes.success) originalContent = readRes.content;

                // 2. PROVISIONAL WRITE
                const res = await window.electronAPI.invoke('fs:writeFile', {
                    path: validation.path,
                    content: toolCall.arguments.content
                });
                if (!res.success) return `Error: ${res.error}`;

                // 3. VISUALIZE
                openIdeDocument({
                    id: `diff:${validation.path}`,
                    title: `Review: ${validation.path!.split('/').pop()}`,
                    type: 'git_diff',
                    originalContent: originalContent,
                    modifiedContent: toolCall.arguments.content,
                    language: getContentTypeFromPath(validation.path!) || 'plaintext'
                });

                // 4. REVIEW
                const decision = await new Promise<'allow_once' | 'allow_always' | 'deny'>((resolve) => {
                    startReview({
                        id: crypto.randomUUID(),
                        type: 'write',
                        operation: `Modify ${validation.path}`,
                        path: validation.path!,
                        risk: 'high',
                        variant: 'review'
                    }, resolve);
                });

                // 5. ACTION
                if (decision === 'deny') {
                    // Revert
                    await window.electronAPI.invoke('fs:writeFile', { path: validation.path, content: originalContent });
                    closeIdeDocument(`diff:${validation.path}`);
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        content: originalContent,
                        type: 'file'
                    });
                    return "User rejected the changes. File reverted to original state.";
                }

                refreshExplorerFiles();
                closeIdeDocument(`diff:${validation.path}`);
                openIdeDocument({
                    id: validation.path!,
                    title: validation.path!.split('/').pop() || 'Untitled',
                    content: toolCall.arguments.content,
                    type: 'file'
                });

                return `Success: File written to ${validation.path}`;
            }

            case 'replace_in_file': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                const { target, replacement } = toolCall.arguments;
                const originalRes = await window.electronAPI.invoke('fs:readFile', validation.path!);
                if (!originalRes || !originalRes.success) return `Error reading file: ${originalRes?.error || 'Unknown error'}`;

                if (!originalRes.content.includes(target)) {
                    return "Error: Target text not found in file. Ensure exact match including whitespace.";
                }
                if (originalRes.content.indexOf(target) !== originalRes.content.lastIndexOf(target)) {
                    return "Error: Target text is ambiguous (found multiple times). Provide more context.";
                }

                const newContent = originalRes.content.replace(target, replacement);
                const replaceRes = await window.electronAPI.invoke('fs:writeFile', { path: validation.path!, content: newContent });

                if (replaceRes.success) {
                    refreshExplorerFiles();
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        content: newContent,
                        type: 'file'
                    });
                    return `Success: Text replaced in ${validation.path}`;
                }
                return `Error writing file: ${replaceRes.error}`;
            }

            case 'list_dir': {
                const validation = validatePath(toolCall.arguments.path || "./");
                if (!validation.valid) return `Error: ${validation.error}`;
                const listRes = await window.electronAPI.invoke('fs:readDir', validation.path);
                if (!listRes || !listRes.success) return `Error: ${listRes?.error || 'Unknown error'}`;
                return (listRes.files || []).map((f: any) => `${f.type === 'folder' ? '[DIR]' : '[FILE]'} ${f.name}`).join('\n') || "Empty directory.";
            }

            case 'find_by_name': {
                const rootValidation = validatePath(toolCall.arguments.root || "./");
                if (!rootValidation.valid) return `Error: ${rootValidation.error}`;
                const findRes = await window.electronAPI.invoke('fs:find', {
                    pattern: toolCall.arguments.pattern,
                    root: rootValidation.path
                });
                if (!findRes || !findRes.success) return `Error: ${findRes?.error || 'Unknown error'}`;
                return (findRes.files || []).join('\n') || "No matches found.";
            }

            case 'grep_search': {
                const rootValidation = validatePath(toolCall.arguments.root || "./");
                if (!rootValidation.valid) return `Error: ${rootValidation.error}`;
                const grepRes = await window.electronAPI.invoke('fs:grep', {
                    query: toolCall.arguments.query,
                    root: rootValidation.path
                });
                if (!grepRes || !grepRes.success) return `Error: ${grepRes?.error || 'Unknown error'}`;
                return (grepRes.files || []).join('\n') || "No matches found.";
            }

            case 'view_file_outline': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;
                const outlineRes = await window.electronAPI.invoke('fs:viewOutline', validation.path);
                if (!outlineRes || !outlineRes.success) return `Error: ${outlineRes?.error || 'Unknown error'}`;
                return outlineRes.outline || "No items found in file.";
            }

            case 'read_terminal': {
                const termRes = await window.electronAPI.invoke('terminal:read');
                if (!termRes) return "Error: Failed to read terminal.";
                return termRes.success ? termRes.content : `Error reading terminal: ${termRes.error}`;
            }

            case 'multi_replace_file_content': {
                const validation = validatePath(toolCall.arguments.path);
                if (!validation.valid) return `Error: ${validation.error}`;

                const changes = toolCall.arguments.changes;
                if (!changes || !Array.isArray(changes)) return "Error: 'changes' arguments must be an array.";

                // 1. BACKUP
                const multiReadRes = await window.electronAPI.invoke('fs:readFile', validation.path!);
                if (!multiReadRes || !multiReadRes.success) return `Error reading file: ${multiReadRes?.error || 'Unknown error'}`;

                const originalContent = multiReadRes.content;
                let currentContent = originalContent;

                for (let i = 0; i < changes.length; i++) {
                    const change = changes[i];
                    if (!currentContent.includes(change.target)) {
                        return `Error: Change ${i + 1}/${changes.length} failed. Target text not found.`;
                    }
                    if (currentContent.indexOf(change.target) !== currentContent.lastIndexOf(change.target)) {
                        return `Error: Change ${i + 1}/${changes.length} failed. Target text found multiple times. Provide more unique context.`;
                    }
                    currentContent = currentContent.replace(change.target, change.replacement);
                }

                // 2. PROVISIONAL WRITE
                const writeRes = await window.electronAPI.invoke('fs:writeFile', { path: validation.path, content: currentContent });
                if (!writeRes.success) return `Error: ${writeRes.error}`;

                // 3. VISUALIZE
                openIdeDocument({
                    id: `diff:${validation.path}`,
                    title: `Review: ${validation.path!.split('/').pop()}`,
                    type: 'git_diff',
                    originalContent: originalContent,
                    modifiedContent: currentContent,
                    language: getContentTypeFromPath(validation.path!) || 'plaintext'
                });

                // 4. REVIEW
                const decision = await new Promise<'allow_once' | 'allow_always' | 'deny'>((resolve) => {
                    startReview({
                        id: crypto.randomUUID(),
                        type: 'write',
                        operation: `Multi-Edit ${validation.path}`,
                        path: validation.path!,
                        risk: 'high',
                        variant: 'review'
                    }, resolve);
                });

                if (decision === 'deny') {
                    await window.electronAPI.invoke('fs:writeFile', { path: validation.path, content: originalContent });
                    closeIdeDocument(`diff:${validation.path}`);
                    openIdeDocument({
                        id: validation.path!,
                        title: validation.path!.split('/').pop() || 'Untitled',
                        content: originalContent,
                        type: 'file'
                    });
                    return "User rejected the edits. File reverted to original state.";
                }

                refreshExplorerFiles();
                closeIdeDocument(`diff:${validation.path}`);
                openIdeDocument({
                    id: validation.path!,
                    title: validation.path!.split('/').pop() || 'Untitled',
                    content: currentContent,
                    type: 'file'
                });

                return `Success: Applied ${changes.length} changes to ${validation.path}`;
            }

            case 'run_command': {
                let cwd = toolCall.arguments.cwd;
                if (!cwd || cwd.trim() === '.' || cwd.trim() === './') {
                    cwd = projectRoot;
                } else if (projectRoot && !cwd.startsWith('/') && !cwd.startsWith('C:') && !cwd.startsWith('file://')) {
                    cwd = `${projectRoot}/${cwd}`.replace(/\/+/g, '/');
                }

                const res = await window.electronAPI.invoke('shell:spawn', {
                    cmd: toolCall.arguments.command,
                    cwd: cwd,
                    projectRoot: projectRoot
                });

                if (res.success) {
                    refreshExplorerFiles();
                    await new Promise(r => setTimeout(r, 500));
                    const statusRes = await window.electronAPI.invoke('shell:status', res.pid);
                    if (statusRes.success && statusRes.status === 'done') {
                        if (!statusRes.stdout && !statusRes.stderr) return "Success (No Output)";
                        return `STDOUT:\n${statusRes.stdout}\nSTDERR:\n${statusRes.stderr}`;
                    } else {
                        return `Command started in background (PID: ${res.pid}). Status: ${statusRes.status}. Output so far:\n${statusRes.stdout}`;
                    }
                }
                return `Error: ${res.error}`;
            }

            case 'command_status': {
                const pid = toolCall.arguments.pid;
                const res = await window.electronAPI.invoke('shell:status', pid);
                if (!res.success) return `Error: ${res.error}`;
                return `Status: ${res.status}\nExit Code: ${res.exitCode}\nSTDOUT:\n${res.stdout}\nSTDERR:\n${res.stderr}`;
            }

            case 'search_web': {
                const searchRes = await fetch(`${API_BASE}/ide/tools/search`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query: toolCall.arguments.query })
                });
                const data = await searchRes.json();
                return typeof data === 'string' ? data : JSON.stringify(data);
            }

            case 'read_url': {
                const readRes = await fetch(`${API_BASE}/ide/tools/read-url`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: toolCall.arguments.url })
                });
                const data = await readRes.json();
                return typeof data === 'string' ? data : JSON.stringify(data);
            }

            default:
                return `Error: Unknown tool '${toolCall.name}'`;
        }
    } catch (e) {
        return `System Error: ${e}`;
    }
};
