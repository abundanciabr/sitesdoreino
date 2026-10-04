"""Inventory of the existing cells inside the unified Django process."""

from pathlib import Path

SERVICES = (
    "admin", "alunos", "catalogo", "checkout", "cursos", "encomendas",
    "forum", "funil", "gamificacao", "identidade", "leads", "mensageria",
    "metricas", "notificacoes", "pagamentos", "pages", "quiz", "sugestoes",
)

# The public prefixes are deliberately distinct from the old internal paths.
# A cell behind SCRIPT_NAME used a local URLconf; identidade and payments did not.
PUBLIC_PREFIXES = (
    ("/webhooks/whatsapp", "mensageria", ""),
    # Respostas de e-mail recebidas pelo provedor (inbound), com token próprio.
    ("/webhooks/email/recebido", "mensageria", ""),
    ("/static/checkout", "checkout", ""),
    ("/api/pagamentos", "pagamentos", ""),
    ("/api/checkout", "checkout", ""),
    ("/forms/sugestoes", "sugestoes", "/forms/sugestoes"),
    ("/conquistas", "gamificacao", "/conquistas"),
    ("/encomendas", "encomendas", "/encomendas"),
    ("/checkout", "checkout", "/checkout"),
    ("/entrar", "identidade", ""),
    ("/estudio", "pages", ""),
    ("/alunos", "alunos", "/alunos"),
    ("/cursos", "cursos", "/cursos"),
    ("/forum", "forum", "/forum"),
    ("/portfolio", "pages", "/portfolio"),
    ("/pages", "pages", "/pages"),
    ("/admin", "admin", "/admin"),
    ("/docs", "admin", "/admin"),
    ("/midia", "admin", "/admin"),
    ("/quiz", "quiz", "/quiz"),
)


def app_configs(modules_root: Path) -> list[str]:
    result = []
    for service in SERVICES:
        if service == "pagamentos":
            roots = [modules_root / service / "pagamentos"]
        else:
            roots = [modules_root / service / "apps"]
        for root in roots:
            if not root.is_dir():
                raise FileNotFoundError(f"módulos da aplicação ausentes: {root}")
            for child in sorted(root.iterdir()):
                if (child / "unified_config.py").is_file():
                    if service == "pagamentos":
                        result.append(f"modules.{service}.pagamentos.{child.name}.unified_config.UnifiedConfig")
                    else:
                        result.append(f"modules.{service}.apps.{child.name}.unified_config.UnifiedConfig")
    return result


_HOST_LOCKED = frozenset({
    "admin", "forum", "gamificacao", "cursos", "pages", "encomendas", "identidade",
})


def service_for_path(
    path: str, host: str = "meshcraft.top", private: bool = False
) -> tuple[str, str]:
    host = host.split(":", 1)[0].lower()
    if private and (path == "/api/catalogo" or path.startswith("/api/catalogo/")):
        return "catalogo", ""
    for prefix, service, script_name in PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            if service in _HOST_LOCKED and host != "meshcraft.top":
                continue
            if service == "pagamentos":
                if path.startswith("/api/pagamentos/webhooks") or path.rstrip("/") in (
                    "/api/pagamentos/mp/webhooks",
                    "/api/pagamentos/mercadopago/webhooks",
                ):
                    if host != "meshcraft.top":
                        continue
                elif not (path.startswith("/api/pagamentos/appmax") and host == "meshcraft.top"):
                    continue
            return service, script_name
    return "funil", ""


def service_for_app_label(label: str) -> str | None:
    service = label.split("_", 1)[0]
    return service if service in SERVICES else None


class ServiceDatabaseRouter:
    def db_for_read(self, model, **hints):
        return service_for_app_label(model._meta.app_label)

    def db_for_write(self, model, **hints):
        return service_for_app_label(model._meta.app_label)

    def allow_relation(self, obj1, obj2, **hints):
        first = service_for_app_label(obj1._meta.app_label)
        second = service_for_app_label(obj2._meta.app_label)
        return first == second if first and second else None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        service = service_for_app_label(app_label)
        if service:
            return db == service
        # Django's contenttypes table has historically existed per cell.
        if app_label == "contenttypes":
            return db in SERVICES
        return False
