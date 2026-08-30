"""A CONFERÊNCIA DO `toca` — o guarda que compara a promessa da tarefa com o diff.

Cada teste aqui é uma linha da regra de `ci/conferencia_do_toca.py`, e todos
rodam **sem rede**: as histórias de PR são montadas à mão, no mesmo desenho de
`ci/tests/test_divida_do_livro.py`. Um guarda cuja única prova fosse o GitHub
de verdade não conseguiria exercitar justamente os casos que decidem se ele é
justo — o rename que esconde a origem, o caminho de rito que todo PR carrega, a
célula nomeada que expande — porque esses estados não se produzem sob encomenda.

O que NÃO se testa aqui, de propósito: se o `gh` responde. Isso é
instrumentação, e o resultado dela já é `ERROR` por construção (INV-CI01) —
"não consegui ler o diff" nunca vira "o diff estava dentro do declarado".
"""

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import conferencia_do_toca as conf  # noqa: E402
import mapa_de_celulas  # noqa: E402
from _nucleo import ErroDeInstrumentacao, Estado  # noqa: E402

Arquivo = conf.Arquivo


@pytest.fixture(scope="module")
def mapa():
    """O mapa REAL de `celulas.yml`.

    De propósito, e não uma fixture inventada: a regra promete derivar as áreas
    da fonte que já existe no projeto. Um teste que montasse o próprio mapa
    provaria só que a função sabe ler o dicionário que ele mesmo escreveu —
    é a armadilha 129 (guarda que usa o objeto medido como régua).
    """
    return mapa_de_celulas.carregar(RAIZ)


def tarefa(toca, tid="TAR-999"):
    return {"id": tid, "titulo": "história de teste", "toca": list(toca)}


def arquivos(*caminhos):
    return [Arquivo(c) for c in caminhos]


# ------------------------------------------------------- o mapa vem de celulas.yml


def test_o_mapa_sai_de_celulas_yml_e_nao_de_lista_nova(mapa):
    """A granularidade é o CAMINHO declarado, não a célula inteira.

    `painel/`, `fila/`, `documentos/` e `services/admin/` pertencem todos à
    célula `admin`. Se a área fosse a célula, quem declarasse `fila` estaria
    autorizado a mexer em `services/admin/` — e a colisão entre dois robôs
    ficaria invisível justamente onde ela dói.
    """
    assert conf.area_do_caminho("painel/registros/x.js", mapa) == "painel"
    assert conf.area_do_caminho("fila/eventos/x.json", mapa) == "fila"
    assert conf.area_do_caminho("services/admin/urls.py", mapa) == "services/admin"
    assert conf.area_do_caminho("services/forum/api.py", mapa) == "services/forum"


def test_o_que_nao_e_de_celula_nenhuma_vira_o_primeiro_segmento(mapa):
    """`ci`, `.github`, `docs` — o vocabulário que as tarefas da fila já usam."""
    assert conf.area_do_caminho("ci/mergear.py", mapa) == "ci"
    assert conf.area_do_caminho(".github/workflows/pouso.yml", mapa) == ".github"
    assert conf.area_do_caminho("RITOS.md", mapa) == "RITOS.md"


def test_prefixo_de_segmento_nao_captura_vizinho_de_nome_parecido(mapa):
    """`services/quiz` não pode engolir `services/quizzes` — um dia existirá."""
    assert conf.area_do_caminho("services/quizzes/api.py", mapa) == "services"


def test_celula_nomeada_no_toca_expande_para_todos_os_caminhos_dela(mapa):
    """Quem declarou a célula declarou tudo que é dela."""
    assert conf.areas_declaradas(["admin"], mapa) == {
        "services/admin",
        "painel",
        "fila",
        "documentos",
    }
    assert conf.areas_declaradas(["ci", "fila"], mapa) == {"ci", "fila"}


def test_todo_toca_das_tarefas_reais_aponta_para_algo_que_existe(mapa):
    """Sanidade contra a fila de verdade, e não só contra histórias inventadas.

    Se esta asserção cair, ou uma tarefa nova escreveu o `toca` num vocabulário
    que a conferência não entende (e o alerta dela nasceria errado), ou uma
    pasta mudou de nome sem ninguém avisar a fila.

    A terceira causa é legítima e tem porta própria: a tarefa de GÊNESE, que
    cria a pasta que declara. Ela precisa dizer isso no campo `cria`, por
    escrito — e é a exigência da declaração explícita que impede esta porta de
    absolver as duas causas de cima.
    """
    erros = []
    tarefas = conf.fila.carregar_tarefas(RAIZ, erros)
    assert tarefas, "nenhuma tarefa lida — o próprio teste está cego"
    orfas = []
    for tid, dados in sorted(tarefas.items()):
        nascendo = conf.areas_criadas(dados)
        for area in conf.areas_declaradas(list(dados.get("toca") or []), mapa):
            if not (RAIZ / area).exists() and area not in nascendo:
                orfas.append(f"{tid}: {area}")
    assert not orfas, (
        "`toca` apontando para caminho que não existe: " + ", ".join(orfas)
    )


# ------------------------------------------------------------------ a regra


def test_diff_dentro_do_declarado_passa(mapa):
    d = conf.conferir(tarefa(["ci", "fila"]), arquivos("ci/x.py", "fila/tarefas/9.json"), mapa)
    assert d.houve is False
    assert conf.avaliar(d).estado is Estado.PASS


def test_area_fora_do_declarado_vira_divergencia(mapa):
    """O caso que a tarefa existe para pegar: a declaração otimista."""
    d = conf.conferir(tarefa(["ci"]), arquivos("ci/x.py", "services/forum/api.py"), mapa)
    assert d.houve is True
    assert set(d.nao_declaradas) == {"services/forum"}
    resultado = conf.avaliar(d)
    assert resultado.estado is Estado.FAIL
    assert "services/forum" in (resultado.detalhe or "")


def test_declarar_um_caminho_da_admin_nao_libera_os_outros(mapa):
    """`fila` é da célula `admin` — e mesmo assim não autoriza `services/admin`."""
    d = conf.conferir(tarefa(["fila"]), arquivos("services/admin/urls.py"), mapa)
    assert set(d.nao_declaradas) == {"services/admin"}


def test_declarado_e_nao_tocado_nao_e_divergencia_mas_aparece(mapa):
    """Declarar a mais custa paralelismo; declarar a MENOS causa colisão.

    Tratar os dois lados como o mesmo defeito faria o alerta gritar por excesso
    de zelo alheio — e guarda que grita à toa é guarda que se aprende a ignorar
    (`armadilhas/174`).
    """
    d = conf.conferir(tarefa(["ci", "infra"]), arquivos("ci/x.py"), mapa)
    assert d.houve is False
    assert d.declaradas_sem_toque == {"infra"}
    resultado = conf.avaliar(d)
    assert resultado.estado is Estado.PASS
    assert "infra" in (resultado.detalhe or "")


# ---------------------------------------------------- o rename (armadilhas/174)


def test_rename_mostra_as_DUAS_pontas(mapa):
    """`armadilhas/174`: um portão que lê só o destino fica cego para a origem.

    `git mv services/forum/x.py services/quiz/x.py` toca as DUAS células. Se a
    conferência olhasse só o destino, ela diria que a `forum` não foi mexida —
    e liberaria em paralelo exatamente a tarefa que vai colidir com esta.
    """
    d = conf.conferir(
        tarefa(["quiz"]),
        [Arquivo("services/quiz/x.py", anterior="services/forum/x.py")],
        mapa,
    )
    assert set(d.nao_declaradas) == {"services/forum"}


def test_rename_dentro_da_mesma_area_nao_vira_alarme_falso(mapa):
    """Renomear dentro da própria área é legítimo e frequente."""
    d = conf.conferir(
        tarefa(["ci"]),
        [Arquivo("ci/novo_nome.py", anterior="ci/nome_antigo.py")],
        mapa,
    )
    assert d.houve is False


def test_arquivo_sem_rename_nao_inventa_origem(mapa):
    assert Arquivo("ci/x.py").caminhos == ("ci/x.py",)
    assert Arquivo("ci/x.py", anterior="ci/x.py").caminhos == ("ci/x.py",)


# ------------------------------------------------------------ os caminhos de rito


def test_o_que_todo_pr_carrega_por_lei_nao_precisa_ser_declarado(mapa):
    """Registro, evento da fila e lição são partes de TERMINAR a tarefa.

    Sem esta isenção a conferência apontaria todo PR do projeto, e o alerta
    viraria ruído no mesmo dia em que nasceu.
    """
    d = conf.conferir(
        tarefa(["ci"]),
        arquivos(
            "ci/x.py",
            "painel/registros/20260830-001.js",
            "fila/eventos/20260830-120000-TAR-999-concluida.json",
            "armadilhas/999-licao-nova.md",
            "armadilhas/INDICE.md",
        ),
        mapa,
    )
    assert d.houve is False
    assert set(d.de_rito) == {"painel", "fila", "armadilhas"}


def test_o_rito_isenta_a_loja_certa_e_nao_a_pasta_toda(mapa):
    """`painel/registros/` é append-only; `painel/logica.js` é código compartilhado.

    Confundir os dois daria isenção silenciosa à regra de cálculo do painel —
    justamente o arquivo em que dois robôs colidem de verdade.
    """
    d = conf.conferir(tarefa(["ci"]), arquivos("painel/logica.js"), mapa)
    assert set(d.nao_declaradas) == {"painel"}
    assert d.de_rito == {}


def test_o_rito_conta_como_toque_para_o_lado_de_quem_declarou(mapa):
    """Quem declarou `painel` e só escreveu o registro declarou o que usou."""
    d = conf.conferir(tarefa(["painel"]), arquivos("painel/registros/x.js"), mapa)
    assert d.declaradas_sem_toque == set()


# ------------------------------------------------------------- a tarefa citada


def test_a_tarefa_sai_do_titulo_ou_do_ramo():
    assert conf.tarefa_citada("feat(ci): TAR-015 conferir o toca", "") == "TAR-015"
    assert conf.tarefa_citada("", "agent/fila/TAR-015-toca") == "TAR-015"
    assert conf.tarefa_citada("nada aqui", "agent/fila/tar015") is None


def test_a_leitura_da_citacao_e_a_MESMA_da_fila():
    """Duas leituras do mesmo fato divergem no primeiro dia em que uma muda."""
    assert conf.fila.tarefas_citadas("TAR-001 e TAR-015") == ["TAR-001", "TAR-015"]


# ------------------------------------------ o alerta: o texto que vai para o PR


def test_o_alerta_nomeia_a_area_fora_do_declarado_e_diz_que_nao_reprova(mapa):
    d = conf.conferir(tarefa(["ci"]), arquivos("services/forum/api.py"), mapa)
    texto = conf.recado(d, 570)
    assert conf.MARCA in texto
    assert "services/forum" in texto
    assert "#570" in texto and "TAR-999" in texto
    # Em sombra o alerta PRECISA dizer que não reprovou ninguém — senão ele
    # assusta como se fosse bloqueio, e a próxima sessão perde tempo caçando
    # um check vermelho que não existe.
    assert "sombra" in texto
    assert "não reprova" in texto


def test_o_alerta_nao_manda_editar_a_tarefa(mapa):
    """A fila só ACRESCENTA: o arquivo da tarefa nunca muda depois de criado."""
    d = conf.conferir(tarefa(["ci"]), arquivos("services/forum/api.py"), mapa)
    texto = conf.recado(d, 570)
    assert "nunca muda depois de criado" in texto
    assert "encolha o PR" in texto


# --------------------------------------------- a sombra, e o dialeto dos estados


def test_a_regra_nasce_em_sombra():
    """Promover é trocar esta palavra — e o diff precisa mostrar a troca."""
    assert conf.AUTORIDADE == "sombra"


def test_em_sombra_a_divergencia_NAO_reprova_o_processo(monkeypatch, capsys):
    """Sombra: observa, avisa e deixa passar. Exit 0, e o texto diz a verdade."""
    d = conf.conferir(
        tarefa(["ci"]), arquivos("services/forum/api.py"), mapa_de_celulas.carregar(RAIZ)
    )
    relatorio = conf.Relatorio("t")
    relatorio.registrar(conf.avaliar(d))
    monkeypatch.setattr(conf, "raiz_do_repo", lambda: RAIZ)
    monkeypatch.setattr(conf, "rodar", lambda raiz, numero: (relatorio, d))
    assert conf.main(["--pr", "570"]) == 0
    saida = capsys.readouterr().out
    assert "SOMBRA" in saida and "teria REPROVADO" in saida


def test_promovida_a_bloqueia_a_MESMA_divergencia_reprova(monkeypatch):
    """A prova de que a sombra é a única coisa segurando o vermelho.

    Sem este teste, `AUTORIDADE` poderia estar desligada por engano (uma regra
    que nunca reprova em situação nenhuma) e nada ficaria vermelho para contar.
    """
    d = conf.conferir(
        tarefa(["ci"]), arquivos("services/forum/api.py"), mapa_de_celulas.carregar(RAIZ)
    )
    relatorio = conf.Relatorio("t")
    relatorio.registrar(conf.avaliar(d))
    monkeypatch.setattr(conf, "AUTORIDADE", "bloqueia")
    monkeypatch.setattr(conf, "raiz_do_repo", lambda: RAIZ)
    monkeypatch.setattr(conf, "rodar", lambda raiz, numero: (relatorio, d))
    assert conf.main(["--pr", "570"]) == 1


def test_falha_de_medicao_vira_ERROR_e_nunca_PASS(monkeypatch):
    """INV-CI01: 'não consegui ler o diff' é resultado, não silêncio."""

    def explode(raiz, numero):
        raise ErroDeInstrumentacao("gh fora do ar", "")

    monkeypatch.setattr(conf, "raiz_do_repo", lambda: RAIZ)
    monkeypatch.setattr(conf, "rodar", explode)
    assert conf.main(["--pr", "570"]) == 2


def test_pr_sem_tarefa_e_SKIP_declarado_nao_PASS_por_omissao(monkeypatch):
    monkeypatch.setattr(
        conf, "dados_do_pr", lambda raiz, n: {"title": "chore: nada", "headRefName": "x"}
    )
    relatorio, divergencia = conf.rodar(RAIZ, 570)
    assert divergencia is None
    assert relatorio.estado is Estado.SKIP
    assert relatorio.resultados[0].estado is Estado.SKIP


def test_tarefa_que_nasce_dentro_do_proprio_pr_e_SKIP(monkeypatch):
    """A conferência roda com a definição da `main`, que ainda não a conhece."""
    monkeypatch.setattr(
        conf,
        "dados_do_pr",
        lambda raiz, n: {"title": "feat: TAR-998 tarefa nova", "headRefName": "x"},
    )
    relatorio, divergencia = conf.rodar(RAIZ, 570)
    assert divergencia is None
    assert relatorio.estado is Estado.SKIP


# --------------------------------------------------------- as bordas com o gh


def test_pr_sem_arquivo_nenhum_e_ERROR_nunca_isencao(monkeypatch):
    """Lista vazia como 'nada fora do toca' daria isenção a toda falha de leitura."""
    monkeypatch.setattr(conf, "_gh", lambda *a, **k: "")
    with pytest.raises(ErroDeInstrumentacao):
        conf.arquivos_do_pr(RAIZ, 570)


def test_a_leitura_do_diff_traz_a_origem_do_rename(monkeypatch):
    """O `previous_filename` da API REST é o que fecha a `armadilhas/174`."""
    monkeypatch.setattr(
        conf,
        "_gh",
        lambda *a, **k: "services/quiz/x.py\tservices/forum/x.py\nci/y.py\t\n",
    )
    lidos = conf.arquivos_do_pr(RAIZ, 570)
    assert lidos[0].caminhos == ("services/quiz/x.py", "services/forum/x.py")
    assert lidos[1].caminhos == ("ci/y.py",)


def test_o_mesmo_alerta_nao_se_repete_a_cada_push(monkeypatch):
    corpo = "linha um\nlinha dois"
    monkeypatch.setattr(conf, "_gh", lambda *a, **k: '"linha um\\nlinha dois"\n')
    assert conf.ja_avisado(RAIZ, 570, corpo) is True


def test_alerta_diferente_nao_e_confundido_com_o_ja_publicado(monkeypatch):
    """Se a divergência MUDOU, o alerta novo tem de entrar."""
    monkeypatch.setattr(conf, "_gh", lambda *a, **k: '"outra coisa"\n')
    assert conf.ja_avisado(RAIZ, 570, "linha um\nlinha dois") is False


def test_comentario_multilinha_nao_e_partido_em_dois(monkeypatch):
    """Cada corpo vem como UMA linha de JSON — senão a comparação nunca casa.

    Um `já avisado` que nunca é verdade republica o mesmo alerta a cada push, e
    o alerta morre afogado no próprio eco.
    """
    monkeypatch.setattr(conf, "_gh", lambda *a, **k: '"a\\n\\nb"\n"c"\n')
    assert conf.ja_avisado(RAIZ, 570, "a\n\nb") is True


# --------------------------------------------- a gênese: criar o que se declara


def test_area_que_a_tarefa_declara_criar_e_dispensada_da_existencia(mapa):
    """A terceira causa legítima: a pasta não existe porque é esta tarefa que a cria."""
    nascendo = conf.areas_criadas({"cria": ["gamificacao"]})
    assert nascendo == {"gamificacao"}
    assert not (RAIZ / "gamificacao").exists(), (
        "o teste ficaria cego se esta pasta passasse a existir de verdade"
    )


def test_sem_declarar_cria_a_pasta_inexistente_continua_reprovando(mapa):
    """A porta da gênese não absolve erro de digitação nem pasta renomeada."""
    assert conf.areas_criadas({}) == set()
    assert conf.areas_criadas({"cria": []}) == set()
    area = next(iter(conf.areas_declaradas(["gamifikacao"], mapa)))
    assert not (RAIZ / area).exists()
    assert area not in conf.areas_criadas({"cria": ["gamificacao"]}), (
        "declarar a criação de uma coisa não pode absolver o nome errado de outra"
    )


def test_cria_normaliza_barra_e_ignora_vazio():
    """Mesma normalização do `toca`, para os dois lados falarem a mesma língua."""
    assert conf.areas_criadas({"cria": ["services\\gamificacao", "  ", "/fila/"]}) == {
        "services/gamificacao",
        "fila",
    }
