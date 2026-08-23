# infra/sincronizar_sites.py — a Receita R11 mecanizada (Lei 1: mecanismo > documento).
# Roda DENTRO do container do catalogo, invocado pelo deploy-infra assim:
#   SITES_JSON="$(cat sites.json)" docker compose exec -T -e SITES_JSON \
#     catalogo python manage.py shell -c "$(cat sincronizar_sites.py)"
# (`shell -c` propaga exceção como exit != 0 — nunca use `shell < arquivo`, que
#  imprime o traceback e sai 0: seria o falso-verde do ARMADILHAS §5.6.)
#
# O que este código FAZ e o que ele NUNCA faz:
#   - Converge cada site LISTADO no JSON: cria se não existe; ajusta name,
#     active e default_offer_slug se divergirem — o Git é a fonte da verdade.
#   - Cria produto e oferta que faltarem (get_or_create, idempotente).
#   - NUNCA edita preço de oferta existente (oferta publicada não muda):
#     divergência vira AVISO no log; nova versão é decisão humana.
#   - Sites que NÃO estão no arquivo nunca são tocados — nem desativados.
#   - Fail-closed: JSON ausente/malformado/incompleto => exceção => o run do
#     deploy-infra reprova. Transação única: ou converge inteiro, ou nada muda.
import json
import os

from django.db import transaction

from apps.ofertas.models import Offer
from apps.produtos.models import Product
from apps.sites.models import Site

bruto = os.environ.get("SITES_JSON", "")
if not bruto.strip():
    raise SystemExit("ERRO: SITES_JSON vazio/ausente — nada foi sincronizado.")
dados = json.loads(bruto)
sites = dados.get("sites")
if not isinstance(sites, list) or not sites:
    raise SystemExit("ERRO: 'sites' precisa ser uma lista não vazia.")

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

        site, criado = Site.objects.get_or_create(
            host=host,
            defaults={
                "name": s["name"],
                "active": bool(s.get("active", True)),
                "default_offer_slug": padrao,
            },
        )
        if criado:
            print(f"criado: site {host}")
        else:
            mudancas = []
            for campo, valor in (
                ("name", s["name"]),
                ("active", bool(s.get("active", True))),
                ("default_offer_slug", padrao),
            ):
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

print("SINCRONIZAÇÃO DE SITES: concluída.")
