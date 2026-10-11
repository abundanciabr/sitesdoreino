"""Sete faixas, treze passos; entregas declaradas e recebimentos com print lido."""

from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_CEILING

from django.db import transaction
from django.utils import timezone
from .bonus_faixas import PONTOS

from .models import (
    AnexoDaJornada,
    JornadaPessoal,
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
# Proporções da tabela do mantenedor: 25, 50, 100, 200, 500, 750, 1000, 2000.
PERCENTUAIS = dict(
    zip(
        range(6, 14),
        map(Decimal, ("1.25", "2.5", "5", "10", "25", "37.5", "50", "100")),
    )
)
GRAUS = ("I", "II", "III", "IV", "V", "VI", "VII")
RESULTADOS = {
    1: "Comecei minha jornada para ganhar os primeiros dólares com modelagem 3D.",
    2: "Concluí meu primeiro item 3D e consigo mostrar o resultado.",
    3: "Concluí e entreguei um trabalho de prática no Sandbox.",
    4: "Concluí e entreguei meu trabalho real na Fila do Dólar.",
    5: "Recebi meu primeiro dinheiro por um trabalho de modelagem 3D.",
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


def passos(meta):
    lista = []
    for nome, cor, ordens in FAIXAS:
        for indice, ordem in enumerate(ordens):
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
                    "grau": f"{indice+1}º" if nome == "Preta" else "",
                    "nome": f"{nome} · {indice+1}º Grau" if nome == "Preta" else nome,
                    "cor": cor,
                    "cores": [cor],
                    "bonus_xp": PONTOS[ordem],
                    "conquista": RESULTADOS.get(
                        ordem,
                        f"Alcancei {str(pct).replace('.', ',')}% da minha meta pessoal.",
                    ),
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


def situacao(pessoa_id, site_id, *, meta_simulada=None):
    jornada = JornadaPessoal.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id
    ).first()
    meta = (
        meta_simulada
        if meta_simulada is not None
        else (jornada.meta_cents if jornada else None)
    )
    declaracoes = jornada.declaracoes if jornada else {}
    recebimentos = list(
        RecebimentoDeclarado.objects.filter(pessoa_id=pessoa_id, site_id=site_id)
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
    lista = passos(meta or 10000)
    for p in lista:
        ordem = p["ordem"]
        p["alcancada"] = (
            ordem == 1
            or (ordem in (2, 3, 4) and bool(declaracoes.get(str(ordem))))
            or (ordem == 5 and total > 0)
            or (ordem >= 6 and meta is not None and total >= p["meta_cents"])
        )
        p["alcancada_em"] = None
    atual = max((p for p in lista if p["alcancada"]), key=lambda p: p["ordem"])
    proxima = next((p for p in lista if p["ordem"] > atual["ordem"]), None)
    grupos = [
        {"nome": nome, "cor": cor, "passos": [p for p in lista if p["ordem"] in ordens]}
        for nome, cor, ordens in FAIXAS
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
    falta = max((proxima["meta_cents"] or 0) - total, 0) if proxima else 0
    fila_usada = bool(declaracoes.get("4")) or any(
        r.origem == "fila" for r in recebimentos
    )
    return {
        "atual": atual,
        "proxima": proxima,
        "lista": lista,
        "grupos": grupos,
        "total": reais(total),
        "total_cents": total,
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
        "recebimentos": recebimentos,
        "historico": RegistroDaJornada.objects.filter(
            pessoa_id=pessoa_id, site_id=site_id
        )[:20],
        "fila_usada": fila_usada,
        "percentual": min(100, total * 100 // (meta or 10000)),
        "falta": reais(falta),
        "chave": str(uuid.uuid4()),
        "celebracao": jornada.celebracao_pendente if jornada else {},
        "proxima_url": (
            "/forum/"
            if fila_usada or (proxima and proxima["ordem"] >= 6)
            else (
                "/encomendas/fila/"
                if proxima and proxima["ordem"] == 4
                else (
                    "/cursos/"
                    if proxima and proxima["ordem"] == 2
                    else "/encomendas/sandbox/"
                )
            )
        ),
        "proxima_acao": (
            "Buscar o próximo trabalho com apoio do Fórum"
            if fila_usada or (proxima and proxima["ordem"] >= 6)
            else (
                "Preparar minha única participação na Fila do Dólar"
                if proxima and proxima["ordem"] == 4
                else (
                    "Criar meu primeiro item nas aulas"
                    if proxima and proxima["ordem"] == 2
                    else "Praticar minha próxima entrega no Sandbox"
                )
            )
        ),
    }


def _registro(jornada, acao, dados, antes):
    depois = situacao(jornada.pessoa_id, jornada.site_id)
    alcancadas = {p["ordem"] for p in depois["lista"] if p["alcancada"]}
    from .bonus_faixas import conceder
    dados["bonus_xp"] = conceder(jornada.pessoa_id, jornada.site_id, alcancadas)
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
    return depois


def registrar_conclusao(pessoa_id, site_id, ordem):
    """A conclusão e a declaração do aluno usam a mesma conquista e o mesmo bônus."""
    if ordem not in (3, 4):
        raise ValueError("Conclusão indisponível.")
    from apps.core.perfil import perfil_de
    perfil_de(pessoa_id, site_id)
    with transaction.atomic():
        JornadaPessoal.objects.get_or_create(pessoa_id=pessoa_id, site_id=site_id)
        j = JornadaPessoal.objects.select_for_update().get(pessoa_id=pessoa_id, site_id=site_id)
        if j.declaracoes.get(str(ordem)):
            from .bonus_faixas import conceder
            conceder(pessoa_id, site_id, [p["ordem"] for p in situacao(pessoa_id, site_id)["lista"] if p["alcancada"]])
            return
        antes = situacao(pessoa_id, site_id)
        j.declaracoes = {**j.declaracoes, str(ordem): timezone.now().isoformat()}
        j.revisao += 1
        j.save(update_fields=["declaracoes", "revisao", "atualizada_em"])
        _registro(j, "conclusao", {"passo": ordem, "texto": RESULTADOS[ordem]}, antes)


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
                pessoa_id=pessoa_id, site_id=site_id, chave=chave
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
            declaracoes = dict(j.declaracoes)
            if dados.get("estado") == "feito":
                if ordem == 2 and not declaracoes.get("2"):
                    from .inicio import requisitos_branca
                    tem_anexo = AnexoDaJornada.objects.filter(
                        pessoa_id=pessoa_id, site_id=site_id, passo=2,
                    ).exists()
                    if not all(requisitos_branca(j, tem_anexo).values()):
                        raise ValueError(
                            "Para concluir o primeiro item, escolha seu motivo, "
                            "defina seu objetivo, assuma seu compromisso e envie seu arquivo."
                        )
                declaracoes[str(ordem)] = timezone.now().isoformat()
                texto = RESULTADOS[ordem]
            elif dados.get("estado") == "corrigir":
                declaracoes[str(ordem)] = None
                texto = (
                    f"Corrigi minha declaração do passo {ordem}; quero praticar mais."
                )
            else:
                raise ValueError("Escolha o que deseja registrar.")
            j.declaracoes = declaracoes
            registro = {"passo": ordem, "texto": texto}
        elif acao in ("recebimento", "correcao"):
            valor = centavos(dados.get("valor", ""))
            from . import prints_recebimentos as prints
            from .prints_recebimentos import preparar

            if valor and acao == "recebimento":
                if (
                    RecebimentoDeclarado.objects.filter(
                        pessoa_id=pessoa_id, site_id=site_id
                    ).count()
                    >= prints.MAX_RECEBIMENTOS_POR_PESSOA
                ):
                    raise ValueError(
                        "Você chegou ao limite de recebimentos registrados. Corrija um dos que já estão lá."
                    )
            elif valor and acao == "correcao" and arquivo is not None:
                alvo = RecebimentoDeclarado.objects.filter(
                    pessoa_id=pessoa_id, site_id=site_id, pk=dados.get("recebimento")
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
                    pessoa_id=pessoa_id, site_id=site_id, pk=dados.get("recebimento")
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
                    },
                )
        else:
            raise ValueError("Escolha uma ação da sua jornada.")
        j.revisao += 1
        j.save()
        depois = _registro(j, acao, registro, antes)
        return antes, depois, depois["atual"]["ordem"] > antes["atual"]["ordem"]
