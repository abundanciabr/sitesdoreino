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

    def test_galeria_publica_na_raiz_preserva_painel_admin(self):
        import httpx
        from unittest.mock import patch
        from config.registry import service_for_path
        from modules.admin.apps.core.galeria_comunidade import IMAGENS
        self.assertEqual(service_for_path('/comunidade'), ('admin', ''))
        self.assertEqual(service_for_path('/comunidade', 'outro.exemplo'), ('funil', ''))
        linhas = [{'slug':slug,'titulo':titulo,'descricao':descricao,'votos':0,'votado':False,'url':'/comunidade/imagens/'+slug} for slug,titulo,descricao in IMAGENS]
        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=type(self).application), base_url='https://meshcraft.top') as client:
                with patch('modules.admin.apps.core.galeria_comunidade.classificacao', return_value=linhas):
                    resposta = await client.get('/comunidade')
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.text.count('class="modelo"'), 9)
                self.assertIn('Path=/comunidade', resposta.headers['set-cookie'])
                self.assertEqual((await client.get('/comunidade/galeria.js')).status_code, 200)
                self.assertEqual((await client.get('/admin/comunidade/')).status_code, 302)
                self.assertEqual((await client.get('/admin/comunidade/votacao/')).status_code, 302)
        asyncio.run(check())

    def test_previa_aula1_tem_endereco_do_curso_e_preserva_galeria_comunidade(self):
        import httpx
        from unittest.mock import patch
        from config.registry import service_for_path
        from modules.admin.apps.core.galeria_aula1 import BASE, IMAGENS

        self.assertEqual(service_for_path(BASE), ("admin", ""))
        self.assertEqual(service_for_path(BASE, "outro.exemplo"), ("funil", ""))
        linhas = [{"slug": slug, "titulo": titulo, "descricao": descricao, "votos": 0,
                   "votado": False, "url": BASE + "/imagens/" + slug}
                  for slug, titulo, descricao in IMAGENS]

        async def check():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=type(self).application),
                                         base_url="https://meshcraft.top") as client:
                with patch("modules.admin.apps.core.galeria_comunidade.classificacao", return_value=linhas):
                    resposta = await client.get(BASE)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta.text.count('class="modelo"'), 6)
                self.assertIn("Path=" + BASE, resposta.headers["set-cookie"])
                self.assertEqual((await client.get(BASE + "/galeria.js")).status_code, 200)
                self.assertEqual((await client.get(BASE + "/galeria.css")).status_code, 200)
                self.assertEqual((await client.get(BASE + "/voto")).status_code, 405)
                self.assertNotEqual((await client.get("/comunidade/aula-1")).status_code, 200)
                self.assertEqual((await client.get("/cursos/healthz")).status_code, 200)
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

    def test_webhooks_mp_unificados_chegam_ao_receptor_sem_consultar_gateway(self):
        import httpx

        async def check():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=type(self).application),
                base_url="https://meshcraft.top",
            ) as client:
                for rota in ("mp", "mercadopago"):
                    caminho = f"/api/pagamentos/{rota}/webhooks"
                    response = await client.get(caminho)
                    self.assertEqual(response.status_code, 405)
                    response = await client.post(
                        caminho + "?data.id=prova-sem-assinatura",
                        json={"type": "payment", "data": {"id": "prova-sem-assinatura"}},
                    )
                    self.assertEqual(response.status_code, 403)
        asyncio.run(check())

    def test_paginas_de_erro_compartilhadas_sao_achadas_em_toda_celula(self):
        """Sem elas, o endereço que não existe virava 500 em vez de 404 (02/10/2026)."""
        from django.template.loader import get_template
        from config.registry import SERVICES
        from config.runtime import serving

        for service in SERVICES:
            with serving(service):
                for status in (404, 500):
                    self.assertIn("site_errors", get_template(f"site_errors/{status}.html").origin.name)
        self.assertIn("site_errors", get_template("site_errors/404.html").origin.name)

    def test_model_checks_keep_real_database_collisions(self):
        from types import SimpleNamespace

        from django.core.checks import Tags, run_checks
        from django.db.models import UniqueConstraint

        from config.checks import check_models_by_database

        actual = run_checks(tags=[Tags.models])
        self.assertFalse(any(item.id in {"models.E032", "models.W035"} for item in actual), actual)

        from config.comando import main as comando
        comando(["admin", "check"])
        comando(["gamificacao", "check"])

        def model(label):
            meta = SimpleNamespace(
                managed=True, proxy=False, db_table="evento",
                label=label, indexes=[],
                constraints=[UniqueConstraint(fields=["pessoa"], name="um_perfil")],
            )

            class CheckedModel:
                _meta = meta

                @classmethod
                def check(cls, **kwargs):
                    return []

            return CheckedModel

        def app(label, checked_model):
            return SimpleNamespace(label=label, get_models=lambda: [checked_model])

        encomendas = app("encomendas_perfis", model("encomendas_perfis.Perfil"))
        gamificacao = app("gamificacao_perfis", model("gamificacao_perfis.Perfil"))
        same_database = app("encomendas_outros", model("encomendas_outros.Perfil"))

        separated = check_models_by_database([encomendas, gamificacao])
        self.assertFalse(any(item.id in {"models.E032", "models.W035"} for item in separated))
        collided = check_models_by_database([encomendas, same_database])
        self.assertIn("models.E032", {item.id for item in collided})
        self.assertIn("models.W035", {item.id for item in collided})

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

    def test_internal_request_preserves_caller_transaction(self):
        import httpx
        from django.db import connections, transaction
        from config.runtime import serving
        from internal import instalar

        instalar()
        committed = []
        with serving("admin"):
            db = connections["admin"]
            with transaction.atomic():
                with db.cursor() as cursor:
                    cursor.execute("SELECT 1")
                transaction.on_commit(lambda: committed.append(True))
                with httpx.Client(trust_env=False) as client:
                    response = client.get("http://catalogo:8000/healthz")
                self.assertEqual(response.status_code, 200)
                self.assertFalse(db.closed_in_transaction)
                with db.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    self.assertEqual(cursor.fetchone(), (1,))
            self.assertEqual(committed, [True])

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
