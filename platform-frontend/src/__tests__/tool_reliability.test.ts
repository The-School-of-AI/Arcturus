// @ts-nocheck
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

        case 'fs:readDir': {
            try {
                const items = fs.readdirSync(args, { withFileTypes: true });
                const files = items.map(d => ({
                    name: d.name,
                    type: d.isDirectory() ? 'folder' : 'file'
                }));
                return { success: true, files };
            } catch (e: any) {
                return { success: false, error: e.message };
            }
        }
        case 'fs:viewOutline': {
            return { success: true, outline: 'Mock Outline: def foo' };
        }
        case 'terminal:read': {
            return { success: true, content: 'Mock Terminal Content' };
        }
    }
    return { success: false, error: 'Unknown channel' };
});

// Mock Global Fetch
(global as any).fetch = vi.fn(async (url, init) => {
    if (url.toString().includes('search')) return { json: async () => ({ result: 'Mock Search Result' }) };
    if (url.toString().includes('read-url')) return { json: async () => ({ content: 'Mock URL Content' }) };
    return { json: async () => ({}) };
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

    it('should handle simple replacements with replace_in_file', async () => {
        const file = 'simple_replace.txt';
        await fs.writeFileSync(path.join(TEST_DIR, file), 'Hello World');

        const res = await executeAgentTool({
            name: 'replace_in_file',
            arguments: { path: file, target: 'World', replacement: 'Universe' }
        }, mockContext);

        expect(res).toContain('Success');
        expect(fs.readFileSync(path.join(TEST_DIR, file), 'utf-8')).toBe('Hello Universe');
    });

    it('should list directory contents', async () => {
        await fs.writeFileSync(path.join(TEST_DIR, 'file1.txt'), '');
        await fs.mkdirSync(path.join(TEST_DIR, 'subdir'));

        // Mock fs:readDir since it uses Electron logic not simple node logic in the real app usually
        // But our tool splits it. Let's rely on the mock implementation we add below.
        const res = await executeAgentTool({
            name: 'list_dir',
            arguments: { path: TEST_DIR }
        }, mockContext);

        expect(res).toContain('[FILE] file1.txt');
        expect(res).toContain('[DIR] subdir');
    });

    it('should run background command and check status', async () => {
        // run_command uses shell:spawn
        const startRes = await executeAgentTool({
            name: 'run_command',
            arguments: { command: 'echo "bg task"', cwd: TEST_DIR }
        }, mockContext);

        expect(startRes).toMatch(/Success|Command started|STDOUT/);

        // If it returned a PID, check status
        if (startRes.includes('PID')) {
            const pidMatch = startRes.match(/PID: (\d+)/);
            if (pidMatch) {
                const statusRes = await executeAgentTool({
                    name: 'command_status',
                    arguments: { pid: pidMatch[1] }
                }, mockContext);
                expect(statusRes).toContain('Status: done');
            }
        }
    });

    it('should read terminal', async () => {
        const res = await executeAgentTool({ name: 'read_terminal', arguments: {} }, mockContext);
        expect(res).toBe('Mock Terminal Content');
    });

    it('should view file outline', async () => {
        const file = 'outline.py';
        await fs.writeFileSync(path.join(TEST_DIR, file), 'def foo(): pass');
        const res = await executeAgentTool({
            name: 'view_file_outline',
            arguments: { path: file }
        }, mockContext);
        expect(res).toContain('def foo');
    });

    it('should apply diff', async () => {
        const file = 'diff_test.txt';
        await fs.writeFileSync(path.join(TEST_DIR, file), 'Original Content');
        // This test mocks the successful application since we don't have python script in test env easily
        // But we should verify it TRIES to call the right shell command
        // Create a valid diff
        const diffContent = `diff --git a/diff_test.txt b/diff_test.txt
index 0000000..1111111 100644
--- a/diff_test.txt
+++ b/diff_test.txt
@@ -1 +1 @@
-Original Content
+Modified Content
`;

        const res = await executeAgentTool({
            name: 'apply_diff',
            arguments: { path: file, diff: diffContent }
        }, mockContext);
        // Our mock shell:exec will return success, so tool should succeed
        expect(res).toContain('Success');
    });

    it('should search web (mocked)', async () => {
        // We need to mock global fetch for this
        const res = await executeAgentTool({
            name: 'search_web',
            arguments: { query: 'test' }
        }, mockContext);
        expect(res).toContain('Mock Search Result');
    });

    it('should read url (mocked)', async () => {
        const res = await executeAgentTool({
            name: 'read_url',
            arguments: { url: 'http://test.com' }
        }, mockContext);
        expect(res).toContain('Mock URL Content');
    });

    it('should replace symbol', async () => {
        // Setup mock script
        const scriptsDir = path.join(TEST_DIR, 'scripts');
        if (!fs.existsSync(scriptsDir)) fs.mkdirSync(scriptsDir);
        // Mock the python script behavior
        await fs.writeFileSync(path.join(scriptsDir, 'replace_symbol.py'), 'print("Success")');

        const file = 'symbol.py';
        await fs.writeFileSync(path.join(TEST_DIR, file), 'def old(): pass');
        const res = await executeAgentTool({
            name: 'replace_symbol',
            arguments: { path: file, symbol: 'old', content: 'def new(): pass' }
        }, mockContext);
        // Mock execution results in success
        expect(res).toContain('Success');
    });
});
