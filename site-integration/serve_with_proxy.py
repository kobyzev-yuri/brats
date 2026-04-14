#!/usr/bin/env python3
"""
Сервер для site-integration: раздаёт статику, проксирует чат в n8n, API ЛК в amocrm-api и события аналитики в sales-analytic.
Один хост (localhost:8000): страница сайта, ЛК (/lk/), прокси /api/n8n-proxy, /api/analytics-proxy и /api/lk/*.

Запуск (из директории site-integration или из корня репо):
  python site-integration/serve_with_proxy.py

Страница: http://localhost:8000/site-integration-example.html
Личный кабинет: http://localhost:8000/lk/login.html
Чат: URL http://localhost:8000/api/n8n-proxy
"""
import http.server
import json
import urllib.request
import sys
import os
from pathlib import Path

PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_WEBHOOK = "http://localhost:5678/webhook/sales-agent-kb"
_raw = (os.environ.get("N8N_WEBHOOK_URL") or "").strip().rstrip("/") or DEFAULT_WEBHOOK
if "/webhook/" not in _raw:
    _raw = _raw.rstrip("/") + "/webhook/sales-agent-kb" if _raw else DEFAULT_WEBHOOK
N8N_WEBHOOK = _raw

AMOCRM_API_BASE = (os.environ.get("AMOCRM_API_BASE_URL") or "http://localhost:8010").rstrip("/")
_ANALYTICS_BASE = (os.environ.get("ANALYTICS_SERVICE_URL") or "http://localhost:8002").rstrip("/")
ANALYTICS_COLLECT_URL = _ANALYTICS_BASE + "/api/analytics/collect"
ANALYTICS_TRIGGER_URL = _ANALYTICS_BASE + "/api/analytics/trigger"

# Директория для раздачи статики (где лежат .html) — всегда относительно расположения этого скрипта
SITE_DIR = str(Path(__file__).resolve().parent)


class ProxyHandler(http.server.SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/lk/") or self.path.startswith("/api/amocrm/"):
            self.proxy_to_amocrm_api()
        else:
            # Если запросили /site-integration/... — отдать файл из текущей директории (без префикса)
            path = self.path.split("?")[0].rstrip("/")
            if path.startswith("/site-integration/") and path != "/site-integration":
                self.path = path[len("/site-integration"):] or "/"
            super().do_GET()

    def do_POST(self):
        if self.path.rstrip("/") == "/api/n8n-proxy":
            self.proxy_to_n8n()
        elif self.path.rstrip("/") == "/api/analytics-proxy":
            self.proxy_to_analytics()
        elif self.path.startswith("/api/analytics-trigger-proxy"):
            self.proxy_to_analytics_trigger()
        elif self.path.startswith("/api/lk/"):
            self.proxy_to_amocrm_api()
        elif self.path.startswith("/api/amocrm/"):
            self.proxy_to_amocrm_api()
        else:
            self.send_error(404)

    def proxy_to_amocrm_api(self):
        """Прокси GET/POST /api/lk/* и /api/amocrm/* на amocrm-api (8010)."""
        path = self.path
        if path.startswith("/api/amocrm/"):
            path = "/api/" + path[len("/api/amocrm/"):]
        url = AMOCRM_API_BASE + path
        headers = {}
        for h in ("Authorization", "Content-Type"):
            v = self.headers.get(h)
            if v:
                headers[h] = v
        data = None
        if self.command == "POST":
            length = int(self.headers.get("Content-Length", 0))
            if length:
                data = self.rfile.read(length)
        req = urllib.request.Request(url, data=data, headers=headers or None, method=self.command)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = resp.read()
                if "/test-lead-from-chat" in path and self.command == "POST":
                    try:
                        j = json.loads(body.decode("utf-8"))
                        created = j.get("created", "?")
                        print(f"[amocrm] POST test-lead-from-chat -> {resp.status} created={created}", flush=True)
                    except Exception:
                        print(f"[amocrm] POST test-lead-from-chat -> {resp.status}", flush=True)
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
        except urllib.error.HTTPError as e:
            if "/test-lead-from-chat" in path:
                print(f"[amocrm] POST test-lead-from-chat -> {e.code} {e.reason}", flush=True)
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            body = json.dumps({"detail": e.reason or str(e)}).encode("utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except urllib.error.URLError as e:
            if "/test-lead-from-chat" in path:
                print(f"[amocrm] POST test-lead-from-chat -> недоступен: {e.reason}", flush=True)
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            body = json.dumps({"detail": "amocrm-api недоступен: " + str(e.reason)}).encode("utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

    def proxy_to_analytics(self):
        """Прокси POST /api/analytics-proxy на sales-analytic (счётчик событий place_interest и др.)."""
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            req = urllib.request.Request(
                ANALYTICS_COLLECT_URL,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            out = json.dumps({"status": "error", "detail": str(e)}).encode("utf-8")
            self.send_header("Content-Length", len(out))
            self.end_headers()
            self.wfile.write(out)

    def proxy_to_analytics_trigger(self):
        """Прокси POST /api/analytics-trigger-proxy?visitor_id=...&session_id=... на sales-analytic trigger."""
        from urllib.parse import urlparse, parse_qs
        try:
            parsed = urlparse(self.path)
            qs = parse_qs(parsed.query)
            visitor_id = (qs.get("visitor_id") or [""])[0]
            session_id = (qs.get("session_id") or [""])[0]
            threshold = (qs.get("threshold") or ["0.7"])[0]
            if not visitor_id or not session_id:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                body = json.dumps({"detail": "visitor_id and session_id required"}).encode("utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return
            url = f"{ANALYTICS_TRIGGER_URL}?visitor_id={urllib.parse.quote(visitor_id)}&session_id={urllib.parse.quote(session_id)}&threshold={urllib.parse.quote(threshold)}"
            req = urllib.request.Request(url, data=b"", method="POST")
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            self.send_response(e.code)
            self.send_header("Content-Type", "application/json")
            try:
                body = e.read()
            except Exception:
                body = json.dumps({"detail": e.reason or str(e)}).encode("utf-8")
            if not body:
                body = json.dumps({"detail": e.reason or str(e)}).encode("utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            out = json.dumps({"triggered": False, "detail": str(e)}).encode("utf-8")
            self.send_header("Content-Length", len(out))
            self.end_headers()
            self.wfile.write(out)

    def proxy_to_n8n(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            try:
                payload = json.loads(body.decode("utf-8")) if body else {}
                msg_preview = (payload.get("message") or "")[:50]
                ext = payload.get("external_id", "")
                print(f"[n8n] POST chat -> message={msg_preview!r}... external_id={ext!r}", flush=True)
            except Exception:
                print("[n8n] POST chat -> (тело не JSON)", flush=True)
            req = urllib.request.Request(
                N8N_WEBHOOK,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
                print(f"[n8n] POST chat <- {resp.status}", flush=True)
                self.send_response(resp.status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            print(f"[n8n] POST chat <- HTTP {e.code} {e.reason}", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            if e.code == 404:
                msg = (
                    f"n8n вернул 404 (Not Found). Проверьте: 1) workflow «Sales Agent - KB Integration» включён (кнопка Active); "
                    f"2) в узле Webhook выбран метод POST (не GET); 3) используется Production URL (не Test). Адрес прокси дергает: {N8N_WEBHOOK}"
                )
            else:
                msg = f"n8n вернул {e.code}: {e.reason}. URL: {N8N_WEBHOOK}"
            err = json.dumps({"agent_response": msg}).encode("utf-8")
            self.send_header("Content-Length", len(err))
            self.end_headers()
            self.wfile.write(err)
        except urllib.error.URLError as e:
            print(f"[n8n] POST chat -> недоступен: {e.reason}", flush=True)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            msg = f"Прокси не смог достучаться до n8n ({e.reason}). Убедитесь, что n8n запущен на 5678. URL: {N8N_WEBHOOK}"
            err = json.dumps({"agent_response": msg}).encode("utf-8")
            self.send_header("Content-Length", len(err))
            self.end_headers()
            self.wfile.write(err)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            err = json.dumps({"agent_response": f"Ошибка: {e}"}).encode()
            self.send_header("Content-Length", len(err))
            self.end_headers()
            self.wfile.write(err)


def main():
    directory = Path(__file__).resolve().parent
    os.chdir(directory)
    server = http.server.HTTPServer(("", PORT), ProxyHandler)
    print(f"Сервер с прокси: http://localhost:{PORT}/")
    print(f"  Страница сайта: http://localhost:{PORT}/site-integration-example.html")
    print(f"  Тест «интерес к объекту»: http://localhost:{PORT}/catalog-interest-test.html")
    print(f"  Личный кабинет: http://localhost:{PORT}/lk/login.html")
    print(f"  Чат (URL в настройках): http://localhost:{PORT}/api/n8n-proxy")
    print("  Логи: запросы к n8n и amocrm (test-lead-from-chat) выводятся в этот терминал.")
    print("Остановка: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
