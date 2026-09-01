"""A medalha de Fundador para quem já estava aqui no começo.

A gamificação nasceu depois da escola. Quem entrou primeiro passou meses sem
nada que dissesse "você estava aqui", e nenhum evento passado vai reaparecer
para contar isso: os eventos de XP só existem a partir do dia em que o motor
começou a escutar. O Fundador é a medalha que fecha esse buraco, e este comando
é o único caminho por onde ela sai.

ELE NÃO ESCREVE CONCESSÃO NOVA: ELE CHAMA A PORTA ÚNICA
--------------------------------------------------------
Quem cria uma `Concessao` neste projeto é `validacao.conceder()`, e só ela. Este
comando lê a lista, decide quem entra, e delega o gesto. Dois caminhos com dois
códigos dariam duas auditorias diferentes para a mesma pergunta, *quem disse que
sim?*, e é essa pergunta que precisa ter uma resposta só meses depois. De
quebra, é `conceder()` que credita os 25 Cristais, recalcula o perfil e escreve
a carta, tudo numa transação: repetir esse encadeamento aqui seria repetir a
chance de esquecer um pedaço dele.

A LISTA É ARGUMENTO, E ISSO NÃO É PREGUIÇA
-------------------------------------------
`--ids` é obrigatório porque **quem é fundador não é derivável desta célula**, e
tentar derivar daria uma resposta errada com cara de certa. Duas razões, as
duas medidas:

1. **O espelho `Pessoa` daqui é PREGUIÇOSO.** Uma linha só nasce no primeiro XP
   creditado ou na primeira visita a `/conquistas`. Perguntar à tabela local
   "quem estava aqui no começo?" responderia, na prática, "quem passou por aqui
   depois que a gamificação subiu", que é o contrário do que a medalha afirma.
2. **Quem sabe de matrícula é a célula `alunos`**, e a `gamificacao` não a
   consome de propósito (`celulas.yml` diz por quê). Puxá-la para dentro seria
   dependência nova, senha de máquina nova e um passo do mantenedor na VPS,
   tudo isso para responder a uma pergunta que se responde uma vez na vida.

A lista de quem estava no começo é conhecimento do mantenedor, não do banco.
Ela entra pela mão dele, e o comando só executa.

ELE RECUSA ENQUANTO A MEDALHA ESTIVER DESLIGADA, E ISSO É O DESENHO
---------------------------------------------------------------------
A economia inteira nasce `ativa=False` (`semear_economia`), porque nesta célula
a economia é DADO e ligá-la é decisão do mantenedor, com data, na tela dele em
`/admin/economia/`. Hoje, em produção, este comando vai mesmo recusar. **Isso
não é defeito e não se conserta.** Um agente futuro que "arrumar" esta recusa
estará dando a um comando de linha o poder de ligar economia por fora da tela
que existe para ligá-la, e a partir daí ninguém mais sabe responder quando a
medalha entrou no ar.

ENSAIO É O PADRÃO
------------------
Sem `--confirmo`, o comando só mostra o que faria. Um comando que escreve por
omissão é um comando que alguém roda por engano, e desfazer concessão é gesto
que não existe.

RE-EXECUTAR É SEGURO, E É O PONTO
----------------------------------
`Unique(pessoa, conquista)` no banco, dentro de `conceder()`. Rodar de novo não
concede duas medalhas, não credita 25 Cristais de novo e não escreve segunda
carta. É por isso que a lista pode chegar em pedaços, e que um id que faltava
pode ser acrescentado amanhã sem ninguém precisar lembrar o que já rodou.

Id que ainda não existe no espelho local é REPORTADO, nunca inventado: criar
`Pessoa` aqui a partir de um id opaco exigiria fabricar um e-mail, e um e-mail
fabricado é uma segunda verdade sobre quem é a pessoa, que é exatamente o que a
Lei 2 proíbe. A pessoa aparece no espelho sozinha, no primeiro XP ou na primeira
visita, e aí basta rodar o comando de novo.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from apps.gamificacao.models import Concessao, ConquistaDefinicao, Pessoa
from apps.gamificacao.validacao import conceder

# O slug é o mesmo que `semear_economia` planta. Constante e não literal solto
# porque o teste e o comando precisam ler a MESMA palavra: uma segunda expressão
# da mesma chave se desalinha no primeiro dia em que alguém mexer numa delas.
SLUG_DO_FUNDADOR = "fundador"


def ids_pedidos(cruas: list[str] | None) -> list[str]:
    """Os ids na ordem em que foram pedidos, sem espaço, sem vazio, sem repetido.

    `--ids a,b --ids c` e `--ids a --ids b --ids c` são a mesma coisa: quem monta
    a lista é uma pessoa copiando de uma planilha, e exigir que ela escolha a
    forma certa de separar seria transformar um gesto de um minuto num erro de
    digitação.

    Repetido sai porque a saída do ensaio é o que o mantenedor vai ler para
    decidir: uma lista que conta a mesma pessoa duas vezes dá um número que não
    bate com a realidade, e um número que não bate ensina a ignorar o relatório.
    """
    vistos: dict[str, None] = {}
    for pedaco in cruas or []:
        for parte in pedaco.split(","):
            limpo = parte.strip()
            if limpo:
                vistos.setdefault(limpo, None)
    return list(vistos)


class Command(BaseCommand):
    help = (
        "Concede a medalha de Fundador às pessoas de uma lista. "
        "Sem --confirmo, apenas mostra o que faria."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help="o site_id da escola que concede (Lei 9: uma fábrica, N lojas)",
        )
        # Sem `required=True` de propósito: a recusa escrita à mão explica POR QUE
        # a lista não é derivável, e essa explicação é a coisa mais importante
        # deste comando. A mensagem crua do argparse diria só que falta um
        # argumento, e quem a lesse iria procurar a consulta que não existe.
        parser.add_argument(
            "--ids",
            action="append",
            default=[],
            metavar="ID[,ID...]",
            help=(
                "os ids de pessoa da plataforma que recebem a medalha; "
                "aceita vírgula e aceita repetir a opção"
            ),
        )
        parser.add_argument(
            "--confirmo",
            action="store_true",
            help="executa de verdade (sem esta opção o comando só faz um ensaio)",
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"]
        ids = ids_pedidos(opcoes["ids"])
        if not ids:
            raise CommandError(
                "PAROU POR SEGURANÇA: nenhum id foi passado em --ids, e este "
                "comando não tem como descobrir sozinho quem é fundador. O "
                "espelho de pessoas desta célula só conhece quem já ganhou XP "
                "ou já abriu a página de conquistas, então perguntar a ele "
                "responderia 'quem chegou por último'. Quem estava aqui no "
                "começo é conhecimento seu: passe a lista, por exemplo "
                "--ids pessoa-1,pessoa-2."
            )

        try:
            conquista = ConquistaDefinicao.objects.get(
                site_id=site, slug=SLUG_DO_FUNDADOR
            )
        except ConquistaDefinicao.DoesNotExist as erro:
            raise CommandError(
                f"PAROU POR SEGURANÇA: não existe a conquista "
                f"{SLUG_DO_FUNDADOR!r} no site {site!r}. Ela nasce na semeadura "
                f"da economia: rode antes 'manage.py semear_economia --site "
                f"{site}'. Nada foi concedido."
            ) from erro

        if not conquista.ativa:
            # Fail-closed, e ele é o coração deste comando. Ver a docstring do
            # módulo antes de "consertar" esta recusa.
            raise CommandError(
                f"PAROU POR SEGURANÇA: a medalha {conquista.nome!r} ainda não "
                f"está ligada no site {site!r}. Ligar uma conquista é decisão "
                "do mantenedor, tomada na tela dele em /admin/economia/, e ela "
                "fica registrada com data. Um comando de linha não liga "
                "economia. Ligue a medalha por lá e rode este comando de novo. "
                "Nada foi concedido."
            )

        conhecidas = {
            pessoa.id_da_plataforma: pessoa
            for pessoa in Pessoa.objects.filter(id_da_plataforma__in=ids)
        }
        ja_tinham = set(
            Concessao.objects.filter(
                conquista=conquista, pessoa_id__in=ids
            ).values_list("pessoa_id", flat=True)
        )

        receberiam = [i for i in ids if i in conhecidas and i not in ja_tinham]
        repetidos = [i for i in ids if i in ja_tinham]
        desconhecidos = [i for i in ids if i not in conhecidas]

        self.stdout.write(f"Fundador no site {site!r}: {len(ids)} pessoa(s) na lista.")
        self._grupo("recebem a medalha", receberiam)
        self._grupo("já têm, e nada muda para elas", repetidos)
        self._grupo("não conheço esta pessoa ainda", desconhecidos)

        if not opcoes["confirmo"]:
            self.stdout.write(
                "ENSAIO: nada foi escrito no banco. Confira a lista acima e, se "
                "ela estiver certa, rode o mesmo comando com --confirmo."
            )
            return

        # A contagem sai do RETORNO de `conceder()`, nunca das listas calculadas
        # acima. Entre a consulta e a escrita alguém pode ter concedido a mesma
        # medalha pela tela, e um relatório que afirma "concedi 4" tendo criado 3
        # é falso-verde: o número precisa vir de quem fez o gesto.
        concedidas = 0
        mantidas = 0
        for id_da_pessoa in ids:
            pessoa = conhecidas.get(id_da_pessoa)
            if pessoa is None:
                continue
            # `validador_papel` fica no default `sistema`, e é o papel honesto:
            # este comando é a escola concedendo em bloco, não uma pessoa
            # olhando um caso. O banco recusa qualquer outro papel sem nome
            # (`concessao_humana_diz_quem_validou`), e inventar um nome aqui
            # daria à auditoria uma resposta falsa para "quem disse que sim?".
            _, nova = conceder(pessoa=pessoa, site_id=site, conquista=conquista)
            if nova:
                concedidas += 1
            else:
                mantidas += 1

        self.stdout.write(
            f"FEITO: {concedidas} medalha(s) concedida(s), "
            f"{mantidas} já existia(m), {len(desconhecidos)} pessoa(s) fora do "
            "espelho local. Rodar de novo é seguro e não concede duas vezes."
        )

    def _grupo(self, rotulo: str, ids: list[str]) -> None:
        """Uma linha por grupo, sempre, mesmo vazio.

        Grupo vazio some da tela quando a saída é condicional, e some justamente
        quando é a notícia mais importante: "0 recebem a medalha" é o que diz ao
        mantenedor que a lista dele já estava toda contemplada.
        """
        self.stdout.write(f"  {rotulo} ({len(ids)}): {', '.join(ids) or 'ninguém'}")
