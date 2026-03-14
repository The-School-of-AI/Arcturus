import os
import sys
import threading
import subprocess

def forward_stream(src, dst):
    try:
        while True:
            data = src.read(4096)
            if not data:
                break
            dst.write(data)
            dst.flush()
    except Exception:
        pass

def main():
    # Prefer PowerShell if available, else cmd
    pwsh = os.path.join(os.environ.get('SYSTEMROOT', 'C:\\Windows'), 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe')
    if os.path.exists(pwsh):
        shell = pwsh
        args = [pwsh, '-NoLogo']
    else:
        shell = os.path.join(os.environ.get('SYSTEMROOT', 'C:\\Windows'), 'System32', 'cmd.exe')
        args = [shell]

    try:
        proc = subprocess.Popen(args,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except Exception as e:
        sys.stderr.write(f"Failed to start shell: {e}\n")
        sys.exit(1)

    t1 = threading.Thread(target=forward_stream, args=(sys.stdin.buffer, proc.stdin))
    t2 = threading.Thread(target=forward_stream, args=(proc.stdout, sys.stdout.buffer))
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()

    try:
        proc.wait()
    except KeyboardInterrupt:
        try:
            proc.terminate()
        except:
            pass

if __name__ == '__main__':
    main()
