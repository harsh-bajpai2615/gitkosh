"""Native macOS login window (WebKit) — no Playwright, no Chromium.

Run standalone:  python -m app.login_helper --out <storage_state.json> --platforms leetcode,codeforces

Opens a real WKWebView using the system cookie store. You log into each site,
then click "Save & Finish"; cookies are written to <out> in the same
{"cookies": [...]} shape the extractors consume, and the helper exits.
"""
from __future__ import annotations

import argparse
import json
import sys

import objc
from Cocoa import (
    NSApplication, NSObject, NSWindow, NSButton, NSView, NSMakeRect,
    NSBackingStoreBuffered, NSApplicationActivationPolicyRegular,
    NSViewWidthSizable, NSViewHeightSizable, NSViewMaxYMargin,
)
from Foundation import NSURL, NSURLRequest
from WebKit import WKWebView, WKWebViewConfiguration, WKWebsiteDataStore

LOGIN_URLS = {
    "leetcode": "https://leetcode.com/accounts/login/",
    "codeforces": "https://codeforces.com/enter",
    "codechef": "https://www.codechef.com/login",
    "neetcode": "https://neetcode.io/",
    "atcoder": "https://atcoder.jp/login",
    "geeksforgeeks": "https://www.geeksforgeeks.org/",
}

# Window style mask: titled | closable | resizable | miniaturizable = 1|2|4|8
_STYLE = 1 | 2 | 4 | 8


class LoginDelegate(NSObject):
    def initWithPlatforms_out_(self, platforms, out_path):
        self = objc.super(LoginDelegate, self).init()
        if self is None:
            return None
        self.platforms = platforms or ["leetcode"]
        self.out_path = out_path
        self.window = None
        self.webview = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        rect = NSMakeRect(0, 0, 1100, 800)
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, _STYLE, NSBackingStoreBuffered, False
        )
        self.window.setTitle_("GitKosh — log in, then click Save & Finish")
        self.window.center()
        content = self.window.contentView()

        bar_h = 44.0
        cfg = WKWebViewConfiguration.alloc().init()
        cfg.setWebsiteDataStore_(WKWebsiteDataStore.defaultDataStore())
        web_rect = NSMakeRect(0, bar_h, rect.size.width, rect.size.height - bar_h)
        self.webview = WKWebView.alloc().initWithFrame_configuration_(web_rect, cfg)
        self.webview.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        content.addSubview_(self.webview)

        # bottom bar: one button per platform + Save & Finish
        x = 10.0
        for i, name in enumerate(self.platforms):
            b = NSButton.alloc().initWithFrame_(NSMakeRect(x, 8, 130, 28))
            b.setTitle_(f"Open {name}")
            b.setBezelStyle_(1)
            b.setTag_(i)
            b.setTarget_(self)
            b.setAction_("openPlatform:")
            b.setAutoresizingMask_(NSViewMaxYMargin)
            content.addSubview_(b)
            x += 138

        done = NSButton.alloc().initWithFrame_(NSMakeRect(rect.size.width - 170, 8, 160, 28))
        done.setTitle_("Save & Finish")
        done.setBezelStyle_(1)
        done.setKeyEquivalent_("\r")
        done.setTarget_(self)
        done.setAction_("saveAndFinish:")
        done.setAutoresizingMask_(1 << 0)  # NSViewMinXMargin (stick to right edge)
        content.addSubview_(done)

        self.window.makeKeyAndOrderFront_(None)
        self._load(self.platforms[0])
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)

    @objc.python_method
    def _load(self, name):
        url = LOGIN_URLS.get(name)
        if url:
            self.webview.loadRequest_(NSURLRequest.requestWithURL_(NSURL.URLWithString_(url)))

    def openPlatform_(self, sender):
        self._load(self.platforms[sender.tag()])

    def saveAndFinish_(self, sender):
        store = WKWebsiteDataStore.defaultDataStore().httpCookieStore()

        def handler(cookies):
            out = []
            for c in cookies:
                out.append({
                    "name": str(c.name()),
                    "value": str(c.value()),
                    "domain": str(c.domain()),
                    "path": str(c.path()),
                    "secure": bool(c.isSecure()),
                })
            with open(self.out_path, "w") as f:
                json.dump({"cookies": out}, f, indent=2)
            print(f"Saved {len(out)} cookies to {self.out_path}")
            NSApplication.sharedApplication().terminate_(None)

        store.getAllCookies_(handler)


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--out", required=True)
    p.add_argument("--platforms", default="leetcode")
    args = p.parse_args(argv)
    platforms = [s.strip() for s in args.platforms.split(",") if s.strip()]

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    delegate = LoginDelegate.alloc().initWithPlatforms_out_(platforms, args.out)
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main(sys.argv[1:])
