---
schema_version: 2
armadilha: 72
estado: documentada
degrau: 6
confianca: baixa
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `corrompe em silencio — nao ha erro na saida para o sino reconhecer, e um sed sem ancora e indistinguivel de um sed legitimo antes de rodar, entao a muralha so produziria falso positivo. Buraco assumido, nao esquecido.`
sinal: null
---

# Substituição em massa de `§3.1` também casa dentro de `§3.13`, `§3.16`, `§3.19`

**Sintoma:** um `sed`/`re.sub` que renomeia referências a seções numeradas
(`ARMADILHAS §3.1` → `RESOLVIDAS.md §3.1`) sai reescrevendo **outras** seções junto:
`ARMADILHAS.md §3.13` vira `RESOLVIDAS.md §3.13`, `§3.16` vira `RESOLVIDAS.md §3.16`.
Nada falha, nada avisa — o resultado é um lote de referências apontando para o
arquivo errado, e o erro só aparece quando um agente futuro abre o link e não acha
nada. Medido em 23/08/2026: 11 linhas erradas em 6 arquivos, numa passada só.
**Causa:** `§3.1` é **prefixo** de `§3.10`…`§3.19`. Sem fronteira à direita, a regex
casa o prefixo e deixa o resto do número pendurado no texto de saída. O mesmo vale
para `§5.1` × `§5.11`…`§5.15`, `§1` × `§1.x`, `§9` × `§9.x`. Ordenar as regras da
mais longa para a mais curta **não resolve** — o problema não é a ordem, é a falta de
fronteira: `§3.13` não contém `§3.10`, mas contém `§3.1`.
**Solução:** fronteira explícita à direita, que barre um dígito **e** um `.`+dígito,
mas continue permitindo o ponto final de frase:

```python
FRONTEIRA = r"(?![0-9])(?!\.[0-9])"
re.sub(rf"ARMADILHAS §{re.escape('3.1')}{FRONTEIRA}", "…", texto)
```

E **confira o de-para antes de aceitar**: imprima cada linha `antes → depois` e leia.
Foi lendo a lista que os 11 falsos-positivos apareceram; nenhum teste os pegaria,
porque texto errado continua sendo texto válido.
**Como desfazer sem `git checkout --`** (útil quando a ferramenta bloqueia comandos
destrutivos, e obrigatório quando há trabalho novo não commitado que não pode ser
perdido): restaure só os arquivos rastreados que a passada tocou, lendo o blob:

```python
blob = subprocess.run(["git","show",f"HEAD:{p}"],capture_output=True,check=True).stdout
Path(p).write_bytes(blob)
```

Com `core.autocrlf=true` o working tree fica em LF e o `git status` continua
mostrando `M` por causa do stat cache — mas `git diff --numstat` sai **vazio**, e é
ele que diz a verdade sobre o conteúdo.
**Origem:** despacho docs/armadilhas-particionado (23/08/2026), ao migrar as
referências cruzadas do `ARMADILHAS.md` particionado.
