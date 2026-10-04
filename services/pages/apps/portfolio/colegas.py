"""Troca de comentários entre alunos do mesmo site, por escolha do autor."""
from .models import PedidoAosColegas
from . import vitrine


def pedir(portfolio, *, pergunta="", projeto=None):
    snapshot = vitrine.snapshot_rascunho(portfolio)
    if projeto is not None:
        ids = set(projeto.pecas.values_list("pk", flat=True))
        snapshot["obras"] = [obra for obra in snapshot["obras"] if obra["id"] in ids]
        materiais = []
        for obra in snapshot["obras"]:
            materiais.append(obra.get("imagem_principal", ""))
            materiais.extend(m["url"] for m in obra["complementos"] + obra["tecnicos"])
            materiais.extend(p["link"] for p in obra["provas_comerciais"])
        snapshot["imagens_ids"] = [i for i in snapshot["imagens_ids"] if any(url.endswith("/" + i) for url in materiais)]
    titulo = projeto.titulo if projeto else snapshot["conteudo"]["pagina"].get("titulo") or "Meu portfólio"
    # Somente peças selecionadas e a pergunta que o autor escolheu compartilhar.
    snapshot["conteudo"] = {"pagina": {"titulo": titulo}}
    snapshot["oferta"] = {}
    return PedidoAosColegas.objects.create(portfolio=portfolio, projeto=projeto,
        titulo=titulo[:200], pergunta=pergunta.strip()[:3000], materiais=snapshot)


def compartilha_imagem(portfolio, imagem_id):
    return any(str(imagem_id) in pedido.materiais.get("imagens_ids", [])
               for pedido in portfolio.pedidos_aos_colegas.filter(encerrado=False).only("materiais"))
