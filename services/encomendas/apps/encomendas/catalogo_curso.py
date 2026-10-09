"""Conteúdo comum da prática e dos pedidos reais; não calcula pagamentos ou XP."""

from copy import deepcopy

VERSAO = "20261009"
CATEGORIAS = (
    ("espadas_objetos", "Armas", "AK-47, Pistola e Espada", "espadas"),
    ("pets", "Animais", "Raposa", "pets"),
    ("carros", "Carros", "Carro", "carros"),
    ("roupas", "Roupas", "Roupa do Goku", "roupas"),
    ("cabelos", "Cabelos", "Masculino e feminino", "cabelos"),
    ("livre", "Projeto livre", "Outro item à escolha do aluno", "livre"),
)
CHAVES_CATEGORIAS = frozenset(c[0] for c in CATEGORIAS)
CATEGORIAS_HISTORICAS = frozenset({"chapeus", "personagens", "acessorios", "animacoes"})


def _projeto(slug, titulo, categoria, briefing, criterios):
    return {
        "slug": slug, "titulo": titulo, "categoria": categoria,
        "briefing": briefing, "tema_curso": titulo,
        "referencias": ["Referência utilizada na atividade do curso ou escolhida para este projeto."],
        "entregaveis": ["Arquivo Blender editável", "Prévias frontal, lateral e em perspectiva"],
        "criterios": criterios + " Arquivo editável organizado e prévias legíveis.",
    }


PROJETOS = (
    _projeto("curso-ak47", "AK-47", "espadas_objetos",
             "Modele uma AK-47 como objeto 3D, aplicando as técnicas de modelagem estudadas no curso. Use a referência para construir os volumes e as proporções do objeto.",
             "Volumes e silhueta coerentes com a referência."),
    _projeto("curso-pistola", "Pistola", "espadas_objetos",
             "Modele uma pistola como objeto 3D, aplicando as técnicas estudadas no curso. Escolha uma referência e construa os volumes e as proporções do objeto.",
             "Volumes e silhueta coerentes com a referência."),
    _projeto("curso-espada", "Espada", "espadas_objetos",
             "Modele uma espada com lâmina, guarda e cabo, aplicando as técnicas estudadas no curso e seguindo a referência escolhida.",
             "Lâmina, guarda e cabo reconhecíveis e proporcionais."),
    _projeto("curso-raposa", "Raposa", "pets",
             "Modele uma raposa, aplicando as técnicas estudadas no curso. Use a referência para construir corpo, cabeça, orelhas e cauda.",
             "Silhueta de raposa reconhecível e proporções coerentes."),
    _projeto("curso-carro", "Carro", "carros",
             "Modele um carro, aplicando as técnicas estudadas no curso. Escolha uma referência e trabalhe os volumes da carroceria, as rodas e as proporções gerais.",
             "Carroceria e rodas organizadas, com proporções coerentes com a referência."),
    _projeto("curso-roupa-goku", "Roupa do Goku", "roupas",
             "Modele a roupa do Goku, aplicando as técnicas de roupas estudadas no curso. Trabalhe os volumes e o caimento conforme a referência; o projeto é a roupa, sem exigir a produção do personagem completo.",
             "Peças da roupa e caimento coerentes com a referência."),
    _projeto("curso-cabelo-masculino", "Cabelo masculino", "cabelos",
             "Modele um cabelo masculino, aplicando as técnicas estudadas no curso. Escolha o penteado de referência e construa o volume e a distribuição das mechas.",
             "Volume e mechas coerentes com o penteado escolhido."),
    _projeto("curso-cabelo-feminino", "Cabelo feminino", "cabelos",
             "Modele um cabelo feminino, aplicando as técnicas estudadas no curso. Escolha o penteado de referência e construa o volume e a distribuição das mechas.",
             "Volume e mechas coerentes com o penteado escolhido."),
    _projeto("curso-projeto-livre", "Projeto livre", "livre",
             "Escolha outro item que deseja modelar com as técnicas estudadas no curso. Descreva o objeto e a referência antes de iniciar; use a conversa para esclarecer o combinado.",
             "O item corresponde à descrição e à referência combinadas."),
)
SLUGS = frozenset(p["slug"] for p in PROJETOS)

# A mesma arte acompanha o projeto na prática e no pedido real. As imagens
# ficam em duas pranchas; o enquadramento só escolhe o quadrante, sem distorcer.
ARTES_PROJETOS = {
    "curso-ak47": ("curso-objetos-v1", "0 0 1 1"),
    "curso-espada": ("curso-objetos-v1", "1 0 1 1"),
    "curso-pistola": ("curso-objetos-v1", "0 1 1 1"),
    "curso-raposa": ("curso-objetos-v1", "1 1 1 1"),
    "curso-carro": ("curso-modelagem-v1", "0 0 1 1"),
    "curso-roupa-goku": ("curso-modelagem-v1", "1 0 1 1"),
    "curso-cabelo-masculino": ("curso-modelagem-v1", "0 1 1 1"),
    "curso-cabelo-feminino": ("curso-modelagem-v1", "1 1 1 1"),
}
ARQUIVOS_ILUSTRACOES = frozenset({"curso-objetos-v1", "curso-modelagem-v1", "curso-categorias-v1"})


def arte_projeto(slug):
    item = ARTES_PROJETOS.get(slug)
    return {"arquivo": item[0], "enquadramento": item[1], "largura": 2, "altura": 2} if item else None


def arte_categoria(chave):
    if chave == "espadas_objetos":
        return {"arquivo": "curso-categorias-v1", "enquadramento": "0.02 0.105 0.465 0.38", "largura": 1, "altura": 1}
    if chave == "cabelos":
        return {"arquivo": "curso-modelagem-v1", "enquadramento": "0 1 2 1", "largura": 2, "altura": 2}
    slug = {"pets": "curso-raposa", "carros": "curso-carro", "roupas": "curso-roupa-goku"}.get(chave)
    return arte_projeto(slug)


def projeto(slug):
    return next((deepcopy(p) for p in PROJETOS if p["slug"] == slug), None)


def dados_publicos():
    return {"versao": VERSAO,
            "categorias": [{"chave": c, "titulo": t, "descricao": d, "arte": a}
                           for c, t, d, a in CATEGORIAS],
            "projetos": deepcopy(list(PROJETOS))}


def retrato(slug):
    item = projeto(slug)
    if item is None:
        raise ValueError("Escolha um projeto do catálogo do curso.")
    return {"versao": VERSAO, **item}


def preparar_projetos(*, site_id, ativar=False):
    """Prepara rascunhos; a ativação é uma chamada expressa, nunca uma migração."""
    from django.db import transaction
    from .sandbox_models import ProjetoSandbox

    with transaction.atomic():
        projetos = []
        for item in PROJETOS:
            dados = {k: deepcopy(item[k]) for k in (
                "titulo", "categoria", "briefing", "referencias", "entregaveis", "criterios")}
            obj, criado = ProjetoSandbox.objects.get_or_create(
                site_id=site_id, slug=item["slug"], defaults={**dados, "ativo": False})
            if ativar:
                for chave, valor in dados.items():
                    setattr(obj, chave, valor)
                obj.ativo = True
                obj.save(update_fields=[*dados, "ativo"])
            projetos.append(obj)
        if ativar:
            # Preserva os projetos antigos, trabalhos e snapshots; só muda a seleção futura.
            ProjetoSandbox.objects.filter(site_id=site_id, ativo=True).exclude(slug__in=SLUGS).update(ativo=False)
    return projetos
