"""Fila da ferramenta; cada projeto entra em um Blender isolado, sem rede."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT=Path('/opt/plataforma/encomendas-arquivos/marketplace/diagnosticos-texturas')
CODE=Path(__file__).resolve().parent
BLENDER=Path('/opt/plataforma/diagnostico-texturas/blender-4.5.9-linux-x64')
IMAGE='sha256:e067accf6a9183c27f66c7181fe27659dba607d7f79a285acb08cb2f913b4a9c'


def own(path,owner):
    os.chown(path,owner.st_uid,owner.st_gid)
    path.chmod(0o700 if path.is_dir() else 0o600)


def save(path,data,owner):
    temp=path.with_suffix('.parcial')
    temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    own(temp,owner)
    temp.replace(path)


def examine(directory):
    owner=directory.stat()
    name='meshcraft-texturas-'+directory.name
    state=directory/'estado.json'
    try:
        request=json.loads((directory/'pedido.json').read_text())
        source=directory/'entrada.blend'
        if (request.get('id')!=directory.name or source.is_symlink() or source.stat().st_size>64*1024*1024):
            raise ValueError('O arquivo não pôde ser conferido. O original foi preservado.')
        with source.open('rb') as stream:
            if hashlib.file_digest(stream,'sha256').hexdigest()!=request.get('sha256'):
                raise ValueError('O conteúdo mudou desde o envio. Envie uma nova cópia para analisar.')
        save(state,{'estado':'examinando'},owner)
        subprocess.run(['docker','stop','-t','1',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        output=directory/'saida'
        output.mkdir(mode=0o700,exist_ok=True)
        own(output,owner)
        with tempfile.TemporaryDirectory(prefix='leitura-',dir=ROOT) as temporary:
            stage=Path(temporary)/'saida'
            stage.mkdir(mode=0o777)
            stage.chmod(0o777)
            args=['docker','run','--rm','--name',name,'--network','none','--read-only',
                  '--cap-drop','ALL','--security-opt','no-new-privileges','--user','65534:65534',
                  '--memory','1536m','--memory-swap','1536m','--cpus','1.5','--pids-limit','64',
                  '--ulimit','nofile=128:128','--ulimit','fsize=67108864:67108864',
                  '--tmpfs','/tmp:rw,noexec,nosuid,size=512m','-e','HOME=/tmp',
                  '-e','OMP_NUM_THREADS=2','-e','OPENBLAS_NUM_THREADS=1',
                  '--mount','type=bind,src='+str(source)+',dst=/entrada.blend,readonly',
                  '--mount','type=bind,src='+str(stage)+',dst=/saida',
                  '--mount','type=bind,src='+str(CODE)+',dst=/ferramenta,readonly',
                  '--mount','type=bind,src='+str(BLENDER)+',dst=/blender,readonly',
                  '--entrypoint','/blender/blender',IMAGE,'--background','--factory-startup','--disable-autoexec',
                  '--threads','2','--python-exit-code','2','--python','/ferramenta/examinar_blender.py',
                  '--','/entrada.blend','/saida']
            timed_out=False
            try:
                subprocess.run(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240)
            except subprocess.TimeoutExpired:
                timed_out=True
            finally:
                subprocess.run(['docker','stop','-t','1',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            result=stage/'resultado.json'
            if result.is_symlink() or not result.is_file() or result.stat().st_size>8*1024*1024:
                raise ValueError('O Blender não conseguiu concluir a leitura deste projeto. Confira a versão do arquivo e tente uma cópia menor com as imagens incluídas.')
            report=json.loads(result.read_text(encoding='utf-8'))
            if report.get('estado')!='concluida':
                raise ValueError(report.get('falha','O Blender não conseguiu examinar este projeto.'))
            if timed_out:
                report.setdefault('limites',[]).append('As medidas foram extraídas, mas a geração das vistas atingiu o tempo disponível.')
            for file in stage.iterdir():
                if not re.fullmatch(r'(frontal|perspectiva)\.png|uv-[0-9]{1,6}\.svg',file.name):
                    continue
                if file.is_symlink() or not file.is_file() or file.stat().st_size>8*1024*1024:
                    continue
                (output/file.name).write_bytes(file.read_bytes())
                own(output/file.name,owner)
            save(output/'resultado.json',report,owner)
        save(state,{'estado':'concluida'},owner)
    except Exception as exc:
        message=str(exc) if isinstance(exc,ValueError) else 'A leitura foi interrompida. O projeto original continua preservado; você pode enviar uma cópia para tentar novamente.'
        save(state,{'estado':'falha','falha':message},owner)


def main():
    ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
    with (ROOT/'.worker.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        while True:
            for job in sorted(ROOT.glob('*/pedido.json'),key=lambda p:p.stat().st_mtime):
                if job.is_symlink() or not re.fullmatch('[a-f0-9]{32}',job.parent.name):continue
                try:state=json.loads((job.parent/'estado.json').read_text()).get('estado')
                except (OSError,ValueError):state='aguardando'
                if state not in ('concluida','falha'):examine(job.parent)
            time.sleep(3)


if __name__=='__main__':main()
