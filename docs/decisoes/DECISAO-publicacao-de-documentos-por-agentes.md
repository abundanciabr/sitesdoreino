# Decisão: publicação de documentos por agentes

**Data:** 23/09/2026. **Decidiu:** mantenedor, nesta sessão.

O mantenedor determinou remover a exigência de que o robô publique páginas
somente pelo editor. Ela impediria agentes sem navegador autenticado de criar
documentos para o site.

Regra expressa do mantenedor: "TUDO AQUI É FEITO POR ROBÔS, E SE ELES NÃO
PUDEREM FAZER QUEM FARÁ?" O custo da assinatura torna especialmente importante
que um robô não devolva ao mantenedor trabalho executável apenas porque um
caminho ou uma ferramenta falhou. Ele procura outro caminho autorizado e
responde pela entrega completa. Decisões destrutivas, caras ou exclusivas do
mantenedor continuam seguindo a regra 4 do Padrão de Trabalho.

Pessoas usam o sistema para criar e gerir conteúdo. Robôs executam o trabalho
mais complexo e precisam de um caminho de escrita para produzir esse conteúdo
sem depender de uma pessoa operar a tela por eles.

O resultado exigido é o documento gravado no banco e a URL pública conferida.
O agente pode usar o editor autenticado ou, para um documento novo, a migração
própria descrita em `armadilhas/347`. Arquivo isolado, PR aberto, merge e deploy
sem conferência da URL não provam publicação.

Esta decisão altera o caminho de execução do agente. O editor continua sendo
a tela de gestão e edição do mantenedor. A migração existente não sobrescreve
documento já criado no banco.
