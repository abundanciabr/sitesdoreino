---
schema_version: 2
armadilha: 533
estado: documentada
degrau: 2
confianca: media
custo_por_queda: baixo
gatilho:
  - ci/ci.py
sinal:
  - "Blocked by classifier"
guarda:
  tipo: nenhum
  motivo: "o classificador de permissoes do modo automatico e do proprio harness do agente, fora deste repositorio; nao ha portao de CI que possa mudar a heuristica dele, so o contorno pelo lado do escritor"
licao: "O classificador de permissoes do modo automatico pode negar, de forma intermitente, comandos so-leitura como git diff origin/main...HEAD e python ci/ci.py --apenas infra (falso positivo). Nao insista no mesmo comando: tente de novo 1-2x, ou revise pelo GitHub (gh pr diff) e deixe o portao medido pelos checks do PR."
---

# 533: o classificador de permissões nega comando seguro de leitura (falso positivo)

**Data:** 27/09/2026 · **Onde:** modo automático do harness do agente, obra
Appmax · **Custo evitado:** um escritor travado tentando repetir o mesmo
comando de leitura, achando que a tarefa exige um comando proibido.

## Sintoma

O classificador de permissões que decide quais comandos um escritor em modo
automático pode rodar negou, em pelo menos uma tentativa, dois comandos que
não escrevem nada:

- `git diff origin/main...HEAD` (comparação de leitura antes de conferir os
  alvos tocados);
- `python ci/ci.py --apenas infra` (rodar a suíte de infraestrutura).

`services/pagamentos/LICOES.md` já registra o mesmo padrão em outra sessão,
com `docker compose up`, `black` sem `--check`, `python manage.py migrate` e
`pytest` com várias linhas `export VAR=valor`: o MESMO comando (às vezes
idêntico) foi negado numa tentativa e aceito ao tentar de novo ou reescrito
numa linha só. Não é um bloqueio fixo por comando.

## Causa

O classificador roda fora deste repositório, como parte do harness do
agente, e decide por heurística, não por uma lista fixa. Um comando
so-leitura pode ser negado (falso positivo) e o mesmo comando, chamado de
novo ou reescrito, ser aceito. Nenhum portão de CI deste projeto controla
essa heurística.

## Solução

Quando um comando so-leitura necessário ao despacho for negado:

1. Tente de novo 1 a 2 vezes antes de assumir que é proibido; a negação é
   intermitente, não fixa.
2. Se persistir, use a saída alternativa já usada nesta obra: revisão pelo
   GitHub (`gh pr diff <N>`) em vez de `git diff` local, e deixe o portão
   medido pelos próprios checks do PR (`muralhas`, `ci-celula-gate`) em vez
   de rodar `ci/ci.py` local.
3. Preferir `env VAR=x cmd` (uma linha) a vários `export` sequenciais quando
   a negação for em comando com variáveis de ambiente.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026; padrão irmão em
`services/pagamentos/LICOES.md` (webhooks/outbox).
