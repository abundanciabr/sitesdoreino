---
schema_version: 2
armadilha: 204
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir "o teste passa um cabeçalho cookie de propósito" de "o teste apagou o cookie de CSRF sem querer"; o que existe é o próprio teste com `enforce_csrf_checks=True`, que fica vermelho na hora — a defesa é escrever esse teste, não um varredor que leia chamadas de cliente
---

# `headers={"cookie": ...}` no cliente de teste do Django APAGA o cookie de CSRF, e o formulário responde 403

**Sintoma.** Um teste que atravessa o formulário inteiro — pede a página, lê o
token que ela imprimiu, devolve o token no POST — reprova com 403, e o log diz:

```
WARNING django.security.csrf Forbidden (CSRF cookie not set.): /a/duvidas/novo
E       assert 403 == 302
```

O token está no corpo do POST. A página realmente imprimiu
`name="csrfmiddlewaretoken"`. E mesmo assim o Django diz que o **cookie** não
foi enviado.

**Causa.** O cliente de teste monta `HTTP_COOKIE` a partir do pote de cookies
dele (`client.cookies`). Passar `headers={"cookie": "..."}` numa chamada
**substitui esse cabeçalho inteiro** — não acrescenta um cookie ao pote. Todo
cookie que o servidor plantou na resposta anterior (aqui, o `csrftoken` da
célula) desaparece daquela requisição.

O engano é natural em célula que reconhece sessão pelo cookie de OUTRA célula:
como o crachá chega de fora, a forma óbvia de simulá-lo é escrever o cabeçalho
na mão — e ela funciona perfeitamente em todo teste que não envolve formulário.
O `403` só aparece no primeiro teste com `enforce_csrf_checks=True`, que é
justamente o teste que quase ninguém escreve.

**Solução: o crachá vai no POTE, não no cabeçalho.**

```python
navegador = Client(enforce_csrf_checks=True)
navegador.cookies["meshcraft_sessao"] = "um-cookie-opaco-qualquer"

tela = navegador.get(url_da_pagina)            # planta o cookie de CSRF
token = extrair(tela.content)
navegador.post(url_de_escrita, {..., "csrfmiddlewaretoken": token})   # 302
```

O navegador de verdade manda os dois cookies na mesma linha; o teste tem de
fazer igual. Quando não há formulário no caminho, `headers={"cookie": ...}` é
mais legível e continua correto — o que não pode é misturar as duas formas
dentro do mesmo fluxo.

**A regra que fica.** Suíte que só usa o cliente padrão (`enforce_csrf_checks`
desligado, que é o default) **não prova formulário nenhum**: ela prova a
permissão da view e passa por cima da porta de CSRF. Um teste que faz o
percurso inteiro com a conferência ligada é barato e pega, de uma vez, este
erro e a família dele — `CSRF_USE_SESSIONS` ligado numa célula que não assina
sessão, `CSRF_COOKIE_PATH` apontando para fora do prefixo público, template que
esqueceu o `{% csrf_token %}`. Todos falham em produção e só lá.

Achado em 30/08/2026, escrevendo a porta de escrita do fórum (`TAR-019`).
