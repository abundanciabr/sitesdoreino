#!/bin/sh
# Execute only as the maintainer in the administrative hosting console.
set -eu
umask 077
[ "$(id -u)" -eq 0 ] || { printf "%s\n" "Use o console administrativo da hospedagem." >&2; exit 1; }
stage='/opt/plataforma/appmax-clones/checkout-roblox-20261009/entrega-autorizada/c7e1e884cc17df19fe7de058707f7c0f1c5fe53b'
base='https://raw.githubusercontent.com/abundanciabr/sitesdoreino/c7e1e884cc17df19fe7de058707f7c0f1c5fe53b'
mkdir -p "$stage/infra/appmax_checkout_teste" "$stage/services/checkout_appmax/assets"
download() {
  curl -fsSL --connect-timeout 10 --max-time 45 "$base/$1" -o "$stage/$1"
  printf "%s  %s\n" "$2" "$stage/$1" | sha256sum -c - >/dev/null
}
download 'infra/appmax_checkout_teste/preparar_publicacao_rota.py' 'cafa02367a40be4cda838557d0338a395026d71ff9b9ecb4f315b73e342e947e'
download 'infra/appmax_checkout_teste/aplicar_referencia_rota_root.py' 'f97bf27924ce924e2ca3fb32ab890ba7887ec7b2843472329c4f66b58b28bf08'
download 'infra/appmax_checkout_teste/publicar_rota_autorizada.py' '59f479f9eed45b079483eb54ae41f076d97a4b482da2d0d005a824679257a0a7'
download 'services/checkout_appmax/server.py' '8573c33f26d3baef60a8774fb4c473290addad065d9b783f5cfdebebbf18a031'
download 'services/checkout_appmax/wrapper.py' 'aea3d9cd74d18dfd832a503d72a06e23ee9fb677a5a0c70f29c6f4195092e641'
download 'services/checkout_appmax/worker.py' '2305e6cc9f491c8e44922d8a3cc990ca4c7731f2553c601f06a97b99ae9ea189'
download 'services/checkout_appmax/assets/checkout.html' 'f629df544dc81c9d6352b569440d6d2a794019c0f7233f3c466a6d7aff77ae73'
download 'services/checkout_appmax/assets/checkout.css' 'fe2cc014247d8283c5e402c7bbfe86d40299c64c15de0b8de62abfd3d5caf783'
download 'services/checkout_appmax/assets/checkout.js' 'f705794dd66ecf5b077c06702b151b386aa7f1ee394549f539dd776497934cb8'
exec python3 "$stage/infra/appmax_checkout_teste/publicar_rota_autorizada.py"
