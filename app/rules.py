import re

RULES = [
    ('destructive', 'critical', '疑似破坏数据操作', r'\brm\s+[^\n]*-[a-zA-Z]*r[a-zA-Z]*f|\bdrop\s+(database|table)\b|\bmkfs\b'),
    ('audit_disabled', 'high', '疑似关闭审计', r'\b(systemctl|service)\s+(stop|disable)\s+(auditd|rsyslog)\b|\bauditctl\s+-e\s+0'),
    ('privilege', 'high', '敏感权限修改', r'\bchmod\s+(777|[ugoa]*\+s)\b|/etc/sudoers|\busermod\s+.*-aG\s+(sudo|wheel)'),
    ('remote_exec', 'high', '下载内容直接交给 Shell 执行', r'\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(ba)?sh\b'),
    ('transfer', 'medium', '需要核实的数据传输', r'\b(scp|rsync)\b|\bcurl\b.*(--upload-file|--data-binary|\s-T\s)'),
]
RANK = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
def detect(command):
    return [{'rule_id': key, 'severity': severity, 'title': title} for key, severity, title, pattern in RULES if re.search(pattern, command, re.I)]

def redact(text):
    text = re.sub(r'(?i)((?:password|passwd|token|api[_-]?key|secret)\s*[=:]\s*)[^\s;]+', r'\1[REDACTED]', text)
    return re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[REDACTED]', text)
