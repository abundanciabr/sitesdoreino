"""Gera um projeto fechado para revisão; não acessa nem modifica a VPS."""
import base64
import ast
import hashlib
import json
import lzma
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = 'python@sha256:2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8'
ACCESS = '/usr/local/lib/meshcraft-acessos'
PROJECT = 'meshcraft-leitura-ed31-20261014'
class WithoutDocstrings(ast.NodeTransformer):
    def visit(self, node):
        node = super().visit(node)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                node.body.pop(0)
        return node


sources = {name: (HERE / name).read_text(encoding='utf-8') for name in ('leitura.py', 'instalar.py')}
files = {name: ast.unparse(WithoutDocstrings().visit(ast.parse(value))) + '\n'
         for name, value in sources.items()}
(HERE / 'pacote').mkdir(exist_ok=True)
for name, value in files.items():
    (HERE / 'pacote' / name).write_text(value, encoding='utf-8', newline='\n')
raw = json.dumps(files, ensure_ascii=True, sort_keys=True).encode()
payload = base64.b64encode(lzma.compress(raw, preset=9)).decode()
digest = hashlib.sha256(raw).hexdigest()
bootstrap = (
    'import base64,hashlib,json,lzma,pathlib,runpy,sys;'
    f'd=lzma.decompress(base64.b64decode({payload!r}));'
    f'assert hashlib.sha256(d).hexdigest()=={digest!r};'
    'f=json.loads(d);assert set(f)=={"leitura.py","instalar.py"};'
    'p=pathlib.Path("/tmp/pacote");p.mkdir(exist_ok=True);'
    '[(p/n).write_text(v,encoding="utf-8") for n,v in f.items()];'
    'sys.path.insert(0,str(p));'
    'runpy.run_path(str(p/("instalar.py" if sys.argv[1]=="instalar" else "leitura.py")),run_name="__main__")'
)
reader_raw = files['leitura.py'].encode()
reader_payload = base64.b64encode(lzma.compress(reader_raw, preset=9)).decode()
reader_bootstrap = (
    'import base64,hashlib,lzma;'
    f'd=lzma.decompress(base64.b64decode({reader_payload!r}));'
    f'assert hashlib.sha256(d).hexdigest()=={hashlib.sha256(reader_raw).hexdigest()!r};'
    'exec(compile(d,"leitura.py","exec"))'
)


def bind(source, target, ro):
    return {'type': 'bind', 'source': source, 'target': target, 'read_only': ro,
            'bind': {'create_host_path': False}}


common = {'image': IMAGE, 'user': '0:0', 'network_mode': 'none', 'read_only': True,
          'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
          'mem_limit': '128m', 'cpus': '0.25', 'pids_limit': 32,
          'tmpfs': ['/tmp:rw,nosuid,nodev,noexec,size=16m'],
          'entrypoint': ['python3', '-B', '-I', '-c', bootstrap]}
install = {'command': ['instalar'], 'restart': 'no',
           'volumes': [bind(ACCESS, ACCESS, False)]}
reader = {'command': ['ler'], 'restart': 'unless-stopped',
          'entrypoint': ['python3', '-B', '-I', '-c', reader_bootstrap],
          'cap_add': ['DAC_READ_SEARCH'],
          'depends_on': {'instalar': {'condition': 'service_completed_successfully'}},
          'volumes': [
              bind(ACCESS + '/leituras-sanitizadas', ACCESS + '/leituras-sanitizadas', False),
              bind('/var/lib/meshcraft-integrador/entregas/fases', '/entrada/fases', True),
              bind('/opt/plataforma/ensaios/selecionadas', '/entrada/selecionadas', True),
              bind('/opt/plataforma/ensaios/execucoes', '/entrada/execucoes', True),
              bind('/usr/local/lib/meshcraft-publicador/atual/provas-funil/tests',
                   '/referencia/provas-funil/tests', True)],
          'logging': {'driver': 'json-file', 'options': {'max-size': '1m', 'max-file': '1'}}}

# YAML usa um único bloco comum; o pacote não é repetido em cada serviço.
lines = ['x-executor: &executor']
lines += ['  ' + key + ': ' + json.dumps(value, ensure_ascii=True, separators=(',', ':'))
          for key, value in common.items()]
lines.append('services:')
for name, service in [('instalar', install), ('leitura', reader)]:
    lines += ['  ' + name + ':', '    <<: *executor']
    lines += ['    ' + key + ': ' + json.dumps(value, ensure_ascii=True, separators=(',', ':'))
              for key, value in service.items()]
content = '\n'.join(lines) + '\n'
first = content[:content.index('  leitura:\n')]
reader_common = dict(common, entrypoint=reader['entrypoint'])
second = 'services:\n  leitura:\n'
second += ''.join('    ' + key + ': ' + json.dumps(value, ensure_ascii=True, separators=(',', ':')) + '\n'
                  for key, value in (reader_common | reader).items() if key != 'depends_on')
second = second.replace('    depends_on: {"instalar":{"condition":"service_completed_successfully"}}\n', '')
for name, text in [('compose-instalar.yaml', first), ('compose-leitura.yaml', second)]:
    if len(text.encode()) > 8192:
        raise ValueError('compose_excede_limite_da_hospedagem_' + name)
    (HERE / name).write_text(text, encoding='utf-8', newline='\n')
manifest = {
    'estado': 'artefato_gerado_instalacao_conferida_separadamente', 'projeto': PROJECT, 'pacote_sha256': digest,
    'compose_sha256': {'instalar': hashlib.sha256(first.encode()).hexdigest(), 'leitura': hashlib.sha256(second.encode()).hexdigest()},
    'compose_bytes': {'instalar': len(first.encode()), 'leitura': len(second.encode())},
    'arquivos': {name: hashlib.sha256(value.encode()).hexdigest() for name, value in files.items()},
    'fontes_com_comentarios': {name: hashlib.sha256(value.encode()).hexdigest() for name, value in sources.items()},
    'imagem': IMAGE, 'entrega': 'ed31b0c03f97',
    'arquivos_existentes_alterados': [ACCESS + '/robo_comando.py', ACCESS + '/operacao_contexto.py'],
    'modulo_novo': ACCESS + '/leitura_sanitizada.py',
    'backup': ACCESS + '/backup-leitura-DATA-UTC',
    'servico_novo': 'leitura: consulta a cada 30 segundos, sem rede ou portas',
    'limite_historico': 'Lê a tentativa selecionada atual; não monta tentativas legadas sem seletor',
    'limites': ['Sem console ou shell livre', 'Sem socket Docker', 'Sem chaves ou credenciais',
               'Sem bancos ou restauração de bancos', 'Sem alteração do publicador ou do Mercado Pago',
               'Sem reinício de serviços existentes', 'Sem alteração dos projetos plataforma e revisor'],
    'autorizacao_recebida': 'Instalacao restrita pelo Gerenciador Docker e DAC_READ_SEARCH para o leitor, confirmadas pelo mantenedor em 14/10/2026',
}
(HERE / 'manifesto.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'estado': manifest['estado'], 'compose_bytes': manifest['compose_bytes'],
                  'pacote_sha256': digest, 'projeto': PROJECT}))
