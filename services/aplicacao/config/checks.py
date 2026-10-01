"""Run Django's complete model checks within each actual database boundary."""

from collections import defaultdict

from django.apps import apps
from django.core.checks import Tags
from django.core.checks.model_checks import check_all_models
from django.core.checks.registry import registry

from .registry import service_for_app_label
from .runtime import serving


def check_models_by_database(app_configs=None, **kwargs):
    groups = defaultdict(list)
    for app_config in app_configs if app_configs is not None else apps.get_app_configs():
        service = service_for_app_label(app_config.label)
        groups[service or "default"].append(app_config)

    errors = []
    for database, configs in groups.items():
        if database == "default":
            errors.extend(check_all_models(app_configs=configs, **kwargs))
        else:
            with serving(database):
                errors.extend(check_all_models(app_configs=configs, **kwargs))
    return errors


check_models_by_database.tags = (Tags.models,)


def install_database_aware_model_checks():
    # Django groups table, index, and constraint names across the entire app
    # registry. They only have to be unique within a single database.
    registry.registered_checks.discard(check_all_models)
    registry.registered_checks.add(check_models_by_database)
