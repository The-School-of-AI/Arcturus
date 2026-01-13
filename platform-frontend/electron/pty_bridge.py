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
            # Make sure we don't block indefinitely
            while True:
                # Watch stdin (from Electron) and master_fd (from Shell)
                read_fds, _, _ = select.select([sys.stdin, master_fd], [], [])
                
                if sys.stdin in read_fds:
                    # Input from Electron -> Write to Shell
                    try:
                        # Read binary data from stdin
                        d = os.read(sys.stdin.fileno(), 1024)
                        if not d: 
                            break # EOF from Electron
                        os.write(master_fd, d)
                    except OSError:
                        break

                if master_fd in read_fds:
                    # Output from Shell -> Write to Electron
                    try:
                        o = os.read(master_fd, 1024)
                        if not o: 
                            break # Shell closed
                        sys.stdout.buffer.write(o)
                        sys.stdout.buffer.flush()
                    except OSError:
                        break
                        
        except Exception as e:
            sys.stderr.write(f"Bridge Error: {e}\n")
        finally:
            os.close(master_fd)
            # Reap child
            os.waitpid(pid, 0)

if __name__ == "__main__":
    main()
