"""Liga a ESCADA DE DEGRAUS de uma escola, e não encosta em mais nada.

POR QUE ESTE COMANDO EXISTE, E POR QUE ELE É TÃO ESTREITO
---------------------------------------------------------
A economia inteira nasce desligada (`semear_economia`), e ligar é decisão do
mantenedor (lei §10.5). Para as REGRAS de pontuação e para as CONQUISTAS ele já
tem interruptor próprio em `/admin/economia/`; para os DEGRAUS não há botão
nenhum, e enquanto não houver a tela do aluno não tem escada para mostrar.

Decisão dele em 01/09/2026, depois de ver `/conquistas` dizendo "Nível 1" e
"você chegou ao último degrau" na mesma tela: **ligar os degraus agora, pelo
pipeline, e ganhar o interruptor na tela em seguida.** Este comando é a primeira
metade — o braço da decisão, não a decisão.

**Ele liga NIVEL, e só NIVEL.** Regra de pontuação, missão, conquista, liga e
cosmético não são tocados nem por engano, e há teste afirmando isso. A diferença
não é preciosismo: degrau não paga nada, é só a régua com que o XP é lido. Uma
regra ligada muda quanto a escola PAGA, e essa continua sendo uma decisão de uma
tela, uma de cada vez, com data.

O QUE ELE RECUSA FAZER, e por quê
---------------------------------
- **Escola sem degrau nenhum:** ligar zero linhas e dizer "OK" seria falso-verde
  puro. Para com "PAROU POR SEGURANÇA" e manda semear antes.
- **Escada de um degrau só:** com um degrau ligado não há para onde subir, e a
  tela do aluno diz "o degrau seguinte ainda não abriu" (`armadilhas/271`). Quem
  rodou isto esperando ver uma escada acharia que o comando falhou. Então ele
  exige pelo menos DOIS, e explica.

Idempotente: rodar duas vezes não muda nada na segunda. Desligar é o gesto
inverso e NÃO mora aqui — ele nasce na tela, que é onde um gesto reversível deve
morar.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.gamificacao.models import (
    ConquistaDefinicao,
    ItemCosmetico,
    LigaDefinicao,
    MissaoDefinicao,
    NivelDefinicao,
    RegraDePontuacao,
)

# Menos que isto não é escada: é um degrau solto, e a tela do aluno diz
# exatamente isso. Ver `Escada.no_topo` em `apps/core/perfil.py`.
MINIMO_DE_DEGRAUS = 2


class Command(BaseCommand):
    help = "Liga todos os degraus (NivelDefinicao) de um site. Não toca em mais nada."

    def add_arguments(self, parser):
        parser.add_argument(
            "--site",
            required=True,
            help=(
                "O site_id da escola. Tem de ser EXATAMENTE o `SITE_ID` do "
                "contêiner da gamificação: ligar degraus de outro site cria uma "
                "escada que existe no banco e não aparece para ninguém."
            ),
        )

    def handle(self, *args, **opcoes):
        site = opcoes["site"].strip()
        if not site:
            raise CommandError("PAROU POR SEGURANÇA: --site veio vazio.")

        degraus = NivelDefinicao.objects.filter(site_id=site).order_by("nivel")
        total = degraus.count()
        if total == 0:
            raise CommandError(
                "PAROU POR SEGURANÇA: não há nenhum degrau cadastrado no site "
                f"{site!r}. Rode `semear_economia --site {site}` antes: ligar "
                "coisa nenhuma e dizer OK seria mentira verde."
            )
        if total < MINIMO_DE_DEGRAUS:
            raise CommandError(
                f"PAROU POR SEGURANÇA: o site {site!r} tem só {total} degrau "
                "cadastrado. Com um degrau não há para onde subir, e a tela do "
                "aluno vai dizer que o degrau seguinte ainda não abriu — quem "
                "rodou isto esperando uma escada acharia que falhou."
            )

        ja_ligados = degraus.filter(ativa=True).count()
        ligados_agora = degraus.filter(ativa=False).update(ativa=True)

        self.stdout.write(f"  degraus no site {site} ......... {total}")
        self.stdout.write(f"  já estavam ligados ............ {ja_ligados}")
        self.stdout.write(f"  ligados agora ................. {ligados_agora}")

        # A conferência que importa para quem lê o log: nada além da escada se
        # mexeu. Ela é feita DEPOIS do UPDATE, contando no banco — não é a
        # repetição de uma promessa escrita acima.
        for modelo, nome in (
            (RegraDePontuacao, "regras de pontuação"),
            (MissaoDefinicao, "missões"),
            (ConquistaDefinicao, "conquistas"),
            (LigaDefinicao, "ligas"),
            (ItemCosmetico, "cosméticos"),
        ):
            ativas = modelo.objects.filter(site_id=site, ativa=True).count()
            self.stdout.write(f"  {nome:22s} ligadas: {ativas}")

        restantes = degraus.filter(ativa=False).count()
        if restantes:
            raise CommandError(
                f"PAROU POR SEGURANÇA: sobraram {restantes} degrau(s) desligado(s) "
                "depois do UPDATE. Não posso afirmar que a escada está de pé."
            )

        # A linha que o pipeline procura. Só existe aqui, no fim do caminho
        # feliz, e nunca no eco do script que chama este comando
        # (`armadilhas/114`).
        self.stdout.write("ESCADA DE DEGRAUS LIGADA OK")
