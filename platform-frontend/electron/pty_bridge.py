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
        try:
            os.execl(shell, shell)
        except Exception as e:
            # If execl fails, we need to report it before exiting
            sys.stderr.write(f"Failed to execute shell {shell}: {e}\n")
            sys.stderr.flush()
            os._exit(1)
    else:
        # Parent process (The Bridge)
        try:
            while True:
                # Watch stdin (fd 0) and master_fd (from Shell)
                try:
                    read_fds, _, _ = select.select([0, master_fd], [], [], 1.0)
                except select.error as e:
                    if e.args[0] == signal.EINTR: continue
                    raise

                if not read_fds:
                    # Check if child is still alive
                    if os.waitpid(pid, os.WNOHANG) != (0, 0):
                        break
                    continue
                
                if 0 in read_fds:
                    # Input from Electron (stdin) -> Write to Shell (master_fd)
                    try:
                        d = os.read(0, 4096)
                        if not d: 
                            # sys.stderr.write("DEBUG: stdin EOF\n")
                            break # EOF
                        os.write(master_fd, d)
                    except (OSError, EOFError) as e:
                        sys.stderr.write(f"Bridge stdin read error: {e}\n")
                        break

                if master_fd in read_fds:
                    # Output from Shell (master_fd) -> Write to Electron (stdout)
                    try:
                        o = os.read(master_fd, 4096)
                        if not o: 
                            # sys.stderr.write("DEBUG: master_fd EOF\n")
                            break # Shell closed
                        os.write(1, o) # Write directly to stdout (fd 1)
                        sys.stdout.flush() # Ensure it's sent
                    except (OSError, EOFError) as e:
                        sys.stderr.write(f"Bridge PTY read error: {e}\n")
                        break
                        
        except Exception as e:
            sys.stderr.write(f"Bridge Loop Error: {e}\n")
            sys.stderr.flush()
        finally:
            try:
                os.close(master_fd)
            except:
                pass
            # Reap child
            try:
                os.waitpid(pid, 0)
            except:
                pass

if __name__ == "__main__":
    main()
