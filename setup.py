"""py2app build config — produces codesync.app.

Build:  .venv/bin/python setup.py py2app
The GUI (Tkinter) and the login window (PyObjC WebKit) live in one bundle; the
app relaunches itself in a 'login' role for the WebKit window.
"""
from setuptools import setup

from app.constants import VERSION

APP = ["app_main.py"]

OPTIONS = {
    "argv_emulation": False,
    "iconfile": "dist_icon/AppIcon.icns",
    "packages": [
        "codesync", "app",
        "requests", "urllib3", "idna", "certifi", "charset_normalizer",
        "bs4", "soupsieve", "html2text", "yaml",
    ],
    # PyObjC frameworks used by the native login window.
    "includes": ["objc", "Foundation", "Cocoa", "WebKit", "tkinter"],
    "plist": {
        "CFBundleName": "CodeSync",
        "CFBundleDisplayName": "CodeSync",
        "CFBundleIdentifier": "com.harshbajpai.codesync",
        "CFBundleShortVersionString": VERSION,
        "CFBundleVersion": VERSION,
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
        # The app opens external login pages; no special entitlements needed unsigned.
    },
}

setup(
    app=APP,
    name="codesync",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
