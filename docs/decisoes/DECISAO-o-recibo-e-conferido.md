# DECISÃO — o recibo do pedido é conferido, não lembrado

**Data:** 29/08/2026 · **Quem decidiu:** o mantenedor (achou o defeito) · **Estado:** valendo

## O que aconteceu

O mantenedor abriu `meshcraft.top/forms/sugestoes/entrar` e leu:

> **Seu pedido já está com a gente**
> Alguém da equipe vai conferir e liberar o seu acesso. Não precisa pedir de
> novo, nem ficar atualizando: esta página se atualiza sozinha e leva você para
> o site assim que a liberação sair.
> `acainitemacapa@gmail.com`

Ao mesmo tempo, o painel dele dizia:

> **Ninguém está esperando agora.** Este zero é medido, não suposto: eu
> perguntei e a fila voltou vazia.

**As duas telas estavam certas sobre o que cada uma sabia.** O painel mediu a
fila e ela estava vazia. A porta não mediu nada — ela leu um **cookie**.

Ele esperou mais de uma hora por um pedido que não existia.

## A causa

`_tela_da_fila` montava o recibo assim:

```python
recibo = request.COOKIES.get(PEDIU_ENTRADA) == _marca_do_pedido(email)
```

Um cookie de **30 dias**, gravado no instante do pedido. Ele não sabe nada sobre
a fila: continua afirmando *"seu pedido está com a gente"* depois de a linha ter
sido liberada, recusada, **ou apagada** — que é justamente o que aconteceu, no
dia em que apagar ficha ainda existia.

E o pior detalhe: **a informação certa já estava disponível, e era jogada fora.**
A `alunos` responde `na_fila` em `GET /alunos/{email}/situacao` desde
28/08/2026. A porta recebia essa resposta e a colapsava:

```python
ESTADO_POR_CATEGORIA = {
    ...
    "cadastrado": SEM_MATRICULA,
    "na_fila": SEM_MATRICULA,   # ← as duas viram a mesma coisa
}
```

Ou seja: a porta descartava o fato e reconstruía uma versão pior dele a partir
do navegador. É *garantia sem mecanismo* (`RETROSPECTIVA-FASE-D.md` §2) na sua
forma mais pura — uma tela afirmando com confiança algo que ninguém conferiu.

## O que muda

1. **`NA_FILA` vira um estado próprio da porta.** `"na_fila"` deixa de casar com
   `SEM_MATRICULA`. A `alunos` já sabia a diferença; agora a porta também.
2. **O recibo vem de `NA_FILA`, e só dele.** Existe uma exceção legítima: logo
   depois do POST, `ja_pediu=True` é a resposta que a `alunos` acabou de dar a
   **este** pedido, nesta requisição — não uma lembrança.
3. **O cookie `caixa_pedido_na_fila` e a `_marca_do_pedido` morreram.** Um
   cookie a menos, uma verdade a menos, e a tela deixa de poder mentir.
4. **`NA_FILA` entra na lista de permissão de quem pode enfileirar.** Sem isso,
   quem já está na fila cairia num redirecionamento mudo ao tentar corrigir um
   telefone errado — o caminho que a lei da fila §7 define como a correção.

## A direção do erro, que é a decisão

O padrão de `ja_pediu` passou a ser `False`.

- Mostrar o **formulário** para quem já pediu custa um reenvio. O reenvio é
  idempotente do outro lado — a chave `(site_id, email)` garante isso — e a lei
  da fila §7 já o prevê como o jeito de corrigir um dado.
- Mostrar o **recibo** para quem não pediu custa uma pessoa esperando
  indefinidamente por algo que nunca vai chegar.

Os dois erros não têm o mesmo preço, e é por isso que o padrão é o barato.

## O que NÃO mudou

- A porta continua **403** para quem não entrou, continua nomeando o e-mail e
  continua oferecendo trocar de conta.
- O relógio que recarrega a página sozinha continua ligado ao recibo — só que
  agora o recibo é um fato.
- A `alunos` fora do ar continua caindo em `INDISPONIVEL`, com a tela dizendo
  que o problema é nosso. **Nenhum caminho novo apaga um pedido real:** o
  formulário só volta quando a `alunos` responde, e responde `cadastrado`.

## Guardas

`services/sugestoes/tests/test_a_fila_de_espera.py`:

- `test_sem_linha_na_fila_a_porta_devolve_o_FORMULARIO_e_nao_o_recibo` — o
  defeito de 29/08 em pessoa;
- `test_recarregar_a_porta_nao_devolve_o_formulario_vazio` — reescrito: o
  recibo sobrevive ao recarregar **porque a `alunos` o confirma**. Ele passava
  antes, com o cookie, e é por isso que o defeito ficou invisível;
- `test_quem_esta_na_fila_pode_reenviar_e_corrigir_os_dados` — a lei §7
  continua valendo com o estado novo.

## A lição, maior que o caso

Um cookie, um `localStorage` ou uma variável de sessão que afirma um fato de
OUTRA célula é sempre uma segunda verdade — e ela só é descoberta no dia em que
discorda. Quando a informação existe do lado de lá, **perguntar é mais barato
que lembrar**: a pergunta erra para "não sei", que tem tela; a lembrança erra
para "tenho certeza", que não tem.
