#!/usr/bin/env python3
"""Recarrega o ambiente da aplicação ativa e prova as entradas do site."""

from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sys


SERVICOS_ANTERIORES = {
    "abrir-a-sala-de-aula.sh": ("cursos", "cursos-relay"),
    "ligar-a-appmax.sh": ("pagamentos",),
    "por-a-chave-da-ia-do-admin.sh": ("admin",),
    "por-a-chave-da-ia-do-forum.sh": ("forum",),
    "provisionar-admin.sh": ("admin",),
    "provisionar-cursos.sh": ("identidade", "alunos"),
    "provisionar-email.sh": ("mensageria", "mensageria-consumer", "mensageria-huey"),
    "provisionar-encomendas.sh": ("identidade", "alunos", "admin", "encomendas", "encomendas-tique"),
    "provisionar-equipe-da-gamificacao.sh": ("gamificacao",),
    "provisionar-forum.sh": ("identidade", "alunos"),
    "provisionar-gamificacao.sh": ("identidade",),
    "provisionar-pages.sh": ("pages",),
    "provisionar-pares-da-prancheta.sh": ("identidade", "alunos", "catalogo", "pages"),
    "provisionar-sugestoes.sh": ("alunos",),
    "provisionar-aviso-de-liberacao.sh": ("identidade", "alunos", "alunos-relay"),
    "provisionar-aviso-no-celular.sh": ("funil", "notificacoes", "notificacoes-consumer"),
    "provisionar-par-da-caixa.sh": ("sugestoes", "admin"),
    "provisionar-par-da-economia.sh": ("gamificacao", "gamificacao-consumer", "admin"),
    "provisionar-par-da-gamificacao-com-o-forum.sh": ("forum", "gamificacao", "gamificacao-consumer"),
    "provisionar-par-da-gamificacao-com-os-alunos.sh": ("alunos", "identidade", "gamificacao"),
    "provisionar-par-da-medicao.sh": ("metricas", "admin"),
    "provisionar-par-do-forum-com-a-gamificacao.sh": ("gamificacao", "gamificacao-consumer", "forum"),
    "provisionar-par-do-funil-com-a-gamificacao.sh": ("gamificacao", "gamificacao-consumer", "funil"),
    "provisionar-par-do-menu.sh": ("catalogo", "admin", "forum", "sugestoes", "gamificacao"),
    "provisionar-par-do-portfolio-com-a-admin.sh": ("admin", "pages"),
    "provisionar-par-do-teste-de-aviso.sh": ("notificacoes", "notificacoes-consumer", "admin"),
    "provisionar-par-dos-parametros.sh": ("encomendas", "admin"),
    "provisionar-pares-da-sala-de-aula.sh": ("identidade", "alunos", "catalogo", "cursos", "admin"),
    "provisionar-pares-de-categorias.sh": ("alunos", "identidade", "admin", "funil"),
    "provisionar-porta-de-avisos.sh": ("funil", "sugestoes", "sugestoes-relay", "notificacoes", "notificacoes-consumer"),
    "provisionar-usuario-ponte.sh": (),
}


def recarregar(origem: str) -> int:
    caminho = Path(__file__).with_name("ativar-aplicacao.py")
    spec = importlib.util.spec_from_file_location("ativar_aplicacao", caminho)
    if spec is None or spec.loader is None:
        raise RuntimeError("ativador da aplicação ausente")
    ativador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ativador)

    if ativador.JOURNAL.is_file():
        estado = json.loads(ativador.JOURNAL.read_text(encoding="utf-8"))
        versao = estado["atual_versao"]
        ambiente = ativador.ambiente_da_aplicacao(
            versao["imagem"], Path(versao["codigo"])
        )
        alvos = ("aplicacao",)
    else:
        if origem not in SERVICOS_ANTERIORES:
            raise RuntimeError("origem do provisionador ausente para retorno anterior")
        ambiente = os.environ.copy()
        admin = ativador.RAIZ / "env" / "admin.env"
        if admin.is_file():
            for linha in admin.read_text(encoding="utf-8").splitlines():
                chave, _, valor = linha.partition("=")
                if chave in {"ALUNOS_API_TOKEN", "TOKEN_CATALOGO"} and valor:
                    ambiente[chave] = valor
        presentes = set(ativador.compose(
            "config", "--services", arquivo=ativador.RAIZ / "docker-compose.yml",
            override=ativador.PUBLICACOES / "imagens.json", ambiente=ambiente,
        ).splitlines())
        alvos = tuple(nome for nome in SERVICOS_ANTERIORES[origem] if nome in presentes)
    if alvos:
        ativador.compose(
            "up", "-d", "--force-recreate", "--wait", "--wait-timeout", "180",
            *alvos, arquivo=ativador.RAIZ / "docker-compose.yml",
            override=ativador.PUBLICACOES / "imagens.json", ambiente=ambiente,
        )
    ativador.provar_site()
    print("APLICACAO-RECARREGADA-E-PROVADA" if ativador.JOURNAL.is_file() else "CELULAS-ANTERIORES-RECARREGADAS-E-PROVADAS")
    return 0


def main() -> int:
    origem = sys.argv[1] if len(sys.argv) == 2 else ""
    return recarregar(origem)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, RuntimeError) as erro:
        print(f"ERRO: aplicação não recarregada/provada: {erro}", file=sys.stderr)
        sys.exit(1)
