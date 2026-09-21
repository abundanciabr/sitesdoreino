---
schema_version: 2
armadilha: 505
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - services/alunos/requirements.txt
  - services/identidade/requirements.txt
  - ci/sessao.py
sinal:
  - "dependência local sem identidade imutável"
  - "Use uma versão publicada antes de reutilizar o ambiente"
  - "outbox_relay-[0-9.]+-py3-none-any\\.whl"
guarda:
  tipo: nenhum
  motivo: a recusa e o proprio guarda funcionando; o que falta e ele aceitar wheel versionada dentro da arvore, e isso e conserto na fila, nao teste novo. Documentar evita que o proximo despacho leia a recusa como defeito da celula
licao: "ci/sessao.py recusa abrir bancada com ambiente para alunos e identidade: identidade_do_venv (linha 849, recusa na 871) levanta 'dependencia local sem identidade imutavel' para requisito terminado em .whl sem URL, e as duas celulas vendorizam outbox_relay-0.3.1-py3-none-any.whl POR DESENHO (armadilhas/487). Ate o conserto, abra com --sem-container e saiba que voce esta SEM BASELINE."
---

# 505: a bancada recusa a wheel que a própria casa manda vendorizar

**Data:** 21/09/2026 · **Onde:** `ci/sessao.py`, células `alunos` e `identidade`
· **Custo evitado:** dez dias de bancadas abertas sem baseline, e uma sessão
montando venv, banco e Redis à mão.

## Sintoma

Abrir a bancada dessas duas células com ambiente morre no passo do venv:

```
dependência local sem identidade imutável
Use uma versão publicada antes de reutilizar o ambiente: services/alunos/vendor/outbox_relay-0.3.1-py3-none-any.whl
```

O mesmo acontece em `identidade`. A única saída hoje é `--sem-container`, que
abre a bancada sem venv, sem serviços e, o que importa, **sem baseline medido**:
quem trabalha ali começa sem saber se a célula já estava vermelha.

## Causa

`identidade_do_venv` (`ci/sessao.py` linha 849) monta o hash do ambiente lendo os
requirements. A linha 871 recusa qualquer requisito que termine em `.whl`, `.zip`
ou `.tar.gz` sem `://`, junto com caminhos locais e instalações editáveis. O
motivo do guarda é legítimo: um caminho local qualquer não garante que o hash do
venv mude quando a dependência muda.

Só que essas duas células vendorizam a wheel do pacote compartilhado **por
desenho da casa**, e isso é lei anterior:

```
services/alunos/requirements.txt:10      services/alunos/vendor/outbox_relay-0.3.1-py3-none-any.whl
services/identidade/requirements.txt:20  services/identidade/vendor/outbox_relay-0.3.1-py3-none-any.whl
```

`armadilhas/487` descreve o portão do pacote compartilhado que mantém essas
wheels em dia. A wheel entrou em 08/09/2026; o guarda entrou em 11/09/2026 no
commit `70b6c733` ("ci: reutilizar ambientes e medir a base isoladamente").
Ninguém cruzou os dois, e desde 11/09 as duas células estão sem ambiente.

## Solução

Até o conserto pousar, abra assim, e diga no relatório que o baseline não foi
medido:

```bash
py -3.12 ci/sessao.py --celula alunos --tarefa <slug> --sem-container
```

O conserto certo, e é o que está na fila, é o guarda somar o **conteúdo** da
wheel à identidade do venv, como já faz com o conteúdo dos requirements: o
arquivo está versionado dentro da árvore, então ele tem identidade imutável de
verdade. O que continua recusado é caminho fora da árvore ou arquivo ausente.

**O que NÃO fazer:** tirar a wheel do requirements para a bancada abrir. Isso
quebra o portão do pacote compartilhado e o deploy das duas células.
