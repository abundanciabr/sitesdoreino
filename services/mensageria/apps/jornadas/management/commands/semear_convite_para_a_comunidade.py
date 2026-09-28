"""Semeia o convite para a Comunidade COMO DADO, versionado, desligado.

Rodada 2 da Comunidade Meshcraft, frente R2-8 (COM-02 e COM-06): o problema é
um aluno que fecha um Bloco do curso e não sabe que a Comunidade existe — esta
sequência vai buscar essa pessoa, no molde exato de
`semear_convite_para_a_prancheta.py`.

O MESMO GATILHO DA PRANCHETA, DE PROPÓSITO
-------------------------------------------
`aula.concluida` com `e_boss` verdadeiro: o Bloco fechado, o mesmo fato
declarado (nunca contagem) que abre o convite para a Prancheta. Nenhum código
muda em `apps/eventos/handlers.py`: `ao_aula_concluida` já itera TODAS as
jornadas ativas com esse gatilho (`Jornada.objects.filter(gatilho=...)`), então
uma segunda jornada com o mesmo gatilho é pega sem tocar o handler.

NÃO CHEGA NO MESMO INSTANTE QUE O CONVITE PARA A PRANCHETA
------------------------------------------------------------
As duas jornadas são inscritas na MESMA chamada do handler (mesmo evento,
mesmo `ancora_em`), e o cronograma é `ancora_em + atraso` — nunca `agora +
atraso` (LICOES.md). O passo 1 da Prancheta tem `atraso=timedelta(0)`: se este
passo 1 também tivesse atraso zero, as duas cartas ficariam elegíveis no MESMO
instante e a mesma passada do motor as entregaria juntas, competindo pela
mesma vaga do teto diário. Por isso este passo 1 nasce com `atraso=timedelta
(days=1)` — o convite chega um dia depois do marco, nunca junto com o da
Prancheta. Provado em teste (`test_o_convite_nao_chega_no_mesmo_instante_que_o_da_prancheta`).

O TEXTO SÓ FALA DO QUE JÁ EXISTE, E TRÊS COISAS FICAM DE FORA DE PROPÓSITO
----------------------------------------------------------------------------
`docs/comunidade/DOSSIE-TECNICO-FUNCIONAL-COMUNIDADE.md` (§16, §17) proíbe
inventar condição comercial, prometer renda e expor nome de membro — a mesma
régua que trava o texto da própria página em
`services/admin/tests/test_comunidade_no_banco.py`. Nenhuma frase daqui promete
renda, cita prazo ou nomeia um membro: o convite aponta para
`meshcraft.top/forum/comunidade`, a porta de entrada que continua aberta aos
alunos.

NASCE DESLIGADA, E ISSO NÃO É EXCESSO DE ZELO
----------------------------------------------
Sem `--ligar`, a jornada entra com `ativa=False` e não inscreve ninguém. Ligar
é decisão do mantenedor, na tela dele (`/admin/escola/jornadas/`), nunca efeito
colateral de um deploy.

IDEMPOTENTE POR CONSTRUÇÃO
--------------------------
Rodar duas vezes não cria duas jornadas nem duas versões, e rodar depois de a
versão estar publicada não muda uma vírgula dela: o banco recusa, porque versão
publicada é pedra (mesma regra de `semear_boas_vindas` e de
`semear_convite_para_a_prancheta`).
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.jornadas.models import Jornada, JornadaVersao, Passo, TextoDoPasso

SLUG = "convite-para-a-comunidade"
GATILHO = "aula.concluida"

# Dois passos: o convite no dia seguinte ao marco (nunca no mesmo instante que
# o da Prancheta, que usa atraso zero), e um lembrete curto uma semana depois.
# Sem condição, como no convite para a Prancheta e pelo mesmo motivo: a
# projeção `EstadoDoAluno` desta célula não sabe nada sobre Comunidade, e
# inventar uma condição que ela não consegue responder seria uma condição que
# mente. A régua de engajamento continua valendo por cima dos dois.
PASSOS = [
    {
        "ordem": 1,
        "atraso": timedelta(days=1),
        "classe": "relacional",
        "textos": {
            "pt-br": (
                "Você já pode entrar na Comunidade",
                "Você fechou um bloco do curso, e a Comunidade Meshcraft está "
                "aberta para você. Lá tem gente modelando os mesmos temas, "
                "fios por assunto e a experiência de quem já passou pelo "
                "curso. Entre pelo fórum em meshcraft.top/forum/comunidade.",
            ),
            "en": (
                "You can join the Community now",
                "You finished a block of the course, and the Meshcraft "
                "Community is open to you. There is people modeling the same "
                "subjects there, threads by topic, and the experience of "
                "those who already went through the course. Join the forum "
                "at meshcraft.top/forum/comunidade.",
            ),
            "es": (
                "Ya puedes entrar a la Comunidad",
                "Cerraste un bloque del curso, y la Comunidad Meshcraft está "
                "abierta para ti. Ahi hay gente modelando los mismos temas, "
                "hilos por asunto y la experiencia de quien ya paso por el "
                "curso. Entra por el foro en meshcraft.top/forum/comunidade.",
            ),
        },
    },
    {
        "ordem": 2,
        "atraso": timedelta(days=8),
        "classe": "engajamento",
        "textos": {
            "pt-br": (
                "A Comunidade continua aberta para você",
                "Se você ainda não entrou, a Comunidade Meshcraft segue "
                "esperando. Um bom começo é ler um fio de alguém que está no "
                "mesmo ponto do curso que você, em "
                "meshcraft.top/forum/comunidade.",
            ),
            "en": (
                "The Community is still open to you",
                "If you have not joined yet, the Meshcraft Community is "
                "still waiting. A good start is reading a thread from "
                "someone at the same point in the course as you, at "
                "meshcraft.top/forum/comunidade.",
            ),
            "es": (
                "La Comunidad sigue abierta para ti",
                "Si todavia no entraste, la Comunidad Meshcraft sigue "
                "esperando. Un buen comienzo es leer un hilo de alguien que "
                "esta en el mismo punto del curso que tu, en "
                "meshcraft.top/forum/comunidade.",
            ),
        },
    },
]


class Command(BaseCommand):
    help = "Semeia (e opcionalmente liga) o convite para a Comunidade de um site."

    def add_arguments(self, parser):
        parser.add_argument("--site-id", required=True)
        parser.add_argument(
            "--ligar",
            action="store_true",
            help="liga a jornada. Sem isto ela nasce DESLIGADA e nao convida ninguem.",
        )

    @transaction.atomic
    def handle(self, *args, **opcoes):
        site_id = opcoes["site_id"]
        jornada, criada = Jornada.objects.get_or_create(
            site_id=site_id, slug=SLUG, defaults={"gatilho": GATILHO, "ativa": False}
        )
        self.stdout.write(
            f"jornada {SLUG}@{site_id}: {'criada' if criada else 'ja existia'}"
        )

        versao = jornada.versoes.order_by("-numero").first()
        if versao is None:
            versao = JornadaVersao.objects.create(jornada=jornada, numero=1)
            self._plantar_passos(versao)
            JornadaVersao.objects.filter(pk=versao.pk).update(
                publicada_em=timezone.now()
            )
            self.stdout.write(f"versao 1 publicada com {len(PASSOS)} passo(s)")
        else:
            self.stdout.write(
                f"versao {versao.numero} ja existe; nada foi alterado "
                "(versao publicada e imutavel: para trocar o texto, publique uma nova)"
            )

        if opcoes["ligar"] and not jornada.ativa:
            Jornada.objects.filter(pk=jornada.pk).update(ativa=True)
            self.stdout.write(
                self.style.SUCCESS(
                    "jornada LIGADA: os proximos blocos fechados entram nela"
                )
            )
        elif not jornada.ativa:
            self.stdout.write(
                "jornada DESLIGADA (use --ligar quando quiser que ela comece a valer)"
            )
        else:
            self.stdout.write("jornada ja estava ligada")

    def _plantar_passos(self, versao):
        for molde in PASSOS:
            passo = Passo.objects.create(
                jornada_versao=versao,
                ordem=molde["ordem"],
                atraso=molde["atraso"],
                classe=molde["classe"],
                condicao_slug="",
                canais=["sino"],
            )
            for idioma, (assunto, corpo) in molde["textos"].items():
                TextoDoPasso.objects.create(
                    passo=passo,
                    idioma=idioma,
                    assunto_visivel=assunto,
                    corpo=corpo,
                )
