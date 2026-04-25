"""
Playwright screenshot worker

NOTE: This script runs in a SEPARATE process to avoid
asyncio event loop conflicts with Streamlit.

Usage: python _playwright_worker.py <html_file> <output_png> <width>
"""
import sys

from playwright.sync_api import sync_playwright


def main():
    if len(sys.argv) < 4:
        print("Usage: _playwright_worker.py <html_file> <output_png> <width>", file=sys.stderr)
        sys.exit(1)

    html_file = sys.argv[1]
    output_png = sys.argv[2]
    page_width = int(sys.argv[3])

    # NOTE: use goto(file://) instead of set_content()
    # set_content() loads from about:blank which blocks file:// images
    from pathlib import Path
    file_uri = Path(html_file).as_uri()

    with sync_playwright() as p:
        browser = p.chromium.launch()
        # NOTE: device_scale_factor=2 生成 2x 高清截图，
        # 适合微信公众号/小红书等平台发布
        page = browser.new_page(
            viewport={"width": page_width, "height": 800},
            device_scale_factor=2,
        )

        # NOTE: goto file:// URI allows loading local images
        page.goto(file_uri, wait_until="networkidle")

        # NOTE: 等待字体加载完成，比硬编码 2s 更可靠
        # 字体加载快时节省时间，慢时不会截到缺字的图
        try:
            page.evaluate("() => document.fonts.ready")
            # 额外等待 500ms 确保渲染完成
            page.wait_for_timeout(500)
        except Exception:
            # 回退：如果 document.fonts 不可用，使用固定等待
            page.wait_for_timeout(2000)

        page.screenshot(path=output_png, full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
