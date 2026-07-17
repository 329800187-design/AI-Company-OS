"""
AI Company OS — 桌面应用入口

使用 PyWebView 创建独立窗口，不依赖浏览器。
"""
import os
import sys
import time
import threading
import webview

# 设置工作目录为脚本所在目录
if getattr(sys, 'frozen', False):
    # 打包后的路径
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

os.chdir(BASE_DIR)

# 全局变量
window = None
server_ready = False


def start_backend():
    """启动 FastAPI 后端"""
    global server_ready

    try:
        import uvicorn
        from backend.app import app

        # 标记服务器就绪
        server_ready = True

        # 启动服务器
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="warning",  # 减少日志输出
            access_log=False
        )
    except Exception as e:
        print(f"Backend error: {e}")
        server_ready = True  # 即使失败也标记为就绪，避免无限等待


def wait_for_server(timeout=30):
    """等待服务器启动"""
    import urllib.request

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
            return True
        except:
            time.sleep(0.5)
    return False


def on_closed():
    """窗口关闭时的清理"""
    # 强制退出程序
    os._exit(0)


def main():
    """主函数"""
    global window

    print("=" * 50)
    print("  AI Company OS v1.5.0")
    print("  Starting...")
    print("=" * 50)

    # 启动后端（后台线程）
    backend_thread = threading.Thread(target=start_backend, daemon=True)
    backend_thread.start()

    # 等待服务器启动
    print("Waiting for server to start...")
    if wait_for_server():
        print("Server started successfully!")
    else:
        print("Server startup timeout, continuing anyway...")

    # 创建窗口
    window = webview.create_window(
        title="AI Company OS",
        url="http://127.0.0.1:8000/app",
        width=1280,
        height=800,
        min_size=(1024, 600),
        resizable=True,
        fullscreen=False,
        frameless=False,
        easy_drag=False,
        text_select=True,
        confirm_close=True,
        on_top=False
    )

    # 窗口关闭事件
    window.events.closed += on_closed

    print("Opening window...")

    # 启动窗口（主线程）
    webview.start(debug=False)


if __name__ == "__main__":
    main()
