"""Runner watchdog: exits with its parent and never kills another task's process group."""
import json, os, pathlib, signal, subprocess, sys, time

def main():
    os.nice(10)
    plan=json.loads(pathlib.Path(sys.argv[1]).read_text());owner=os.getppid();log=pathlib.Path(plan['log']);started=time.monotonic();peak=0
    with log.open('ab',buffering=0) as stream:
        process=subprocess.Popen(plan['argv'],cwd=plan['cwd'],env=plan['env'],stdout=stream,stderr=stream)
        while process.poll() is None:
            if os.getppid()!=owner:
                os.killpg(os.getpgrp(),signal.SIGTERM);return
            # Logs bounded while streaming, never read wholesale into daemon memory.
            if log.stat().st_size>plan['maxLogBytes']:
                os.killpg(os.getpgrp(),signal.SIGTERM);return
            time.sleep(.5)
        code=process.returncode
    pathlib.Path(plan['receipt']).write_text(json.dumps({'returncode':code,'seconds':time.monotonic()-started}))
    sys.exit(0 if code==0 else 1)
if __name__=='__main__':main()
