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

    O nome **não muda sozinho**, e trocá-lo pede `--renomear`. A opção existe
    porque não há tela de produto no painel: sem ela, quem errasse o nome de um
    curso não teria caminho nenhum para corrigir, e a recusa apontaria para uma
    tela que não existe.
    """

    help = (
        "Cadastra um curso como produto do catálogo (idempotente pelo apelido). "
        "Imprime o id, que é o que a matrícula guarda."
    )

    def add_arguments(self, parser):
        parser.add_argument("apelido", help="a chave curta, minúscula, sem espaço")
        parser.add_argument("nome", help="o nome que a pessoa lê na lista")
        parser.add_argument(
            "--renomear",
            action="store_true",
            help=(
                "troca o nome de um curso que já existe. Sem esta opção, um nome "
                "diferente avisa e não altera nada"
            ),
        )

    def handle(self, apelido: str, nome: str, renomear: bool = False, **opts):
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
        elif curso.name == nome:
            self.stdout.write(f"ℹ já existia: {curso.name}")
        elif renomear:
            antigo = curso.name
            curso.name = nome
            curso.save(update_fields=["name"])
            self.stdout.write(
                self.style.SUCCESS(f"✅ renomeado: '{antigo}' agora é '{curso.name}'")
            )
        else:
            # Rodar de novo com outro nome não renomeia em silêncio: o nome sai
            # na lista de escolher, e trocá-lo é decisão de quem opera. A opção
            # existe porque, sem ela, corrigir o nome de um curso não teria
            # caminho nenhum: não há tela de produto no painel.
            self.stdout.write(
                self.style.WARNING(
                    f"ℹ já existia com OUTRO nome: '{curso.name}' (você pediu '{nome}').\n"
                    "   Nada foi alterado. Para trocar mesmo, rode de novo com --renomear:\n"
                    f"   manage.py criar_curso {curso.slug} '{nome}' --renomear"
                )
            )

        self.stdout.write(f"   apelido: {curso.slug}")
        self.stdout.write(f"   id:      {curso.id}")
