"""Checklist descritivo dos quatro caminhos; a avaliação é a fonte da conquista."""

from apps.gamificacao.models import AnexoDaJornada, JornadaPessoal, RecebimentoDeclarado
from apps.gamificacao.inicio import etapas_inicio


def _item(ordem, titulo, estado, detalhe, acao=None, *, sufixo=None, bloqueado=False):
    return {
        "id": f"criterio-{ordem}" if sufixo is None else f"{sufixo}-{ordem}",
        "titulo": titulo,
        "estado": estado,
        "detalhe": detalhe,
        "acao": acao,
        "bloqueado": bloqueado,
    }


def _dinheiro(cents):
    reais, centavos = divmod(int(cents), 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


ATIVIDADES = {
    None: {
        ordem: ("Escolher meu caminho", "Escolha um dos quatro caminhos para conhecer esta atividade.", "/trilha/inicio/motivo/")
        for ordem in (5, 6, 7)
    },
    "freelancer": {
        5: ("Concluir uma prática no Sandbox", "A IA confere o trabalho com o briefing da prática.", "/trilha/sandbox/"),
        6: ("Entregar o trabalho real da Fila do Dólar", "O cliente confere e aceita a entrega real.", "/trilha/fila/"),
        7: ("Conferir meu primeiro recebimento por modelagem 3D", "O material deve ligar trabalho, valor e recebimento; leitura visual não autentica pagamento.", "/trilha/recebimentos/"),
    },
    "ugc": {
        5: ("Mudar a cor do acessório e salvar", "Conferimos a alteração de cor realizada e salva.", "/trilha/ciclo/"),
        6: ("Ajustar a proporção e comparar", "Conferimos a mudança de proporção e sua comparação com a versão anterior.", "/trilha/ciclo/"),
        7: ("Apresentar meu acessório", "A imagem final, o nome e o uso imaginado serão avaliados.", "/trilha/ciclo/"),
    },
    "jogo": {
        5: ("Mudar a cor do objeto e salvar", "Conferimos a alteração de cor pensada para o cenário.", "/trilha/ciclo/"),
        6: ("Ajustar a proporção e registrar", "Conferimos a proporção alterada e o resultado registrado.", "/trilha/ciclo/"),
        7: ("Apresentar o visual do jogo", "A imagem final e o local de uso imaginado serão avaliados.", "/trilha/ciclo/"),
    },
    "aprender": {
        5: ("Experimentar uma mudança de cor e salvar", "Conferimos a mudança de cor realizada e salva.", "/trilha/ciclo/"),
        6: ("Alterar a proporção e observar", "Conferimos a pequena alteração e a diferença observada.", "/trilha/ciclo/"),
        7: ("Apresentar a criação final", "A imagem final e uma mudança feita desde o começo serão avaliadas.", "/trilha/ciclo/"),
    },
}


def montar_checklists(pessoa_id, site_id, jornada):
    """Descreve o que será conferido, sem transformar envio ou clique em aprovação."""
    registro = JornadaPessoal.objects.filter(pessoa_id=pessoa_id, site_id=site_id).first()
    caminho = jornada.get("caminho")
    inicio = registro.inicio if registro else {}
    tem_anexo = AnexoDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, passo=2,
    ).exists()
    etapas_inicio_atual = etapas_inicio(pessoa_id, site_id, registro, tem_anexo)
    etapas = {p["ordem"]: p for p in jornada["lista"]}
    recebimentos = list(RecebimentoDeclarado.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, fora_da_progressao=False,
    ).values("estado", "valor_cents", "leitura"))
    aguardando_print = any(r["estado"] in ("pendente", "analisando", "falha") for r in recebimentos)
    esclarecer_print = any(r["estado"] == "esclarecer" for r in recebimentos)
    total_conferido = jornada.get("total_conferido_cents", 0)
    resultado = {}

    for ordem, etapa in etapas.items():
        alcancada = etapa["alcancada"]
        anterior = ordem == 1 or etapas[ordem - 1]["alcancada"]
        bloqueado = not anterior
        feedback = etapa.get("feedback") or ""
        pendente_avaliacao = etapa.get("avaliacao_resultado") in ("incompleta", "falha")
        observacao = ("A avaliação desta etapa está guardada. A faixa chega após "
                      "o reconhecimento e as faixas anteriores." if bloqueado else "")
        if ordem == 1:
            itens = [_item(1, "Começar minha jornada", "concluido",
                           "A faixa branca é o começo dos quatro caminhos.")]
        elif ordem == 2:
            motivo = etapas_inicio_atual[0]
            motivo_estado = "concluido" if motivo["concluida"] else (
                "andamento" if inicio.get("motivo") else "pendente")
            plano_estado = "concluido" if alcancada else (
                "andamento" if inicio.get("compromisso_curso_em") or pendente_avaliacao else "pendente")
            itens = [
                _item(2, "Meu motivo", motivo_estado,
                      "Caminho escolhido." if motivo["concluida"] else
                      "Escolha um dos quatro caminhos para modelar em 3D.",
                      {"rotulo": "Escolher meu caminho", "url": "/trilha/inicio/motivo/"},
                      sufixo="motivo"),
                _item(2, "Meu compromisso", plano_estado,
                      feedback or ("Conferimos seu motivo, seu compromisso e a resposta sobre o próximo passo."
                                   if alcancada else
                                   "Assuma o compromisso e responda qual será o próximo passo; o site confere a resposta."),
                      {"rotulo": "Assumir meu compromisso", "url": "/trilha/inicio/objetivo/"},
                      sufixo="plano", bloqueado=not motivo["concluida"]),
            ]
        elif ordem == 3:
            itens = [_item(3, "Relatar meu primeiro item 3D",
                           "concluido" if alcancada else "andamento" if inicio.get("item_nome") or pendente_avaliacao else "pendente",
                           feedback or "Conte qual item criou e uma ação concreta que realizou. A IA avalia o relato, sem alegar que examinou um objeto ausente.",
                           {"rotulo": "Descrever meu item", "url": "/trilha/inicio/item/"},
                           sufixo="item", bloqueado=bloqueado)]
        elif ordem == 4:
            itens = [_item(4, "Apresentar meu item para análise",
                           "concluido" if alcancada else "andamento" if tem_anexo or pendente_avaliacao else "pendente",
                           feedback or "Apresente imagem ou arquivo 3D compatível. A IA confere o material e informa o que conseguiu examinar.",
                           {"rotulo": "Apresentar meu item", "url": "/trilha/inicio/envio/"},
                           sufixo="envio", bloqueado=bloqueado)]
        elif 5 <= ordem <= 7:
            titulo, descricao, url = ATIVIDADES.get(caminho, ATIVIDADES[None])[ordem]
            em_andamento = pendente_avaliacao or (ordem == 7 and caminho == "freelancer" and
                                                  (aguardando_print or esclarecer_print))
            itens = [_item(ordem, titulo,
                           "concluido" if alcancada else "andamento" if em_andamento else "pendente",
                           feedback or descricao,
                           None if alcancada else {"rotulo": "Abrir atividade", "url": url},
                           bloqueado=bloqueado)]
            if ordem == 7 and caminho == "freelancer" and not alcancada:
                if esclarecer_print:
                    observacao = "O material precisa mostrar um identificador que ligue o trabalho ao recebimento."
                elif aguardando_print:
                    observacao = "O print aguarda leitura; ainda não há avaliação concluída."
        else:
            limite = etapa["meta_cents"] if jornada["meta_escolhida"] else None
            percentual = etapa["percentual"]
            itens = [
                _item(ordem, "Escolher minha meta pessoal",
                      "concluido" if jornada["meta_escolhida"] else "pendente",
                      "Meta escolhida." if jornada["meta_escolhida"] else "Escolha uma meta para medir os graus.",
                      sufixo="meta"),
                _item(ordem, f"Alcançar {str(percentual).replace('.', ',')}% da meta",
                      "concluido" if alcancada else "andamento" if total_conferido else "pendente",
                      feedback or (f"{_dinheiro(total_conferido)} vinculados a trabalhos, de {_dinheiro(limite)} necessários."
                                   if limite is not None else "O limite depende da meta escolhida."),
                      bloqueado=bloqueado),
            ]
        resultado[ordem] = {"itens": itens, "observacao": observacao}
    return resultado
