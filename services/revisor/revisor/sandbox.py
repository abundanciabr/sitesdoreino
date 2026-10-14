"""Linux isolation. No permissive fallback when namespaces are unavailable."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile


TIMEOUT = 60
MEMORY_BYTES = 1536 * 1024 * 1024
OUTPUT_BYTES = 2_000_000
MAX_UPLOAD = 50_000_000
LINUX = sys.platform == 'linux'


def accepted(filename, size):
    if Path(filename).suffix.lower() not in {'.fbx','.glb'}:
        raise ValueError('unsupported_type')
    if not 0 < size <= MAX_UPLOAD:
        raise ValueError('too_large')


def command(directory, profile, scale, *, app='/opt/revisor', blender='/usr/bin/blender'):
    directory = Path(directory).resolve()
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError('invalid_temporary')
    directory.joinpath('request.json').write_text(json.dumps({'profile':profile,'studs_per_unit':scale}), 'utf-8')
    args = ['bwrap','--unshare-all','--die-with-parent','--new-session','--clearenv',
            '--ro-bind','/usr','/usr','--ro-bind','/lib','/lib',
            '--ro-bind',app,app,'--bind',str(directory),'/work',
            '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
            '--setenv','HOME','/tmp','--setenv','PYTHONPATH',app,
            '--setenv','PYTHONDONTWRITEBYTECODE','1','--setenv','OMP_NUM_THREADS','1',
            '--chdir','/work']
    if Path('/lib64').exists():
        args.extend(['--ro-bind','/lib64','/lib64'])
    if Path('/etc/ld.so.cache').exists():
        args.extend(['--ro-bind','/etc/ld.so.cache','/etc/ld.so.cache'])
    args += ['--', blender, '--background', '--factory-startup', '--disable-autoexec',
             '--threads','1','--python-exit-code','23', '--python',app+'/revisor/importer_blender.py',
             '--','/work/input'+directory.joinpath('suffix').read_text('ascii'), '/work/request.json','/work/result.json']
    return args


def resource_limits():
    import resource
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES,MEMORY_BYTES))
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_BYTES,OUTPUT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT,TIMEOUT))
    resource.setrlimit(resource.RLIMIT_CORE, (0,0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128,128))


def analyze(stream, filename, size, profile, scale=None, *, runner=subprocess.Popen, timeout=TIMEOUT,
            temporary_root=None, app='/opt/revisor', blender='/usr/bin/blender'):
    accepted(filename, size)  # Reject format/size before the first read.
    if not LINUX:
        raise RuntimeError('linux_isolation_required')
    suffix = Path(filename).suffix.lower()
    with tempfile.TemporaryDirectory(prefix='revisor-', dir=temporary_root) as temporary:
        directory = Path(temporary)
        directory.joinpath('suffix').write_text(suffix, 'ascii')
        copied = 0
        with directory.joinpath('input'+suffix).open('wb') as output:
            while chunk := stream.read(65536):
                copied += len(chunk)
                if copied > MAX_UPLOAD or copied > size:
                    raise ValueError('too_large')
                output.write(chunk)
        if copied != size:
            return {'state':'unreadable', 'reason':'cannot_read_file'}
        process = None
        try:
            process = runner(command(directory, profile, scale, app=app, blender=blender),
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             env={}, start_new_session=True, preexec_fn=resource_limits)
            process.wait(timeout=timeout)
            result_path = directory/'result.json'
            if process.returncode != 0 or not result_path.is_file() or result_path.stat().st_size > OUTPUT_BYTES:
                return {'state':'unreadable','reason':'cannot_read_file'}
            result = json.loads(result_path.read_text('utf-8'))
            if result.get('state') not in {'completed','unreadable'}:
                raise ValueError('invalid_parser_output')
            return result
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return {'state':'unreadable','reason':'cannot_read_file'}
        finally:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
