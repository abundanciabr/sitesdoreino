"""Pauta da Reunião e pedidos privados retomáveis, sem execução automática."""

from __future__ import annotations

import datetime as dt
import json
from uuid import uuid4

from django.core import signing
from django.db import DatabaseError
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from . import analista as analista_
from . import pedido_da_reuniao as pedidos
from . import fila_no_github, robos
from .models import Documento
from .placar import montar_o_placar, site_de

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


def _formulario(hoje, foto, admin):
    return signing.dumps(
        {
            "id": str(uuid4()),
            "dia": hoje.isoformat(),
            "foto": foto,
            "autor": admin["email"],
        },
        salt="reuniao-pauta",
    )


@require_http_methods(["GET", "POST"])
def reuniao(request):
    hoje = timezone.localdate()
    campos = request.POST if request.method == "POST" else {}
    pediram_o_analista = campos.get("acao") == analista_.ACAO
    erro, status = "", 200
    formulario = campos.get("formulario", "")
    original = None
    if request.method == "POST" and not pediram_o_analista:
        try:
            original = signing.loads(formulario, salt="reuniao-pauta")
            if original["autor"] != request.admin["email"]:
                raise signing.BadSignature("autor diferente")
            doc, _ = pedidos.salvar_inicial(
                original["id"],
                campos,
                dt.date.fromisoformat(original["dia"]),
                original["foto"],
                request.admin,
            )
            return redirect("pedido_reuniao", identidade=original["id"])
        except (signing.BadSignature, KeyError, ValueError) as exc:
            if isinstance(exc, pedidos.ConflitoDoPedido):
                erro, status = str(exc), 409
            else:
                erro, status = (
                    "A pauta não pôde ser identificada. Seu texto continua abaixo; confira e salve novamente.",
                    400,
                )
                formulario = ""
                original = None
        except DatabaseError:
            erro, status = (
                "Não consegui confirmar a gravação. Seu texto continua abaixo; repita Salvar pedido privado para recuperar o mesmo pedido.",
                503,
            )
    contexto = montar_o_placar(hoje, site_de(request))
    foto = (contexto.get("mudancas") or {}).get("foto_de_hoje")
    if original is not None:
        foto = original["foto"]
    if not formulario:
        formulario = _formulario(hoje, foto, request.admin)
    return render(
        request,
        "admin/reuniao.html",
        {
            "admin": request.admin,
            **contexto,
            "passos": PASSOS,
            "campos": campos,
            "formulario": formulario,
            "foto_da_pauta": foto,
            "erro_pedido": erro,
            "pedidos_salvos": Documento.objects.filter(
                nome__startswith=pedidos.PREFIXO, publico=False, arquivado=False
            ).order_by("-atualizado_em"),
            "montou": request.method == "POST" and not pediram_o_analista,
            "vence_em_dias": VENCE_EM_DIAS,
            "analista": analista_.para_a_tela(
                momento="reuniao",
                dossie=(
                    analista_.dossie_da_reuniao(contexto, hoje)
                    if pediram_o_analista
                    else ""
                ),
                hoje=hoje,
                pediram=pediram_o_analista,
            ),
        },
        status=status,
    )


def _publicado(envelope, remoto):
    pasta = robos.diretorio_da_fila()
    estados = robos.ler_estados(pasta)
    if estados is None:
        return {
            "detalhe": "Não consegui confirmar o que chegou ao site: a fila publicada está indisponível."
        }
    vinculos = [
        (tid, dado)
        for tid, dado in estados.items()
        if isinstance(dado.get("pedido"), dict)
        and dado["pedido"].get("id") == envelope["pedido"]["id"]
    ]
    if not vinculos:
        return {
            "detalhe": "Esta cópia da fila ainda não confirma o pedido no site. Ela pode ser anterior ao recebimento no ramo."
        }
    if len(vinculos) != 1:
        return {
            "erro": True,
            "detalhe": "Mais de uma tarefa está vinculada ao pedido. Peça ao robô para conferir a origem antes de continuar.",
        }
    tid, dado = vinculos[0]
    if (
        dado["pedido"] != envelope["pedido"]
        or any(
            type(dado["pedido"][campo]) is not int for campo in ("documento", "versao")
        )
        or (remoto and remoto.tarefa and remoto.tarefa != tid)
    ):
        return {
            "erro": True,
            "tarefa": tid,
            "detalhe": "A fila publicada contém outra versão deste pedido. Continue na mesma tarefa; esta versão não tem aplicação confirmada.",
        }
    grupo = next((g for g in robos.COLUNAS if robos.e_deste_grupo(dado, g)), None)
    resultado = {
        "tarefa": tid,
        "situacao": grupo["rotulo"] if grupo else "Estado não reconhecido",
        "detalhe": "A identidade da tarefa consta nesta cópia da fila. Resultado dos itens ainda não conferido.",
    }
    if remoto and remoto.artefatos:
        try:
            for caminho, conteudo in remoto.artefatos:
                arquivo = pasta / caminho.removeprefix("fila/")
                if (
                    not arquivo.resolve().is_relative_to(pasta.resolve())
                    or arquivo.read_bytes().replace(b"\r\n", b"\n") != conteudo
                ):
                    raise ValueError("artefato divergente")
        except (OSError, ValueError):
            resultado["detalhe"] = (
                "A identidade consta na fila, mas não consegui confirmar os mesmos artefatos na publicação. Resultado ainda não conferido."
            )
        else:
            resultado["detalhe"] = (
                "A tarefa e a explicação recebidas também constam nesta cópia publicada. Resultado dos itens ainda não conferido."
            )
    if dado.get("estado") == "concluída":
        resultado[
            "detalhe"
        ] += " A conclusão foi registrada na fila; isso não comprova aqui a aplicação de cada item."
    return resultado


@require_http_methods(["GET", "POST"])
def pedido_reuniao(request, identidade):
    doc = get_object_or_404(
        Documento,
        nome=pedidos.nome_do_pedido(identidade),
        publico=False,
        arquivado=False,
    )
    versao = doc.versoes.order_by("-pk").first()
    if versao is None:
        raise Http404
    texto, erro, status = doc.corpo, "", 200
    versao_editada = versao.pk
    if request.method == "POST":
        texto = request.POST.get("texto", texto)
        versao_editada = request.POST.get("versao", "")
        try:
            try:
                esperada = int(request.POST.get("versao", ""))
            except ValueError as exc:
                raise pedidos.ConflitoDoPedido(
                    "A versão enviada é inválida. Reabra o pedido salvo antes de continuar."
                ) from exc
            acao = request.POST.get("acao")
            if acao == "salvar":
                pedidos.editar(doc.nome, esperada, texto, request.admin)
            elif (
                acao == "autorizar" and request.POST.get("publicacao_publica") == "sim"
            ):
                pedidos.autorizar(
                    doc.nome,
                    esperada,
                    request.admin,
                    texto_exibido=request.POST.get("texto"),
                )
            else:
                raise pedidos.ConflitoDoPedido(
                    "Para autorizar, leia o texto e confirme que a tarefa e os registros serão públicos."
                )
            return redirect("pedido_reuniao", identidade=identidade)
        except pedidos.ConflitoDoPedido as exc:
            erro, status = str(exc), 409
        except DatabaseError:
            erro, status = (
                "Não consegui confirmar a gravação. Seu texto continua abaixo; repita o mesmo gesto para recuperar o pedido.",
                503,
            )
        doc.refresh_from_db()
        versao = doc.versoes.order_by("-pk").first()
    dados = pedidos.envelope(doc, versao)
    autorizado = pedidos.envelope_autorizado(doc, versao)
    recibo = None
    if request.method == "GET" and request.GET.get("conferir") == "1":
        recibo = fila_no_github.consultar_recibo_reuniao(dados)
    publicado = _publicado(dados, recibo)
    if publicado.get("erro") or (recibo and recibo.estado == "divergente"):
        autorizado = None
    return render(
        request,
        "admin/pedido_reuniao.html",
        {
            "admin": request.admin,
            "documento": doc,
            "versao": versao,
            "identidade": identidade,
            "texto": texto,
            "versao_editada": versao_editada,
            "pode_autorizar": str(versao_editada) == str(versao.pk)
            and texto.replace("\r\n", "\n") == versao.corpo.replace("\r\n", "\n"),
            "erro_pedido": erro,
            "recibo": recibo,
            "publicado": publicado,
            "envelope": (
                json.dumps(autorizado, ensure_ascii=False, sort_keys=True, indent=2)
                if autorizado
                else ""
            ),
        },
        status=status,
    )
