# apps/sugestoes/management/commands/semear_demo.py
"""Povoa a Caixa com ideias de vitrine — uma por status — e sabe desfazer.

POR QUE ESTE COMANDO EXISTE
---------------------------
Um quadro vazio não se avalia. Antes da inauguração de 31/08/2026 o mantenedor
precisou ver como a Caixa FICA cheia: as seis faixas do roadmap ocupadas, os
votos empilhados, o "em alta" com algo dentro. Sem dado, a única forma de
julgar a tela era imaginar — e imaginar não pega faixa vazia que quebra o
layout nem contador que não cabe na coluna.

O QUE ELE NÃO FAZ, E ISSO É DESENHO
------------------------------------
**Não cria uma única linha append-only.** Nem `HistoricoStatus` nem
`ChangeSpecAprovado`. As duas tabelas têm trigger `BEFORE UPDATE OR DELETE` no
Postgres (migrations `0001` e `0004`): uma linha dessas nasce imortal, e a
sugestão que a tivesse ficaria impossível de apagar — o `CASCADE` do Django
bateria no trigger e a demo viraria permanente. Por isso cada ideia nasce JÁ no
status final, por INSERT.

O INSERT é o caminho permitido de propósito: o trigger `sugestoes_exige_changespec`
é `BEFORE UPDATE OF status`, e a trava do `save()` (INV-SUG10) só olha
`not self._state.adding`. Criar em `em_desenvolvimento` não fura o corredor do
ChangeSpec — o corredor guarda a TRANSIÇÃO `planejado → em_desenvolvimento`,
que é onde o risco mora. Nada aqui transiciona.

COMO SE APAGA
-------------
`--remover` — e ele é o motivo de todo o resto ter a forma que tem. Tudo que
este comando cria pendura numa identidade de e-mail `@demo.invalid` (domínio
reservado pela RFC 2606: não resolve, não é de ninguém, não colide com aluno
real). Remover é achar essas identidades e desmontar de dentro para fora.

Se o mantenedor tiver mexido no status de uma ideia demo pelo painel, ela
GANHOU histórico append-only e não pode mais ser apagada. Nesse caso o comando
**arquiva** em vez de apagar — some do quadro do aluno do mesmo jeito
(`DECISAO-arquivar-ideia.md`) — e diz na tela quantas caíram nesse caminho.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.core.sessao import cunhar_ou_recuperar
from apps.sugestoes.models import (
    Categoria,
    Comentario,
    Identidade,
    Quadro,
    Sugestao,
    Voto,
)

# O domínio que marca TUDO que este comando cria. RFC 2606 reserva `.invalid`
# justamente para isto: nunca resolve, então nenhum e-mail daqui pode alcançar
# uma pessoa real, e nenhum aluno real pode nascer com um destes por engano.
DOMINIO_DEMO = "demo.invalid"

S = Sugestao.Status

# (titulo, categoria, status, votos, problema, solucao)
IDEIAS = [
    (
        "Calculadora de preço para modelos 3D",
        "carreira",
        S.EM_ANALISE,
        87,
        "Eu nunca sei quanto cobrar. Chuto um valor, o cliente aceita rápido "
        "demais, e aí eu sei que cobrei barato.",
        "Uma calculadora que pergunte horas, complexidade e tipo de cliente e "
        "devolva uma faixa de preço com um mínimo defensável.",
    ),
    (
        "Biblioteca de materiais prontos para Blender",
        "blender",
        S.EM_ANALISE,
        64,
        "Passo mais tempo refazendo material de madeira e metal do que "
        "modelando de verdade.",
        "Um pacote de materiais já configurados para exportar certo no Roblox, "
        "com preview.",
    ),
    (
        "Aula sobre retopologia para Roblox",
        "curso",
        S.EM_ANALISE,
        41,
        "Meus modelos ficam com contagem de polígono alta demais e o Roblox "
        "reclama na hora de subir.",
        "Uma aula só de retopologia, do sculpt pesado até a malha limpa.",
    ),
    (
        "Modo escuro na plataforma",
        "plataforma",
        S.EM_ANALISE,
        23,
        "Estudo de madrugada e a tela branca queima a vista.",
        "Um botão de tema escuro que lembre a escolha.",
    ),
    (
        "Checklist de otimização antes de subir pro Roblox",
        "roblox",
        S.EM_ANALISE,
        17,
        "Sempre esqueço alguma coisa e descubro só depois que o modelo já "
        "está no jogo.",
        "Uma lista curta de conferência: escala, pivô, textura, contagem de "
        "faces, nome das partes.",
    ),
    (
        "Gerador de portfólio automático",
        "ferramentas",
        S.PLANEJADO,
        112,
        "Não sei fazer site, então meu portfólio é uma pasta do Drive. "
        "Cliente nenhum leva isso a sério.",
        "Eu subo os renders, escolho um layout, e sai uma página com link "
        "próprio para mandar no chat.",
    ),
    (
        "Aula de rigging de personagem no Blender",
        "curso",
        S.PLANEJADO,
        58,
        "Sei modelar o personagem, mas na hora de fazer ele se mexer eu travo.",
        "Uma aula de rig do zero, terminando com o boneco andando dentro do "
        "Roblox Studio.",
    ),
    (
        "Modelo de contrato para trabalho freelance",
        "carreira",
        S.PLANEJADO,
        39,
        "Já tomei calote duas vezes. Combinei tudo por mensagem e não tinha "
        "nada escrito.",
        "Um contrato simples, em português, para preencher e mandar em PDF.",
    ),
    (
        "Conversor de textura para o padrão do Roblox",
        "ferramentas",
        S.EM_DESENVOLVIMENTO,
        76,
        "Minha textura fica linda no Blender e chega lavada no Roblox.",
        "Uma ferramenta que receba o arquivo e devolva já no tamanho e no "
        "formato que o Roblox espera.",
    ),
    (
        "Aula: do zero ao primeiro UGC aprovado",
        "curso",
        S.EM_DESENVOLVIMENTO,
        95,
        "Tentei mandar meu primeiro acessório e foi recusado sem eu entender "
        "o motivo.",
        "Uma aula que acompanhe um item inteiro, do rascunho até a aprovação, "
        "mostrando cada regra na prática.",
    ),
    (
        "Caixa de Sugestões",
        "plataforma",
        S.IMPLEMENTADO,
        134,
        "As ideias boas morriam no meio do grupo de mensagem e ninguém "
        "conseguia achar de novo.",
        "Um lugar dentro da plataforma para escrever, votar e acompanhar até "
        "a entrega.",
    ),
    (
        "Entrar com a conta do Google",
        "plataforma",
        S.IMPLEMENTADO,
        88,
        "Mais uma senha para esquecer.",
        "Botão de entrar com o Google, sem criar senha nova.",
    ),
    (
        "Aula sobre UV Mapping",
        "curso",
        S.IMPLEMENTADO,
        52,
        "Minhas texturas esticam nos cantos e eu não sei por quê.",
        "Uma aula de UV do começo, com os erros clássicos lado a lado.",
    ),
    (
        "Aplicativo de celular da plataforma",
        "plataforma",
        S.NAO_PLANEJADO,
        29,
        "Queria assistir as aulas no ônibus sem abrir o navegador.",
        "Um app na loja do Android e do iPhone.",
    ),
    (
        "Curso completo de programação em Lua",
        "curso",
        S.NAO_PLANEJADO,
        44,
        "Queria também programar o jogo, não só modelar.",
        "Uma trilha inteira de Lua dentro desta mesma plataforma.",
    ),
    (
        "Ferramenta que calcula quanto cobrar",
        "carreira",
        S.MESCLADO,
        12,
        "Não tenho ideia de preço e acabo aceitando qualquer valor.",
        "Algo que me diga uma faixa justa.",
    ),
]

# Quem escreve comentário. Os primeiros nomes da lista de identidades — o resto
# das identidades existe só para dar peso aos contadores de voto.
COMENTARIOS = {
    "Calculadora de preço para modelos 3D": [
        (0, "Isso aqui salvaria minha vida. Semana passada cobrei R$ 40 num "
            "trabalho que levou 11 horas."),
        (3, "Se der pra separar preço de UGC e preço de encomenda, melhor "
            "ainda — são mercados bem diferentes."),
    ],
    "Gerador de portfólio automático": [
        (1, "Perdi um freela porque mandei link do Drive e o cara nem abriu."),
        (5, "Queria que desse pra escolher a ordem dos trabalhos, não só a "
            "data."),
        (2, "+1. E se der pra ter um domínio meu depois, fecha."),
    ],
    "Aula: do zero ao primeiro UGC aprovado": [
        (4, "A parte de aprovação é a que ninguém explica direito no YouTube."),
    ],
    "Aplicativo de celular da plataforma": [
        (6, "Entendo o custo, mas o site no celular já funciona bem pra mim."),
    ],
}

NOMES = [
    "Ana", "Bruno", "Caio", "Duda", "Enzo", "Fê", "Gabi", "Heitor",
    "Isa", "João", "Kau", "Lele", "Miguel", "Nina", "Otto", "Pedro",
]


class Command(BaseCommand):
    help = "Ideias de vitrine na Caixa, uma por status — e --remover desfaz"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--remover",
            action="store_true",
            help="apaga tudo que este comando criou (ou arquiva, se já tiver histórico)",
        )

    def handle(self, *, site_id: str, remover: bool, **opts):
        if remover:
            return self._remover()
        return self._criar(site_id)

    # ---------------------------------------------------------------- criar --

    def _criar(self, site_id: str):
        quadro = Quadro.objects.filter(
            site_id=site_id, produto_id__isnull=True
        ).first()
        if quadro is None:
            raise CommandError(
                f"PAROU POR SEGURANÇA: não existe quadro para o site {site_id}. "
                "Rode `seed_sugestoes --site-id <id>` primeiro — é ele que "
                "inaugura o quadro e as categorias."
            )

        categorias = {c.slug: c for c in quadro.categorias.all()}
        faltando = {ideia[1] for ideia in IDEIAS} - set(categorias)
        if faltando:
            raise CommandError(
                "PAROU POR SEGURANÇA: o quadro não tem as categorias "
                f"{sorted(faltando)}. Rode `seed_sugestoes` para completá-las."
            )

        if Sugestao.objects.filter(autor__email__endswith=DOMINIO_DEMO).exists():
            self.stdout.write(
                self.style.WARNING(
                    "Já existem ideias de demonstração neste banco. "
                    "Rode com --remover antes de semear de novo."
                )
            )
            return

        quantos_votantes = max(ideia[3] for ideia in IDEIAS)
        with transaction.atomic():
            pessoas = self._pessoas(quantos_votantes)
            criadas = {}
            for n, (titulo, slug, status, votos, problema, solucao) in enumerate(IDEIAS):
                ideia = Sugestao.objects.create(
                    quadro=quadro,
                    categoria=categorias[slug],
                    autor=pessoas[n % len(NOMES)],
                    titulo=titulo,
                    problema=problema,
                    solucao_proposta=solucao,
                    status=status,
                )
                criadas[titulo] = ideia
                Voto.objects.bulk_create(
                    [
                        Voto(sugestao=ideia, autor=pessoa)
                        for pessoa in pessoas[:votos]
                    ]
                )

            # A mesclada aponta para a canônica — é o que a tela usa para dizer
            # "esta ideia virou aquela ali". Sem o ponteiro, `mesclado` aparece
            # como um beco sem saída.
            mesclada = criadas["Ferramenta que calcula quanto cobrar"]
            mesclada.sugestao_canonica = criadas[
                "Calculadora de preço para modelos 3D"
            ]
            mesclada.save(update_fields=["sugestao_canonica"])

            Comentario.objects.bulk_create(
                [
                    Comentario(
                        sugestao=criadas[titulo], autor=pessoas[quem], texto=texto
                    )
                    for titulo, falas in COMENTARIOS.items()
                    for quem, texto in falas
                ]
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ demo semeada: {len(IDEIAS)} ideias em "
                f"{len({i[2] for i in IDEIAS})} status, "
                f"{Voto.objects.filter(autor__email__endswith=DOMINIO_DEMO).count()} votos, "
                f"{Comentario.objects.filter(autor__email__endswith=DOMINIO_DEMO).count()} comentários, "
                f"{len(pessoas)} pessoas fictícias (@{DOMINIO_DEMO})."
            )
        )

    def _pessoas(self, quantas: int) -> list[Identidade]:
        """Identidades fictícias, pela MESMA porta que a entrada de verdade usa.

        `cunhar_ou_recuperar` é o único módulo autorizado a cunhar identidade
        nesta célula, e o teste-guarda `test_so_um_modulo_cunha_identidade…`
        recusa por AST qualquer segundo caminho. A razão dele é INV-SUG11: toda
        linha nova precisa nascer com `id_da_plataforma`, senão a pessoa some do
        endereçamento de avisos meses depois.

        Um comando de demo poderia ter pedido exceção na lista do invariante.
        Passar pela porta é melhor: as pessoas fictícias saem com a MESMA forma
        das de verdade — o que é justamente o ponto de uma vitrine — e o
        invariante fica intacto, sem uma segunda entrada para alguém alargar
        depois.
        """
        pessoas = []
        for n in range(quantas):
            email = f"aluno{n:03d}@{DOMINIO_DEMO}"
            # Fail-closed: o `--remover` encontra o que apagar SÓ pelo domínio.
            # Um e-mail fora dele seria uma pessoa fictícia imortal no banco.
            if not email.endswith(f"@{DOMINIO_DEMO}"):  # pragma: no cover
                raise CommandError(
                    f"PAROU POR SEGURANÇA: {email} está fora de @{DOMINIO_DEMO} "
                    "e o --remover não saberia apagá-la."
                )
            pessoas.append(
                cunhar_ou_recuperar(
                    email=email,
                    nome=f"{NOMES[n % len(NOMES)]} (demo)",
                    id_da_plataforma=f"demo-{n:03d}",
                )
            )
        return pessoas

    # -------------------------------------------------------------- remover --

    def _remover(self):
        pessoas = Identidade.objects.filter(email__endswith=DOMINIO_DEMO)
        if not pessoas.exists():
            self.stdout.write("Não há nada de demonstração neste banco.")
            return

        ideias = list(Sugestao.objects.filter(autor__in=pessoas))
        apagadas, arquivadas = 0, 0

        # Votos e comentários que pessoas fictícias deixaram em ideias DE
        # VERDADE não somem por cascade (a ideia não é delas). Vão primeiro,
        # senão o PROTECT do autor barra a remoção da identidade no fim.
        Comentario.objects.filter(autor__in=pessoas).delete()
        Voto.objects.filter(autor__in=pessoas).delete()

        for ideia in ideias:
            # Uma a uma, e não em massa: se UMA tiver ganhado histórico
            # append-only (o mantenedor mexeu no status pelo painel), o trigger
            # do Postgres recusa o cascade e derrubaria o lote inteiro junto.
            try:
                with transaction.atomic():
                    ideia.delete()
                apagadas += 1
            except Exception:
                with transaction.atomic():
                    ideia.arquivada_em = timezone.now()
                    ideia.motivo_do_arquivamento = (
                        "Ideia de demonstração, retirada do quadro. Não pôde "
                        "ser apagada porque já tinha histórico append-only."
                    )
                    ideia.save(
                        update_fields=["arquivada_em", "motivo_do_arquivamento"]
                    )
                arquivadas += 1

        # Só as identidades que não sobraram amarradas a nada arquivado.
        sobraram = Identidade.objects.filter(
            email__endswith=DOMINIO_DEMO, sugestoes__isnull=True
        ).distinct()
        quantas_pessoas = sobraram.count()
        sobraram.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ demo retirada: {apagadas} ideias apagadas, "
                f"{arquivadas} arquivadas (tinham histórico), "
                f"{quantas_pessoas} pessoas fictícias removidas."
            )
        )
        if arquivadas:
            self.stdout.write(
                "As arquivadas não aparecem mais no quadro do aluno — "
                "elas ficam fora de vista, e é isso que importa."
            )
