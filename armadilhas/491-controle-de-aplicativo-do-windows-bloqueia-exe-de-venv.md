---
schema_version: 2
armadilha: 491
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/ci.py
  - services/*/Makefile
  - ci/sessao.py
sinal:
  - "\\be=4551\\b"
guarda:
  tipo: sino
  dono: ci/sessao.py
  detector: passo de baseline na abertura da sessão
licao: "No Windows com Controle de Aplicativo ativo, chamar o .exe de uma ferramenta dentro do venv (black.exe, pytest.exe) morre com e=4551, mesmo com o pacote instalado. python -m <ferramenta> roda a mesma ferramenta sem passar pelo .exe e funciona. O baseline da abertura de sessao trata esse ERROR como celula quebrada; e ERROR de instrumento desta maquina."
---

# Controle de Aplicativo do Windows bloqueia o `.exe` de dentro do venv

**Data:** 18/09/2026 · **Onde:** `ci/ci.py`, `Makefile`, passo de baseline de `ci/sessao.py` ·
**Custo evitado:** uma célula inteira presumida quebrada, quando só o lint está com o instrumento errado

## Sintoma

Nesta máquina Windows, `make ci` local reprova no passo `lint` com o processo
morrendo com `e=4551`, sem mensagem alguma da ferramenta de lint. O mesmo
acontece com qualquer `.exe` de dentro de um venv (`black.exe`, `pytest.exe`),
não só o de lint.

## Causa

A política de Controle de Aplicativo do Windows (Windows Defender
Application Control / SmartScreen de aplicativo) bloqueia a execução dos
atalhos `.exe` gerados dentro de `Scripts/` do venv, porque não são
binários assinados que a política reconhece. `black.exe` é um desses
atalhos: ele só existe para invocar `python -m black` por baixo, e a
política intercepta antes disso acontecer. Chamar o mesmo pacote pelo
módulo (`python -m black`) não passa por nenhum `.exe` novo, só pelo
interpretador já permitido, e roda normal.

## Solução

Quando `make ci` ou qualquer passo de lint reprovar com `e=4551`, ou um
`.exe` de venv falhar sem produzir mensagem de lint nenhuma, não é o código
da célula: é o instrumento. Rode a ferramenta pelo módulo, nunca pelo
atalho:

```bash
python -m black --check .
python -m pytest
```

O baseline medido pela abertura de sessão (`ci/sessao.py`) hoje registra
esse ERROR como se fosse falha herdada da célula. Quem confiar nesse
baseline sem checar `e=4551` vai sair consertando código que está correto.

## Família: instrumento escolhido pelo ambiente, não pela bancada

Esta é a terceira armadilha da mesma família nesta sessão: o instrumento que
o ambiente escolhe por conveniência (o primeiro do PATH, o atalho `.exe`, o
arquivo já pronto) não é o instrumento que a bancada precisa, e o sintoma
sempre parece defeito de código.

- armadilha 489: `ci/freeze-de-contrato.sh` escolhe o primeiro Python do
  PATH, não o da bancada.
- armadilha 490: um exportador que lê o próprio contrato congelado mede a
  si mesmo em vez de medir o código.
- armadilha 491 (esta): o atalho `.exe` do venv é bloqueado pela política do
  sistema, e o mesmo pacote pelo módulo Python funciona.

## O que NÃO é a causa

Não é o pacote de lint estar ausente ou mal instalado: `python -m black`
prova que ele está lá e funciona. Não é bug em `ci/ci.py`: ele chama o que o
`Makefile` manda chamar, e o `Makefile` chama o `.exe`. O defeito é a
política de segurança desta máquina interceptando um binário não assinado
que sequer precisa existir.
