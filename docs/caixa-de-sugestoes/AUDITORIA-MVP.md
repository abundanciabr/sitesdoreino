# AUDITORIA DO MVP — o Definition of Done da §11, item a item

> **Executada em 25/08/2026 (EVO-41, fecho do Lote 4).** Método: **prova por
> mutação**, não leitura. Para cada invariante declarado "coberto", o código foi
> quebrado de propósito num worktree descartável e a suíte teve de ficar
> **vermelha** — teste que passa mas nunca poderia falhar é decoração, e
> "desconfie de teste que passa" só vira evidência quando alguém tenta.
>
> **Quem escreveu isto é auditor, não conserta nada.** Toda divergência achada
> está registrada abaixo, com o argumento de qual lado está errado; nenhuma foi
> corrigida neste PR.
>
> Alvo medido: `origin/main` (o código da célula em `099edb1` e `a841567` é
> byte a byte o mesmo — os merges do intervalo tocaram só `armadilhas/`).

---

## Baseline, antes de qualquer mutação

```
$ cd services/sugestoes && python -m pytest -q
306 passed, 4 warnings in 17.76s
```

```
$ python ci/ci.py
  contrato/sugestoes    PASS   idêntico ao congelado (91 linhas comparadas)
  seguranca/sugestoes   PASS   1 operação(ões) com autenticação conferida na fonte
  guardas/declaracao    PASS   18 guardas declarados em 15 invariantes, todos em disco
  guardas/dentes        PASS   52 guardas .py com teste de verdade, sem skip/xfail
  testar-o-testador     PASS   483 passed in 44.59s
RESULTADO  SKIP            (exit 0 — os SKIP são das células ainda em esqueleto)
```

Ao fim de **cada** mutação o worktree foi restaurado e conferido:
`git status --porcelain` vazio e `306 passed` de volta.

---

## PLACAR

| # | Item do §11 | Veredito |
|---|---|---|
| 1 | Todas as invariantes da §8 cobertas por teste automatizado | **PASS COM RESSALVA** |
| 2 | Nenhuma ForeignKey cruzando banco de célula | **PASS** |
| 3 | Endpoint de avaliação de produto retorna **403** para qualquer ator sem role de staff | **PASS COM RESSALVA** — o §11 e o código discordam, e quem está errado é o §11 |
| 4 | Evento de mudança de status **publicado antes do commit** da transação | **PASS COM RESSALVA** — o §11 descreve o anti-padrão que o código evita |
| 5 | Auditoria do estado AS-IS documentada e anexada | **PASS COM RESSALVA** — existe, foi anexada a tempo, e **envelheceu** |

**Nenhum FAIL.** As quatro ressalvas são de três naturezas diferentes, e vale
não misturá-las: a do item 1 é um **buraco real de cobertura** (invariante sem
guarda, porque a funcionalidade não existe); as dos itens 3 e 4 são **erros de
redação do próprio §11**, com o código certo; a do item 5 é um **documento que
envelheceu**.

---

## Item 1 — Todas as invariantes da §8 cobertas por teste automatizado

**Veredito: PASS COM RESSALVA.** Cinco das seis invariantes têm guarda que
**morde**, provado por mutação. A sexta — *merge de sugestão é transacional* —
**não tem guarda nenhum**, e não pode ter: a funcionalidade não existe.

### 1.1 — "Um ator vota no máximo uma vez por sugestão"

**Mutação A** — a unicidade sai do model **e** da migration `0001_initial`:

```diff
-        migrations.AddConstraint(
-            model_name="voto",
-            constraint=models.UniqueConstraint(
-                fields=("sugestao", "autor"), name="voto_unico_por_ator_e_sugestao"
-            ),
-        ),
     class Meta:
-        constraints = [
-            models.UniqueConstraint(
-                fields=["sugestao", "autor"], name="voto_unico_por_ator_e_sugestao"
-            )
-        ]
+        pass
```

```
FAILED tests/test_inv_voto_unico_por_ator.py::test_segundo_voto_do_mesmo_ator_na_mesma_sugestao_e_recusado
1 failed, 305 passed, 4 warnings in 20.74s
```

> **Observação de auditoria, e ela não é ressalva:** só **um** teste reprova.
> Os guardas de endpoint continuam verdes porque o `get_or_create` de
> `participacao.py` resolve o caso comum em Python — a unicidade do banco é a
> rede de baixo, que só aparece na corrida de dois cliques. Está certo assim,
> mas quem apagar a constraint achando que "os testes de votar cobrem" vai
> encontrar 305 verdes.

### 1.2 — "Desvotar apaga a linha, nunca marca como inativa"

**Mutação B** — o desvoto lógico nasce (`Voto.removido_em` + migration `0006`):

```
E   AssertionError: Voto ganhou campo de desvoto lógico: {'removido_em'}.
    Desvotar apaga a linha (spec §8).
E   assert not ({'autor', 'criado_em', 'id', 'removido_em', 'sugestao'} &
                {'apagado_em', 'ativo', 'deleted_at', 'inativo', 'removido_em'})
FAILED tests/test_inv_voto_unico_por_ator.py::test_voto_nao_tem_campo_de_desvoto_logico
1 failed, 4 passed in 0.87s
```

**Mutação C** — `desvotar` para de apagar (`.delete()` → `.count()`):

```
FAILED tests/test_inv_aviso_nasce_com_o_status.py::test_o_vinculo_sobrevive_ao_desvoto
FAILED tests/test_inv_envelope_casa_com_contrato.py::test_os_votos_levam_quem_votou_e_o_total_depois_do_fato
FAILED tests/test_inv_voto_pelo_endpoint.py::test_desvotar_apaga_a_linha_e_nao_marca_nada
FAILED tests/test_inv_voto_pelo_endpoint.py::test_desvotar_duas_vezes_tambem_nao_estoura
FAILED tests/test_inv_voto_pelo_endpoint.py::test_o_voto_e_do_ator_da_sessao_e_de_mais_ninguem
FAILED tests/test_o_rosto.py::test_votar_e_desvotar_pela_tela_mudam_a_contagem_que_a_pessoa_ve
FAILED tests/test_participacao.py::test_uma_sessao_de_aluno_de_ponta_a_ponta
7 failed, 299 passed, 4 warnings in 16.07s
```

**COBERTO.**

### 1.3 — "`HistoricoStatus` é append-only" — os três degraus, falsificados separadamente

**Mutação D** — degrau 1, o `save()`/`delete()` de instância em
`RegistroAppendOnly` deixa de recusar:

```
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_o_registro_nao_e_editado_nem_apagado
FAILED tests/test_inv_historico_append_only.py::test_save_de_linha_ja_existente_e_recusado
FAILED tests/test_inv_historico_append_only.py::test_delete_da_instancia_e_recusado
3 failed, 303 passed, 4 warnings in 15.61s
```

**Mutação E** — degrau 2, o `AppendOnlyQuerySet` passa a delegar ao Django:

```
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_o_registro_nao_e_editado_nem_apagado
FAILED tests/test_inv_historico_append_only.py::test_update_em_massa_e_recusado
FAILED tests/test_inv_historico_append_only.py::test_bulk_update_e_recusado
FAILED tests/test_inv_historico_append_only.py::test_delete_em_massa_e_recusado
4 failed, 302 passed, 4 warnings in 18.27s
```

**Mutação F** — degrau 3, o trigger `sugestoes_historico_append_only` não é
criado (o `CREATE TRIGGER` da migration `0001` vira `SELECT 1;`):

```
FAILED tests/test_inv_historico_append_only.py::test_update_em_sql_cru_e_recusado_pelo_postgres
FAILED tests/test_inv_historico_append_only.py::test_delete_em_sql_cru_e_recusado_pelo_postgres
2 failed, 304 passed, 4 warnings in 15.51s
```

**COBERTO, e coberto por degrau.** Cada camada tem quem a derrube sozinha — é
exatamente a escada que o EVO-40 descobriu estar sem dente no degrau 1 e
consertou. Nenhum degrau está sendo carregado por outro.

### 1.4 — "`AvaliacaoInterna` nunca é lida ou escrita por endpoint que o aluno acessa"

**Mutação G** — a página do aluno passa a **ler** a avaliação
(`select_related("avaliacao")` em `ver_sugestao`):

```
FAILED tests/test_inv_avaliacao_interna_fora_do_alcance.py::test_nenhuma_consulta_do_aluno_toca_a_tabela_da_avaliacao
1 failed, 305 passed, 4 warnings in 15.58s
```

**Mutação H** — a rota de comentar passa a **escrever** na avaliação
(`update_or_create`):

```
FAILED tests/test_inv_avaliacao_interna_fora_do_alcance.py::test_nenhuma_consulta_do_aluno_toca_a_tabela_da_avaliacao
FAILED tests/test_inv_avaliacao_interna_fora_do_alcance.py::test_a_jornada_do_aluno_nao_escreve_na_avaliacao
FAILED tests/test_inv_avaliacao_interna_fora_do_alcance.py::test_o_modulo_do_aluno_nem_nomeia_a_avaliacao_interna
3 failed, 303 passed, 4 warnings in 15.28s
```

**COBERTO.** E um achado de calibragem que vale registrar: a **primeira**
tentativa da mutação H usou `get_or_create` sobre uma linha que a fixture já
tinha criado — escrita que não muda nada. O resultado:

```
FAILED ...::test_nenhuma_consulta_do_aluno_toca_a_tabela_da_avaliacao
FAILED ...::test_o_modulo_do_aluno_nem_nomeia_a_avaliacao_interna
2 failed, 304 passed
```

`test_a_jornada_do_aluno_nao_escreve_na_avaliacao` **ficou verde**, porque ele
compara o conteúdo antes e depois e nada tinha mudado. Não é defeito do guarda
(os outros dois degraus pegaram, que é para isso que a escada existe) — é o
lembrete de que **o degrau do meio sozinho não cobre escrita idempotente**. Quem
mexer neste arquivo: os três degraus são necessários, nenhum é redundante.

### 1.5 — "Nenhum model desta célula tem ForeignKey apontando para fora do banco"

Ver o **item 2**, abaixo — é o mesmo invariante, medido lá.

### 1.6 — "`Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` com ChangeSpec aprovado" (INV-SUG10)

Três degraus, falsificados separadamente.

**Mutação I** — degrau 1, o ponto de estrangulamento em
`registrar_mudanca_de_status` perde o `raise CorredorAusente`:

```
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_a_recusa_nem_chega_a_travar_a_linha
1 failed, 305 passed, 4 warnings in 15.95s
```

> Confirma, de fora, o que o `LICOES.md` da célula registrou: **um único teste**
> segura este degrau, e é o que mede o SQL (recusar antes do
> `SELECT … FOR UPDATE`). Sem ele, apagar o degrau 1 inteiro deixaria a suíte
> **verde** — os degraus 2 e 3 cobririam o buraco e a frase em português
> continuaria aparecendo pelo aviso preventivo da página. O guarda existe e
> morde; a margem é de um teste só.

**Mutação J** — degrau 2, o `Sugestao.save()` perde a conferência:

```
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_o_save_recusa_sem_changespec
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_o_save_sem_update_fields_tambem_e_recusado
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_o_changespec_de_OUTRA_ideia_nao_serve
3 failed, 303 passed, 4 warnings in 15.52s
```

**Mutação K** — degrau 3, o trigger `sugestoes_exige_changespec` da migration
`0004` não é criado:

```
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_queryset_update_e_recusado_pelo_postgres
FAILED tests/test_inv_changespec_trava_o_desenvolvimento.py::test_update_em_sql_cru_e_recusado_pelo_postgres
2 failed, 304 passed, 4 warnings in 12.97s
```

**COBERTO nos três degraus.**

### 1.7 — "Merge de sugestão é transacional" — **O BURACO, e é o achado deste despacho**

O invariante da §8, por extenso:

> *Merge de sugestão é transacional: ator que votou nas duas sugestões não vira
> dois votos; comentários e histórico da sugestão mesclada são preservados,
> nunca apagados; a URL da sugestão mesclada continua resolvendo, redirecionando
> para a canônica.*

**Não há guarda para nenhuma das quatro promessas dessa frase.** Não por
esquecimento: **a funcionalidade não existe.** Medido:

```
$ grep -rn "mescl|canonica|merge" services/sugestoes/apps/ --include=*.py
apps/core/moderacao.py:25  (comentário: "Mesclar sugestão. A §10 põe merge em V1.1")
apps/sugestoes/eventos.py:25 (comentário: "Fora daqui, de propósito: sugestao.mesclada")
apps/sugestoes/models.py:139  MESCLADO = "mesclado", "Mesclado"
apps/sugestoes/models.py:161  sugestao_canonica = models.ForeignKey(...)
# nenhuma linha de CÓDIGO escreve `sugestao_canonica` nem move votos.

$ ls contracts/eventos/ | grep sugestao
sugestao.criada.v1.json
sugestao.status-alterado.v1.json
sugestao.voto-adicionado.v1.json
sugestao.voto-removido.v1.json
# o `sugestao.mesclada` da §7 não foi congelado — não há o que emitir.
```

**A divergência é do documento, e é uma contradição interna da própria spec:**
a **§10** põe *"merge administrativo transacional"* explicitamente em **V1.1**;
a **§8** lista o invariante do merge sem ressalva; e a **§11** exige *"todas as
invariantes da seção 8"* para declarar o **MVP** pronto. As três não cabem
juntas: **o §11, como está escrito, é impossível de cumprir no MVP** — e um
agente futuro que o leia ao pé da letra ou (a) implementa merge dentro de um
despacho de fechamento, que é escopo de V1.1 entrando pela porta dos fundos, ou
(b) escreve um guarda vazio para o item ficar marcado, que é pior.

**O que existe no lugar, e é a coisa certa:** um guarda que impede alguém de
**fingir** que mesclou. Mutação L — `MESCLADO` entra na lista
`STATUS_QUE_A_EQUIPE_ESCOLHE`:

```
FAILED tests/test_inv_status_grava_historico.py::test_mesclado_nao_entra_pela_porta_do_status
1 failed, 305 passed, 4 warnings in 17.92s
```

Ou seja: o rótulo "mesclado" não pode ser aplicado por ninguém enquanto a
operação não existir, e a lista de mescladas não nasce mentindo com
`sugestao_canonica` vazia.

**Recomendação (não aplicada — auditor não conserta):** a §8 deveria marcar o
invariante do merge como **`(V1.1)`**, e a §11 deveria dizer *"todas as
invariantes da §8 que valem para o escopo do MVP"*. É uma linha em cada, e
resolve a contradição sem afrouxar nada. Enquanto não for feito, este item fica
**PASS COM RESSALVA**, com a ressalva sendo esta seção inteira.

---

## Item 2 — Nenhuma ForeignKey cruzando banco de célula

**Veredito: PASS.**

O guarda `tests/test_inv_sem_fk_para_fora.py::test_nenhuma_foreign_key_aponta_para_fora_da_celula`
varre os models de verdade pelo registro de apps — não uma lista mantida à mão.

**Mutação M** — uma FK para fora nasce (`Quadro.tipo → contenttypes.ContentType`,
um app que **está** no `INSTALLED_APPS` da célula mas **não** é dela):

```
E   AssertionError: FK saindo do banco da célula (Lei 3 / spec §8):
    sugestoes.Quadro.tipo -> contenttypes.ContentType. Referência a dado de
    outra célula é SNAPSHOT em coluna opaca (o que `Quadro.site_id` e
    `Quadro.produto_id` já são), nunca FK.
E   assert not ['sugestoes.Quadro.tipo -> contenttypes.ContentType']
FAILED tests/test_inv_sem_fk_para_fora.py::test_nenhuma_foreign_key_aponta_para_fora_da_celula
1 failed, 4 passed in 0.28s
```

E o guarda tem o guarda dele: `test_o_guarda_nao_passa_no_vazio` reprova se
alguém apagar `apps.sugestoes` do `INSTALLED_APPS` — sem isso a varredura
passaria verde por não ter nada a inspecionar.

Nota de leitura, para quem chegar aqui achando que achou uma violação:
`Sugestao.autor → Identidade` **é** ForeignKey de verdade e **não** fura a Lei 3.
`Identidade` mora no mesmo `sugestoes_db`. O que o Postgres não sustenta é
constraint **entre bancos**; dentro do banco, integridade referencial é de graça.

---

## Item 3 — "Endpoint de avaliação de produto retorna **403** para qualquer ator sem role de staff"

**Veredito: PASS COM RESSALVA. O §11 e o código discordam, e quem está errado é
o §11.**

### O que a célula devolve de verdade — medido, não suposto

Sonda descartável, três classes de ator, as quatro rotas da equipe:

```
ANONIMO            avaliacao (POST)   -> 302 /entrar
ANONIMO            fila (GET)         -> 302 /entrar
ANONIMO            moderar (GET)      -> 302 /entrar
ANONIMO            status (POST)      -> 302 /entrar

ALUNO (com sessao) avaliacao (POST)   -> 403
ALUNO (com sessao) fila (GET)         -> 403
ALUNO (com sessao) moderar (GET)      -> 403
ALUNO (com sessao) status (POST)      -> 403

SEM MATRICULA      avaliacao (POST)   -> 302 /entrar
SEM MATRICULA      fila (GET)         -> 302 /entrar
SEM MATRICULA      moderar (GET)      -> 302 /entrar
SEM MATRICULA      status (POST)      -> 302 /entrar
```

Ou seja: **403 para um dos três atores sem crachá; 302 para os outros dois.**
Lido ao pé da letra — *"403 para **qualquer** ator sem role de staff"* — o §11
está **falso em dois terços dos casos**.

### O 403 que existe morde, e isso está provado

**Mutação N** — `exige_staff` devolve 302 em vez de 403:

```
FAILED tests/test_changespecs.py::test_o_aluno_nem_chega_ao_segundo_portao
FAILED tests/test_inv_entrada_staff_sem_matricula.py::test_papel_do_contrato_nao_da_cracha
FAILED tests/test_inv_so_staff_modera.py::test_aluno_com_sessao_leva_403_em_TODA_rota_de_moderacao
FAILED tests/test_inv_so_staff_modera.py::test_o_aluno_nao_ve_a_fila_nem_o_texto_da_avaliacao
FAILED tests/test_inv_so_staff_modera.py::test_o_cracha_sai_com_a_variavel_de_ambiente
5 failed, 301 passed, 4 warnings in 13.73s
```

E a varredura é do **urlconf**, não de uma lista escrita à mão: rota de equipe
nova entra no guarda sozinha.

### Qual dos dois está errado, e por quê — o código

O desenho é **dois portões empilhados**, não um:

```python
def exige_staff(view):
    @wraps(view)
    def cracha(request, ator, *args, **kwargs):
        if not ator.e_staff:
            return HttpResponseForbidden(SEM_CRACHA, content_type="text/plain")
        return view(request, ator, *args, **kwargs)
    cracha.exige_staff = True
    return exige_sessao(cracha)          # ← o porteiro de sessão fica POR FORA
```

Três razões pelas quais o 403 universal seria **pior**, e não melhor:

1. **403 para quem não tem sessão é um beco.** "Proibido" é a resposta certa a
   quem já entrou e não tem o papel; a quem nem entrou, a única resposta útil é
   o botão de entrar. Devolver 403 ali seria dizer "tente de novo" sem dizer o
   quê — ou pior, esconder a porta de alguém com um link salvo.
2. **O 403 universal quebraria um invariante vizinho.** `exige_sessao` é o
   atributo por onde `tests/test_inv_sem_sessao_nada.py` varre o urlconf
   exigindo porteiro em toda rota não pública. Empilhar é o que faz as **três**
   varreduras (sem-sessão · staff · participação) somarem o urlconf inteiro, sem
   sobra nem sobreposição.
3. **O 302 do anônimo não vaza nada.** A view não roda: nada é lido, nada é
   escrito. O que o §11 quer garantir — *a avaliação interna não é alcançada por
   quem não é da equipe* — está garantido nas duas formas.

### Redação proposta para o §11 (não aplicada — fora dos alvos deste despacho)

> *"O endpoint de avaliação de produto devolve **403** a quem tem sessão de
> aluno e não tem crachá de equipe; quem chega **sem sessão** é mandado para a
> porta (**302** para `/entrar`) e a view não roda. Os dois portões são
> empilhados de propósito."*

---

## Item 4 — "Evento de mudança de status é **publicado antes do commit** da transação de status"

**Veredito: PASS COM RESSALVA. O mecanismo certo existe e morde; a frase do §11
descreve o anti-padrão que esse mecanismo existe para evitar.**

### O que o código faz

```python
    with transaction.atomic():
        ...
        travada.save(update_fields=["status"])
        HistoricoStatus.objects.create(...)
        avisar_os_interessados(...)
        eventos.emitir_status_alterado(...)     # ← grava na OUTBOX, antes do commit
    transaction.on_commit(relay_apos_commit)    # ← PUBLICA no Redis, depois do commit
```

São **dois momentos diferentes**, e a diferença é o desenho inteiro:

| passo | quando | o que garante |
|---|---|---|
| **registrar** o evento na outbox | **dentro** da transação, antes do commit | rollback leva status, histórico, avisos e evento juntos — nunca sobra um sem o outro |
| **publicar** no stream do Redis | **depois** do commit (`on_commit`) | no fio nunca aparece um fato que a transação ainda podia desfazer |

### A divergência

*"Publicado antes do commit"*, ao pé da letra, significa **mandar o fato para o
barramento enquanto a transação ainda pode ser desfeita** — o dual-write
clássico: o consumidor reage a uma mudança de status que, um milissegundo
depois, não aconteceu. É precisamente o que o padrão outbox (INV-P6 desta casa)
existe para impedir, e é o oposto do que o §11 quer.

O que o §11 **queria** dizer, e o código cumpre: *o evento nasce dentro da mesma
transação do status — não há status mudado sem evento registrado, nem evento
registrado sem status mudado.*

### A prova de que a igualdade morde

**Mutação O** — a emissão sai do `with` e ganha uma transação própria (que é o
dual-write literal):

```
FAILED tests/test_inv_aviso_nasce_com_o_status.py::test_o_rollback_da_transacao_nao_deixa_NENHUM_aviso_orfao
FAILED tests/test_inv_outbox_transacional.py::test_status_nao_muda_se_o_evento_nao_puder_ser_emitido
2 failed, 304 passed, 4 warnings in 14.08s
```

O segundo é a metade do INV-P6 que quase ninguém escreve: não *"rollback não
deixa evento órfão"* (essa continua verde mesmo com a emissão fora do `with`),
e sim a inversa — **emissão que falha desfaz o fato**.

### Redação proposta para o §11 (não aplicada)

> *"O evento de mudança de status é **registrado na outbox dentro da mesma
> transação** que muda o status (antes do commit), e **publicado no stream
> depois do commit**. Rollback leva os dois juntos; o fio nunca vê um fato que
> a transação podia desfazer."*

---

## Item 5 — "Auditoria do estado AS-IS documentada e anexada a este spec antes da implementação"

**Veredito: PASS COM RESSALVA.** O `AUDITORIA-AS-IS.md` existe, está na mesma
pasta da spec, e foi escrito em **23/08/2026** — antes da primeira linha de
código da célula (EVO-10, PR #108). **Na letra do §11, o item está cumprido.**

A ressalva é que *"existe"* não é *"está correto"*. Conferido item a item contra
a realidade de hoje, **quatro afirmações do documento envelheceram**, e uma
delas é justamente o "maior achado" dele:

| Onde | O documento diz | A realidade de 25/08/2026 |
|---|---|---|
| **Q1** | *"7 bancos"* | **10.** `grep -c '^CREATE DATABASE' infra/provisionamento-postgres.sql` → `10` (entraram `sugestoes_db`, `identidade_db`, `admin_db`) |
| **Q2** (o "maior achado") | *"**Não existe login de usuário final em nenhuma célula**"* | **Existe.** A célula `identidade` está em `services/identidade/` e no ar desde 25/08: `entrar/google`, `entrar/google/retorno`, `entrar/sair` no `config/urls.py` dela |
| **Q2** (consequência) | *"Caminho de menor invenção: identidade por e-mail + **link mágico**"* | **Descartado pelo mantenedor** na EVO-01 (23/08): é *Entrar com Google*, porque a plataforma não manda e-mail. Lei em `DECISAO-EVO-01-identidade.md` |
| **Q4** (tabela de peças) | escrita para **8 células** | **11** em `services/`: admin, alunos, catalogo, checkout, funil, identidade, leads, mensageria, pagamentos, quiz, sugestoes |
| **Q5** | lista `sugestao.mesclada` entre os nomes de evento | **não foi congelado** — `contracts/eventos/` tem só os 4 (ver item 1.7) |

**Por que isto importa mais do que parece:** o `AUDITORIA-AS-IS.md` é citado
como insumo pela própria spec (§3 e §11) e pelo `PLANO-MESTRE.md` §5.1. Um agente
futuro que o abra para "medir o terreno" vai ler que **não existe login de aluno
na plataforma** — e essa frase, que era o achado mais importante do documento em
23/08, hoje induz ao erro oposto: fazer a célula inventar identidade quando já
existe uma célula dedicada a isso.

**Recomendação (não aplicada — o arquivo está fora dos alvos deste despacho):**
o `AUDITORIA-AS-IS.md` merece uma tarja no topo, no mesmo espírito da correção de
24/08 que ele já carrega na Q4 — *"este é o retrato de 23/08/2026; a plataforma
mudou desde então: veja a tabela em `AUDITORIA-MVP.md` item 5"*. Auditoria é
fotografia com data; o erro não é envelhecer, é envelhecer sem dizer a data.

---

## O que a auditoria NÃO cobre, dito alto

- **Nada aqui foi medido em produção.** Todos os vereditos são sobre o código de
  `origin/main` e a suíte local. A prova de fora (a Caixa respondendo em
  `meshcraft.top/forms/sugestoes/`) é outro instrumento, e é do maestro.
- **A trava do ChangeSpec nunca foi exercitada com uma aprovação real**, porque
  não há nenhum ChangeSpec real (ver `docs/changespecs/README.md`). O que está
  provado é a mecânica; o que falta é a primeira volta completa com gente.
- **Merge de sugestão continua sem existir**, e é V1.1 — item 1.7.
