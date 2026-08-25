# Variável some do env quando o provisionamento da célula roda de novo

**Sintoma:** uma variável que já estava funcionando em `/opt/plataforma/env/<celula>.env`
simplesmente **não está mais lá** depois que alguém re-executou o script de
provisionamento daquela célula. Nada acusa: o container sobe, o deploy fica verde, e o
que a variável ligava some — a Caixa volta a "ninguém aprova", ou o login para de ser
reconhecido. Quanto mais fail-closed for a variável, mais silencioso é o estrago:
fail-closed **por falta de valor** é indistinguível de fail-closed **por decisão**.

**Causa:** há duas famílias de script tocando o mesmo arquivo, e elas não se conhecem:

| Família | O que faz | Exemplo |
|---|---|---|
| **cria** | `cat > env/<celula>.env <<ENV … ENV` — escreve o arquivo INTEIRO a partir de um heredoc que é o molde congelado no dia em que foi escrito | `infra/provisionar-sugestoes.sh`, `infra/provisionar-identidade.sh` |
| **acrescenta** | `>>` ou `sed -i` numa chave só, preservando o resto | `infra/provisionar-aprovadores.sh` |

Tudo que a família "acrescenta" pôs no arquivo depois é **apagado** pela próxima execução
da família "cria" — porque o heredoc dela não tem essas chaves. E a família "cria" é
idempotente *por desenho* ("rodar de novo é seguro"), o que convida a rodá-la de novo.

O projeto já sabia disso — em comentário, dentro do próprio heredoc:

> `# O molde é infra/env/sugestoes.env.exemplo — se aquele arquivo ganhar variável nova,`
> `# esta função precisa ganhar junto, senão a célula sobe sem ela.`

É **garantia sem mecanismo** (RETROSPECTIVA-FASE-D, padrão 2): um comentário pedindo
que dois arquivos sejam editados juntos, sem nada que meça se foram. Em 25/08/2026 a
divergência já existia e ninguém tinha visto — três chaves do molde faltavam no gerador,
duas delas do login que estava no ar havia horas.

**Como medir, em um comando** (o molde menos o heredoc; saída vazia = convergidos):

```bash
comm -23 \
  <(grep -oE '^[A-Z_]+=' infra/env/sugestoes.env.exemplo | tr -d '=' | sort -u) \
  <(sed -n '/^cat > env\/sugestoes.env/,/^ENV$/p' infra/provisionar-sugestoes.sh \
     | grep -oE '^[A-Z_]+=' | tr -d '=' | sort -u)
```

Medido em 25/08/2026, `sugestoes`:

```
IDENTIDADE_API_TOKEN
IDENTIDADE_API_URL
SUGESTOES_APROVADORES
```

As duas primeiras são o login da célula (`provisionar-identidade.sh` as acrescenta
DEPOIS, com `>>`); a terceira é a lista de aprovadores. Re-rodar o provisionamento da
Caixa hoje **fecharia a Caixa** — o próprio `sugestoes.env.exemplo` diz que sem
`IDENTIDADE_API_*` ela responde a tela de indisponibilidade.

**Solução — três, em ordem de força:**

1. **Não escreva o arquivo inteiro se ele já existe.** Um script que apenas ACRESCENTA
   nunca cria este problema. Escrever por heredoc só se justifica quando o script está
   *gerando* segredos (chave do Django, senha do banco) — e nesse caso ele é, por
   definição, a primeira coisa que roda naquela célula. Se o env já está vivo,
   reescrevê-lo rotaciona segredos em uso e derruba as sessões de todo mundo, o que é
   pior do que a chave que some.
2. **Deixe a re-execução ser barata de consertar** e diga isso no lugar onde a pessoa
   vai olhar: uma nota no `.env.exemplo` e no cabeçalho do script "acrescenta", com o
   nome do script que reconstrói o que se perdeu. Idempotência é o que torna a cura
   uma linha.
3. **Mecanize o comando acima** num guarda, se a família "cria" for crescer. Enquanto
   houver dois scripts com `cat > env/`, o comentário é a única coisa segurando — e
   comentário não reprova PR nenhum.

**✅ FECHADO no mesmo dia, pela segunda das duas saídas.** A opção "quem escreve tudo
passa a ler o que existe" foi descartada com motivo: o script teria de **adivinhar** valor
que não é dele — o token do par `sugestoes↔identidade` pertence ao
`provisionar-identidade.sh`. Adivinhar seria trocar um estrago silencioso por outro. Ficou
a opção de **medir a divergência e parar**:

* cada script que reescreve env inteiro ganhou uma **trava de deriva** — antes do `cat >`,
  compara as chaves do arquivo vivo com uma lista `CHAVES_QUE_EU_GERO` e imprime
  `PAROU POR SEGURANÇA` com **a lista nominal do que seria apagado**, dizendo qual script
  é dono de cada chave órfã. Sai 1, e nada é alterado;
* a trava entrou nos **dois** scripts da família "cria", não só no flagrado — o
  `identidade.env` ainda não divergiu, e esperar ele divergir seria aguardar um incidente
  cujo mecanismo já se conhece;
* e a lista, que é cópia consciente do heredoc (o script roda na VPS, sem Python e sem o
  repositório), ganhou guarda próprio: `ci/tests/test_provisionamento_nao_perde_variavel.py`
  lê os dois arquivos e reprova se divergirem, se a trava sumir, ou se o script escrever
  chave que o molde não documenta. Provado por mutação nos dois sentidos.
* o cabeçalho que dizia "IDEMPOTENTE: rodar de novo é seguro" foi corrigido: a promessa
  agora vem com a ressalva e com o aviso de que re-rodar **rotaciona a chave do Django**
  (todo mundo deslogado) e a senha do banco.

**A regra que generaliza:** quando dois escritores dividem um arquivo e um deles escreve
o arquivo *inteiro*, o outro está sempre a uma execução de ser apagado. Ou o que escreve
tudo passa a ler o que existe, ou alguém mede a divergência — comentário pedindo
disciplina não é nenhum dos dois.

**Origem:** despacho da lista de aprovadores da Caixa, 25/08/2026
(`infra/provisionar-aprovadores.sh`). A divergência foi encontrada ao conferir se a
chave nova precisaria entrar também no gerador; as duas chaves do login apareceram de
brinde, e não eram conhecidas.
