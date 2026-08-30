---
schema_version: 2
armadilha: 196
estado: observada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a pasta de rascunho é do harness, não do repositório — nenhum portão deste projeto a enxerga, e um teste que exigisse nome único num diretório fora do Git não teria o que medir num PR; a defesa é de disciplina (nome único por sessão) até alguém achar um mecanismo do lado do harness
---

# O arquivo de rascunho do agente é COMPARTILHADO entre sessões irmãs — e o `--body-file` publica o texto de outra

**Sintoma.** Você escreve o corpo do seu PR num arquivo do diretório de rascunho
que o harness anuncia como "session-specific, isolated from the user's project",
publica com `gh pr edit <N> --body-file <rascunho>`, e o harness avisa:

```
Note: .../scratchpad/pr-body.md changed on disk since you last read it.
```

E o conteúdo que aparece é de OUTRO assunto — o PR de outra frente, com outros
arquivos e outros números. Você não editou nada; outra sessão escreveu no mesmo
caminho.

**Causa.** O caminho do rascunho carrega um identificador de sessão
(`.../<uuid>/scratchpad`), o que dá a impressão de isolamento. Mas num despacho
com **agentes irmãos** — a sessão raiz delegando vários robôs em paralelo — os
irmãos herdam o identificador do pai, e o diretório é o **mesmo para todos**. Um
nome genérico (`pr-body.md`, `notas.md`, `saida.txt`) é então uma colisão
esperando a hora: dois robôs escrevem, o último ganha, e nada avisa antes.

É a `RETROSPECTIVA-FASE-D` §7 (sessões paralelas: arquivo novo, nunca o fim de um
arquivo compartilhado) aplicada a uma superfície que **não é do repositório** —
por isso nenhuma muralha deste projeto a protege, e por isso ela engana: as
outras colisões de sessão paralela (`armadilhas/053`, `/068`, `/135`) todas
moram no Git, onde há mecanismo.

**O que estava a um passo de acontecer.** Se o outro robô tivesse escrito
**antes** do meu `gh pr edit` ler o arquivo, o meu PR teria sido publicado com a
descrição do PR dele — texto plausível, formatado, assinado do mesmo jeito, e
sobre outro assunto inteiro. Ninguém revisa descrição de PR procurando isso.

**Solução: nome único por sessão, sempre.** O prefixo mais barato é o da tarefa
ou do ramo:

```bash
CORPO="$SCRATCH/pr-body-TAR-017.md"      # nunca `pr-body.md`
gh pr edit 573 --body-file "$CORPO"
```

E, depois de qualquer publicação feita a partir de um arquivo de rascunho,
**confira o que foi publicado, não o que você escreveu** — é a prova de fora
(`RETROSPECTIVA-FASE-D` §3), e custa um comando:

```bash
gh pr view <N> --json body --jq '.body | .[0:300]'
```

**Origem.** 30/08/2026, TAR-017. O rascunho `pr-body.md` foi sobrescrito por um
robô irmão que trabalhava no fórum da escola, entre o meu `gh pr edit` e o aviso
do harness. Desta vez o `gh` leu o arquivo antes da troca e o PR 573 saiu certo
— conferido pela leitura de fora. Foi sorte de milissegundos, não desenho.
