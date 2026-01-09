import re

def parse_violations(file_path):
    violations = {}
    with open(file_path, 'r') as f:
        for line in f:
            parts = line.strip().split(':', 1)
            if len(parts) == 2:
                filename, content = parts
                filename = filename.strip()
                if filename not in violations:
                    violations[filename] = []
                violations[filename].append(content.strip())
    return violations

def generate_report():
    all_files = []
    with open('all_tsx_files.txt', 'r') as f:
        all_files = [line.strip() for line in f if line.strip()]

    violations_map = parse_violations('css_violations.txt')

    report_lines = []
    report_lines.append("# CSS Single Source of Truth Audit Report")
    report_lines.append("")
    report_lines.append(f"**Total Files Scanned:** {len(all_files)}")
    report_lines.append(f"**Files with Violations:** {len(violations_map)}")
    report_lines.append("")
    report_lines.append("## Compliance Status")
    report_lines.append("")
    report_lines.append("| Status | File | Violations (Sample) |")
    report_lines.append("| :--- | :--- | :--- |")

    # Sort files: Failures first
    sorted_files = sorted(all_files, key=lambda x: (0 if x in violations_map else 1, x))

    for filename in sorted_files:
        if filename in violations_map:
            status = "❌ FAIL"
            # Get unique violations, limited to 3
            unique_v = list(set(violations_map[filename]))[:3]
            v_str = "<br>".join([f"`{v[:40]}...`" if len(v) > 40 else f"`{v}`" for v in unique_v])
            if len(violations_map[filename]) > 3:
                v_str += f"<br>...and {len(violations_map[filename])-3} more"
            report_lines.append(f"| {status} | `{filename}` | {v_str} |")
        else:
            status = "✅ PASS"
            report_lines.append(f"| {status} | `{filename}` | - |")

    output_path = '/Users/rohanshravan/.gemini/antigravity/brain/8e9812b2-5702-451d-989e-36dc3e5ff6c4/css_audit_report.md'
    with open(output_path, 'w') as f:
        f.write('\n'.join(report_lines))
    
    print(f"Report generated at {output_path}")

if __name__ == "__main__":
    generate_report()
