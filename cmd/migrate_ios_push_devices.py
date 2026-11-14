"""Create the iOS device registry in each configured supply database."""
from app.database import _engines
from app.models.ios_push_device import IOSPushDevice


def main():
    done = set()
    failures = []
    for site, group in _engines.items():
        engine = group['supply']
        key = (engine.url.host, engine.url.port, engine.url.database)
        if key in done:
            continue
        try:
            IOSPushDevice.__table__.create(engine, checkfirst=True)
            print(f"{site}: {engine.url.database}: OK")
            done.add(key)
        except Exception as exc:
            print(f"{site}: {type(exc).__name__}: {exc}")
            failures.append(site)
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
