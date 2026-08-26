# apps/sugestoes/management/commands/relatorio_id_da_plataforma.py
"""Quantas identidades locais já têm o id da plataforma, e quantas ainda não.

É o antídoto que a §9 do `docs/notificacoes/PLANO-MESTRE.md` exige nominalmente
para o risco número 1 da Fase 1 — *"Fase 1 sai errada e o id da plataforma some;
todo o resto herda o defeito"* — cuja segunda metade é **"relatório do que ficou
sem"**. O teste-guarda prova que o dado é gravado; este comando responde a
pergunta que nenhum teste responde: **em produção, agora, quanto falta?**

Por que a resposta não é "zero" no dia seguinte ao deploy, e isso é o desenho:
a migration `0006` não preenche linha antiga nenhuma (não há de onde derivar o
dado sem pedir à `identidade` a lista de gente dela — Lei 3). Cada linha antiga
ganha o id **na próxima entrada da pessoa**, então este número desce sozinho,
no ritmo em que as pessoas voltam. Um número que não desce em semanas é o
sintoma de que a frente 2 de `apps/core/sessao.py::cunhar_ou_recuperar` parou de
funcionar — e é para isso que ele existe.

**Somente leitura**: dois `COUNT(*)` e nada mais. Nenhuma escrita, nenhum efeito
colateral, seguro de rodar em produção a qualquer hora.
"""

from django.core.management.base import BaseCommand

from apps.sugestoes.models import Identidade


class Command(BaseCommand):
    help = "Quantas identidades locais já casaram com a identidade da plataforma"

    def handle(self, **opts):
        # Um `COUNT` por pergunta, e o total somado dos dois — em vez de um
        # `.count()` da tabela inteira. Se as duas consultas discordassem do
        # total, o relatório mentiria sem nada acusar; somando, "com + sem" é o
        # total por construção.
        com = Identidade.objects.filter(id_da_plataforma__isnull=False).count()
        sem = Identidade.objects.filter(id_da_plataforma__isnull=True).count()
        total = com + sem
        # Sem `%` quando não há ninguém: "0.0% casadas" de uma tabela vazia é
        # uma frase que parece um problema e não é.
        fatia = f" ({100 * com / total:.1f}%)" if total else ""

        self.stdout.write("RELATÓRIO — id da plataforma nas identidades da Caixa")
        self.stdout.write(f"  com o id da plataforma: {com}{fatia}")
        self.stdout.write(f"  ainda sem o id:         {sem}")
        self.stdout.write(f"  total de identidades:   {total}")
        if sem:
            self.stdout.write(
                "  Nenhuma ação necessária: cada uma ganha o id na próxima "
                "entrada da pessoa (INV-SUG11)."
            )
