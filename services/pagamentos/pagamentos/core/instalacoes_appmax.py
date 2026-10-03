"""Associa a identidade dos avisos Appmax à instalação local."""

from django.conf import settings

from pagamentos.core.models import InstalacaoAppmax


def instalacao_do_webhook(app_uuid: str) -> InstalacaoAppmax | None:
    configuracoes = settings.APPMAX_INSTALACOES
    com_uuid = {
        app_id: dados.get("app_uuid", "")
        for app_id, dados in configuracoes.items()
        if dados.get("app_uuid")
    }
    if com_uuid:
        correspondencias = [
            app_id for app_id, uuid_configurado in com_uuid.items()
            if uuid_configurado == app_uuid
        ]
        if len(correspondencias) != 1:
            return None
        return InstalacaoAppmax.objects.filter(app_id=correspondencias[0]).first()
    # Instalações anteriores à inclusão de app_uuid continuam recebendo o ID
    # numérico até a configuração da Appmax ser atualizada.
    return InstalacaoAppmax.objects.filter(app_id=app_uuid).first()


def instalacao_do_inbox(app_id: str) -> InstalacaoAppmax | None:
    configuracoes = settings.APPMAX_INSTALACOES
    if any(dados.get("app_uuid") for dados in configuracoes.values()):
        if not configuracoes.get(app_id, {}).get("app_uuid"):
            return None
    return InstalacaoAppmax.objects.filter(app_id=app_id).first()
