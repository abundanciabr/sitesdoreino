"""Prepara apenas os três ajustes de expectativas e as provas do acesso novo."""
from pathlib import Path
import ast
import hashlib
import io
import json
import subprocess
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TREE = 'a4ef3ca4768f42d7d809981b7852711d88c35901'
LOGIN = 'f1729e35a8b5d4b24a630d5ecc10bc72cb9aac27'
BASE = 'acd6c0fc546bb0c9719f14d550590b9471e64160'
HOME = 'a5cceeecc672cc5e6d8e33d61ccdee77c0c2c144'
NAMES = ('test_categorias_na_home.py', 'test_quadrinho_de_progresso.py', 'test_sessao_no_site.py')

def git_file(ref, name):
    return subprocess.check_output(['git', 'show', ref + ':services/funil/tests/' + name], cwd=ROOT)

original = {name: git_file(HOME if name == NAMES[2] else BASE, name) for name in NAMES}
changed = {name: git_file(LOGIN, name) for name in NAMES}
# Preserva a alteração posterior da home deslogada, já instalada na suíte.
changed[NAMES[2]] = changed[NAMES[2]].replace(
    b'assert \'class="sessao"\' in conteudo',
    b'assert (\'class="sessao"\' in conteudo) == (pagina != "/")', 1)
changed['test_acesso_aluno.py'] = git_file(LOGIN, 'test_acesso_aluno.py')
for name, content in changed.items():
    ast.parse(content, filename=name)
    target = HERE / 'arquivos' / name
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(content)
for name, content in original.items():
    target = HERE / 'originais' / name
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(content)
manifest = {'id': 'acesso-central-ed31-20261014', 'entrega': 'ed31b0c03f97',
    'tree_candidata': TREE, 'commit_login': LOGIN,
    'originais': {n: hashlib.sha256(v).hexdigest() for n, v in original.items()},
    'novos': {n: hashlib.sha256(v).hexdigest() for n, v in changed.items()},
    'alteracao': 'Expectativas do login central; mantém a alteração posterior da home e acrescenta as provas de matrícula, CSRF e não duplicação.',
    'estado': 'preparado_nao_instalado'}
(HERE / 'manifesto.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
fixture = ROOT / 'output/acesso-login-20261014/prova-referencia-externa'
fixture.mkdir(exist_ok=True)
data = subprocess.check_output(['git', 'archive', '--format=zip', TREE, 'services/funil', 'packages/site_errors'], cwd=ROOT)
with zipfile.ZipFile(io.BytesIO(data)) as archive:
    for member in archive.infolist():
        target = (fixture / member.filename).resolve()
        target.relative_to(fixture.resolve())
    archive.extractall(fixture)
for name, content in original.items():
    (fixture / 'services/funil/tests' / name).write_bytes(content)
print(json.dumps(manifest, ensure_ascii=False))
