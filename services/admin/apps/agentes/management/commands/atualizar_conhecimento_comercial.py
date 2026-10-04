"""`manage.py atualizar_conhecimento_comercial [--host meshcraft.top ...]`

Põe em dia, agora, o índice comercial dos sites (o mesmo que o laço dos robôs
faz sozinho a cada meia hora). Sem `--host`, vale para os sites já conhecidos.
Não gasta modelo: lê o catálogo e os documentos marcados.
"""

from django.core.management.base import BaseCommand

from apps.agentes import conhecimento_comercial


class Command(BaseCommand):
    help = "Atualiza o conhecimento comercial (catálogo, oferta, materiais) dos sites."

    def add_arguments(self, parser):
        parser.add_argument("--host", action="append", default=[], help="Domínio do site; pode repetir.")

    def handle(self, *args, **opcoes):
        hosts = opcoes.get("host") or conhecimento_comercial.hosts_conhecidos()
        for host in hosts:
            r = conhecimento_comercial.atualizar_host(host)
            linha = (
                f"{r['site']['host'] or host}: {r.get('novas', 0)} nova(s), {r.get('mudadas', 0)} mudada(s), "
                f"{r.get('iguais', 0)} igual(is), {r.get('sairam', 0)} saiu(saíram)"
            )
            if r.get("faltou"):
                linha += "; não respondeu: " + ", ".join(r["faltou"])
            self.stdout.write(linha)
