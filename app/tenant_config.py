"""Load site-to-database mappings from environment variables."""
import os

DB_KEYS = ("DB_NAME", "SUPPLY_DB_NAME", "REFERENCE_DB_NAME", "WAREHOUSE_DB_NAME",
           "DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "COOKIE_NAME")


def load_tenants():
    tenants = {}
    hosts = {}
    names = [name.strip().upper() for name in os.getenv("TENANTS", "").split(",") if name.strip()]
    for name in names:
        if not name.replace("_", "").isalnum() or name in tenants:
            raise ValueError(f"Invalid or duplicate tenant name: {name}")
        prefix = f"TENANT_{name}_"
        configured_hosts = os.getenv(prefix + "HOSTS") or os.getenv(prefix + "HOST", "")
        site_hosts = [host.strip().lower() for host in configured_hosts.split(",") if host.strip()]
        if not site_hosts:
            raise ValueError(f"{prefix}HOSTS must be configured")
        config = {key: os.environ[prefix + key] for key in DB_KEYS if os.getenv(prefix + key)}
        # Never silently use another tenant's databases.
        for key in ("DB_NAME", "SUPPLY_DB_NAME", "REFERENCE_DB_NAME"):
            if not config.get(key):
                raise ValueError(f"{prefix}{key} must be configured")
        tenants[name] = config
        for host in site_hosts:
            if host in hosts:
                raise ValueError(f"Duplicate tenant host: {host}")
            hosts[host] = name
    return tenants, hosts
