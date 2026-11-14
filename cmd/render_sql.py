"""Render a SQL migration for a configured site; output is written to stdout."""
import argparse
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# Allow running the script directly from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.tenant_config import load_tenants

load_dotenv()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("sql_file", type=Path)
parser.add_argument("--site", help="hostname from TENANTS (required in multi-site mode)")
args = parser.parse_args()
tenants, hosts = load_tenants()
site = hosts.get((args.site or "").lower(), (args.site or "").upper())
if tenants and site not in tenants:
    parser.error("specify a configured --site")
config = tenants.get(site, {})
sql = args.sql_file.read_text(encoding="utf-8")

def replace(match):
    key = match.group(1)
    value = config.get(key) or os.getenv(key, "")
    if not re.fullmatch(r"[A-Za-z0-9_$]+", value):
        parser.error(f"{key} must contain a valid database name")
    return value

sys.stdout.write(re.sub(r"\{\{(DB_NAME|SUPPLY_DB_NAME|REFERENCE_DB_NAME|WAREHOUSE_DB_NAME)\}\}", replace, sql))
