"""Dependências incorporadas por outro ID: Git real e publicação comprovada."""
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import entregas
import ponte_entregas
from integrador_servico import Servico, Estados
from ponte_entregas import Autoridade, ErroPonte
from testes_integrador_servico import _git, I1, I2, C2, entrega, IntegradorFalso, PonteFalsa


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    origem, destino = tmp_path / 'integrador', tmp_path / 'plataforma'
    repos = [origem / 'codigo/repo.git', destino / 'codigo/repo.git', tmp_path / 'publico.git']
    for repo in repos:
        repo.parent.mkdir(parents=True, exist_ok=True)
        _git('init', '--bare', repo)
    trabalho = tmp_path / 'trabalho'
    _git('init', trabalho)

    def commit(nome, texto):
        path = trabalho / nome
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(texto, encoding='utf-8')
        _git('-C', trabalho, 'add', '.')
        _git('-C', trabalho, '-c', 'user.name=Teste', '-c', 'user.email=teste@localhost',
             'commit', '-m', nome)
        return _git('-C', trabalho, 'rev-parse', 'HEAD')

    base = commit('site.txt', 'antes')
    original = commit('site.txt', 'quiz interativo')
    _git('-C', trabalho, 'push', repos[0], 'HEAD:refs/heads/original')
    # Mesmo conteúdo entrou por um commit diferente, sem ancestralidade do original.
    _git('-C', trabalho, 'checkout', '-b', 'incorporada', base)
    commit('outro.txt', 'trabalho independente')
    ativa = commit('site.txt', 'quiz interativo')
    for repo in repos:
        _git('-C', trabalho, 'push', repo, 'HEAD:refs/heads/main')
    reg = {'id': I1, 'commit': original, 'base': base, 'estado': entregas.NA_MAIN,
           'candidata': None, 'promovida_candidata': None}
    registros = origem / 'entregas'
    registros.mkdir()
    registro = registros / (I1 + '.json')
    registro.write_text(json.dumps(reg), encoding='utf-8')
    publicacoes = destino / 'publicacoes'
    publicacoes.mkdir()
    (publicacoes / '.ativacao.lock').touch()
    pacote = {'id': 'e' * 64}
    journal = {'atual': ativa, 'servicos': ['aplicacao'],
               'aprovada': {'sha': ativa, 'pacote': pacote}}
    arquivo = publicacoes / 'aplicacao.json'
    arquivo.write_text(json.dumps(journal), encoding='utf-8')
    monkeypatch.setattr(ponte_entregas, 'REPO_PUBLICO', str(repos[2]))
    autoridade = Autoridade(origem, destino, tmp_path / 'ferramentas')
    provas = []

    def prova(plataforma, sha, ferramentas, celula, **kw):
        provas.append(sha)
        assert sha != original  # Não inventa ensaio ou ativação para o ID original.
        return {'identidade': 'd' * 64, 'candidata': sha, 'celula': celula,
                'pacote_publicador': pacote}

    monkeypatch.setattr(autoridade, '_ensaio', lambda: SimpleNamespace(
        RecusaEnsaio=RuntimeError, verificar_prova_historica=prova))
    executar = ponte_entregas.subprocess.run
    chamadas = []
    saude = {'Running': True, 'Health': {'Status': 'healthy'}}

    def run(comando, *args, **kwargs):
        chamadas.append(comando)
        if comando[-1] == 'conferir-atual':
            return SimpleNamespace(returncode=0)
        if comando[:4] == ['docker', 'compose', 'ps', '-q']:
            return SimpleNamespace(returncode=0, stdout='container-aprovado\n')
        if comando[:2] == ['docker', 'inspect']:
            return SimpleNamespace(returncode=0, stdout=json.dumps(saude))
        return executar(comando, *args, **kwargs)

    monkeypatch.setattr(ponte_entregas.subprocess, 'run', run)
    integ = SimpleNamespace(ler=lambda id_: reg if id_ == I1 else None,
        git=lambda *args, **kw: executar(['git', '--git-dir', str(repos[0]), *args],
                                        capture_output=True, text=True, check=kw.get('check', False)))
    worker = Servico(integ, autoridade, Estados(tmp_path / 'fases'))
    return SimpleNamespace(**locals())


def test_outro_id_ativo_libera_sem_fabricar_ativacao_original(cenario):
    c = cenario
    estado = {'id': I2, 'dependencias_comprovadas': {'antiga': {}}}
    assert c.worker._dependencias_ativas({'depende_de': [I1]}, estado) == ([], False)
    prova = estado['dependencias_comprovadas'][I1]['celulas']['aplicacao']
    assert prova['sha_aprovada'] == c.ativa
    assert prova['arquivos_conferidos'] == 1
    assert c.worker.estados.ler(I1) is None
    assert json.loads(c.registro.read_text()) == c.reg
    assert not any('update-ref' in cmd or 'fetch' in cmd for cmd in c.chamadas)


def test_conteudo_so_na_main_nao_libera(cenario):
    c = cenario
    c.journal.update(atual=c.base, aprovada={'sha': c.base, 'pacote': c.pacote})
    c.arquivo.write_text(json.dumps(c.journal))
    assert c.worker._dependencias_ativas({'depende_de': [I1]}) == ([I1], False)


def test_reversao_posterior_nao_libera_e_descarta_prova_anterior(cenario):
    c = cenario
    estado = {}
    assert c.worker._dependencias_ativas({'depende_de': [I1]}, estado) == ([], False)
    reversao = c.commit('site.txt', 'antes')
    for repo in c.repos:
        _git('-C', c.trabalho, 'push', repo, 'HEAD:refs/heads/main')
    c.journal.update(atual=reversao, aprovada={'sha': reversao, 'pacote': c.pacote})
    c.arquivo.write_text(json.dumps(c.journal))
    assert c.worker._dependencias_ativas({'depende_de': [I1]}, estado) == ([I1], False)
    assert 'dependencias_comprovadas' not in estado


@pytest.mark.parametrize('falha', ['container', 'pacote', 'journal', 'identidade', 'base'])
def test_ausencia_de_prova_real_nao_libera(cenario, falha):
    c = cenario
    if falha == 'container':
        c.saude['Running'] = False
    elif falha == 'pacote':
        c.journal['aprovada']['pacote'] = {'id': 'f' * 64}
    elif falha == 'journal':
        c.journal['atual'] = c.base
    else:
        c.reg['commit' if falha == 'identidade' else 'base'] = 'f' * 40
        c.registro.write_text(json.dumps(c.reg))
    c.arquivo.write_text(json.dumps(c.journal))
    try:
        resposta = c.autoridade.conferir_dependencia(I1, c.original, 'aplicacao')
    except ErroPonte:
        return
    assert resposta['situacao'] != 'preservada'


def test_duas_celulas_exigem_as_duas_ativas(tmp_path):
    dep = {'id': I1, 'estado': entregas.NA_MAIN, 'base': 'a' * 40, 'commit': 'b' * 40}
    integ = SimpleNamespace(ler=lambda _: dep, git=lambda *a, **k: SimpleNamespace(
        stdout='services/admin/app.py\0services/funil/app.py\0'))
    chamadas = []

    def conferir(id_, commit, celula):
        chamadas.append(celula)
        return ({'situacao': 'preservada', 'sha_aprovada': 'c' * 40,
                 'prova_identidade': 'd' * 64, 'arquivos_conferidos': 1}
                if celula == 'aplicacao' else {'situacao': 'aguardando'})

    worker = Servico(integ, SimpleNamespace(conferir_dependencia=conferir), Estados(tmp_path))
    assert worker._dependencias_ativas({'depende_de': [I1]}) == ([I1], False)
    assert chamadas == ['aplicacao', 'funil']


def test_rodada_publica_dependente_na_primeira_passagem(cenario, tmp_path):
    c = cenario

    class Integrador(IntegradorFalso):
        def git(self, *args, **kwargs):
            if '--no-renames' in args:
                return c.integ.git(*args, **kwargs)
            return super().git(*args, **kwargs)

    ponte = PonteFalsa()
    ponte.conferir_dependencia = c.autoridade.conferir_dependencia
    integ = Integrador([c.reg, entrega(I2, C2, [I1])])
    worker = Servico(integ, ponte, Estados(tmp_path / 'rodada'))
    resultados = worker.rodada()
    assert {'id': I2, 'fase': 'ativa'} in resultados
    assert integ.promocoes == [I2]
    assert ('publicar', I2) in ponte.chamadas
    assert worker.estados.ler(I1) is None
    assert worker.estados.ler(I2)['dependencias_comprovadas'][I1]['commit'] == c.original
