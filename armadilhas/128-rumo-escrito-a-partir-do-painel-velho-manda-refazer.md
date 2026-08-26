# Rumo escrito a partir do painel velho manda refazer o que já está pronto

**Sintoma:** o livro de ocorrências tem registros de tipo `rumo` — "o próximo passo
desta frente é X" — e, ao despachar X, o agente descobre no código que **X já foi
entregue**, às vezes no dia anterior, com PR mergeado e deploy verde. Não há erro,
não há vermelho: só um lote inteiro prestes a ser gasto refazendo trabalho feito.

**Medido em 26/08/2026:** dos quatro rumos registrados naquele dia, **três
descreviam trabalho já concluído em 25/08**:

| Rumo registrado | Realidade medida no código |
|---|---|
| "faltam as três peças da fábrica: o vigia dos vigias, o alarme completo e a partida em 1 comando" | as três entraram em 25/08 — PRs #173, #171 e #174 |
| "apresentar o site à Caixa: as duas peças guardam a mesma pessoa em fichas separadas" | a Fase 1 do plano de notificações entrou em 25/08 (`id_da_plataforma` em `services/sugestoes`) |
| "algumas peças do site mostram hora com fuso errado" | nenhuma célula renderizava data em template — o defeito existia, mas **dormente**, e nada estava errado na tela |

**Causa:** os rumos foram redigidos a partir de uma **fotografia de painel** —
`docs/paineis/fotografias/fotografia-20260825-retomada.html`. E a fotografia estava
internamente inconsistente: a seção 4 dizia "faltam 3 peças" e o bloco de incidentes
do MESMO arquivo, mais abaixo, dizia "PLACAR FINAL: 6 de 6 mergeados", listando
nominalmente as três peças. Quem lê de cima para baixo e para na seção 4 escreve um
rumo falso, de boa-fé.

Fotografia é **história congelada** — é para isso que ela existe, e por isso não se
atualiza. Ela é fonte legítima para "o que aconteceu naquele dia" e fonte **ilegítima**
para "o que falta hoje".

**Solução — a regra, em uma frase: `rumo` é o único tipo de registro cujo conteúdo
precisa ser medido no CÓDIGO antes de ser escrito.** Os outros tipos narram um fato
que acabou de acontecer, e quem escreve estava lá. O `rumo` afirma uma **ausência**
("isto ainda não existe"), e ausência não se lê em documento nenhum: lê-se em disco.

Antes de registrar um rumo, gaste os dois minutos:

```bash
ls ci/ services/            # a peça que eu vou prometer já está aí?
grep -rn "<o sintoma>" ...  # o defeito que eu vou descrever ainda existe?
git log --oneline -15 -- <caminho>   # alguém já mexeu nisto?
```

E, ao despachar um rumo escrito por outra sessão, **meça de novo antes de gastar o
lote**. Foi o que salvou o lote de 26/08: a medição custou minutos, o despacho teria
custado o lote inteiro.

**O antídoto que já existia e não foi usado:** o rumo se fecha com um registro NOVO
apontando `responde_a`. Quem entregou as três peças em 25/08 registrou a entrega,
mas ninguém apontou `responde_a` para os rumos — porque os rumos foram escritos
DEPOIS. Rumo nascido velho não tem como ser fechado pela mecânica da casa: ele
precisa nascer medido.

**Categoria** (RETROSPECTIVA-FASE-D): é a **prova de fora** aplicada ao futuro, e é
prima do **falso-verde** — um documento afirmando estado em vez de o estado ser
medido. A mesma doença que a lei anti-duplicação cura para o passado, aqui aparecida
no tempo verbal do futuro.

**Origem:** lote do fuso horário, 26/08/2026 — o lote foi despachado com quatro
rumos e sobrou um, porque três já estavam feitos.
