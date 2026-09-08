"""Check the real stale-part condition without importing or running archiver."""

import ast
import difflib
import hashlib
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

source = Path(sys.argv[1] if len(sys.argv) > 1 else "/root/get_ws_data_crypto/archiver.py")
original = source.read_text()
before = "datetime.fromtimestamp(stat.st_mtime)) > timedelta(minutes=ARCHIVER_MIN_AGE_MINUTES)"
after = "datetime.fromtimestamp(stat.st_mtime, timezone.utc)) > timedelta(minutes=ARCHIVER_MIN_AGE_MINUTES)"
assert original.count(before) == 1, "Expected one unfixed stale-part condition"
fixed = original.replace(before, after)
patch = "".join(difflib.unified_diff(original.splitlines(True), fixed.splitlines(True), fromfile="a/archiver.py", tofile="b/archiver.py"))
assert patch == Path(__file__).with_name("archiver-stale-part-utc.patch").read_text()


def expression(code):
    tree = ast.parse(code)
    process = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "process_file")
    matches = [n.test for n in ast.walk(process) if isinstance(n, ast.If) and "st_mtime" in ast.unparse(n.test)]
    assert len(matches) == 1
    return compile(ast.Expression(matches[0]), str(source), "eval")


# Compile only the pure clock function; module-level logging and all file I/O stay unexecuted.
tree = ast.parse(original)
clock = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_now")
scope = {"datetime": datetime, "timezone": timezone}
exec(compile(ast.Module(body=[clock], type_ignores=[]), str(source), "exec"), scope)
assert scope["_now"]().utcoffset() == timedelta(0)
now = datetime(2026, 9, 8, 0, 0, tzinfo=timezone.utc)
scope.update(timedelta=timedelta, _now=lambda: now, ARCHIVER_MIN_AGE_MINUTES=60)
broken, repaired = expression(original), expression(fixed)
for zone in ("UTC", "Europe/Rome", "Pacific/Honolulu"):
    os.environ["TZ"] = zone
    time.tzset()
    for age in (-1, 0, 3599, 3600, 3601, 86400):
        scope["stat"] = SimpleNamespace(st_mtime=now.timestamp() - age)
        try:
            eval(broken, scope)
        except TypeError as error:
            assert "offset-naive" in str(error) and "offset-aware" in str(error)
        else:
            raise AssertionError("The original condition did not reproduce the timezone error")
        assert eval(repaired, scope) is (age > 3600), (zone, age)
    print(f"{zone}: difetto riprodotto, correzione valida su 6 età e soglia stretta")
assert source.read_text() == original, "Source changed during the check"
print("Sorgente invariato SHA256:", hashlib.sha256(original.encode()).hexdigest())
