from urllib.parse import quote

from django.db import migrations, transaction


HOSTE = "meshcraft.top"
SLUG_DA_PAGINA = "oferta"
NOME_DO_PRODUTO_DE_TESTE = "Curso de Teste"
PRECO_DO_TESTE_EM_CENTAVOS = 990


def imagem_ficticia():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600">'
        '<rect width="1200" height="600" fill="#e5e7eb"/>'
        '<text x="50%" y="50%" text-anchor="middle" '
        'dominant-baseline="middle" font-family="sans-serif" font-size="64" '
        'fill="#111827">TESTE FICTÍCIO</text></svg>'
    )
    return "data:image/svg+xml," + quote(svg, safe="")


def secoes_ficticias(slug_da_oferta):
    imagem = imagem_ficticia()
    texto = "TESTE FICTÍCIO: conteúdo criado apenas para validar a página."
    return [
        {
            "nome": "cubo",
            "slots": {
                "headline": "TESTE FICTÍCIO: página completa de demonstração.",
                "subheadline": texto,
                "cta_texto": "TESTE FICTÍCIO: abrir checkout de teste",
                "cta_destino": f"/checkout/{slug_da_oferta}/",
                "imagem": imagem,
            },
        },
        {
            "nome": "viloes",
            "slots": {
                "headline": "TESTE FICTÍCIO: situação de demonstração.",
                "vilao_1": "TESTE FICTÍCIO: personagem A encontra uma etapa de exemplo.",
                "vilao_2": "TESTE FICTÍCIO: personagem B encontra outra etapa de exemplo.",
                "vilao_3": "TESTE FICTÍCIO: personagem C encontra uma terceira etapa.",
                "prova": "TESTE FICTÍCIO: estes personagens e situações não são reais.",
            },
        },
        {
            "nome": "metodo",
            "slots": {
                "headline": "TESTE FICTÍCIO: método de demonstração.",
                "texto": texto,
                "imagem": imagem,
                "prova": "TESTE FICTÍCIO: nenhum resultado real está sendo alegado.",
            },
        },
        {
            "nome": "instrumentos",
            "slots": {
                "headline": "TESTE FICTÍCIO: instrumentos de demonstração.",
                "texto": texto,
                "indice_de_estudios": "TESTE FICTÍCIO: índice ilustrativo, sem estúdios reais.",
                "prova": "TESTE FICTÍCIO: esta informação não é uma prova comercial.",
            },
        },
        {
            "nome": "percurso",
            "slots": {
                "headline": "TESTE FICTÍCIO: percurso de demonstração.",
                "texto": texto,
                "prova": "TESTE FICTÍCIO: não há alunos ou conclusão de curso neste relato.",
            },
        },
        {
            "nome": "tempo",
            "slots": {
                "headline": "TESTE FICTÍCIO: seção de duração.",
                "texto": "TESTE FICTÍCIO: nenhuma duração real é informada ou prometida.",
                "prova": "TESTE FICTÍCIO: não existem números de duração nesta simulação.",
            },
        },
        {
            "nome": "para_quem_nao_serve",
            "slots": {
                "headline": "TESTE FICTÍCIO: seis recusas de demonstração.",
                "recusa_1": "TESTE FICTÍCIO: cenário de recusa número um.",
                "recusa_2": "TESTE FICTÍCIO: cenário de recusa número dois.",
                "recusa_3": "TESTE FICTÍCIO: cenário de recusa número três.",
                "recusa_4": "TESTE FICTÍCIO: cenário de recusa número quatro.",
                "recusa_5": "TESTE FICTÍCIO: cenário de recusa número cinco.",
                "recusa_6": "TESTE FICTÍCIO: cenário de recusa número seis.",
            },
        },
        {
            "nome": "se_eu_parar",
            "slots": {
                "headline": "TESTE FICTÍCIO: seção sobre interrupção.",
                "texto": "TESTE FICTÍCIO: este texto não descreve regras reais de acesso.",
            },
        },
        {
            "nome": "oferta",
            "slots": {
                "headline": "TESTE FICTÍCIO: oferta para demonstração.",
                "o_que_recebe": "TESTE FICTÍCIO: conteúdo ilustrativo, sem entrega comercial.",
                "parcelamento": "TESTE FICTÍCIO: nenhuma condição de parcelamento é oferecida.",
                "cta_texto": "TESTE FICTÍCIO: abrir checkout de teste",
            },
        },
        {
            "nome": "carta",
            "slots": {
                "headline": "TESTE FICTÍCIO: carta de demonstração.",
                "texto": "TESTE FICTÍCIO: esta carta não foi escrita por uma pessoa real.",
                "assinatura": "TESTE FICTÍCIO: equipe fictícia de testes",
            },
        },
        {
            "nome": "perguntas",
            "slots": {
                "headline": "TESTE FICTÍCIO: perguntas de demonstração.",
                "perguntas": (
                    "TESTE FICTÍCIO: como funciona o acesso? Resposta de exemplo. "
                    "Existe garantia? Esta resposta fictícia não cria uma política "
                    "de reembolso nem altera direitos legais."
                ),
            },
        },
    ]


def site_ativo(site):
    return bool(site is not None and site.active)


def site_tem_oferta_padrao(site):
    return bool(site is not None and site.default_offer_slug)


def oferta_pode_receber_seed(oferta):
    return oferta is not None


def oferta_tem_slug_padrao(oferta, site):
    return oferta.slug == site.default_offer_slug


def oferta_tem_produto_de_teste(oferta):
    return oferta.product.name == NOME_DO_PRODUTO_DE_TESTE


def oferta_tem_preco_de_teste(oferta):
    return oferta.price_cents == PRECO_DO_TESTE_EM_CENTAVOS


def pagina_ainda_nao_existe(pagina_existe):
    return not pagina_existe


def gravar_pagina(banco, Page, PageDraft, PageVersion, site, oferta, secoes):
    @transaction.atomic(using=banco)
    def gravar():
        pagina = Page.objects.using(banco).create(
            site=site, slug=SLUG_DA_PAGINA, offer=oferta
        )
        PageVersion.objects.using(banco).create(page=pagina, version=1, secoes=secoes)
        PageDraft.objects.using(banco).create(
            page=pagina, base_version=1, secoes=secoes
        )

    gravar()


def semear_pagina_de_oferta_teste(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Offer = apps.get_model("ofertas", "Offer")
    Page = apps.get_model("paginas", "Page")
    PageDraft = apps.get_model("paginas", "PageDraft")
    PageVersion = apps.get_model("paginas", "PageVersion")
    banco = schema_editor.connection.alias if schema_editor else "default"

    site = Site.objects.using(banco).filter(host=HOSTE).first()
    if not site_ativo(site) or not site_tem_oferta_padrao(site):
        return

    ofertas = Offer.objects.using(banco).filter(site=site).select_related("product")
    oferta = next(
        (item for item in ofertas if oferta_tem_slug_padrao(item, site)), None
    )
    if not oferta_pode_receber_seed(oferta):
        return
    if not oferta_tem_produto_de_teste(oferta):
        return
    if not oferta_tem_preco_de_teste(oferta):
        return

    pagina_existe = (
        Page.objects.using(banco).filter(site=site, slug=SLUG_DA_PAGINA).exists()
    )
    if not pagina_ainda_nao_existe(pagina_existe):
        return

    secoes = [
        {"nome": secao["nome"], "ordem": ordem, "slots": secao["slots"]}
        for ordem, secao in enumerate(secoes_ficticias(oferta.slug))
    ]
    gravar_pagina(banco, Page, PageDraft, PageVersion, site, oferta, secoes)


class Migration(migrations.Migration):
    dependencies = [("paginas", "0001_initial")]

    operations = [
        migrations.RunPython(
            semear_pagina_de_oferta_teste,
            migrations.RunPython.noop,
        )
    ]
