import socket, threading

_last_message = None
_msg_lock = threading.Lock()
_running = False
_conn = None
_conn_lock = threading.Lock()

def _set_last(msg):
    global _last_message
    with _msg_lock:
        _last_message = msg

def getLastMessage():
    with _msg_lock:
        return _last_message

def _client_loop(conn, addr):
    global _conn
    with _conn_lock:
        _conn = conn
    print(f"[terminal] Client connected from {addr}", flush=True)
    try:
        conn.sendall(b"Connected to MeTTaClaw. Type your message and press Enter.\n\n")
        buf = b""
        while _running:
            data = conn.recv(1024)
            if not data:
                break
            buf += data
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                line = line.decode(errors="ignore").strip()
                if line:
                    _set_last(f"user: {line}")
    except Exception:
        pass
    finally:
        with _conn_lock:
            if _conn is conn:
                _conn = None
        conn.close()
        print("[terminal] Client disconnected", flush=True)

def _server_loop(port):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    srv.settimeout(1.0)
    print(f"[terminal] Listening on port {port}. Connect with: nc localhost {port}", flush=True)
    while _running:
        try:
            conn, addr = srv.accept()
            t = threading.Thread(target=_client_loop, args=(conn, addr), daemon=True)
            t.start()
        except socket.timeout:
            continue
        except Exception:
            break
    srv.close()

def start_terminal(port=3333):
    global _running
    _running = True
    t = threading.Thread(target=_server_loop, args=(port,), daemon=True)
    t.start()
    return t

def stop_terminal():
    global _running
    _running = False

def send_message(text):
    text = text.replace("\\n", "\n")
    with _conn_lock:
        conn = _conn
    if conn:
        try:
            conn.sendall(f"Agent: {text}\n\n".encode())
        except Exception:
            pass
