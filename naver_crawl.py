import asyncio
import json
import os
import datetime
from playwright.async_api import async_playwright
from coupang_auth import _find_chromium_executable, _data_path

NAVER_BASE = "https://sell.smartstore.naver.com"
GRAPHQL_URL = f"{NAVER_BASE}/o/v3/graphql"

DELIVERY_QUERY = """query smartstoreFindDeliveriesByDetailConditions_ForSaleDelivery($dateRange_from: String, $dateRange_to: String, $delayDispatchGuideTreatStateType: DelayDispatchGuideTreatStateType, $deliveryDirectionClass: DeliveryDirectionClassType, $deliveryMethodType: DeliveryMethodType, $deliveryNo: String, $detailSearch_keyword: String, $detailSearch_type: DetailSearchType, $detailedOrderStatus: DetailedSearchOrderStatusType, $deviceClassType: DeviceClassType, $merchantNo: String!, $orderStatus: SearchOrderStatusType, $paging_page: Int, $paging_size: Int, $rangeType: RangeType, $serviceType: String!, $sort_direction: SortDirectionType, $sort_type: SortType) {
  deliveryList: smartstoreFindDeliveriesByDetailConditions_ForSaleDelivery(
    dateRange_from: $dateRange_from dateRange_to: $dateRange_to
    delayDispatchGuideTreatStateType: $delayDispatchGuideTreatStateType
    deliveryDirectionClass: $deliveryDirectionClass deliveryMethodType: $deliveryMethodType
    deliveryNo: $deliveryNo detailSearch_keyword: $detailSearch_keyword
    detailSearch_type: $detailSearch_type detailedOrderStatus: $detailedOrderStatus
    deviceClassType: $deviceClassType merchantNo: $merchantNo orderStatus: $orderStatus
    paging_page: $paging_page paging_size: $paging_size rangeType: $rangeType
    serviceType: $serviceType sort_direction: $sort_direction sort_type: $sort_type
  ) {
    elements { ...deliveryElementField __typename }
    pagination { ...paginationField __typename }
    __typename
  }
}
fragment deliveryElementField on SaleDeliverySeller {
  returnCareTarget branchId merchantChannelNo deliveryFeeClass deliveryInvoiceNo
  orderQuantity productName payDateTime deliveryDateTime deliveryFeeRatingClass
  productOrderMemo orderMemberId remoteAreaCostChargeAmt payLocationType totalDiscountAmt
  orderNo payMeansClass productClass oneYearOrderAmt saleChannelType oneYearOrderCount
  deliveryCompanyName sellerProductManagementCode grade orderMemberTelNo deliveryFeeAmt
  claimNo deliveryMethod deliveryMethodPay biztalkAccountId giftName receiverTelNo2
  productPayAmt receiverTelNo1 sixMonthOrderAmt orderStatus productUnitPrice
  waybillPrintDateTime threeMonthOrderCount orderMemberName productOrderNo deliveryCompanyCode
  productOptionContents standardGroupProductOptions dispatchDueDateTime
  knowledgeShoppingCommissionAmt productOptionAmt productNo individualCustomUniqueCode
  orderDateTime placingOrderDateTime inflowPath receiverName settlementExpectAmt deliveryNo
  threeMonthOrderAmt sellerDiscountAmt deliveryFeeDiscountAmt dispatchDateTime sixMonthOrderCount
  receiverZipCode payCommissionAmt takingGoodsPlaceAddress syncDateTime productOrderStatus
  sellerInternalCode2 sellerOptionManagementCode sellerInternalCode1 deliveryBundleGroupSeq
  productUrl subscriptionRound subscriptionPeriodCount fulfillmentCompanyName
  receiverIntegratedAddress receiverDisplayBaseAddress receiverDisplayDetailAddress
  deliveryAttributeText hopeDelivery initTotalDiscountAmt initProductPayAmt quantityClaimYn
  quantityClaimNo subscriptionHopeDelivery deliveryTagType entryMethodType entryMethodContent
  pickupLocationType pickupLocationContent deliveryCompanyNameAtOrder
  membershipsArrivalGuaranteeClaimSupportTarget __typename
}
fragment paginationField on Pagination { size totalElements page totalPages __typename }"""


def save_naver_cookies(account_id, cookies):
    p = _data_path("naver_cookies_all.json")
    all_cookies = {}
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                all_cookies = json.load(f)
        except: pass
    all_cookies[account_id] = cookies
    with open(p, "w") as f:
        json.dump(all_cookies, f)


def delete_naver_cookies(account_id):
    """네이버 쿠키만 삭제 (계정은 유지)"""
    p = _data_path("naver_cookies_all.json")
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                all_cookies = json.load(f)
            all_cookies.pop(account_id, None)
            with open(p, "w") as f:
                json.dump(all_cookies, f)
        except: pass


def verify_naver_cookies(account_id="default", timeout=8):
    """저장된 쿠키로 네이버 셀러센터 API 호출 → 로그인 유효성 검증."""
    cookies = load_naver_cookies(account_id)
    if not cookies:
        return False
    try:
        import urllib.request, ssl
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name") and c.get("value") is not None)
        if not cookie_header:
            return False
        req = urllib.request.Request(
            f"{NAVER_BASE}/api/v1/sellers/account",
            headers={
                "Cookie": cookie_header,
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }
        )
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            if resp.status != 200:
                return False
            ctype = resp.headers.get("Content-Type", "").lower()
            if "json" not in ctype:
                return False
            data = json.loads(resp.read().decode("utf-8"))
            return bool(data and (data.get("naverPay") or data.get("loginId") or data.get("sellerNo") or data.get("id")))
    except Exception:
        return False


def load_naver_cookies(account_id="default"):
    # 먼저 계정별 쿠키
    p = _data_path("naver_cookies_all.json")
    if os.path.exists(p):
        try:
            with open(p, "r") as f:
                return json.load(f).get(account_id, [])
        except: pass
    # 기존 단일 쿠키 파일
    p2 = _data_path("naver_cookies.json")
    if os.path.exists(p2):
        try:
            with open(p2, "r") as f:
                return json.load(f)
        except: pass
    return []


def _ts_to_str(ts):
    """밀리초 타임스탬프 → 날짜 문자열"""
    if not ts:
        return ""
    try:
        return datetime.datetime.fromtimestamp(int(ts) / 1000).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)


def _normalize_naver_order(item, account_id=""):
    """네이버 주문 데이터 정규화 (쿠팡과 동일한 구조로)"""
    return {
        "orderId": item.get("orderNo", ""),
        "productOrderNo": item.get("productOrderNo", ""),
        "orderedAt": _ts_to_str(item.get("payDateTime")),
        "orderItems": [{
            "vendorItemPackageName": item.get("productName", ""),
            "orderPrice": int(item.get("productPayAmt") or 0),
            "vendorItemId": str(item.get("productNo") or ""),
            "sellerProductCode": item.get("sellerProductManagementCode") or "",
            "orderQuantity": int(item.get("orderQuantity") or 1),
        }],
        "receiver": {
            "name": item.get("receiverName", ""),
            "safeNumber": item.get("receiverTelNo1") or item.get("receiverTelNo2") or "",
            "addr1": item.get("receiverIntegratedAddress") or item.get("receiverDisplayBaseAddress") or "",
            "addr2": item.get("receiverDisplayDetailAddress") or "",
        },
        "memberName": item.get("orderMemberName", ""),
        "memberPhoneNumber": item.get("orderMemberTelNo", ""),
        "deliveryMemo": item.get("productOrderMemo") or "",
        "parcelPrintMessage": item.get("productOrderMemo") or "",
        "linked_username": account_id,
        "market": "naver",
        "totalPrice": int(item.get("productPayAmt") or 0),
        "settlementPrice": int(item.get("settlementExpectAmt") or 0),
        "deliveryStatusCode": item.get("productOrderStatus") or item.get("orderStatus") or "",
        "productOrderStatus": item.get("productOrderStatus") or "",
        "invoiceNumber": item.get("deliveryInvoiceNo") or "",
        "deliverCode": item.get("deliveryCompanyCode") or "",
        "deliverName": item.get("deliveryCompanyName") or item.get("deliveryCompanyNameAtOrder") or "",
        "productOptionContents": item.get("productOptionContents") or "",
        "sellerOptionManagementCode": item.get("sellerOptionManagementCode") or "",
    }


async def _naver_login_and_get_page(playwright, account_id="default"):
    """네이버 셀러센터 로그인 (쿠키 기반)"""
    chrome = _find_chromium_executable()
    browser = await playwright.chromium.launch(headless=True, executable_path=chrome)
    context = await browser.new_context()

    cookies = load_naver_cookies(account_id)
    if cookies:
        await context.add_cookies(cookies)

    page = await context.new_page()
    await page.goto(NAVER_BASE, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    # 로그인 체크
    if "nid.naver.com" in page.url or "login" in page.url.lower():
        # 쿠키 만료 → headless=False로 수동 로그인
        await browser.close()
        browser = await playwright.chromium.launch(headless=False, executable_path=chrome)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto(NAVER_BASE, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        # 로그인 대기 (60초)
        for _ in range(60):
            await asyncio.sleep(1)
            if "sell.smartstore" in page.url and "login" not in page.url.lower() and "nid.naver" not in page.url:
                break

        if "sell.smartstore" not in page.url:
            await browser.close()
            return None, None, None

        # 쿠키 저장
        new_cookies = await context.cookies()
        save_naver_cookies(account_id, new_cookies)

    return browser, context, page


async def _get_merchant_no(context, page):
    """merchantNo 자동 추출 - 발주/발송 페이지에서 GraphQL 요청 캡처"""
    captured_merchant = [None]

    async def on_req(request):
        if "graphql" in request.url and request.post_data:
            try:
                body = json.loads(request.post_data)
                mn = body.get("variables", {}).get("merchantNo")
                if mn:
                    captured_merchant[0] = mn
            except: pass

    page.on("request", on_req)

    # 발주/발송 페이지로 이동하여 검색 트리거
    await page.evaluate("window.location.hash = '#/naverpay/sale/delivery'")
    await asyncio.sleep(3)

    # 검색 버튼 클릭
    await page.evaluate("""
        () => {
            const btns = document.querySelectorAll('button');
            for (const b of btns) {
                if (b.textContent.trim() === '검색') { b.click(); return; }
            }
        }
    """)
    await asyncio.sleep(3)

    if captured_merchant[0]:
        return captured_merchant[0]

    # account API에서 naverPay.referenceKey로 추출
    try:
        resp = await context.request.get(f"{NAVER_BASE}/api/v1/sellers/account", headers={"Accept": "application/json"})
        if resp.ok:
            data = await resp.json()
            npay = data.get("naverPay", {})
            ref_key = npay.get("referenceKey")
            if ref_key:
                return str(ref_key)
    except: pass

    return None


async def scrape_naver_orders(account_id="default", merchant_no=None, start_date=None, end_date=None, order_status="ALL", callback=None):
    """네이버 스마트스토어 주문 크롤링"""
    if not start_date:
        start_date = (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.date.today().strftime("%Y-%m-%d")

    # 날짜를 밀리초 타임스탬프로 변환
    from_ts = str(int(datetime.datetime.strptime(start_date, "%Y-%m-%d").timestamp() * 1000))
    to_ts = str(int((datetime.datetime.strptime(end_date, "%Y-%m-%d") + datetime.timedelta(days=1) - datetime.timedelta(seconds=1)).timestamp() * 1000))

    async with async_playwright() as p:
        chrome = _find_chromium_executable()
        browser = await p.chromium.launch(headless=True, executable_path=chrome)
        context = await browser.new_context()
        cookies = load_naver_cookies(account_id) or load_naver_cookies("default")
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()

        # merchantNo가 있으면 페이지 로드 건너뛰기 (속도 최적화)
        if merchant_no:
            await page.goto(NAVER_BASE, wait_until="domcontentloaded")
            await asyncio.sleep(1)
        else:
            await page.goto(NAVER_BASE, wait_until="domcontentloaded")
            await asyncio.sleep(2)

        # merchantNo 자동 추출
        if not merchant_no:
            if callback:
                callback(f"네이버: merchantNo 추출 중...")
            await page.goto(f"{NAVER_BASE}/#/naverpay/sale/delivery", wait_until="domcontentloaded")
            await asyncio.sleep(3)

            # GraphQL 요청에서 merchantNo 캡처
            captured_merchant = [None]
            async def on_req(request):
                if "graphql" in request.url and request.post_data and "merchantNo" in request.post_data:
                    try:
                        body = json.loads(request.post_data)
                        mn = body.get("variables", {}).get("merchantNo")
                        if mn:
                            captured_merchant[0] = mn
                    except: pass
            page.on("request", on_req)

            # 검색 트리거
            await page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button');
                    for (const b of btns) {
                        if (b.textContent.trim() === '검색') { b.click(); return; }
                    }
                }
            """)
            await asyncio.sleep(3)

            merchant_no = captured_merchant[0]
            if not merchant_no:
                merchant_no = await _get_merchant_no(context, page)

        if not merchant_no:
            if callback:
                callback("네이버: merchantNo를 찾을 수 없습니다")
            await browser.close()
            return []

        # merchantNo 저장 (다음번에 재사용)
        try:
            p = _data_path("naver_accounts.json")
            accs = []
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    accs = json.load(f)
            for a in accs:
                if str(a.get("account_id")) == str(account_id):
                    a["merchant_no"] = merchant_no
                    a["account_id"] = str(account_id)
                    break
            else:
                accs.append({"account_id": str(account_id), "merchant_no": merchant_no, "store_name": "스마트스토어", "market": "naver"})
            with open(p, "w", encoding="utf-8") as f:
                json.dump(accs, f, ensure_ascii=False, indent=2)
        except: pass

        if callback:
            callback(f"네이버: merchantNo={merchant_no}, 주문 수집 중...")

        # GraphQL로 주문 데이터 수집
        all_orders = []
        current_page = 1
        page_size = 100

        while True:
            variables = {
                "merchantNo": merchant_no,
                "serviceType": "MP",
                "paging_page": current_page,
                "paging_size": page_size,
                "sort_type": "RECENTLY_ORDER_YMDT",
                "sort_direction": "DESC",
                "orderStatus": order_status,
                "rangeType": "PAY_COMPLETED",
                "dateRange_from": from_ts,
                "dateRange_to": to_ts,
                "detailedOrderStatus": "ALL",
            }

            try:
                resp = await context.request.post(
                    GRAPHQL_URL,
                    data=json.dumps({
                        "operationName": "smartstoreFindDeliveriesByDetailConditions_ForSaleDelivery",
                        "variables": variables,
                        "query": DELIVERY_QUERY,
                    }),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    }
                )

                if not resp.ok:
                    break

                data = await resp.json()
                delivery_list = data.get("data", {}).get("deliveryList", {})
                elements = delivery_list.get("elements", [])
                pagination = delivery_list.get("pagination", {})
                total_pages = int(pagination.get("totalPages", 1))
                total_elements = int(pagination.get("totalElements", 0))

                if not elements:
                    break

                for item in elements:
                    all_orders.append(_normalize_naver_order(item, account_id))

                if callback:
                    callback(f"네이버: {len(all_orders)}/{total_elements}건 수집 중... ({current_page}/{total_pages})")

                if current_page >= total_pages:
                    break
                current_page += 1

            except Exception as e:
                print(f"네이버 주문 크롤링 오류 (p{current_page}): {e}")
                break

        # 구매확정 수집 → 배송완료에 추가 (배송완료일 기준 필터링)
        if callback:
            callback(f"네이버: 구매확정 수집 중...")
        try:
            # 넓은 기간으로 가져온 후 배송완료일로 필터링
            _start_d = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
            wide_start = str(int((datetime.datetime.combine(_start_d - datetime.timedelta(days=8), datetime.time.min)).timestamp() * 1000))
            pd_page = 1
            pd_added = 0
            while True:
                pd_resp = await context.request.post(
                    GRAPHQL_URL,
                    data=json.dumps({
                        "operationName": "SmartStoreFindPurchaseDecisionsByDetailConditions_ForPurchaseDecision",
                        "variables": {
                            "merchantNo": merchant_no, "serviceType": "MP",
                            "paging_page": pd_page, "paging_size": 100,
                            "sort_type": "PRODUCT_ORDER_PURCHASE_DECISION_COMPLETE_OPERATION_YMDT",
                            "sort_direction": "DESC",
                            "rangeType": "PURCHASE_DECISION_COMPLETED",
                            "dateRange_from": wide_start, "dateRange_to": to_ts,
                        },
                        "query": PURCHASE_DECISION_QUERY,
                    }),
                    headers={"Content-Type": "application/json", "Accept": "application/json"})
                if not pd_resp.ok:
                    break
                pd_data = await pd_resp.json()
                if pd_data.get("errors"):
                    break
                pd_list = pd_data.get("data", {}).get("purchaseDecisionList", {})
                pd_elements = pd_list.get("elements", [])
                pd_total_pages = int(pd_list.get("pagination", {}).get("totalPages", 1))
                if not pd_elements:
                    break
                for item in pd_elements:
                    # 배송완료일 기준 필터링
                    dct = item.get("deliveryCompleteDateTime") or item.get("deliveryDateTime")
                    if dct:
                        dct_ms = int(dct)
                        if int(from_ts) <= dct_ms <= int(to_ts):
                            order = _normalize_naver_order(item, account_id)
                            order["productOrderStatus"] = "PURCHASE_DECIDED"
                            order["deliveryStatusCode"] = "PURCHASE_DECIDED"
                            all_orders.append(order)
                            pd_added += 1
                    else:
                        # 배송완료일 없으면 결제일로 대체
                        order = _normalize_naver_order(item, account_id)
                        order["productOrderStatus"] = "PURCHASE_DECIDED"
                        order["deliveryStatusCode"] = "PURCHASE_DECIDED"
                        all_orders.append(order)
                        pd_added += 1
                if pd_page >= pd_total_pages:
                    break
                pd_page += 1
            if callback:
                callback(f"네이버: 구매확정 {pd_added}건 추가")
        except Exception as e:
            print(f"네이버 구매확정 오류: {e}")

        await browser.close()

        if callback:
            callback(f"네이버: 주문 {len(all_orders)}건 수집 완료")
        return all_orders


def get_naver_orders(account_id="default", merchant_no=None, start_date=None, end_date=None, order_status="ALL", callback=None):
    """네이버 주문 수집 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            scrape_naver_orders(account_id, merchant_no, start_date, end_date, order_status, callback)
        )
        return {"code": 200, "data": result}
    except Exception as e:
        print(f"네이버 주문 크롤링 오류: {e}")
        return {"code": 500, "data": [], "error": str(e)}
    finally:
        loop.close()


def _selenium_to_playwright_cookies(raw):
    """Selenium 쿠키 → Playwright 쿠키 형식 변환"""
    out = []
    for c in raw:
        ck = {
            "name": c.get("name", ""),
            "value": c.get("value", ""),
            "domain": c.get("domain", ""),
            "path": c.get("path", "/"),
        }
        if "expiry" in c:
            ck["expires"] = float(c["expiry"])
        if "secure" in c:
            ck["secure"] = bool(c["secure"])
        if "httpOnly" in c:
            ck["httpOnly"] = bool(c["httpOnly"])
        ss = c.get("sameSite")
        if ss in ("Strict", "Lax", "None"):
            ck["sameSite"] = ss
        out.append(ck)
    return out


def _profile_dir_for(account_id):
    d = _data_path(os.path.join("chrome_profile", account_id or "default"))
    os.makedirs(d, exist_ok=True)
    return d


def do_naver_login(account_id="default", callback=None, naver_id=None, naver_pw=None, login_type="seller"):
    """네이버 로그인 (undetected-chromedriver + 프로필 유지 + 세션 재사용).

    naver_id/naver_pw 전달 시 자동 입력 후 로그인 시도.
    login_type: 'seller' = 이메일/판매자 아이디, 'naver' = 네이버 아이디.
    캡차/2차인증 등은 사용자가 직접 처리.
    """
    import time, random
    try:
        import undetected_chromedriver as uc
        from selenium.webdriver.common.by import By
        from selenium.webdriver.common.keys import Keys
        from selenium.webdriver.common.action_chains import ActionChains
    except Exception as e:
        print(f"undetected-chromedriver 미설치: {e}")
        return None

    original_account_id = account_id
    profile_dir = _profile_dir_for(account_id)

    options = uc.ChromeOptions()
    options.add_argument("--window-size=560,720")
    options.add_argument("--window-position=120,80")
    options.add_argument("--disable-features=MaximizeOnRestore")
    options.add_argument(f"--user-data-dir={profile_dir}")

    driver = None
    try:
        driver = uc.Chrome(options=options, use_subprocess=True)
        try:
            driver.set_window_rect(x=120, y=80, width=560, height=720)
        except Exception:
            try:
                driver.set_window_size(560, 720)
                driver.set_window_position(120, 80)
            except: pass

        # 1. 먼저 셀러센터 접속 시도 → 이미 로그인돼 있으면 바로 성공
        if callback: callback("스마트스토어 셀러센터 접속 중...")
        driver.get(NAVER_BASE)
        time.sleep(1.5)

        def _is_on_smartstore():
            url = driver.current_url
            return "sell.smartstore" in url and "login" not in url.lower() and "nid.naver" not in url and "accounts.commerce" not in url

        def _has_login_button():
            """랜딩 페이지의 '로그인하기' 진입 버튼이 보이면 True (=비로그인)"""
            for sel in ["button.btn-login", "button.btn.btn-login"]:
                try:
                    b = driver.find_element(By.CSS_SELECTOR, sel)
                    if b.is_displayed(): return True
                except: pass
            for xp in ["//button[.//span[normalize-space(.)='로그인하기']]",
                       "//button[contains(normalize-space(.),'로그인하기')]"]:
                try:
                    b = driver.find_element(By.XPATH, xp)
                    if b.is_displayed(): return True
                except: pass
            return False

        # 로그인하기 버튼 보이면 비로그인 → 로그인 진행. 안 보이면 이미 로그인됨.
        already_logged_in = _is_on_smartstore() and not _has_login_button()

        # 2. 로그인 필요 — sell.smartstore 랜딩의 "로그인하기" 진입 버튼 자동 클릭
        if not already_logged_in:
            if callback: callback("'로그인하기' 버튼 클릭 중...")
            entry_clicked = False
            for _ in range(8):
                for sel in ["button.btn-login", "button.btn.btn-login",
                            "button[ng-click*='vm.login']", "button[ng-click*='login']"]:
                    try:
                        b = driver.find_element(By.CSS_SELECTOR, sel)
                        if b.is_displayed():
                            try: b.click()
                            except: driver.execute_script("arguments[0].click();", b)
                            entry_clicked = True; break
                    except: pass
                if not entry_clicked:
                    for xp in ["//button[.//span[normalize-space(.)='로그인하기']]",
                               "//button[contains(normalize-space(.),'로그인하기')]"]:
                        try:
                            b = driver.find_element(By.XPATH, xp)
                            if b.is_displayed():
                                try: b.click()
                                except: driver.execute_script("arguments[0].click();", b)
                                entry_clicked = True; break
                        except: pass
                if entry_clicked: break
                time.sleep(0.5)
            time.sleep(1.2)

            # 2-1. 로그인 방식 탭 선택
            if callback: callback("로그인 방식 탭 선택...")
            tab_text = "네이버 아이디로 로그인" if login_type == "naver" else "이메일/판매자 아이디로 로그인"
            original_window = driver.current_window_handle
            windows_before = set(driver.window_handles)
            tab_clicked = False
            for _ in range(4):
                for xp in [
                    f"//button[contains(normalize-space(.),'{tab_text}')]",
                    f"//a[contains(normalize-space(.),'{tab_text}')]",
                    f"//*[@role='tab' and contains(normalize-space(.),'{tab_text}')]",
                    f"//li[contains(normalize-space(.),'{tab_text}')]",
                ]:
                    try:
                        el = driver.find_element(By.XPATH, xp)
                        if el.is_displayed():
                            try: el.click()
                            except: driver.execute_script("arguments[0].click();", el)
                            tab_clicked = True; break
                    except: pass
                if tab_clicked: break
                time.sleep(0.4)
            if tab_clicked:
                time.sleep(0.8)

            # 2-2. 네이버 아이디 탭은 새 팝업 창으로 nid.naver.com 이 열림 → 해당 창으로 switch
            in_iframe = False
            switched_window = False
            if login_type == "naver":
                for _ in range(12):
                    new_windows = set(driver.window_handles) - windows_before
                    if new_windows:
                        for wh in new_windows:
                            try:
                                driver.switch_to.window(wh)
                                if "nid.naver" in (driver.current_url or "").lower() or driver.find_elements(By.ID, "id"):
                                    switched_window = True
                                    break
                            except: pass
                        if switched_window: break
                    # 팝업 아니고 같은 창에서 이동한 경우
                    if "nid.naver" in (driver.current_url or "").lower():
                        break
                    # iframe 케이스도 혹시 모르니
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    for fr in iframes:
                        try:
                            src = (fr.get_attribute("src") or "").lower()
                            if "nid.naver" in src or "nidlogin" in src:
                                driver.switch_to.frame(fr)
                                in_iframe = True; break
                        except: pass
                    if in_iframe: break
                    time.sleep(0.4)
                # 페이지 안정화
                for _ in range(8):
                    try:
                        ready = driver.execute_script("return document.readyState")
                        if ready == "complete": break
                    except: pass
                    time.sleep(0.3)
                time.sleep(0.5)

            auto_filled = False
            # ID/PW 입력 필드 대기 (최대 ~6초)
            id_el = pw_el = None
            for _ in range(12):
                for sel_id, sel_pw in [
                    ("#id", "#pw"),
                    ("input[name='id']", "input[name='pw']"),
                    ("input[placeholder*='아이디']", "input[type='password']"),
                    ("input[type='text']:not([type='hidden'])", "input[type='password']"),
                ]:
                    try:
                        _id = driver.find_element(By.CSS_SELECTOR, sel_id)
                        _pw = driver.find_element(By.CSS_SELECTOR, sel_pw)
                        if _id and _pw and _id.is_displayed() and _pw.is_displayed():
                            id_el, pw_el = _id, _pw
                            break
                    except: pass
                if id_el and pw_el: break
                time.sleep(0.5)

            if naver_id and naver_pw and id_el and pw_el:
                try:
                    def _fill(el, value):
                        """ID/PW 강제 입력 — send_keys 실패 시 JS fallback + input 이벤트 dispatch"""
                        try: el.click()
                        except: pass
                        try: el.clear()
                        except: pass
                        try:
                            el.send_keys(value)
                        except Exception:
                            pass
                        # 값 검증
                        try:
                            cur = el.get_attribute("value") or ""
                        except: cur = ""
                        if cur != value:
                            # JS 로 value 강제 + input/change 이벤트 dispatch (Angular 리바인딩)
                            driver.execute_script(
                                "arguments[0].focus();"
                                "arguments[0].value = arguments[1];"
                                "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));"
                                "arguments[0].dispatchEvent(new Event('change', {bubbles: true}));",
                                el, value
                            )

                    _fill(id_el, naver_id)
                    _fill(pw_el, naver_pw)
                    if callback: callback("로그인 시도 중...")
                    time.sleep(0.4)
                    clicked = False
                    # 1) 클래스 기반 — sell.smartstore 로그인 버튼 (btn btn-login)
                    for sel in ["button.btn-login", "button.btn.btn-login",
                                "button[ng-click*='login']", "button[ng-click*='vm.login']"]:
                        try:
                            btn = driver.find_element(By.CSS_SELECTOR, sel)
                            if btn.is_displayed():
                                try: btn.click()
                                except: driver.execute_script("arguments[0].click();", btn)
                                clicked = True; break
                        except: pass
                    # 2) 텍스트 기반 (로그인하기/로그인)
                    if not clicked:
                        for xp in [
                            "//button[.//span[normalize-space(.)='로그인하기']]",
                            "//button[contains(normalize-space(.),'로그인하기')]",
                            "//button[normalize-space(.)='로그인']",
                            "//a[contains(normalize-space(.),'로그인하기')]",
                            "//input[@type='submit']",
                        ]:
                            try:
                                btn = driver.find_element(By.XPATH, xp)
                                if btn.is_displayed():
                                    try: btn.click()
                                    except: driver.execute_script("arguments[0].click();", btn)
                                    clicked = True; break
                            except: pass
                    # 3) nid.naver.com 폴백
                    if not clicked:
                        for sel in ["#log\\.login", "button.btn_login", "button.login_btn",
                                    "a.btn_login", "button[type='submit']", ".btn_type_login"]:
                            try:
                                btn = driver.find_element(By.CSS_SELECTOR, sel)
                                if btn.is_displayed():
                                    try: btn.click()
                                    except: driver.execute_script("arguments[0].click();", btn)
                                    clicked = True; break
                            except: pass
                    # 3) 엔터키 폴백
                    if not clicked:
                        pw_el.send_keys(Keys.RETURN)
                    auto_filled = True
                except Exception as e:
                    print(f"자동입력 실패: {e}")

            # iframe 에서 작업했으면 메인 document 복귀
            if in_iframe:
                try: driver.switch_to.default_content()
                except: pass

            if callback: callback("로그인 대기 중... (캡차/2차인증 시 직접 처리)")
            for i in range(180):
                time.sleep(1)
                # 팝업 창에서 로그인한 경우: 팝업 닫히면 원래 창으로 복귀
                if switched_window:
                    try:
                        handles = driver.window_handles
                        if original_window in handles:
                            try: driver.switch_to.window(original_window)
                            except: pass
                    except: pass
                if _is_on_smartstore():
                    already_logged_in = True
                    break
                if auto_filled and i >= 2:
                    err_msg = ""
                    for sel in ["#err_common", ".error_message", ".login_error",
                                "[class*='error_message']", "[class*='alert']"]:
                        try:
                            el = driver.find_element(By.CSS_SELECTOR, sel)
                            t = (el.text or "").strip()
                            if t and ("비밀번호" in t or "아이디" in t or "일치" in t or "잘못" in t or "확인" in t):
                                err_msg = t; break
                        except: pass
                    if err_msg:
                        return {"success": False, "message": err_msg}
                if callback and i % 15 == 0:
                    callback(f"로그인 대기 중... ({180-i}초)")

            # 원래 창으로 확실히 복귀
            if switched_window:
                try:
                    if original_window in driver.window_handles:
                        driver.switch_to.window(original_window)
                except: pass

            if not already_logged_in:
                return {"success": False, "message": "로그인 시간 초과"}

        # 3. 셀러센터 도달 재확인 (로그인 성공 직후 네이버 쪽 리다이렉트 거치는 경우 대비)
        if callback: callback("셀러센터 진입 확인 중...")
        if not _is_on_smartstore():
            driver.get(NAVER_BASE)
            time.sleep(3)
            for _ in range(30):
                if _is_on_smartstore(): break
                time.sleep(1)
        if not _is_on_smartstore():
            return {"success": False,
                    "message": "셀러센터(sell.smartstore.naver.com) 진입 실패. 판매자 계정인지 확인하세요."}
        time.sleep(2)

        # 4. 쿠키 추출 — CDP로 모든 도메인 쿠키 수집 (.smartstore + .naver)
        raw_cookies = []
        try:
            result = driver.execute_cdp_cmd("Network.getAllCookies", {})
            raw_cookies = result.get("cookies", [])
        except Exception as e:
            print(f"CDP 쿠키 조회 실패, driver.get_cookies() fallback: {e}")
            raw_cookies = driver.get_cookies()

        # 필수 도메인 체크 — smartstore 쿠키 없으면 실패
        domains = {c.get("domain", "") for c in raw_cookies}
        has_smartstore = any("smartstore" in d for d in domains)
        if not raw_cookies or len(raw_cookies) < 5 or not has_smartstore:
            return {"success": False,
                    "message": f"셀러센터 쿠키 수집 실패 (쿠키 {len(raw_cookies)}개, 스마트스토어 쿠키 {'있음' if has_smartstore else '없음'})"}
        cookies = _selenium_to_playwright_cookies(raw_cookies)

        # 5. merchant_no + 아이디 추출
        merchant_no = ""
        try:
            driver.get(f"{NAVER_BASE}/api/v1/sellers/account")
            time.sleep(2)
            body_txt = driver.find_element(By.TAG_NAME, "body").text
            data = json.loads(body_txt)
            merchant_no = str(data.get("naverPay", {}).get("referenceKey", ""))
            api_id = data.get("loginId") or data.get("userId") or data.get("id") or ""
            if api_id and account_id == "default":
                account_id = api_id
        except Exception as e:
            print(f"merchant_no 추출 실패: {e}")

        if not merchant_no:
            # 계정 저장은 하지만 명확한 에러 리턴
            save_id = original_account_id if original_account_id != "default" else account_id
            save_naver_cookies(save_id, cookies)
            return {"success": False,
                    "message": f"merchant_no 추출 실패. 셀러센터 대시보드 권한/가입 여부 확인 필요."}

        if account_id == "default" and merchant_no:
            account_id = f"naver_{merchant_no}"

        save_id = original_account_id if original_account_id != "default" else account_id
        save_naver_cookies(save_id, cookies)
        if callback: callback(f"네이버 로그인 완료! ({save_id})")
        return {"account_id": save_id, "merchant_no": merchant_no}
    except Exception as e:
        print(f"네이버 로그인 오류: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        try:
            if driver:
                driver.quit()
        except: pass


# ── 네이버 반품/취소/교환 크롤링 ──────────────────
RETURN_QUERY = """query findClaimReturnsBySummaryInfoTypeMp_ForClaimReturn($merchantNo: String!, $paging_page: Int, $paging_size: Int, $serviceType: String!, $sort_direction: SortDirectionType, $sort_type: SortType, $summaryInfoType: SummaryInfoType!, $sellerOrderSearchTypes: [SellerOrderSearchType]!) {
  returnList: findClaimReturnsBySummaryInfoTypeMp_ForClaimReturn(merchantNo: $merchantNo paging_page: $paging_page paging_size: $paging_size serviceType: $serviceType sort_direction: $sort_direction sort_type: $sort_type summaryInfoType: $summaryInfoType sellerOrderSearchTypes: $sellerOrderSearchTypes) {
    elements { ...returnElementField __typename }
    pagination { ...paginationField __typename }
    __typename
  }
}
fragment returnElementField on ClaimReturnSeller {
  returnCareTarget deliveryFeeClass holdbackStatus deliveryInvoiceNo orderQuantity productName
  payDateTime orderMemberId totalDiscountAmt orderNo productClass claimRequestDateTime
  claimRequestReason backDeliveryInvoiceNo saleChannelType deliveryCompanyName
  sellerProductManagementCode claimStatus orderMemberTelNo claimNo deliveryMethod
  merchantChannelNo productPayAmt receiverTelNo1 productUnitPrice orderMemberName
  productOrderNo productOptionContents claimDeliveryFeeAmt productOptionAmt productNo
  backDeliveryCompanyName receiverName deliveryNo refundDateTime deliveryFeeDiscountAmt
  syncDateTime productOrderStatus sellerInternalCode1 sellerInternalCode2
  deliveryBundleGroupSeq productUrl fulfillmentCompanyName
  collectRemoteAreaCostChargeAmt deliveryAttributeText initTotalDiscountAmt initProductPayAmt
  quantityClaimYn membershipsArrivalGuaranteeClaimSupportTarget receiverTelNo2 claimCollectStatus
  claimCollectDateTime claimRequestOperatorType branchId holdbackReleaseDateTime holdbackConfigDateTime
  refundOperator refundExpectDateTime claimCollectStatusExposureText backDeliveryMethod
  backDeliveryMethodExposureText claimCollectAddress returnReceiveAddress backDeliveryNo
  claimDeliveryFeePayMethod claimDeliveryFeePayMethodText claimExtraFeePayMethod
  claimExtraFeePayAmt claimRejectDetail claimRequestReasonCollectFail giftName biztalkAccountId
  branchDeliveryStartDateTime branchDeliveryEndDateTime discountAmtChangedInfo deliveryFeeChangedInfo
  standardGroupProductOptions deliveryFeeAmt orderMemberNo __typename
}
fragment paginationField on Pagination { size totalElements page totalPages __typename }"""


RETURN_DETAIL_QUERY = 'query findClaimReturnsByDetailConditionsMp_ForClaimReturn($claimStatus: ClaimStatusType, $dateRange_from: String, $dateRange_to: String, $detailSearch_keyword: String, $detailSearch_type: DetailSearchType, $merchantNo: String!, $paging_page: Int, $paging_size: Int, $rangeType: RangeType, $serviceType: String!, $sort_direction: SortDirectionType, $sort_type: SortType) {\n  returnList: findClaimReturnsByDetailConditionsMp_ForClaimReturn(\n    claimStatus: $claimStatus\n    dateRange_from: $dateRange_from\n    dateRange_to: $dateRange_to\n    detailSearch_keyword: $detailSearch_keyword\n    detailSearch_type: $detailSearch_type\n    merchantNo: $merchantNo\n    paging_page: $paging_page\n    paging_size: $paging_size\n    rangeType: $rangeType\n    serviceType: $serviceType\n    sort_direction: $sort_direction\n    sort_type: $sort_type\n  ) {\n    elements {\n      ...returnElementField\n      __typename\n    }\n    pagination {\n      ...paginationField\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment returnElementField on ClaimReturnSeller {\n  returnCareTarget\n  deliveryFeeClass\n  holdbackStatus\n  deliveryInvoiceNo\n  claimExtraFeePayAmt\n  orderQuantity\n  productName\n  payDateTime\n  deliveryFeeRatingClass\n  orderMemberId\n  discountAmtChangedInfo\n  refundExpectDateTime\n  claimCollectStatusExposureText\n  totalDiscountAmt\n  orderNo\n  productClass\n  claimCollectDateTime\n  deliveryFeeChangedInfo\n  claimRequestDateTime\n  claimRequestReason\n  backDeliveryInvoiceNo\n  refundOperator\n  saleChannelType\n  deliveryCompanyName\n  sellerProductManagementCode\n  holdbackReleaseDateTime\n  claimStatus\n  holdbackConfigDateTime\n  orderMemberTelNo\n  orderMemberNo\n  deliveryFeeAmt\n  claimNo\n  backDeliveryMethodExposureText\n  deliveryMethod\n  biztalkAccountId\n  branchDeliveryStartDateTime\n  branchDeliveryEndDateTime\n  branchId\n  merchantChannelNo\n  giftName\n  receiverTelNo2\n  productPayAmt\n  receiverTelNo1\n  claimCollectStatus\n  productUnitPrice\n  claimRequestOperatorType\n  orderMemberName\n  productOrderNo\n  productOptionContents\n  standardGroupProductOptions\n  claimCollectAddress\n  claimDeliveryFeeAmt\n  productOptionAmt\n  productNo\n  returnReceiveAddress\n  backDeliveryCompanyName\n  receiverName\n  deliveryNo\n  refundDateTime\n  deliveryFeeDiscountAmt\n  claimRejectDetail\n  backDeliveryMethod\n  syncDateTime\n  productOrderStatus\n  backDeliveryNo\n  sellerInternalCode2\n  sellerInternalCode1\n  deliveryBundleGroupSeq\n  productUrl\n  claimDeliveryFeePayMethod\n  claimDeliveryFeePayMethodText\n  claimExtraFeePayMethod\n  fulfillmentCompanyName\n  collectRemoteAreaCostChargeAmt\n  claimRequestReasonCollectFail\n  deliveryAttributeText\n  initTotalDiscountAmt\n  initProductPayAmt\n  quantityClaimYn\n  membershipsArrivalGuaranteeClaimSupportTarget\n  __typename\n}\n\nfragment paginationField on Pagination {\n  size\n  totalElements\n  page\n  totalPages\n  __typename\n}'

PURCHASE_DECISION_QUERY = 'query SmartStoreFindPurchaseDecisionsByDetailConditions_ForPurchaseDecision($merchantNo: String!, $serviceType: String!, $claimStatus: ClaimStatusType, $dateRange_from: String, $dateRange_to: String, $detailSearch_keyword: String, $detailSearch_type: DetailSearchType, $paging_page: Int, $paging_size: Int, $rangeType: RangeType, $sort_direction: SortDirectionType, $sort_type: SortType) {\n  purchaseDecisionList: SmartStoreFindPurchaseDecisionsByDetailConditions_ForPurchaseDecision(\n    merchantNo: $merchantNo\n    serviceType: $serviceType\n    claimStatus: $claimStatus\n    dateRange_from: $dateRange_from\n    dateRange_to: $dateRange_to\n    detailSearch_keyword: $detailSearch_keyword\n    detailSearch_type: $detailSearch_type\n    paging_page: $paging_page\n    paging_size: $paging_size\n    rangeType: $rangeType\n    sort_direction: $sort_direction\n    sort_type: $sort_type\n  ) {\n    elements {\n      ...purchaseDecisionElementField\n      __typename\n    }\n    pagination {\n      ...paginationField\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment purchaseDecisionElementField on PurchaseDecisionSeller {\n  returnCareTarget\n  branchId\n  merchantChannelNo\n  deliveryFeeAmt\n  deliveryFeeClass\n  deliveryMethod\n  biztalkAccountId\n  deliveryInvoiceNo\n  productPayAmt\n  orderStatus\n  productUnitPrice\n  purchaseDecisionCompleteDateTime\n  orderQuantity\n  productName\n  orderMemberName\n  payDateTime\n  productOrderNo\n  productOptionContents\n  standardGroupProductOptions\n  deliveryFeeRatingClass\n  orderMemberId\n  knowledgeShoppingCommissionAmt\n  remoteAreaCostChargeAmt\n  productOptionAmt\n  productNo\n  payLocationType\n  totalDiscountAmt\n  orderNo\n  payMeansClass\n  productClass\n  inflowPath\n  receiverName\n  settlementExpectAmt\n  deliveryNo\n  deliveryCompleteDateTime\n  saleChannelType\n  sellerDiscountAmt\n  deliveryCompanyName\n  deliveryFeeDiscountAmt\n  dispatchDateTime\n  sellerProductManagementCode\n  payCommissionAmt\n  syncDateTime\n  productOrderStatus\n  sellerInternalCode2\n  sellerInternalCode1\n  deliveryBundleGroupSeq\n  productUrl\n  fulfillmentCompanyName\n  sellerOptionManagementCode\n  deliveryAttributeText\n  initTotalDiscountAmt\n  initProductPayAmt\n  membershipsArrivalGuaranteeClaimSupportTarget\n  __typename\n}\n\nfragment paginationField on Pagination {\n  size\n  totalElements\n  page\n  totalPages\n  __typename\n}'

CANCEL_DETAIL_QUERY = 'query findClaimCancelsByDetailConditionsMp_ForClaimCancel($claimStatus: ClaimStatusType, $dateRange_from: String, $dateRange_to: String, $detailSearch_keyword: String, $detailSearch_type: DetailSearchType, $merchantNo: String!, $paging_page: Int, $paging_size: Int, $rangeType: RangeType, $serviceType: String!, $sort_direction: SortDirectionType, $sort_type: SortType) {\n  cancelListMp: findClaimCancelsByDetailConditionsMp_ForClaimCancel(\n    claimStatus: $claimStatus\n    dateRange_from: $dateRange_from\n    dateRange_to: $dateRange_to\n    detailSearch_keyword: $detailSearch_keyword\n    detailSearch_type: $detailSearch_type\n    merchantNo: $merchantNo\n    paging_page: $paging_page\n    paging_size: $paging_size\n    rangeType: $rangeType\n    serviceType: $serviceType\n    sort_direction: $sort_direction\n    sort_type: $sort_type\n  ) {\n    elements {\n      ...cancelElementField\n      __typename\n    }\n    pagination {\n      ...paginationField\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment cancelElementField on CancelClaimSeller {\n  deliveryFeeAmt\n  deliveryFeeClass\n  biztalkAccountId\n  giftName\n  receiverTelNo2\n  productPayAmt\n  receiverTelNo1\n  productUnitPrice\n  cancelDateTime\n  orderQuantity\n  productName\n  claimRequestOperatorType\n  clamRequestDateTime\n  orderMemberName\n  payDateTime\n  productOrderNo\n  productOptionContents\n  standardGroupProductOptions\n  deliveryFeeRatingClass\n  orderMemberId\n  orderMemberNo\n  productOptionAmt\n  discountAmtChangedInfo\n  productNo\n  refundExpectDateTime\n  totalDiscountAmt\n  claimRequestAdmissionOperator\n  orderNo\n  productClass\n  receiverName\n  deliveryFeeChangedInfo\n  claimRequestReason\n  refundOperator\n  saleChannelType\n  receiverAddress\n  deliveryFeeDiscountAmt\n  receiverZipCode\n  sellerProductManagementCode\n  syncDateTime\n  productOrderStatus\n  sellerInternalCode2\n  claimRequestAdmissionDateTime\n  sellerInternalCode1\n  deliveryBundleGroupSeq\n  productUrl\n  claimStatus\n  orderMemberTelNo\n  fulfillmentCompanyName\n  deliveryAttributeText\n  initTotalDiscountAmt\n  initProductPayAmt\n  quantityClaimYn\n  __typename\n}\n\nfragment paginationField on Pagination {\n  size\n  totalElements\n  page\n  totalPages\n  __typename\n}'

EXCHANGE_DETAIL_QUERY = 'query SmartStoreFindClaimExchangesByDetailConditions_ForClaimExchange($claimStatus: ClaimStatusType, $dateRange_from: String, $dateRange_to: String, $detailSearch_keyword: String, $detailSearch_type: DetailSearchType, $memberNo: String, $merchantNo: String!, $serviceType: String!, $paging_page: Int, $paging_size: Int, $rangeType: RangeType, $sort_direction: SortDirectionType, $sort_type: SortType) {\n  exchangeList: SmartStoreFindClaimExchangesByDetailConditions_ForClaimExchange(\n    claimStatus: $claimStatus\n    dateRange_from: $dateRange_from\n    dateRange_to: $dateRange_to\n    detailSearch_keyword: $detailSearch_keyword\n    detailSearch_type: $detailSearch_type\n    memberNo: $memberNo\n    serviceType: $serviceType\n    merchantNo: $merchantNo\n    paging_page: $paging_page\n    paging_size: $paging_size\n    rangeType: $rangeType\n    sort_direction: $sort_direction\n    sort_type: $sort_type\n  ) {\n    elements {\n      ...exchangeElementField\n      __typename\n    }\n    pagination {\n      ...paginationField\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment exchangeElementField on ClaimExchangeSeller {\n  lastClaimNo\n  beforeClaimNo\n  reDeliveryAddress\n  returnCareTarget\n  branchId\n  merchantChannelNo\n  deliveryFeeClass\n  redeliveryOperationDateTime\n  holdbackStatus\n  deliveryInvoiceNo\n  claimExtraFeePayAmt\n  reDeliveryNo\n  orderQuantity\n  productName\n  claimType\n  payDateTime\n  deliveryFeeRatingClass\n  purchaseDecisionExtensionReasonDetailContent\n  orderMemberId\n  reDeliveryStatus\n  claimCollectStatusExposureText\n  totalDiscountAmt\n  claimRejectDetailContent\n  orderNo\n  productClass\n  claimCollectDateTime\n  reDeliveryInvoiceNo\n  purchaseDecisionExtensionReason\n  claimRequestReason\n  backDeliveryInvoiceNo\n  exchangeRequestDateTime\n  reDeliveryCompanyName\n  deliveryCompanyName\n  sellerProductManagementCode\n  holdbackReleaseDateTime\n  claimStatus\n  holdbackConfigDateTime\n  orderMemberTelNo\n  orderMemberNo\n  purchaseDecisionExtensionDateTime\n  deliveryFeeAmt\n  claimNo\n  backDeliveryMethodExposureText\n  deliveryMethod\n  biztalkAccountId\n  giftName\n  receiverTelNo2\n  productPayAmt\n  receiverTelNo1\n  claimCollectStatus\n  productUnitPrice\n  claimRequestOperatorType\n  orderMemberName\n  productOrderNo\n  productOptionContents\n  standardGroupProductOptions\n  claimCollectAddress\n  claimDeliveryFeeAmt\n  productOptionAmt\n  productNo\n  purchaseDecisionExpectDateTime\n  returnReceiveAddress\n  backDeliveryCompanyName\n  receiverName\n  deliveryNo\n  deliveryFeeDiscountAmt\n  reDeliveryMethod\n  syncDateTime\n  productOrderStatus\n  backDeliveryNo\n  sellerInternalCode2\n  sellerInternalCode1\n  deliveryBundleGroupSeq\n  productUrl\n  claimDeliveryFeePayMethod\n  claimDeliveryFeePayMethodText\n  claimExtraFeePayMethod\n  fulfillmentCompanyName\n  collectRemoteAreaCostChargeAmt\n  claimRequestReasonCollectFail\n  deliveryAttributeText\n  purchaseDecisionExtensionStatusType\n  initTotalDiscountAmt\n  initProductPayAmt\n  quantityClaimYn\n  membershipsArrivalGuaranteeClaimSupportTarget\n  __typename\n}\n\nfragment paginationField on Pagination {\n  size\n  totalElements\n  page\n  totalPages\n  __typename\n}'

NAVER_CLAIM_STATUS_MAP = {
    "RETURN_REQUEST": "반품요청",
    "COLLECTING": "반품요청",
    "COLLECT_DONE": "반품요청",
    "RETURN_DONE": "반품완료",
    "RETURN_WITHDRAW": "반품완료",
}


def _normalize_naver_claim(item, account_id=""):
    """네이버 반품 데이터 정규화"""
    return {
        "orderId": item.get("orderNo", ""),
        "cancelId": item.get("claimNo", ""),
        "orderedAt": _ts_to_str(item.get("claimRequestDateTime") or item.get("payDateTime")),
        "orderItems": [{
            "vendorItemPackageName": item.get("productName", ""),
            "orderPrice": int(item.get("productPayAmt") or 0),
            "vendorItemId": str(item.get("productNo") or ""),
            "sellerProductCode": item.get("sellerProductManagementCode") or "",
            "orderQuantity": int(item.get("orderQuantity") or 1),
        }],
        "receiver": {
            "name": item.get("receiverName", ""),
            "safeNumber": item.get("receiverTelNo1") or "",
            "addr1": "",
            "addr2": "",
        },
        "amount": int(item.get("productPayAmt") or 0),
        "refundStatus": item.get("claimStatus") or item.get("claimCollectStatus") or "",
        "returnReason": item.get("claimRequestReason") or "",
        "memberName": item.get("orderMemberName", ""),
        "memberPhoneNumber": item.get("orderMemberTelNo", ""),
        "deliveryMemo": "",
        "parcelPrintMessage": "",
        "linked_username": account_id,
        "market": "naver",
        "productOptionContents": item.get("productOptionContents") or "",
    }


async def scrape_naver_claims(account_id="default", merchant_no=None, start_date=None, end_date=None, callback=None):
    """네이버 반품 크롤링"""
    if not merchant_no:
        accs = []
        p = _data_path("naver_accounts.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                accs = json.load(f)
        for a in accs:
            if a.get("account_id") == account_id:
                merchant_no = a.get("merchant_no", "")
                break
    if not merchant_no:
        return {}

    result = {"출고중지요청": [], "반품요청": [], "교환요청": [], "출고중지완료": [], "반품완료": [], "교환완료": []}

    if not end_date:
        end_date = datetime.date.today().strftime("%Y-%m-%d")
    if not start_date:
        start_date = (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    start_d = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    end_d = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    from_ts = str(int(datetime.datetime.combine(start_d, datetime.time.min).timestamp() * 1000))
    to_ts = str(int(datetime.datetime.combine(end_d + datetime.timedelta(days=1), datetime.time.min).timestamp() * 1000 - 1))

    async with async_playwright() as p:
        chrome = _find_chromium_executable()
        browser = await p.chromium.launch(headless=True, executable_path=chrome)
        context = await browser.new_context()
        cookies = load_naver_cookies(account_id) or load_naver_cookies("default")
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto("https://sell.smartstore.naver.com/#/home/dashboard", wait_until="domcontentloaded")
        await asyncio.sleep(2)

        search_types = ["NORMAL_ORDER", "GIFTING", "TODAY_DISPATCH", "PRE_ORDER", "SUBSCRIPTION", "RENTAL", "ARRIVAL_GUARANTEE"]

        for status_type in ["RETURN_REQUEST", "COLLECTING", "COLLECT_DONE", "RETURN_DONE"]:
            if callback:
                callback(f"네이버 반품({status_type}) 수집 중...")
            try:
                resp = await context.request.post(GRAPHQL_URL,
                    data=json.dumps({
                        "operationName": "findClaimReturnsByDetailConditionsMp_ForClaimReturn",
                        "variables": {
                            "merchantNo": merchant_no, "serviceType": "MP",
                            "paging_page": 1, "paging_size": 100,
                            "claimStatus": status_type,
                            "rangeType": "RETURN_REQUEST",
                            "dateRange_from": from_ts,
                            "dateRange_to": to_ts,
                            },
                        "query": RETURN_DETAIL_QUERY,
                    }),
                    headers={"Content-Type": "application/json", "Accept": "application/json"})

                if resp.ok:
                    d = await resp.json()
                    if not d.get("errors"):
                        cl = d.get("data", {}).get("returnList", {})
                        elements = cl.get("elements", [])
                        tab = NAVER_CLAIM_STATUS_MAP.get(status_type, "반품요청")
                        for item in elements:
                            result[tab].append(_normalize_naver_claim(item, account_id))
            except Exception as e:
                print(f"네이버 반품 오류 ({status_type}): {e}")

        # 취소 수집
        for cstatus in ["CANCEL_REQUEST", "CANCEL_DONE"]:
            if callback:
                callback(f"네이버 취소({cstatus}) 수집 중...")
            try:
                resp = await context.request.post(GRAPHQL_URL,
                    data=json.dumps({
                        "operationName": "findClaimCancelsByDetailConditionsMp_ForClaimCancel",
                        "variables": {
                            "merchantNo": merchant_no, "serviceType": "MP",
                            "paging_page": 1, "paging_size": 100,
                            "claimStatus": cstatus, "rangeType": "CLAIM_REQUEST",
                            "dateRange_from": from_ts, "dateRange_to": to_ts,
                        },
                        "query": CANCEL_DETAIL_QUERY,
                    }),
                    headers={"Content-Type": "application/json", "Accept": "application/json"})
                if resp.ok:
                    d = await resp.json()
                    if not d.get("errors"):
                        cl = d.get("data", {}).get("cancelListMp", {})
                        elements = cl.get("elements", [])
                        tab = "출고중지요청" if "REQUEST" in cstatus else "출고중지완료"
                        for item in elements:
                            result[tab].append(_normalize_naver_claim(item, account_id))
            except Exception as e:
                print(f"네이버 취소 오류 ({cstatus}): {e}")

        # 교환 수집
        for estatus in ["EXCHANGE_REQUEST", "EXCHANGE_DONE"]:
            if callback:
                callback(f"네이버 교환({estatus}) 수집 중...")
            try:
                resp = await context.request.post(GRAPHQL_URL,
                    data=json.dumps({
                        "operationName": "SmartStoreFindClaimExchangesByDetailConditions_ForClaimExchange",
                        "variables": {
                            "merchantNo": merchant_no, "serviceType": "MP",
                            "paging_page": 1, "paging_size": 100,
                            "claimStatus": estatus, "rangeType": "EXCHANGE_REQUEST",
                            "dateRange_from": from_ts, "dateRange_to": to_ts,
                        },
                        "query": EXCHANGE_DETAIL_QUERY,
                    }),
                    headers={"Content-Type": "application/json", "Accept": "application/json"})
                if resp.ok:
                    d = await resp.json()
                    if not d.get("errors"):
                        cl = d.get("data", {}).get("exchangeList", {})
                        elements = cl.get("elements", [])
                        tab = "교환요청" if "REQUEST" in estatus else "교환완료"
                        for item in elements:
                            result[tab].append(_normalize_naver_claim(item, account_id))
            except Exception as e:
                print(f"네이버 교환 오류 ({estatus}): {e}")

        await browser.close()

    if callback:
        total = sum(len(v) for v in result.values())
        callback(f"네이버 클레임 {total}건 수집 완료")
    return result


def get_naver_claims(account_id="default", merchant_no=None, start_date=None, end_date=None, callback=None):
    """네이버 반품 수집 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_naver_claims(account_id, merchant_no, start_date, end_date, callback))
    except Exception as e:
        print(f"네이버 반품 오류: {e}")
        return {"반품요청": [], "반품완료": []}
    finally:
        loop.close()


# ═══════════════════════════════════════════
# 네이버 송장등록 (배송처리)
# ═══════════════════════════════════════════
INVOICE_MUTATION = """mutation updateDeliveryInvoiceInfoList_ForSaleDelivery($merchantNo: String!, $serviceType: String!, $deliveryInvoiceInfoList: [DeliveryInvoiceInfoInput!]!) {
  updateDeliveryInvoiceInfoList_ForSaleDelivery(merchantNo: $merchantNo, serviceType: $serviceType, deliveryInvoiceInfoList: $deliveryInvoiceInfoList) {
    success
    failure {
      productOrderNo
      errorMessage
      __typename
    }
    __typename
  }
}"""


async def scrape_register_naver_invoices(account_id, merchant_no, orders, callback=None):
    """네이버 스마트스토어 송장 일괄 등록.

    orders: [{"productOrderNo": str, "deliveryCompanyCode": str, "invoiceNumber": str, "deliveryMethodType": str}, ...]
    반환: {"success": 성공건수, "fail": 실패건수, "errors": [에러문자열]}
    """
    if not orders:
        return {"success": 0, "fail": 0, "errors": []}

    # merchant_no 자동 로드
    if not merchant_no:
        try:
            p = _data_path("naver_accounts.json")
            if os.path.exists(p):
                with open(p, "r", encoding="utf-8") as f:
                    accs = json.load(f)
                for a in accs:
                    if str(a.get("account_id")) == str(account_id):
                        merchant_no = a.get("merchant_no", "")
                        break
        except: pass
    if not merchant_no:
        return {"success": 0, "fail": len(orders), "errors": ["merchant_no 없음 — 재연동 필요"]}

    async with async_playwright() as p:
        chrome = _find_chromium_executable()
        browser = await p.chromium.launch(headless=True, executable_path=chrome)
        context = await browser.new_context()
        cookies = load_naver_cookies(account_id) or load_naver_cookies("default")
        if cookies:
            await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto(NAVER_BASE, wait_until="domcontentloaded")
        await asyncio.sleep(1)

        # GraphQL payload 작성 — 한 번에 일괄 전송
        invoice_list = []
        for o in orders:
            item = {
                "productOrderNo": str(o.get("productOrderNo", "") or o.get("orderId", "")),
                "deliveryCompanyCode": o.get("deliveryCompanyCode") or o.get("courierCode", ""),
                "deliveryInvoiceNumber": o.get("invoiceNumber", ""),
                "deliveryMethodType": o.get("deliveryMethodType", "DELIVERY"),
            }
            invoice_list.append(item)

        variables = {
            "merchantNo": str(merchant_no),
            "serviceType": "MP",
            "deliveryInvoiceInfoList": invoice_list,
        }

        if callback:
            callback(f"네이버 송장 {len(invoice_list)}건 등록 요청 중...")

        success_cnt = 0
        fail_cnt = 0
        errors = []
        try:
            resp = await context.request.post(
                GRAPHQL_URL,
                data=json.dumps({
                    "operationName": "updateDeliveryInvoiceInfoList_ForSaleDelivery",
                    "variables": variables,
                    "query": INVOICE_MUTATION,
                }),
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
            body = await resp.json()
            if body.get("errors"):
                errs = body.get("errors", [])
                msgs = [e.get("message", "") for e in errs]
                fail_cnt = len(invoice_list)
                errors.extend(msgs)
            else:
                result = (body.get("data") or {}).get("updateDeliveryInvoiceInfoList_ForSaleDelivery") or {}
                success_cnt = int(result.get("success") or 0)
                failure_list = result.get("failure") or []
                fail_cnt = len(failure_list)
                for f in failure_list:
                    errors.append(f"{f.get('productOrderNo','')}: {f.get('errorMessage','')}")
                # success 가 숫자가 아니라 리스트/누락일 수도 있음 — 보정
                if success_cnt == 0 and not failure_list:
                    success_cnt = len(invoice_list)
        except Exception as e:
            fail_cnt = len(invoice_list)
            errors.append(f"요청 오류: {e}")

        await browser.close()

        if callback:
            callback(f"네이버 송장 등록 완료: 성공 {success_cnt} / 실패 {fail_cnt}")
        return {"success": success_cnt, "fail": fail_cnt, "errors": errors}


def register_invoices_on_naver(account_id, merchant_no, orders, callback=None):
    """네이버 송장등록 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_register_naver_invoices(account_id, merchant_no, orders, callback))
    except Exception as e:
        print(f"네이버 송장등록 오류: {e}")
        return {"success": 0, "fail": len(orders) if orders else 0, "errors": [str(e)]}
    finally:
        loop.close()
