import logging
import os
import re
# from datetime import date, datetime, timedelta

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)


def process_holidays(holidays: list[str]) -> dict:
    """
    Process list of holidays to a dictionary format.

    Args:
        holidays (list[str]): List of holidays in "YYYYMMDD - Name" format

    Returns:
        dict: Dictionary where keys are dates in "YYYY-MM-DD" format and values are holiday names
    """
    logger.debug("Extracting holidays from list")
    holiday_dict = {}
    for holiday in holidays:
        date, name = holiday.split(" - ")
        holiday_dict[date] = name
    return holiday_dict


def timesheet_nitor_sync(
    playwright,
    url: str,
    username: str,
    holidays: dict[str, str],
    project: str,
    logs: str,
):
    """
    Perform timesheet sync for Nitor.

    This function opens a Playwright browser instance, navigates to the
    timesheet URL, logs in, navigates to the projects page, selects the
    configured project, navigates to the time entries page, and adds a
    new time entry for each weekday until the latest existing entry.

    Args:
        playwright: A Playwright browser instance
        url (str): The URL of the timesheet login page
        username (str): The username to log in with
        holidays (dict[str, str]): A dictionary of holiday dates (keys) and
            their corresponding names (values)
        project (str): The project ID to select on the projects page
        logs (str): The comment to add to each new time entry
    """
    browser = playwright.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context()
    page = context.new_page()
    page.goto(url)
    logger.info(f"{url} loaded successfully")
    page.fill("#username", username)
    page.fill("#password", os.getenv("TIMESHEET_NITOR_PASSWORD"))
    page.click("#login-submit")
    page.wait_for_load_state("networkidle")
    logger.info(f"After login, current URL is: {page.url}")
    page.get_by_role("link", name="Projects").click()
    page.wait_for_url("**/projects")
    logger.info(f"Navigated to Projects page: {page.url}")
    page.wait_for_selector("#projects-index")
    page.click(f"a.project[href='/projects/{project}']")
    page.wait_for_load_state("networkidle")
    logger.info(f"Project page loaded successfully: {page.url}")
    page.click(f"a[href='/projects/{project}/time_entries']")
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("table.time-entries tbody tr")
    latest_row = page.locator("table.time-entries tbody tr").first
    last_entry_date = latest_row.locator("td.spent_on").inner_text()
    logger.info(f"Last entry found for date: {last_entry_date}")
    weekdays = get_weekdays_until(last_entry_date)
    if weekdays:
        logger.info(f"Adding entries for following dates:\n{weekdays}")
        holiday_dates = list(holidays.keys())
        page.click("a.icon-time-add")
        page.wait_for_load_state("networkidle")
        for idx, _date in enumerate(weekdays):
            logger.info(f"Adding entry for: {_date}")
            page.wait_for_selector("#time_entry_spent_on")
            page.fill("#time_entry_spent_on", _date)
            page.fill("input#time_entry_hours", str(8))
            if _date in holiday_dates:
                page.fill("input#time_entry_comments", holidays[_date])
                page.select_option("select#time_entry_activity_id", "Holiday")
            else:
                page.fill("input#time_entry_comments", logs)
                page.select_option("select#time_entry_activity_id", "Task")
            if idx < len(weekdays) - 1:
                page.click("input[name='continue']")  # "Create and add another"
                logger.info(f"Adding another entry for: {weekdays[idx+1]}")
            else:
                page.click("input[name='commit']")  # "Create"
                logger.info("Added all entries.")
            page.wait_for_load_state("networkidle")
        logger.info("All missing entries added, browser closed.")
    else:
        logger.info("Nothing to add, closing browser.")
    page.click("a.time-entries")
    page.wait_for_load_state("networkidle")
    browser.close()


def timesheet_sync(client: str, config: dict) -> bool:
    """
    Perform timesheet sync for the given client.

    Args:
        client (str): The client name, either "nitor"
        config (dict): A dictionary containing the configuration for the client

    Returns:
        bool: True if the timesheet sync was successful, False otherwise
    """
    holidays = process_holidays(holidays=config[client]["holidays"])
    url = config[client]["url"]
    username = config[client]["username"]
    project = config[client]["project"]
    logs = config[client]["logs"]
    logs = ", ".join(logs)

    with sync_playwright() as playwright:
        if client.lower() == "nitor":
            timesheet_nitor_sync_v2(playwright, url, username, holidays, project, logs)


def timesheet_nitor_sync_v2(
    playwright,
    url: str,
    username: str,
    holidays: dict[str, str],
    project: str,
    logs: str,
):
    """
    Perform timesheet sync for Nitor.

    This function opens a Playwright browser instance, navigates to the
    timesheet URL, logs in, navigates to the projects page, selects the
    configured project, navigates to the time entries page, and adds a
    new time entry for each weekday until the latest existing entry.

    Args:
        playwright: A Playwright browser instance
        url (str): The URL of the timesheet login page
        username (str): The username to log in with
        holidays (dict[str, str]): A dictionary of holiday dates (keys) and
            their corresponding names (values)
        project (str): The project ID to select on the projects page
        logs (str): The comment to add to each new time entry
    """
    browser = playwright.chromium.launch(headless=False, slow_mo=300)
    context = browser.new_context()
    page = context.new_page()
    page.goto(url)
    logger.info(f"{url} loaded successfully")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill(os.getenv("TIMESHEET_NITOR_PASSWORD"))
    page.get_by_role("button", name=re.compile("log in", re.IGNORECASE)).click()
    page.wait_for_load_state("networkidle")
    logger.info(f"After login, current URL is: {page.url}")
    page.get_by_role("button", name=re.compile("timesheet", re.IGNORECASE)).click()
    logger.info(f"Navigated to Projects page: {page.url}")
    page.wait_for_load_state("networkidle")
    latest_row = page.locator("table tbody tr").first
    date_cell = latest_row.locator("td").nth(1)
    last_entry_date = date_cell.text_content()
    weekdays = get_weekdays_until(last_entry_date)
    if weekdays:
        logger.info(f"Adding entries for following dates:\n{weekdays}")
        holiday_dates = list(holidays.keys())
        page.get_by_role("button", name=re.compile("log time", re.IGNORECASE)).click()
        page.wait_for_load_state("networkidle")
        for idx, _date in enumerate(weekdays):
            logger.info(f"Adding entry for: {_date}")
            page.get_by_role("combobox", name="project").click()
            page.get_by_role("option", name=project.lower()).click()
            page.locator("#datetime").fill(_date)
            page.get_by_role("spinbutton", name="hours").click()
            page.locator("#hours").fill(str(8))
            if _date in holiday_dates:
                page.get_by_role("combobox", name="activity").click()
                page.get_by_role("option", name="holiday").click()
                page.get_by_role("textbox", name="comment").click()
                _logs = f"{holidays[_date]} - A Company Holiday"
                page.locator("#comment").fill(_logs)
            else:
                page.get_by_role("combobox", name="activity").click()
                page.get_by_role("option", name="task").click()
                date_obj = datetime.strptime(_date, "%Y-%m-%d")
                page.get_by_role("combobox", name="work mode").click()
                page.get_by_role("option", name="work from home").click()
                if date_obj.weekday() == 2:  # Monday=0 ... Sunday=6
                    page.get_by_role("combobox", name="work mode").click()
                    page.get_by_role("option", name="work from office").click()
                page.get_by_role("textbox", name="comment").click()
                page.locator("#comment").fill(logs)

            if idx < len(weekdays) - 1:
                page.get_by_role(
                    "button", name=re.compile("save & add another", re.IGNORECASE)
                ).click()
                logger.info(f"Adding another entry for: {weekdays[idx+1]}")
            else:
                page.get_by_role("button", name="Save", exact=True).click()
                logger.info("Added all entries.")
            page.wait_for_load_state("networkidle")
        logger.info("All missing entries added, browser closed.")
    else:
        logger.info("Nothing to add, closing browser.")
    browser.close()
