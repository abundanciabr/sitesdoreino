---
schema_version: 2
armadilha: 322
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum sinal mecânico separa "comentário que descreve o que este arquivo faz" de "comentário que descreve o que outro PR vai fazer". Um portão que tentasse casar rota citada em comentário com `urlpatterns` reprovaria toda explicação legítima. O que segura é a regra de onde a profecia mora (tabela da escada, na constituição da célula) e o PR do degrau consertar a profecia que ele invalida
sinal:
  - "degrau 7.3"
  - "o que nasce aqui adiante"
  - "quando nascer"
---

# Comentário que profetiza o degrau seguinte envelhece sem avisar, e mente no arquivo mais confiável da célula

**Sintoma.** Você abre `config/urls.py` de uma célula para saber quais rotas ela
tem, e o comentário no topo descreve uma porta que não existe:

```python
#   degrau 7.3 — a recepção de eventos (`/interno/eventos`), fechada por Bearer
#                de par, fail-closed: evento inválido vai para a fila de mortos.
urlpatterns = [
    path("healthz", healthz),
]
```

O degrau 7.3 foi entregue, está no ar, e **não é isso.** A recepção virou
consumidor de Redis Streams, sem rota HTTP nenhuma. O comentário nunca esteve
certo: ele era um palpite escrito com a mesma tinta de um fato.

Nada acusa. Nenhum teste lê comentário, o `black` não se importa, a muralha
aprova, o `make ci` fica verde. E o arquivo em que a mentira ficou é justamente
aquele que qualquer um abre primeiro para responder "o que esta célula expõe?".

**Causa.** A gênese de uma célula nasce com a escada inteira desenhada (é o que
esta casa manda fazer: `PLANO-*.md` §8, a tabela de degraus na constituição). A
tentação seguinte é dizer isso também no código, no lugar onde o degrau vai
nascer, "para quem chegar depois não se perder". O texto fica ótimo no dia em
que é escrito.

Aí o degrau seguinte é construído por OUTRA sessão, com contexto próprio, e
descobre um caminho melhor. Ela acrescenta o que faltava e passa longe do
comentário, porque o comentário está num arquivo que ela não precisou tocar.
A profecia sobrevive ao fato que a desmentiu.

É a mesma família de `armadilhas/148` (ler do espelho velho em vez do
`origin/main`) e da doença do painel (`armadilhas/156`): **o mesmo fato em dois
lugares, e só um deles tem quem o corrija.**

**Solução, em duas regras.**

1. **Comentário de código descreve o que o arquivo FAZ hoje.** Se a frase tem
   verbo no futuro ("vai nascer", "quando nascer", "o que nasce aqui adiante"),
   ela não é comentário: é planejamento, e planejamento mora na tabela da escada
   da constituição da célula, que é lida como documento e revisada como
   documento. Um ponteiro é suficiente e não apodrece: `# a escada desta célula
   está em constituicoes/AGENTS.<celula>.md`.

2. **O PR que entrega o degrau conserta a profecia que ele desmente.** É trabalho
   do degrau, não faxina de outra pessoa: quem acabou de construir é a única
   pessoa no mundo que sabe exatamente qual palpite morreu. Custa três linhas no
   mesmo PR e evita que o próximo agente construa contra um desenho revogado.

**O que quase aconteceu, e é o custo real.** No degrau 7.4 da `metricas` (a porta
de leitura), o comentário dizia que a célula já teria uma porta `/interno/` com
Bearer desde o 7.3. Um agente que confiasse nele montaria a porta nova em
`/interno/`, para "ficar junto da que já existe" — endereço errado, contra o
formato majoritário da casa, e num prefixo que existe justamente para separar
porta de máquina de página pública, que esta célula não tem. O erro só apareceria
no congelamento do contrato, um PR depois, quando o endereço já é promessa.

**Origem:** degrau 7.4 da célula `metricas` (a porta de leitura do livro de
fatos), 04/09/2026. O `config/urls.py` e a constituição da célula descreviam a
recepção como porta HTTP `/interno/eventos`; ela nasceu, dois PRs antes, como
consumidor de Redis Streams. Os dois textos foram corrigidos no PR que descobriu
a divergência.
