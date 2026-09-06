"""Diz de QUAL produto do catalogo um curso e, que e o que abre a sala.

    manage.py apontar_o_produto_do_curso --site <site> --curso <apelido> --produto <id>

E o outro lado do `criar_curso` do catalogo: la o curso vira produto e ganha um
id; aqui o curso da sala de aula passa a apontar para esse id. A matricula
guarda o mesmo id, e e essa igualdade que a sala confere a cada visita
(`DECISAO-cursos-matriculas-e-alunos.md` secao 1).

POR QUE UM COMANDO, E NAO UM CAMPO NA PORTA DE MAQUINA
-------------------------------------------------------
As duas resolviam o problema, e a diferenca e o preco de cada uma contra
quantas vezes ela e usada. Apontar o produto de um curso e um ato de
instalacao: acontece UMA vez por curso, na maquina, junto do `criar_curso` que
acabou de imprimir o id. Um campo na porta de maquina custaria um Rito de
Contrato, com o mantenedor presente, para um gesto que ninguem repete; e
enquanto ele nao existisse, o curso ficaria fechado. O comando existe no
minuto em que este PR pousa.

Se um dia isto virar coisa de trocar toda semana, a porta de maquina e o
caminho, e a troca sera barata: o campo ja existe no modelo.

POR QUE UM COMANDO, E NAO UMA MIGRACAO DE DADOS
------------------------------------------------
[INV-CUR-C2]: nenhuma migracao desta celula roda codigo
(`tests/test_inv_c2_conteudo_so_pela_porta.py`). E o id do produto so existe
depois de o catalogo criar o produto, na maquina, num tempo que nenhuma
migracao alcanca.

IDEMPOTENTE, E NAO TROCA EM SILENCIO
-------------------------------------
Rodar de novo com o mesmo id nao muda nada e diz isso. Rodar com um id
DIFERENTE do que ja esta la e RECUSADO, e a recusa e o ponto: trocar o produto
de um curso troca quem entra nele, e uma tecla errada no meio de um id de 36
letras nao pode virar "todo mundo perdeu o acesso" sem ninguem ver. Quem
realmente quer trocar diz `--trocar`.
"""

from django.core.management.base import BaseCommand, CommandError

from apps.cursos.models import Curso


class Command(BaseCommand):
    help = (
        "Aponta o curso desta sala para o produto do catalogo (idempotente). "
        "O id do produto e o que `manage.py criar_curso` imprime no catalogo."
    )

    def add_arguments(self, parser):
        parser.add_argument("--site", required=True, help="o id do site da escola")
        parser.add_argument(
            "--curso", required=True, help="o apelido do curso no endereco"
        )
        parser.add_argument(
            "--produto", required=True, help="o id do produto no catalogo"
        )
        parser.add_argument(
            "--trocar",
            action="store_true",
            help="aceita trocar um produto ja apontado por outro",
        )

    def handle(self, *, site: str, curso: str, produto: str, trocar: bool, **opts):
        site = site.strip()
        apelido = curso.strip().lower()
        produto = produto.strip()

        if not site or not apelido or not produto:
            raise CommandError(
                "--site, --curso e --produto nao podem ser vazios.\n"
                "Exemplo: manage.py apontar_o_produto_do_curso "
                "--site 3f2b1c9a-... --curso profissional --produto 7d4e...\n"
                "O id do produto e o que `manage.py criar_curso` imprime no catalogo."
            )
        if len(produto) > 64:
            raise CommandError(
                f"o id do produto tem {len(produto)} letras, e o campo guarda 64.\n"
                "Confira se voce colou o id (algo como 7d4e1f2a-...) e nao o "
                "nome do curso."
            )

        # Fail-closed com o nome de tudo na mensagem: um curso que nao existe
        # aqui costuma ser o apelido errado ou o site errado, e adivinhar qual
        # dos dois custa uma ida a maquina.
        alvo = Curso.objects.filter(site_id=site, slug=apelido).first()
        if alvo is None:
            conhecidos = ", ".join(
                c.slug for c in Curso.objects.filter(site_id=site).order_by("slug")
            )
            raise CommandError(
                f"nao existe curso '{apelido}' no site '{site}'. "
                + (
                    f"Os cursos deste site sao: {conhecidos}."
                    if conhecidos
                    else "Este site nao tem curso nenhum: rode o semear_esqueleto antes."
                )
                + "\nNada foi alterado."
            )

        if alvo.produto_id == produto:
            self.stdout.write(f"ja estava apontado: {alvo.slug} -> {produto}")
            return

        if alvo.produto_id and not trocar:
            raise CommandError(
                f"o curso '{alvo.slug}' ja aponta para o produto "
                f"'{alvo.produto_id}', e voce pediu '{produto}'.\n"
                "Trocar o produto de um curso troca QUEM ENTRA nele: quem tem a "
                "matricula antiga perde o acesso na hora.\n"
                "Se e isso mesmo que voce quer, rode de novo com --trocar no "
                "fim. Nada foi alterado."
            )

        anterior = alvo.produto_id
        alvo.produto_id = produto
        alvo.save(update_fields=["produto_id"])

        if anterior:
            self.stdout.write(
                self.style.WARNING(
                    f"TROCADO: {alvo.slug} deixou de apontar para '{anterior}' "
                    f"e passou a apontar para '{produto}'."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS(f"apontado: {alvo.slug} -> {produto}"))
        self.stdout.write("   a sala deste curso ja abre para quem tem essa matricula.")
