---
schema_version: 2
armadilha: 240
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: o teste que executa o script cobre os dois cenários separadamente (catálogo mudo e catálogo com zero resultados) e exige mensagens diferentes; o padrão em si não tem varredor, porque `cmd | grep` é legítimo em quase todo outro uso
sinal:
  - 'PAROU POR SEGURANÇA: não consegui perguntar'
---

# `descobrir | grep` diz "não consegui perguntar" quando a resposta foi "não há nenhum"

**Sintoma.** Um script de provisionamento para com a tela errada. O mantenedor lê
"não consegui perguntar ao catálogo quais sites existem" e vai conferir se o
serviço caiu, se a rede está de pé, se o container subiu. Nada disso é o
problema: o catálogo respondeu na hora, e o que ele disse foi que **não há
nenhum site ativo**. As duas telas mandam olhar lugares diferentes, e uma delas
manda olhar o lugar errado.

**Causa.** O idioma é o pipe único de descoberta, que aparece em todo script que
pergunta algo à plataforma e filtra a resposta:

```bash
SITES=$(docker compose exec -T catalogo python manage.py shell -c "…" \
  | grep -E '^[0-9a-fA-F-]{36}\s') \
  || parar "não consegui perguntar ao catálogo quais sites existem."
```

O exit status de um pipe é o do ÚLTIMO comando. E `grep` sai **1** quando não
casa nada, exatamente como sairia se o comando da frente tivesse morrido. As
duas causas chegam ao `||` indistinguíveis:

| o que aconteceu | exit do pipe | o que a tela diz |
|---|---|---|
| o container não respondeu | 1 (grep sem entrada) | "não consegui perguntar" ✅ |
| respondeu, e não há site ativo | 1 (grep sem casamento) | "não consegui perguntar" ❌ |

**Solução — dois passos, e a única regra é a ordem.** Guarde a resposta CRUA
primeiro, com o `||` colado no comando que pode falhar de verdade. Filtre
depois, num segundo passo que nunca derruba o script (`|| true`), e trate o
"filtrou e não sobrou nada" como o caso próprio que ele é:

```bash
BRUTO=$(docker compose exec -T catalogo python manage.py shell -c "…") \
  || parar "não consegui perguntar ao catálogo quais sites existem."

SITES=$(printf '%s\n' "$BRUTO" | grep -E '^[0-9a-fA-F-]{36}\s' || true)
QUANTOS=$(printf '%s\n' "$SITES" | grep -c . || true)
[ "${QUANTOS:-0}" -ge 1 ] || parar "o catálogo não tem NENHUM site ativo. …"
```

`set -o pipefail` **não** resolve isto: ele faz o pipe falhar quando o primeiro
comando falha, mas continua sem distinguir os dois casos quando quem falha é o
`grep` do fim.

**Por que vale a linha a mais.** O script de provisionamento é a única coisa
deste projeto que o mantenedor roda com as próprias mãos, e ele é leigo em
terminal. Uma tela que manda olhar o lugar errado gasta o recurso mais caro da
casa: o tempo dele na frente de um terminal, sem saber o que fazer com a
mensagem. Este é o mesmo espírito do "PAROU POR SEGURANÇA" ser específico, e não
um erro genérico.

**Onde já está copiado.** O idioma veio de `infra/semear-caixa.sh`, que ainda o
tem (e de lá para `semear-demo-caixa.sh` e `esvaziar-caixa.sh`). Lá o efeito é
menor porque um catálogo vazio é improvável no meio da operação, mas a tela
enganosa é a mesma. Quem for mexer num deles, conserta de passagem.

**Origem:** 31/08/2026, TAR-049 (o provisionamento da célula `gamificacao`, PR
#693). Não foi achado por leitura: o teste que EXECUTA o script montou o cenário
"catálogo sem site ativo", esperou a mensagem própria e recebeu a genérica.
Copiar um idioma de um script que funciona não copia os cenários que ele nunca
viveu.
