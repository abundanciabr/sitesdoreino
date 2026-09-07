---
schema_version: 2
armadilha: 390
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
gatilho:
  - services/admin/apps/core/porta.py
  - services/admin/config/urls.py
sinal:
  - "302 para o login"
  - "o cracha vem antes da tela"
guarda:
  tipo: nenhum
  motivo: nao ha conserto de codigo a fazer; a porta esta certa. O que muda e a FRASE que o robo escreve no livro, e isso e julgamento, nao mecanismo
licao: Um 302 em `/admin/<qualquer coisa>/` NAO prova que a rota existe: a porta e MIDDLEWARE e redireciona antes do roteamento, entao `/admin/rota-que-nao-existe-abc123/` responde 302 igual. Ele prova que a celula esta de pe. Para dizer "a tela esta no ar", cite o deploy verde mais a rota no codigo que subiu, e diga que quem abre a tela e o mantenedor.
---

# Um 302 no `/admin/` prova que a porta funciona, não que a sua tela existe

**Sintoma.** Não há sintoma, e é esse o problema. Você entrega uma tela nova do
Admin, o deploy fica verde, e escreve no livro a prova de fora:

```
prova de fora: GET https://meshcraft.top/admin/placar/fechamento/ -> 302
(o crachá vem antes da tela)
```

Parece uma medição, tem número, tem endereço, tem explicação. E **não prova
nada sobre a sua tela.**

**Medido em 07/09/2026**, com um controle que ninguém tinha feito antes:

```
/admin/placar/fechamento/               -> 302
/admin/placar/rota-que-nao-existe-abc123/ -> 302
/admin/placar/                          -> 302
```

Uma rota inventada na hora responde exatamente o mesmo que a tela recém-nascida.

**Causa.** `PortaAdministrativa` é **middleware** (`services/admin/config/settings.py`,
na lista `MIDDLEWARE`), e middleware roda **antes** da resolução de URL. Quem
não tem crachá é redirecionado sem que o Django chegue a perguntar se aquele
endereço existe. O 404 nunca acontece, porque a requisição não anda até lá.

O desenho está CERTO: fail-closed, e a porta antes de tudo é exatamente o que
se quer numa área administrativa. O que está errado é a inferência do robô, e
ela é sedutora porque o 302 realmente informa alguma coisa: que a célula está
de pé e respondendo depois do deploy. Só não informa a única coisa que a frase
diz que informa.

**A extensão, medida e não estimada:** **25 registros** de `painel/registros/`
usam essa frase como prova de fora. Nenhum deles está mentindo sobre o deploy;
todos estão dizendo mais do que mediram.

**Solução.** Para uma tela atrás da porta do Admin, a prova honesta tem três
pernas, e nenhuma delas é o 302 sozinho:

1. **O deploy verde**, lido por `gh run view <id> --json status,conclusion`
   (nunca pelo exit de um cano, `feedback_veredito_de_runs`).
2. **A rota registrada no código que subiu** — `grep` no `urls.py` do commit
   que o deploy carregou, não no seu worktree.
3. **O mantenedor abrindo a tela.** Ele tem o crachá; o robô não tem e nunca
   vai ter. Se a tela importa, peça a ele uma olhada, e o que ele disser vira
   registro com `autoridade: mantenedor`.

E escreva a frase certa: **"a célula respondeu depois do deploy"**, não "a tela
está no ar". A diferença entre as duas é tudo.

**Quando o 302 VALE:** como sonda de que a célula subiu e a porta está fechada
(que é uma medição de segurança de verdade, e boa). Comparar 405 → 302 depois
de aposentar uma rota de escrita, como a TAR-014 fez, também vale: ali a
MUDANÇA do código é observável de fora, e é a mudança que prova, não o valor.

**Primo de:** `armadilhas/271` (a tela lê ausência de dado como conclusão) e
`armadilhas/378` (o arquivo do disco lido como censo). A família é a mesma:
**um sinal fácil ocupando o lugar da medição que ninguém fez.** A diferença é
que aqui o enganado é o robô sobre o próprio trabalho.
