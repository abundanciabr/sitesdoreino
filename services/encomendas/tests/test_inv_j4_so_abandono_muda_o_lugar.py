"""[INV-ENC-J4] Passar, expirar e pausar nunca alteram `data_entrada_fila`. Só abandono.

Lei: `docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §5 (justiça).
Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §6.2, §6.3 e §6.6.

Este invariante protege uma frase que o plano repete três vezes e que o aluno vai
ler na tela: **"você mantém o seu lugar"**. Passar sem tempo, ficar em silêncio
uma tarde, desligar o interruptor numa semana de prova — nada disso custa a
posição na fila. Uma única coisa custa, e ela está escrita: abandonar uma
encomenda depois de aceitá-la.

**Por que a garantia é de FORMA, e não só de comportamento.** Comportamento mede
os gestos que existem hoje; a próxima sessão acrescenta gestos. O degrau 2.5
traz a pausa automática por três silêncios, a chamada aberta e a
reclassificação — e é exatamente ali que alguém, com toda a boa intenção, pode
escrever `perfil.data_entrada_fila = agora` para "reiniciar a espera" de quem
ficou muito tempo pausado. Nenhum teste de comportamento escrito hoje pegaria
isso: o gesto ainda não existe.

Então este guarda varre o código da célula e exige que **toda escrita em
`data_entrada_fila` esteja numa função declarada nesta lista**. Hoje a lista
está VAZIA, e essa é a informação: nenhum código da célula move o lugar de
ninguém. Quando o abandono chegar (degrau 2.5), quem o escrever acrescenta o
nome da função aqui, com o motivo — e o diff mostra a mudança para quem revisa.
"""

import ast
from datetime import datetime, timedelta, timezone as fuso
from pathlib import Path

from apps.encomendas import motor
from apps.encomendas.models import Oferta, PerfilProfissional

SITE = "escola-a"
AGORA = datetime.now(tz=fuso.utc)

CELULA = Path(__file__).resolve().parent.parent
CAMPO = "data_entrada_fila"

# AS ÚNICAS FUNÇÕES QUE PODEM MOVER O LUGAR DE ALGUÉM NA FILA.
#
# Vazia hoje, e a vacuidade é o estado correto no degrau 2.3: o motor lê a data
# e nunca a escreve. Quem trouxer o abandono (degrau 2.5, plano §6.6) declara
# aqui o nome da função que manda o aluno para o fim da fila, com o motivo ao
# lado — e só o abandono tem esse direito.
QUEM_PODE_MOVER_O_LUGAR: set[str] = set()

# `migrations/` fica de fora: uma migração é fotografia do esquema, e a
# `data_entrada_fila` que aparece lá é a coluna nascendo, não alguém a movendo.
IGNORADAS = {"migrations"}


# Os gestos do ORM que GRAVAM. A peneira é estreita de propósito: varrer todo
# argumento nomeado `data_entrada_fila=` acusaria a LEITURA que monta o
# `Candidato` do motor, e medir a coisa errada com precisão é como um portão
# morre. `update()` e `bulk_*` estão aqui porque não passam por `save()`
# (`armadilhas/023`), que é justamente por onde a mudança escaparia.
ESCRITAS_DO_ORM = {
    "create",
    "update",
    "get_or_create",
    "update_or_create",
    "bulk_create",
    "bulk_update",
}


class _Varredor(ast.NodeVisitor):
    """Acha toda ESCRITA em `data_entrada_fila`, e a função em que ela mora.

    Três formas de gravar o mesmo campo, e as três contam: a atribuição de
    atributo (`perfil.data_entrada_fila = x`), o argumento nomeado de um gesto
    do ORM que grava (`create`, `update`, ...) e a citação do campo em
    `save(update_fields=[...])`.
    """

    def __init__(self):
        self.achados: list[tuple[int, str]] = []
        self.funcao = "<módulo>"

    def visit_FunctionDef(self, no):
        anterior, self.funcao = self.funcao, no.name
        self.generic_visit(no)
        self.funcao = anterior

    def visit_Assign(self, no):
        for alvo in no.targets:
            if isinstance(alvo, ast.Attribute) and alvo.attr == CAMPO:
                self.achados.append((no.lineno, self.funcao))
        self.generic_visit(no)

    def visit_Call(self, no):
        nome = getattr(no.func, "attr", None) or getattr(no.func, "id", None)
        for chave in no.keywords:
            if chave.arg == CAMPO and nome in ESCRITAS_DO_ORM:
                self.achados.append((no.lineno, self.funcao))
            if chave.arg == "update_fields" and nome == "save":
                for item in getattr(chave.value, "elts", []):
                    if isinstance(item, ast.Constant) and item.value == CAMPO:
                        self.achados.append((no.lineno, self.funcao))
        self.generic_visit(no)


def _arquivos_da_celula():
    for caminho in sorted((CELULA / "apps").rglob("*.py")):
        if IGNORADAS & set(caminho.parts):
            continue
        yield caminho


# ---------------------------------------------------------------------------
# 1. A FORMA: ninguém escreve no lugar de ninguém
# ---------------------------------------------------------------------------


def test_nenhuma_funcao_da_celula_move_o_lugar_na_fila():
    """A varredura, e a lista vazia que ela guarda.

    Vermelho aqui não significa "você errou": significa "você acabou de escrever
    um gesto que mexe no lugar de alguém na fila, e a lei diz que só o abandono
    pode". Se for o abandono, declare a função em `QUEM_PODE_MOVER_O_LUGAR` com
    o motivo. Se não for, o conserto é não escrever no campo.
    """
    achados = []
    for caminho in _arquivos_da_celula():
        varredor = _Varredor()
        varredor.visit(ast.parse(caminho.read_text(encoding="utf-8")))
        for linha, funcao in varredor.achados:
            if funcao not in QUEM_PODE_MOVER_O_LUGAR:
                achados.append(f"{caminho.relative_to(CELULA)}:{linha} em {funcao}()")

    assert achados == [], (
        f"escrita em `{CAMPO}` fora da lista declarada: "
        + "; ".join(achados)
        + ". [INV-ENC-J4]: passar, expirar e pausar NUNCA mudam o lugar na fila; "
        "só o abandono (lei §5, plano §6.2 e §6.6). Se esta escrita É o abandono, "
        "acrescente o nome da função a `QUEM_PODE_MOVER_O_LUGAR` com o motivo ao "
        "lado. Se não é, ela não deveria existir."
    )


def test_a_lista_de_quem_pode_mover_cabe_numa_tela():
    """Uma isenção que ninguém vê é como uma regra que ninguém escreveu.

    A lista está vazia no degrau 2.3 e deve caber num olhar para sempre: se ela
    crescer além do abandono, alguém transformou "só o abandono" em "vários
    gestos", que é o invariante morrendo por acúmulo em vez de por decisão.
    """
    assert len(QUEM_PODE_MOVER_O_LUGAR) <= 1, (
        "só o abandono pode mover o lugar de alguém na fila (lei §5). "
        f"Declaradas: {sorted(QUEM_PODE_MOVER_O_LUGAR)}"
    )


def test_o_varredor_enxerga_as_quatro_formas_de_gravar():
    """O guarda que não morde é indistinguível do guarda desligado.

    Sem esta prova, a varredura acima passaria igualmente bem se o `_Varredor`
    não achasse nada — e é exatamente assim que um portão morre em silêncio.
    """
    codigo = (
        "def move():\n"
        "    perfil.data_entrada_fila = agora\n"
        "    Perfil.objects.update(data_entrada_fila=agora)\n"
        "    Perfil.objects.create(pessoa=p, data_entrada_fila=agora)\n"
        "    perfil.save(update_fields=['data_entrada_fila'])\n"
    )
    varredor = _Varredor()
    varredor.visit(ast.parse(codigo))

    assert [funcao for _, funcao in varredor.achados] == ["move"] * 4


def test_o_varredor_deixa_a_LEITURA_em_paz():
    """A outra metade da régua: ler o campo não é movê-lo.

    O motor monta um `Candidato(data_entrada_fila=perfil.data_entrada_fila)` a
    cada passada, e isso é leitura. Um varredor que acusasse toda menção ao nome
    do campo reprovaria o próprio motor no primeiro dia, seria afrouxado na
    mesma tarde, e a regra morreria por ter medido demais.
    """
    codigo = (
        "def le():\n"
        "    return Candidato(data_entrada_fila=perfil.data_entrada_fila)\n"
        "def ordena(perfis):\n"
        "    return sorted(perfis, key=lambda p: p.data_entrada_fila)\n"
        "def filtra():\n"
        "    return Perfil.objects.filter(data_entrada_fila__lt=agora)\n"
    )
    varredor = _Varredor()
    varredor.visit(ast.parse(codigo))

    assert varredor.achados == []


# ---------------------------------------------------------------------------
# 2. O COMPORTAMENTO: os três gestos que a lei nomeia, um a um
# ---------------------------------------------------------------------------


def test_passar_nao_muda_o_lugar(semeado, criar_perfil, criar_encomenda):
    """Passar é instantâneo e sem punição (plano §6.3)."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila
    criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=aluno).responder(
        Oferta.Resultado.PASSOU,
        motivo_passe=Oferta.MotivoDoPasse.SEM_TEMPO,
        em=AGORA,
    )
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes


def test_expirar_nao_muda_o_lugar(semeado, criar_perfil, criar_encomenda):
    """Silêncio é sem punição, e o plano diz isso com todas as letras."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila
    criar_encomenda()
    motor.rodar(AGORA, site_id=SITE)

    Oferta.objects.get(aluno=aluno).responder(Oferta.Resultado.EXPIROU, em=AGORA)
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes


def test_pausar_e_religar_nao_mudam_o_lugar(semeado, criar_perfil):
    """ "O aluno religa e volta ao mesmo lugar" — plano §6.3, palavra por palavra."""
    aluno = criar_perfil("pes-1", entrada=AGORA - timedelta(days=40))
    antes = aluno.data_entrada_fila

    aluno.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    aluno.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    aluno.refresh_from_db()

    assert aluno.data_entrada_fila == antes
    assert aluno.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL


def test_quem_voltou_da_pausa_recupera_a_vez_que_tinha(
    semeado, criar_perfil, criar_encomenda
):
    """O efeito visível de tudo isto, e o único que o aluno sente.

    Manter a data seria detalhe de banco se não mudasse quem recebe. Aqui muda:
    a pessoa mais antiga da fila pausa, perde uma rodada, religa — e volta a ser
    a primeira da vez seguinte, na frente de quem entrou depois dela.
    """
    ana = criar_perfil("pes-ana", entrada=AGORA - timedelta(days=100))
    bia = criar_perfil("pes-bia", entrada=AGORA - timedelta(days=50))

    ana.mudar_disponibilidade(
        PerfilProfissional.Disponibilidade.PAUSADO,
        modo_da_pausa=PerfilProfissional.ModoDaPausa.MANUAL,
    )
    primeira = criar_encomenda(cliente="cli-1")
    motor.rodar(AGORA, site_id=SITE)
    assert Oferta.objects.get(encomenda=primeira).aluno_id == bia.id

    ana.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
    Oferta.objects.get(aluno=bia).responder(Oferta.Resultado.EXPIROU, em=AGORA)
    segunda = criar_encomenda(cliente="cli-2")
    motor.rodar(AGORA, site_id=SITE)

    assert Oferta.objects.get(encomenda=segunda).aluno_id == ana.id
