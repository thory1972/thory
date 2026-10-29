import base64
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google import genai
from PIL import Image
from supabase import create_client

st.set_page_config(page_title="실습 게시판 만들기")

# Supabase 연결 (이 파일 옆 .env 의 주소와 키)
load_dotenv(Path(__file__).parent / ".env")
supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])

# 올라온 결과물 (drafts 표, 최근 것이 위)
rows = supabase.table("drafts").select("*").order("created_at", desc=True).execute().data
uploads = pd.DataFrame(rows, columns=["id", "created_at", "practice_no", "comment"])

# 결과물 사진은 이 파일 옆 uploads 폴더에 "글 번호.확장자" 로 둔다 (사진이 없는 예전 글은 그대로 글만 보임)
PHOTO_DIR = Path(__file__).parent / "uploads"


def photo_of(draft_id):
    found = sorted(PHOTO_DIR.glob(f"{draft_id}.*"))
    return found[0] if found else None


# 결과물마다 AI 한 줄 피드백은 이 파일 옆 feedback 폴더에 "글 번호.txt" 로 둔다 (한 번 만들면 다시 부르지 않음)
FEEDBACK_DIR = Path(__file__).parent / "feedback"


def feedback_of(draft_id):
    path = FEEDBACK_DIR / f"{draft_id}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else None


# AI 한 줄 피드백 만들기 (한 줄 설명만 보내고, 사진은 보내지 않는다. 실패하면 오류를 그대로 올려 보낸다)
def make_feedback(draft_id, practice_no, comment):
    text = f"실습 {practice_no} 결과물의 한 줄 설명: {comment}"
    # genai.Client()는 GEMINI_API_KEY 환경 변수에서 키를 읽는다
    # 서버가 붐빌 때 화면이 멈춰 있지 않도록 60초(60000ms) 뒤에는 포기한다
    client = genai.Client(http_options={"timeout": 60000})
    interaction = client.interactions.create(
        model="gemini-3.5-flash-lite",
        system_instruction=instruction("feedback_format.txt").strip(),
        input=text,
    )
    FEEDBACK_DIR.mkdir(exist_ok=True)
    (FEEDBACK_DIR / f"{draft_id}.txt").write_text(interaction.output_text.strip(), encoding="utf-8")
    save_log("AI 피드백", None, text, interaction.output_text.strip())


# 지금 보여줄 화면 (0=첫 화면, 1, 2, 3, 4=안내)
if "page" not in st.session_state:
    st.session_state.page = 0


def go(page):
    st.session_state.page = page
    st.rerun()


# 첫 화면 히어로 배경 영상 (이 파일 옆 hero.mp4, 없으면 같은 파란 그러데이션만 보임)
HERO_VIDEO = Path(__file__).parent / "hero.mp4"


# 영상을 페이지 안에 바로 넣는다 (고친 시각이 바뀌면 다시 읽음)
@st.cache_data
def hero_video_src(mtime):
    return "data:video/mp4;base64," + base64.b64encode(HERO_VIDEO.read_bytes()).decode()


# 첫 화면 · 서비스 소개 (배경 #9ac1f0 · 글자 #a0e548 · 강조 #e45f2b, 글자는 배경과 대비가 낮아 진한 그림자를 둠)
# 히어로 칸: 영상을 칸 전체에 깔고 그 위에 제목 · 한 줄 소개 · 시작하기 버튼을 올린다
def landing():
    st.html("""<style>
    .stApp { background: #9ac1f0; }
    .st-key-hero { position: relative; overflow: hidden; border-radius: 16px; padding: 56px 24px 48px;
        margin-top: 24px; background: linear-gradient(135deg, #075985, #0EA5E9); }
    .st-key-hero > * { position: relative; z-index: 1; }
    .st-key-hero > [data-testid="stElementContainer"]:has(.hero-video) { position: absolute; inset: 0;
        z-index: 0; margin: 0; }
    .hero-video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover;
        pointer-events: none; }
    .landing { text-align: center; color: #a0e548;
        text-shadow: 0 1px 2px #1d3557, 0 0 6px rgba(29, 53, 87, 0.6); }
    .landing h1 { font-size: 3rem; font-weight: 800; color: #a0e548; margin-bottom: 12px; }
    .landing .intro { font-size: 1.25rem; margin-bottom: 16px; }
    .landing ol { list-style: none; padding: 0; margin-top: 24px; display: grid; gap: 16px;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); text-align: left; }
    .landing li { padding: 20px; border-radius: 12px; border-top: 4px solid #e45f2b;
        background: rgba(29, 53, 87, 0.12); font-size: 1.05rem; }
    .landing li b { display: block; color: #e45f2b; text-shadow: none; font-size: 1.5rem; margin-bottom: 4px; }
    .st-key-landing_start { align-self: center; width: min(320px, 100%); }
    .st-key-landing_start button { background: #e45f2b; border-color: #e45f2b; color: #ffffff;
        font-size: 1.15rem; padding: 12px 0; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); }
    .st-key-landing_start button:hover { background: #c94d1d; border-color: #c94d1d; color: #ffffff; }
    </style>""")

    with st.container(key="hero"):
        if HERO_VIDEO.exists():
            src = hero_video_src(HERO_VIDEO.stat().st_mtime)
            st.html(f'<video class="hero-video" src="{src}" autoplay muted loop playsinline></video>')
        st.html("""<div class="landing">
          <h1>실습 게시판 만들기</h1>
          <p class="intro">실습 개수만 넣으면 번호가 매겨진 실습 게시판이 만들어집니다</p>
        </div>""")
        if st.button("시작하기", key="landing_start", width="stretch"):
            go(1)

    st.html("""<div class="landing"><ol>
        <li><b>1</b>실습 개수를 넣고 만들기를 누르는 화면</li>
        <li><b>2</b>만들어진 게시판들을 목록으로 보여주는 화면</li>
        <li><b>3</b>결과물을 올리고, 올라온 결과물을 보는 화면</li>
    </ol></div>""")


# 화면1 · 만들기
def screen1():
    st.title("실습 게시판 만들기")

    # 넣는 자리
    count = st.number_input("실습 개수", min_value=1, step=1, value=None, placeholder="3")

    # 버튼
    if st.button("만들기", type="primary", width="stretch"):
        if count is None:
            go(4)
        else:
            st.session_state.count = int(count)
            go(2)

    st.divider()
    st.caption("넣은 개수만큼 게시판 칸이 만들어집니다")


# 화면2 · 게시판 목록 (넣은 개수만큼, 올라온 개수는 drafts 표에서 셈)
def screen2():
    st.title("게시판 목록")

    for i in range(1, st.session_state.count + 1):
        name = f"실습 {i}"
        board_rows = uploads[uploads["practice_no"] == i]
        # 가장 최근에 올라온 사진 하나 (uploads 는 최근 것이 위, 사진이 없는 예전 글은 건너뜀)
        latest = next((p for p in map(photo_of, board_rows["id"]) if p), None)
        with st.container(border=True):
            if st.button(name, width="stretch"):
                st.session_state.board = i
                go(3)
            if latest:
                st.image(str(latest), width=160)
            st.caption(f"올라온 개수 {len(board_rows)}개")

    if st.button("처음으로", width="stretch"):
        go(1)


# 화면3 · 게시판 하나 (목록에서 누른 실습)
def screen3():
    no = st.session_state.board
    name = f"실습 {no}"
    board_rows = uploads[uploads["practice_no"] == no]

    st.title(name)

    # 올리는 자리 (올리면 drafts 표에 한 줄 저장, 칸은 비워짐)
    with st.container(border=True):
        st.subheader("올리기")
        with st.form("upload", clear_on_submit=True, border=False):
            # 한 번에 사진 1장만 고를 수 있게 한다
            photo = st.file_uploader("사진 올리는 칸", type=["png", "jpg", "jpeg"], accept_multiple_files=False)
            comment = st.text_input("한 줄 설명")
            submitted = st.form_submit_button("올리기", type="primary", width="stretch")

    if submitted:
        if photo is None:
            st.warning("사진을 1장 골라 주세요")
        elif not comment.strip():
            st.warning("한 줄 설명을 넣어 주세요")
        else:
            # 글은 drafts 표에 남기고, 받은 글 번호로 사진 파일 이름을 정한다
            saved = supabase.table("drafts").insert({"practice_no": no, "comment": comment.strip()}).execute().data
            PHOTO_DIR.mkdir(exist_ok=True)
            (PHOTO_DIR / f"{saved[0]['id']}{Path(photo.name).suffix.lower()}").write_bytes(photo.getvalue())
            # 올리자마자 AI 한 줄 피드백을 만든다 (실패해도 결과물은 올라가고, 오류는 다시 그린 화면에 한 번 보여 준다)
            try:
                make_feedback(saved[0]["id"], no, comment.strip())
            except Exception as e:
                st.session_state.feedback_error = f"피드백을 받지 못했습니다: {e}"
            st.rerun()

    if "feedback_error" in st.session_state:
        st.error(st.session_state.pop("feedback_error"))

    # 올라온 결과물 (한 줄에 3칸)
    left, right = st.columns([3, 1])
    left.subheader("올라온 결과물")
    right.caption(f"{len(board_rows)}개")
    if board_rows.empty:
        st.caption("아직 올라온 결과물이 없습니다")
    for start in range(0, len(board_rows), 3):
        for col, (_, row) in zip(st.columns(3), board_rows.iloc[start:start + 3].iterrows()):
            with col.container(border=True):
                photo_path = photo_of(row["id"])
                if photo_path:
                    st.image(str(photo_path))
                st.write(row["comment"])
                st.caption(row["created_at"][:16].replace("T", " "))
                # AI 한 줄 피드백 (없으면 버튼으로 만든다)
                feedback = feedback_of(row["id"])
                if feedback:
                    st.caption(f"🤖 AI 피드백: {feedback}")
                elif st.button("AI 피드백 받기", key=f"feedback_{row['id']}"):
                    try:
                        make_feedback(row["id"], no, row["comment"])
                        st.rerun()
                    except Exception as e:
                        st.error(f"피드백을 받지 못했습니다: {e}")

    # 내려받기 (이 게시판에 올라온 결과물, 엑셀에서도 한글이 안 깨지게 utf-8-sig)
    st.download_button(
        "내려받기",
        board_rows.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{name}.csv",
        mime="text/csv",
        width="stretch",
    )

    if st.button("목록으로", width="stretch"):
        go(2)


# 안내 · 실습 개수를 비우고 만들기를 눌렀을 때 (확인을 누르면 화면1로 돌아감)
def screen4():
    st.title("안내")
    st.warning("몇 개를 만들지 숫자로 넣어 주세요")
    if st.button("확인", type="primary", width="stretch"):
        go(1)


# AI 답에 붙이는 고정 지시문 (이 파일 옆 글 파일: 답변 초안은 answer_format.txt, 대화창은 chat_format.txt)
# 부를 때마다 새로 읽어서, 글 파일만 고치면 앱을 다시 켜지 않아도 바로 반영되게 한다
def instruction(name):
    return "\n\n" + (Path(__file__).parent / name).read_text(encoding="utf-8").strip()


# 말투 (화면에 보이는 이름은 여기 고정, AI에게 주는 설명은 이 파일 옆 tones.txt 의 "이름 = 설명" 줄)
TONES = ["정중하게", "친근하게", "간결하게"]


# 고른 말투 지시 (지시문 맨 끝에 붙여서 앞의 말투 설명보다 먼저 따르게 한다, tones.txt 에 없으면 붙이지 않음)
def tone_instruction(tone):
    for line in (Path(__file__).parent / "tones.txt").read_text(encoding="utf-8").splitlines():
        name, _, desc = line.partition("=")
        if name.strip() == tone:
            return f"\n\n[말투 — 위 지시의 말투 설명보다 이것을 따른다. 세 문장 형식은 그대로 지킨다]\n- {desc.strip()}"
    return ""


# AI 답을 화면에 보여 줌 (마크다운은 줄바꿈 하나를 무시하므로, 줄 끝에 공백 두 칸을 붙여 줄이 바뀌게 한다)
def show_ai_text(box, text):
    box.write(text.replace("\n", "  \n"))


# AI 기록을 Supabase 에 못 남길 때 대신 쓰는 파일 (이 파일 옆 ai_logs.jsonl, 한 줄에 기록 하나)
LOG_FILE = Path(__file__).parent / "ai_logs.jsonl"


# AI 기록 남기기 (먼저 Supabase ai_logs 표에, 표가 없거나 안 되면 ai_logs.jsonl 에. 기록이 안 돼도 받은 답은 그대로 보인다)
def save_log(source, tone, text, answer):
    record = {"source": source, "tone": tone, "input": text, "output": answer}
    try:
        supabase.table("ai_logs").insert(record).execute()
    except Exception:
        try:
            record["created_at"] = datetime.now(timezone.utc).isoformat()
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            st.warning(f"기록을 남기지 못했습니다: {e}")


# 사이드바 · 지난 결과 (Supabase ai_logs 표와 ai_logs.jsonl 을 모아서, 최근 것이 위, 최근 100개)
def log_sidebar():
    with st.sidebar.expander("지난 결과"):
        logs = []
        try:
            logs += supabase.table("ai_logs").select("*").order("created_at", desc=True).limit(100).execute().data
        except Exception:
            pass  # 표가 아직 없으면 파일에 남은 기록만 보여 준다
        if LOG_FILE.exists():
            logs += [json.loads(line) for line in LOG_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        logs = sorted(logs, key=lambda r: pd.to_datetime(r["created_at"], utc=True), reverse=True)[:100]
        if not logs:
            st.caption("아직 남은 결과가 없습니다")
            return
        table = pd.DataFrame(logs)
        # Supabase 시간은 세계 표준시라 한국 시간으로 바꿔 보여 준다
        table["created_at"] = (
            pd.to_datetime(table["created_at"], utc=True).dt.tz_convert("Asia/Seoul").dt.strftime("%Y-%m-%d %H:%M")
        )
        table = table[["created_at", "source", "tone", "input", "output"]]
        table.columns = ["때", "어디서", "말투", "넣은 것", "받은 답"]
        st.dataframe(table, hide_index=True)


# AI 답 점검 (정확히 세 줄이고 300자 이하면 통과, "확실하지 않은 내용이에요"로 시작하면 그대로 통과)
RETRY_TEXT = "다시 시도해 주세요"


def answer_ok(text):
    text = text.strip()
    if text.lstrip("[").startswith("확실하지 않은 내용이에요"):
        return True
    return len(text.splitlines()) == 3 and len(text) <= 300


# 점검을 못 넘으면 한 번 더 묻는다 (ask 는 AI를 한 번 부르는 함수, 두 번 다 못 넘으면 ok 가 False)
def ask_checked(ask):
    interaction = ask()
    if not answer_ok(interaction.output_text):
        interaction = ask()
    return interaction, answer_ok(interaction.output_text)


# 사이드바 · 답변 초안 (문의 글을 넣으면 AI가 답변 초안을 만든다, 어느 화면에서나 보임)
def draft_sidebar():
    with st.sidebar:
        st.subheader("답변 초안")
        question = st.text_area("문의 글")
        tone = st.radio("말투", TONES, horizontal=True, key="draft_tone")

        if st.button("답변 초안 만들기", type="primary", width="stretch"):
            if not question.strip():
                st.warning("문의 글을 넣어 주세요")
            else:
                try:
                    # genai.Client()는 GEMINI_API_KEY 환경 변수에서 키를 읽는다
                    # 서버가 붐빌 때 화면이 멈춰 있지 않도록 60초(60000ms) 뒤에는 포기한다
                    client = genai.Client(http_options={"timeout": 60000})
                    interaction, ok = ask_checked(lambda: client.interactions.create(
                        model="gemini-3.5-flash-lite",
                        system_instruction="고객 문의 글에 대한 답변 초안을 한국어로, 정중하고 간결하게 작성한다."
                        + instruction("answer_format.txt")
                        + tone_instruction(tone),
                        input=question,
                    ))
                    # 화면을 옮겨도 남아 있도록 session_state 에 둔다 (점검을 못 넘으면 답 대신 다시 시도 안내)
                    st.session_state.draft = interaction.output_text if ok else RETRY_TEXT
                    save_log("답변 초안", tone, question, interaction.output_text)
                except Exception as e:
                    st.error(f"답을 받지 못했습니다: {e}")

        # 결과 자리
        if "draft" in st.session_state:
            show_ai_text(st, st.session_state.draft)


# 챗봇 아이콘 그림 (원본은 1.6MB 라서, 로봇 얼굴만 정사각형으로 잘라 128px 로 줄여 한 번만 만든다)
@st.cache_data
def bot_icon():
    path = Path(__file__).parent / "AI 답변 초안 로봇 도우미.png"
    icon = Image.open(path).crop((418, 20, 1118, 720)).resize((128, 128), Image.LANCZOS)
    buf = io.BytesIO()
    icon.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


# AI 답 옆 복사 버튼 (누르면 답 전체를 클립보드에 넣고, 잠깐 ✅ 로 바뀜)
def copy_button(text):
    # AI 답은 JS 문자열로만 들어가게 하고, < 까지 바꿔서 답 속 태그가 코드로 실행되지 않게 한다
    text_js = json.dumps(text).replace("<", "\\u003c")
    st.iframe(f"""
    <button id="copy" style="border: none; background: transparent; font-size: 18px; cursor: pointer;">📋</button>
    <script>
    const btn = document.getElementById("copy");
    btn.onclick = () => navigator.clipboard.writeText({text_js})
        .then(() => btn.textContent = "✅", () => btn.textContent = "❌")
        .finally(() => setTimeout(() => btn.textContent = "📋", 1500));
    </script>""", height=40)


# 대화 한 줄 (AI 답이면 오른쪽에 복사 버튼을 붙인다)
def show_message(box, m):
    with box.chat_message(m["role"]):
        if m.get("ai"):
            text_col, copy_col = st.columns([6, 1])
            show_ai_text(text_col, m["content"])
            with copy_col:
                copy_button(m["content"])
        else:
            st.write(m["content"])


# 챗봇 · 오른쪽 아래 아이콘 (누르면 대화창이 열리고 닫힘, PRD.md 를 읽고 서비스에 대해 답함)
def chatbot():
    if "chat_open" not in st.session_state:
        st.session_state.chat_open = False
        st.session_state.chat = [{"role": "assistant", "content": "안녕하세요! 이 서비스에 대해 궁금한 점을 물어보세요."}]
        st.session_state.chat_last_id = None

    # 아이콘과 대화창을 화면 오른쪽 아래에 띄운다 (밝은/어두운 테마에 맞춰 바탕색을 고름)
    dark = st.context.theme.type == "dark"
    st.html(f"""<style>
    .st-key-chatbot_btn {{ position: fixed; right: 24px; bottom: 24px; z-index: 1000; width: auto; }}
    .st-key-chatbot_btn button {{ width: 64px; height: 64px; border-radius: 50%; padding: 0;
        background-image: url("data:image/png;base64,{bot_icon()}") !important;
        background-size: cover !important; background-position: center !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25); }}
    .st-key-chatbot_btn button p {{ visibility: hidden; }}
    .st-key-chatbot_win {{ position: fixed; right: 24px; bottom: 100px; z-index: 1000;
        width: min(360px, calc(100vw - 48px)); padding: 12px; border-radius: 12px;
        background: {"#0e1117" if dark else "#ffffff"}; box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25); }}
    </style>""")

    with st.container(key="chatbot_btn"):
        if st.button("🤖", key="chatbot_toggle"):
            st.session_state.chat_open = not st.session_state.chat_open

    if not st.session_state.chat_open:
        return

    with st.container(key="chatbot_win"):
        st.subheader("무엇이든 물어보세요")
        # 말투를 바꾸면 다음 답부터 바뀐 말투로 답한다
        tone = st.radio("말투", TONES, horizontal=True, key="chat_tone")
        messages = st.container(height=320, border=False)
        for m in st.session_state.chat:
            show_message(messages, m)

        question = st.chat_input("궁금한 점을 적어 주세요", key="chatbot_input")
        if question:
            st.session_state.chat.append({"role": "user", "content": question})
            show_message(messages, st.session_state.chat[-1])
            try:
                # 물을 때마다 PRD.md 를 새로 읽어서, PRD 가 바뀌면 답도 따라 바뀌게 한다
                prd = (Path(__file__).parent / "PRD.md").read_text(encoding="utf-8")
                # genai.Client()는 GEMINI_API_KEY 환경 변수에서 키를 읽는다
                # 서버가 붐빌 때 화면이 멈춰 있지 않도록 60초(60000ms) 뒤에는 포기한다
                client = genai.Client(http_options={"timeout": 60000})
                # 앞 대화는 previous_interaction_id 로 이어지지만, system_instruction 은 매번 다시 보내야 한다
                # 다시 물을 때도 같은 앞 대화에 이어서 묻는다 (못 넘은 답은 앞 대화에 넣지 않음)
                interaction, ok = ask_checked(lambda: client.interactions.create(
                    model="gemini-3.5-flash-lite",
                    system_instruction=(
                        "너는 이 서비스의 상담 챗봇이다. 아래 PRD.md 내용만 근거로, 서비스에 대해 묻는 말에 "
                        "한국어로 친절하고 짧게 답한다. PRD.md 에 없는 내용은 지어내지 말고 모른다고 답한다.\n\n"
                        + prd
                        + instruction("chat_format.txt")
                        + tone_instruction(tone)
                    ),
                    input=question,
                    previous_interaction_id=st.session_state.chat_last_id,
                ))
                if ok:
                    st.session_state.chat_last_id = interaction.id
                    reply = {"role": "assistant", "content": interaction.output_text, "ai": True}
                else:
                    reply = {"role": "assistant", "content": RETRY_TEXT}
                save_log("대화창", tone, question, interaction.output_text)
            except Exception as e:
                reply = {"role": "assistant", "content": f"답을 받지 못했습니다: {e}"}
            st.session_state.chat.append(reply)
            show_message(messages, reply)


# 첫 화면은 소개만 보여주고, 사이드바와 챗봇은 기능 화면에서만 그린다
if st.session_state.page == 0:
    landing()
    st.stop()

if st.sidebar.button("첫 화면으로", width="stretch"):
    go(0)
draft_sidebar()
chatbot()
log_sidebar()  # 대화창 다음에 그려야 방금 대화창에서 받은 답도 목록에 바로 보인다
{1: screen1, 2: screen2, 3: screen3, 4: screen4}[st.session_state.page]()
