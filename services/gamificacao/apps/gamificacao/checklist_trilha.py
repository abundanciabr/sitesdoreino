"""Checklist de leitura da jornada, sem criar nem alterar conquistas."""

from apps.gamificacao.models import FaixaDoAluno, RecebimentoDeclarado, AnexoDaJornada


def _item(ordem, titulo, estado, detalhe, acao=None, *, sufixo=None):
    return {
        "id": f"criterio-{ordem}" if sufixo is None else f"{sufixo}-{ordem}",
        "titulo": titulo,
        "estado": estado,
        "detalhe": detalhe,
        "acao": acao,
    }


def _estado(alcancada, andamento=False):
    return "concluido" if alcancada else ("andamento" if andamento else "pendente")


def _dinheiro(cents):
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def montar_checklists(pessoa_id, site_id, jornada):
    """A conquista vem só de situacao; eventos e registros apenas contextualizam."""
    tem_anexo = AnexoDaJornada.objects.filter(pessoa_id=pessoa_id, site_id=site_id, passo=2).exists()
    etapas = {p["ordem"]: p for p in jornada["lista"]}
    faixas = {
        faixa.ordem: faixa
        for faixa in FaixaDoAluno.objects.filter(
            pessoa__id_da_plataforma=pessoa_id,
            site_id=site_id,
            ordem__in=(2, 3, 4),
        ).only("ordem", "origem", "estado")
    }
    recebimentos = list(
        RecebimentoDeclarado.objects.filter(
            pessoa__id_da_plataforma=pessoa_id, site_id=site_id
        ).values("estado", "valor_cents", "leitura")
    )
    em_leitura = any(
        r["valor_cents"] > 0 and r["estado"] in ("pendente", "analisando")
        for r in recebimentos
    )
    corrigir = any(r["estado"] in ("falha", "esclarecer") for r in recebimentos)
    meta_escolhida = jornada["meta_escolhida"]
    total = jornada["total_cents"]
    resultado = {}

    for ordem, etapa in etapas.items():
        alcancada = etapa["alcancada"]
        observacao = ""
        if ordem == 1:
            itens = [_item(1, "Começar minha jornada", "concluido",
                           "A entrada na jornada já está registrada.")]
        elif ordem in (2, 3, 4):
            faixa = faixas.get(ordem)
            origem = {2: "item", 3: "sandbox", 4: "fila"}[ordem]
            iniciou = bool(faixa and faixa.origem == origem and faixa.estado == "alcancada") or (ordem == 2 and tem_anexo)
            titulo = {
                2: "Concluir meu primeiro item 3D",
                3: "Concluir e entregar uma prática no Sandbox",
                4: "Concluir e entregar meu trabalho real na Fila",
            }[ordem]
            detalhe = {
                2: "Um arquivo foi guardado no inventário; a conclusão ainda não foi registrada." if tem_anexo else "Um item 3D foi salvo; a conclusão do primeiro item ainda não foi registrada.",
                3: "Uma prática no Sandbox foi iniciada; a entrega concluída ainda não foi registrada.",
                4: "Um trabalho da Fila foi aceito; a entrega concluída ainda não foi registrada.",
            }[ordem] if iniciou else "Ainda não há registro de conclusão desta etapa."
            if alcancada:
                detalhe = "Resultado registrado na jornada."
            acao = None if alcancada else {
                2: {"rotulo": "Registrar meu primeiro item", "url": "/trilha/inventario/#primeiro-item"},
                3: {"rotulo": "Abrir Sandbox", "url": "/encomendas/sandbox/"},
                4: {"rotulo": "Abrir Fila", "url": "/encomendas/fila/"},
            }[ordem]
            itens = [_item(ordem, titulo, _estado(alcancada, iniciou if ordem == 2 else False),
                           detalhe, acao)]
            if ordem == 2 and iniciou and not alcancada:
                observacao = "Salvar um item não comprova sua conclusão."
        elif ordem == 5:
            detalhe = (
                "Recebimento confirmado contabilizado na jornada."
                if alcancada else
                "Há comprovante em leitura; ele ainda não conta como recebimento confirmado."
                if em_leitura else
                "Há registro que precisa de correção ou esclarecimento; ele não conta como confirmado."
                if corrigir else
                "Nenhum recebimento confirmado foi registrado."
            )
            itens = [_item(5, "Receber meu primeiro dinheiro por modelagem 3D",
                           _estado(alcancada, em_leitura), detalhe)]
            if corrigir and not alcancada:
                observacao = "A correção do comprovante depende do registro existente."
        else:
            limite = etapa["meta_cents"] if meta_escolhida else None
            titulo = etapa["conquista"].replace("Alcancei", "Alcançar", 1)
            itens = [
                _item(ordem, "Escolher minha meta pessoal",
                      _estado(meta_escolhida),
                      "Meta pessoal escolhida." if meta_escolhida else "Meta pessoal ainda não escolhida.",
                      sufixo="meta"),
                _item(ordem, titulo, _estado(alcancada, bool(meta_escolhida and total > 0)),
                      f"{_dinheiro(total)} confirmados de {_dinheiro(limite)}."
                      if limite is not None else
                      "O limite desta etapa depende da meta pessoal escolhida."),
            ]
            if not meta_escolhida:
                observacao = "Sem meta escolhida, nenhum limite monetário desta etapa é real."
        resultado[ordem] = {"itens": itens, "observacao": observacao}
    return resultado
