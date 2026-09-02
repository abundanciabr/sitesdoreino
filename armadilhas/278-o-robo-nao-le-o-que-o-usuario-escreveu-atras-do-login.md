---
schema_version: 2
armadilha: 278
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: Nenhum portao impede um robo de pedir copia manual ao mantenedor, e nenhum teste afirma 'existe tela de exportar para este conteudo' sem virar uma lista a mao de todo conteudo do site (a Classe 8 do PLANO-MESTRE). O que existe e o habito: faltando o conteudo, construa a porta de saida em vez de pedir a copia.
sinal:
  - '302\s+https://meshcraft\.top/(admin|forms)/'
  - 'Location: /forms/sugestoes/entrar'
---

# Pediram para analisar o que os usuários escreveram, e o robô não enxerga uma linha

**Sintoma.** O mantenedor pede algo como *"analise as sugestões que os alunos
mandaram"*, *"veja as dúvidas do fórum"*, *"me diga o que a turma está pedindo"*.
Você vai buscar o conteúdo e não acha em lugar nenhum. No repositório só existe a
semente (que cria categorias, nunca texto de gente). Em produção, toda porta
devolve a mesma coisa:

```
302  https://meshcraft.top/forms/sugestoes/
302  https://meshcraft.top/admin/caixa/
```

**Causa.** Não é permissão faltando, e não adianta insistir: **é o desenho**.
Todo texto escrito por uma pessoa nesta plataforma mora atrás de um login, e o
agente não tem sessão de ninguém. Ele alcança o que é público, o que é máquina
(com token, e o token mora no env da VPS) e o que está versionado. Conteúdo de
gente não é nenhum dos três.

O que o agente CONSEGUE ver é a contagem, quando existe um caminho de máquina
para ela. Foi assim que uma sessão de 31/08/2026 soube que sobravam 2 ideias na
Caixa sem conseguir dizer o que estava escrito nelas (registro `20260831-002`,
na frase dela: *"eu enxergo a contagem, não o conteúdo"*).

**O erro que essa parede convida.** As duas saídas fáceis são ruins:

1. **Pedir a cópia tela por tela.** "Abra a ideia 1, copie, abra a ideia 2,
   copie..." Custa minutos do mantenedor a cada vez que a pergunta voltar, e
   ela volta.
2. **Um bloco de colar no terminal da VPS** que imprime tudo. Funciona uma vez,
   põe o leigo no terminal por um trabalho de leitura, e não deixa nada de pé:
   na semana seguinte é o mesmo bloco outra vez.

Um workflow que imprima o conteúdo no log do Actions é **pior que as duas**: o
repositório é público de propósito, e o log e os artefatos também são. Texto que
o aluno escreveu num lugar com login não pode sair por ali.

**Solução: construa a porta de saída, uma vez.** Uma tela na área do dono que
monte o conteúdo inteiro em texto corrido, num campo único, para ele selecionar
e colar onde quiser. O gesto dele passa a ser três teclas, para sempre, e
funciona para qualquer destino (uma conversa com uma IA, um documento, um
e-mail). O caso desta entrada: `/admin/caixa/exportar/`, aba 5 da Caixa de
Sugestões, PR #850.

Três detalhes que o caso ensinou, e que valem para a próxima tela dessas:

- **Tire o nome de quem escreveu.** Nas telas de operação o nome fica, e deve.
  Numa tela de EXPORTAR ele não fica: o texto foi feito para deixar a área
  administrativa, e a análise funciona sem saber de quem é. O que não precisa
  viajar não viaja.
- **Sem JavaScript.** A porta do Admin manda `script-src 'self'` e a célula não
  serve estático nenhum, então um botão "copiar" custaria um arquivo servido e
  uma exceção na política. Um `<textarea readonly>` faz o mesmo: clicar dentro e
  apertar Ctrl+A seleciona só o conteúdo dele, nunca a página em volta
  (`armadilhas/199` conta o que acontece quando se briga com essa política).
- **O texto que sai declara o que NÃO saiu.** Quem receber, do outro lado, não
  tem como adivinhar que a contagem de comentários veio sem o texto dos
  comentários. Análise que não sabe o que falta inventa o que falta.

**A fronteira que sobra, e é honesta.** O que o contrato entre as células não
promete continua fora do alcance da tela: no caso da Caixa, o texto dos
comentários (`contracts/sugestoes.openapi.yaml` entrega `comentarios` como
número). Trazê-lo é RITOS.md §3, uma conversa com o mantenedor, não uma linha de
código. Registre a lacuna em vez de contorná-la em silêncio.
