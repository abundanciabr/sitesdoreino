"""Cliente de transporte; não oferece stdin, caminho ou comando arbitrário."""
import json
import socket


def atender_previas(args):
    if not args or args[0] != 'previas':
        return None
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(10)
            sock.connect('/run/meshcraft-previas.sock')
            sock.sendall(json.dumps(args[1:]).encode()+b'\n')
            sock.shutdown(socket.SHUT_WR)
            body = b''
            while len(body) < 1024 * 1024:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                body += chunk
            data = json.loads(body)
        print(json.dumps(data, ensure_ascii=True))
        return 2 if data.get('recusado') else 0
    except (OSError, ValueError):
        print('{"indisponivel":true,"motivo":"canal_previas_indisponivel"}')
        return 3
