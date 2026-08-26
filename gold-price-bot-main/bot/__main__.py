# نقطه‌ی ورود: python -m bot
import logging

from .bot import build_app
from .config import LOG_PATH, validate


def main() -> None:
    errors = validate()
    if errors:
        raise SystemExit(
            "خطای پیکربندی:\n- " + "\n- ".join(errors)
            + "\n\nفایل .env را از روی .env.example بساز و پر کن."
        )

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(LOG_PATH, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    from .config import BOT_TOKEN

    app = build_app(BOT_TOKEN)   # post_init داخل همین تابع سیم‌کشی شده است
    print("🤖 ربات در حال اجراست — Ctrl+C برای توقف")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
