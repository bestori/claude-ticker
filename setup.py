from setuptools import setup

APP = ["app.py"]
OPTIONS = {
    "argv_emulation": False,
    "packages": [
        "requests",
        "certifi",
        "browser_cookie3",
        "objc",
        "AppKit",
        "Foundation",
        "WebKit",
        "Crypto",
    ],
    "includes": ["sqlite3"],
    "excludes": ["tkinter", "rumps", "matplotlib", "numpy"],
    "plist": {
        "CFBundleName": "ClaudeTicker",
        "CFBundleDisplayName": "Claude Ticker",
        "CFBundleIdentifier": "com.user.claude-ticker",
        "CFBundleVersion": "1.1.0",
        "CFBundleShortVersionString": "1.1",
        "LSUIElement": True,
        "NSAppleEventsUsageDescription": (
            "Claude Ticker reads browser cookies for authentication."
        ),
        "NSKeychainUsageDescription": (
            "Claude Ticker decrypts browser cookies to authenticate with claude.ai."
        ),
    },
}

setup(
    name="ClaudeTicker",
    app=APP,
    data_files=[],
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
