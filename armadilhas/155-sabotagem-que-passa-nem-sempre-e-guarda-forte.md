# Sabotagem que "passa" nem sempre é guarda forte — às vezes a sabotagem não aplicou

**Sintoma:** você faz a prova por mutação (estraga o código de propósito para
ver o guarda ficar vermelho), a suíte fica **verde**, e você conclui uma de duas
coisas erradas:

- *"o guarda é fraco, vou reforçar"* — e reforça um guarda que já era bom; ou
- pior: *"o comportamento sabotado também é aceitável"* — e afrouxa o guarda.

**A terceira explicação, que quase ninguém considera: a sabotagem nunca chegou
a ser aplicada.** O `sed` não casou, o `replace` não achou a âncora, a
indentação era outra, o arquivo tinha CRLF, o acento não bateu. Aí a suíte roda
sobre o código **original** e fica verde pelo motivo mais banal do mundo.

É a família do **falso-verde** (`RETROSPECTIVA-FASE-D.md`, padrão 1) aplicada ao
próprio instrumento de prova. O verde não veio da força do guarda; veio de nada
ter mudado.

**Como aconteceu aqui (28/08/2026, célula `forum`):** duas sabotagens rodaram
juntas e as duas "passaram".

| Sabotagem | O que realmente houve |
|---|---|
| Liberar área de turma "por enquanto" | O `sed` usou 8 espaços de indentação; a linha tinha 4. **Não aplicou.** O guarda estava bom o tempo todo |
| "Não consegui conferir a matrícula" virar "é aluno" | **Aplicou de verdade** — e passou, porque **nenhum dos 39 testes chamava `quem_e()`**: todos montavam o ator à mão. O guarda do caminho de rede simplesmente não existia |

Ou seja: dos dois verdes, **um era instrumento quebrado e o outro era buraco
real**. Tratar os dois do mesmo jeito teria escondido o buraco.

**Solução — duas linhas de disciplina, e nenhuma delas é "prestar atenção":**

1. **Confira que a sabotagem existe no arquivo antes de rodar a suíte.** Em
   Python, use `assert` na âncora em vez de `sed`:
   ```python
   t = io.open(p, encoding="utf-8").read()
   assert ALVO in t, "a âncora da sabotagem não existe — o teste seria inútil"
   io.open(p, "w", encoding="utf-8").write(t.replace(ALVO, SABOTAGEM, 1))
   ```
   Um `replace` que não acha a âncora devolve o texto intacto **sem erro** —
   exatamente como o `sed`. O `assert` é o que transforma isso em falha ruidosa.

2. **Quando uma sabotagem passar, a primeira pergunta é "ela aplicou?", não "o
   guarda é fraco?".** Confirme lendo o arquivo (`grep` na linha sabotada) antes
   de mexer em qualquer teste.

**E o corolário que vale mais que os dois:** *nenhum teste chamava a função que
faz a chamada de rede.* Uma suíte com dezenas de testes verdes pode ter zero
cobertura do caminho onde mora a decisão de segurança, porque montar o objeto
pronto é mais cômodo do que exercitar a cadeia. Ao escrever guarda de
autorização, pergunte: **existe um teste que entra pela mesma porta que a
requisição real entra?** Se todos constroem o ator/usuário à mão, a resposta é
não.
