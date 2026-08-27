# Uma linha em `request.session` desloga a pessoa do site INTEIRO — quando a célula compartilha o nome do cookie

**Sintoma:** você guarda uma bobagem qualquer na sessão do Django — uma
lembrança de tela, um "já vi este aviso" — e o teste seguinte mostra a pessoa
como **visitante**, com a página quase vazia:

```
assert 'Seu pedido já está com a gente' in '...<a class="botao discreto" href="/">&#8592; Voltar ao site</a>...'
```

Nenhum erro, nenhum log. A requisição anterior funcionou; a próxima é de um
desconhecido. Em produção o efeito é pior que um teste vermelho: **a pessoa
clica num botão de formulário e é deslogada da plataforma toda.**

**Causa:** duas linhas do `config/settings.py`, escritas com bom motivo, que
juntas viram uma armadilha:

```python
SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_NAME = "meshcraft_sessao"   # o MESMO nome que a `identidade` assina
```

O nome compartilhado é deliberado — é o que faz o `sair` de uma célula encerrar
a sessão do site inteiro. Mas com o backend `signed_cookies` a sessão **É** o
cookie: qualquer escrita em `request.session` faz o Django reserializar e
reenviar `meshcraft_sessao` com o conteúdo DESTA célula. O cookie assinado pela
`identidade` é sobrescrito, e ninguém mais reconhece a pessoa.

Vale para qualquer célula que compartilhe o nome do cookie de sessão com quem o
assina — não é específico da `sugestoes`.

**Solução:** nessas células, `request.session` é somente-leitura na prática.
Estado de conveniência da própria célula mora em **cookie próprio**, com nome
próprio:

```python
resposta = render(...)
resposta.set_cookie(
    "caixa_pedido_na_fila", marca,        # nome PRÓPRIO, nunca o da sessão do site
    max_age=..., httponly=True, samesite="Lax",
    secure=settings.SESSION_COOKIE_SECURE,
)
return resposta
```

E se o cookie precisa distinguir pessoas, guarde uma **marca opaca**
(`sha256(SECRET_KEY + email)`), não o e-mail: `signing.dumps` NÃO esconde nada —
é base64 assinado, e o endereço continua legível no navegador.

**O guarda que impede a volta** — mede a resposta, não a intenção:

```python
assert "meshcraft_sessao" not in resposta.cookies, (
    "a resposta reescreveu o cookie de sessão do SITE"
)
```

Um `grep` por `request.session` também serve, mas é frágil: pega o nome, não o
efeito. O teste acima continua valendo se alguém deslogar a pessoa por outro
caminho.

**Como isto foi pego:** implementando o formulário da fila de liberação
(`sugestoes`, 27/08/2026). O teste que caiu não era o do cookie — era um banal
*"recarregar a página não pode mostrar o formulário vazio de novo"*. Só a
segunda leitura do HTML quase vazio explicou o porquê. É o argumento a favor de
testar a JORNADA (pedir → recarregar) e não só o clique: um teste que parasse na
resposta do POST teria ficado verde, e o bug chegaria à produção intacto.

**Quem PODE escrever ali:** só a célula que ASSINA o cookie. Varredura em
27/08/2026 (`grep -rn "request\.session\[" services/*/apps`): a única que
escreve é a `identidade`, que é a dona — e está certa. A `sugestoes` compartilha
o nome e não escreve; a `admin` não tem sessão nenhuma. Se a sua célula aparecer
nessa lista sem ser a dona do cookie, o bug já está em produção.

**Origem:** Fase 1 da fila de liberação, formulário da Caixa
(`docs/decisoes/DECISAO-fila-de-liberacao.md`).
