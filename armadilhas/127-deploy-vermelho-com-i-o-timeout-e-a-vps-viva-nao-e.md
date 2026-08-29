---
schema_version: 2
armadilha: 127
estado: recorrente
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: `a vacina (medir a porta 22, repetir com pausa, parar na terceira e registrar) ainda nao foi construida — e este e o maior sangramento medido do catalogo: 6 quedas em 3 dias, mais a de 29/08/2026 durante a propria auditoria. Buraco assumido, com o conserto ja desenhado.`
sinal:
  - `dial tcp [^\n]*:22: i/o timeout`
---

# Deploy vermelho com `i/o timeout` e a VPS viva: nem todo timeout é a armadilha 017

**Sintoma:** `deploy-celula` falha em `dial tcp ***:22: i/o timeout` — e o padrão é
**intermitente**, não constante: numa mesma janela de merge de 10 minutos, o deploy
de uma célula passa, o da seguinte falha, o rerun passa, o da terceira falha
**duas vezes** e passa na terceira. A plataforma responde 200 de fora o tempo
inteiro.

**Por que isso confunde:** a [017](017-cloudflare-na-frente-do-dominio-deploy-morre-em.md)
descreve a MESMA mensagem de erro, e ela é a primeira que o índice devolve. Mas a
017 é uma falha **permanente e explicável** (o `VPS_HOST` virou um domínio atrás do
Cloudflare, que não repassa a porta 22): depois que ela começa, nenhum deploy passa
mais. Tratar o caso intermitente como se fosse a 017 leva a mexer em segredo de
repositório — que é território do mantenedor — para consertar algo que não está
quebrado.

**A medição que separa os dois casos, em uma linha, do PC:**

```bash
timeout 10 bash -c 'exec 3<>/dev/tcp/217.196.62.220/22 && head -c 30 <&3'
```

- Imprime `SSH-2.0-OpenSSH_9.6p1 Ubuntu-3` ⇒ a porta 22 está viva e alcançável.
  O problema está entre o **runner do GitHub** e a VPS, não na configuração.
  É blip: `gh run rerun <id> --failed`.
- Não imprime nada / trava ⇒ aí sim investigue a 017 (o que o `VPS_HOST` resolve?).

Vale confirmar também que o site continua no ar — `curl -o /dev/null -w "%{http_code}"
https://meshcraft.top/healthz`. Deploy vermelho por SSH significa que a imagem NOVA
não subiu; a **antiga continua servindo**. Ninguém fica fora do ar, mas o merge que
você acabou de fazer **não está em produção** até o rerun ficar verde — e é fácil
esquecer disso e reportar a entrega como no ar.

**Solução:** rerun. Se o segundo rerun também falhar, **espere ~1 minuto antes do
terceiro** em vez de emendar: em 26/08/2026 as duas primeiras tentativas do deploy
do `funil` falharam a 80 segundos uma da outra, e a terceira — depois da pausa —
passou. Reruns emendados parecem baratos e podem estar batendo exatamente na janela
que causou o timeout.

**Regra de parada:** três reruns vermelhos com o banner respondendo ⇒ pare de repetir
e registre uma pendência no livro (`painel/registros/`). Repetir uma quarta vez não
é diagnóstico, e a essa altura o merge já está na `main` sem estar em produção — o
que o mantenedor precisa saber é exatamente isso.

**Origem:** janela de merge do lote do fuso horário, 26/08/2026 — deploys dos PRs
#233 (verde de primeira), #234 (1 rerun) e #235 (2 vermelhos, verde no 3º), com o
banner SSH respondendo do PC durante toda a janela e os três domínios em 200.
