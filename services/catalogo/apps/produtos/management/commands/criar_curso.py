# apps/produtos/management/commands/criar_curso.py
from django.core.management.base import BaseCommand, CommandError

from apps.produtos.models import Product


class Command(BaseCommand):
    """Cadastra um curso como produto do catálogo, e imprime o id dele.

    Até 06/09/2026 o único jeito de um `Product` nascer era o `seed_esqueleto`,
    que cria uma peça de teste de ponta a ponta. Não havia caminho nenhum para
    cadastrar um curso de verdade, e por isso a tela de liberar aluno não tinha
    o que oferecer (`DECISAO-cursos-matriculas-e-alunos.md` §6).

    O **preço fica em zero** e é assim de propósito: quem cobra é a Offer, que
    é por site, e a plataforma ainda não vende. Zero aqui significa "não está à
    venda por este produto", não "de graça".
    """

    help = (
        "Cadastra um curso como produto do catálogo (idempotente pelo apelido). "
        "Imprime o id, que é o que a matrícula guarda."
    )

    def add_arguments(self, parser):
        parser.add_argument("apelido", help="a chave curta, minúscula, sem espaço")
        parser.add_argument("nome", help="o nome que a pessoa lê na lista")

    def handle(self, apelido: str, nome: str, **opts):
        apelido = apelido.strip().lower()
        nome = nome.strip()
        if not apelido or not nome:
            raise CommandError(
                "apelido e nome não podem ser vazios.\n"
                "Exemplo: manage.py criar_curso profissional 'Profissional'"
            )

        curso, criado = Product.objects.get_or_create(
            slug=apelido,
            defaults={"name": nome, "price_cents": 0, "active": True},
        )

        if criado:
            self.stdout.write(self.style.SUCCESS(f"✅ criado: {curso.name}"))
        elif curso.name != nome:
            # Rodar de novo com outro nome não renomeia em silêncio: o nome sai
            # na lista de escolher, e trocá-lo é decisão de quem opera.
            self.stdout.write(
                self.style.WARNING(
                    f"ℹ já existia com OUTRO nome: '{curso.name}' (você pediu '{nome}').\n"
                    "   Nada foi alterado. Para renomear, mude pelo painel do catálogo."
                )
            )
        else:
            self.stdout.write(f"ℹ já existia: {curso.name}")

        self.stdout.write(f"   apelido: {curso.slug}")
        self.stdout.write(f"   id:      {curso.id}")
