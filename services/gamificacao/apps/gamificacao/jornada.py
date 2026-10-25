"""Quatro caminhos; faixas conquistadas após avaliação real e sequencial."""

from __future__ import annotations

import re
import hashlib
import json
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from django.db import transaction
from django.utils import timezone
from .bonus_faixas import PONTOS, SLUGS
from .historico_reinicio import marcos_anteriores
from .cerimonias import para_tela as cerimonia_para_tela

from .models import (
    AnexoDaJornada,
    AvaliacaoDaJornada,
    AvaliacaoSandboxProjetada,
    FaixaDoAluno,
    JornadaPessoal,
    LancamentoDeXP,
    RecebimentoDeclarado,
    RegistroDaJornada,
    VersaoDoRecebimento,
)

FAIXAS = (
    ("Branca", "#f4f4f4", (1,)),
    ("Amarela", "#f2c200", (2,)),
    ("Azul", "#2b6fd6", (3,)),
    ("Vermelha", "#ce3341", (4,)),
    ("Verde", "#2e9d4a", (5,)),
    ("Marrom", "#7a4a26", (6,)),
    ("Preta", "#1d1d1d", (7, 8, 9, 10, 11, 12, 13)),
)
# Percentuais dos graus de clientes, após o primeiro recebimento reconhecido.
PERCENTUAIS = dict(
    zip(
        range(8, 14),
        map(Decimal, ("5", "10", "25", "37.5", "50", "100")),
    )
)
CAMINHOS = frozenset(("freelancer", "ugc", "jogo", "aprender"))
GRAUS = ("I", "II", "III", "IV", "V", "VI", "VII")
RESULTADOS = {
    1: "Comecei minha jornada de modelagem 3D.",
    2: "Escolher meu caminho e assumir o compromisso.",
    3: "Descrever meu primeiro item e uma ação concreta que realizei nele.",
    4: "Apresentar imagem ou arquivo 3D para análise do meu item.",
}
RESULTADOS_POR_CAMINHO = {
    "freelancer": {
        5: "Concluir uma prática do Sandbox conforme o briefing, reconhecida pela análise automática.",
        6: "Entregar o trabalho real da Fila do Dólar com aceite do cliente.",
        7: "Conferir meu primeiro recebimento por modelagem 3D, ligado ao trabalho e valor.",
    },
    "ugc": {
        5: "Alterar e salvar a cor de uma parte do acessório.",
        6: "Mudar a proporção do acessório e comparar as versões.",
        7: "Apresentar imagem final, nome e uso imaginado do acessório.",
    },
    "jogo": {
        5: "Alterar e salvar a cor do objeto pensando no cenário.",
        6: "Ajustar a proporção do objeto e registrar o resultado.",
        7: "Apresentar a imagem final e explicar onde usaria o objeto no jogo.",
    },
    "aprender": {
        5: "Experimentar e salvar uma mudança de cor.",
        6: "Fazer uma pequena alteração de proporção e observar a diferença.",
        7: "Apresentar a criação final e explicar uma mudança feita desde o começo.",
    },
}
APOIOS = {
    "guiado": (
        "Quero orientação",
        "Divida a entrega em três partes: entenda o pedido, crie o item e confira os arquivos antes de entregar. Use o tutor para tirar uma dúvida por vez.",
    ),
    "autonomo": (
        "Quero tentar sozinho",
        "Faça uma versão com o que já sabe. Depois compare com o pedido e use o feedback para escolher o próximo ajuste.",
    ),
    "desafio": (
        "Quero praticar mais",
        "No Sandbox, faça outra versão do item por conta própria e compare as duas. Mantenha o pedido como referência; a prática extra é opcional.",
    ),
}


def reais(cents):
    inteiro, centavos = divmod(int(cents), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{centavos:02d}"


def centavos(texto):
    valor = str(texto).strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d{1,2})?", valor):
        valor = valor.replace(".", "").replace(",", ".")
    else:
        valor = valor.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", valor):
        raise ValueError("Informe um valor em reais, com até duas casas decimais.")
    try:
        resultado = int(Decimal(valor) * 100)
    except (InvalidOperation, ValueError):
        raise ValueError("Confira o valor informado.") from None
    if resultado > 2147483647:
        raise ValueError("Confira o valor informado.")
    return resultado


def passos(meta, caminho="freelancer"):
    lista = []
    for nome, cor, ordens in FAIXAS:
        for indice, ordem in enumerate(ordens):
            if caminho != "freelancer" and ordem > 7:
                continue
            pct = PERCENTUAIS.get(ordem)
            limite = (
                int(
                    (Decimal(meta) * pct / 100).to_integral_value(
                        rounding=ROUND_CEILING
                    )
                )
                if pct
                else None
            )
            lista.append(
                {
                    "ordem": ordem,
                    "faixa": nome,
                    "grau": f"{indice+1}º" if nome == "Preta" and caminho == "freelancer" else "",
                    "nome": f"{nome} · {indice+1}º Grau" if nome == "Preta" and caminho == "freelancer" else nome,
                    "cor": cor,
                    "cores": [cor],
                    "bonus_xp": PONTOS[ordem],
                    "conquista": (f"Alcançar {str(pct).replace('.', ',')}% da minha meta pessoal em recebimentos conferidos."
                                  if pct else RESULTADOS.get(ordem) or
                                  RESULTADOS_POR_CAMINHO.get(caminho, {}).get(ordem) or
                                  "Escolher meu caminho para conhecer esta atividade."),
                    "percentual": pct,
                    "meta_cents": limite,
                    "limite": reais(limite) if limite is not None else None,
                }
            )
    return lista


ESPERANDO_LEITURA = ("pendente", "analisando", "falha")


def _soma_anterior(r):
    """O recebimento ainda guarda o último valor confirmado (leitor em andamento ou caído)?"""
    return r.estado in ESPERANDO_LEITURA or (
        r.estado == "esclarecer" and (r.leitura or {}).get("motivo") == "leitor"
    )


def _conquistas_anteriores(pessoa_id, site_id, jornada):
    """Lê faixas já concedidas, sem criar uma avaliação ou um crédito novo."""
    anteriores = marcos_anteriores(pessoa_id, site_id)
    data_reserva = jornada.atualizada_em if jornada else timezone.now()
    alcancadas = {ordem: dado["criado_em"] or data_reserva
                  for ordem, dado in anteriores["bonus"].items()}
    for ordem, _origem in anteriores["faixas"]:
        if isinstance(ordem, int) and 2 <= ordem <= 13:
            alcancadas.setdefault(ordem, data_reserva)
    from .faixas import limite_das_faixas_legadas
    for faixa in FaixaDoAluno.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, estado=FaixaDoAluno.Estado.ALCANCADA,
        alcancada_em__lt=limite_das_faixas_legadas(site_id),
    ).values("ordem", "alcancada_em"):
        alcancadas.setdefault(faixa["ordem"], faixa["alcancada_em"])
    # A confirmação antiga da amarela só valia após quatro tarefas completas.
    if jornada and jornada.declaracoes.get("2") and jornada.confirmacoes_sequenciais.get("2"):
        from .bonus_inicio import recebido
        from .inicio import requisitos_branca
        tem_anexo = AnexoDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, passo=2,
        ).exists()
        if all(requisitos_branca(jornada, tem_anexo).values()) and all(
            recebido(pessoa_id, site_id, etapa) > 0 for etapa in (1, 2, 3, 4)
        ):
            alcancadas.setdefault(2, data_reserva)
    # A projeção só marca reconhecida_em quando o avaliador antigo aceitou o
    # Sandbox. Projeções pendentes, envios e simples declarações ficam de fora.
    reconhecimento = AvaliacaoSandboxProjetada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, reconhecida_em__isnull=False,
    ).order_by("reconhecida_em").values_list("reconhecida_em", flat=True).first()
    if reconhecimento:
        alcancadas.setdefault(3, reconhecimento)
    return alcancadas


def situacao(pessoa_id, site_id, *, meta_simulada=None):
    from .sandbox_avaliacoes import resumo as resumo_sandbox
    jornada = JornadaPessoal.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id
    ).first()
    meta = (
        meta_simulada
        if meta_simulada is not None
        else (jornada.meta_cents if jornada else None)
    )
    declaracoes = jornada.declaracoes if jornada else {}
    caminho = (jornada.inicio or {}).get("motivo") if jornada else None
    if caminho not in CAMINHOS:
        caminho = None
    reconhecidas = {}
    recentes = {}
    historicas = []
    bonus_historicos = {}
    slugs_para_ordem = {"bonus-faixa-" + slug: ordem for ordem, slug in SLUGS.items()}
    for lancamento in LancamentoDeXP.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, pontos__gt=0,
        regra_slug__in=slugs_para_ordem,
    ).exclude(status="estornado").values("regra_slug", "criado_em", "pontos"):
        ordem_historica = slugs_para_ordem[lancamento["regra_slug"]]
        bonus_historicos.setdefault(ordem_historica, lancamento)
    for ordem_historica, lancamento in marcos_anteriores(pessoa_id, site_id)["bonus"].items():
        bonus_historicos.setdefault(ordem_historica, lancamento)
    conquistas_anteriores = _conquistas_anteriores(pessoa_id, site_id, jornada)
    # Um grau já creditado prova a antiga conquista; os passos intermediários
    # ficam reconhecidos como baseline, sem fabricar novas avaliações ou XP.
    for ordem_historica in range(2, max((*bonus_historicos, *conquistas_anteriores), default=1) + 1):
        reconhecidas[ordem_historica] = (
            conquistas_anteriores.get(ordem_historica)
            or bonus_historicos.get(ordem_historica, {}).get("criado_em")
            or conquistas_anteriores.get(max(conquistas_anteriores, default=1))
            or bonus_historicos.get(max(bonus_historicos, default=1), {}).get("criado_em")
        )
    for avaliacao in AvaliacaoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id,
    ).order_by("criada_em", "id").values("ordem", "caminho", "resultado", "feedback", "criada_em"):
        historicas.append(avaliacao)
        if avaliacao["caminho"] == "comum" or avaliacao["caminho"] == caminho:
            recentes[avaliacao["ordem"]] = avaliacao
            if avaliacao["resultado"] == "reconhecida":
                reconhecidas.setdefault(avaliacao["ordem"], avaliacao["criada_em"])
    recebimentos = list(
        RecebimentoDeclarado.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id, fora_da_progressao=False,
        )
        .defer("print_bytes")
        .order_by("-recebido_em", "-id")
    )
    total = sum(
        r.valor_cents
        if r.estado == "confirmado"
        else (r.leitura or {}).get("anterior_cents", 0)
        if _soma_anterior(r)
        else 0
        for r in recebimentos
    )
    total_conferido = sum(
        r.valor_cents for r in recebimentos
        if r.estado == "confirmado" and (r.leitura or {}).get("correspondencia_trabalho") is True
    )
    lista = passos(meta or 10000, caminho)
    anterior_alcancada = True
    for p in lista:
        ordem = p["ordem"]
        criterio = ordem == 1 or ordem in reconhecidas
        p["alcancada"] = anterior_alcancada and criterio
        anterior_alcancada = p["alcancada"]
        p["alcancada_em"] = reconhecidas.get(ordem) if p["alcancada"] else None
        p["feedback"] = recentes.get(ordem, {}).get("feedback", "")
        p["avaliacao_resultado"] = recentes.get(ordem, {}).get("resultado")
        if ordem in reconhecidas and not p["feedback"]:
            p["feedback"] = "Conquista histórica preservada."
            p["avaliacao_resultado"] = "historica"
    atual = max((p for p in lista if p["alcancada"]), key=lambda p: p["ordem"])
    proxima = next((p for p in lista if p["ordem"] > atual["ordem"]), None)
    grupos = [
        {"nome": nome, "cor": cor, "passos": [p for p in lista if p["ordem"] in ordens]}
        for nome, cor, ordens in FAIXAS if any(p["ordem"] in ordens for p in lista)
    ]
    for r in recebimentos:
        from .prints_recebimentos import mensagem

        r.mensagem = mensagem(r)
        r.valor = reais(r.valor_cents)
        r.valor_input = f"{r.valor_cents / 100:.2f}"
        r.valor_original_input = f"{r.valor_original_cents / 100:.2f}"
        r.versoes = (
            VersaoDoRecebimento.objects.filter(
                recebimento=r, pessoa_id=pessoa_id, site_id=site_id
            )
            .defer("print_bytes")
            .order_by("-revisao")
        )
    falta = max((proxima["meta_cents"] or 0) - total_conferido, 0) if proxima else 0
    fila_usada = 6 in reconhecidas or any(
        r.origem == "fila" for r in recebimentos
    )
    fila_para_proximo = bool(fila_usada and proxima and proxima["ordem"] >= 7)
    if proxima is None:
        proxima_url, proxima_acao = "", "Ciclo concluído"
    elif caminho is None:
        proxima_url, proxima_acao = "/trilha/inicio/motivo/", "Escolher um dos quatro caminhos"
    elif proxima["ordem"] == 2:
        proxima_url, proxima_acao = "/trilha/inicio/objetivo/", "Definir meu compromisso"
    elif proxima["ordem"] == 3:
        proxima_url, proxima_acao = "/trilha/inicio/item/", "Descrever meu primeiro item"
    elif proxima["ordem"] == 4:
        proxima_url, proxima_acao = "/trilha/inicio/envio/", "Apresentar meu item para análise"
    elif caminho != "freelancer":
        proxima_url, proxima_acao = "/trilha/ciclo/", "Continuar a prática do meu caminho"
    elif proxima["ordem"] == 5:
        proxima_url, proxima_acao = "/trilha/sandbox/", "Concluir uma prática avaliada no Sandbox"
    elif proxima["ordem"] == 6:
        proxima_url, proxima_acao = "/trilha/fila/", "Entregar trabalho ao cliente da Fila do Dólar"
    else:
        proxima_url, proxima_acao = "/trilha/recebimentos/", "Conferir meu próximo recebimento"
    return {
        "atual": atual,
        "proxima": proxima,
        "lista": lista,
        "grupos": grupos,
        "total": reais(total),
        "total_cents": total,
        "total_conferido_cents": total_conferido,
        "meta": reais(meta or 10000),
        "meta_input": f"{(meta or 10000) / 100:.2f}",
        "meta_escolhida": meta is not None,
        "meta_cents": meta,
        "proposito": jornada.proposito if jornada else "",
        "apoio": jornada.apoio if jornada else "guiado",
        "apoios": [
            {
                "valor": k,
                "nome": v[0],
                "selecionado": k == (jornada.apoio if jornada else "guiado"),
            }
            for k, v in APOIOS.items()
        ],
        "dica": APOIOS.get(jornada.apoio if jornada else "guiado", APOIOS["guiado"])[1],
        "revisao": jornada.revisao if jornada else 0,
        "caminho": caminho,
        "avaliacoes_historicas": historicas,
        "graus_historicos": [{"ordem": ordem, "bonus_xp": dado["pontos"],
                              "conquistada_em": dado["criado_em"]}
                             for ordem, dado in sorted(bonus_historicos.items()) if ordem >= 7],
        "recebimentos": recebimentos,
        "sandbox_avaliacoes": resumo_sandbox(pessoa_id, site_id)["avaliacoes"],
        "historico": RegistroDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id
        )[:20],
        "fila_usada": fila_usada,
        "percentual": min(100, total_conferido * 100 // (meta or 10000)),
        "falta": reais(falta),
        "chave": str(uuid.uuid4()),
        "celebracao": cerimonia_para_tela(jornada),
        "proxima_url": proxima_url,
        "proxima_acao": proxima_acao,
    }


def _registro(jornada, acao, dados, antes):
    depois = situacao(jornada.pessoa_id, jornada.site_id)
    alcancadas = {p["ordem"] for p in depois["lista"] if p["alcancada"]}
    avaliadas = set(AvaliacaoDaJornada.objects.filter(
        pessoa_id=jornada.pessoa_id, site_id=jornada.site_id, resultado="reconhecida",
    ).values_list("ordem", flat=True))
    equivalentes_pagas = set()
    for ordem, evidencia in AvaliacaoDaJornada.objects.filter(
        pessoa_id=jornada.pessoa_id, site_id=jornada.site_id, resultado="reconhecida",
    ).values_list("ordem", "evidencia"):
        if (evidencia or {}).get("credito_equivalente_confirmado"):
            equivalentes_pagas.add(ordem)
    ja_creditadas = set(LancamentoDeXP.objects.filter(
        pessoa_id=jornada.pessoa_id, site_id=jornada.site_id, pontos__gt=0,
        regra_slug__startswith="bonus-faixa-",
    ).exclude(status="estornado").values_list("regra_slug", flat=True))
    baseline_max = max(
        (ordem for ordem, slug in SLUGS.items() if "bonus-faixa-" + slug in ja_creditadas),
        default=1,
    )
    baseline_max = max(baseline_max, *_conquistas_anteriores(
        jornada.pessoa_id, jornada.site_id, jornada), 1)
    from .bonus_faixas import conceder
    dados["bonus_xp"] = conceder(jornada.pessoa_id, jornada.site_id,
                                  {ordem for ordem in alcancadas & avaliadas
                                   if ordem > baseline_max and ordem not in equivalentes_pagas})
    dados.update(
        {
            "texto": dados.get("texto", "Registro atualizado."),
            "passo_antes": antes["atual"]["ordem"],
            "passo_depois": depois["atual"]["ordem"],
            "meta_cents": jornada.meta_cents,
            "total_cents": depois["total_cents"],
        }
    )
    RegistroDaJornada.objects.create(
        pessoa_id=jornada.pessoa_id, site_id=jornada.site_id, acao=acao, dados=dados
    )
    depois["bonus_xp"] = dados["bonus_xp"]
    return depois


def registrar_avaliacao(pessoa_id, site_id, ordem, resultado, feedback, evidencia):
    """Guarda uma tentativa examinada e libera em sequência as reconhecidas.

    ``evidencia`` descreve o trabalho efetivamente conferido e pode trazer
    ``chave`` (ID estável da tentativa). A repetição da mesma tentativa é idempotente.
    """
    if type(ordem) is not int or ordem not in range(2, 14):
        raise ValueError("Ordem de faixa inválida.")
    if resultado not in ("reconhecida", "incompleta", "falha"):
        raise ValueError("Resultado de avaliação inválido.")
    if not isinstance(feedback, str) or not feedback.strip():
        raise ValueError("A avaliação precisa de feedback concreto.")
    if not isinstance(evidencia, dict) or not evidencia:
        raise ValueError("A avaliação precisa identificar a evidência examinada.")
    try:
        payload = json.dumps([resultado, feedback, evidencia], sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        raise ValueError("Evidência inválida.") from None
    chave = hashlib.sha256(str(evidencia.get("chave") or payload).encode()).hexdigest()
    from apps.core.perfil import perfil_de
    perfil_de(pessoa_id, site_id)
    with transaction.atomic():
        JornadaPessoal.objects.get_or_create(pessoa_id=pessoa_id, site_id=site_id)
        j = JornadaPessoal.objects.select_for_update().get(pessoa_id=pessoa_id, site_id=site_id)
        caminho = (j.inicio or {}).get("motivo")
        equivalente = evidencia.get("conquista_equivalente_original")
        if equivalente is not None:
            esperado = {5: (3, "sandbox"), 6: (4, "fila")}.get(ordem)
            if (not isinstance(equivalente, dict) or esperado is None or
                (equivalente.get("ordem"), equivalente.get("origem")) != esperado):
                raise ValueError("Vínculo de conquista histórica inválido.")
            origem_antiga, origem_nome = esperado
            registro_antigo = FaixaDoAluno.objects.filter(
                pessoa_id=pessoa_id, site_id=site_id, ordem=origem_antiga,
                origem=origem_nome,
            ).exists()
            conclusao_antiga = RegistroDaJornada.objects.filter(
                pessoa_id=pessoa_id, site_id=site_id, acao="conclusao",
                dados__passo=origem_antiga,
            ).exists()
            credito_antigo = LancamentoDeXP.objects.filter(
                pessoa_id=pessoa_id, site_id=site_id, pontos__gt=0,
                regra_slug="bonus-faixa-" + SLUGS[origem_antiga],
            ).exclude(status="estornado").exists()
            anterior = marcos_anteriores(pessoa_id, site_id)
            registro_antigo |= (origem_antiga, origem_nome) in anterior["faixas"]
            conclusao_antiga |= origem_antiga in anterior["conclusoes"]
            credito_antigo |= origem_antiga in anterior["bonus"]
            if origem_antiga == 3:
                projecao_antiga = AvaliacaoSandboxProjetada.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id,
                    reconhecida_em__isnull=False,
                    reconhecida_analise_id=str(evidencia.get("analise_id") or ""),
                ).exists()
                registro_antigo |= projecao_antiga
                conclusao_antiga |= RegistroDaJornada.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id,
                    acao="avaliacao_sandbox", dados__analise_id=str(evidencia.get("analise_id") or ""),
                ).exists()
            evidencia = {**evidencia,
                         "credito_equivalente_confirmado": bool(
                             registro_antigo and conclusao_antiga and credito_antigo)}
        if ordem >= 5 and caminho not in CAMINHOS:
            raise ValueError("Escolha um dos quatro caminhos antes desta avaliação.")
        if ordem >= 8 and caminho != "freelancer":
            raise ValueError("Graus adicionais pertencem ao caminho de clientes.")
        if resultado == "reconhecida" and ordem >= 7 and caminho == "freelancer":
            if not all(evidencia.get(campo) for campo in
                       ("recebimento_id", "referencia_trabalho", "valor_cents")):
                raise ValueError("Confira o vínculo entre trabalho, recebimento e valor.")
            recebimento = RecebimentoDeclarado.objects.filter(
                pk=evidencia["recebimento_id"], pessoa_id=pessoa_id, site_id=site_id,
                estado="confirmado", fora_da_progressao=False,
            ).first()
            if (not recebimento or not recebimento.referencia_trabalho
                or recebimento.referencia_trabalho != evidencia["referencia_trabalho"]
                or recebimento.valor_cents != evidencia["valor_cents"]
                or (recebimento.leitura or {}).get("correspondencia_trabalho") is not True):
                raise ValueError("O recebimento e o trabalho ainda não foram conferidos.")
            if ordem >= 8:
                if j.meta_cents is None:
                    raise ValueError("Defina a meta antes dos graus adicionais.")
                total_reconhecido = sum(r.valor_cents for r in RecebimentoDeclarado.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id, estado="confirmado",
                    fora_da_progressao=False,
                ) if (r.leitura or {}).get("correspondencia_trabalho") is True)
                limite = int((Decimal(j.meta_cents) * PERCENTUAIS[ordem] / 100).to_integral_value(
                    rounding=ROUND_CEILING))
                if total_reconhecido < limite:
                    raise ValueError("O valor conferido ainda não alcançou este grau.")
        antes = situacao(pessoa_id, site_id)
        avaliacao, criada = AvaliacaoDaJornada.objects.get_or_create(
            pessoa_id=pessoa_id, site_id=site_id, ordem=ordem, chave=chave,
            defaults={"caminho": "comum" if ordem <= 4 else caminho,
                      "resultado": resultado, "feedback": feedback.strip(), "evidencia": evidencia},
        )
        if not criada:
            if (avaliacao.resultado, avaliacao.feedback, avaliacao.evidencia) != (
                resultado, feedback.strip(), evidencia
            ):
                raise ValueError("A chave desta avaliação já representa outro resultado.")
            antes["bonus_xp"] = 0
            return antes
        depois = _registro(j, "avaliacao", {
            "passo": ordem, "avaliacao_id": avaliacao.pk,
            "resultado": resultado, "texto": feedback.strip(),
        }, antes)
        if depois["atual"]["ordem"] > antes["atual"]["ordem"]:
            from .avisos_faixas import avisar
            avisar(j, antes, depois)
            from .cerimonias import acrescentar
            acrescentar(j, antes, depois)
            j.save(update_fields=["celebracao_pendente", "atualizada_em"])
        return depois


def registrar_conclusao(pessoa_id, site_id, ordem):
    """Compatibilidade: registra o fato antigo sem fingir que houve avaliação."""
    if ordem not in (3, 4):
        raise ValueError("Conclusão indisponível.")
    from apps.core.perfil import perfil_de
    perfil_de(pessoa_id, site_id)
    with transaction.atomic():
        j, _ = JornadaPessoal.objects.get_or_create(pessoa_id=pessoa_id, site_id=site_id)
        j = JornadaPessoal.objects.select_for_update().get(pk=j.pk)
        if str(ordem) not in j.declaracoes:
            j.declaracoes = {**j.declaracoes, str(ordem): timezone.now().isoformat()}
            j.save(update_fields=["declaracoes", "atualizada_em"])
            RegistroDaJornada.objects.create(pessoa_id=pessoa_id, site_id=site_id,
                acao="conclusao", dados={"passo": ordem, "texto": "Conclusão registrada; avaliação pendente."})


def reconciliar_recebimentos(pessoa_id, site_id):
    """Aproveita leituras com trabalho vinculado, inclusive após escolher a meta."""
    j = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    if not j or (j.inicio or {}).get("motivo") != "freelancer":
        return situacao(pessoa_id, site_id)
    recebimentos = [r for r in RecebimentoDeclarado.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, estado="confirmado",
        fora_da_progressao=False,
    ).order_by("recebido_em", "id") if r.referencia_trabalho and
        (r.leitura or {}).get("correspondencia_trabalho") is True]
    reconhecidas = set(AvaliacaoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, caminho="freelancer",
        resultado="reconhecida", ordem__gte=7,
    ).values_list("ordem", flat=True))
    total = 0
    for r in recebimentos:
        total += r.valor_cents
        evidencia = {
            "recebimento_id": r.pk, "referencia_trabalho": r.referencia_trabalho,
            "valor_cents": r.valor_cents, "print_sha256": r.print_sha256,
            "recebido_em": r.recebido_em.isoformat(),
            "conferencia": "leitura visual; sem autenticacao bancaria",
            "chave": f"recebimento:{r.pk}:revisao:{r.revisao}:primeiro",
        }
        if 7 not in reconhecidas:
            registrar_avaliacao(pessoa_id, site_id, 7, "reconhecida",
                f"Conferi o identificador do trabalho e o recebimento de {reais(r.valor_cents)} "
                "no material. A leitura visual não autentica o pagamento.", evidencia)
            reconhecidas.add(7)
        if j.meta_cents:
            for ordem, percentual in PERCENTUAIS.items():
                if ordem in reconhecidas:
                    continue
                if total * 100 < j.meta_cents * percentual:
                    continue
                registrar_avaliacao(pessoa_id, site_id, ordem, "reconhecida",
                    f"Recebimentos conferidos de {reais(total)} alcançaram "
                    f"{str(percentual).replace('.', ',')}% da meta de {reais(j.meta_cents)}. "
                    f"Grau {ordem - 6} conquistado.",
                    {**evidencia, "meta_cents": j.meta_cents, "total_cents": total,
                     "percentual": str(percentual),
                     "chave": f"recebimento:{r.pk}:revisao:{r.revisao}:grau:{ordem}:meta:{j.meta_cents}"})
                reconhecidas.add(ordem)
    return situacao(pessoa_id, site_id)


def recuperar_avaliacoes_anteriores(pessoa_id, site_id, fatos=None):
    from .historico_avaliacoes import recuperar_avaliacoes_anteriores as recuperar
    return recuperar(pessoa_id, site_id, fatos=fatos)


def salvar(pessoa_id, site_id, dados, *, arquivo=None):
    """Todas as escritas da pessoa são serializadas pela mesma linha da jornada."""
    from apps.core.perfil import perfil_de

    perfil_de(pessoa_id, site_id)
    with transaction.atomic():
        JornadaPessoal.objects.get_or_create(pessoa_id=pessoa_id, site_id=site_id)
        j = JornadaPessoal.objects.select_for_update().get(
            pessoa_id=pessoa_id, site_id=site_id
        )
        antes = situacao(pessoa_id, site_id)
        acao = dados.get("acao")
        try:
            revisao = int(dados.get("revisao", "-1"))
        except (TypeError, ValueError):
            raise ValueError("Abra novamente a página antes de salvar.") from None
        # Um envio repetido do mesmo recebimento retorna o registro, sem somar outra vez.
        if acao == "recebimento":
            try:
                chave = uuid.UUID(str(dados.get("chave", "")))
            except ValueError:
                raise ValueError(
                    "Abra novamente a página para registrar o recebimento."
                ) from None
            if RecebimentoDeclarado.objects.filter(
                pessoa_id=pessoa_id, site_id=site_id, chave=chave,
            ).exists():
                return antes, antes, False
        if revisao != j.revisao:
            raise ValueError(
                "Seu registro mudou em outra aba. Atualize a página para continuar."
            )
        registro = {}
        if acao == "meta":
            meta = centavos(dados.get("meta", ""))
            if not 10000 <= meta <= 100000:
                raise ValueError("Escolha uma meta entre R$ 100,00 e R$ 1.000,00.")
            j.meta_cents = meta
            j.proposito = str(dados.get("proposito", "")).strip()[:280]
            registro = {
                "anterior": antes["meta_cents"],
                "texto": f"Escolhi minha meta: {reais(meta)}.",
            }
        elif acao == "apoio":
            if dados.get("apoio") not in APOIOS:
                raise ValueError("Escolha como deseja praticar agora.")
            j.apoio = dados["apoio"]
            registro = {"texto": f"Meu apoio agora: {APOIOS[j.apoio][0]}."}
        elif acao == "declaracao":
            try:
                ordem = int(dados.get("passo", ""))
            except ValueError:
                raise ValueError("Escolha um resultado da jornada.") from None
            if ordem not in (2, 3, 4):
                raise ValueError(
                    "Esse passo acompanha seus recebimentos automaticamente."
                )
            if ordem == 3:
                raise ValueError("A prática do Sandbox é reconhecida pela análise da entrega.")
            declaracoes = dict(j.declaracoes)
            confirmacoes = dict(j.confirmacoes_sequenciais)
            if dados.get("estado") == "feito":
                if declaracoes.get(str(ordem)):
                    return antes, antes, False
                agora = timezone.now().isoformat()
                declaracoes.setdefault(str(ordem), agora)
                texto = "Atividade informada; avaliação pendente."
            elif dados.get("estado") == "corrigir":
                confirmacoes.pop(str(ordem), None)
                texto = (
                    f"Corrigi minha declaração do passo {ordem}; quero praticar mais."
                )
            else:
                raise ValueError("Escolha o que deseja registrar.")
            j.declaracoes = declaracoes
            j.confirmacoes_sequenciais = confirmacoes
            registro = {"passo": ordem, "texto": texto}
        elif acao in ("recebimento", "correcao"):
            valor = centavos(dados.get("valor", ""))
            referencia_trabalho = str(dados.get("referencia_trabalho", "")).strip()
            if len(referencia_trabalho) > 280:
                raise ValueError("Descreva o trabalho em até 280 caracteres.")
            if valor and not referencia_trabalho:
                raise ValueError("Identifique o trabalho de modelagem 3D ligado a este recebimento.")
            from . import prints_recebimentos as prints
            from .prints_recebimentos import preparar

            if valor and acao == "recebimento":
                if (
                    RecebimentoDeclarado.objects.filter(
                        pessoa_id=pessoa_id, site_id=site_id,
                        fora_da_progressao=False,
                    ).count()
                    >= prints.MAX_RECEBIMENTOS_POR_PESSOA
                ):
                    raise ValueError(
                        "Você chegou ao limite de recebimentos registrados. Corrija um dos que já estão lá."
                    )
            elif valor and acao == "correcao" and arquivo is not None:
                alvo = RecebimentoDeclarado.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id, pk=dados.get("recebimento"),
                    fora_da_progressao=False,
                ).first()
                if (
                    alvo
                    and VersaoDoRecebimento.objects.filter(recebimento=alvo).count()
                    >= prints.MAX_VERSOES_POR_RECEBIMENTO
                ):
                    raise ValueError(
                        "Esse recebimento já teve prints demais. Fale com o suporte."
                    )

            print_bytes, print_sha256 = preparar(arquivo) if valor else (None, "")
            moeda_original = str(dados.get("moeda_original", "BRL")).strip().upper()
            if not re.fullmatch(r"[A-Z]{3}", moeda_original):
                raise ValueError(
                    "Informe a moeda que aparece no print, como BRL ou USD."
                )
            valor_original = (
                centavos(dados.get("valor_original", ""))
                if moeda_original != "BRL" and valor
                else valor
            )
            if valor and not valor_original:
                raise ValueError("Informe o valor original que aparece no print.")
            try:
                recebido_em = date.fromisoformat(str(dados.get("recebido_em", "")))
            except ValueError:
                raise ValueError("Informe o dia em que recebeu o dinheiro.") from None
            if recebido_em > timezone.localdate():
                raise ValueError(
                    "Registre um dinheiro que já recebeu; a data está no futuro."
                )
            if acao == "recebimento":
                origem = dados.get("origem")
                if origem not in ("fila", "fora") or not valor:
                    raise ValueError(
                        "Informe um recebimento positivo e onde ele aconteceu."
                    )
                r = RecebimentoDeclarado.objects.create(
                    pessoa_id=pessoa_id,
                    site_id=site_id,
                    chave=chave,
                    valor_cents=valor,
                    origem=origem,
                    referencia_trabalho=referencia_trabalho,
                    recebido_em=recebido_em,
                    print_bytes=print_bytes,
                    print_sha256=print_sha256,
                    moeda_original=moeda_original,
                    valor_original_cents=valor_original,
                )
                registro = {
                    "recebimento": r.pk,
                    "texto": f"Declarei {reais(valor)} ({'Fila do Dólar' if origem == 'fila' else 'fora do site'}); print aguardando leitura.",
                }
            else:
                r = RecebimentoDeclarado.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id, pk=dados.get("recebimento"),
                    fora_da_progressao=False,
                ).first()
                if r is None:
                    raise ValueError("Recebimento não encontrado na sua jornada.")
                registro = {
                    "recebimento": r.pk,
                    "valor_anterior": r.valor_cents,
                    "data_anterior": r.recebido_em.isoformat(),
                    "texto": f"Corrigi um recebimento para {reais(valor)}.",
                }
                # Enquanto o robô relê, o último valor confirmado continua somando.
                if r.estado == "confirmado":
                    anterior = r.valor_cents
                elif _soma_anterior(r):
                    anterior = (r.leitura or {}).get("anterior_cents", 0)
                else:
                    anterior = 0
                r.valor_cents, r.recebido_em = valor, recebido_em
                r.referencia_trabalho = referencia_trabalho or r.referencia_trabalho
                if print_bytes:
                    r.print_bytes, r.print_sha256 = print_bytes, print_sha256
                r.moeda_original, r.valor_original_cents = (
                    moeda_original,
                    valor_original,
                )
                r.estado = "pendente" if valor else "anulado"
                r.leitura = {"anterior_cents": anterior} if anterior and valor else {}
                r.tentar_em, r.analise_iniciada_em = None, None
                r.tentativas = 0
                r.revisao += 1
                r.save()
            if print_bytes:
                VersaoDoRecebimento.objects.create(
                    pessoa_id=pessoa_id,
                    site_id=site_id,
                    recebimento=r,
                    revisao=r.revisao,
                    print_bytes=print_bytes,
                    print_sha256=print_sha256,
                    dados={
                        "valor_cents": valor,
                        "moeda_original": moeda_original,
                        "valor_original_cents": valor_original,
                        "recebido_em": recebido_em.isoformat(),
                        "referencia_trabalho": referencia_trabalho,
                    },
                )
        else:
            raise ValueError("Escolha uma ação da sua jornada.")
        j.revisao += 1
        j.save()
        depois = _registro(j, acao, registro, antes)
        if acao == "meta":
            depois = reconciliar_recebimentos(pessoa_id, site_id)
        return antes, depois, depois["atual"]["ordem"] > antes["atual"]["ordem"]
