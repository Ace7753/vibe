def is_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def find_free_port(preferred=(8080, 8085, 8086, 8090, 0)) -> int:
    for port in preferred:
        if port == 0:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]
        if is_port_free(port):
            return port
    raise RuntimeError("No free port found")


def main() -> None:
    port = int(os.getenv("PORT", "0") or 0)
    if port and not is_port_free(port):
        print(f"Port {port} is busy, choosing another free port.")
        port = 0
    if port == 0:
        port = find_free_port()

    url = f"http://127.0.0.1:{port}"
    print(f"Starting app at {url}")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()