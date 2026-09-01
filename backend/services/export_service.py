"""报告导出服务 — PDF / CSV / Markdown 导出"""
import csv
import io
import json
import os
from datetime import datetime
from typing import Dict, List, Optional


def _get_html_header(title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title>
<style>
body {{ font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #1a1a1a; }}
h1 {{ font-size: 24px; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }}
h2 {{ font-size: 18px; margin-top: 24px; color: #2563eb; }}
.step {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px 16px; margin: 8px 0; }}
.step-done {{ border-left: 4px solid #22c55e; }}
.step-fail {{ border-left: 4px solid #ef4444; }}
.agent {{ font-size: 12px; color: #64748b; }}
.summary {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 16px; white-space: pre-wrap; }}
.tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
.tag-success {{ background: #dcfce7; color: #16a34a; }}
.tag-fail {{ background: #fce7e7; color: #dc2626; }}
.footer {{ margin-top: 40px; font-size: 12px; color: #94a3b8; text-align: center; }}
</style></head><body>
"""


def _get_html_footer():
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    return f'<div class="footer">由 AI Company OS 生成 · {now}</div></body></html>'


def export_session_as_html(session: Dict, steps: List[Dict], summary: str) -> str:
    """将执行结果导出为 HTML 报告"""
    goal = session.get("goal", "未命名任务")
    status = session.get("status", "unknown")

    html = _get_html_header(f"执行报告: {goal}")
    html += f'<h1>📋 执行报告: {goal}</h1>'
    html += f'<p>状态: <span class="tag {"tag-success" if status=="completed" else "tag-fail"}">{status}</span></p>'
    html += f'<p>会话: {session.get("session_id", "")[:16]}...</p>'

    if summary:
        html += "<h2>📊 结果概览</h2>"
        lines = summary.split("\n")
        html += '<div class="summary">'
        for line in lines:
            t = line.strip()
            if not t:
                html += "<br>"
            elif t.startswith("✅") or t.startswith("❌"):
                html += f"<p><b>{t}</b></p>"
            elif t.startswith("- ") or t.startswith("• "):
                html += f"<p style='padding-left:12px;margin:2px 0'>{t}</p>"
            else:
                html += f"<p>{t}</p>"
        html += "</div>"

    if steps:
        html += "<h2>📌 执行步骤</h2>"
        for s in steps:
            agent = s.get("assigned_agent", "?")
            desc = s.get("description", "")
            st = s.get("status", "")
            cls = "step-done" if st == "completed" else "step-fail"
            html += f'<div class="step {cls}">'
            html += f'<div><b>🤖 {agent}</b>: {desc}</div>'
            html += f'<div class="agent">状态: {st}</div>'
            if s.get("result_summary"):
                html += f'<div class="agent">{s["result_summary"][:100]}</div>'
            html += "</div>"

    html += _get_html_footer()
    return html


def export_session_as_csv(session: Dict, steps: List[Dict], summary: str) -> str:
    """将执行结果导出为 CSV"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["字段", "值"])
    writer.writerow(["目标", session.get("goal", "")])
    writer.writerow(["状态", session.get("status", "")])
    writer.writerow(["会话 ID", session.get("session_id", "")])
    writer.writerow(["创建时间", session.get("created_at", "")])
    writer.writerow(["完成时间", session.get("completed_at", "")])
    writer.writerow([])
    writer.writerow(["步骤", "Agent", "描述", "状态", "结果摘要"])
    for i, s in enumerate(steps, 1):
        writer.writerow([
            i,
            s.get("assigned_agent", ""),
            s.get("description", ""),
            s.get("status", ""),
            s.get("result_summary", "")[:200],
        ])
    return output.getvalue()


def export_session_as_json(session: Dict, steps: List[Dict], summary: str) -> str:
    """将执行结果导出为 JSON"""
    return json.dumps({
        "session": {k: v for k, v in session.items() if k != "summary"},
        "summary": summary,
        "steps": steps,
        "exported_at": datetime.now().isoformat(),
    }, ensure_ascii=False, indent=2)
