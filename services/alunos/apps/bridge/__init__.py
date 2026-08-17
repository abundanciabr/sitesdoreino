# apps/bridge/__init__.py — Lei da Ponte (constituicoes/AGENTS.alunos.md)
# Nenhuma ponte é implementada na Fase 0 — cada uma entra por brief próprio, atrás de
# BRIDGE_<SISTEMA>_ENABLED=0 por padrão. O resto da célula conhece SÓ esta interface;
# nenhum outro arquivo importa nada de dentro de apps/bridge/<sistema>.py diretamente.


def notificar_pontes(matricula) -> None:
    """Ponto único de saída para sistemas externos (formação, comunidade, CRM).

    Falha da ponte NUNCA impede a matrícula local. Sem pontes habilitadas nesta
    fase — stub intencionalmente vazio.
    """
    return None
