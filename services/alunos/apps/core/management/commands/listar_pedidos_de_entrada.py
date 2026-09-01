"""Quem pediu entrada nesta escola, e em que pé está o pedido de cada um.

Esta célula é a única que sabe responder isso, e ela responde por E-MAIL: a
`Matricula` identifica a pessoa por endereço, e não existe `id_da_plataforma`
aqui. Quem precisa da resposta traduzida em id opaco pergunta à `identidade` do
seu lado (é o que `conceder_fundador`, da `gamificacao`, faz com a saída deste
comando). A tradução não mora aqui de propósito: esta célula não consome a
`identidade` para nada, e puxá-la para dentro por causa de uma lista seria uma
dependência nova, com senha de máquina nova, para uma pergunta de leitura.

SOMENTE LEITURA, E ISSO É O DESENHO
------------------------------------
Nenhuma escrita, nenhuma rede, nenhum efeito. Ele existe para ser lido antes de
uma decisão e para alimentar outro comando, e as duas coisas ficam mais seguras
quando rodar não muda nada. Rodar de novo dá a mesma resposta.

DUAS PLATEIAS, UM COMANDO SÓ
-----------------------------
Uma pessoa lendo precisa de nome, e-mail e situação, agrupados e contados. Outro
comando precisa de uma coluna limpa de e-mails, sem cabeçalho e sem resumo, para
consumir com `$(...)` num script. São dois formatos da MESMA verdade, e por isso
uma opção (`--formato`), nunca dois comandos: dois comandos seriam duas consultas
que um dia discordariam sobre quem está na lista, e a divergência apareceria
como gente recebendo o que não devia.

A UNIDADE DA LISTA É A PESSOA, NÃO A MATRÍCULA
-----------------------------------------------
A mesma pessoa pode ter várias matrículas no mesmo site (uma por curso é o
normal). Listá-la duas vezes daria um total que não bate com a quantidade de
gente, e número que não bate ensina a ignorar o relatório. Então a lista é por
pessoa, deduplicada pelo e-mail em caixa baixa, e a situação mostrada é a do
pedido MAIS RECENTE dela.

Caixa baixa só para COMPARAR: o e-mail impresso é o que está gravado. Quem é
dono da forma canônica de um e-mail é a `identidade`, e reescrever o dado alheio
na saída criaria uma segunda verdade sobre o endereço da pessoa.

ELE NÃO DECIDE QUEM MERECE NADA
--------------------------------
O comando não tem situação preferida e não esconde ninguém por conta própria:
sem `--exceto`, ele lista todo mundo que pediu entrada. Quem decide quem entra
numa concessão é quem chama, e a política fica escrita lá, em um lugar só
(`infra/conceder-fundador-aos-alunos.sh` documenta a dele em português).

`--exceto` recusa situação que o modelo não declara, e essa recusa é a peça mais
importante daqui. Um `--exceto recusadas` (com o "s" a mais) seria aceito em
silêncio por um filtro tolerante, não excluiria ninguém, e o resultado seria uma
lista maior do que quem a leu imaginava. Filtro que erra para o lado de incluir
gente precisa falhar alto.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.matriculas.models import Matricula

FORMATO_PESSOAS = "pessoas"
FORMATO_EMAILS = "emails"

# A ordem de `STATUS_CHOICES` é a ordem em que os grupos saem na tela. Ela vem do
# modelo, e não de uma lista própria daqui: uma segunda lista de situações
# esqueceria a próxima que nascer, e o grupo dela sumiria da saída sem erro.
SITUACOES = tuple(nome for nome, _ in Matricula.STATUS_CHOICES)


def situacoes_pedidas(cruas: list[str] | None) -> list[str]:
    """As situações pedidas, sem espaço, sem vazio e sem repetida.

    `--exceto recusada,encerrada` e `--exceto recusada --exceto encerrada` são a
    mesma coisa. Quem escreve a linha está lendo um cabeçalho de script, não a
    documentação do argparse, e exigir a forma certa de separar transformaria um
    gesto de um minuto num erro de digitação.
    """
    vistas: dict[str, None] = {}
    for pedaco in cruas or []:
        for parte in pedaco.split(","):
            limpa = parte.strip().lower()
            if limpa:
                vistas.setdefault(limpa, None)
    return list(vistas)


def uma_linha_por_pessoa(matriculas) -> dict[str, tuple[str, str, str]]:
    """Chave de comparação do e-mail para (e-mail gravado, nome, situação).

    Espera as matrículas em ordem CRESCENTE de chegada: a última a ser vista de
    cada pessoa vence, e é por isso que a situação exibida é a do pedido mais
    recente dela.
    """
    por_pessoa: dict[str, tuple[str, str, str]] = {}
    for matricula in matriculas:
        chave = matricula.email.strip().lower()
        por_pessoa[chave] = (
            matricula.email.strip(),
            matricula.name.strip(),
            matricula.status,
        )
    return por_pessoa


class Command(BaseCommand):
    help = (
        "Lista quem pediu entrada neste site, com a situação de cada pedido. "
        "Só lê: não escreve nada e não fala com ninguém."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id da escola cujos pedidos serão listados",
        )
        parser.add_argument(
            "--exceto",
            action="append",
            default=[],
            metavar="SITUACAO[,SITUACAO...]",
            help=(
                "deixa de fora quem SÓ tem pedido nestas situações; "
                "aceita vírgula e aceita repetir a opção"
            ),
        )
        parser.add_argument(
            "--formato",
            choices=[FORMATO_PESSOAS, FORMATO_EMAILS],
            default=FORMATO_PESSOAS,
            help=(
                "'pessoas' (padrão) para ler na tela, com nome e contagem; "
                "'emails' para outro comando consumir, um por linha e nada mais"
            ),
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"]
        excetuadas = situacoes_pedidas(opcoes["exceto"])

        desconhecidas = [s for s in excetuadas if s not in SITUACOES]
        if desconhecidas:
            # Fail-closed, e ele é o coração deste comando. Ver a docstring do
            # módulo antes de trocar esta recusa por um filtro tolerante.
            raise CommandError(
                "PAROU POR SEGURANÇA: não existe a situação "
                f"{', '.join(repr(s) for s in desconhecidas)} nesta escola. As "
                f"situações que existem são: {', '.join(SITUACOES)}. Um nome "
                "escrito errado não deixaria ninguém de fora, e a lista sairia "
                "maior do que você espera. Nada foi listado."
            )

        # Crescente de propósito: `uma_linha_por_pessoa` deixa vencer a última
        # que vê. O desempate por `id` existe porque `enrolled_at` é
        # `auto_now_add` e duas linhas criadas no mesmo instante empatariam,
        # deixando a ordem por conta do banco.
        todas = list(
            Matricula.objects.filter(site_id=site).order_by("enrolled_at", "id")
        )
        na_lista = uma_linha_por_pessoa(m for m in todas if m.status not in excetuadas)
        # Quem ficou de fora é quem NÃO tem nenhum pedido fora das situações
        # excluídas. A diferença importa: alguém com um pedido recusado e outro
        # ativo continua na lista, porque ela é sobre a pessoa e não sobre a
        # linha. A situação mostrada aqui vem do pedido mais recente de todos.
        de_fora = {
            chave: dados
            for chave, dados in uma_linha_por_pessoa(todas).items()
            if chave not in na_lista
        }

        if opcoes["formato"] == FORMATO_EMAILS:
            # Uma coluna e nada mais. Cabeçalho, total ou linha em branco aqui
            # viraria um "e-mail" na lista de quem consome a saída.
            for _, (email, _nome, _situacao) in sorted(na_lista.items()):
                self.stdout.write(email)
            return

        self.stdout.write(
            f"Pedidos de entrada no site {site!r}: {len(na_lista)} pessoa(s)."
        )
        for situacao in SITUACOES:
            do_grupo = sorted(
                (email, nome)
                for email, nome, atual in na_lista.values()
                if atual == situacao
            )
            self.stdout.write(f"  {situacao} ({len(do_grupo)}):")
            for email, nome in do_grupo:
                self.stdout.write(f"    {email}  {nome or 'sem nome'}")

        if excetuadas:
            # Grupo vazio sai na tela do mesmo jeito. Ele some justamente quando
            # é a notícia mais importante: "0 ficaram de fora" é o que diz a quem
            # lê que o filtro não tirou ninguém desta escola.
            self.stdout.write(
                f"  ficaram de fora, porque só têm pedido "
                f"{', '.join(excetuadas)} ({len(de_fora)}):"
            )
            for _, (email, nome, _situacao) in sorted(de_fora.items()):
                self.stdout.write(f"    {email}  {nome or 'sem nome'}")

        self.stdout.write(f"TOTAL na lista: {len(na_lista)} pessoa(s).")
