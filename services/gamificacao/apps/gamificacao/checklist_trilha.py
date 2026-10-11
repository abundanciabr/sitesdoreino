"""Checklist de leitura da jornada, sem criar nem alterar conquistas."""

from apps.gamificacao.models import FaixaDoAluno, RecebimentoDeclarado, AnexoDaJornada, JornadaPessoal
from apps.gamificacao.inicio import requisitos_branca


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
    registro_inicio = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    requisitos = requisitos_branca(registro_inicio, tem_anexo)
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
        elif ordem == 2:
            faixa = faixas.get(2)
            iniciou_item = tem_anexo or bool(faixa and faixa.origem == "item" and faixa.estado == "alcancada")
            detalhe_item = (
                "Resultado registrado na jornada." if alcancada else
                "Um arquivo foi guardado no inventário; a conclusão ainda não foi registrada." if tem_anexo else
                "Um item 3D foi salvo; a conclusão do primeiro item ainda não foi registrada." if iniciou_item else
                "Envie seu primeiro item 3D ou uma imagem dele e registre a conclusão."
            )
            itens = [
                _item(2, "Meu motivo", _estado(requisitos['motivo']),
                      "Motivo escolhido." if requisitos['motivo'] else "Escolha o motivo que te trouxe à modelagem 3D.",
                      {"rotulo": "Abrir meu motivo", "url": "/conquistas/inicio/motivo/"}, sufixo="motivo"),
                _item(2, "Meu objetivo e compromisso", _estado(requisitos['objetivo'] and requisitos['compromisso']),
                      "Objetivo definido e compromisso assumido." if requisitos['objetivo'] and requisitos['compromisso'] else
                      "Defina seu objetivo e assuma seu compromisso para este começo.",
                      {"rotulo": "Abrir meu objetivo e compromisso", "url": "/conquistas/inicio/objetivo/"}, sufixo="plano"),
                _item(2, "Meu primeiro item 3D", _estado(alcancada, iniciou_item),
                      detalhe_item,
                      {"rotulo": "Abrir meu primeiro item", "url": "/conquistas/inicio/item/"}, sufixo="item"),
                _item(2, "Enviar meu 3D", _estado(requisitos['item']),
                      "Arquivo do primeiro item guardado em privado." if requisitos['item'] else
                      "Envie o arquivo do seu item 3D ou uma imagem dele.",
                      {"rotulo": "Enviar meu 3D", "url": "/conquistas/inicio/item/#inicio-form-item"}, sufixo="envio"),
            ]
            if iniciou_item and not alcancada:
                observacao = "Seu trabalho continua guardado. Complete os quatro requisitos e confirme a conclusão para alcançar a faixa amarela."
        elif ordem in (3, 4):
            faixa = faixas.get(ordem)
            origem = {3: "sandbox", 4: "fila"}[ordem]
            iniciou = bool(faixa and faixa.origem == origem and faixa.estado == "alcancada")
            titulo = {
                3: "Concluir e entregar uma prática no Sandbox",
                4: "Concluir e entregar meu trabalho real na Fila",
            }[ordem]
            detalhe = {
                3: "Uma prática no Sandbox foi iniciada; a entrega concluída ainda não foi registrada.",
                4: "Um trabalho da Fila foi aceito; a entrega concluída ainda não foi registrada.",
            }[ordem] if iniciou else "Ainda não há registro de conclusão desta etapa."
            if alcancada:
                detalhe = "Resultado registrado na jornada."
            elif registro_inicio and registro_inicio.declaracoes.get(str(ordem)):
                detalhe = "Uma conclusão anterior está guardada. Você pode confirmá-la ao chegar a esta etapa."
            acao = None if alcancada else {
                3: {"rotulo": "Abrir Sandbox", "url": "/encomendas/sandbox/"},
                4: {"rotulo": "Abrir Fila", "url": "/encomendas/fila/"},
            }[ordem]
            itens = [_item(ordem, titulo, _estado(alcancada),
                           detalhe, acao)]
        elif ordem == 5:
            detalhe = (
                "Recebimento confirmado contabilizado na jornada."
                if alcancada else
                "Seu recebimento confirmado continua guardado. Conclua as faixas anteriores para avançar."
                if total > 0 else
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
        if ordem > 2 and not etapas[ordem - 1]['alcancada']:
            observacao = "Seus registros continuam guardados. Conclua os requisitos das faixas anteriores para alcançar esta faixa."
        resultado[ordem] = {"itens": itens, "observacao": observacao}
    return resultado
