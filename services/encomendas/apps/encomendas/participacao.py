"""Consulta comum de participação também para as entradas do percurso antigo."""

from .models import PerfilProfissional


def fase_liberada(site_id: str) -> bool:
    from .models import FaseMarketplace

    return FaseMarketplace.objects.filter(site_id=site_id, alunos_liberados=True).exists()


def perfil_autorizado(site_id: str, perfil_id) -> bool:
    from .marketplace import acesso_aluno

    pessoa = PerfilProfissional.objects.filter(
        site_id=site_id, pk=perfil_id
    ).values_list("pessoa_id", flat=True).first()
    return bool(pessoa and acesso_aluno(site_id=site_id, pessoa_id=pessoa))
