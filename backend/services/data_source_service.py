"""
Data Source Service — 数据源读取服务层

统一 CSV/JSON/inline 数据读取，返回标准化 DataSourceResult。
供 Data Agent 及其他需要数据读取的模块使用。

数据源优先级：
  1. file_path（CSV/JSON 文件路径）
  2. url（远程 CSV/JSON URL）
  3. content / data / rows（内联数据）

返回：
  DataSourceResult(
    ok=True/False,
    df=pandas.DataFrame or None,
    source_type="csv" | "json" | "inline" | "none",
    row_count=int,
    col_count=int,
    columns=list[str],
    file_name=str,
    error=str or None,
  )
"""
import json
import logging
import os
import io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

URL_READ_TIMEOUT_SECONDS = 15
MAX_REMOTE_BYTES = 10 * 1024 * 1024

# 尝试导入 pandas
try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


@dataclass
class DataSourceResult:
    """数据源读取结果"""
    ok: bool = False
    df: Any = None  # pandas.DataFrame or None
    source_type: str = "none"  # csv / json / inline / none
    row_count: int = 0
    col_count: int = 0
    columns: List[str] = field(default_factory=list)
    file_name: str = ""
    error: Optional[str] = None


def load_csv(file_path: str) -> DataSourceResult:
    """
    读取 CSV 文件。

    Args:
        file_path: CSV 文件路径

    Returns:
        DataSourceResult
    """
    if not PANDAS_AVAILABLE:
        return DataSourceResult(ok=False, error="pandas 未安装，请运行: pip install pandas")

    if not os.path.exists(file_path):
        return DataSourceResult(ok=False, error=f"文件不存在: {file_path}")

    try:
        df = pd.read_csv(file_path, encoding="utf-8")
        return DataSourceResult(
            ok=True,
            df=df,
            source_type="csv",
            row_count=len(df),
            col_count=len(df.columns),
            columns=list(df.columns),
            file_name=os.path.basename(file_path),
        )
    except UnicodeDecodeError:
        # 尝试 GBK 编码
        try:
            df = pd.read_csv(file_path, encoding="gbk")
            return DataSourceResult(
                ok=True,
                df=df,
                source_type="csv",
                row_count=len(df),
                col_count=len(df.columns),
                columns=list(df.columns),
                file_name=os.path.basename(file_path),
            )
        except Exception as e:
            return DataSourceResult(ok=False, error=f"CSV 读取失败（尝试 utf-8 和 gbk）: {e}")
    except Exception as e:
        return DataSourceResult(ok=False, error=f"CSV 读取失败: {e}")


def load_json(file_path: str) -> DataSourceResult:
    """
    读取 JSON 文件（数组格式 → DataFrame）。

    Args:
        file_path: JSON 文件路径

    Returns:
        DataSourceResult
    """
    if not PANDAS_AVAILABLE:
        return DataSourceResult(ok=False, error="pandas 未安装，请运行: pip install pandas")

    if not os.path.exists(file_path):
        return DataSourceResult(ok=False, error=f"文件不存在: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict):
            # 尝试常见的嵌套结构
            if "data" in raw and isinstance(raw["data"], list):
                df = pd.DataFrame(raw["data"])
            elif "rows" in raw and isinstance(raw["rows"], list):
                df = pd.DataFrame(raw["rows"])
            elif "items" in raw and isinstance(raw["items"], list):
                df = pd.DataFrame(raw["items"])
            else:
                # 单条记录 → 单行 DataFrame
                df = pd.DataFrame([raw])
        else:
            return DataSourceResult(ok=False, error=f"JSON 格式不支持: 期望数组或对象，实际 {type(raw).__name__}")

        return DataSourceResult(
            ok=True,
            df=df,
            source_type="json",
            row_count=len(df),
            col_count=len(df.columns),
            columns=list(df.columns),
            file_name=os.path.basename(file_path),
        )
    except json.JSONDecodeError as e:
        return DataSourceResult(ok=False, error=f"JSON 解析失败: {e}")
    except Exception as e:
        return DataSourceResult(ok=False, error=f"JSON 读取失败: {e}")


def load_inline(data: Any) -> DataSourceResult:
    """
    读取内联数据（字符串或列表）。

    支持格式：
      - JSON 字符串（数组或对象）
      - CSV 字符串
      - Python list[dict]

    Args:
        data: 内联数据

    Returns:
        DataSourceResult
    """
    if not PANDAS_AVAILABLE:
        return DataSourceResult(ok=False, error="pandas 未安装，请运行: pip install pandas")

    if not data:
        return DataSourceResult(ok=False, error="内联数据为空")

    try:
        # 已经是 list[dict]
        if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            df = pd.DataFrame(data)
            return DataSourceResult(
                ok=True,
                df=df,
                source_type="inline",
                row_count=len(df),
                col_count=len(df.columns),
                columns=list(df.columns),
                file_name="inline_data",
            )

        # 字符串
        if isinstance(data, str):
            data = data.strip()
            if not data:
                return DataSourceResult(ok=False, error="内联数据字符串为空")

            # 尝试 JSON
            if data.startswith("[") or data.startswith("{"):
                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, list):
                        df = pd.DataFrame(parsed)
                    elif isinstance(parsed, dict):
                        # 嵌套结构
                        for key in ("data", "rows", "items"):
                            if key in parsed and isinstance(parsed[key], list):
                                df = pd.DataFrame(parsed[key])
                                break
                        else:
                            df = pd.DataFrame([parsed])
                    else:
                        return DataSourceResult(ok=False, error=f"JSON 值类型不支持: {type(parsed).__name__}")

                    return DataSourceResult(
                        ok=True,
                        df=df,
                        source_type="inline",
                        row_count=len(df),
                        col_count=len(df.columns),
                        columns=list(df.columns),
                        file_name="inline_data",
                    )
                except json.JSONDecodeError:
                    pass  # 不是 JSON，继续尝试 CSV

            # 尝试 CSV
            import io
            df = pd.read_csv(io.StringIO(data))
            return DataSourceResult(
                ok=True,
                df=df,
                source_type="inline",
                row_count=len(df),
                col_count=len(df.columns),
                columns=list(df.columns),
                file_name="inline_data",
            )

        return DataSourceResult(ok=False, error=f"不支持的数据类型: {type(data).__name__}")

    except Exception as e:
        return DataSourceResult(ok=False, error=f"内联数据读取失败: {e}")


def load_url(url: str) -> DataSourceResult:
    """
    读取远程 CSV/JSON URL。

    Args:
        url: 远程数据 URL

    Returns:
        DataSourceResult
    """
    if not PANDAS_AVAILABLE:
        return DataSourceResult(ok=False, error="pandas 未安装，请运行: pip install pandas")

    if not url:
        return DataSourceResult(ok=False, error="URL 为空")

    try:
        try:
            import requests
        except ImportError:
            return DataSourceResult(ok=False, error="requests 未安装，无法读取远程 URL")

        resp = requests.get(url, timeout=URL_READ_TIMEOUT_SECONDS)
        resp.raise_for_status()
        content = resp.content
        if len(content) > MAX_REMOTE_BYTES:
            return DataSourceResult(ok=False, error=f"URL 数据超过大小限制: {MAX_REMOTE_BYTES} bytes")

        text = content.decode(resp.encoding or "utf-8", errors="replace")
        lowered_url = url.lower()
        content_type = resp.headers.get("content-type", "").lower()

        if lowered_url.endswith(".json") or "json" in content_type:
            raw = json.loads(text)
            if isinstance(raw, list):
                df = pd.DataFrame(raw)
            elif isinstance(raw, dict):
                for key in ("data", "rows", "items"):
                    if key in raw and isinstance(raw[key], list):
                        df = pd.DataFrame(raw[key])
                        break
                else:
                    df = pd.DataFrame([raw])
            else:
                return DataSourceResult(ok=False, error=f"JSON 值类型不支持: {type(raw).__name__}")
            source_type = "json"
        else:
            df = pd.read_csv(io.StringIO(text))
            source_type = "csv"

        file_name = url.split("/")[-1] or "remote_data"
        return DataSourceResult(
            ok=True,
            df=df,
            source_type=source_type,
            row_count=len(df),
            col_count=len(df.columns),
            columns=list(df.columns),
            file_name=file_name,
        )
    except Exception as e:
        return DataSourceResult(ok=False, error=f"URL 数据读取失败: {e}")


def detect_and_load(task: Dict[str, Any]) -> DataSourceResult:
    """
    从 task 字典中自动检测数据源并加载。

    检测优先级：
      1. file_path / path → 文件读取
      2. url → 远程读取
      3. content / data / rows → 内联读取
      4. context.file_path / context.data → 从 context 中提取
      5. input.file_path / input.data → 从 input 中提取

    Args:
        task: 任务字典（来自 AgentTask 的 context + input 合并）

    Returns:
        DataSourceResult
    """
    # 1. 直接字段
    file_path = task.get("file_path", task.get("path", ""))
    url = task.get("url", "")
    content = task.get("content", task.get("data", task.get("rows", "")))

    # 2. 从 context/input 中提取
    ctx = task.get("context", {})
    inp = task.get("input", {})
    if not file_path:
        file_path = ctx.get("file_path", ctx.get("path", inp.get("file_path", inp.get("path", ""))))
    if not url:
        url = ctx.get("url", inp.get("url", ""))
    if not content:
        content = ctx.get("content", ctx.get("data", ctx.get("rows",
                    inp.get("content", inp.get("data", inp.get("rows", ""))))))

    # 3. 按优先级尝试加载
    if file_path:
        ext = os.path.splitext(str(file_path))[1].lower()
        if ext == ".csv":
            return load_csv(str(file_path))
        elif ext == ".json":
            return load_json(str(file_path))
        elif ext in (".xlsx", ".xls"):
            # 交给 DataAgent 原有的 pandas 路径处理
            return DataSourceResult(ok=False, error="xlsx/xls 由 DataAgent 原有路径处理")
        elif ext == ".tsv":
            if not PANDAS_AVAILABLE:
                return DataSourceResult(ok=False, error="pandas 未安装")
            try:
                import pandas as pd
                df = pd.read_csv(str(file_path), sep="\t")
                return DataSourceResult(
                    ok=True, df=df, source_type="csv",
                    row_count=len(df), col_count=len(df.columns),
                    columns=list(df.columns), file_name=os.path.basename(str(file_path)),
                )
            except Exception as e:
                return DataSourceResult(ok=False, error=f"TSV 读取失败: {e}")
        elif ext == ".parquet":
            if not PANDAS_AVAILABLE:
                return DataSourceResult(ok=False, error="pandas 未安装")
            try:
                import pandas as pd
                df = pd.read_parquet(str(file_path))
                return DataSourceResult(
                    ok=True, df=df, source_type="csv",
                    row_count=len(df), col_count=len(df.columns),
                    columns=list(df.columns), file_name=os.path.basename(str(file_path)),
                )
            except Exception as e:
                return DataSourceResult(ok=False, error=f"Parquet 读取失败: {e}")
        else:
            return DataSourceResult(ok=False, error=f"不支持的文件格式: {ext}")

    if url:
        return load_url(str(url))

    if content:
        return load_inline(content)

    return DataSourceResult(ok=False, error="未检测到数据源")
