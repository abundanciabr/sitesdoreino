"""Explorações do aluno no serviço de quiz, sem cadastro de contato comercial."""

import os

import httpx


class QuizIndisponivel(Exception):
    pass


class QuizRecusado(Exception):
    pass


class QuizDoPortfolio:
    def chamar(self, caminho, *, site_id, aluno_id=None, dados=None):
        base = os.environ.get("QUIZ_PORTFOLIO_API_URL", "").rstrip("/")
        token = os.environ.get("QUIZ_PORTFOLIO_API_TOKEN", "")
        if not base or not token:
            raise QuizIndisponivel(
                "O quiz está indisponível agora. Seus projetos continuam guardados e você pode começar diretamente."
            )
        identidade = {"site_id": site_id}
        if aluno_id:
            identidade["aluno_id"] = aluno_id
        try:
            with httpx.Client(timeout=8) as cliente:
                resposta = cliente.request(
                    "GET" if dados is None else "POST",
                    base + "/" + caminho,
                    headers={"Authorization": "Bearer " + token},
                    params=identidade if dados is None else None,
                    json={**(dados or {}), **identidade} if dados is not None else None,
                )
            if resposta.status_code == 404:
                return None
            if resposta.status_code in (400, 422):
                corpo = resposta.json()
                raise QuizRecusado(
                    corpo.get("erro")
                    or corpo.get("detail")
                    or "Confira as respostas e tente novamente."
                )
            resposta.raise_for_status()
            return resposta.json()
        except (httpx.HTTPError, ValueError) as erro:
            raise QuizIndisponivel(
                "Não foi possível conversar com o quiz agora. O que já foi salvo continua guardado; tente novamente."
            ) from erro


quiz = QuizDoPortfolio()
