---
schema_version: 2
armadilha: 324
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o portão compara o congelado com o schema VIVO byte a byte, e as duas pontas carregam a mesma prosa errada — divergência zero, PASS legítimo. Nenhuma máquina sabe se uma frase em português descreve o que o código faz. O que existe é a leitura da saída do exportador antes de abrir o PR do Rito, e ela cabe em dois minutos
sinal:
  - "ESCREVER AQUI SIGNIFICA"
  - "info.description"
  - "idêntico ao congelado"
  - "export_openapi"
---

# A prosa da porta também vira pedra: leia o `description` antes do Rito de Contrato

**Sintoma.** Não há sintoma, e nunca haverá. É o ponto.

Você acrescenta uma operação à porta de máquina de uma célula, com teste,
mutação e muralha verde. O PR mergeia. No PR seguinte, o do Rito de Contrato,
você roda o exportador, gera o `contracts/<celula>.openapi.yaml` e mede:

```
  contrato/<celula>   PASS   idêntico ao congelado (760 linhas comparadas)
```

PASS honesto, e o arquivo está errado. No `info.description` do documento,
congelada palavra por palavra, está a frase que descrevia a porta de ontem:

```
ESCREVER AQUI SIGNIFICA PUBLICAR VERSAO NOVA.
```

Só que agora a porta tem duas escritas, e a segunda não publica versão nenhuma.

**Causa.** `ci/contract_freeze.py` compara o congelado com o schema VIVO. As
duas pontas saem do mesmo lugar, então a prosa errada aparece idêntica dos dois
lados e a divergência é zero. O portão está certo: ele mede o que promete medir.

O que não é medido por nada é a única parte do contrato escrita para uma pessoa.
`info.description`, o `summary` e o `description` de cada operação são o texto
que quem for construir a tela do outro lado vai ler para saber o que "salvar"
significa. Nenhum teste os compara com o comportamento, porque nenhuma máquina
sabe fazer isso.

**E a janela onde ela apodrece é criada pela própria lei.** `armadilhas/228`
obriga a ordem *porta primeiro, contrato depois*, em dois PRs — a cerca
(`ci/cerca-de-celula.sh`) proíbe juntá-los. Então existe sempre um intervalo em
que a porta já mudou e a autodescrição dela ainda não, e o PR que fecha esse
intervalo é justamente o que transforma a prosa em pedra: corrigir uma frase
depois do congelamento exige **outro Rito de Contrato**, com o mantenedor
presente.

O reflexo que atrapalha é razoável: texto dentro de um `description=` parece
comentário, e comentário não é código. Aqui ele é conteúdo do artefato
congelado.

**Solução — dois minutos, entre um PR e o outro.** Antes de abrir o PR do Rito,
gere a saída crua e LEIA as frases dela:

```bash
cd services/<celula> && python manage.py export_openapi | python -m json.tool | less
```

E responda três perguntas, com o diff da porta ao lado:

1. **O `info.description` ainda descreve TODAS as operações?** Frase que começa
   com "esta porta faz X" ou "escrever aqui significa Y" é a primeira a
   envelhecer, porque foi escrita quando havia uma operação só.
2. **Ele conta quantas são?** "As cinco operações" vira mentira no dia em que
   nasce a sexta, e o número é o pedaço mais fácil de esquecer.
3. **O `description` da operação NOVA explica a consequência, e não só o gesto?**
   Quem consome não vê o código: se desligar uma sequência não interrompe quem
   já está dentro, isso precisa estar escrito aqui, ou a tela do outro lado vai
   prometer o que o sistema não faz.

**Onde já mordeu.** 04/09/2026, degrau 6d do
`PLANO-SEQUENCIAS-DE-MENSAGENS.md`. O PR #1009 acrescentou o interruptor
(`setJourneyActive`) à porta da `mensageria` e mergeou verde; a frase acima só
apareceu quando o YAML do PR seguinte foi gerado e lido. Custou um PR a mais
(#1010) — barato, porque ainda era antes. Depois do congelamento, o mesmo
conserto seria uma sessão de arquitetura com o mantenedor.

Parente de `armadilhas/228` (a ordem dos dois PRs) e de `armadilhas/318` (a
premissa que o padrão copiado não carrega): as três são a mesma família — **o
que a lei separa em dois PRs cria um intervalo, e é dentro dele que a verdade
sobre a porta fica velha.**
