# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller 打包配置文件

使用方法：
    pyinstaller build.spec
"""

import os
import sys

# 项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(SPEC))

# 收集数据文件
datas = [
    # 前端静态文件
    (os.path.join(ROOT_DIR, 'backend', 'static-new'), 'backend/static-new'),
    # .env.example
    (os.path.join(ROOT_DIR, '.env.example'), '.'),
    # 配置文件
    (os.path.join(ROOT_DIR, 'backend', 'database'), 'backend/database'),
]

# 收集隐式导入
hiddenimports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'webview',
    'webview.platforms.edgechromium',
    'backend.app',
    'backend.config',
    'backend.database.database',
    'backend.routers',
    'agents.ceo_agent.agent',
    'agents.codex_agent.agent',
    'agents.qa_agent.agent',
    'agents.cto_agent.agent',
    'agents.system_agent.agent',
    'agents.openclaw_agent.agent',
    'agents.image_agent.agent',
    'agents.marketing_agent.agent',
    'agents.video_agent.agent',
    'agents.data_agent.agent',
]

a = Analysis(
    ['main.py'],
    pathex=[ROOT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'scipy',
        'test',
        'tests',
    ],
    noarchive=False,
    optimize=1,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AI-Company-OS',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ROOT_DIR, 'assets', 'icon.ico') if os.path.exists(os.path.join(ROOT_DIR, 'assets', 'icon.ico')) else None,
)
