"""Preserva a regra de /docs/ fora do código candidato à publicação."""
import ast
import hashlib
import json
from pathlib import Path

INTEIROS = (
    'apps/core/publicacao_manual_docs.py',
    'apps/core/editor_de_documentos.py',
    'apps/core/migrations/0047_docs_somente_publicacao_manual.py',
    'apps/core/templates/admin/documento_admin.html',
)
PARTES = {
    'apps/core/models.py': ('Documento',),
    'apps/core/porta.py': ('PortaAdministrativa._responder',),
    'apps/core/views.py': ('docs_publicos', 'doc_publico', 'documento_admin'),
    'apps/core/documentos.py': ('listar', '_semear'),
    'apps/core/documento_em_pagina.py': ('doc_publico_moldura',),
    'apps/core/midia.py': ('arquivo_da_semente_servir',),
}


def arvore(caminho):
    texto = caminho.read_text(encoding='utf-8').replace('modules.admin.apps.', 'apps.')
    modulo = ast.parse(texto)
    for nodo in ast.walk(modulo):
        if isinstance(nodo, ast.Constant) and nodo.value == 'admin_core':
            nodo.value = 'core'
        if isinstance(nodo, ast.ClassDef) and nodo.name == 'Documento':
            meta = next(n for n in nodo.body if isinstance(n, ast.ClassDef) and n.name == 'Meta')
            if not any(isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == 'db_table' for t in n.targets) for n in meta.body):
                meta.body.extend(ast.parse("db_table = 'core_documento'").body)
    return modulo


def resumo(raiz):
    def digest(dados):
        return hashlib.sha256(dados).hexdigest()
    valores = {}
    for nome in INTEIROS:
        caminho = raiz / nome
        if caminho.is_symlink() or not caminho.is_file():
            raise RuntimeError('docs: peça da proteção ausente: ' + nome)
        if nome.endswith('.py'):
            dados = ast.dump(arvore(caminho), include_attributes=False).encode()
        else:
            dados = caminho.read_bytes().replace(b'\r\n', b'\n')
        valores[nome] = digest(dados)
    for nome, partes in PARTES.items():
        modulo = arvore(raiz / nome)
        for parte in partes:
            nodo = modulo
            for pedaco in parte.split('.'):
                nodo = next(n for n in nodo.body if getattr(n, 'name', None) == pedaco)
            valores[nome + ':' + parte] = digest(ast.dump(nodo, include_attributes=False).encode())
    rotas = [ast.dump(n, include_attributes=False) for n in ast.walk(arvore(raiz / 'config/urls.py'))
             if isinstance(n, ast.Call) and n.args and isinstance(n.args[0], ast.Constant)
             and isinstance(n.args[0].value, str)
             and n.args[0].value.lstrip('^').startswith(('docs/', 'documentos/'))]
    valores['rotas-docs'] = digest(json.dumps(sorted(rotas)).encode())
    return valores


def conferir(raiz):
    politica = Path(__file__).resolve().parents[1] / 'docs/politica.json'
    if politica.is_symlink() or not politica.is_file():
        raise RuntimeError('docs: referência independente ausente; publicação impedida')
    referencia = json.loads(politica.read_text(encoding='utf-8'))
    atual = resumo(raiz)
    diferentes = sorted(k for k in set(atual) | set(referencia['resumo'])
                        if atual.get(k) != referencia['resumo'].get(k))
    if diferentes:
        raise RuntimeError('docs: regra manual alterada; publicação impedida: ' + ', '.join(diferentes))


def conferir_fontes_docs(fonte):
    conferir(Path(fonte) / 'services/admin')


def conferir_codigo_docs(codigo):
    conferir(Path(codigo) / 'modules/admin')
