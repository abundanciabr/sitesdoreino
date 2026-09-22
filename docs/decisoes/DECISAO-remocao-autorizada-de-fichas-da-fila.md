# Remoção autorizada de fichas e eventos específicos da fila

Decisão expressa do mantenedor em 21/09/2026. Esta decisão substitui a regra
append-only de `fila/LEIA-ME.md` apenas para as TARs abaixo e não cria uma
regra geral de remoção.

## Escopo

Depois de o backup desta decisão estar integrado, a remoção física em PR
separado elimina as fichas e todos os eventos de:

`TAR-153`, `TAR-359`, `TAR-398`, `TAR-399`, `TAR-400`, `TAR-401`, `TAR-450`,
`TAR-457`, `TAR-488`, `TAR-494`, `TAR-496`, `TAR-498`, `TAR-516`, `TAR-517`,
`TAR-518`, `TAR-554`, `TAR-555`, `TAR-569`, `TAR-578`, `TAR-586`, `TAR-587`,
`TAR-588`, `TAR-589`, `TAR-590` e `TAR-601`.

Referências históricas a esses identificadores em decisões, consultas e livro
de ocorrências permanecem. Elas descrevem fatos já acontecidos e não são
dependências da fila calculada.

## Backup verificável

O arquivo `fila/backups/20260922-fichas-e-eventos-tars-autorizadas.zip` guarda
as 25 fichas e os 27 eventos canônicos, produzidos da revisão
`441d1d8030f89a7aa2da4c8f643660ddb4706804` antes da remoção.

SHA-256:

`22eabed833f6b14946802abed98634d098a90ea55ddc33e7206971b6236249e7`

Confira o arquivo com:

```powershell
(Get-FileHash fila/backups/20260922-fichas-e-eventos-tars-autorizadas.zip -Algorithm SHA256).Hash.ToLower()
tar -tf fila/backups/20260922-fichas-e-eventos-tars-autorizadas.zip
```

O primeiro comando precisa devolver o SHA-256 acima. O segundo precisa listar
52 arquivos de conteúdo, todos sob `fila-remocao-autorizada-20260922/fila/`.

## Limite e reversão

Esta autorização só vale para os caminhos de `fila/tarefas/` e
`fila/eventos/` pertencentes às 25 TARs listadas. Não autoriza editar nem
eliminar fatos históricos fora desses caminhos. A recuperação é uma nova
mudança que extrai os arquivos do backup e passa novamente pela validação da
fila; ela não altera o backup nem esta decisão.
