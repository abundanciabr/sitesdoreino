---
schema_version: 2
armadilha: 127
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: vacina
  detector: rerun_de_deploy
  dono: ci/rerun_de_deploy.py
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

**Desde 30/08/2026 (TAR-013) O PRÓPRIO DEPLOY FAZ ISTO — você provavelmente não
precisa fazer nada.** O `deploy-celula.yml` mede a porta 22 na partida e depois
de cada recusa, repete com pausa (45 s e 60 s) e só a 3ª tentativa decide o
veredito. E ele **registra**: o resumo do run diz, em português, quantas
tentativas foram precisas, o que cada medição da porta disse e se o que foi
mergeado está ou não em produção — abrir a execução basta, não é preciso cavar
log. A medição e a tabela de decisão moram em `ci/sonda_da_vps.py`; a fiação e o
porquê de cada regra estão nos comentários do job `deploy`.

Duas coisas que o desenho garante, e que valem saber antes de mexer:

- **A sonda nunca derruba entrega que ainda poderia dar certo.** A única direção
  em que ela encurta o laço é a provada: DUAS medições dizendo "porta morta"
  pulam a 3ª tentativa (é a 017, e a 3ª só falharia igual). Porta viva ou "não
  consegui medir" mantêm o retry inteiro.
- **O workflow lê `outputs.veredito`, nunca `outcome`.** O `outcome` de um passo
  só tem dois valores e juntaria "a porta está morta" com "não consegui medir" —
  a confusão que o [INV-CI01] proíbe, e que faria a sonda abortar deploys por
  defeito próprio.

> **Esta lição tem DUAS guardas, e o frontmatter só cabe uma.** O campo
> `guarda.dono` acima aponta para `ci/rerun_de_deploy.py` (a vacina do PC), que
> é a que existia primeiro. A vacina de dentro do deploy é imposta por
> `ci/tests/test_sonda_da_vps.py` — ele reprova se os passos de medição saírem
> do workflow, se a parada antecipada se contentar com UMA medição, ou se
> alguém trocar a leitura do veredito pelo `outcome`. Buraco de vocabulário
> declarado, não silencioso.

**Se mesmo assim o run terminar vermelho, aí sim rode a vacina do PC:**

```bash
python ci/rerun_de_deploy.py --run <id>      # ou --ultimo
```

Ela cuida do que o deploy não alcança: um run que já terminou (inclusive o
CANCELADO da [188](188-deploy-de-push-cancelado-pela-cadeira-musical-fica-fora-do-ar.md)).
Colhe o veredito por `--json` (nunca por pipe), confirma que a falha é o timeout
de SSH, mede a porta 22 — a MESMA medição, importada de `ci/sonda_da_vps.py`,
para que as duas vacinas não possam discordar sobre o mesmo fato —, separa o
blip da [017](017-cloudflare-na-frente-do-dominio-deploy-morre-em.md), repete com
pausa, para na terceira e escreve o texto da pendência para o livro.
`--so-diagnosticar` decide e explica sem repetir nada.

O texto abaixo continua valendo — é o raciocínio que as duas vacinas automatizam,
e é o que você lê quando elas PARAM e devolvem a decisão para um humano.

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
