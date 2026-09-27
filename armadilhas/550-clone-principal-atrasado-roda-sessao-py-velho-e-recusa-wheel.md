---
schema_version: 2
armadilha: 550
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/sessao.py
guarda:
  tipo: nenhum
  motivo: "o gancho de abertura roda o ci/sessao.py que ja esta no disco daquela arvore; ensinar o proprio script atrasado a se atualizar sozinho antes de rodar exigiria reescrever o bootstrap para buscar a versao da main antes de decidir qualquer coisa, mudanca de codigo fora do alcance de uma entrada de licao"
licao: "python ci/sessao.py roda o arquivo QUE JA ESTA na arvore chamada, nao uma versao da main. O clone principal, 1413 entregas atrasado e com mudancas nao commitadas de outra sessao, tem ci/sessao.py velho que recusa a wheel por 'dependencia local sem identidade imutavel', mesmo com sha256 ja anotado na main. Abra a bancada a partir do ci/sessao.py de um worktree ja atualizado."
---

# 550: o clone principal atrasado roda o `ci/sessao.py` velho e recusa a wheel já resolvida na main

**Data:** 27/09/2026 · **Onde:** `ci/sessao.py`, clone principal, tarefa 837,
obra Appmax · **Custo evitado:** abertura de bancada em pagamentos/checkout
recusada por um motivo já corrigido, achando que a wheel em si está sem
identidade quando o problema é o script de abertura estar desatualizado.

## Sintoma

Abrir a bancada a partir do clone principal (`ci/sessao.py --celula
pagamentos ...` ou `--celula checkout ...`) recusa com

```
dependência local sem identidade imutável
```

mesmo o `sha256` da wheel em questão já estando anotado na `main` (o mesmo
fato que `armadilhas/248`/vizinhas exigem, já satisfeito).

## Causa

`python ci/sessao.py ...` executa o arquivo `ci/sessao.py` **que já está no
disco daquela árvore de trabalho**, não uma cópia buscada da `main` no
momento da chamada. O clone principal (`C:/Users/davia/abundanciabr/
sitesdoreino-limpo-20260923`) estava 1413 entregas atrás de `origin/main` e
carregava, além disso, mudanças não commitadas deixadas por outra sessão. O
gancho de atualização automática (que normalmente traria o script em dia)
não avança sobre uma árvore com mudanças locais não commitadas — por
desenho, ele nunca descarta trabalho alheio sem avisar — então o clone
principal continuou executando a versão antiga de `ci/sessao.py`, de antes
do conserto que passou a aceitar a wheel pelo `sha256` já anotado.

## Solução

Nunca abra bancada nova a partir de um clone que você sabe (ou suspeita)
estar muito atrasado. Rode a abertura a partir do `ci/sessao.py` de uma
bancada (worktree) já atualizada, referenciando o binário por caminho
absoluto:

```bash
python C:/Users/davia/abundanciabr/wt-<bancada-em-dia>/ci/sessao.py \
  --celula <celula> --tarefa <slug>
```

O worktree criado por essa chamada nasce a partir da `main` atual, então a
recusa por identidade imutável desaparece assim que o script que decide é o
script em dia, não o do clone principal parado.

## Origem

Tarefa 837, obra Appmax, sessão de coordenação de 27/09/2026; clone
principal `sitesdoreino-limpo-20260923`; `ci/sessao.py`.
