"""A rota que faz o servidor depor: `/admin/painel/diag.json`.

Existe porque ninguém entra na VPS (Lei 5) e ninguém vê o navegador do dono. Sem
isto, a única forma de saber o que acontece com a porta é deduzir lendo código —
que é exatamente como o incidente de 27/08/2026 foi diagnosticado, e por isso o
diagnóstico continua sendo hipótese e não medição.

Quem protege esta rota é a porta (`apps/core/porta.py`), como todas as outras:
ela NÃO está em `CAMINHOS_ISENTOS`. Os números são de dentro da casa.

Responde 200 mesmo com `erro` dentro, pelo mesmo motivo de `divida.py`: um 500
aqui faria o painel inteiro parecer quebrado por causa de uma medição auxiliar.
A tela lê o campo e mostra "não consegui medir", no lugar certo, sem derrubar o
resto.
"""

from __future__ import annotations

from django.http import JsonResponse
from django.views.decorators.http import require_safe

from . import medidor


@require_safe
def diag_json(request):
    """Os contadores em memória deste processo, para a aba Operação."""
    resposta = JsonResponse(medidor.leitura())
    resposta["Cache-Control"] = "no-store"
    return resposta
