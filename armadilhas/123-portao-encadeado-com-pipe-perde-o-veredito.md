# Portão encadeado com `| tail` e `&&` mergeia mesmo depois de dizer "MERGE RECUSADO" — o `&&` obedece ao `tail`, não ao portão

**Sintoma:** numa linha só do tipo

```bash
python ci/mergear.py 224 --conferir 2>&1 | tail -4 && python ci/mergear.py 224 --confirmo 224
```

o primeiro comando imprime **`RESULTADO ERROR` / `MERGE RECUSADO`** e, mesmo
assim, o segundo roda e mergeia. A recusa aparece na tela e não impede nada.

**Causa:** o exit status de um pipeline é o do **último** comando — aqui, o
`tail`, que sai 0 sempre que consegue imprimir. O `exit 2` do portão é
descartado antes de o `&&` decidir. É a mesma classe do falso-verde nº 1 do
projeto (`RETROSPECTIVA-FASE-D.md` §1: *"veredito de run lido de um comando com
`| tail`"*), agora na forma de **encadeamento de portões**: não é um veredito
lido errado, é um veredito perdido no cano.

Neste caso concreto (26/08/2026) nada quebrou, e por um motivo que vale
registrar: **`ci/mergear.py --confirmo` refaz a verificação inteira por conta
própria** antes de agir, e só mergeou porque o próprio gate dele passou (os
checks tinham acabado de ficar verdes entre as duas chamadas). Ou seja: quem
salvou foi o desenho do portão, não o encadeamento. Com um portão que
confiasse na conferência anterior, o merge teria saído com ERROR na tela.

**Solução:**

1. **Nunca pendure `| tail`, `| head` ou `| grep` num comando cujo exit code vai
   decidir o próximo passo.** Se quiser encurtar a saída, rode o portão sozinho,
   deixe o exit falar, e só então filtre — ou use `set -o pipefail`.
2. **Nunca encadeie `--conferir && --confirmo` na mesma linha.** São dois atos
   com intenções diferentes: conferir é para você LER; confirmar é para agir.
   Rode um, leia o veredito, decida, rode o outro.
3. Ao construir qualquer verificador novo, mantenha o padrão do `mergear.py`:
   **quem age refaz a própria medição**, sem confiar em conferência anterior. Foi
   isso que transformou um erro de encadeamento em susto em vez de incidente.

**Origem:** auditoria da reforma dos painéis, 26/08/2026 — o PR #224 foi
mergeado logo após um `--conferir` que imprimiu `MERGE RECUSADO`. O merge era
legítimo (4 checks conferidos depois, na fonte estruturada: SUCCESS/SKIPPED
declarado), mas a linha que o disparou não tinha o direito de saber disso.
