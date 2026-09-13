---
schema_version: 2
armadilha: 461
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: medio
gatilho:
  - services/admin/apps/core/templates/admin/_cartao_robo.html
guarda:
  tipo: nenhum
  motivo: "A correção pertence à TAR-319; o teste de renderização ainda não existe porque este PR registra o achado sem alterar o produto."
sinal:
  - "o template aplica |urlize à evidência inteira"
  - "a evidência contém entrega= ou publicacao="
  - "o href começa com http://entrega=https:// ou http://publicacao=https://"
licao: "Não aplique urlize ao par chave=https:// da evidência canônica. Preserve o texto bruto, extraia o URL e renderize o destino separado com escape seguro; o teste precisa conferir o href e o clique."
---

# `urlize` engole o rótulo da evidência estruturada

Quando a prova canônica usa `entrega=https://...` ou `publicacao=https://...`,
aplicar `urlize` ao texto inteiro transforma a chave em parte do endereço. O
Django produz `http://entrega=https://...`: a prova continua legível, mas o
atalho não abre o destino real.

A defesa é preservar a cadeia histórica e renderizar cada URL extraído em um
link separado, com escape seguro. O teste precisa usar o formato real do
reconciliador, conferir o `href` HTTPS e exercer o clique do cartão concluído.
