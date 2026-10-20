# 경고창을 띄우는 윈도우 기능을 쓰려고 불러온다
import ctypes
# Claude Code 가 넘겨주는 JSON 글을 읽으려고 불러온다
import json
# 파일 경로와 환경 변수를 다루려고 불러온다
import os
# 표준 입력·출력과 종료 코드를 다루려고 불러온다
import sys

# 오류 메시지의 한글이 깨지지 않게 UTF-8 로 내보낸다
sys.stderr.reconfigure(encoding="utf-8")

# 안내 화면에 글자 그대로 들어 있어야 하는 문구
NOTICE = "몇 개를 만들지 숫자로 넣어 주세요"


# 주어진 파일이 화면 파일인지 가리는 함수
def is_screen_file(path, project_dir):
    # 함수 설명
    """이 폴더 안의 .html 파일 가운데 dashboard/ 밖에 있는 것이 화면 파일이다."""
    # 비교하기 쉽게 파일 경로를 절대 경로·소문자로 맞춘다
    path = os.path.normcase(os.path.abspath(path))
    # 프로젝트 폴더 경로도 같은 방식으로 맞춘다
    root = os.path.normcase(os.path.abspath(project_dir))
    # .html 이 아니거나 프로젝트 폴더 밖에 있는 파일이면
    if not path.endswith(".html") or not path.startswith(root + os.sep):
        # 화면 파일이 아니다
        return False
    # 프로젝트 폴더를 기준으로 한 상대 경로를 구한다
    rel = os.path.relpath(path, root)
    # 맨 앞 폴더가 dashboard 가 아니면 화면 파일이다
    return rel.split(os.sep)[0] != "dashboard"


# 이번 답에서 고친 화면 파일을 대화 기록에서 찾는 함수
def screen_files_touched_this_turn(transcript_path, project_dir):
    # 함수 설명
    """마지막 사용자 질문 뒤로 Edit·Write 로 만들거나 고친 화면 파일 목록."""
    # 고친 화면 파일을 모을 빈 목록
    touched = []
    # 대화 기록 파일을 UTF-8 로 연다
    with open(transcript_path, encoding="utf-8") as f:
        # 대화 기록을 한 줄씩 읽는다
        for line in f:
            # 이 줄을 JSON 으로 읽어 본다
            try:
                # 한 줄이 대화 기록 한 칸이다
                entry = json.loads(line)
            # JSON 으로 읽을 수 없는 줄이면
            except Exception:
                # 건너뛴다
                continue
            # 이 칸의 내용(글, 도구 사용 등)을 꺼낸다
            content = (entry.get("message") or {}).get("content")
            # 사용자 쪽 칸이고 시스템이 끼워 넣은 칸이 아니면
            if entry.get("type") == "user" and not entry.get("isMeta"):
                # 도구 실행 결과를 돌려준 칸인지 확인한다
                is_tool_result = isinstance(content, list) and any(
                    # 내용 가운데 tool_result 가 하나라도 있는지 본다
                    c.get("type") == "tool_result" for c in content
                # any( 괄호를 닫는다
                )
                # 도구 결과가 아니라 사용자의 새 질문이면
                if not is_tool_result:
                    # 목록을 비운다
                    touched = []  # 새 질문이 시작되면 다시 센다
                # 사용자 칸은 더 볼 것이 없으니 다음 줄로 간다
                continue
            # Claude 쪽 칸이 아니거나 내용이 목록이 아니면
            if entry.get("type") != "assistant" or not isinstance(content, list):
                # 건너뛴다
                continue
            # Claude 칸의 내용을 하나씩 본다
            for c in content:
                # Edit 나 Write 도구를 쓴 것이면
                if c.get("type") == "tool_use" and c.get("name") in ("Edit", "Write"):
                    # 그 도구가 고친 파일 경로를 꺼낸다
                    path = (c.get("input") or {}).get("file_path", "")
                    # 경로가 있고 화면 파일이면
                    if path and is_screen_file(path, project_dir):
                        # 목록에 더한다
                        touched.append(path)
    # 이번 답에서 고친 화면 파일 목록을 돌려준다
    return touched


# 고친 화면 파일에 안내 문구가 빠졌는지 가리는 함수
def notice_missing(paths):
    # 함수 설명
    """고친 화면 파일 가운데 안내 문구가 그대로 들어 있지 않은 것이 있는가."""
    # 같은 파일은 한 번만 보도록 겹치는 경로를 없애고 하나씩 본다
    for path in set(paths):
        # 그 사이 지워져서 파일이 없으면
        if not os.path.exists(path):
            # 건너뛴다
            continue
        # 파일을 읽어 본다
        try:
            # 화면 파일을 UTF-8 로 연다
            with open(path, encoding="utf-8") as f:
                # 파일 안에 안내 문구가 글자 그대로 없으면
                if NOTICE not in f.read():
                    # 빠졌다고 알린다
                    return True
        # 파일을 읽다가 오류가 나면
        except Exception:
            # 건너뛴다
            continue
    # 모든 파일에 문구가 있으면 빠지지 않았다고 알린다
    return False


# 훅이 실행되면 처음 도는 함수
def main():
    # Claude Code 가 넘겨준 입력을 읽어 본다
    try:
        # 표준 입력의 JSON 을 읽는다
        data = json.load(sys.stdin)
    # 입력을 읽을 수 없으면
    except Exception:
        # 막지 않고 통과시킨다
        return 0

    # 이 훅 때문에 이어서 일하는 중이면 다시 막지 않는다 (끝없이 반복되지 않게)
    if data.get("stop_hook_active"):
        # 통과시킨다
        return 0

    # 대화 기록 파일 경로를 꺼낸다
    transcript_path = data.get("transcript_path", "")
    # 경로가 없거나 그 파일이 없으면
    if not transcript_path or not os.path.exists(transcript_path):
        # 통과시킨다
        return 0

    # 프로젝트 폴더를 정한다 (환경 변수 → 입력의 cwd → 지금 폴더 순서)
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    # 이번 답에서 고친 화면 파일을 찾는다
    touched = screen_files_touched_this_turn(transcript_path, project_dir)
    # 안내 문구가 빠진 화면 파일이 없으면
    if not notice_missing(touched):
        # 통과시킨다
        return 0

    # 경고창에 경고 아이콘을 붙이는 값
    MB_ICONWARNING = 0x30
    # 경고창을 다른 창들보다 맨 위에 두는 값
    MB_TOPMOST = 0x40000
    # 경고창을 맨 앞으로 끌어오는 값
    MB_SETFOREGROUND = 0x10000
    # 경고 소리를 낸다
    ctypes.windll.user32.MessageBeep(0x30)
    # 경고창을 띄운다 (누를 때까지 기다린다)
    ctypes.windll.user32.MessageBoxW(
        # 주인 창 없음
        0,
        # 경고창 내용
        "[안내 문구가 빠졌어요]",
        # 경고창 제목
        "block-lorem",
        # 경고 아이콘 + 맨 위 + 맨 앞
        MB_ICONWARNING | MB_TOPMOST | MB_SETFOREGROUND,
    # MessageBoxW( 괄호를 닫는다
    )

    # Claude 에게 보낼 메시지를 오류 출력에 쓴다
    sys.stderr.write("안내 화면에 '몇 개를 만들지 숫자로 넣어 주세요' 문구를 그대로 넣어라\n")
    # 종료 코드 2 는 "막아라"라는 뜻이다
    return 2


# 이 파일을 직접 실행했을 때만
if __name__ == "__main__":
    # main 을 돌리고 그 결과를 종료 코드로 돌려준다
    sys.exit(main())
