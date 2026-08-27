# Dublê com forma diferente da real responde a outra pergunta — e vira alarme falso

**Sintoma:** um guarda correto acusa uma violação que **não existe no código de
produção**. Em 26/08/2026 foi o guarda de privacidade da Caixa —
`test_nenhum_envelope_carrega_dado_pessoal` — reprovando com
`'@' vazou em sugestao.status-alterado` no primeiro envelope que passou a
carregar `ator_id`.

**Causa:** o dublê da célula `identidade` inventava o id de plataforma como
`f"idt-{email}"`. A `identidade` de verdade cunha `secrets.token_urlsafe(16)` —
opaco, sem nada da pessoa dentro. O e-mail no fio era **do teste**, não do
código: em produção o campo nunca conteve um `@`.

**Por que isto é perigoso e não só chato.** O caminho fácil, com a suíte
vermelha e o relógio correndo, é "consertar" o guarda: excluir `ator_id` da
varredura, ou trocar `"@" not in cru` por uma exceção. Feito isso, o guarda
continua verde para sempre — inclusive no dia em que um e-mail **de verdade**
entrar no envelope. Um alarme falso é a forma mais eficiente conhecida de
desligar um alarme bom: ele convence a próxima pessoa de que o alarme é o
problema.

**A pergunta que separa os dois casos, e ela é curta:** *o dublê tem a mesma
FORMA do real?* Se não tem, o vermelho é do dublê. Se tem, o vermelho é seu.

**Solução:** conserte o dublê, nunca o guarda.

```python
def id_da_plataforma_de(email: str) -> str:
    """Opaco, como o de verdade — e determinístico, para a mesma pessoa
    receber sempre o mesmo id (que é o que a célula real faz)."""
    return "idt-" + hashlib.sha256(email.encode("utf-8")).hexdigest()[:22]
```

Determinístico importa: vários testes dependem de a mesma pessoa reentrar e ser
reconhecida. Aleatório consertaria a forma e quebraria a identidade.

**A regra geral, que vale para todo dublê:** um dublê pode ser mais SIMPLES que
o real (menos campos, sem rede, sem latência); não pode ter FORMA diferente nos
campos que existem. Id opaco é opaco no dublê. Data em UTC é UTC no dublê.
Campo nulável é nulável no dublê — e é por isso que o dublê precisa saber
responder *sem* o campo (ver a armadilha irmã, 132).

**Sinal de alerta no diff:** dublê que constrói um valor A PARTIR de outro campo
(`f"idt-{email}"`, `f"user-{nome}"`, `email.split("@")[0]`). Toda vez que isso
aparece, o dublê acabou de acoplar dois dados que no real são independentes — e
alguma asserção vai passar ou falhar pelo motivo errado.

**Origem:** despacho da adoção do formato novo na Caixa, 26/08/2026 (PR #245),
Fase 2 do sininho.
