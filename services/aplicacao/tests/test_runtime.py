"""Single-process smoke proof with synthetic configuration only."""

import asyncio
import os
import tempfile
import unittest
from pathlib import Path


class RuntimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from config.registry import SERVICES

        root = Path(__file__).resolve().parents[1]
        if not (root / "modules" / "forum" / "config" / "settings.py").is_file():
            raise RuntimeError("execute preparar.py antes desta prova")
        cls.env_dir = tempfile.TemporaryDirectory()
        cls.old_env_dir = os.environ.get("APLICACAO_ENV_DIR")
        os.environ["APLICACAO_ENV_DIR"] = cls.env_dir.name
        scripts = {
            "admin": "/admin", "alunos": "/alunos", "checkout": "/checkout",
            "cursos": "/cursos", "encomendas": "/encomendas", "forum": "/forum",
            "gamificacao": "/conquistas", "pages": "/pages", "quiz": "/quiz",
            "sugestoes": "/forms/sugestoes",
        }
        for service in SERVICES:
            lines = [f"DJANGO_SECRET_KEY=synthetic-{service}", "DEBUG=1",
                     f"SCRIPT_NAME={scripts.get(service, '')}"]
            if service != "funil":
                lines.append("DATABASE_URL=sqlite:///:memory:")
            if service == "pagamentos":
                lines += ["MP_ACCESS_TOKEN=TEST-synthetic", "MP_WEBHOOK_SECRET=synthetic"]
            (Path(cls.env_dir.name) / f"{service}.env").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )
        from config.asgi import application, app_do_servico
        cls.application = application
        cls.app_do_servico = staticmethod(app_do_servico)

    @classmethod
    def tearDownClass(cls):
        if cls.old_env_dir is None:
            os.environ.pop("APLICACAO_ENV_DIR", None)
        else:
            os.environ["APLICACAO_ENV_DIR"] = cls.old_env_dir
        cls.env_dir.cleanup()

    def test_all_handlers_and_urlconfs(self):
        import httpx
        from django.urls import get_resolver
        from config.registry import SERVICES
        from config.runtime import serving

        async def check():
            for service in SERVICES:
                with serving(service):
                    self.assertTrue(get_resolver(f"modules.{service}.config.urls").url_patterns)
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=self.app_do_servico(service)),
                    base_url="https://meshcraft.top",
                ) as client:
                    response = await client.get("/healthz")
                self.assertEqual(response.status_code, 200, service)
        asyncio.run(check())

    def test_host_private_settings_templates_and_transaction(self):
        from django.conf import settings
        from django.db import connection, connections, transaction
        from django.template import TemplateDoesNotExist
        from django.template.loader import get_template
        from config.registry import service_for_path
        from config.runtime import serving

        self.assertEqual(service_for_path("/admin/healthz", "outro.exemplo"), ("funil", ""))
        self.assertEqual(service_for_path("/api/catalogo/produtos"), ("funil", ""))
        self.assertEqual(service_for_path("/api/catalogo/produtos", private=True), ("catalogo", ""))
        with serving("identidade"):
            self.assertEqual(settings.SECRET_KEY, "synthetic-identidade")
        with serving("admin"):
            self.assertEqual(settings.SECRET_KEY, "synthetic-admin")
            with self.assertRaises(TemplateDoesNotExist):
                get_template("base_mobile.html")
        with serving("funil"):
            self.assertIn("funil", get_template("base_mobile.html").origin.name)
        with serving("forum"):
            self.assertEqual(connection.alias, "forum")
            called = []
            with transaction.atomic():
                self.assertTrue(connections["forum"].in_atomic_block)
                transaction.on_commit(lambda: called.append(True))
                self.assertFalse(called)
            self.assertEqual(called, [True])

    def test_home_translation_uses_funil_catalog_and_base_dir(self):
        from django.conf import settings
        from django.template import Context, Template
        from django.template.loader import get_template
        from django.test import RequestFactory
        from config.runtime import serving
        from modules.funil.apps.i18n.catalogo import catalogo_instalado
        from modules.funil.apps.core.rodape import montar

        with serving("funil"):
            self.assertEqual(Path(settings.BASE_DIR),
                             Path(__file__).resolve().parents[1] / "modules" / "funil")
            self.assertIn("landing.titulo", catalogo_instalado())
            request = RequestFactory().get("/")
            request.idioma = "pt-br"
            rendered = Template('{% load t %}{% t "landing.titulo" %}').render(
                Context({"request": request})
            )
            self.assertEqual(rendered, "Meshcraft")
            home = get_template("funil/landing_i18n.html").render({
                "request": request, "rodape": montar("completo", ano=2026),
            })
            self.assertIn("Meshcraft", home)
            self.assertNotIn("landing.titulo", home)
            self.assertNotIn("rodape.link_inicio", home)
            self.assertIn('href="/"', home)
            self.assertIn('href="/cadastro"', home)

    def test_internal_asgi_restores_outer_url_state(self):
        import httpx
        from django.urls import (
            get_script_prefix, get_urlconf, set_script_prefix, set_urlconf,
        )

        async def check():
            before_prefix, before_urlconf = get_script_prefix(), get_urlconf()
            try:
                set_script_prefix("/funil/")
                set_urlconf("modules.funil.config.urls")
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app=self.app_do_servico("gamificacao")),
                    base_url="http://gamificacao:8000",
                ) as client:
                    response = await client.get("/healthz")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(get_script_prefix(), "/funil/")
                self.assertEqual(get_urlconf(), "modules.funil.config.urls")
            finally:
                set_script_prefix(before_prefix)
                set_urlconf(before_urlconf)

        asyncio.run(check())

    def test_migration_contenttype_and_permission_copy(self):
        from django.db import connections
        from config.migracoes import adotar_contenttypes_permissoes, adotar_historico

        db = connections["forum"]
        with db.cursor() as cur:
            cur.execute("CREATE TABLE django_migrations (id INTEGER PRIMARY KEY, app TEXT, name TEXT, applied TEXT)")
            cur.execute("CREATE TABLE django_content_type (id INTEGER PRIMARY KEY, app_label TEXT, model TEXT, UNIQUE(app_label,model))")
            cur.execute("CREATE TABLE auth_permission (id INTEGER PRIMARY KEY, name TEXT, content_type_id INTEGER, codename TEXT, UNIQUE(content_type_id,codename))")
            cur.execute("INSERT INTO django_migrations (app,name,applied) VALUES ('core','0001_initial','2026-01-01')")
            cur.execute("INSERT INTO django_content_type (app_label,model) VALUES ('core','documento')")
            cur.execute("INSERT INTO auth_permission (name,content_type_id,codename) VALUES ('Can view',1,'view_documento')")
        mapping = [("core", "forum_core")]
        self.assertEqual(adotar_historico(db, mapping), 1)
        self.assertEqual(adotar_contenttypes_permissoes(db, mapping), (1, 1))
        self.assertEqual(adotar_historico(db, mapping), 0)
        self.assertEqual(adotar_contenttypes_permissoes(db, mapping), (0, 0))
        with db.cursor() as cur:
            for table, column, expected in (
                ("django_migrations", "app", ["core", "forum_core"]),
                ("django_content_type", "app_label", ["core", "forum_core"]),
                ("auth_permission", "content_type_id", [1, 2]),
            ):
                cur.execute(f"SELECT {column} FROM {table} ORDER BY id")
                self.assertEqual([row[0] for row in cur.fetchall()], expected)


if __name__ == "__main__":
    unittest.main()
