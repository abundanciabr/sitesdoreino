"""`/admin/mapa/` — o mapa do site inteiro, numa página só.

Pedido do mantenedor em 30/08/2026: *"crie um mapa completo do site no painel do
admin"*. A plataforma cresceu por partes — o site, o login, o fórum, a Caixa de
Sugestões, a compra, a área administrativa — e não havia nenhum lugar que
respondesse a pergunta mais simples de todas: **que endereços este site tem?**

## De onde vêm os dados — e por que esta célula NÃO os inventa

| O quê | De onde | Quem escreveu |
|---|---|---|
| O texto de cada endereço | `painel/mapa-do-site.json` | gente, uma entrada por rota |
| O endereço real, o alcance | o mesmo arquivo, **conferido** | `ci/mapa_do_site.py`, na muralha de todo PR |

A pasta `painel/` já viaja para dentro desta imagem (o `deploy-celula` copia a
pasta inteira — é o mesmo caminho por onde o painel do dono e o mapa para IA
chegam aqui), então este arquivo não precisa de passo de build próprio.

**Nada aqui é recalculado.** O endereço, o alcance e a existência de cada rota
são medidos pelo cartógrafo do CI a partir do roteamento do Traefik e dos
`urls.py` das 13 células — e o PR reprova se o mapa e o código discordarem, nos
dois sentidos. Recalcular aqui dentro seria a segunda definição do mesmo fato,
que é exatamente a lei anti-duplicação do `CLAUDE.md`: no dia em que as duas
divergissem, ninguém saberia qual está certa.

**Se o arquivo não vier, a página DIZ isso** (500 e uma frase clara), nunca um
mapa vazio. "Este site não tem endereço nenhum" seria a mentira mais convincente
que esta tela poderia contar — é o falso-verde do padrão 1 da
`RETROSPECTIVA-FASE-D`, na forma de uma tela em branco.

## Sem `{% static %}`, sem script, sem rota nova de arquivo

O estilo é o da própria área (`admin/base.html`), embutido. Célula sob
`SCRIPT_NAME` que serve estático por tag monta endereço da célula ERRADA
(`armadilhas/102`) — e uma página que é só texto e links não precisa de nada
disso.
"""

from __future__ import annotations

import json
from pathlib import Path

from django.shortcuts import render
from django.views.decorators.http import require_GET

from .painel import diretorio_do_painel

NOME_DO_ARQUIVO = "mapa-do-site.json"

# Os quatro públicos, na ordem em que a página os desenha — de fora para
# dentro: quem passa na rua, quem é da casa, você, e as máquinas. O vocabulário
# é o mesmo de `ci/mapa_do_site.py` (que o exige fechado): um valor novo aqui
# sem lá cairia num grupo inexistente, e a linha sumiria da tela sem erro.
GRUPOS = (
    (
        "visitante",
        "Para quem só visita",
        "Qualquer pessoa do mundo abre, sem entrar em nada.",
    ),
    (
        "aluno",
        "Para quem é aluno",
        "Precisa entrar com a conta — e, em algumas, ter o acesso liberado por você.",
    ),
    (
        "equipe",
        "Para você",
        "A área administrativa. Quem não está na sua lista de administradores "
        "recebe “não existe”, e não “você não pode”.",
    ),
    (
        "maquina",
        "Só para as máquinas",
        "Ninguém abre à mão: são as portas por onde as partes do site conversam "
        "entre si, e os sinais de vida que o servidor consulta sozinho.",
    ),
)

CHAVES = frozenset(chave for chave, _, _ in GRUPOS)


def arquivo_do_mapa() -> Path | None:
    """`painel/mapa-do-site.json`, na mesma pasta (embutida ou de checkout)."""
    pasta = diretorio_do_painel()
    if pasta is None:
        return None
    candidato = pasta / NOME_DO_ARQUIVO
    return candidato if candidato.is_file() else None


def _e_molde(endereco: str) -> bool:
    """Endereço com `<pedaço>` ou expressão regular vale para MUITOS endereços.

    `/forum/t/<int:topico_id>` não é um lugar: é a forma de todos os assuntos do
    fórum. A tela precisa saber disso para não oferecer um link que devolve 404.
    """
    return "<" in endereco or "(?P" in endereco


def _preparar(entrada: dict) -> dict:
    """Uma linha da tela, a partir de uma entrada do arquivo.

    O link só existe quando há para onde ir de verdade: endereço concreto, que a
    internet alcança, e que não é um gesto de botão. Um link que devolve 404 (ou
    que dispara uma ação!) é pior que nenhum link — o dono conclui que o site
    quebrou.
    """
    endereco = str(entrada.get("endereco", ""))
    exemplo = entrada.get("exemplo")
    gesto = bool(entrada.get("gesto"))
    publico = entrada.get("alcance") == "publico"
    molde = _e_molde(endereco)
    link = None
    if publico and not gesto:
        if isinstance(exemplo, str) and exemplo:
            link = exemplo
        elif not molde:
            link = endereco
    return {
        "titulo": entrada.get("titulo", ""),
        "descricao": entrada.get("descricao", ""),
        "observacao": entrada.get("observacao"),
        "endereco": endereco,
        "exemplo": exemplo,
        "link": link,
        "molde": molde,
        "gesto": gesto,
        "interno": not publico,
        "celula": entrada.get("celula", ""),
        "para_quem": entrada.get("para_quem", ""),
    }


@require_GET
def mapa_do_site(request):
    """A página. Agrupa por público, e separa as páginas dos gestos de botão."""
    caminho = arquivo_do_mapa()
    if caminho is None:
        return render(
            request,
            "admin/mapa_do_site.html",
            {"admin": request.admin, "mapa_ausente": True},
            status=500,
        )
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        entradas = [_preparar(e) for e in dados["enderecos"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        # Mesma lei da pasta ausente: um arquivo torto vira uma tela que diz
        # "não consegui ler o mapa", nunca um mapa pela metade.
        return render(
            request,
            "admin/mapa_do_site.html",
            {"admin": request.admin, "mapa_ausente": True},
            status=500,
        )

    grupos = []
    for chave, titulo, explicacao in GRUPOS:
        do_grupo = [e for e in entradas if e["para_quem"] == chave]
        paginas = [e for e in do_grupo if not e["gesto"]]
        gestos = [e for e in do_grupo if e["gesto"]]
        if not do_grupo:
            continue
        grupos.append(
            {
                "chave": chave,
                "titulo": titulo,
                "explicacao": explicacao,
                "paginas": paginas,
                "gestos": gestos,
                "total": len(do_grupo),
            }
        )

    return render(
        request,
        "admin/mapa_do_site.html",
        {
            "admin": request.admin,
            "grupos": grupos,
            "total": len(entradas),
            # As três contas são DISJUNTAS e somam o total — é isso que faz a
            # capa desta página ser conferível de cabeça. A primeira versão
            # dizia "71 páginas para abrir" contando as 33 portas de máquina
            # junto: número certo, resposta errada para a pergunta que o dono
            # faz olhando o cartão ("quantas telas eu tenho?").
            "total_telas": sum(
                1 for e in entradas if not e["gesto"] and e["para_quem"] != "maquina"
            ),
            "total_gestos": sum(1 for e in entradas if e["gesto"]),
            "total_maquina": sum(
                1 for e in entradas if not e["gesto"] and e["para_quem"] == "maquina"
            ),
            "total_internos": sum(1 for e in entradas if e["interno"]),
            # As entradas que nenhum grupo acolheu. Zero hoje — o vocabulário é
            # fechado dos dois lados —, e a tela as mostra em voz alta se um dia
            # não for: linha que some sem erro é a pior forma de perder um fato.
            "orfas": [e for e in entradas if e["para_quem"] not in CHAVES],
        },
    )
