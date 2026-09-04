"""Os parâmetros são DADO, com histórico por linha nova. E a prova é de fora.

Lei §3.8: *"A tabela `Parametro` mora nesta célula: `chave`, `valor`, `desde`,
`motivo`, `quem`; mudar é acrescentar uma linha, nunca `UPDATE`; o motor lê o
valor vigente em `agora` (...). Nenhum número da seção 6.12 vive em código: um
teste-guarda lê cada chave do banco e reprova constante mágica no motor."*

Este arquivo é esse teste-guarda, e ele tem três dentes:

1. **`test_a_semente_grava_os_27_valores_da_lei`** lê cada chave DO BANCO depois
   de rodar a semente, e compara com a tabela da lei transcrita aqui. É a prova
   de fora: se a semente errar um valor, quem discorda é o teste, não o autor.
2. **`test_mudar_um_parametro_e_acrescentar_uma_linha`** e os dois irmãos
   provam que o PostgreSQL recusa `UPDATE` e `DELETE` na tabela. Sem eles,
   "nunca UPDATE" seria uma frase num documento.
3. **`test_nenhuma_constante_magica_no_codigo_da_celula`** varre a árvore da
   célula com `ast` e reprova o número solto. É o dente que morde os degraus
   2.3 e 2.4 (o motor e os relógios), onde a tentação de escrever
   `timedelta(hours=3)` em vez de ler `relogio_da_oferta` é máxima.

Se um número da lei §6 voltar a viver em código, isso é o **critério de morte 5**
da lei §9: pare e reabra a decisão com o mantenedor.
"""

import ast
from datetime import datetime, timedelta, timezone as fuso
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.encomendas.models import CHAVES_DE_PARAMETRO, Parametro

SITE = "escola-a"
AGORA = datetime(2026, 9, 4, 12, 0, tzinfo=fuso.utc)

# A tabela da lei §6, transcrita AQUI, de propósito, e não importada do
# semeador: um teste que importa a resposta do arquivo que ele mede não mede
# nada. As 19 linhas da lei viram 27 chaves porque várias juntam duas ou três
# chaves numa célula só ("janela_inicio / janela_fim").
A_LEI_SECAO_6 = {
    "relogio_da_oferta": "3",
    "janela_inicio": "08:00",
    "janela_fim": "22:00",
    "silencios_para_pausa": "3",
    "horas_para_virar_aberta": "24",
    "encomendas_simultaneas_por_aluno": "1",
    "prazo_producao.simples": "3",
    "prazo_producao.vestivel_veiculo": "7",
    "prazo_producao.personagem": "14",
    "dias_de_revisao_no_prazo_prometido": "1",
    "extensoes_por_encomenda": "1",
    "extensao_horas": "48",
    "extensao_pedida_ate_horas_antes": "24",
    "sla_do_revisor": "24",
    "amostragem_de_revisao": "5",
    "aprovacao_tacita": "48",
    "correcoes_incluidas": "1",
    "prazo_da_correcao": "48",
    "passes_nao_pronto_para_reclassificar": "2",
    "passes_nao_pronto_para_aviso": "3",
    "janela_dos_passes": "30",
    "repasse_apos_aprovacao": "proximo_dia_util",
    "meta_aprovacao_cliente_novo": "4",
    "entregas_para_nivel_intermediario": "1",
    "entregas_para_nivel_avancado": "5",
    "janela_sem_abandono": "90",
    "pausa_por_segundo_abandono": "30",
}

CELULA = Path(__file__).resolve().parent.parent
# O ÚNICO arquivo da célula onde um número da lei §6 pode aparecer. Ele não é
# código de decisão: é a semente, e a partir do primeiro INSERT quem manda é o
# banco. Esta lista é curta e visível de propósito; crescer é diff.
ONDE_O_NUMERO_PODE_MORAR = {
    CELULA / "apps" / "encomendas" / "management" / "commands" / "semear_parametros.py",
}


def semear(site=SITE):
    saida = StringIO()
    call_command("semear_parametros", site=site, stdout=saida)
    return saida.getvalue()


# ---------------------------------------------------------------------------
# 1. O catálogo e a semente
# ---------------------------------------------------------------------------


def test_o_catalogo_tem_as_27_chaves_da_lei():
    """Chave a mais ou a menos reprova aqui, antes de o motor ler `None`."""
    assert sorted(CHAVES_DE_PARAMETRO) == sorted(A_LEI_SECAO_6)
    assert len(CHAVES_DE_PARAMETRO) == 27


def test_a_semente_grava_os_27_valores_da_lei(db):
    """A prova de fora: cada chave é LIDA DO BANCO e comparada com a lei."""
    semear()
    do_banco = dict(
        Parametro.objects.filter(site_id=SITE).values_list("chave", "valor")
    )
    assert do_banco == A_LEI_SECAO_6


def test_toda_linha_semeada_diz_desde_quando_e_por_que(db):
    """`desde`, `motivo` e `quem` não são enfeite: são o histórico da lei §3.8."""
    semear()
    for linha in Parametro.objects.filter(site_id=SITE):
        assert linha.desde is not None
        assert len(linha.motivo) >= 15, linha.chave
        # A semente não tem pessoa atrás: quem semeia é a instalação da célula.
        assert linha.quem == ""


def test_a_semente_nao_pisa_em_cima_da_mudanca_do_dono(db):
    """Idempotente por CHAVE, não pela linha.

    Um `get_or_create` pela linha inteira reinstalaria o valor de fábrica ao
    lado da mudança do mantenedor, e a mais nova venceria. Como a tabela é
    append-only, não haveria como desfazer.
    """
    semear()
    Parametro.objects.create(
        site_id=SITE,
        chave="relogio_da_oferta",
        valor="5",
        desde=AGORA,
        motivo="O piloto de papel mostrou que tres horas nao dao tempo.",
        quem="dono-1",
    )
    semear()
    assert (
        Parametro.objects.filter(site_id=SITE, chave="relogio_da_oferta").count() == 2
    )
    assert Parametro.vigente_em("relogio_da_oferta", AGORA, site_id=SITE).valor == "5"


def test_a_semente_e_por_site(db):
    """Lei 9: uma fábrica, N lojas. Semear a escola A não semeia a escola B."""
    semear(site="escola-a")
    assert Parametro.objects.filter(site_id="escola-b").count() == 0


# ---------------------------------------------------------------------------
# 2. Mudar é acrescentar uma linha, nunca UPDATE
# ---------------------------------------------------------------------------


def test_o_valor_vigente_e_o_de_agora_e_nao_o_mais_recente(db):
    """A regra inteira da lei §3.8 cabe nesta asserção.

    Um parâmetro mudado às 15h NÃO reescreve uma oferta feita às 14h. Sem isto,
    a mudança do mantenedor seria retroativa, e uma oferta já feita passaria a
    ser julgada por uma regra que não existia quando ela nasceu.
    """
    semear()
    Parametro.objects.create(
        site_id=SITE,
        chave="relogio_da_oferta",
        valor="5",
        desde=AGORA.replace(hour=15),
        motivo="O piloto de papel mostrou que tres horas nao dao tempo.",
        quem="dono-1",
    )
    as_14h = Parametro.vigente_em(
        "relogio_da_oferta", AGORA.replace(hour=14), site_id=SITE
    )
    as_16h = Parametro.vigente_em(
        "relogio_da_oferta", AGORA.replace(hour=16), site_id=SITE
    )
    assert (as_14h.valor, as_16h.valor) == ("3", "5")


def test_antes_da_semente_nao_ha_valor_inventado(db):
    """`vigente_em` devolve `None`, e não um padrão embutido.

    Um padrão em código seria exatamente a constante mágica que a lei proíbe, e
    ele esconderia uma semeadura que não rodou: a célula trabalharia com números
    que ninguém escolheu.
    """
    assert Parametro.vigente_em("relogio_da_oferta", AGORA, site_id=SITE) is None


def test_mudar_um_parametro_e_acrescentar_uma_linha(db):
    """O PostgreSQL recusa o `UPDATE`. Sem gatilho, isto seria só uma frase."""
    semear()
    linha = Parametro.objects.get(site_id=SITE, chave="relogio_da_oferta")
    with pytest.raises(IntegrityError, match="append-only"):
        Parametro.objects.filter(pk=linha.pk).update(valor="5")


def test_uma_linha_de_parametro_nao_se_apaga(db):
    semear()
    with pytest.raises(IntegrityError, match="append-only"):
        Parametro.objects.filter(site_id=SITE, chave="janela_fim").delete()


def test_a_chave_fora_do_vocabulario_e_recusada(db):
    """A tabela não é um saco de configuração: chave nova é diff visível."""
    with pytest.raises(
        IntegrityError, match="chave_de_parametro_no_vocabulario_fechado"
    ):
        Parametro.objects.create(
            site_id=SITE,
            chave="preco_do_item_simples",
            valor="1000",
            desde=AGORA,
            motivo="Dinheiro nao mora nesta celula, e esta chave prova isso.",
            quem="dono-1",
        )


def test_mudanca_sem_motivo_escrito_e_recusada(db):
    """Um histórico com motivo "ajuste" não responde nada seis meses depois."""
    with pytest.raises(IntegrityError, match="mudanca_de_parametro_tem_motivo_escrito"):
        Parametro.objects.create(
            site_id=SITE,
            chave="relogio_da_oferta",
            valor="5",
            desde=AGORA,
            motivo="ajuste",
            quem="dono-1",
        )


def test_duas_linhas_da_mesma_chave_no_mesmo_instante_sao_recusadas(db):
    """Duas respostas para "quanto vale agora" é a pergunta ambígua."""
    semear()
    vigente = Parametro.objects.get(site_id=SITE, chave="relogio_da_oferta")
    with pytest.raises(IntegrityError, match="uma_linha_por_chave_por_momento"):
        Parametro.objects.create(
            site_id=SITE,
            chave="relogio_da_oferta",
            valor="9",
            desde=vigente.desde,
            motivo="Duas linhas valendo do mesmo instante nao podem existir.",
            quem="dono-1",
        )


def test_o_tipo_de_cada_chave_vem_do_catalogo(db):
    """O `valor` é sempre texto; a chave é quem diz o tipo (contrato em papel)."""
    semear()
    assert (
        Parametro.objects.get(chave="janela_inicio", site_id=SITE).tipo == "hora_do_dia"
    )
    assert (
        Parametro.objects.get(chave="relogio_da_oferta", site_id=SITE).tipo == "horas"
    )
    assert (
        Parametro.objects.get(chave="repasse_apos_aprovacao", site_id=SITE).tipo
        == "enum"
    )


# ---------------------------------------------------------------------------
# 3. Nenhum número da lei §6 vive em código
# ---------------------------------------------------------------------------


def _arquivos_da_celula():
    for caminho in sorted((CELULA / "apps").rglob("*.py")):
        if caminho in ONDE_O_NUMERO_PODE_MORAR:
            continue
        if "migrations" in caminho.parts:
            # A migração é fotografia do esquema, não regra viva: os
            # `max_length` dela não são decisão de ninguém.
            continue
        yield caminho


# As chamadas em que um número solto é, quase sempre, um parâmetro escrito à
# mão. É uma peneira estreita de propósito: varrer TODO literal numérico da
# célula acusaria `max_length=64` e `version=1`, e medir a coisa errada com
# precisão é como um portão morre.
CHAMADAS_DE_TEMPO = {"timedelta", "time", "relativedelta"}

# As constantes de MÓDULO declaradas: números que não são parâmetro da lei §6 e
# que, por isso, podem viver em código. A lista é curta e visível de propósito;
# crescer é diff, e cada entrada precisa do motivo escrito ao lado.
CONSTANTES_DECLARADAS = {
    # O `minLength` do `MudancaDeParametro` do contrato em papel. Não é regra de
    # negócio da fila (não está na lei §6, e o mantenedor não a edita numa
    # tela): é a régua de "escreveu por quê", e ela vale para toda linha nova.
    "TAMANHO_MINIMO_DO_MOTIVO",
}


class _Varredor(ast.NodeVisitor):
    def __init__(self):
        self.achados = []

    def visit_Call(self, no):
        nome = getattr(no.func, "id", None) or getattr(no.func, "attr", None)
        if nome in CHAMADAS_DE_TEMPO:
            argumentos = list(no.args) + [k.value for k in no.keywords]
            for argumento in argumentos:
                if isinstance(argumento, ast.Constant) and isinstance(
                    argumento.value, int
                ):
                    self.achados.append((no.lineno, nome, argumento.value))
        self.generic_visit(no)

    def visit_Assign(self, no):
        # Constante de MÓDULO com número: `RELOGIO_DA_OFERTA_HORAS = 3`. É a
        # forma clássica da constante mágica, e ela não tem nenhuma razão de
        # existir numa célula cujos números todos moram no banco.
        for alvo in no.targets:
            if (
                isinstance(alvo, ast.Name)
                and alvo.id.isupper()
                and alvo.id not in CONSTANTES_DECLARADAS
                and isinstance(no.value, ast.Constant)
                and isinstance(no.value.value, int)
                and not isinstance(no.value.value, bool)
            ):
                self.achados.append((no.lineno, alvo.id, no.value.value))
        self.generic_visit(no)


def test_nenhuma_constante_magica_no_codigo_da_celula():
    """O dente que morde os degraus 2.3 e 2.4, antes de eles serem escritos.

    A tentação concreta tem nome: escrever `expira_em = agora + timedelta(hours=3)`
    no motor de oferta em vez de ler `relogio_da_oferta` do banco. Funciona,
    passa em teste, e transforma um parâmetro que o mantenedor edita numa tela
    em algo que só muda por PR. É o critério de morte 5 da lei §9.

    A varredura é do MÓDULO, não do valor: ela não pergunta "este 3 é o relógio
    da oferta?" (pergunta que erraria feio, porque 3 também é `max_length`).
    Ela pergunta "existe número solto onde um parâmetro deveria estar sendo
    lido?" — chamada de duração, ou constante de módulo.
    """
    achados = []
    for caminho in _arquivos_da_celula():
        varredor = _Varredor()
        varredor.visit(ast.parse(caminho.read_text(encoding="utf-8")))
        for linha, onde, valor in varredor.achados:
            achados.append(f"{caminho.relative_to(CELULA)}:{linha} {onde}={valor}")

    assert achados == [], (
        "número solto no código desta célula: "
        + "; ".join(achados)
        + ". Os 27 parâmetros da lei §6 são DADO (lei §3.8): leia o valor "
        "vigente com `Parametro.vigente_em(chave, agora, site_id=...)`. Se o "
        "número não for parâmetro nenhum, ele ainda assim não é constante de "
        "módulo: passe-o como argumento, ou reabra a decisão (critério de "
        "morte 5 da lei §9)."
    )


def test_as_isencoes_cabem_numa_tela(db):
    """Uma isenção que ninguém vê é como uma regra que ninguém escreveu.

    Duas listas de exceção existem neste arquivo, e as duas são curtas de
    propósito: o semeador (o único lugar onde um número da lei §6 pode morar) e
    as constantes de módulo declaradas. Se qualquer uma crescer, o diff mostra,
    e quem revisa pergunta por quê.
    """
    assert len(CONSTANTES_DECLARADAS) <= 3, (
        "a lista de constantes de módulo declaradas cresceu. Cada número que "
        "entra ali é um número que deixou de ser dado; confira se ele não é "
        "parâmetro da lei §6 disfarçado."
    )


def test_o_semeador_e_o_unico_isento(db):
    """A isenção existe, é uma só, e este teste a mantém visível.

    Se a lista `ONDE_O_NUMERO_PODE_MORAR` crescer, o diff mostra. Uma isenção
    que ninguém vê é como uma regra que ninguém escreveu.
    """
    assert len(ONDE_O_NUMERO_PODE_MORAR) == 1
    (unico,) = ONDE_O_NUMERO_PODE_MORAR
    assert unico.exists() and unico.name == "semear_parametros.py"
