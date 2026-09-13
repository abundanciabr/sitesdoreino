---
schema_version: 2
armadilha: 415
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: medio
gatilho:
  - painel/registros/
guarda:
  tipo: nenhum
  motivo: "O mecanismo sabe que um registro foi respondido, mas não consegue inferir qual fato posterior fecha um alerta antigo. O vínculo continua sendo uma decisão de quem escreve o registro."
sinal:
  - "alerta âmbar antigo"
  - "problemas abertos depois do deploy"
licao: "Uma entrega verde posterior não fecha um alerta âmbar anterior por inferência. Depois de confirmar a entrega e o deploy, acrescente um registro novo com responde_a apontando para cada alerta que ele resolve. Sem esse ponteiro, a área continua cobrando trabalho já feito."
---

# Alerta antigo sem resposta continua na área

## Sintoma

A área mostra um alerta âmbar que já foi resolvido por um PR posterior. A
entrega verde existe no livro, mas o alerta continua em “Quebrado ou em alerta”.

## Causa

`painel/logica.js` calcula problemas abertos pela ausência de um registro cujo
`responde_a` aponta para o alerta. A gravidade verde da entrega prova o fato
novo, mas não declara qual alerta antigo ela encerra. Inferir esse vínculo
misturaria fatos e poderia fechar o alerta errado.

## Solução

1. Confirme o PR e o deploy pela fonte estruturada e pela evidência publicada.
2. Crie um arquivo novo em `painel/registros/` para cada alerta resolvido.
3. Use `tipo: "resposta"` e `responde_a` com o `arquivo` exato do alerta, sem
   editar o registro antigo.
4. Rode o gerador, o verificador externo e abra a área novamente.

O registro `20260908-107` fechou este caso para o alerta de tamanho do painel.
