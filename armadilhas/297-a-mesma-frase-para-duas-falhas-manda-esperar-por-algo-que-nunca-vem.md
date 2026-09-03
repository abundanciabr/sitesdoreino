---
schema_version: 2
armadilha: 297
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: services/funil/tests/test_avisos_no_celular.py
sinal:
  - `AbortError: Registration failed - push service error`
  - `Não deu certo agora. Você pode tentar de novo mais tarde.`
---

# A mesma frase para duas falhas manda a pessoa esperar por algo que nunca vem

**Sintoma:** o dono do site clica em "Ligar os avisos", a tela responde **"Não
deu certo agora. Você pode tentar de novo mais tarde."**, e mais tarde dá
exatamente no mesmo. Do lado do servidor está tudo verde: a rota responde, a
chave está configurada, o deploy passou. Não há erro em log nenhum, porque o
pedido nunca chegou ao servidor.

No console do navegador, o erro verdadeiro:

```
AbortError: Registration failed - push service error
```

**Causa:** `pushManager.subscribe()` e o `fetch` que manda a inscrição para o
nosso servidor falham por motivos de naturezas OPOSTAS, e o código tratava os
dois com um `.catch` só no fim da cadeia:

- o `subscribe` recusando é o **navegador** não conseguindo registrar o
  aparelho no serviço de push do fabricante. Nada do nosso lado muda isso, e
  nada muda sozinho com o tempo. O caso real é o **Brave**, que vem de fábrica
  com as mensagens push do Google desligadas (`brave://settings/privacy`);
- o `fetch` recusando é o **nosso** servidor não confirmando, e aí esperar é
  conselho honesto.

Um `.catch` pendurado no fim da cadeia pega os dois e apaga a diferença. O
resultado não é uma tela feia: é uma tela que **mente**, prometendo a quem usa
Brave um "mais tarde" que nunca chega. E mente em silêncio, porque a falha do
navegador não produz linha de log em servidor nenhum.

**Solução:** trate a recusa do `subscribe` no **segundo argumento do `.then`**,
que só alcança ela, e deixe o desfecho do servidor no caminho de dentro:

```js
registro.pushManager.subscribe({ ... }).then(function (inscricao) {
  // ... o POST, e aqui "nao-deu" é verdade (foi o nosso lado)
}, aparelhoNaoPode);   // <- só a recusa do navegador chega aqui
```

Duas frases no catálogo, nunca uma. A do navegador manda olhar os ajustes de
privacidade; a do servidor manda tentar mais tarde.

**Não decida pela MENSAGEM do erro.** Ela varia entre navegador e versão, não é
traduzida, e casá-la por texto é uma régua que quebra sozinha na próxima
atualização do Chromium. O LUGAR onde a promessa quebrou já diz tudo o que a
tela precisa saber.

**A lição que vale além do push:** toda vez que dois caminhos de falha
desaguam num `catch` comum, a mensagem resultante é honesta para um deles no
máximo. Vale para pagamento recusado (pelo banco ou pela nossa validação),
upload que falhou (arquivo grande demais ou disco cheio), login negado (senha
errada ou serviço fora). Se a frase diz o que fazer, ela precisa saber quem
recusou.

**Contexto:** achada em 02/09/2026 pelo próprio mantenedor, usando o site no
Brave. O diagnóstico só foi possível lendo o console do navegador dele, e essa
é a parte mais cara: sem alguém com acesso à máquina, um aluno nessa situação
simplesmente desistiria em silêncio, e o site continuaria parecendo saudável do
lado de cá.
