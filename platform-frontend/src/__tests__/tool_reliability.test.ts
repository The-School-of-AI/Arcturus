// @vitest-environment node

import { describe, it, expect, vi, beforeAll, afterAll } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';
import { executeAgentTool, ToolContext } from '../features/ide/utils/agentTools';

const execAsync = promisify(exec);

// --- MOCK SETUP ---
// We mock window.electronAPI to simulate the Electron Main Process
// But we implement the logic using REAL Node.js calls to verify the underlying commands work.

const mockInvoke = vi.fn(async (channel: string, args: any) => {
    switch (channel) {
        case 'fs:writeFile': {
            fs.mkdirSync(path.dirname(args.path), { recursive: true });
            fs.writeFileSync(args.path, args.content);
            return { success: true };
        }
        case 'fs:readFile': {
            try {
                const content = fs.readFileSync(args, 'utf-8');
                return { success: true, content };
            } catch (e: any) {
                return { success: false, error: e.message };
            }
        }
        case 'fs:delete': {
            if (fs.existsSync(args)) fs.unlinkSync(args);
            return { success: true };
        }
        case 'fs:isGitignored': {
            // Simple mock: assume nothing is ignored in test env
            return { success: true, ignored: false };
        }
        case 'shell:spawn': {
            // We'll simulate spawn by just running it via exec (blocking for simplicity in test, or async)
            // Ideally we should return a PID and simulate status.
            // For this test, we'll run it immediately and store result in a "process map"
            try {
                const { stdout, stderr } = await execAsync(args.cmd, { cwd: args.cwd });
                // We fake a PID
                const pid = Math.floor(Math.random() * 10000).toString();
                (global as any).mockProcesses = (global as any).mockProcesses || {};
                (global as any).mockProcesses[pid] = { status: 'done', stdout, stderr, exitCode: 0 };
                return { success: true, pid };
            } catch (e: any) {
                const pid = Math.floor(Math.random() * 10000).toString();
                (global as any).mockProcesses = (global as any).mockProcesses || {};
                (global as any).mockProcesses[pid] = { status: 'done', stdout: '', stderr: e.message, exitCode: e.code || 1 };
                return { success: true, pid };
            }
        }
        case 'shell:exec': {
            // Synchronous exec (as used by synchronous tools)
            try {
                const { stdout, stderr } = await execAsync(args.cmd, { cwd: args.cwd });
                return { success: true, stdout, stderr };
            } catch (e: any) {
                return { success: false, error: e.message, stdout: '', stderr: e.message };
            }
        }
        case 'shell:status': {
            const proc = (global as any).mockProcesses?.[args];
            if (!proc) return { success: false, error: 'Process not found' };
            return { success: true, ...proc };
        }
        case 'fs:grep': {
            // REAL LOGIC TEST: Use the EXACT command logic from main.cjs (the fixed version)
            // We are testing if `grep -r -l -E` works for `vec1|vec2`
            const query = args.query;
            const root = args.root;

            // Note: In test env, we might not be in a git repo, so git grep might fail.
            // We'll simulate the main.cjs fallback logic.
            try {
                // Try git grep (might fail if not in repo)
                try {
                    const { stdout } = await execAsync(`git grep -I -l -E "${query}"`, { cwd: root });
                    const files = stdout.split('\n').filter(Boolean).map(f => f.replace(/^\.\//, ''));
                    return { success: true, files: files.slice(0, 50) };
                } catch (gitErr) {
                    // Fallback
                    const excludes = '--exclude-dir=.git --exclude-dir=node_modules --exclude-dir=.vscode --exclude-dir=dist --exclude-dir=build --exclude-dir=coverage --exclude-dir=.next';
                    const { stdout } = await execAsync(`grep -r -l -I -E ${excludes} "${query}" .`, { cwd: root });
                    const files = stdout.split('\n').filter(Boolean).map(f => f.replace(/^\.\//, ''));
                    return { success: true, files: files.slice(0, 50) };
                }
            } catch (e: any) {
                if (e.code === 1) return { success: true, files: [] }; // No matches
                return { success: false, error: e.message };
            }
        }
        case 'fs:find': {
            try {
                const { stdout } = await execAsync(`find . -name "*${args.pattern}*" -not -path "*/.*"`, { cwd: args.root });
                const files = stdout.split('\n').filter(Boolean).map(f => f.replace(/^\.\//, ''));
                return { success: true, files };
            } catch (e: any) {
                return { success: false, error: e.message };
            }
        }
    }
    return { success: false, error: 'Unknown channel' };
});

// Mock Global Window
(global as any).window = {
    electronAPI: {
        invoke: mockInvoke
    }
};

describe('Agent Tool Reliability', () => {
    const TEST_DIR = path.join(process.cwd(), 'temp_test_workspace_' + Date.now());

    const mockContext: ToolContext = {
        projectRoot: TEST_DIR,
        permissions: { blocked_commands: [], require_confirmation: false },
        startReview: (req, cb) => cb('allow_always'),
        openIdeDocument: vi.fn(),
        closeIdeDocument: vi.fn(),
        refreshExplorerFiles: vi.fn(),
        checkContentSafety: () => ({ safe: true, violations: [] }),
        checkPathSafety: () => ({ safe: true }),
        getContentTypeFromPath: (p) => p.split('.').pop() || null,
        API_BASE: 'http://localhost:3000'
    };

    beforeAll(() => {
        if (fs.existsSync(TEST_DIR)) fs.rmSync(TEST_DIR, { recursive: true, force: true });
        fs.mkdirSync(TEST_DIR);
    });

    afterAll(() => {
        if (fs.existsSync(TEST_DIR)) fs.rmSync(TEST_DIR, { recursive: true, force: true });
    });

    it('should create a file, find it, grep inside it, and execute it', async () => {
        const pyFile = 'vector_add.py';
        const pyContent = `
import sys
vec1 = [1, 2, 3]
vec2 = [4, 5, 6]
print(f"Adding {vec1} and {vec2}")
`;

        // 1. WRITE FILE
        const writeRes = await executeAgentTool({
            name: 'write_file',
            arguments: { path: pyFile, content: pyContent }
        }, mockContext);

        expect(writeRes).toContain('Success');
        expect(fs.existsSync(path.join(TEST_DIR, pyFile))).toBe(true);

        // 2. FIND FILE
        const findRes = await executeAgentTool({
            name: 'find_by_name',
            arguments: { pattern: 'vector', root: TEST_DIR }
        }, mockContext);
        expect(findRes).toContain('vector_add.py');

        // 3. GREP SEARCH (The critical test for regex support)
        // Testing "vec1|vec2" which failed previously
        const grepRes = await executeAgentTool({
            name: 'grep_search',
            arguments: { query: 'vec1|vec2', root: TEST_DIR }
        }, mockContext);

        // Debug output if empty
        if (grepRes.includes('No matches')) {
            console.error('Grep failed. Result:', grepRes);
        }

        expect(grepRes).toContain('vector_add.py');

        // 4. RUN SCRIPT
        const runRes = await executeAgentTool({
            name: 'run_script', // Should use run_script or run_command? run_script calls shell:exec via run_command logic usually?
            // In agentTools.ts, we have 'run_script' and 'run_command'.
            // run_script uses shell:exec (sync)
            // run_command uses shell:spawn (async)
            // Agent logs show usage of 'run_command' mostly? Or 'run_script'?
            // The new tool we added is 'run_script'.
            // Let's test 'run_script' for sync execution.
            arguments: { command: `python3 ${pyFile}` }
        }, mockContext);

        expect(runRes).toContain('STDOUT');
        expect(runRes).toContain('Adding [1, 2, 3] and [4, 5, 6]');
    });

    it('should handle multi_replace_file_content correctly', async () => {
        const file = 'replace_test.txt';
        const content = 'Hello World\nAnother Line\nTarget 1\nTarget 2';
        await fs.writeFileSync(path.join(TEST_DIR, file), content);

        const res = await executeAgentTool({
            name: 'multi_replace_file_content',
            arguments: {
                path: file,
                changes: [
                    { target: 'Target 1', replacement: 'Replaced 1' },
                    { target: 'Target 2', replacement: 'Replaced 2' }
                ]
            }
        }, mockContext);

        expect(res).toContain('Success');
        const newContent = fs.readFileSync(path.join(TEST_DIR, file), 'utf-8');
        expect(newContent).toContain('Replaced 1');
        expect(newContent).toContain('Replaced 2');
        expect(newContent).not.toContain('Target 1');
    });
});
