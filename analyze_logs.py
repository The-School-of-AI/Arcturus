
import re

def analyze_failures(file_path):
    try:
        with open(file_path, 'r', encoding='utf-16') as f:
            content = f.read()
    except UnicodeError:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

    # Extract all FAILED lines
    failed_lines = re.findall(r'FAILED (tests/.*)', content)
    
    # Extract UnicodeDecodeError segments
    unicode_errors = re.findall(r'UnicodeDecodeError:.*', content)
    
    # Extract AssertionError segments related to executables
    exec_errors = re.findall(r'AssertionError: Demo script not executable:.*', content)

    print(f"Total Failures: {len(failed_lines)}")
    print(f"UnicodeDecodeErrors: {len(unicode_errors)}")
    print(f"Executable Bit Errors: {len(exec_errors)}")
    
    print("\nCategorized Failed Tests:")
    for test in failed_lines:
        print(f"- {test}")

if __name__ == "__main__":
    analyze_failures('baseline_regression_full.log')
