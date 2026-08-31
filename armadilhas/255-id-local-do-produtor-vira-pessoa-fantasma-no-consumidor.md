---
schema_version: 2
armadilha: 255
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/gamificacao/tests/test_interruptores.py
sinal:
  - `autor_da_sugestao_id`
  - id opaco da identidade dentro da celula
---

# O id que o produtor manda é LOCAL dele, e creditar por ele cria uma pessoa fantasma

**Sintoma.** Um consumidor lê um evento, credita alguém, e **nada dá errado**: o
ledger enche, o log fica limpo, os testes passam. Mas a tela da pessoa que
trabalhou continua marcando zero, para sempre. Não há erro para procurar, não há
exceção, não há linha vermelha em lugar nenhum — só um número que não sobe.

**Causa.** O evento carrega DOIS tipos de identificador de pessoa, e eles se
parecem muito:

| campo | o que é | serve para creditar fora da célula? |
|---|---|---|
| `data.autor_id`, `data.autor_da_sugestao_id` | id opaco **local da célula que emitiu** | **não** |
| `ator_id` (no envelope) | id da **plataforma**, o único que atravessa | sim |

Nesta casa a `sugestoes` guarda os dois lado a lado — `Identidade.id` (local) e
`Identidade.id_da_plataforma` ([INV-SUG11]) — e eles são **cunhados
separadamente para a mesma pessoa**. O contrato de cada evento diz isso com
todas as letras (*"id opaco da identidade DENTRO da celula sugestoes"*), mas a
frase é fácil de ler por cima, porque o campo se chama `autor_id` e é
exatamente o que se procura.

Como o consumidor chaveia o perfil pelo id de plataforma, creditar o id local
faz `get_or_create` **criar uma pessoa nova** — uma que nenhuma sessão jamais vai
resolver. Daí o silêncio: do ponto de vista do banco, está tudo certo.

**Por que os testes não pegam.** Porque quem escreve o teste monta o envelope
imaginando o campo que gostaria de ter. Aqui a suíte da `gamificacao` montava
`ator_id` no envelope de `sugestao.criada.v1` — um campo que o contrato
**proibia** (`additionalProperties: false`). A suíte media uma forma que a
produção nunca enviava, e o próprio cabeçalho do arquivo já advertia contra
isso, com estas palavras: *"um teste com envelope de fantasia provaria que o
motor funciona com dados que nunca vão chegar"*. A advertência estava escrita e
mesmo assim não impediu — porque ninguém compara o envelope do teste com o
schema congelado.

**Solução, em três partes.**

1. **Fail-closed no consumidor.** Só id de plataforma credita; ausente devolve
   `None` e o crédito não acontece, com o motivo no log. Nada de `or` caindo no
   campo local — é o `or` que parece tolerância e é o bug:

   ```python
   # ERRADO: o segundo caminho credita um fantasma, em silêncio
   return envelope.get("ator_id") or data.get("autor_id")
   # CERTO: não sei de quem é ⇒ não pago, e digo por quê no log
   return envelope.get("ator_id") or None
   ```

2. **O produtor manda o crachá da plataforma, e ele é OPCIONAL.** Obrigatório
   não dá: o `id_da_plataforma` é `null=True` por decisão da célula que o guarda
   (*"nada disto pode recusar ninguém"*), e o evento nasce dentro da transação do
   fato ([INV-P6]) — exigir o campo faria **o fato falhar** para quem ainda não
   tem o id. Campo novo opcional é a via retrocompatível que o RITOS §3.3
   prescreve, e dispensa `*.v2.json`.

3. **Omitir a chave, nunca mandar `null`.** O relay faz
   `envelope.update(envelope_extra)`; um `None` viaja como `ator_id: null` e o
   contrato declara `type: string`. Ausente é o que "não sei" quer dizer.

**Como medir que está curado** (sem rede, e é a prova que vale): monte o
envelope **exatamente como o contrato permite** — sem o campo novo — e afirme que
ninguém foi creditado E que nenhuma pessoa nasceu:

```python
envelope = _envelope()
del envelope["ator_id"]           # a forma que o contrato v1 permitia
assert aplicar(envelope, SITE) == []
assert not PerfilJogador.objects.exists(), "nenhuma Pessoa fantasma nasceu"
```

Com o `or data.get("autor_id")` de volta, isso fica vermelho na asserção:
`Left contains one more item: <LancamentoDeXP: +10 sugestao-criada …>`.

**A regra de bolso que fica.** Antes de creditar, endereçar ou casar alguém a
partir de um evento de outra célula, **leia a `description` do campo no contrato
congelado**, não o nome dele. Se a frase disser "dentro da célula X", aquele id
não serve para nada fora da célula X — e o dia em que você o usar mesmo assim
não vai produzir erro nenhum, que é justamente o problema.

Irmã de `armadilhas/195` (vermelho na asserção, não na exceção) e do padrão
*falso-verde* da `docs/decisoes/RETROSPECTIVA-FASE-D.md`.
