---
schema_version: 2
armadilha: 377
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - infra/provisionar-par-do-portfolio-com-a-admin.sh
  - infra/provisionar-pages.sh
  - infra/provisionar-admin.sh
guarda:
  tipo: nenhum
  motivo: o conserto e em infra/, caminho CODEOWNERS, e virou tarefa na fila; ate la o que existe e esta licao
sinal:
  - "n[aã]o consegui recarregar"
  - "a pr[oó]xima entrega de cada c[eé]lula rel[eê] o env"
licao: Roteiro que recarrega célula com `docker compose up -d <servico> >/dev/null 2>&1` pode DERRUBAR o container e não subi-lo, e o `2>&1` apaga a única prova disso. Um passo que mexe em processo no ar mede o resultado (`docker compose ps` e a rota de saúde de fora) e nunca trata "não recarreguei" como aviso benigno.
---

# Roteiro que recarrega célula esconde o erro, e a deixa caída

**Sintoma.** O roteiro de provisionamento roda até o fim, imprime `PRONTO`, e
avisa em tom de rodapé:

```
== recarregando as duas células ==
  (aviso: não consegui recarregar admin pages. Os arquivos JÁ estão certos;
   a próxima entrega de cada célula relê o env. Avise o agente.)

PRONTO: a fila da conferência do portfólio está aberta.
```

A frase promete que nada de ruim aconteceu: os arquivos estão certos, e a
próxima entrega resolve. Mas a célula estava **fora do ar**, e ninguém soube:

```
https://meshcraft.top/pages/          502
https://meshcraft.top/pages/healthz   502
```

Medido em 06/09/2026, três vezes seguidas, cerca de seis minutos depois do
`PRONTO`. Quem descobriu foi a maestro, sondando de fora por hábito; o roteiro
tinha dito o contrário na tela.

**Causa.** O passo de recarregar é assim:

```sh
if docker compose up -d $ALVOS >/dev/null 2>&1; then
  echo "  recarreguei:$ALVOS"
else
  echo "  (aviso: não consegui recarregar$ALVOS ...)"
fi
```

Duas coisas se somam, e cada uma sozinha seria inofensiva:

1. **`docker compose up -d <servico>` não é atômico.** Ele REMOVE o container
   antigo antes de subir o novo. Se o `up` falhar no meio (ou o comando inteiro
   sair diferente de zero por qualquer razão), o estado final não é "continuou
   como estava": é **removido e não substituído**. A saída real do conserto
   mostra os dois tempos, e o primeiro já tinha acontecido:
   `✔ Container plataforma-pages-1 Removed` / `✔ Container 548d…pages-1 Started`.

2. **`2>&1` apagou a prova.** O erro que teria dito o porquê foi para
   `/dev/null`, então nem quem colou nem quem leu a tela tinha como saber o que
   houve. O roteiro sabia que falhou e escolheu não mostrar.

O texto do aviso é a terceira parte do problema: ele afirma um fato que o
roteiro **não mediu** ("os arquivos JÁ estão certos" é verdade; "a próxima
entrega relê o env" também; mas a conclusão que o leitor tira, *"então está
tudo funcionando como antes"*, é falsa). Aviso que tranquiliza sem medir é pior
que erro cru.

**Solução.** Um passo que mexe em processo no ar tem três obrigações, e nenhuma
delas é opcional:

- **Nunca engolir a saída de erro.** Capture em variável e imprima no caso
  ruim; `>/dev/null 2>&1` num comando que muda o mundo é cegueira deliberada.
- **Medir o resultado, não o código de saída.** Depois do `up`, rodar
  `docker compose ps <servicos>` e conferir que cada um está `Up` e `healthy`.
  Exit zero de um `up` não é prova de container de pé.
- **Falar a verdade sobre o estado.** Se o container não voltou, isso não é
  aviso: é **PARADA**, com a linha de conserto pronta na tela e o alerta de que
  a página está fora do ar agora.

O conserto que devolveu a célula:

```bash
cd /opt/plataforma && docker compose up -d admin pages; docker compose ps admin pages
```

```
✔ Container plataforma-pages-1   Started
pages   Up 20 seconds (healthy)
admin   Up 4 minutes (healthy)
```

E a prova de fora, que é a que vale: `/pages/healthz` 200, `/pages/` 200,
`/pages/equipe` 200.

**Parente próximo.** A `armadilhas/260` (o botão de consertar entregue e nunca
apertado) e a `armadilhas/253` (arquivo corrigido, deploy verde, página no ar
com o texto antigo) são da mesma família: **entregar a capacidade e verificar o
efeito são dois passos, e o rito só media o primeiro.** A diferença aqui é que
o roteiro chegou a TENTAR o segundo, viu que falhou, e mesmo assim imprimiu
`PRONTO`.
