# A VÍDEO-AULA EM TEXTO entra no vocabulário fechado das peças (TAR-233).
#
# ESQUEMA E SÓ ESQUEMA. O vocabulário de `Peca.tipo` é fechado no BANCO, por
# `tipo_de_peca_no_vocabulario_fechado`: sem esta migração, a peça nova é
# recusada com IntegrityError mesmo com o `TextChoices` já a declarando. Por
# isso a restrição cai e nasce de novo, agora com dezenove palavras.
#
# Nenhuma linha existente muda: aula que já está no ar simplesmente não tem
# esta peça, e a tela do aluno não mostra botão nenhum enquanto ela não for
# escrita. Quem a escreve é a porta de máquina (`putLesson`), nunca um
# `RunPython` daqui: [INV-CUR-C2] proíbe migração que roda código nesta célula
# (`tests/test_inv_c2_conteudo_so_pela_porta.py`).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cursos", "0006_curso_produto_id"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="peca",
            name="tipo_de_peca_no_vocabulario_fechado",
        ),
        migrations.AlterField(
            model_name="peca",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("pedido", "O pedido"),
                    ("em_jogo", "O que está em jogo"),
                    ("voce_vai_conseguir", "Você vai conseguir"),
                    ("recall", "Recall"),
                    ("par_de_comparacao", "Par de comparação"),
                    ("erro_produtivo", "Erro produtivo"),
                    ("eu_faco", "Eu faço"),
                    ("nos_fazemos", "Nós fazemos"),
                    ("voce_faz", "Você faz"),
                    ("drills", "Drills"),
                    ("erros_classicos", "Erros clássicos"),
                    ("regra_do_padrao", "Regra do padrão"),
                    ("critica_de_atelier", "Crítica de ateliê"),
                    ("checkpoint", "Checkpoint"),
                    ("pagina_do_portfolio", "Página do portfólio"),
                    ("dicionario_cartao_respostas", "Dicionário, cartão e respostas"),
                    ("roteiro", "Roteiro da aula (interno)"),
                    ("guia_do_mentor", "Guia do mentor (interno)"),
                    ("videoaula_em_texto", "A vídeo-aula, em texto"),
                ],
                max_length=30,
            ),
        ),
        migrations.AddConstraint(
            model_name="peca",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    (
                        "tipo__in",
                        [
                            "pedido",
                            "em_jogo",
                            "voce_vai_conseguir",
                            "recall",
                            "par_de_comparacao",
                            "erro_produtivo",
                            "eu_faco",
                            "nos_fazemos",
                            "voce_faz",
                            "drills",
                            "erros_classicos",
                            "regra_do_padrao",
                            "critica_de_atelier",
                            "checkpoint",
                            "pagina_do_portfolio",
                            "dicionario_cartao_respostas",
                            "roteiro",
                            "guia_do_mentor",
                            "videoaula_em_texto",
                        ],
                    )
                ),
                name="tipo_de_peca_no_vocabulario_fechado",
            ),
        ),
    ]
