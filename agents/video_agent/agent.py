"""
Video Agent — 视频创意智能体（轻量版）

能力：
1. video_script: 视频脚本生成（纯文本 AI）
2. video_storyboard: 分镜脚本
3. video_idea: 视频创意点子
4. video_generate: 视频生成占位（API 就绪后对接 Sora/Runway/Pika）
"""
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER


VIDEO_SCRIPT_PROMPT = """你是一位专业视频脚本编剧。根据需求生成完整的视频脚本。

输出格式（JSON）：
{
  "title": "视频标题",
  "duration": "预估时长（秒）",
  "platform": "YouTube|抖音|B站|TikTok|Instagram",
  "format": "tutorial|vlog|review|short|commercial|documentary",
  "hook": "前3秒抓人开头",
  "scenes": [
    {
      "scene_number": 1,
      "duration": 15,
      "visual": "画面描述（镜头/构图/动作）",
      "audio": "旁白/对话/背景音乐",
      "text_overlay": "屏幕文字",
      "transition": "切换方式"
    }
  ],
  "cta": "结尾行动号召",
  "equipment_notes": "拍摄设备建议"
}

只输出 JSON，不要其他文字。"""

STORYBOARD_PROMPT = """你是一位专业分镜师。为视频生成详细的分镜脚本。

输出格式（JSON）：
{
  "title": "分镜标题",
  "total_scenes": 8,
  "aspect_ratio": "16:9",
  "scenes": [
    {
      "scene": 1,
      "shot_type": "wide|medium|close-up|extreme_close-up|aerial|tracking",
      "camera_angle": "eye_level|low_angle|high_angle|dutch_angle",
      "duration": 5,
      "description": "画面内容详细描述",
      "dialogue": "台词",
      "notes": "导演备注"
    }
  ]
}

只输出 JSON，不要其他文字。"""

VIDEO_IDEA_PROMPT = """你是一位创意总监。为视频内容提供创意点子。

输出格式（JSON）：
{
  "title": "创意主题",
  "hook": "一句话抓人",
  "concept": "核心创意概念",
  "target_audience": "目标观众",
  "viral_potential": "low|medium|high",
  "why_it_works": "为什么这个创意有效",
  "similar_examples": ["参考视频1", "参考视频2"],
  "production_difficulty": "low|medium|high"
}

只输出 JSON，不要其他文字。"""


class VideoAgent(BaseAgent):
    """Video Agent — 视频创意与脚本"""

    AGENT_ID = "video"
    DISPLAY_NAME = "视频创意"
    CAPABILITIES = ["video", "script", "storyboard"]
    TASK_TYPES = ["video_script", "video_storyboard", "video_idea"]

    PROMPTS = {
        "video_script": VIDEO_SCRIPT_PROMPT,
        "video_storyboard": STORYBOARD_PROMPT,
        "video_idea": VIDEO_IDEA_PROMPT,
    }

    def __init__(self, api_key: Optional[str] = None, timeout: int = 60):
        super().__init__(name="video", timeout=timeout)
        try:
            config = get_ai_config()
            self.api_key = api_key or config["api_key"]
            self.model = config["model"]
            self.api_base = config["base_url"]
        except RuntimeError:
            self.api_key = ""
            self.model = "deepseek-chat"
            self.api_base = "https://api.deepseek.com"

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"vid_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "video_script")
        goal = task.get("goal", "")
        prompt = task.get("prompt", task.get("video_brief", goal))

        if not prompt:
            return self._result(task_id, "失败", "缺少视频内容需求描述", {})

        # video_generate 当前不可用
        if task_type == "video_generate":
            return self._result(task_id, "暂不支持",
                "视频生成 API（Sora/Runway/Pika）尚未集成。\n可用的替代方案：\n"
                "1. 使用 video_script 先生成脚本\n2. 使用 video_storyboard 生成分镜\n"
                "3. 将脚本导入 RunwayML (https://runwayml.com) 生成视频",
                {"available_alternatives": ["video_script", "video_storyboard", "video_idea"]})

        sys_prompt = self.PROMPTS.get(task_type, VIDEO_SCRIPT_PROMPT)

        if self.api_key:
            ai_result = self._call_ai(sys_prompt, prompt)
            if ai_result:
                ai_result["content_type"] = task_type
                return self._result(
                    task_id, "生成完成",
                    self._extract_summary(task_type, ai_result),
                    ai_result,
                )

        return self._rule_fallback(task_id, task_type, prompt)

    def _call_ai(self, system_prompt: str, user_prompt: str) -> Optional[Dict]:
        try:
            import urllib.request

            if AI_PROVIDER == "claude":
                payload = json.dumps({
                    "model": self.model, "max_tokens": 3000,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/v1/messages",
                    data=payload,
                    headers={"Content-Type": "application/json",
                             "x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["content"][0]["text"]
            else:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.8, "max_tokens": 3000,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base.rstrip('/')}/chat/completions",
                    data=payload,
                    headers={"Content-Type": "application/json",
                             "Authorization": f"Bearer {self.api_key}"},
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    text = body["choices"][0]["message"]["content"]

            return self._extract_json(text)
        except Exception as e:
            print(f"[Video Agent] AI 调用失败: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try: return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{[\s\S]*\}", text)
            if m:
                try: return json.loads(m.group())
                except json.JSONDecodeError: pass
        return None

    @staticmethod
    def _extract_summary(task_type: str, data: Dict) -> str:
        if task_type == "video_script":
            return data.get("title", "脚本已生成")
        elif task_type == "video_storyboard":
            return f"分镜脚本: {data.get('total_scenes', '?')} 个镜头"
        elif task_type == "video_idea":
            return data.get("title", data.get("hook", "创意已生成"))
        return "视频内容已生成"

    def _rule_fallback(self, task_id: str, task_type: str, prompt: str) -> Dict:
        topic = prompt[:40]
        if task_type == "video_script":
            data = {
                "title": f"{topic}",
                "duration": "60-90秒",
                "scenes": [
                    {"scene_number": 1, "duration": 15, "visual": "开场引入话题",
                     "audio": f"今天我们来聊聊{topic}", "text_overlay": topic},
                    {"scene_number": 2, "duration": 30, "visual": "核心内容展示",
                     "audio": f"关于{topic}的关键点...#1 #2 #3"},
                    {"scene_number": 3, "duration": 15, "visual": "总结+CTA",
                     "audio": "想看更多？点赞关注！"},
                ],
                "mode": "template_fallback",
            }
        elif task_type == "video_storyboard":
            data = {
                "total_scenes": 6,
                "scenes": [
                    {"scene": 1, "shot_type": "wide", "description": "主题引入，环境建立"},
                    {"scene": 2, "shot_type": "medium", "description": f"核心内容: {topic}"},
                    {"scene": 3, "shot_type": "close-up", "description": "细节/情感放大"},
                ],
                "mode": "template_fallback",
            }
        else:
            data = {
                "title": f"关于{topic}的视频创意",
                "concept": f"用故事化的方式讲解{topic}",
                "viral_potential": "medium",
                "mode": "template_fallback",
            }

        return self._result(
            task_id, f"生成完成（模板模式）",
            f"使用模板生成{task_type}。配置 AI API Key 获得智能定制。",
            data,
        )

    def _result(self, task_id: str, status: str, summary: str,
                data: Dict = None) -> Dict:
        return {
            "task_id": task_id, "agent": "video_agent",
            "agent_name": "Video 视频创意",
            "status": status, "summary": summary,
            "result": summary, "data": data or {}, "output": data or {},
        }
