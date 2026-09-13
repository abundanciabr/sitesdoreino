"""Consulta usa os índices reais e devolve apenas a orientação recuperada."""
import json
from pathlib import Path

import pytest

import consultar_armadilhas as consulta
from indice_de_armadilhas import Entrada, montar, montar_sinais, montar_gatilhos


@pytest.fixture
def catalogo(tmp_path):
    pasta = tmp_path / 'armadilhas'
    pasta.mkdir()
    entradas = []
    for numero in range(1, 6):
        p = pasta / f'{numero:03d}-erro.md'
        p.write_text(f'''---
schema_version: 2
armadilha: {numero}
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: Consulta ativa para orientar o agente.
sinal:
  - `FalhaConhecida numero {numero}`
gatilho:
  - services/exemplo/*.py
licao: Confira o comando e restaure a configuração antes de repetir, caso {numero}.
---
# Erro {numero}
**Sintoma:** FalhaConhecida numero {numero}.
**Solução:** Restaure a configuração.
''', encoding='utf-8')
        entradas.append(Entrada(p))
    (pasta / 'SINAIS.json').write_text(montar_sinais(entradas), encoding='utf-8')
    (pasta / 'GATILHOS.json').write_text(montar_gatilhos(entradas), encoding='utf-8')
    (pasta / 'INDICE.md').write_text(montar(entradas), encoding='utf-8')
    return tmp_path


def test_sinal_real_com_caminho_deduplica_e_limita(catalogo):
    # guarda: ci/consultar_armadilhas.py:81
    r = consulta.consultar(catalogo, 'FalhaConhecida numero 1', 'services/exemplo/rota.py')
    assert r['estado'] == 'PASS'
    assert [x['id'] for x in r['resultados']] == ['001', '002', '003']
    assert all(len(x['licao']) <= 500 for x in r['resultados'])
    assert r['resultados'][0]['arquivo'] == 'armadilhas/001-erro.md'


def test_glob_nao_e_regex_e_normaliza_barra(catalogo):
    assert len(consulta.consultar(catalogo, caminho=r'services\exemplo\rota.py')['resultados']) == 3
    assert not consulta.consultar(catalogo, caminho='services/exemplo/rotaXpy')['resultados']


def test_gatilho_de_diretorio_inclui_descendentes_sem_confundir_vizinhos(catalogo):
    # guarda: ci/consultar_armadilhas.py:67
    indice = catalogo / 'armadilhas/GATILHOS.json'
    dados = json.loads(indice.read_text(encoding='utf-8'))
    dados['gatilhos'][0]['caminho'] = 'services/admin/'
    indice.write_text(json.dumps(dados), encoding='utf-8')
    for caminho in ['services/admin/views.py', r'services\admin\tests\test_views.py']:
        resultado = consulta.consultar(catalogo, caminho=caminho)
        assert resultado['estado'] == 'PASS'
        assert [item['id'] for item in resultado['resultados']] == ['001']
    assert not consulta.consultar(catalogo, caminho='services/admin_extra/views.py')['resultados']


def test_extrai_solucao_sem_metadados_nem_historia(tmp_path):
    # guarda: ci/consultar_armadilhas.py:25
    p = tmp_path / 'antiga.md'
    p.write_text('# Erro antigo\n**Sintoma:** caiu\n**Solução:** Use o comando certo\ne confira a saída.\n**Origem:** HISTORIA SECRETA\n', encoding='utf-8')
    assert consulta.extrair_licao(p) == 'Use o comando certo e confira a saída.'
    p.write_text('# Erro\n## Solução\n' + 'Resolva. ' * 200 + '\n## História\nHISTORIA', encoding='utf-8')
    assert len(consulta.extrair_licao(p)) == 500
    assert 'HISTORIA' not in consulta.extrair_licao(p)


def test_indice_textual_encontra_entrada_sem_sinal(catalogo):
    # guarda: ci/consultar_armadilhas.py:58
    p = catalogo / 'armadilhas/SINAIS.json'
    p.write_text('{"versao":1,"sinais":[]}', encoding='utf-8')
    assert consulta.consultar(catalogo, 'FalhaConhecida numero 2')['resultados'][0]['id'] == '002'


def test_desconhecido_tem_acao_util(catalogo):
    r = consulta.consultar(catalogo, 'NaoExiste98765')
    assert r['estado'] == 'PASS' and r['resultados'] == []
    assert 'Refine' in r['acao']


@pytest.mark.parametrize('arquivo,conteudo', [('SINAIS.json', None), ('GATILHOS.json', '{'), ('SINAIS.json', '{"versao":99,"sinais":[]}'), ('SINAIS.json', '{"sinais":{}}'), ('INDICE.md', None)])
def test_indice_ausente_ou_corrompido_e_error(catalogo, arquivo, conteudo):
    # guarda: ci/consultar_armadilhas.py:33
    p = catalogo / 'armadilhas' / arquivo
    if conteudo is None:
        p.unlink()
    else:
        p.write_text(conteudo, encoding='utf-8')
    r = consulta.consultar(catalogo, 'NaoExiste98765', 'services/exemplo/rota.py')
    assert r['estado'] == 'ERROR'
    assert 'python ci/indice_de_armadilhas.py' in r['acao']


def test_cli_json_compacto_e_entrada_invalida(catalogo, monkeypatch, capsys):
    monkeypatch.setattr(consulta, 'RAIZ', catalogo)
    assert consulta.main(['FalhaConhecida numero 1']) == 0
    saida = capsys.readouterr().out
    assert len(saida.splitlines()) == 1
    assert json.loads(saida)['resultados'][0]['id'] == '001'
    assert consulta.main([]) == 2
    assert json.loads(capsys.readouterr().out)['estado'] == 'ERROR'
    for args in [['--caminho'], ['--desconhecido'], ['erro', 'sem-aspas']]:
        assert consulta.main(args) == 2
        assert json.loads(capsys.readouterr().out)['estado'] == 'ERROR'


@pytest.mark.parametrize('alteracao', ['regex', 'arquivo'])
def test_fonte_invalida_nao_vira_resultado_vazio(catalogo, alteracao):
    p = catalogo / 'armadilhas/SINAIS.json'
    dados = json.loads(p.read_text(encoding='utf-8'))
    dados['sinais'][0][alteracao] = '[' if alteracao == 'regex' else '../fora.md'
    p.write_text(json.dumps(dados), encoding='utf-8')
    r = consulta.consultar(catalogo, 'FalhaConhecida numero 1')
    assert r['estado'] == 'ERROR'
    assert r['resultados'] == []
