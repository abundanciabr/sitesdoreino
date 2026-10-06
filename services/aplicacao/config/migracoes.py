"""Adopt each database's existing migrations under its new app label.

The old rows remain for a recoverable rollback to the former containers.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def adotar_historico(connection, mappings):
    """Copy completed migration names in one database without changing old rows."""
    count = 0
    with connection.cursor() as cursor:
        for old_label, new_label in mappings:
            cursor.execute(
                """INSERT INTO django_migrations (app, name, applied)
                   SELECT %s, old.name, old.applied
                   FROM django_migrations AS old
                   WHERE old.app = %s
                     AND NOT EXISTS (
                       SELECT 1 FROM django_migrations AS new
                       WHERE new.app = %s AND new.name = old.name
                     )""",
                [new_label, old_label, new_label],
            )
            count += cursor.rowcount
    return count


def adotar_contenttypes_permissoes(connection, mappings):
    """Keep old identities for rollback and mirror them under new app labels."""
    tables = set(connection.introspection.table_names())
    if "django_content_type" not in tables:
        return 0, 0
    contenttypes = permissions = 0
    with connection.cursor() as cursor:
        for old_label, new_label in mappings:
            cursor.execute(
                """INSERT INTO django_content_type (app_label, model)
                   SELECT %s, old.model
                   FROM django_content_type AS old
                   WHERE old.app_label = %s
                     AND NOT EXISTS (
                       SELECT 1 FROM django_content_type AS new
                       WHERE new.app_label = %s AND new.model = old.model
                     )""",
                [new_label, old_label, new_label],
            )
            contenttypes += cursor.rowcount
            if "auth_permission" not in tables:
                continue
            cursor.execute(
                """INSERT INTO auth_permission (name, content_type_id, codename)
                   SELECT old_permission.name, new_type.id, old_permission.codename
                   FROM auth_permission AS old_permission
                   JOIN django_content_type AS old_type
                     ON old_type.id = old_permission.content_type_id
                   JOIN django_content_type AS new_type
                     ON new_type.app_label = %s AND new_type.model = old_type.model
                   WHERE old_type.app_label = %s
                     AND NOT EXISTS (
                       SELECT 1 FROM auth_permission AS new_permission
                       WHERE new_permission.content_type_id = new_type.id
                         AND new_permission.codename = old_permission.codename
                     )""",
                [new_label, old_label],
            )
            permissions += cursor.rowcount
    return contenttypes, permissions


def preparar_migracoes():
    import django
    from django.apps import apps
    from django.db import connections, transaction
    from .registry import ACTIVE_SERVICES as SERVICES

    django.setup()
    adopted = {}
    for service in SERVICES:
        if service == "funil":
            continue
        connection = connections[service]
        if "django_migrations" not in connection.introspection.table_names():
            adopted[service] = 0
            continue
        prefix = service + "_"
        mappings = [
            (app.label[len(prefix):], app.label)
            for app in apps.get_app_configs()
            if app.label.startswith(prefix)
        ]
        with transaction.atomic(using=service):
            migrations = adotar_historico(connection, mappings)
            contenttypes, permissions = adotar_contenttypes_permissoes(connection, mappings)
            adopted[service] = {
                "migrations": migrations,
                "contenttypes": contenttypes,
                "permissions": permissions,
            }
    return adopted


if __name__ == "__main__":
    for service, counts in preparar_migracoes().items():
        print(f"{service}: {counts}")
