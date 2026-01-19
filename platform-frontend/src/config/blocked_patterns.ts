/**
 * BLOCKED_PATTERNS - Security patterns to detect and block dangerous code
 * 
 * These patterns are checked BEFORE writing files or executing code.
 * Matches any of these patterns will BLOCK the operation.
 * 
 * Ported from Python sandbox (tools/sandbox.py) and extended for TypeScript.
 */

export interface BlockedPattern {
    pattern: RegExp;
    description: string;
}

export interface BlockedPatterns {
    shell: BlockedPattern[];
    python: BlockedPattern[];
    javascript: BlockedPattern[];
    paths: BlockedPattern[];
}

export const BLOCKED_PATTERNS: BlockedPatterns = {
    // Shell command patterns (applied to run_command)
    shell: [
        { pattern: /rm\s+-rf\s+[\/~]/i, description: "Recursive file deletion from root/home" },
        { pattern: /sudo\s+/i, description: "Sudo command" },
        { pattern: />\s*\/dev\/sd/i, description: "Direct disk write" },
        { pattern: /mkfs/i, description: "Filesystem format" },
        { pattern: /dd\s+if=.*of=\/dev/i, description: "Direct disk write with dd" },
        { pattern: /:\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:/i, description: "Fork bomb" },
        { pattern: /shutdown|reboot|init\s+0/i, description: "System shutdown/reboot" },
        { pattern: /curl.*\|\s*(ba)?sh/i, description: "Piped remote script execution" },
        { pattern: /wget.*\|\s*(ba)?sh/i, description: "Piped remote script execution" },
    ],

    // Python code patterns (applied to .py files)
    python: [
        { pattern: /os\.system\s*\(/i, description: "Shell command execution via os.system" },
        { pattern: /subprocess\.(run|call|Popen|check_output)/i, description: "Subprocess execution" },
        { pattern: /(?<!#.*)eval\s*\(/i, description: "Eval execution" },
        { pattern: /(?<!#.*)exec\s*\(/i, description: "Exec execution" },
        { pattern: /shutil\.rmtree\s*\(\s*['"]\//i, description: "Directory deletion from root" },
        { pattern: /os\.(remove|unlink)\s*\(\s*['"]\//i, description: "File deletion from root" },
        { pattern: /open\s*\(\s*['"]\/etc\//i, description: "System file access (/etc)" },
        { pattern: /open\s*\(\s*['"]\/proc\//i, description: "Proc file access" },
        { pattern: /__import__\s*\(\s*['"]os['"]\s*\)/i, description: "Dynamic os import" },
        { pattern: /socket\.socket\s*\(/i, description: "Raw socket creation" },
        { pattern: /while\s+True\s*:\s*$/m, description: "Potential infinite loop without break" },
    ],

    // JavaScript/TypeScript patterns (applied to .js/.ts/.jsx/.tsx files)
    javascript: [
        { pattern: /(?<!\/\/.*)eval\s*\(/i, description: "Eval execution" },
        { pattern: /new\s+Function\s*\(\s*['"].*return/i, description: "Dynamic function creation" },
        { pattern: /require\s*\(\s*['"]child_process['"]\s*\)/i, description: "Child process import" },
        { pattern: /require\s*\(\s*['"]fs['"]\s*\).*unlinkSync\s*\(\s*['"]\//i, description: "File deletion from root" },
        { pattern: /process\.exit\s*\(/i, description: "Process termination" },
        { pattern: /while\s*\(\s*true\s*\)\s*\{(?![\s\S]*break)/i, description: "Potential infinite loop" },
    ],

    // Sensitive file paths (applied to ALL file operations)
    paths: [
        { pattern: /^\.env$/i, description: "Environment file (.env)" },
        { pattern: /\.env\.(local|production|development)$/i, description: "Environment file variant" },
        { pattern: /\.pem$/i, description: "Certificate/key file" },
        { pattern: /id_rsa/i, description: "SSH private key" },
        { pattern: /id_ed25519/i, description: "SSH private key (ed25519)" },
        { pattern: /\.aws\/credentials/i, description: "AWS credentials" },
        { pattern: /\.ssh\/config/i, description: "SSH config" },
        { pattern: /\.netrc$/i, description: "Netrc credentials" },
        { pattern: /\.npmrc$/i, description: "NPM credentials" },
        { pattern: /\.pypirc$/i, description: "PyPI credentials" },
    ]
};

/**
 * Check if content contains any blocked patterns
 * @param content - The content to check
 * @param type - The type of content ('shell', 'python', 'javascript')
 * @returns { safe: boolean, violations: string[] }
 */
export function checkContentSafety(
    content: string,
    type: 'shell' | 'python' | 'javascript'
): { safe: boolean; violations: string[] } {
    const patterns = BLOCKED_PATTERNS[type] || [];
    const violations: string[] = [];

    for (const { pattern, description } of patterns) {
        if (pattern.test(content)) {
            violations.push(description);
        }
    }

    return { safe: violations.length === 0, violations };
}

/**
 * Check if a file path is for a sensitive file
 * @param filePath - The file path to check
 * @returns { safe: boolean, violation?: string }
 */
export function checkPathSafety(filePath: string): { safe: boolean; violation?: string } {
    for (const { pattern, description } of BLOCKED_PATTERNS.paths) {
        if (pattern.test(filePath)) {
            return { safe: false, violation: description };
        }
    }
    return { safe: true };
}

/**
 * Get the content type based on file extension
 */
export function getContentTypeFromPath(filePath: string): 'python' | 'javascript' | null {
    const ext = filePath.split('.').pop()?.toLowerCase();
    if (ext === 'py') return 'python';
    if (['js', 'ts', 'jsx', 'tsx', 'mjs', 'cjs'].includes(ext || '')) return 'javascript';
    return null;
}
