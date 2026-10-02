# Cartões históricos do placar

Os arquivos JSON desta pasta são a semente inicial das métricas. A migração `0041_placar_persistente` importa cada cartão para o banco sem sobrescrever uma edição já salva.

O site lê exclusivamente os cartões do banco. Edite metas, datas, perguntas, orientação e curva semanal em `/admin/placar/editar/`; mudar um JSON desta pasta não altera o cartão ativo. O editor usa `placar.validar` antes de salvar para que as telas continuem mostrando apenas cartões completos.

As chaves e fórmulas existentes foram preservadas na importação. A fonte que mede compras continua sendo a lista de matrículas da célula alunos; o cartão guarda a definição e a meta, enquanto o resultado é calculado na abertura da tela.
