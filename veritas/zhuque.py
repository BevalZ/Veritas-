"""Tencent Zhuque AI text detector helper flow."""

import platform
import subprocess
import webbrowser

ZHUQUE_URL = "https://matrix.tencent.com/ai-detect/"

__all__ = ["ZHUQUE_URL", "copy_to_clipboard_from_namespace", "launch_zhuque_ai_detect_from_namespace"]


def _namespace_value(namespace, name, default=None):
    return (namespace or {}).get(name, default)


def copy_to_clipboard_from_namespace(namespace, text: str) -> bool:
    """Copy text to the system clipboard across supported desktop platforms."""
    platform_module = _namespace_value(namespace, "platform", platform)
    subprocess_module = _namespace_value(namespace, "subprocess", subprocess)
    system = platform_module.system()
    try:
        if system == "Windows":
            process = subprocess_module.Popen(
                ["clip.exe"],
                stdin=subprocess_module.PIPE,
            )
            process.communicate(text.encode("utf-16"))
            return process.returncode == 0
        if system == "Darwin":
            process = subprocess_module.Popen(
                ["pbcopy"],
                stdin=subprocess_module.PIPE,
            )
            process.communicate(text.encode("utf-8"))
            return process.returncode == 0
        for cmd in [["xclip", "-selection", "clipboard"], ["xsel", "--clipboard", "--input"]]:
            try:
                process = subprocess_module.Popen(cmd, stdin=subprocess_module.PIPE)
                process.communicate(text.encode("utf-8"))
                if process.returncode == 0:
                    return True
            except FileNotFoundError:
                continue
        return False
    except Exception as e:
        print(f"⚠️ 剪贴板写入失败: {e}")
        return False


def launch_zhuque_ai_detect_from_namespace(namespace, text: str):
    """Open Zhuque AI text detector after copying a bounded text sample."""
    copy_to_clipboard = _namespace_value(namespace, "copy_to_clipboard")
    webbrowser_module = _namespace_value(namespace, "webbrowser", webbrowser)
    platform_module = _namespace_value(namespace, "platform", platform)
    subprocess_module = _namespace_value(namespace, "subprocess", subprocess)
    zhuque_url = _namespace_value(namespace, "ZHUQUE_URL", ZHUQUE_URL)
    input_func = _namespace_value(namespace, "input", input)
    if not callable(copy_to_clipboard):
        copy_to_clipboard = lambda value: copy_to_clipboard_from_namespace(namespace, value)

    print("\n" + "=" * 60)
    print("🤖 腾讯朱雀AI文本检测")
    print("=" * 60)

    detect_text = text[:8000]
    if len(text) > 8000:
        print(f"⚠️ 文本较长({len(text)}字符)，仅复制前8000字符到剪贴板（朱雀字数限制）")

    clip_ok = copy_to_clipboard(detect_text)
    if clip_ok:
        print("✅ 文本已复制到剪贴板")
    else:
        print("❌ 剪贴板写入失败，请手动复制论文文本")

    print(f"🌐 正在打开朱雀AI检测页面...")
    webbrowser_module.open(zhuque_url)

    system = platform_module.system()
    try:
        if system == "Windows":
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                "论文文本已复制到剪贴板！\n\n"
                "请在打开的朱雀AI检测页面中粘贴文本并点击检测。\n"
                "检测完成后，点击确定继续后续审查流程。",
                "🤖 朱雀AI文本检测",
                0x40,
            )
        elif system == "Darwin":
            subprocess_module.run([
                "osascript", "-e",
                'display dialog "论文文本已复制到剪贴板！\n\n请在朱雀AI检测页面中粘贴文本并点击检测。\n检测完成后，点击确定继续后续审查流程。" '
                'buttons {"确定"} default button "确定" with title "🤖 朱雀AI文本检测" with icon note',
            ])
        else:
            try:
                subprocess_module.run([
                    "zenity", "--info", "--title=🤖 朱雀AI文本检测", "--width=400",
                    "--text=论文文本已复制到剪贴板！\n\n请在朱雀AI检测页面中粘贴文本并点击检测。\n检测完成后，点击确定继续后续审查流程。",
                ])
            except FileNotFoundError:
                input_func("\n⏸️ 论文文本已复制到剪贴板，请在浏览器中粘贴检测。\n检测完成后按回车继续...")
    except Exception:
        input_func("\n⏸️ 论文文本已复制到剪贴板，请在浏览器中粘贴检测。\n检测完成后按回车继续...")

    print("✅ 朱雀AI检测流程结束，继续后续审查...")
