"""Semeia os 27 parametros da Fila do Primeiro Dolar, com os valores da lei.

O UNICO LUGAR DA CELULA ONDE UM NUMERO DA LEI SECAO 6 APARECE
--------------------------------------------------------------
Lei secao 3.8: *"Nenhum numero da secao 6.12 vive em codigo: um teste-guarda le
cada chave do banco e reprova constante magica no motor."* Este arquivo e a
excecao declarada, e ele nao e codigo de decisao: e a SEMENTE. A partir do
primeiro INSERT, quem manda e o banco, e mudar um valor e acrescentar uma linha
nova pela tela do Admin, sem PR. Se um destes numeros reaparecer no motor, nos
relogios ou numa tela, isso e o criterio de morte 5 da lei secao 9: pare e
reabra a decisao com o mantenedor. Guarda: `tests/test_parametros_sao_dado.py`.

POR QUE UM COMANDO, E NAO UMA MIGRACAO DE DADOS
-----------------------------------------------
A mesma decisao do `semear_areas` do forum e do `semear_economia` da
gamificacao, pelo mesmo motivo medido la: migracao de dados entra no banco de
TODO teste, e uma fixture que criasse um parametro colidiria com o teste que
mede a tabela vazia. Semear e CONTEUDO, nao esquema.

E ha a razao de dono: a partir do momento em que estas linhas existem, elas sao
do mantenedor. Uma migracao as recriaria em todo ambiente novo, inclusive as que
ele tivesse mudado de proposito.

IDEMPOTENTE, E QUE NAO PISA EM CIMA DE EDICAO HUMANA
-----------------------------------------------------
A conferencia e por CHAVE, nao pela linha da semente: se a chave ja tem qualquer
linha neste site, o comando nao acrescenta nada. Um `get_or_create` pela linha
inteira reinstalaria o valor de fabrica ao lado da mudanca do mantenedor, e a
mais nova venceria; como a tabela e append-only, nao haveria como desfazer.

E O QUE NAO E PARAMETRO, DE PROPOSITO
--------------------------------------
Preco, taxa e moeda NAO estao aqui: sao as decisoes pendentes 1 e 2 do plano, e
vivem onde o dinheiro vive, na celula `pagamentos`, quando o mantenedor disser
que o site vai vender (lei secao 3.4). Uma chave de preco nesta tabela seria
dinheiro morando na celula errada, que e o criterio de morte 3.
"""

from datetime import datetime, timezone

from django.core.management.base import BaseCommand

from apps.encomendas.models import CHAVES_DE_PARAMETRO, Parametro

# O comeco dos tempos desta celula. Instante fixo, e no passado, por duas
# razoes: a leitura e por `desde <= agora` (o valor vigente EM `agora`, lei
# secao 3.8), entao a semente precisa ja valer no primeiro segundo; e qualquer
# mudanca do mantenedor, sendo posterior, vence sem empate. Nao e valor de
# negocio, e por isso mora aqui e nao na tabela.
COMECO_DOS_TEMPOS = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

MOTIVO_DA_SEMENTE = (
    "Valor inicial da tabela da secao 6 da DECISAO-fila-do-primeiro-dolar.md, "
    "gravado pela semente da celula."
)

# Os 27 valores iniciais, na ordem da lei secao 6. A tabela da lei tem 19
# linhas porque varias juntam duas ou tres chaves numa celula so ("janela_inicio
# / janela_fim", "prazo_producao.simples / .vestivel_veiculo / .personagem"); as
# CHAVES distintas sao 27, e sao elas que o banco guarda. O despacho da TAR-120
# dizia 21, e a divergencia esta reportada: onde o despacho e a lei discordam,
# vence a lei.
VALORES_INICIAIS = {
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


class Command(BaseCommand):
    help = (
        "Semeia os parametros da Fila do Primeiro Dolar com os valores iniciais "
        "da lei. Idempotente: nao toca em chave que ja tem historico."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id que recebe as linhas (Lei 9: uma fabrica, N lojas)",
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"]

        # Falha ALTO se o catalogo e a semente discordarem, em vez de semear
        # 26 chaves e declarar sucesso. Uma chave nova no catalogo sem valor
        # inicial deixaria o motor lendo `None` para ela, e o `None` viraria um
        # padrao inventado no primeiro `or` que alguem escrevesse.
        faltando = sorted(set(CHAVES_DE_PARAMETRO) - set(VALORES_INICIAIS))
        sobrando = sorted(set(VALORES_INICIAIS) - set(CHAVES_DE_PARAMETRO))
        if faltando or sobrando:
            raise SystemExit(
                "PAROU POR SEGURANCA: o catalogo de chaves e a semente "
                f"discordam. Sem valor inicial: {faltando}. Fora do catalogo: "
                f"{sobrando}. Nada foi gravado."
            )

        novas, ja_tinham = 0, 0
        for chave, valor in VALORES_INICIAIS.items():
            if Parametro.objects.filter(site_id=site, chave=chave).exists():
                ja_tinham += 1
                continue
            Parametro.objects.create(
                site_id=site,
                chave=chave,
                valor=valor,
                desde=COMECO_DOS_TEMPOS,
                motivo=MOTIVO_DA_SEMENTE,
                quem="",
            )
            novas += 1

        self.stdout.write(
            f"parametros: {novas} semeada(s), {ja_tinham} ja tinha(m) historico "
            f"(site {site})."
        )
