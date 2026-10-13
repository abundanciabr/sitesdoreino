"""Compara somente a pesquisa aprovada com uma referência externa à candidata."""
import ast
import hashlib
import json
from pathlib import Path

INTEIROS = {
    'cursos': (
        'apps/core/satisfacao.py', 'apps/core/satisfacao_contexto.py',
        'apps/core/templates/cursos/satisfacao.html',
        'apps/core/templatetags/botoes_admin.py',
    ),
    'quiz': tuple('apps/quiz/' + nome + '.py' for nome in (
        'nps', 'nps_revisado', 'nps_previa', 'nps_respondentes', 'nps_acoes', 'participacao')),
}
MODELOS = ('NPSConfig', 'NPSTentativa', 'NPSAtendimento', 'NPSRevisao', 'NPSParticipacao')
POLITICA = Path(__file__).resolve().parents[1] / 'satisfacao/politica.json'


class IntegridadePesquisaErro(ValueError):
    pass


def seguro(raiz, nome):
    caminho = Path(raiz)
    if caminho.is_symlink() or not caminho.is_dir():
        raise IntegridadePesquisaErro('pesquisa: raiz ausente ou inválida')
    for parte in nome.split('/'):
        caminho = caminho / parte
        if caminho.is_symlink():
            raise IntegridadePesquisaErro('pesquisa: link simbólico em ' + nome)
    if not caminho.is_file():
        raise IntegridadePesquisaErro('pesquisa: arquivo ausente: ' + nome)
    return caminho


def arvore(raiz, nome, servico):
    texto = seguro(raiz, nome).read_text(encoding='utf-8')
    texto = texto.replace('modules.' + servico + '.apps.', 'apps.')
    texto = texto.replace('modules.' + servico + '.config.', 'config.')
    modulo = ast.parse(texto)
    if servico == 'quiz' and (nome == 'apps/quiz/models.py' or '/migrations/' in nome):
        for nodo in ast.walk(modulo):
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str):
                if nodo.value.startswith('quiz_quiz.'):
                    nodo.value = nodo.value.replace('quiz_quiz.', 'quiz.', 1)
                elif nodo.value == 'quiz_quiz':
                    nodo.value = 'quiz'
        for classe in modulo.body if nome.endswith('/models.py') else ():
            if not isinstance(classe, ast.ClassDef) or classe.name not in MODELOS:
                continue
            meta = next((n for n in classe.body if isinstance(n, ast.ClassDef) and n.name == 'Meta'), None)
            if meta is None:
                meta = ast.ClassDef(name='Meta', bases=[], keywords=[], body=[], decorator_list=[])
                classe.body.append(meta)
            if not any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name)
                    and t.id == 'db_table' for t in n.targets) for n in meta.body):
                meta.body.extend(ast.parse('db_table = ' + repr('quiz_' + classe.name.lower())).body)
        if '/migrations/' in nome:
            for n in ast.walk(modulo):
                if not isinstance(n, ast.Call) or not isinstance(n.func, ast.Attribute) or n.func.attr != 'CreateModel':
                    continue
                modelo = next((k.value.value for k in n.keywords if k.arg == 'name'
                    and isinstance(k.value, ast.Constant)), None)
                opcoes = next((k for k in n.keywords if k.arg == 'options'), None)
                if not modelo:
                    continue
                if opcoes is None:
                    opcoes = ast.keyword(arg='options', value=ast.Dict(keys=[], values=[]))
                    n.keywords.append(opcoes)
                if isinstance(opcoes.value, ast.Dict) and not any(isinstance(k, ast.Constant)
                        and k.value == 'db_table' for k in opcoes.value.keys):
                    opcoes.value.keys.append(ast.Constant('db_table'))
                    opcoes.value.values.append(ast.Constant('quiz_' + modelo.lower()))
    return modulo


def dump(nodo):
    # Python 3.12 acrescenta este campo vazio a funções/classes comuns.
    # Parâmetros genéricos reais continuam representados e protegidos.
    for n in ast.walk(nodo):
        if getattr(n, 'type_params', None) == []:
            del n.type_params
    return ast.dump(nodo, include_attributes=False)


def resumo(raiz, *, pacote=False):
    valores = {}
    raiz = Path(raiz)
    for diretorio in (raiz, raiz / ('modules' if pacote else 'services')):
        if diretorio.is_symlink() or not diretorio.is_dir():
            raise IntegridadePesquisaErro('pesquisa: diretório ausente ou inválido')

    def guardar(chave, dados):
        if not isinstance(dados, bytes):
            dados = json.dumps(dados, ensure_ascii=False, sort_keys=True).encode()
        valores[chave] = hashlib.sha256(dados).hexdigest()

    def pasta(servico):
        return Path(raiz) / ('modules' if pacote else 'services') / servico

    for servico, nomes in INTEIROS.items():
        for nome in nomes:
            dados = dump(arvore(pasta(servico), nome, servico)) if nome.endswith('.py') else seguro(
                pasta(servico), nome).read_bytes().replace(b'\r\n', b'\n')
            guardar(servico + '/' + nome, dados)
    modulo = arvore(pasta('quiz'), 'apps/quiz/models.py', 'quiz')
    for nome in MODELOS:
        encontrados = [n for n in modulo.body if isinstance(n, ast.ClassDef) and n.name == nome]
        if len(encontrados) != 1:
            raise IntegridadePesquisaErro('pesquisa: modelo ausente ou duplicado: ' + nome)
        guardar('quiz/modelo:' + nome, dump(encontrados[0]))
    migrations = pasta('quiz') / 'apps/quiz/migrations'
    if migrations.is_symlink() or not migrations.is_dir():
        raise IntegridadePesquisaErro('pesquisa: migrações ausentes ou inválidas')
    for caminho in sorted(migrations.glob('*.py')):
        texto = seguro(pasta('quiz'), 'apps/quiz/migrations/' + caminho.name).read_text(encoding='utf-8').lower()
        if any(m in texto for m in ('npsconfig', 'npstentativa', 'npsatendimento', 'npsrevisao', 'npsparticipacao', 'nps_')):
            nome = 'apps/quiz/migrations/' + caminho.name
            guardar('quiz/' + nome, dump(arvore(pasta('quiz'), nome, 'quiz')))
    modulo = arvore(pasta('quiz'), 'apps/quiz/editor.py', 'quiz')
    autorizacao = [n for n in modulo.body if isinstance(n, ast.FunctionDef) and n.name == '_authorized']
    if len(autorizacao) != 1:
        raise IntegridadePesquisaErro('pesquisa: autorização ausente ou duplicada')
    guardar('quiz/autorizacao', dump(autorizacao[0]))
    for servico in ('cursos', 'quiz'):
        modulo = arvore(pasta(servico), 'config/urls.py', servico)
        prefixos = ('satisfacao/', 'api/cursos/satisfacao-contexto') if servico == 'cursos' else ('interno/nps/',)
        rotas = [n for n in ast.walk(modulo) if isinstance(n, ast.Call) and n.args
            and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
            and n.args[0].value.lstrip('^').startswith(prefixos)]
        # Inclui os vínculos dos nomes chamados pelas rotas, impedindo trocar o handler por outro import.
        nomes = {n.id for rota in rotas for n in ast.walk(rota) if isinstance(n, ast.Name)} - {'path', 're_path'}
        vinculos = []
        for n in modulo.body:
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                selecionados = [a for a in n.names if (a.asname or a.name.split('.')[0]) in nomes]
                if selecionados:
                    copia = ast.ImportFrom(module=n.module, names=selecionados, level=n.level) if isinstance(
                        n, ast.ImportFrom) else ast.Import(names=selecionados)
                    vinculos.append(dump(copia))
            elif isinstance(n, (ast.Assign, ast.FunctionDef, ast.ClassDef)):
                definidos = {getattr(n, 'name', None)} | {t.id for t in getattr(n, 'targets', []) if isinstance(t, ast.Name)}
                if definidos & nomes:
                    vinculos.append(dump(n))
        guardar(servico + '/rotas-pesquisa', sorted(dump(n) for n in rotas))
        guardar(servico + '/vinculos-pesquisa', sorted(vinculos))
    modulo = arvore(pasta('cursos'), 'apps/core/views.py', 'cursos')
    convites = []
    for n in ast.walk(modulo):
        if isinstance(n, ast.If) and any(isinstance(c, ast.Name) and c.id == 'pode_avaliar_curso'
                for c in ast.walk(n.test)):
            convites.append(dump(n))
        elif isinstance(n, ast.Dict):
            for chave, valor in zip(n.keys, n.values):
                if isinstance(chave, ast.Constant) and chave.value == 'url_pesquisa':
                    convites.append(dump(valor))
        elif isinstance(n, ast.ImportFrom) and n.module == 'satisfacao':
            convites.append(dump(n))
    guardar('cursos/convites-pesquisa', sorted(convites))
    for nome in ('catalogo', 'mapa'):
        texto = seguro(pasta('cursos'), 'apps/core/templates/cursos/' + nome + '.html').read_text(encoding='utf-8')
        guardar('cursos/convite-template:' + nome, [l.strip() for l in texto.splitlines()
            if 'url_pesquisa' in l or 'satisfacao' in l])
    return valores


def comparar(atual, referencia):
    if not isinstance(referencia, dict) or not referencia or any(not isinstance(v, str)
            or len(v) != 64 or any(c not in '0123456789abcdef' for c in v) for v in referencia.values()):
        raise IntegridadePesquisaErro('pesquisa: referência independente inválida')
    diferentes = sorted(k for k in set(atual) | set(referencia) if atual.get(k) != referencia.get(k))
    if diferentes:
        raise IntegridadePesquisaErro('pesquisa aprovada alterada; publicação impedida: ' + ', '.join(diferentes))


def conferir(raiz, *, pacote=False):
    if POLITICA.parent.is_symlink() or POLITICA.is_symlink() or not POLITICA.is_file():
        raise IntegridadePesquisaErro('pesquisa: referência independente ausente; publicação impedida')
    referencia = json.loads(POLITICA.read_text(encoding='utf-8'))
    comparar(resumo(raiz, pacote=pacote), referencia['resumo'])


def conferir_fontes_satisfacao(fonte):
    conferir(fonte)


def conferir_codigo_satisfacao(codigo):
    conferir(codigo, pacote=True)
