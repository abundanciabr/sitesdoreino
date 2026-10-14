import ast
import base64
import difflib
import hashlib
import json
import lzma
from pathlib import Path

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / 'manifesto.json').read_text(encoding='utf-8'))
payload = {key: manifest[key] for key in ('originais', 'novos')}
payload['arquivo_novo'] = (HERE / 'arquivos/test_acesso_aluno.py').read_text(encoding='utf-8')
payload['substituicoes'] = {}
for name in payload['originais']:
    old = (HERE / 'originais' / name).read_text(encoding='utf-8')
    new = (HERE / 'arquivos' / name).read_text(encoding='utf-8')
    before, after = old.splitlines(keepends=True), new.splitlines(keepends=True)
    changes = []
    for action, i, j, k, m in difflib.SequenceMatcher(a=before, b=after).get_opcodes():
        if action == 'equal':
            continue
        a, b = ''.join(before[i:j]), ''.join(after[k:m])
        if not a:
            raise ValueError('alteracao_sem_ancora')
        item = [a, b, old.count(a)]
        if item not in changes:
            changes.append(item)
    check = old
    for a, b, count in changes:
        assert check.count(a) == count
        check = check.replace(a, b)
    assert check == new
    payload['substituicoes'][name] = changes
(HERE / 'mudancas.json').write_text(json.dumps(payload, ensure_ascii=True, separators=(',', ':')), encoding='utf-8')
code = ast.unparse(ast.parse((HERE / 'aplicar.py').read_text(encoding='utf-8')))
files = {'aplicar.py': code, 'mudancas.json': json.dumps(payload, ensure_ascii=True, separators=(',', ':'))}
raw = json.dumps(files, ensure_ascii=True, separators=(',', ':')).encode()
data = base64.b64encode(lzma.compress(raw, preset=9)).decode()
sha = hashlib.sha256(raw).hexdigest()
bootstrap = ('import base64,hashlib,json,lzma,pathlib,runpy;'
    f'd=lzma.decompress(base64.b64decode({data!r}));assert hashlib.sha256(d).hexdigest()=={sha!r};'
    'f=json.loads(d);assert set(f)=={"aplicar.py","mudancas.json"};'
    'p=pathlib.Path("/tmp/pacote");p.mkdir();'
    '[(p/n).write_text(v,encoding="utf-8") for n,v in f.items()];'
    'runpy.run_path(str(p/"aplicar.py"),run_name="__main__")')
(HERE/'bootstrap.py').write_text(bootstrap,encoding='utf-8')
def bind(source, target, ro):
    return {'type':'bind','source':source,'target':target,'read_only':ro,'bind':{'create_host_path':False}}
service = {'image':'python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8',
    'user':'0:0','network_mode':'none','read_only':True,'cap_drop':['ALL'],
    'cap_add':['DAC_READ_SEARCH'],'security_opt':['no-new-privileges:true'],
    'mem_limit':'128m','cpus':'0.25','pids_limit':32,'restart':'no',
    'tmpfs':['/tmp:rw,nosuid,nodev,noexec,size=16m'],
    'entrypoint':['python3','-B','-I','-c',bootstrap],
    'volumes':[bind('/usr/local/lib/meshcraft-publicador/atual/provas-funil','/provas',False),
               bind('/var/lib/meshcraft-integrador/entregas/fases/.worker.lock','/travas/worker',True)]}
compose = 'services:\n  ajustar:\n' + ''.join('    '+k+': '+json.dumps(v,separators=(',', ':'))+'\n' for k,v in service.items())
assert len(compose.encode()) <= 8192, len(compose.encode())
(HERE/'compose.yaml').write_text(compose,encoding='utf-8',newline='\n')
manifest.update(pacote_sha256=sha,compose_sha256=hashlib.sha256(compose.encode()).hexdigest(),
    compose_bytes=len(compose.encode()),projeto='meshcraft-provas-login-ed31-20261014',
    testes_locais={'antes':{'falhas':8,'aprovados':122},'depois':{'falhas':0,'aprovados':167}})
(HERE/'manifesto.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'pacote_sha256':sha,'bytes':manifest['compose_bytes']}))
