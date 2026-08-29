# O número do servidor vem no dia UTC, e você nomeia o arquivo no dia daqui

**Sintoma:** você pede o número atômico do próximo registro, ele devolve `001`
num dia em que já existem dezenas de registros, e o arquivo que você cria
**colide com um que já existe**:

```
$ python ci/reservar.py numero registro
001
$ ls painel/registros/ | grep 20260828-001
20260828-001-o-painel-passou-a-explicar-o-proprio-defeito.js   ⟵ já existe!
```

Medido em 28/08/2026, às 21h03 no relógio do mantenedor — **00h03 de 29/08 em
UTC**.

**Causa:** o almoxarife (`ci/reservar.py`) numera por dia **UTC**, que é o
relógio do servidor onde a reserva é atômica. Você, olhando a pasta e o próprio
relógio, nomeia o arquivo com a data **local**. Entre 21h e 24h em Brasília, as
duas datas são diferentes — e aí o número certo do dia seguinte vira número
repetido do dia de hoje. O gerador reprova (a trava de id repetido funciona),
mas a leitura natural do erro é "o allocator está quebrado", e não está.

**Solução:** use a MESMA data que o allocator usou — a de UTC:

```bash
N=$(python ci/reservar.py numero registro)
DIA=$(python -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d'))")
# arquivo: painel/registros/$DIA-$N-slug.js   (e o campo `arquivo` igual)
```

O campo `quando` continua sendo a data do FATO no relógio de quem viveu o fato —
um registro de 29/08 (UTC) contando algo que aconteceu às 21h de 28/08 está
correto, e o gerador aceita: a data do nome é **identidade**, não cronologia. A
gaveta do mês também sai do nome, então nada muda de lugar por causa disso.

**Origem:** Onda 3 do `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`, PR #436.
