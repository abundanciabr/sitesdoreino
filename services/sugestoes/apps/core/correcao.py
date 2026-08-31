# apps/core/correcao.py
"""Corrigir o que o aluno escreveu — o nome da ideia e o texto dela.

Lei do assunto: `docs/decisoes/DECISAO-corrigir-o-texto-de-uma-ideia.md`
(31/08/2026, decisão do mantenedor). Ele trouxe o caso: um aluno escreveu
"turorial" no nome de duas sugestões, e não havia em lugar nenhum do site onde
consertar. As duas perguntas foram decididas por ele, por pergunta estruturada:

1. **O que dá para corrigir:** o nome E o texto (`problema`, `solucao_proposta`).
   Corrigir só o nome deixaria o mesmo erro de digitação vivo três linhas
   abaixo, dentro do texto, sem caminho nenhum para consertá-lo.
2. **O aluno não vê marca nenhuma.** Correção calada, na tela dele. O rastro
   existe inteiro, e mora onde só a equipe alcança: a `CorrecaoDeTexto`,
   append-only nos três degraus, guardando o texto anterior palavra por palavra.

**Por que a regra mora aqui, e não no corpo do endpoint.** Mesma lição de
`apps/core/apagamento.py`: enquanto existe UM chamador, escrever a regra dentro
dele parece igual — e deixa de ser no dia em que nasce o segundo (lá foi o
comando que esvazia a Caixa). Aqui o segundo chamador plausível já tem nome: uma
correção em massa por `manage.py`, no dia em que o mantenedor quiser trocar uma
palavra em várias ideias de uma vez. Um módulo próprio faz esse caminho futuro
herdar por construção as quatro travas abaixo.

AS TRAVAS, E POR QUE CADA UMA
------------------------------
* **Ideia apagada não se corrige.** `DECISAO-apagar-ideia.md` promete que o
  conteúdo não existe mais em lugar nenhum; escrever um título novo nela seria
  ressuscitar a linha por outra porta, e a `CorrecaoDeTexto` guardaria como
  "antes" um vazio que não é o que a pessoa tinha escrito.
* **As mesmas réguas da criação** (`apps/core/participacao.py::nova_sugestao`):
  título obrigatório e de até 140 caracteres, problema obrigatório. Uma régua
  mais frouxa aqui deixaria a equipe gravar, por uma porta lateral, uma ideia
  que o aluno não conseguiria ter criado — e o título passaria de 140 direto
  para o `CharField`, que trunca em silêncio no Postgres... ou estoura, conforme
  o banco. Nenhum dos dois é resposta.
* **"Nada mudou" é recusa, não sucesso mudo.** Salvar o formulário sem ter
  tocado em nada devolveria "Pronto, corrigido" tendo gravado zero linhas —
  falso-verde de produto (`RETROSPECTIVA-FASE-D` §1), a mesma doença que a
  nota da avaliação já curou nesta casa quando parou de arredondar em silêncio.
* **Uma linha de rastro por campo alterado**, na MESMA transação da escrita. Se
  o rastro pudesse ficar para trás, a única cópia do texto original sumiria
  exatamente na hora em que ele deixou de existir na `Sugestao`.
"""

from django.db import transaction

from apps.sugestoes.models import CorrecaoDeTexto

# Os três campos que a escola pode corrigir, na ordem em que a tela os mostra.
# Nomes iguais aos da `Sugestao` de propósito (ver `CorrecaoDeTexto.Campo`):
# quem escreve usa `setattr`, quem lê usa `getattr`, e não existe mapa de
# tradução para envelhecer.
CAMPOS = ("titulo", "problema", "solucao_proposta")

TAMANHO_MAXIMO_DO_TITULO = 140


class CorrecaoInvalida(Exception):
    """Correção recusada ANTES de qualquer escrita.

    Recusa não precisa de rollback, e a mensagem é em português porque quem lê
    é gente — a mesma forma do `ChangeSpecInvalido`: `args[0]` é uma LISTA de
    frases, para quem preenche o formulário não descobrir um problema por vez.
    """


def _conferir(sugestao, textos: dict) -> dict:
    """Tudo que precisa ser verdade antes de a `Sugestao` mudar de texto."""
    erros = []

    if sugestao.apagada_em is not None:
        # Sozinha: as outras frases falariam de um texto que não existe mais.
        raise CorrecaoInvalida(
            [
                "Esta ideia foi apagada definitivamente — não há texto para "
                "corrigir, e escrever um novo aqui traria de volta o que a "
                "decisão de apagar promete ter destruído."
            ]
        )

    limpos = {campo: (textos.get(campo) or "").strip() for campo in CAMPOS}

    if not limpos["titulo"]:
        erros.append(
            "O nome da ideia não pode ficar vazio — é ele que aparece na lista "
            "para todo mundo."
        )
    elif len(limpos["titulo"]) > TAMANHO_MAXIMO_DO_TITULO:
        erros.append(
            f"O nome precisa caber em {TAMANHO_MAXIMO_DO_TITULO} caracteres, "
            "a mesma régua de quando o aluno escreveu."
        )

    if not limpos["problema"]:
        erros.append(
            "O texto do problema não pode ficar vazio — é o que os outros "
            "alunos leem antes de votar."
        )

    if erros:
        raise CorrecaoInvalida(erros)

    mudancas = {
        campo: valor
        for campo, valor in limpos.items()
        if valor != getattr(sugestao, campo)
    }
    if not mudancas:
        raise CorrecaoInvalida(
            [
                "Não havia nada para mudar: o texto enviado é igual ao que já "
                "estava gravado. Nada foi corrigido, e nenhum registro foi "
                "criado."
            ]
        )
    return mudancas


def corrigir(*, sugestao, por, **textos) -> list[CorrecaoDeTexto]:
    """O único caminho de escrita do texto de uma ideia. Devolve o que mudou.

    `por` é a `Identidade` de quem corrigiu — sempre alguém, ao contrário do
    apagamento, que aceita `None` porque um passo de pipeline não é uma pessoa.
    Aqui o gesto é de gente por definição: correção é alguém lendo e decidindo
    que aquilo está errado.
    """
    mudancas = _conferir(sugestao, textos)

    registros = []
    with transaction.atomic():
        for campo, valor in mudancas.items():
            # `create()` linha a linha, e não `bulk_create`: são três no pior
            # caso, e o caminho de uma linha por vez é o que passa pelo
            # `save()` do `RegistroAppendOnly` — o primeiro dos três degraus.
            # Trocar isso por uma gravação em lote economizaria duas consultas
            # e pularia o degrau, que é o oposto do que esta tabela existe para
            # garantir.
            registros.append(
                CorrecaoDeTexto.objects.create(
                    sugestao=sugestao,
                    campo=campo,
                    antes=getattr(sugestao, campo),
                    depois=valor,
                    corrigido_por=por,
                )
            )
            setattr(sugestao, campo, valor)
        # `update_fields` com só o que mudou: gravar os três sempre faria um
        # `UPDATE` tocar colunas que ninguém pediu para tocar, e num model cujo
        # `save()` carrega a trava do ChangeSpec ([INV-SUG10]) é melhor que a
        # gravação diga exatamente o que ela é.
        sugestao.save(update_fields=list(mudancas))

    return registros
