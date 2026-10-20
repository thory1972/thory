import ctypes
import json
import os
import re
import sys

sys.stderr.reconfigure(encoding="utf-8")

PRD_RE = re.compile(r"(?<![\w.-])prd\.md(?![\w.-])", re.IGNORECASE)

# PRD.md 를 읽기만 하는 명령 (이 명령들은 PRD.md 가 들어 있어도 막지 않는다)
READ_COMMANDS = {
    # bash
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "rg",
    "wc", "diff", "cmp", "file", "stat", "ls", "dir", "md5sum", "sha1sum",
    "sha256sum", "sort", "uniq", "cut", "nl", "od", "xxd", "hexdump",
    "strings", "echo", "printf", "test", "realpath", "dirname", "basename",
    "awk", "sed", "cd",
    # PowerShell
    "get-content", "gc", "type", "select-string", "sls", "get-item", "gi",
    "get-childitem", "gci", "test-path", "get-filehash", "measure-object",
    "compare-object", "resolve-path", "split-path", "write-output",
    "write-host", "select-object", "format-list", "out-host", "out-string",
    "where-object", "set-location", "findstr",
}
COPY_COMMANDS = {"cp", "copy", "copy-item", "cpi"}


def split_command(command):
    """따옴표 밖의 ; && || | 줄바꿈으로 명령을 나누고, 따옴표 밖의 > 리다이렉트 대상도 모은다."""
    segments, targets = [], []
    buf, quote, i = "", None, 0
    while i < len(command):
        ch = command[i]
        if quote:
            if ch == quote:
                quote = None
            buf += ch
            i += 1
            continue
        if ch in "'\"":
            quote = ch
            buf += ch
            i += 1
            continue
        if ch in ";|\n" or command.startswith("&&", i):
            segments.append(buf)
            buf = ""
            i += 2 if command.startswith(("&&", "||"), i) else 1
            continue
        if ch == ">":
            j = i + 1
            if j < len(command) and command[j] == ">":
                j += 1
            if j < len(command) and command[j] == "&":
                buf += command[i:j + 1]
                i = j + 1
                continue
            while j < len(command) and command[j] in " \t":
                j += 1
            m = re.match(r"""["']?([^\s"';|&]+)""", command[j:])
            if m:
                targets.append(m.group(1))
            buf += command[i:j]
            i = j
            continue
        buf += ch
        i += 1
    segments.append(buf)
    return segments, targets


def first_word(segment):
    s = segment.strip()
    s = re.sub(r"^\$[\w:]+\s*=\s*", "", s)  # PowerShell 변수 대입: $x = ...
    s = s.lstrip("(&. \t")
    words = s.split()
    if not words:
        return ""
    word = os.path.basename(words[0].strip("\"'").replace("\\", "/")).lower()
    return word[:-4] if word.endswith(".exe") else word


def command_writes_prd(command):
    segments, targets = split_command(command)
    if any(PRD_RE.search(t) for t in targets):
        return True
    for segment in segments:
        if not PRD_RE.search(segment):
            continue
        word = first_word(segment)
        if word in COPY_COMMANDS:
            args = [a.strip("\"'") for a in segment.split()[1:] if not a.startswith("-")]
            if args and PRD_RE.search(args[-1]):
                return True
            continue
        if word == "sed" and re.search(r"(^|\s)(-i|--in-place)", segment):
            return True
        if word == "awk" and "inplace" in segment:
            return True
        if word not in READ_COMMANDS:
            return True
    return False


def touches_prd(data):
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})

    if tool_name in ("Bash", "PowerShell"):
        return command_writes_prd(tool_input.get("command", ""))

    if tool_name not in ("Edit", "Write"):
        return False

    file_path = tool_input.get("file_path", "")
    if not file_path:
        return False

    cwd = data.get("cwd") or os.getcwd()
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or cwd
    prd_path = os.path.normcase(os.path.abspath(os.path.join(project_dir, "PRD.md")))
    target_path = os.path.normcase(os.path.abspath(
        file_path if os.path.isabs(file_path) else os.path.join(cwd, file_path)
    ))
    return target_path == prd_path


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    if not touches_prd(data):
        return 0

    MB_ICONWARNING = 0x30
    MB_TOPMOST = 0x40000
    MB_SETFOREGROUND = 0x10000
    ctypes.windll.user32.MessageBeep(0x30)
    ctypes.windll.user32.MessageBoxW(
        0,
        "[기획서는 직접 고쳐 주세요]",
        "PRD 자물쇠",
        MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND,
    )

    sys.stderr.write("PRD.md 는 잠겨 있으니 고치지 말고 바꿀 내용을 제안만 하라\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
