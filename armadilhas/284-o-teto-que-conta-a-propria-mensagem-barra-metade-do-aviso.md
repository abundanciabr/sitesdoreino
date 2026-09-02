---
schema_version: 2
armadilha: 284
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: nenhum portão sabe distinguir "este teto deve contar a linha atual" de "não deve" — depende do que a unidade do teto significa no domínio; o guarda é o par de testes que prova as duas pontas (o irmão do mesmo passo passa, a segunda mensagem do dia é barrada)
sinal:
  - a segunda via de um mesmo aviso registrada como barrada pelo teto que a primeira via acabou de gastar
  - `ja recebeu 1 hoje (teto de 1 por dia)` numa entrega que é o MESMO acontecimento de outra
---

# O teto que conta a própria mensagem barra metade do aviso, e parece estar funcionando

**Sintoma.** Um aviso configurado para sair por dois caminhos (sininho **e**
e-mail) sai por um só. A tabela de entregas fica assim:

```
email    barrada_pela_regua     ja recebeu 1 hoje (teto de 1 por dia)
sino     enviada
```

E o e-mail nunca volta: dez dias de varredura depois, a linha continua
`barrada_pela_regua`, `enviado_em=None`. A jornada seguiu em frente sem ele.

**O que torna isto perigoso é a tela.** A explicação gravada é *"já recebeu 1
hoje"*, que se lê como **a régua funcionando**. Quem for investigar "por que o
aluno não recebeu o e-mail?" encontra uma resposta plausível, correta na forma e
falsa no fundo: a mensagem que ele "já recebeu" **é a própria**, pela outra via.

**Causa.** O teto contava LINHAS de entrega, e a entrega é gravada **por canal**
— de propósito, para que sino entregue, e-mail devolvido e WhatsApp barrado
sejam três resultados independentes. Aí o sino saía, gravava
`resultado="enviada"`, e o e-mail **do mesmo passo** batia na linha que o sino
acabara de escrever.

**A correção que parece bastar e não basta.** O reflexo é contar mensagens
distintas em vez de linhas:

```python
.values("inscricao_id", "passo_id").distinct().count()   # ainda vermelho
```

Com teto 1, a linha do sino **continua valendo 1**, e o e-mail continua barrado
por ela. Medido: o guarda dos dois canais seguiu falhando depois desta mudança.
A conta só fica certa quando se percebe que a pergunta do teto não é *"quantas
saíram hoje?"* e sim:

> **quantas OUTRAS mensagens esta pessoa já recebeu hoje?**

A mensagem que está sendo avaliada **não conta contra si mesma**.

**Solução.** Quem avalia recebe a identidade do que está avaliando, e a exclui:

```python
def _quantas_hoje(destinatario_id, site_id, momento, excluir=None):
    consulta = Entrega.objects.filter(...)
    if excluir is not None:
        inscricao_id, passo_id = excluir
        consulta = consulta.exclude(inscricao_id=inscricao_id, passo_id=passo_id)
    return consulta.values("inscricao_id", "passo_id").distinct().count()

# e quem chama diz qual mensagem é:
regua.avaliar(..., mensagem=(inscricao.pk, passo.pk))
```

**A régua que generaliza:** todo limitador de taxa precisa responder, em código,
**qual é a unidade que ele conta** — e se a coisa em avaliação já está dentro da
contagem. Quando a unidade do teto (a mensagem) e a unidade da tabela (a entrega
por canal) são diferentes, contar a tabela é contar errado, e o erro só aparece
no dia em que a segunda via existir.

**Por que ninguém viu antes.** A célula inteira usava um canal só
(`canais=["sino"]`), então o defeito era **latente**: 108 testes verdes, produção
correta, e um caminho — o multicanal, que é a razão de a chave da entrega incluir
o canal — sem um único teste funcional. Ele acordaria no degrau seguinte da
escada, o do e-mail de verdade.

**Irmã:** `armadilhas/283`, da mesma revisão — o desfecho que faltava na
varredura. O hábito que acha as duas é o mesmo: perguntar de cada guarda *"o que
ele faz quando nada acontece?"* e *"ele está se contando?"*
