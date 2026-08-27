# Entry point: python -m bot  (Railway edition)
# Dev comments are English; user-facing messages stay Persian.
import logging
import os
import threading

from .bot import build_app
from .config import LOG_PATH, validate


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit(
            "خطای پیکربندی:\n- " + "\n- ".join(errors)
            + "\n\nمتغیرهای BOT_TOKEN و ADMIN_IDS را در Railway Variables تنظیم کن."
        )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),   # live log in the Railway dashboard
        ],
    )

    # Railway healthcheck: a tiny web server on $PORT so Railway knows the
    # process is alive (polling does the actual bot work)
    port = int(os.getenv("PORT", "8080"))

    def _run_health_server() -> None:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"gold-price-bot is running")

            def log_message(self, *args):
                pass  # silent — we don't want extra logs

        HTTPServer(("0.0.0.0", port), Handler).serve_forever()

    threading.Thread(target=_run_health_server, daemon=True).start()

    from .config import BOT_TOKEN

    app = build_app(BOT_TOKEN)   # post_init is wired inside this call
    print("🤖 ربات در حال اجراست — برای توقف، سرویس را در Railway Restart کن")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()