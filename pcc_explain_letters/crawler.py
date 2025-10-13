# crawler.py
import time
import re
import urllib.parse as urlparse

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from config import (
    SEARCH_URL, MAX_RESULTS,
    XPATH_CONTENT_INPUT,         # //input[@name='keyword1']
)

DETAIL_FUNC = "readExplainLetter"   # onclick handler name

# ----------------------
# Driver setup
# ----------------------
def make_driver(headless=True):
    opts = webdriver.ChromeOptions()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--start-maximized")
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

# ----------------------
# Helpers (iframes/windows)
# ----------------------
def _switch_default(driver):
    driver.switch_to.default_content()

def _scan_iframes(driver):
    _switch_default(driver)
    return driver.find_elements(By.TAG_NAME, "iframe")

def _find_in_any_frame(driver, by, value, timeout_each=6):
    """Return (element, frame_idx or None)."""
    _switch_default(driver)
    # default
    try:
        el = WebDriverWait(driver, timeout_each).until(EC.presence_of_element_located((by, value)))
        return el, None
    except Exception:
        pass
    # frames
    frames = _scan_iframes(driver)
    for idx, f in enumerate(frames):
        try:
            _switch_default(driver)
            driver.switch_to.frame(f)
            el = WebDriverWait(driver, timeout_each).until(EC.presence_of_element_located((by, value)))
            return el, idx
        except Exception:
            continue
    _switch_default(driver)
    return None, None

def _switch_to_frame_index(driver, idx):
    _switch_default(driver)
    if idx is None:
        return
    frames = _scan_iframes(driver)
    if idx < len(frames):
        driver.switch_to.frame(frames[idx])

def _maybe_switch_to_new_window(driver, wait_sec=5):
    cur = driver.current_window_handle
    end = time.time() + wait_sec
    while time.time() < end:
        handles = driver.window_handles
        if len(handles) > 1:
            for h in handles:
                if h != cur:
                    driver.switch_to.window(h)
                    return True
        time.sleep(0.2)
    return False

# ----------------------
# Search page
# ----------------------
def perform_search(driver, keyword: str):
    driver.get(SEARCH_URL)
    print("DEBUG: opened", driver.current_url)

    # 1) fill keyword1 (may live in an iframe)
    kw_input, fidx = _find_in_any_frame(driver, By.XPATH, XPATH_CONTENT_INPUT, timeout_each=10)
    if not kw_input:
        raise RuntimeError("Could not locate input[name=keyword1].")

    _switch_to_frame_index(driver, fidx)
    kw_input.clear()
    kw_input.send_keys(keyword)

    # 2) click the real '確認查詢' which is <a onclick="submitForms()">
    #    find it near the form or anywhere in the same context
    submit, _ = _find_in_any_frame(driver, By.XPATH, "//a[contains(@onclick,'submitForms')]", timeout_each=4)
    if submit is None:
        # try current context only (some pages generate it late)
        try:
            submit = WebDriverWait(driver, 4).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@onclick,'submitForms')]"))
            )
        except Exception:
            submit = None

    if submit is None:
        # hard fallback: execute the function in the page
        try:
            driver.execute_script("if (typeof submitForms === 'function') submitForms();")
        except Exception:
            pass
    else:
        try:
            ActionChains(driver).move_to_element(submit).pause(0.1).click(submit).perform()
        except Exception:
            driver.execute_script("arguments[0].click();", submit)

    # if a new window/tab opened, switch
    _switch_default(driver)
    _maybe_switch_to_new_window(driver, wait_sec=5)

    # wait until the results page shows rows that include readExplainLetter(...)
    ok = _wait_for_results(driver, total_wait=15)
    if not ok:
        print("DEBUG: results not detected. title=", driver.title, "url=", driver.current_url)
        raise RuntimeError("Search submitted, but no results detected.")

def _wait_for_results(driver, total_wait=12):
    xp = f"//*[contains(@onclick,'{DETAIL_FUNC}(')]"
    end = time.time() + total_wait
    while time.time() < end:
        _switch_default(driver)
        # default
        try:
            if driver.find_elements(By.XPATH, xp):
                return True
        except Exception:
            pass
        # frames
        frames = _scan_iframes(driver)
        for f in frames:
            try:
                _switch_default(driver)
                driver.switch_to.frame(f)
                if driver.find_elements(By.XPATH, xp):
                    return True
            except Exception:
                continue
        time.sleep(0.3)
    return False

# ----------------------
# Iterating details directly (click -> back)
# ----------------------
def scrape_first_n_details(driver, n=50):
    """
    Click each unique pk via readExplainLetter(pk), capture detail HTML, go back, repeat.
    De-duplicates pks per page and across pages.
    """
    collected = []
    seen_pk = set()
    page_guard = 0

    while len(collected) < n and page_guard < 40:
        page_guard += 1

        # --- collect unique PKs on this page (anchors only) ---
        pk_order = []           # preserve in-page order
        pk_set_page = set()

        xp_anchor = "//*[self::a and contains(@onclick,'readExplainLetter(')]"

        # default content
        _switch_default(driver)
        for el in driver.find_elements(By.XPATH, xp_anchor):
            pk = _pk_from_onclick(el.get_attribute("onclick") or "")
            if pk and (pk not in pk_set_page) and (pk not in seen_pk):
                pk_set_page.add(pk)
                pk_order.append((pk, None))

        # frames
        frames = _scan_iframes(driver)
        for idx, f in enumerate(frames):
            try:
                _switch_default(driver)
                driver.switch_to.frame(f)
                for el in driver.find_elements(By.XPATH, xp_anchor):
                    pk = _pk_from_onclick(el.get_attribute("onclick") or "")
                    if pk and (pk not in pk_set_page) and (pk not in seen_pk):
                        pk_set_page.add(pk)
                        pk_order.append((pk, idx))
            except Exception:
                continue

        print(f"DEBUG: unique items on this page: {len(pk_order)}")

        # nothing new on this page? try next page
        if not pk_order:
            if not _click_next_if_exists(driver):
                break
            continue

        # --- click each unique pk once ---
        for pk, fidx in pk_order:
            if len(collected) >= n:
                break
            seen_pk.add(pk)

            _switch_to_frame_index(driver, fidx)
            el = _find_element_with_pk(driver, pk)
            if not el:
                _switch_default(driver)
                continue

            try:
                driver.execute_script("arguments[0].click();", el)
            except Exception:
                try:
                    ActionChains(driver).move_to_element(el).pause(0.1).click(el).perform()
                except Exception:
                    _switch_default(driver)
                    continue

            _switch_default(driver)
            _maybe_switch_to_new_window(driver, wait_sec=3)

            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(0.4)

            html = driver.page_source
            cur_url = driver.current_url
            collected.append({"html": html, "url": cur_url, "pk": pk})
            print(f"DEBUG: scraped pk={pk} (total {len(collected)})")

            driver.back()
            time.sleep(0.8)
            _wait_for_results(driver, total_wait=10)

        # next page if we still need more
        if len(collected) < n:
            if not _click_next_if_exists(driver):
                break

    print(f"DEBUG: total scraped details: {len(collected)}")
    return collected[:n]

def _find_element_with_pk(driver, pk):
    # anchor only, to avoid img/button duplicates
    xp = f"//a[contains(@onclick,'readExplainLetter(') and contains(@onclick,'{pk}')]"
    try:
        return driver.find_element(By.XPATH, xp)
    except Exception:
        return None

def _pk_from_onclick(onclick: str):
    m = re.search(rf"{DETAIL_FUNC}\s*\(\s*([0-9]+)\s*\)", onclick)
    return m.group(1) if m else None

def _click_next_if_exists(driver):
    _switch_default(driver)
    next_xps = [
        "//a[contains(.,'下一頁')]",
        "//button[contains(.,'下一頁')]",
        "//input[@type='button' and contains(@value,'下一頁')]",
    ]
    for xp in next_xps:
        els = driver.find_elements(By.XPATH, xp)
        if els:
            try:
                els[0].click()
                time.sleep(0.9)
                return True
            except Exception:
                pass

    # try inside iframes
    frames = _scan_iframes(driver)
    for f in frames:
        try:
            _switch_default(driver)
            driver.switch_to.frame(f)
            for xp in next_xps:
                els = driver.find_elements(By.XPATH, xp)
                if els:
                    els[0].click()
                    time.sleep(0.9)
                    _switch_default(driver)
                    return True
        except Exception:
            continue

    _switch_default(driver)
    return False

# legacy export (kept for compatibility with run.py if needed)
def extract_pk_from_url(url: str):
    q = urlparse.urlparse(url).query
    params = urlparse.parse_qs(q)
    return params.get("pkPrmsRuleContent", [""])[0]

def fetch_detail_html(driver, url: str):
    # not used in the new flow (we click elements rather than using URLs)
    _switch_default(driver)
    driver.get(url)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
    time.sleep(0.5)
    return driver.page_source
