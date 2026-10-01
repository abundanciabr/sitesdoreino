"""`manage.py conta_do_robo emitir|revogar|conferir` — a credencial do robô.

Ver `apps/core/conta_do_robo.py` para o desenho inteiro.

- `emitir`: sorteia uma credencial nova, grava SÓ o sha256 dela numa linha da
  auditoria e imprime o valor UMA vez, sozinho, no stdout. A anterior deixa de
  valer na hora. Recusa-se a imprimir num terminal: o valor vai pelo cano, da
  VPS direto para o cofre da máquina do mantenedor, sem passar pela tela:

      ssh sitesdoreino-vps 'docker exec $(docker ps -q --filter label=com.docker.compose.project=plataforma --filter label=com.docker.compose.service=admin | head -n1) python manage.py conta_do_robo emitir' | python ci/cofre.py guardar robo-admin

- `revogar`: acrescenta a linha de revogação. Nenhuma credencial vale até a
  próxima emissão.
- `conferir`: diz se há credencial vigente e desde quando. Nunca o valor.
"""

import secrets

from django.core.management.base import BaseCommand, CommandError

from apps.auditoria.models import Registro
from apps.core import conta_do_robo

QUEM = {"quem_email": "conta-do-robo@vps.invalid", "quem_id": "manage.py:conta_do_robo"}


class Command(BaseCommand):
    help = "Emite, revoga ou confere a credencial da conta do robô (nunca a mostra na tela)."

    def add_arguments(self, parser):
        parser.add_argument("acao", choices=("emitir", "revogar", "conferir"))

    def handle(self, *args, acao: str, **options):
        if acao == "emitir":
            self._emitir()
        elif acao == "revogar":
            self._revogar()
        else:
            self._conferir()

    def _emitir(self) -> None:
        if self.stdout.isatty():
            raise CommandError(
                "Recusado: a credencial sairia na tela. Rode pelo cano, direto "
                "para o cofre (ver o cabeçalho deste comando). Nada foi emitido."
            )
        credencial = secrets.token_urlsafe(32)
        Registro.objects.create(
            acao=Registro.EMITIR_CREDENCIAL_DO_ROBO,
            alvo=conta_do_robo.ALVO,
            desfecho=Registro.OK,
            detalhe=conta_do_robo.PREFIXO_DA_IMPRESSAO
            + conta_do_robo.impressao(credencial),
            **QUEM,
        )
        self.stdout.write(credencial)
        self.stderr.write(
            "conta_do_robo: credencial nova emitida; a anterior deixou de valer."
        )

    def _revogar(self) -> None:
        Registro.objects.create(
            acao=Registro.REVOGAR_CREDENCIAL_DO_ROBO,
            alvo=conta_do_robo.ALVO,
            desfecho=Registro.OK,
            **QUEM,
        )
        self.stdout.write("conta_do_robo: revogada; nenhuma credencial vale agora.")

    def _conferir(self) -> None:
        if conta_do_robo.impressao_vigente() is None:
            self.stdout.write("conta_do_robo: nenhuma credencial vigente.")
            return
        emitida = (
            Registro.objects.filter(
                alvo=conta_do_robo.ALVO, acao=Registro.EMITIR_CREDENCIAL_DO_ROBO
            )
            .order_by("-id")
            .values_list("quando", flat=True)
            .first()
        )
        self.stdout.write(
            f"conta_do_robo: vigente, emitida em {emitida:%Y-%m-%d %H:%M} UTC."
        )
