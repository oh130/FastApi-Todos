import os

from playwright.sync_api import sync_playwright

BASE_URL = os.environ.get("UI_BASE_URL", "http://127.0.0.1:8000")


def test_todo_ui_crud():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(BASE_URL)

        # 추가
        page.fill("#title", "Playwright 테스트")
        page.fill("#description", "UI 자동화 테스트")
        page.click("#todo-form button[type=submit]")
        page.wait_for_selector("#todo-list li:has-text('Playwright 테스트')")
        assert page.locator("#todo-list li", has_text="Playwright 테스트").count() == 1

        # 수정 (인라인 편집 폼)
        page.locator("#todo-list li", has_text="Playwright 테스트").locator(
            "button", has_text="Edit"
        ).click()
        edit_row = page.locator("li.edit-row")
        edit_row.wait_for()
        title_input = edit_row.locator("input[type=text]").nth(0)
        title_input.fill("")
        title_input.fill("Playwright 테스트 수정")
        edit_row.locator("button.save-btn").click()
        page.wait_for_selector("#todo-list li:has-text('Playwright 테스트 수정')")
        assert page.locator("#todo-list li", has_text="Playwright 테스트 수정").count() == 1

        # 삭제 (confirm 대화상자)
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator("#todo-list li", has_text="Playwright 테스트 수정").locator(
            "button", has_text="Delete"
        ).click()
        page.wait_for_timeout(500)
        assert page.locator("#todo-list li", has_text="Playwright 테스트 수정").count() == 0

        browser.close()
