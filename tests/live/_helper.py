"""
Shared helpers for live integration tests against the real TickTick API.
Run with:  PYTHONDONTWRITEBYTECODE=1 python3 tests/live/01_utils.py
"""
import sys, os, traceback, time, textwrap
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

# ── colours ─────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS  = f"{GREEN}PASS{RESET}"
FAIL  = f"{RED}FAIL{RESET}"
SKIP  = f"{YELLOW}SKIP{RESET}"
INFO  = f"{CYAN}INFO{RESET}"

_results: list[tuple[str,str,str]] = []   # (name, status, detail)

def _header(title: str):
    bar = "═" * 60
    print(f"\n{BOLD}{CYAN}{bar}{RESET}")
    print(f"{BOLD}{CYAN}  {title}{RESET}")
    print(f"{BOLD}{CYAN}{bar}{RESET}")

def check(name: str, fn, *, expect_key: str|None = None,
          expect_no_error: bool = True, skip_reason: str|None = None):
    """Run fn(), report PASS/FAIL.  Returns the result or None on failure."""
    if skip_reason:
        _results.append((name, "SKIP", skip_reason))
        print(f"  {SKIP}  {name}  ({skip_reason})")
        return None
    try:
        t0 = time.monotonic()
        result = fn()
        elapsed = time.monotonic() - t0
        # error detection
        is_err = False
        detail = ""
        if isinstance(result, dict):
            if "error" in result and expect_no_error:
                is_err = True
                detail = result.get("message") or result.get("error", "")
            elif expect_key and expect_key not in result:
                is_err = True
                detail = f"missing key '{expect_key}' in result"
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            if "error" in result[0] and expect_no_error:
                is_err = True
                detail = result[0].get("error","")
        if is_err:
            _results.append((name, "FAIL", detail))
            print(f"  {FAIL}  {name}  — {detail}")
            return result
        _results.append((name, "PASS", f"{elapsed:.2f}s"))
        print(f"  {PASS}  {name}  ({elapsed:.2f}s)")
        return result
    except Exception as e:
        tb = traceback.format_exc().strip().split("\n")[-1]
        _results.append((name, "FAIL", tb))
        print(f"  {FAIL}  {name}  — {tb}")
        return None

def assert_result(name: str, result, condition, detail: str = ""):
    """Extra assertion after a check() call."""
    if condition:
        _results.append((name, "PASS", detail))
        print(f"  {PASS}    → {name}")
    else:
        _results.append((name, "FAIL", detail))
        print(f"  {FAIL}    → {name}  — {detail}")

def show_sample(label: str, data, n: int = 3):
    """Print a pretty sample of a list or dict."""
    import json
    if isinstance(data, list):
        sample = data[:n]
    else:
        sample = data
    s = json.dumps(sample, ensure_ascii=False, indent=2, default=str)
    lines = s.split("\n")[:20]
    print(f"    {INFO} {label}:")
    for l in lines:
        print(f"      {l}")
    if len(s.split("\n")) > 20:
        print("      ...")

def summary():
    """Print final summary and exit 1 if any failures."""
    total  = len(_results)
    passed = sum(1 for _,s,_ in _results if s == "PASS")
    failed = sum(1 for _,s,_ in _results if s == "FAIL")
    skipped= sum(1 for _,s,_ in _results if s == "SKIP")
    bar = "─" * 60
    print(f"\n{bar}")
    print(f"{BOLD}RÉSULTATS : {passed}/{total-skipped} réussis  |  {failed} échecs  |  {skipped} ignorés{RESET}")
    if failed:
        print(f"\n{RED}Échecs :{RESET}")
        for name, s, detail in _results:
            if s == "FAIL":
                detail_short = textwrap.shorten(str(detail), 80)
                print(f"  ✗ {name}: {detail_short}")
        sys.exit(1)
    print(f"{GREEN}Tout est bon.{RESET}")
