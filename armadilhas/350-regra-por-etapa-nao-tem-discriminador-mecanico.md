---
schema_version: 2
armadilha: 350
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: ci/tests/test_prestacao_de_contas.py
sinal:
  - "checklist ausente ap[óo]s (?:Bash|Edit|Write|PowerShell)"
---

# 350 — Obrigação "ao fim de cada etapa" não tem discriminador mecânico: meça a ponta que dá, e declare o meio

**Data:** 05/09/2026 · **Onde:** qualquer portão de hook (`Stop`,
`PostToolUse`) que tente cobrar do robô algo "a cada passo", "a cada etapa",
"a cada fase" · **Custo evitado:** um portão que grita a cada `ls`, e que o
mantenedor aprende a ignorar em um dia (o mesmo destino que as 225
notificações de espera teriam dado à prestação de contas, se ela fosse cobrada
em todo turno)

## Sintoma

O mantenedor pede: "toda e cada tarefa mostre um checklist e um roadmap claro
de onde está e o que ainda precisa ser feito ao final de cada etapa". A
primeira ideia de mecanismo é contar: reimpressões do checklist contra
chamadas de ferramenta, ou contra "mudanças no mundo". Em transcript real, isso
dá uma destas duas saídas, e as duas são ruins:

```
🧾 checklist ausente após Bash: ls ci/tests        ← grita a cada leitura
🧾 checklist ausente após Edit em a.py             ← grita no meio de uma etapa de 3 edições
```

Ou o portão cala de vez, porque quem o escreveu viu o ruído e afrouxou a régua
até ela não pegar mais nada.

## Causa

"Etapa" é uma unidade do PLANO do robô, não do transcript. A máquina vê
chamadas de ferramenta e falas; não vê onde uma etapa começa e acaba. Qualquer
contagem por chamada mede a coisa errada com precisão, e medir a coisa errada
com precisão é como um portão morre (`CLAUDE.md`, lei do travessão).

## Solução

Separe a obrigação em pontas, e meça só a que a máquina enxerga:

1. **A ponta final é mensurável.** O fim do turno já é cobrado pelo `Stop`
   (`ci/prestacao_de_contas.py`); exija que a prestação de contas CONTENHA o
   checklist no estado final (linha `- [x]`/`- [ ]`). É uma regex de uma
   linha, com par vermelho (`[x]` solto na prosa não vale) e par verde
   (`- [ ]` aberto com NÃO PRONTO vale, senão o portão ensina a marcar o que
   não foi feito).
2. **A ponta do meio fica na lei, no aviso de abertura e na memória do robô**,
   e a lei DIZ que ela não tem mecanismo. O `--plano` do `UserPromptSubmit` é a
   única janela em que a ponta do meio pode ser lembrada antes de acontecer.
3. **A recusa da ponta final ensina as três pontas.** Quem foi cobrado uma vez
   no fecho aprende a reimprimir no meio: o molde da recusa diz "reimpresso
   marcado ao fim de CADA etapa".

A prova de que a régua está no lugar certo: o teste novo tem de ficar VERMELHO
contra o portão antigo por FALTA do checklist, e não por ruído em turno de
leitura. Medido em 05/09/2026, sabotando SÓ o guarda da caixinha: 4 testes
vermelhos pelo guarda (relatório sem checklist, caixinha solta na prosa,
PRONTO com caixa aberta, caixinha quebrada em duas linhas); os outros 13 que caem contra o portão velho caem porque a recusa passou a
ensinar a caixinha, que é molde, não guarda. Conte os dois números separados:
"15 vermelhos" é prova inflada, e foi assim que a primeira versão desta
entrada saiu (achado do revisor do PR #1126). E os testes das 225 esperas
continuam calados.
