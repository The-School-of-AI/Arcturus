import os
import pty
import sys
import select
import fcntl
import struct
import termios
import signal

# Handle window size changes if possible, or signals
def signal_handler(signum, frame):
    pass

signal.signal(signal.SIGWINCH, signal_handler)

def main():
    # shell = os.environ.get('SHELL', '/bin/bash')
    # Default to zsh on Mac if available, else bash
    shell = '/bin/zsh' if os.path.exists('/bin/zsh') else '/bin/bash'
    
    # Create PTY
    # pty.fork() works on POSIX (Mac/Linux)
    try:
        pid, master_fd = pty.fork()
    except OSError as e:
        sys.stderr.write(f"Error forking PTY: {e}\n")
        return

    if pid == 0:
        # Child process (The Shell)
        # Inherits the slave end of the PTY
        # We can set environment variables here if needed
        os.execl(shell, shell)
    else:
        # Parent process (The Bridge)
        # master_fd is the file descriptor to read/write to the shell
        
        try:
            # Set stdin to non-blocking
            # fcntl.fcntl(sys.stdin, fcntl.F_SETFL, os.O_NONBLOCK)
            
            while True:
                # Watch stdin (fd 0) and master_fd (from Shell)
                read_fds, _, _ = select.select([0, master_fd], [], [])
                
                if 0 in read_fds:
                    # Input from Electron (stdin) -> Write to Shell (master_fd)
                    try:
                        d = os.read(0, 4096)
                        if not d: 
                            break # EOF
                        os.write(master_fd, d)
                    except (OSError, EOFError):
                        break

                if master_fd in read_fds:
                    # Output from Shell (master_fd) -> Write to Electron (stdout)
                    try:
                        o = os.read(master_fd, 4096)
                        if not o: 
                            break # Shell closed
                        os.write(1, o) # Write directly to stdout (fd 1)
                    except (OSError, EOFError):
                        break
                        
        except Exception as e:
            sys.stderr.write(f"Bridge Error: {e}\n")
            sys.stderr.flush()
        finally:
            os.close(master_fd)
            # Reap child
            os.waitpid(pid, 0)

if __name__ == "__main__":
    main()
