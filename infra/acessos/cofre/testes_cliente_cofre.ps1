# Teste local do transporte binário, sem SSH/VPS, chaves ou backups reais.
$ErrorActionPreference = 'Stop'
$cliente = Join-Path $PSScriptRoot 'puxar-cofre-restrito.ps1'
$erros = $null
$tokens = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($cliente, [ref]$tokens, [ref]$erros)
if ($erros.Count) { throw "cliente PowerShell inválido: $($erros[0].Message)" }
$funcao = $ast.Find({ param($no) $no -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
  $no.Name -eq 'Baixar-Cofre' }, $true)
if (-not $funcao) { throw 'função de transporte ausente' }
. ([scriptblock]::Create($funcao.Extent.Text))
$temporario = Join-Path ([System.IO.Path]::GetTempPath()) ('cofre teste - ' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory $temporario | Out-Null
try {
  $ssh = Join-Path $temporario 'ssh-ficticio.exe'
  $Vps = 'alias-ficticio'
  $utf8 = [System.Text.UTF8Encoding]::new($false)
  $codigo = @'
using System;
using System.Text;
public class SshFicticio {
  public static int Main(string[] args) {
    string entrada = Console.In.ReadToEnd();
    if (args.Length != 6 || args[0] != "-o" || args[1] != "BatchMode=yes" ||
        args[2] != "alias-ficticio" || args[3] != "cofre" ||
        args[4] != "fetch" || args[5] != "backups-de-banco" ||
        entrada != "YWJj\nZGVm\n") return 7;
    byte[] bytes = new byte[] { 0, 255, 254, 128, 10, 13, 0, 65 };
    Console.OpenStandardOutput().Write(bytes, 0, bytes.Length);
    return 0;
  }
}
'@
  Add-Type -TypeDefinition $codigo -OutputAssembly $ssh -OutputType ConsoleApplication
  $saida = Join-Path $temporario 'marcador.bin'
  Baixar-Cofre 'fetch' 'backups-de-banco' $saida @('YWJj', 'ZGVm')
  $esperado = [byte[]](0, 255, 254, 128, 10, 13, 0, 65)
  $recebido = [System.IO.File]::ReadAllBytes($saida)
  if (-not [System.Linq.Enumerable]::SequenceEqual([byte[]]$recebido, [byte[]]$esperado)) {
    throw 'bytes binários alterados'
  }
  $recusado = $false
  try { Baixar-Cofre 'fetch' 'backups-de-banco' (Join-Path $temporario 'falha.bin') @('nome-invalido') }
  catch { $recusado = $true }
  if (-not $recusado) { throw 'falha do SSH foi ignorada' }
  Write-Output 'Transporte binário local: OK; entrada tipada e falha do SSH: OK'
} finally {
  Remove-Item -LiteralPath $temporario -Recurse -Force -ErrorAction SilentlyContinue
}
