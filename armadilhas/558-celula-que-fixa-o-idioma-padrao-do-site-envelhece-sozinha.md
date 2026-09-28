---
schema_version: 2
armadilha: 558
estado: guardada
degrau: 1
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: services/identidade/tests/test_login_por_senha.py
sinal:
  - 'IDIOMA_PADRAO\s*=\s*"'
gatilho:
  - services/identidade/apps/core/views.py
  - services/funil/apps/i18n/idiomas.py
licao: "Só o funil sabe o idioma padrão do site, e o padrão mora na raiz sem prefixo. Outra célula que monta URL do site deriva o prefixo do caminho recebido: primeiro segmento com forma de idioma repete-se; sem ele, a URL fica na raiz. Nunca fixe idioma padrão em constante fora do funil: a identidade fixou pt-br e toda recusa de login caiu em /pt-br/login, 404, por um mês."
---

# 558: célula que fixa o idioma padrão do site envelhece sozinha quando o padrão muda

**Data:** 28/09/2026 · **Onde:** `services/identidade/apps/core/views.py::_recusar` ·
**Custo evitado:** um mês de "Not Found" em toda recusa de login do meshcraft
(senha errada, token vencido, volta do Google com problema), sem nenhum teste
vermelho e sem alarme, descoberto pelo mantenedor ao errar a própria senha.

## Sintoma

```
POST /entrar/senha (token fresco, senha errada)
302 -> https://meshcraft.top/pt-br/login?erro=senha-invalida
GET  /pt-br/login?erro=senha-invalida -> 404
```

A pessoa que erra a senha vê a página de "Not Found" com a referência do erro,
e nunca lê "E-mail ou senha incorretos". O mesmo para `nao-confere` e
`email-nao-verificado`.

## Causa

A célula `identidade` montava a URL da tela de login com
`f"/{idioma}/login"` e tinha uma constante própria com o idioma padrão, `pt-br`,
para destino sem prefixo. Era uma cópia da regra de prefixo do `funil`, e a cópia foi escrita
quando todo idioma levava prefixo. Em 25/08/2026 o padrão passou a morar na
raiz; em 27/08/2026 o padrão do meshcraft virou `pt-br`, e `/pt-br/*` deixou
de existir. O `funil` se regenerou sozinho porque toda URL dele sai de
`caminho_publico()`; a cópia na `identidade` não tinha como saber, e a suíte
dela concordava com a própria cópia (`/pt-br/login?erro=...` nos asserts).

## Solução

A tela de login fica ao lado do destino pedido: `_prefixo_de_idioma(destino)`
devolve `/es` para `/es/cadastro` e vazio para `/cadastro` ou `/`; a URL vira
`{prefixo}/login?erro=...`. A constante de idioma padrão foi removida. Os
testes passaram a esperar `/login?erro=...` para destino na raiz
(`test_recusa_na_raiz_volta_para_login_sem_prefixo_de_idioma`, e os asserts
de `nao-confere` e `email-nao-verificado`).

Regra para a próxima célula: não copie a regra de idioma; derive o prefixo
do caminho que você já recebeu, e teste o caso da raiz.

## Origem

TAR-941, sessão do mantenedor em 28/09/2026. Relacionada à armadilha 098
(tirar o prefixo do padrão torna o primeiro segmento ambíguo).
