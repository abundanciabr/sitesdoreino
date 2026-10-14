from django.conf import settings
from django.core import signing
from django.contrib.sessions.backends.signed_cookies import SessionStore as Assinada
from .acesso_escola import PRAZO_SESSAO

class SessionStore(Assinada):
    def load(self):
        try:
            dados = signing.loads(self.session_key, serializer=self.serializer,
                max_age=PRAZO_SESSAO, salt="django.contrib.sessions.backends.signed_cookies")
            if not dados.get("acesso_escola_persistente"):
                dados = signing.loads(self.session_key, serializer=self.serializer,
                    max_age=settings.SESSION_COOKIE_AGE, salt="django.contrib.sessions.backends.signed_cookies")
            return dados
        except (signing.BadSignature, ValueError, TypeError):
            self.create()
            return {}
