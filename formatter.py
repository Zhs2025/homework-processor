import json
from typing import Any

Args = Any
Output = Any


async def main(args: Args) -> Output:
    params = args.params
    raw_str = params['input']
    markdown_result = ""

    try:
        raw_data = json.loads(raw_str)

        # ── 顶层失败熔断处理 ──────────────────────────────────────────────
        if not raw_data.get("success", True):
            error_msg = raw_data.get("error_message", "未知错误")
            subject   = raw_data.get("metadata", {}).get("subject", "")
            label_map = {"chinese": "语文", "math": "数学", "english": "英语"}
            subject_label = label_map.get(subject, subject or "作业")
            markdown_result = "\n".join([
                f"## ❌ {subject_label}批改失败",
                "",
                f"> **错误原因**：{error_msg}",
                "",
                "请检查输入内容是否与所选学科匹配，或重新提交。",
            ])
            return {"formatted_text": markdown_result}

        # ── 提取 data 与 subject ──────────────────────────────────────────
        data = raw_data.get("data", {}) or {}
        subject = raw_data.get("metadata", {}).get("subject", "")

        # ── 按学科分支渲染 ────────────────────────────────────────────────
        if subject == "chinese":
            markdown_result = _render_chinese(data)
        elif subject == "math":
            markdown_result = _render_math(data)
        elif subject == "english":
            markdown_result = _render_english(data)
        else:
            markdown_result = f"```json\n{json.dumps(raw_data, ensure_ascii=False, indent=2)}\n```"

    except Exception:
        markdown_result = raw_str

    return {"formatted_text": markdown_result}


def _render_chinese(data: dict) -> str:
    is_melted   = data.get("is_melted", False)
    fact_errors = data.get("fact_errors_found", [])
    total_score = data.get("total_score", 0)
    dims        = data.get("dimensions", {})
    suggestions = data.get("overall_suggestion", [])

    lines = ["## 📝 语文批改反馈报告", ""]

    if is_melted:
        lines += ["> ⚠️ **前置熔断触发**：本篇作文存在严重偏题、内容空洞或疑似抄袭，已终止常规评分流程。", ""]

    lines += [f"* **📊 综合总分**：{total_score} / 100", "", "---", ""]

    dim_config = [
        ("emotional_understanding",  "情感主旨理解",  40),
        ("detail_analysis",          "关键细节剖析",  30),
        ("expression_and_resonance", "联想表达与文风", 20),
        ("structure_and_grammar",    "结构与行文规范", 10),
    ]
    lines += ["### 📐 四维评分详情", "", "| 维度 | 满分 | 得分 | 点评 |", "| :--- | :---: | :---: | :--- |"]
    for key, label, full in dim_config:
        dim     = dims.get(key, {})
        score   = dim.get("score", "-")
        comment = dim.get("comment", "暂无点评").replace("|", "｜")
        lines.append(f"| {label} | {full} | {score} | {comment} |")
    lines.append("")

    if fact_errors:
        lines += ["### 🚨 事实性错误", ""]
        for err in fact_errors:
            lines.append(f"* ❌ {err}")
        lines.append("")

    if suggestions:
        lines += ["### 🚀 修改建议", ""]
        for i, sug in enumerate(suggestions, 1):
            lines.append(f"{i}. {sug}")
        lines.append("")

    return "\n".join(lines)


def _render_math(data: dict) -> str:
    is_correct         = data.get("is_correct", False)
    error_step         = data.get("error_step", "")
    error_reason       = data.get("error_reason", "")
    corrected_solution = data.get("corrected_solution", "")

    lines = ["## 📝 数学批改反馈报告", ""]

    if is_correct:
        lines += ["* **✅ 综合评定**：解题过程完全正确，逻辑严密！", ""]
    else:
        lines += [
            "* **❌ 综合评定**：解题过程存在错误，请参考以下分析。",
            "", "---", "",
            "### 🔍 错误定位", "",
            f"* **出错步骤**：{error_step or '（未能精确定位）'}",
            "",
            "### 🧐 错因深度分析", "",
            f"{error_reason or '（无详细分析）'}",
            "",
        ]
        if corrected_solution:
            lines += ["### ✏️ 正确推导步骤（从出错处起）", "", "```text", corrected_solution, "```", ""]

    return "\n".join(lines)


def _render_english(data: dict) -> str:
    word_count     = data.get("word_count", 0)
    grammar_errors = data.get("grammar_errors", [])
    native_sug     = data.get("native_suggestions", [])
    polished_essay = data.get("polished_essay", "")

    lines = [
        "## 📝 英语批改反馈报告", "",
        f"* **📜 综合评定**：扫描完成（原文共 **{word_count}** 词）",
        "", "---", "",
        "### 🔍 语法错误诊断", "",
    ]

    if grammar_errors:
        for i, err in enumerate(grammar_errors, 1):
            lines += [
                f"{i}. **[{err.get('error_type', '语法错误')}]**",
                f"   * ❌ 原文：`{err.get('original', '')}`",
                f"   * ✅ 正确：`{err.get('corrected', '')}`",
                f"   * 💡 *错因：{err.get('explanation_zh', '')}*",
                "",
            ]
    else:
        lines += ["> ✅ 未发现明显语法错误。", ""]

    lines += ["### 🌟 母语地道化润色建议", ""]
    if native_sug:
        for sug in native_sug:
            lines += [
                f"* 🔸 **原句**：`{sug.get('original_sentence', '')}`",
                f"  * 🎯 **地道表达**：**{sug.get('better_alternative', '')}**",
                f"  * 💡 *润色理由：{sug.get('reason_zh', '')}*",
                "",
            ]
    else:
        lines += ["> 语句表达通顺，暂无润色建议。", ""]

    if polished_essay:
        lines += ["### 📄 全篇润色最终版", "", "```text", polished_essay, "```", ""]

    return "\n".join(lines)