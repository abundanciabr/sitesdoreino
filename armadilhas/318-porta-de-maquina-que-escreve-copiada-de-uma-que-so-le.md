---
schema_version: 2
armadilha: 318
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o portão que existiria teria de saber que uma operação POST é "escrita perigosa", e nenhum sinal mecânico separa isso de um POST de busca paginada. O que segura é o teste de 403 do par que só lê, e ele só existe se quem escreve a porta souber que precisa dele. Enquanto isso, a pergunta de dez segundos abaixo responde
sinal:
  - "TOKENS_ACEITOS"
  - "conjunto plano"
  - "grau a mais"
---

# Porta de máquina que ESCREVE, copiada de uma que só lê, nasce com um conjunto de token plano

**Sintoma.** Não há sintoma. É o ponto.

A porta nova passa em todo teste de 401, o `make ci` fica verde, a muralha
aprova, e a porta é copiada exatamente como Lei 3 manda: `bearerAuth` lendo
`settings.TOKENS_ACEITOS`, que é o conjunto montado de `TOKENS_ACEITOS_<PAR>`.
Ela também tem uma operação que grava alguma coisa séria. E **todo par
consumidor que tem o token para ler tem o token para gravar**, porque o conjunto
é um só.

Ninguém percebe porque o modo de falha exige duas coisas ao mesmo tempo: uma
segunda célula pedindo o token para uma tarefa inocente, e alguém decidindo usar
o poder que ela ganhou de graça.

**Causa.** As dez células que já tinham porta de máquina quando esta nasceu são,
quase todas, portas de LEITURA — o fórum devolve tópico, a gamificação devolve
nível, o catálogo devolve produto. Nelas o conjunto plano está certo: quem
entra, lê, e ler é tudo que há para fazer. O padrão que se copia é esse, e ele
não carrega o aviso, porque no lugar de onde foi copiado não havia o que avisar.

Quem escreve a porta seguinte copia o padrão inteiro, corretamente, e leva junto
a premissa invisível de que "entrar" e "poder tudo" são a mesma coisa.

**Solução, e ela já existia na casa.** A `identidade` resolveu isto antes de
qualquer plano: `TOKENS_COMPLETOS_*` decide quem pode ver e-mail, e
`TOKENS_SENHA_*` decide quem pode gravar senha. São graus PRÓPRIOS, conferidos
no handler, não segundo *security scheme* no contrato — um 403 nomeado explica
melhor e não dobra a superfície congelada.

A pergunta de dez segundos, antes de escrever a primeira linha de uma porta:

> **Esta porta tem alguma operação que MUDA alguma coisa? Se tiver, o par que
> só precisa desenhar uma tela de consulta pode executá-la?**

Se a resposta for sim, o conjunto precisa ser dois:

```python
# settings.py — dois conjuntos, os dois fail-closed
TOKENS_SOMENTE_LEITURA = {v for k, v in os.environ.items()
                          if k.startswith("TOKENS_SOMENTE_LEITURA_") and v}
TOKENS_PUBLICACAO = {v for k, v in os.environ.items()
                     if k.startswith("TOKENS_PUBLICACAO_") and v}

# auth.py — o Bearer aceita os DOIS: quem publica também lê
def authenticate(self, request, token):
    if token in tokens_de_leitura() or token in tokens_de_publicacao():
        return token
    return None

# o handler que escreve — 403, e não 401: o crachá é válido, falta o grau
if request.auth not in tokens_de_publicacao():
    raise HttpError(403, "este par nao tem o grau de publicacao")
```

**O detalhe que a `identidade` faz diferente, e por que aqui foi mudado.** Lá o
par precisa estar nos DOIS envs: `TOKENS_SENHA_ADMIN` não dispensa
`TOKENS_ACEITOS_ADMIN`. Isso tem um modo de falha chato e silencioso do lado do
mantenedor: ele põe a senha de publicação no arquivo de env, a tela lê tudo
certo, e a primeira tentativa de salvar devolve 403 sem nada estar errado no
código. Nenhum log acusa, porque nada falhou. Fazer o grau alto CONTER a leitura
custa uma linha e apaga esse dia inteiro.

**E o teste que prova, porque sem ele isto é só uma boa intenção.** O guarda de
401 não vê nada disto: ele testa a AUSÊNCIA de crachá, e o par que só lê tem
crachá. O teste que morde é outro, e é uma linha:

```python
def test_quem_so_le_leva_403_ao_tentar_publicar():
    resposta = postar("/…", {…}, token=TOKEN_SO_LEITURA)
    assert resposta.status_code == 403
```

Prove-o por mutação: troque `if request.auth not in tokens_de_publicacao()` por
`if False` e confira que ESTE teste fica vermelho. Se ele continuar verde, o
grau a mais não existe — existe só o comentário dizendo que existe.

**Origem:** TAR-137 (porta de máquina da `mensageria`, degrau 6c do
`PLANO-SEQUENCIAS-DE-MENSAGENS.md`), 04/09/2026. A porta expõe quatro leituras e
uma escrita, e a escrita PUBLICA a versão de uma sequência que manda mensagem
para alunos de verdade. Parente de `armadilhas/228` e `armadilhas/311`: as três
são a mesma família — **o padrão que se copia entre células carrega as premissas
da célula de origem, e elas não vêm escritas.**
