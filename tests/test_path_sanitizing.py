"""Local-path detection in the notebook sanitizer and the upload scanner.

Example paths are assembled at runtime so this file itself stays free of
literal local paths (it is an upload candidate and is scanned too).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BS = "\\"
MARK = "[LOCAL_PATH_REMOVED]"


def load_tool(name):
    spec = importlib.util.spec_from_file_location(f"tool_{name}", ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sanitizer_removes_local_paths():
    sanitize = load_tool("sanitize_notebooks").sanitize_line
    paths = [
        "C:" + BS + "Users" + BS + "someone" + BS + "data.csv",
        "D:" + "/research/data.xlsx",
        "/Users" + "/someone/project/a.csv",
        "/home" + "/someone/a.csv",
        "E:" + BS + "企业微信" + BS + "a.xlsx",
        "WeDrive" + "/team/a.csv",
    ]
    for path in paths:
        assert sanitize(f'pd.read_csv(r"{path}")') == f'pd.read_csv(r"{MARK}")'


def test_sanitizer_keeps_escaped_newlines_and_urls():
    sanitize = load_tool("sanitize_notebooks").sanitize_line
    for line in ['print("Combined Data Tail:' + BS + 'n", df)', 'url = "https://example.com/a"', "ratio = 1:2"]:
        assert sanitize(line) == line


def test_upload_scanner_flags_enterprise_sync_folders_but_not_gitignore_entries():
    pattern = load_tool("check_upload_candidates").PATTERNS["enterprise sync folder path"]
    assert pattern.search("x = '" + "OneDrive" + "/team/a.csv'")
    assert pattern.search("企业微信" + BS + "a.xlsx")
    assert not pattern.search("." + "WeDrive" + "\n*.log")
