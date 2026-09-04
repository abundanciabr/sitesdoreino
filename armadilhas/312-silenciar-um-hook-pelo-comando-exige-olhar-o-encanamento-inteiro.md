---
schema_version: 2
armadilha: 312
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_sino_cala_ao_ler_codigo_fonte.py
---

# O sino toca quando você só LÊ o arquivo que imprime a mensagem, e a cura ("ler não é sintoma") só é segura se olhar o encanamento INTEIRO do comando

**Sintoma.** Você dá um `sed -n '200,400p'` num arquivo de teste, ou um `grep`
num script de `ci/`, para conferir um fato. A saída é código-fonte. E o hook
badala como se a falha estivesse acontecendo:

```
$ sed -n '200,400p' ci/tests/test_guarda_declarada_e_sino.py
🔔 SINO DAS ARMADILHAS: a saída deste comando casa com a assinatura da armadilhas/021
   Casou: 'ConfigError: Schema for status 201 is not set'
🔔 SINO DAS ARMADILHAS: … armadilhas/203 … Casou: 'entrada declara detector que a muralha não tem'
```

Aconteceu duas vezes na sessão que escreveu este conserto, lendo o próprio
código do sino. Medido em 04/09/2026: **43 das 81 armadilhas com sinal casavam
texto benigno do repositório, em 205 arquivos versionados**, e um `cat` em
qualquer um deles tocava (205 de 205).

**Causa.** Assinatura baseada em MENSAGEM aparece, por construção, no arquivo que
imprime a mensagem, e em teste, registro do livro, workflow e documento que a
citam. Estreitar o sinal não cura (a TAR-043 mediu que leva à cegueira): o que
distingue não é o TEXTO da saída, é o CONTEXTO em que ela foi produzida. O sino
já sabia disso para `armadilhas/` (`LENDO_O_CATALOGO`) e para mais nada.

**Solução, e as três arestas que cortam.** `e_so_leitura()` em
`ci/sino_das_armadilhas.py` cala o sino quando o comando é só leitura. As regras
que fizeram a diferença entre cura e tiro no pé:

1. **Olhe TODOS os segmentos, não o primeiro.** `python x.py | grep FAIL`,
   `cat x && python x`, `echo "$(make ci)"`, `` cat `python x` `` e `find -exec`
   têm um leitor no começo e um executor no meio. A saída é de uma falha REAL
   que passou por um filtro. A régua é "todo segmento é leitor" (separadores:
   `|`, `&&`, `||`, `;`, quebra de linha, `$(`, crase), e um comando que não
   está na lista de leitores NÃO é leitor (fail-noisy). A mutação "basta o
   primeiro segmento" derrubou 8 testes.
2. **Corpo de heredoc é texto; a LINHA DE ABERTURA é comando.** A primeira
   versão do regex apagava a linha inteira do `<<'EOF'` e engolia o `| python -`
   que vinha depois dela: `cat <<'EOF' | python -` passou a "só leitura". Guarde
   a linha, tire só o corpo.
3. **Artefato de saída não é código-fonte.** `cat deploy.log`, a pasta `tasks/`
   do harness (a saída de um comando em segundo plano, onde o PostToolUse pode
   não ter passado), `/tmp`, scratchpad: ler isso é o momento em que o sino mais
   serve. Uma lista curta de padrões mantém o sino acordado aí.

O que ficou de fora, dito: o arquivo lido não é conferido contra `git ls-files`
(o hook roda do espelho e tem 20 s). Ler um `.txt` solto com `cat` também cala,
e isso é barulho a menos, não cegueira: a saída de um `cat` nunca é o evento de
uma falha.

**E o aviso que engana quem testa o conserto:** o hook da SUA sessão roda de
`${CLAUDE_PROJECT_DIR}`, o clone principal, com o sino de lá. Você conserta na
bancada, roda o teste (verde), dá um `grep` para conferir, e o sino toca de
novo. Não é o conserto que falhou: é o espelho velho (`armadilhas/148`, TAR-050).
A prova é o teste na bancada, não o silêncio da sua janela.

**Origem.** TAR-048, 04/09/2026 (lote `ci` de 03/09), medida da TAR-043
(30/08/2026). Guarda: `ci/tests/test_sino_cala_ao_ler_codigo_fonte.py`, com a
varredura do repositório real (`test_nenhum_arquivo_versionado_toca_ao_ser_lido`).
