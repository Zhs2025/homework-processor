import io
import json
import re

import streamlit as st

from formatter import _render_chinese, _render_english, _render_math

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="作业批改助手", page_icon="📝", layout="wide")
st.title("📝 AI 作业批改助手")

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 设置")
    subject = st.selectbox("学科", ["英语", "语文", "数学"])
    model_name = st.selectbox("模型", ["Gemini Flash", "DeepSeek"])
    api_key = st.text_input("API Key", type="password", placeholder="粘贴你的 API Key")
    st.divider()
    st.caption("支持 .txt / .docx / .pdf 上传")


# ── Helpers ────────────────────────────────────────────────────────────────────
PROMPT_FILES = {"语文": "chinese.txt", "数学": "math.txt", "英语": "English.txt"}


def load_prompt(subj: str) -> str:
    with open(PROMPT_FILES[subj], encoding="utf-8") as f:
        return f.read()


def read_uploaded_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    if name.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="ignore")
    if name.endswith(".docx"):
        from docx import Document
        doc = Document(io.BytesIO(uploaded_file.read()))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    if name.endswith(".pdf"):
        import pdfplumber
        pages = []
        with pdfplumber.open(io.BytesIO(uploaded_file.read())) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    pages.append(t)
        return "\n".join(pages)
    return ""


def build_prompt(subj: str, homework: str, math_question: str = "", math_answer: str = "") -> str:
    template = load_prompt(subj)
    template = template.replace("{作业内容}", homework)
    if subj == "数学":
        template = template.replace("{数学题目}", math_question)
        template = template.replace("{标准答案或关键步骤}", math_answer)
    return template


def call_gemini(prompt: str, key: str) -> str:
    import google.generativeai as genai
    genai.configure(api_key=key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text


def call_deepseek(prompt: str, key: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=key, base_url="https://api.deepseek.com")
    resp = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    return resp.choices[0].message.content


def call_model(name: str, prompt: str, key: str) -> str:
    if name == "Gemini Flash":
        return call_gemini(prompt, key)
    return call_deepseek(prompt, key)


def extract_json(raw: str) -> dict:
    """Parse JSON, stripping accidental ```json fences if present."""
    raw = raw.strip()
    # Strip fences
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Last resort: find first {...} block
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


def render_result(raw: str) -> str:
    try:
        data_root = extract_json(raw)
    except Exception:
        return raw  # show raw if unparseable

    if not data_root.get("success", True):
        error_msg = data_root.get("error_message", "未知错误")
        subj = data_root.get("metadata", {}).get("subject", "")
        label = {"chinese": "语文", "math": "数学", "english": "英语"}.get(subj, "作业")
        return "\n".join([
            f"## ❌ {label}批改失败",
            "",
            f"> **错误原因**：{error_msg}",
            "",
            "请检查输入内容是否与所选学科匹配，或重新提交。",
        ])

    data = data_root.get("data", {}) or {}
    subj = data_root.get("metadata", {}).get("subject", "")
    if subj == "chinese":
        return _render_chinese(data)
    if subj == "math":
        return _render_math(data)
    if subj == "english":
        return _render_english(data)
    return f"```json\n{json.dumps(data_root, ensure_ascii=False, indent=2)}\n```"


# ── Main area ──────────────────────────────────────────────────────────────────
# Math extra inputs
math_question, math_answer = "", ""
if subject == "数学":
    st.subheader("📐 数学题目信息")
    col1, col2 = st.columns(2)
    with col1:
        math_question = st.text_area("题目内容", placeholder="粘贴或输入数学题目……", height=100)
    with col2:
        math_answer = st.text_area("参考答案 / 关键步骤（选填）", placeholder="标准答案或解题关键步骤……", height=100)
    st.divider()

# Input method tabs
st.subheader("📄 作业内容")
tab_upload, tab_paste = st.tabs(["📁 上传文件", "✏️ 粘贴文本"])

homework_text = ""
with tab_upload:
    uploaded = st.file_uploader("上传作业文件", type=["txt", "docx", "pdf"], label_visibility="collapsed")
    if uploaded:
        homework_text = read_uploaded_file(uploaded)
        st.success(f"已读取：{uploaded.name}（{len(homework_text)} 字符）")
        with st.expander("预览文本"):
            st.text(homework_text[:1000] + ("……" if len(homework_text) > 1000 else ""))

with tab_paste:
    pasted = st.text_area("在此粘贴作业内容", height=200, placeholder="直接粘贴文字……", label_visibility="collapsed")
    if pasted.strip():
        homework_text = pasted

# Submit
st.divider()
submit = st.button("🚀 开始批改", type="primary", use_container_width=True)

if submit:
    if not api_key:
        st.error("请在侧边栏填写 API Key。")
    elif not homework_text.strip():
        st.error("请上传文件或粘贴作业内容。")
    elif subject == "数学" and not math_question.strip():
        st.error("请填写数学题目内容。")
    else:
        with st.spinner("正在批改，请稍候……"):
            try:
                prompt = build_prompt(subject, homework_text, math_question, math_answer)
                raw_response = call_model(model_name, prompt, api_key)
                markdown_output = render_result(raw_response)
            except Exception as e:
                st.error(f"调用模型出错：{e}")
                st.stop()

        st.divider()
        st.subheader("📊 批改结果")
        st.markdown(markdown_output)

        with st.expander("查看原始 JSON 响应"):
            st.code(raw_response, language="json")
