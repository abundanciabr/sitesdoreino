# infra/sincronizar_sites.py — a Receita R11 mecanizada (Lei 1: mecanismo > documento).
# Roda DENTRO do container do catalogo, invocado pelo deploy-infra assim:
#   SITES_JSON="$(cat sites.json)" docker compose exec -T -e SITES_JSON \
#     catalogo python manage.py shell -c "$(cat sincronizar_sites.py)"
# (`shell -c` propaga exceção como exit != 0 — nunca use `shell < arquivo`, que
#  imprime o traceback e sai 0: seria o falso-verde do ARMADILHAS §5.6.)
#
# ─────────────────────────────────────────────────────────────────────────────
# POR QUE ESTE SCRIPT É TOLERANTE À VERSÃO DA IMAGEM (leia antes de "consertar")
# ─────────────────────────────────────────────────────────────────────────────
# Ele é injetado no container que JÁ ESTÁ RODANDO na VPS — cuja imagem pode ser
# mais VELHA que este arquivo. `deploy-infra` e `deploy-celula` disparam EM
# PARALELO no mesmo merge; não há ordem entre os dois. Em 24/08/2026 isso travou
# o canal de deploy inteiro: este script importava `normalizar_idiomas` de
# `apps.sites.models` — símbolo que só existe na imagem NOVA — e o run morreu em
# `ImportError`; o portão de deploy então reprovou o `deploy-celula` por causa do
# irmão vermelho; e a imagem nova, única fonte do símbolo, só chega pelo
# `deploy-celula`. Impasse fechado (armadilhas/078).
#
# Daí as duas regras deste arquivo:
#   1. ZERO import de símbolo recém-criado da célula. Só ORM estável (Site,
#      Product, Offer) e `django.db`.
#   2. Campo que a IMAGEM em execução ainda não conhece vira PENDÊNCIA declarada
#      em voz alta, nunca exceção: sincroniza o que dá, avisa, sai 0. Depois que
#      o `deploy-celula` publicar a imagem nova e rodar `migrate`, RE-RODAR o
#      `deploy-infra` grava o que ficou pendente — é assim que a fase 4 do i18n
#      fecha, e é por isso que a tolerância existe.
#      (A tolerância para AÍ: modelo novo + banco sem a coluna reprova de
#       propósito — o porquê medido está em `idioma_disponivel`.)
# ─────────────────────────────────────────────────────────────────────────────
#
# O que este código FAZ e o que ele NUNCA faz:
#   - Converge cada site LISTADO no JSON: cria se não existe; ajusta name,
#     active, default_offer_slug e os idiomas (default_language + languages) se
#     divergirem — o Git é a fonte da verdade.
#   - Valida a declaração de idiomas SEMPRE, inclusive contra imagem velha:
#     sites.json incoerente reprova o deploy (o conserto é no Git, não na ordem
#     dos workflows). A regra é CÓPIA CONSCIENTE do `normalizar_idiomas` de
#     `services/catalogo/apps/sites/models.py` — cópia porque importar de lá é
#     exatamente o que quebrou o canal; e toda cópia consciente exige guarda
#     mecânica contra deriva (docs/historico/RESOLVIDAS.md §5.11). A guarda é
#     `ci/tests/test_sincronizar_sites_tolerante.py`, que roda as duas
#     implementações lado a lado sobre o mesmo corpo de casos: mudou a regra no
#     modelo, aquele teste fica vermelho até esta cópia acompanhar.
#   - Cria produto e oferta que faltarem (get_or_create, idempotente).
#   - NUNCA edita preço de oferta existente (oferta publicada não muda):
#     divergência vira AVISO no log; nova versão é decisão humana.
#   - Sites que NÃO estão no arquivo nunca são tocados — nem desativados.
#   - Fail-closed: JSON ausente/malformado/incompleto => exceção => o run do
#     deploy-infra reprova. Transação única: ou converge inteiro, ou nada muda.
#   - NUNCA grava torto e NUNCA finge que gravou: campo indisponível sai do
#     conjunto de escrita e aparece NOMEADO no aviso do fim do log.
import json
import os
import re

from django.db import connection, transaction

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site

# Os campos que podem faltar na imagem/banco em execução (PLANO-I18N, fase 4).
CAMPOS_DE_IDIOMA = ("default_language", "languages")

# BCP 47 na forma que aparece na URL: minúscula, com hífen (en, pt-br, es).
# Cópia consciente de `apps/sites/models.py` — ver o cabeçalho.
CODIGO_DE_IDIOMA = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")


class DeclaracaoIncoerente(Exception):
    """Idiomas declarados no sites.json que não fecham entre si."""


def normalizar_idiomas(default_language, languages):
    """Normaliza e VALIDA a declaração de idiomas de um site — fail-closed.

    CÓPIA CONSCIENTE de `normalizar_idiomas` em
    `services/catalogo/apps/sites/models.py`, mensagens inclusive. Não é
    esquecimento: importar de lá amarra este script à versão da imagem contra a
    qual ele roda, e foi assim que o canal de deploy travou (armadilhas/078). A
    deriva entre as duas cópias é impedida por
    `ci/tests/test_sincronizar_sites_tolerante.py`, não por boa vontade.

    Devolve `(default_language, languages)` na forma canônica: código em
    minúsculas e `indexable` sempre explícito — assim a comparação de
    convergência lá embaixo é um `!=` honesto, sem falso "mudou" a cada deploy.

    Levanta `DeclaracaoIncoerente` em qualquer incoerência. Site monolíngue é
    `("", [])` e continua passando intocado por aqui.
    """
    padrao = (default_language or "").strip().lower()

    if not languages:
        languages = []
    if not isinstance(languages, list):
        raise DeclaracaoIncoerente(
            "languages precisa ser uma lista de objetos {code, indexable}."
        )

    normalizados = []
    vistos = set()
    for item in languages:
        if not isinstance(item, dict):
            raise DeclaracaoIncoerente(
                f"cada idioma precisa ser um objeto {{code, indexable}}, veio {item!r}."
            )
        bruto_do_code = item.get("code")
        if not isinstance(bruto_do_code, str) or not bruto_do_code.strip():
            raise DeclaracaoIncoerente(f"idioma sem 'code': {item!r}.")
        code = bruto_do_code.strip().lower()
        if not CODIGO_DE_IDIOMA.match(code):
            raise DeclaracaoIncoerente(
                f"código de idioma inválido: {bruto_do_code!r} — esperado BCP 47 "
                f"minúsculo, como 'en', 'pt-br', 'es'."
            )
        if code in vistos:
            raise DeclaracaoIncoerente(f"código de idioma duplicado: {code!r}.")
        vistos.add(code)

        indexable = item.get("indexable", True)
        if not isinstance(indexable, bool):
            raise DeclaracaoIncoerente(
                f"'indexable' de {code!r} precisa ser true/false, veio {indexable!r}."
            )
        normalizados.append({"code": code, "indexable": indexable})

    if not normalizados:
        # Monolíngue é a AUSÊNCIA dos dois (contrato: "ausente ⇒ monolíngue").
        # Idioma padrão sem idioma nenhum é o mesmo tipo de torto que o inverso.
        if padrao:
            raise DeclaracaoIncoerente(
                f"default_language {padrao!r} declarado sem 'languages' — site sem "
                f"idiomas é monolíngue e não tem idioma padrão."
            )
        return "", []

    if not padrao:
        raise DeclaracaoIncoerente(
            f"site com idiomas {sorted(vistos)} precisa de default_language."
        )
    if padrao not in vistos:
        raise DeclaracaoIncoerente(
            f"default_language {padrao!r} não está entre os idiomas declarados "
            f"{sorted(vistos)}."
        )
    return padrao, normalizados


def idioma_disponivel():
    """A imagem em execução conhece os campos de idioma do Site?

    Devolve `(True, "")` ou `(False, motivo)` — o motivo vai inteiro para o log,
    porque "os idiomas não foram gravados" sem o porquê é o mesmo que silêncio.

    Roda ANTES de abrir a transação de propósito: erro de banco capturado
    DENTRO de um `atomic()` envenena a transação inteira (ARMADILHAS §4.8).

    São duas perguntas, e elas terminam DIFERENTE — a assimetria é medida, não
    esquecimento:

    - **Modelo sem os campos** (imagem velha) ⇒ TOLERA. É exatamente o impasse
      que este arquivo existe para quebrar, e o resto do sites.json converge
      normalmente: o ORM da imagem velha nem sabe que os campos existem.
    - **Modelo com os campos e banco sem as colunas** (`migrate` não rodou) ⇒
      REPROVA, com mensagem de operador. Aqui não há "sincronizar o que dá":
      todo SELECT do Django pede TODAS as colunas do modelo, então nem
      `Site.objects.get_or_create(host=...)` roda — medido em 24/08/2026,
      `OperationalError: no such column: sites_site.default_language`. Seguir
      em frente seria fingir. E este estado não é ordem de workflow: é célula
      meio-implantada, com o catálogo devolvendo erro para quem o consome.
    """
    no_modelo = {campo.name for campo in Site._meta.get_fields()}
    faltam = [nome for nome in CAMPOS_DE_IDIOMA if nome not in no_modelo]
    if faltam:
        return False, (
            f"o modelo Site da imagem do catálogo EM EXECUÇÃO não tem "
            f"{', '.join(faltam)} — é uma imagem anterior à fase 4 do i18n"
        )

    tabela = Site._meta.db_table
    with connection.cursor() as cursor:
        no_banco = {
            coluna.name
            for coluna in connection.introspection.get_table_description(cursor, tabela)
        }
    faltam = [
        Site._meta.get_field(nome).column
        for nome in CAMPOS_DE_IDIOMA
        if Site._meta.get_field(nome).column not in no_banco
    ]
    if faltam:
        raise SystemExit(
            f"ERRO: o modelo Site tem {', '.join(CAMPOS_DE_IDIOMA)}, mas a tabela "
            f"{tabela} não tem a(s) coluna(s) {', '.join(faltam)} — a imagem nova "
            f"subiu e o `migrate` NÃO rodou. Neste estado o catálogo não consegue "
            f"nem LER a tabela de sites (todo SELECT pede as colunas que faltam), "
            f"então NÃO há nada que dê para sincronizar com segurança. Conserto: "
            f"rode o migrate da célula (o deploy-celula faz isso) e re-rode o "
            f"deploy-infra. Isto NÃO é o impasse de ordem entre workflows "
            f"(armadilhas/078) — aquele é imagem VELHA, e este script o tolera."
        )
    return True, ""


bruto = os.environ.get("SITES_JSON", "")
if not bruto.strip():
    raise SystemExit("ERRO: SITES_JSON vazio/ausente — nada foi sincronizado.")
dados = json.loads(bruto)
sites = dados.get("sites")
if not isinstance(sites, list) or not sites:
    raise SystemExit("ERRO: 'sites' precisa ser uma lista não vazia.")

suporta_idioma, motivo_sem_idioma = idioma_disponivel()
if not suporta_idioma:
    print(f"AVISO: {motivo_sem_idioma}.")
    print("AVISO: este run sincroniza TUDO menos os idiomas — detalhe no fim do log.")
idiomas_pendentes = []

with transaction.atomic():
    for s in sites:
        host = s["host"].strip().lower()
        if not host or "." not in host or any(c in host for c in " /:@"):
            raise SystemExit(f"ERRO: host inválido no sites.json: {s['host']!r}")
        ofertas = s["ofertas"]
        if not isinstance(ofertas, list) or not ofertas:
            raise SystemExit(f"ERRO: {host} sem lista de ofertas.")
        slugs = [o["slug"] for o in ofertas]
        padrao = s["default_offer_slug"]
        if padrao not in slugs:
            raise SystemExit(
                f"ERRO: default_offer_slug {padrao!r} de {host} não está nas ofertas {slugs} — a raiz responderia 404."
            )

        # Idioma é dado do site (PLANO-I18N D3). Ausência dos dois campos =
        # site monolíngue, que é o caso de todo site que não declarou nada.
        # A VALIDAÇÃO roda mesmo em imagem velha: declaração torta no Git é erro
        # do Git, e escondê-la atrás da tolerância seria fingir que passou.
        try:
            idioma_padrao, idiomas = normalizar_idiomas(
                s.get("default_language", ""), s.get("languages", [])
            )
        except DeclaracaoIncoerente as erro:
            raise SystemExit(f"ERRO: idiomas de {host} incoerentes — {erro}")

        campos_do_git = [
            ("name", s["name"]),
            ("active", bool(s.get("active", True))),
            ("default_offer_slug", padrao),
        ]
        if suporta_idioma:
            campos_do_git += [
                # `idiomas` já vem normalizado (code minúsculo, indexable
                # explícito) e é assim que fica guardado — então o != compara
                # duas formas canônicas, sem falso "mudou" a cada deploy.
                ("default_language", idioma_padrao),
                ("languages", idiomas),
            ]
        elif idiomas:
            # Só vira pendência o que havia REALMENTE a gravar: site monolíngue
            # não perde nada rodando contra imagem velha.
            idiomas_pendentes.append(host)

        site, criado = Site.objects.get_or_create(
            host=host, defaults=dict(campos_do_git)
        )
        if criado:
            print(f"criado: site {host}")
        else:
            mudancas = []
            for campo, valor in campos_do_git:
                if getattr(site, campo) != valor:
                    setattr(site, campo, valor)
                    mudancas.append(campo)
            if mudancas:
                site.save()
                print(f"ajustado: site {host} ({', '.join(mudancas)})")
            else:
                print(f"ok: site {host} já conforme")

        for o in ofertas:
            preco = o["price_cents"]
            if not isinstance(preco, int) or isinstance(preco, bool) or preco < 1:
                raise SystemExit(
                    f"ERRO: price_cents inválido em {host}/{o['slug']}: {preco!r} (centavos inteiros, >= 1)."
                )
            p = o["produto"]
            produto, p_criado = Product.objects.get_or_create(
                slug=p["slug"],
                defaults={"name": p["name"], "price_cents": preco, "active": True},
            )
            print(f"{'criado' if p_criado else 'ok'}: produto {produto.slug}")
            oferta, o_criada = Offer.objects.get_or_create(
                site=site,
                slug=o["slug"],
                defaults={"product": produto, "price_cents": preco, "version": 1},
            )
            if o_criada:
                print(f"criada: oferta {host}/{oferta.slug} ({preco} cents)")
            elif oferta.price_cents != preco:
                print(
                    f"AVISO: oferta {host}/{oferta.slug} tem {oferta.price_cents} cents em produção e {preco} no arquivo — NÃO editada (nova versão é decisão humana)."
                )
            else:
                print(f"ok: oferta {host}/{oferta.slug} já conforme")

if idiomas_pendentes:
    print("=" * 78)
    print("AVISO: IDIOMAS NÃO GRAVADOS NESTE RUN — pendência declarada, não falha.")
    print(f"Motivo: {motivo_sem_idioma}.")
    print(f"Campos pendentes: {', '.join(CAMPOS_DE_IDIOMA)}.")
    print(f"Sites afetados: {', '.join(idiomas_pendentes)}.")
    print("Nada foi gravado pela metade: o resto do sites.json convergiu inteiro e")
    print("os idiomas ficaram exatamente como já estavam no banco.")
    print("POR QUE O RUN SEGUE VERDE: a imagem nova só chega pelo deploy-celula, e o")
    print("portão de deploy reprova o deploy-celula enquanto o deploy-infra estiver")
    print("vermelho — falhar aqui travaria o canal de deploy inteiro.")
    print("O QUE FALTA: assim que o deploy-celula publicar a imagem nova e rodar")
    print("migrate, RE-RODE o deploy-infra; esta mesma sincronização grava os")
    print("idiomas e este aviso some sozinho.")
    print("=" * 78)
    print("SINCRONIZAÇÃO DE SITES: concluída COM IDIOMAS PENDENTES (aviso acima).")
else:
    print("SINCRONIZAÇÃO DE SITES: concluída.")
