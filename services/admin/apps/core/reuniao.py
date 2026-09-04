"""`/admin/reuniao/` — o modo reunião de segunda-feira (degrau 3 do plano).

A quarta disciplina das 4 Disciplinas da Execução é a cadência de
responsabilidade: uma reunião curta, toda semana, com pauta fixa, que termina
em compromissos. Os documentos do Scale OS (1.1 §96 a §105) pedem que a
reunião aconteça DENTRO do painel, em oito passos, e que no fim o sistema
grave decisões, tarefas e compromissos.

## Como isso vira desta casa, sem quebrar uma lei

1. **A pauta lê o placar, nunca outra montagem.** Os oito passos são o mesmo
   `montar_o_placar()` de `/admin/placar/` (as estrelas-guia, a meta, a
   direção, os compromissos, a restrição). O que ainda não tem fonte diz
   "sem dados até o degrau N", como a capa.
2. **Esta tela não escreve nada.** Nem no banco da `admin`, nem no livro. Um
   compromisso é um REGISTRO do livro (tipo `compromisso`, PR #942), e
   registro entra por PR, escrito por um robô. O que a reunião produz é **o
   pedido para o robô**: um bloco de texto, montado dos campos que o
   mantenedor preencheu no passo 8, para ele colar numa sessão. É o mesmo
   caminho que o painel do dono já usa para os diagnósticos ("um bloco
   copiável para colar numa sessão", `painel/LEIA-ME.md`), e o mesmo de
   `/admin/caixa/exportar/`: sem JavaScript (a porta manda `script-src
   'self'` e a célula não serve estático), um campo de texto que se seleciona
   com Ctrl+A.
3. **Sem escrita, sem auditoria a fazer.** A lei da `admin` (§4.3) exige
   linha de auditoria em toda ESCRITA. Aqui o POST calcula e devolve; o
   estado de ninguém muda. Recarregar a página apaga o que foi digitado, e
   isso é dito na tela: o que vale é o que chegar ao livro.
"""

from __future__ import annotations

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .placar import montar_o_placar

#: Os oito passos da pauta, na ordem do Scale OS 1.1 §98 a §105, traduzidos.
PASSOS = (
    (
        "estrelas",
        "As estrelas-guia",
        "30 segundos: onde a escola está, no longo prazo.",
    ),
    (
        "meta",
        "A meta e a direção",
        "Estamos ganhando? A barra do mês, a meta grande e as duas medidas da semana.",
    ),
    (
        "compromissos",
        "Os compromissos da semana passada",
        "Feito, parcial ou não feito: cada resposta é um registro que responde ao compromisso.",
    ),
    ("doze", "O placar de doze", "Só os desvios."),
    (
        "restricao",
        "A restrição desta semana",
        "Continua sendo a mesma? Se sim, aprofundar; se não, nomear a nova.",
    ),
    ("experimentos", "Os experimentos", "O que terminou, o que ensinou."),
    ("decisoes", "As decisões", "O que ficou decidido hoje."),
    ("novos", "Os compromissos novos", "Um ou dois por pessoa, nunca quinze."),
)

#: O prazo padrão de um compromisso: a semana.
VENCE_EM_DIAS = 7

#: Quantos compromissos novos a pauta aceita por reunião (Scale OS 2 §74:
#: "1 a 2 compromissos de alto impacto; não lista de 15 tarefas").
MAXIMO_DE_COMPROMISSOS = 2


def montar_o_pedido(campos: dict, hoje, foto: str | None = None) -> str | None:
    """O bloco para colar numa sessão de robô. `None` se não há o que pedir.

    `foto` é a linha `cartao=valor; ...` do placar de agora (degrau 6). Ela
    entra no pedido quando o passo 8 tem "tirar a foto" marcado: é assim que
    o placar ganha memória sem célula de medição, e o registro que a grava é
    o de sempre (tipo `medicao`, campo `foto`).
    """
    compromissos = [
        campos.get(f"compromisso{i}", "").strip()
        for i in range(1, MAXIMO_DE_COMPROMISSOS + 1)
    ]
    compromissos = [c for c in compromissos if c]
    decisoes = campos.get("decisoes", "").strip()
    aprendemos = campos.get("aprendemos", "").strip()
    confirmar = campos.get("confirmar_restricao", "").strip()
    tirar_foto = bool(campos.get("tirar_foto")) and bool(foto)
    if not (compromissos or decisoes or aprendemos or confirmar or tirar_foto):
        return None
    linhas = [
        f"Reunião de segunda-feira do painel de gestão, {hoje.strftime('%d/%m/%Y')}.",
        "Registre no livro de ocorrências (painel/registros/), um registro por item,",
        "pelo rito de sempre (PR com o registro a bordo; molde em painel/LEIA-ME.md):",
        "",
    ]
    for c in compromissos:
        linhas += [
            f"- COMPROMISSO (tipo `compromisso`, vence_em_dias: {VENCE_EM_DIAS}, frente: vender,",
            f"  autoridade: mantenedor): {c}",
        ]
    if confirmar:
        linhas += [
            "- RESTRIÇÃO CONFIRMADA (tipo `decisao`, autoridade: mantenedor):",
            f"  a restrição desta semana é {confirmar}. Grave `confirmada` no cartão",
            "  painel/cartoes/restricao-da-semana.json com a etapa, a data e o registro.",
        ]
    if decisoes:
        linhas += [
            "- DECISÃO (tipo `decisao`, autoridade: mantenedor):",
            f"  {decisoes}",
        ]
    if aprendemos:
        linhas += [
            "- APRENDIZADO (tipo `nota`, ou armadilha se for classe nova):",
            f"  {aprendemos}",
        ]
    if tirar_foto:
        linhas += [
            "- FOTO DA SEMANA (tipo `medicao`, autoridade: sessao, evidencia: o link",
            f"  do PR, verificado_em: {hoje.isoformat()}), com o campo `foto` exatamente assim:",
            f'  foto: "{foto}"',
            "  Título: 'Foto da semana do placar de gestão'. É o que o placar compara",
            "  na próxima segunda para dizer o que mudou.",
        ]
    linhas += [
        "",
        "Compromisso da semana passada cumprido: registro tipo `resposta` com",
        "`responde_a` apontando para o arquivo do compromisso. O veredito é calculado.",
    ]
    return "\n".join(linhas)


@require_http_methods(["GET", "POST"])
def reuniao(request):
    """A pauta guiada. GET mostra os oito passos; POST devolve o pedido para o robô."""
    hoje = timezone.localdate()
    contexto = montar_o_placar(hoje)
    campos = request.POST if request.method == "POST" else {}
    foto = (contexto.get("mudancas") or {}).get("foto_de_hoje")
    pedido = montar_o_pedido(campos, hoje, foto) if request.method == "POST" else None
    return render(
        request,
        "admin/reuniao.html",
        {
            "admin": request.admin,
            **contexto,
            "passos": PASSOS,
            "campos": campos,
            "pedido": pedido,
            "montou": request.method == "POST",
            "vence_em_dias": VENCE_EM_DIAS,
        },
    )
