import asyncio
import json
import urllib.parse
import datetime
import os
from playwright.async_api import async_playwright
from coupang_auth import load_cookies, save_cookies, _find_chromium_executable

BASE_URL   = "https://wing.coupang.com"

SEARCH_API = f"{BASE_URL}/tenants/sfl-portal/delivery/management/dashboard/search"


async def _login_and_get_page(playwright, username, password):
    _chrome_path = _find_chromium_executable()
    browser = await playwright.chromium.launch(headless=True, executable_path=_chrome_path)
    context = await browser.new_context()
    cookies = load_cookies(username)
    if cookies:
        try: await context.add_cookies(cookies)
        except: pass
    page = await context.new_page()
    await page.goto(BASE_URL, wait_until="domcontentloaded")
    await asyncio.sleep(0.5)
    if "login" in page.url:
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await asyncio.sleep(0.5)
        await page.fill('#username', username)
        await page.fill('#password', password)
        await page.click('#kc-login')
        await asyncio.sleep(0.5)
        if "login" in page.url:
            await browser.close()
            return None, None, None
        new_cookies = await context.cookies()
        save_cookies(username, [dict(c) for c in new_cookies])
    return browser, context, page


async def _fetch_raw(page, start_date, end_date, status_code, callback=None, label=""):
    """단일 status_code로 API 호출 (context.request 직접 호출로 고속화)"""
    # page에서 context 추출
    context = page.context
    all_items = []
    next_box_id = None
    page_num = 1
    count_per_page = 50

    while True:
        condition = {
            "nextShipmentBoxId": next_box_id,
            "startDate": start_date,
            "endDate": end_date,
            "deliveryStatus": status_code,
            "deliveryMethod": None,
            "detailConditionKey": "NAME",
            "detailConditionValue": None,
            "selectedComplexConditionKey": None,
            "deliverCode": None,
            "storePickupStatus": None,
            "isEsdToday": None,
            "isEsdIn5d": None,
            "isEsdTmr": None,
            "countPerPage": count_per_page,
            "page": page_num,
            "shipmentType": None,
        }
        encoded = urllib.parse.quote(json.dumps(condition, ensure_ascii=False))
        url = f"{SEARCH_API}?condition={encoded}&mockingTestMode=false"

        try:
            resp = await context.request.get(
                url,
                headers={"Accept": "application/json"}
            )
            if not resp.ok:
                break
            result = await resp.json()

            items = []
            if isinstance(result, list):
                items = result
            elif isinstance(result, dict):
                data = result.get("data")
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get("content") or data.get("list") or []
                else:
                    items = result.get("content") or result.get("list") or []

            if not items:
                break

            all_items.extend(items)
            if callback:
                callback(f"{label}[{status_code}]: {len(all_items)}건 수집 중...")

            if len(items) < count_per_page:
                break

            next_box_id = items[-1].get("shipmentBoxId")
            if not next_box_id:
                break
            page_num += 1

        except Exception as e:
            print(f"API 오류 ({status_code} p{page_num}): {e}")
            break

    return all_items


def _normalize(raw, username):
    """실제 API 응답 필드 기준 정규화"""
    result = []
    for o in raw:
        if not isinstance(o, dict):
            continue

        # 상품명/가격
        raw_items = o.get("items") or []
        if raw_items:
            norm_items = [{
                "vendorItemPackageName": (
                    it.get("vendorItemName") or
                    it.get("vendorInventoryItemName") or
                    it.get("productName") or
                    it.get("itemName") or ""
                ),
                "orderPrice": int(it.get("salePrice") or it.get("orderPrice") or 0),
                "vendorItemId": str(it.get("vendorItemId") or it.get("optionSrl") or ""),
                "sellerProductCode": "",
                "orderQuantity": int(it.get("count") or it.get("quantity") or it.get("purchaseCount") or 1),
            } for it in raw_items]
        else:
            norm_items = [{"vendorItemPackageName": "", "orderPrice": 0, "vendorItemId": "", "sellerProductCode": "", "orderQuantity": 1}]

        # 안심번호
        safe = ""
        dto = o.get("safeNumberDto")
        if isinstance(dto, dict):
            safe = dto.get("safeNumber") or ""
        if not safe:
            safe = o.get("receiverMobile") or ""

        receiver = {
            "name":       o.get("receiverName") or o.get("memberName") or "",
            "safeNumber": safe,
            "addr1":      o.get("addr1") or "",
            "addr2":      o.get("addr2") or "",
        }

        memo = o.get("message") or o.get("remark") or ""

        result.append({
            "orderId":            str(o.get("orderId") or o.get("shipmentBoxId") or ""),
            "shipmentBoxId":      str(o.get("shipmentBoxId") or ""),
            "realOrderId":        str(o.get("orderId") or ""),
            "orderedAt":          o.get("paidAt") or o.get("createdAt") or "",
            "orderItems":         norm_items,
            "receiver":           receiver,
            "parcelPrintMessage": memo,
            "deliveryMemo":       memo,
            "linked_username":    username,
            "confirmed":          o.get("confirmed", False),
            "deliveryStatusCode": o.get("deliveryStatusCode") or "",
            "invoiceNumber":      o.get("invoiceNumber") or "",
            "deliverCode":        o.get("deliverCode") or o.get("courierCode") or "",
            "deliverName":        o.get("deliverName") or o.get("courierName") or "",
            "totalPrice":         0,
            "memberName":         o.get("memberName") or "",
            "memberPhoneNumber":  o.get("lastFourMobileNumber") or "",
        })
    return result


async def scrape_orders_all(username, password, start_date, end_date, callback=None):
    """주문 5종 병렬 수집 - 반품/교환 없음"""
    done_end = end_date
    done_start = start_date

    result = {"결제완료":[],"발송대기":[],"배송지시":[],"배송중":[],"배송완료":[]}

    async with async_playwright() as p:
        browser, context, page = await _login_and_get_page(p, username, password)
        if not browser:
            return result

        if callback: callback(f"{username}: 전체 상태 병렬 수집 중...")

        accept_raw, instruct_raw, departure_raw, delivering_raw, final_raw = await asyncio.gather(
            _fetch_raw(page, start_date, end_date, "ACCEPT", callback, username),
            _fetch_raw(page, done_start, done_end, "INSTRUCT", callback, username),
            _fetch_raw(page, done_start, done_end, "DEPARTURE", callback, username),
            _fetch_raw(page, done_start, done_end, "DELIVERING", callback, username),
            _fetch_raw(page, done_start, done_end, "FINAL_DELIVERY", callback, username),
        )

        norm = _normalize(accept_raw, username)
        result["결제완료"] = [o for o in norm if not o.get("confirmed")]
        result["발송대기"] = _normalize(instruct_raw, username)
        result["배송지시"] = _normalize(departure_raw, username)
        result["배송중"] = _normalize(delivering_raw, username)
        result["배송완료"] = _normalize(final_raw, username)

        if callback: callback(f"{username}: 가격 조회 중...")
        all_orders = result["결제완료"]+result["발송대기"]+result["배송지시"]+result["배송중"]+result["배송완료"]
        await _fetch_order_prices(context, all_orders)

        await browser.close()
    return result


def get_all_orders_only(username, password, start_date, end_date, callback=None):
    """주문 5종만 수집 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            scrape_orders_all(username, password, start_date, end_date, callback)
        )
        return {"code": 200, "data": result}
    except Exception as e:
        print(f"주문수집 오류: {e}")
        return {"code": 500, "data": {}}
    finally:
        loop.close()


# ── 반품/교환/취소 크롤링 ──────────────────────────────
ORDER_DETAIL_API = f"{BASE_URL}/tenants/sfl-portal/order/detail"
RETURN_API = f"{BASE_URL}/tenants/sfl-portal/return-delivery/search"

def _norm_claim(item, username):
    """반품/교환/취소 항목 정규화"""
    # items 배열에서 상품명/vendorItemId 추출 (반품/교환/출고중지 각각 다른 필드명)
    sub_items = (item.get("items") or item.get("stopShipmentResponseItemDtos") or
                 item.get("omsSimpleOrderItemDtos") or item.get("productInfoList") or [])
    if sub_items and isinstance(sub_items, list) and isinstance(sub_items[0], dict):
        si = sub_items[0]
        p_name = si.get("vendorItemName") or si.get("productName") or si.get("vendorInventoryName") or ""
        vid = str(si.get("vendorItemId") or "")
    else:
        p_name = (item.get("productName") or item.get("vendorItemName") or
                  item.get("vendorItemPackageName") or item.get("vendorInventoryItemName") or
                  item.get("itemName") or item.get("exposedProductName") or "")
        vid = str(item.get("vendorItemId") or "")
    return {
        "orderId":    str(item.get("orderId", "")),
        "cancelId":   str(item.get("cancelId", "")),
        "orderedAt":  item.get("receiptDate") or item.get("orderedAt") or "",
        "orderItems": [{
            "vendorItemPackageName": p_name,
            "orderPrice": int(item.get("amount") or item.get("salePrice") or 0),
            "vendorItemId": vid,
            "sellerProductCode": "",
        }],
        "receiver": {
            "name":      item.get("receiverName") or item.get("ordererName") or "",
            "safeNumber": item.get("receiverPhoneNumber") or "",
            "addr1":     item.get("deliveryAddress") or "",
            "addr2":     "",
        },
        "amount":       int(item.get("amount") or 0),
        "refundStatus": item.get("refundStatus") or item.get("shipmentStopStatus") or "",
        "returnReason": item.get("returnReason") or item.get("cancelReason") or "",
        "courierName":  item.get("courierName") or item.get("deliveryCompanyName") or item.get("returnDeliveryCompanyName") or "",
        "invoiceNumber": item.get("invoiceNumber") or item.get("returnInvoiceNumber") or "",
        "deliveryMemo": "",
        "parcelPrintMessage": "",
        "linked_username": username,
    }

RETURN_LIST_URL = f"{BASE_URL}/tenants/sfl-portal/return-delivery/list"
STOP_API = f"{BASE_URL}/tenants/sfl-portal/stop-shipment/search"
STOP_LIST_URL = f"{BASE_URL}/tenants/sfl-portal/stop-shipment/list"
EXCHANGE_API = f"{BASE_URL}/tenants/sfl-portal/exchange/search"
EXCHANGE_LIST_URL = f"{BASE_URL}/tenants/sfl-portal/exchange/list"

async def scrape_returns(username, password, refund_status="REQUEST",
                         start_date=None, end_date=None, callback=None):
    """
    반품/교환/취소 수집
    refund_status:
      - "REQUEST"            : 반품접수
      - "COLLECTING"         : 반품진행
      - "COLLECTED"          : 수거완료
      - "REFUND_COMPLETED"   : 반품완료
      - "EXCHANGE_REQUEST"   : 교환접수
      - "CANCEL_REQUEST"     : 출고중지요청
    """
    async with async_playwright() as p:
        browser, context, page = await _login_and_get_page(p, username, password)
        if not browser:
            return []

        if callback: callback(f"{username}: 반품/교환 준비 중...")

        # 반품 페이지 방문 (XSRF 토큰 세팅)
        await page.goto(RETURN_LIST_URL)
        await asyncio.sleep(0.5)

        # XSRF 토큰 추출
        all_cookies = await context.cookies()
        xsrf_token = ""
        for c in all_cookies:
            if 'xsrf' in c['name'].lower() or 'csrf' in c['name'].lower():
                xsrf_token = c['value']
                break

        if not xsrf_token:
            if callback: callback(f"{username}: XSRF 토큰 없음")
            await browser.close()
            return []

        all_items = []
        current_page = 0

        while True:
            body = {
                "refundStatus": refund_status,
                "wingCoupangConfirmStatus": None,
                "from": start_date,
                "to": end_date,
                "orderId": None,
                "cancelId": None,
                "searchKeywordValue": None,
                "pagePredicate": {"currentPage": current_page}
            }

            try:
                resp = await context.request.post(
                    RETURN_API,
                    data=json.dumps(body),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                        "x-xsrf-token": xsrf_token,
                        "Referer": RETURN_LIST_URL,
                    }
                )
                data = await resp.json()

                content = data.get("content", [])
                pagination = data.get("pagination", {})

                if not content:
                    break

                all_items.extend(content)

                if callback:
                    callback(f"{username}: [{refund_status}] {len(all_items)}건 수집 중...")

                total_pages = pagination.get("totalPages", 1)
                if current_page + 1 >= total_pages:
                    break

                current_page += 1

            except Exception as e:
                print(f"반품 API 오류 (p{current_page}): {e}")
                break

        await browser.close()

    # 정규화
    result = []
    for item in all_items:
        items_list = item.get("productInfoList") or item.get("orderItems") or []
        norm_items = []
        for it in items_list:
            norm_items.append({
                "vendorItemPackageName": it.get("productName") or it.get("vendorItemName") or it.get("vendorItemPackageName") or it.get("vendorInventoryItemName") or it.get("itemName") or it.get("sellerProductName") or it.get("exposedProductName") or "",
                "orderPrice": int(it.get("salePrice") or it.get("price") or 0),
                "vendorItemId": str(it.get("vendorItemId") or it.get("optionSrl") or ""),
                "sellerProductCode": "",
            })
        if not norm_items:
            pn = item.get("productName") or item.get("vendorItemName") or item.get("vendorItemPackageName") or item.get("vendorInventoryItemName") or item.get("itemName") or item.get("sellerProductName") or item.get("exposedProductName") or ""
            norm_items = [{"vendorItemPackageName": pn, "orderPrice": int(item.get("amount", 0)), "vendorItemId": str(item.get("vendorItemId","") or ""), "sellerProductCode": ""}]

        result.append({
            "orderId": str(item.get("orderId", "")),
            "cancelId": str(item.get("cancelId", "")),
            "orderedAt": item.get("receiptDate") or item.get("orderedAt") or "",
            "orderItems": norm_items,
            "receiver": {
                "name": item.get("receiverName") or item.get("ordererName") or "",
                "safeNumber": item.get("receiverPhoneNumber") or "",
                "addr1": item.get("deliveryAddress") or "",
                "addr2": "",
            },
            "amount": int(item.get("amount", 0)),
            "refundStatus": item.get("refundStatus", ""),
            "returnReason": item.get("returnReason") or item.get("cancelReason") or "",
            "courierName": item.get("courierName") or item.get("deliveryCompanyName") or item.get("returnDeliveryCompanyName") or "",
            "invoiceNumber": item.get("invoiceNumber") or item.get("returnInvoiceNumber") or "",
            "deliveryMemo": "",
            "parcelPrintMessage": "",
            "linked_username": username,
        })

    return result


async def scrape_all_with_returns(username, password, start_date, end_date, callback=None):
    """주문 5종 + 반품/교환/취소 한번에 수집"""
    today = datetime.date.today()
    done_end = end_date
    done_start = start_date
    two_weeks_end   = end_date
    two_weeks_start = start_date

    result = {
        "결제완료": [], "발송대기": [], "배송지시": [],
        "배송중": [],   "배송완료": [],
        "출고중지요청": [], "반품요청": [], "교환요청": [],
        "출고중지완료": [], "반품완료": [], "교환완료": [],
    }

    async with async_playwright() as p:
        browser, context, page = await _login_and_get_page(p, username, password)
        if not browser:
            return result

        if callback: callback(f"{username}: 준비 중...")

        # ── 주문 5종 (기존 scrape_all_statuses 와 완전 동일) ──
        if callback: callback(f"{username}: [결제완료/발송대기] 수집 중...")
        accept_raw = await _fetch_raw(page, start_date, end_date, "ACCEPT", callback, username)
        accept_norm = _normalize(accept_raw, username)
        result["결제완료"] = [o for o in accept_norm if not o.get("confirmed")]
        result["발송대기"] = [o for o in accept_norm if o.get("confirmed")]

        # 발송대기 = INSTRUCT (송장 미등록)
        if callback: callback(f"{username}: [발송대기] 수집 중...")
        raw = await _fetch_raw(page, done_start, done_end, "INSTRUCT", callback, username)
        result["발송대기"] = _normalize(raw, username)

        # 배송지시 = DEPARTURE
        if callback: callback(f"{username}: [배송지시] 수집 중...")
        raw = await _fetch_raw(page, done_start, done_end, "DEPARTURE", callback, username)
        result["배송지시"] = _normalize(raw, username)

        # 배송중 = DELIVERING
        if callback: callback(f"{username}: [배송중] 수집 중...")
        raw = await _fetch_raw(page, done_start, done_end, "DELIVERING", callback, username)
        result["배송중"] = _normalize(raw, username)

        # 배송완료 = FINAL_DELIVERY
        if callback: callback(f"{username}: [배송완료] 수집 중...")
        raw = await _fetch_raw(page, done_start, done_end, "FINAL_DELIVERY", callback, username)
        result["배송완료"] = _normalize(raw, username)

        # ── 주문 가격 일괄 조회 (병렬) ──
        if callback: callback(f"{username}: 가격 정보 조회 중...")
        all_orders = (result["결제완료"] + result["발송대기"] +
                      result["배송지시"] + result["배송중"] + result["배송완료"])
        await _fetch_order_prices(context, all_orders)

        # ── 반품/교환/취소 (XSRF 토큰 방식) ──
        await page.goto(RETURN_LIST_URL)
        await asyncio.sleep(0.5)

        all_cookies = await context.cookies()
        xsrf_token = next((c["value"] for c in all_cookies if "xsrf" in c["name"].lower()), "")

        if xsrf_token:
            # ── 반품요청 ──
            if callback: callback(f"{username}: [반품요청] 수집 중...")
            current_page = 0
            while True:
                try:
                    resp = await context.request.post(
                        RETURN_API,
                        data=json.dumps({
                            "refundStatus": "REQUEST",
                            "wingCoupangConfirmStatus": None,
                            "from": start_date, "to": end_date,
                            "orderId": None, "cancelId": None,
                            "searchKeywordValue": None,
                            "pagePredicate": {"currentPage": current_page}
                        }),
                        headers={"Content-Type": "application/json",
                                 "Accept": "application/json, text/plain, */*",
                                 "x-xsrf-token": xsrf_token,
                                 "Referer": RETURN_LIST_URL}
                    )
                    d = await resp.json()
                    for item in d.get("content", []):
                        result["반품요청"].append(_norm_claim(item, username))
                    if current_page + 1 >= d.get("pagination", {}).get("totalPages", 1):
                        break
                    current_page += 1
                except Exception as e:
                    print(f"반품 오류: {e}"); break

            # ── 교환요청 ──
            if callback: callback(f"{username}: [교환요청] 수집 중...")
            try:
                resp = await context.request.post(
                    EXCHANGE_API,
                    data=json.dumps({
                        "exchangeStatusType": None,
                        "coupangConfirmSearchCondtionType": None,
                        "from": start_date,
                        "to": end_date,
                        "searchType": "orderId",
                        "email": None,
                        "orderId": None,
                        "searchKeywordValue": None,
                        "page": 1,
                        "pageSize": 50,
                    }),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                        "x-xsrf-token": xsrf_token,
                        "Referer": EXCHANGE_LIST_URL,
                    }
                )
                d = await resp.json()
                for item in (d.get("content") or d.get("data") or []):
                    result["교환요청"].append(_norm_claim(item, username))
            except Exception as e:
                print(f"교환요청 오류: {e}")

            # ── 교환완료 ──
            if callback: callback(f"{username}: [교환완료] 수집 중...")
            try:
                resp = await context.request.post(
                    EXCHANGE_API,
                    data=json.dumps({
                        "exchangeStatusType": "SUCCESS",
                        "coupangConfirmSearchCondtionType": None,
                        "from": two_weeks_start,
                        "to": two_weeks_end,
                        "searchType": "orderId",
                        "email": None,
                        "orderId": None,
                        "searchKeywordValue": None,
                        "page": 1,
                        "pageSize": 50,
                    }),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/plain, */*",
                        "x-xsrf-token": xsrf_token,
                        "Referer": EXCHANGE_LIST_URL,
                    }
                )
                d = await resp.json()
                for item in (d.get("content") or d.get("data") or []):
                    result["교환완료"].append(_norm_claim(item, username))
            except Exception as e:
                print(f"교환완료 오류: {e}")

            # ── 출고중지요청(출고중지) ──
            if callback: callback(f"{username}: [출고중지요청] 수집 중...")
            await page.goto(STOP_LIST_URL)
            await asyncio.sleep(0.5)
            stop_cookies = await context.cookies()
            stop_xsrf = next((c["value"] for c in stop_cookies if "xsrf" in c["name"].lower()), xsrf_token)
            current_page = 0
            while True:
                try:
                    resp = await context.request.post(
                        STOP_API,
                        data=json.dumps({
                            "shipmentStopSearchType": "SHIPMENT_STOP_REQUEST",
                            "from": start_date,
                            "to": end_date,
                            "searchKeywordValue": None,
                            "orderId": None,
                            "cancelId": None,
                            "pagePredicate": {"currentPage": current_page}
                        }),
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/plain, */*",
                            "x-xsrf-token": stop_xsrf,
                            "Referer": STOP_LIST_URL,
                        }
                    )
                    d = await resp.json()
                    content_list = d.get("content", [])
                    for item in content_list:
                        result["출고중지요청"].append(_norm_claim(item, username))
                    if current_page + 1 >= d.get("pagination", {}).get("totalPages", 1):
                        break
                    current_page += 1
                except Exception as e:
                    print(f"취소 오류: {e}"); break

            # ── 출고중지완료(출고중지완료) ──
            if callback: callback(f"{username}: [출고중지완료] 수집 중...")
            current_page = 0
            while True:
                try:
                    resp = await context.request.post(
                        STOP_API,
                        data=json.dumps({
                            "shipmentStopSearchType": "SHIPMENT_STOP_COMPLETE",
                            "from": two_weeks_start,
                            "to": two_weeks_end,
                            "searchKeywordValue": None,
                            "orderId": None,
                            "cancelId": None,
                            "pagePredicate": {"currentPage": current_page}
                        }),
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/plain, */*",
                            "x-xsrf-token": stop_xsrf,
                            "Referer": STOP_LIST_URL,
                        }
                    )
                    d = await resp.json()
                    for item in d.get("content", []):
                        result["출고중지완료"].append(_norm_claim(item, username))
                    if current_page + 1 >= d.get("pagination", {}).get("totalPages", 1):
                        break
                    current_page += 1
                except Exception as e:
                    print(f"출고중지완료 오류: {e}"); break

            # ── 반품완료 ──
            if callback: callback(f"{username}: [반품완료] 수집 중...")
            current_page = 0
            while True:
                try:
                    resp = await context.request.post(
                        RETURN_API,
                        data=json.dumps({
                            "refundStatus": "REFUND_COMPLETED",
                            "wingCoupangConfirmStatus": None,
                            "from": two_weeks_start,
                            "to": two_weeks_end,
                            "orderId": None,
                            "cancelId": None,
                            "searchKeywordValue": None,
                            "pagePredicate": {"currentPage": current_page}
                        }),
                        headers={
                            "Content-Type": "application/json",
                            "Accept": "application/json, text/plain, */*",
                            "x-xsrf-token": xsrf_token,
                            "Referer": RETURN_LIST_URL,
                        }
                    )
                    d = await resp.json()
                    for item in d.get("content", []):
                        result["반품완료"].append(_norm_claim(item, username))
                    if current_page + 1 >= d.get("pagination", {}).get("totalPages", 1):
                        break
                    current_page += 1
                except Exception as e:
                    print(f"반품완료 오류: {e}"); break

        if callback:
            callback(
                f"{username} 완료 - "
                f"결제완료:{len(result['결제완료'])} 발송대기:{len(result['발송대기'])} "
                f"취소:{len(result['출고중지요청'])} 반품:{len(result['반품요청'])} 교환:{len(result['교환요청'])}"
            )
        await browser.close()

    return result



async def _fetch_order_prices(context, orders, max_concurrent=30):
    """주문 상세 API 병렬 호출로 가격 채우기"""
    import asyncio as _asyncio
    semaphore = _asyncio.Semaphore(max_concurrent)

    async def fetch_one(order):
        order_id = order.get("realOrderId") or order.get("orderId")
        if not order_id or order_id == "0":
            return
        async with semaphore:
            try:
                resp = await context.request.get(
                    f"{ORDER_DETAIL_API}/{order_id}/order"
                )
                if resp.status == 200:
                    d = await resp.json()
                    order["totalPrice"] = int(d.get("price") or 0)
            except Exception as e:
                pass  # 가격 없으면 0 유지

    await _asyncio.gather(*[fetch_one(o) for o in orders])

def get_returns(username, password, refund_status, start_date, end_date, callback=None):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            scrape_returns(username, password, refund_status, start_date, end_date, callback)
        )
        return {"code": 200, "data": result}
    except Exception as e:
        print(f"반품 크롤링 오류: {e}")
        return {"code": 500, "data": []}
    finally:
        loop.close()


def get_all_with_returns(username, password, start_date, end_date, callback=None):
    """쿠팡 30일 제한 → 30일씩 분할 수집 + 중복 제거"""
    sd = datetime.datetime.strptime(start_date, "%Y-%m-%d").date()
    ed = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
    total_days = (ed - sd).days

    if total_days <= 30:
        # 30일 이하면 한번에
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                scrape_all_with_returns(username, password, start_date, end_date, callback)
            )
            return {"code": 200, "data": result}
        except Exception as e:
            print(f"전체 크롤링 오류: {e}")
            return {"code": 500, "data": {}}
        finally:
            loop.close()
    else:
        # 30일 초과면 30일씩 분할
        merged = {}
        seen_ids = set()
        chunk_start = sd
        while chunk_start < ed:
            chunk_end = min(chunk_start + datetime.timedelta(days=29), ed)
            cs = chunk_start.strftime("%Y-%m-%d")
            ce = chunk_end.strftime("%Y-%m-%d")
            if callback:
                callback(f"{username}: {cs}~{ce} 수집 중...")
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    scrape_all_with_returns(username, password, cs, ce, callback)
                )
                for k, items in result.items():
                    if k not in merged:
                        merged[k] = []
                    for item in items:
                        oid = item.get("orderId", "") or item.get("shipmentBoxId", "")
                        if oid and oid not in seen_ids:
                            seen_ids.add(oid)
                            merged[k].append(item)
            except Exception as e:
                print(f"분할 수집 오류 ({cs}~{ce}): {e}")
            finally:
                loop.close()
            chunk_start = chunk_end + datetime.timedelta(days=1)
        return {"code": 200, "data": merged}


# ── 택배사 목록 수집 ──────────────────────────────────────

async def scrape_courier_list(username, password, callback=None):
    """Wing 배송준비중 페이지에서 택배사 select 옵션 수집 → [{name, code}, ...]"""
    async with async_playwright() as p:
        browser, context, page = await _login_and_get_page(p, username, password)
        if not browser:
            return []

        if callback: callback("택배사 목록 수집 중...")

        # ── 1단계: 네트워크 응답 가로채기 (페이지 로드 시 택배사 데이터 캡처) ──
        captured_courier_data = []
        async def _capture_response(response):
            try:
                ct = response.headers.get("content-type", "")
                if response.status == 200 and "json" in ct:
                    body = await response.text()
                    # 택배사 관련 키워드가 포함된 응답 캡처
                    if any(kw in body for kw in ['"deliverCode"', '"courierCode"', '"CJGLS"', '"HANJIN"', '"LOTTE"', '"deliveryCompany"']):
                        captured_courier_data.append(body)
            except: pass

        page.on("response", _capture_response)

        # 배송지시/결제완료 등 여러 상태 페이지 시도 (택배사 select가 있는 페이지 찾기)
        couriers_vue = []
        for try_status in ["INSTRUCT", "ACCEPT_READY", "ACCEPT_PAYMENT"]:
            await page.goto(
                f"{BASE_URL}/tenants/sfl-portal/delivery/management?deliverStatus={try_status}",
                wait_until="domcontentloaded"
            )
            await asyncio.sleep(2)
            # select 태그 존재 확인
            has_select = await page.evaluate("() => document.querySelectorAll('select').length > 0")
            if has_select:
                break

        # ── 2단계: Vue _value 속성으로 직접 코드 추출 시도 ──
        couriers_vue = await page.evaluate("""
            () => {
                const results = [];
                const selects = document.querySelectorAll('select');
                for (const sel of selects) {
                    let isCourierSelect = false;
                    for (const opt of sel.options) {
                        const t = opt.textContent.trim();
                        if (t === '택배사 선택' || t === '택배사선택') {
                            isCourierSelect = true; break;
                        }
                    }
                    if (!isCourierSelect) continue;
                    for (const opt of sel.options) {
                        const name = opt.textContent.trim();
                        if (!name || name === '택배사 선택' || name === '택배사선택') continue;
                        // Vue 2: _value에 바인딩된 원본 객체가 있음
                        const vueVal = opt._value;
                        let code = '';
                        if (vueVal && typeof vueVal === 'object') {
                            code = vueVal.deliverCode || vueVal.courierCode || vueVal.code || vueVal.value || '';
                        } else if (vueVal && typeof vueVal === 'string' && vueVal !== '[object Object]') {
                            code = vueVal;
                        }
                        results.push({name: name, code: code});
                    }
                    if (results.length > 0) break;
                }
                // Vue 컴포넌트 데이터에서도 시도
                if (results.length === 0 || results.every(r => !r.code)) {
                    // select 부모 요소의 __vue__ 인스턴스 탐색
                    for (const sel of selects) {
                        let el = sel;
                        while (el) {
                            const vm = el.__vue__ || el.__vueParentComponent;
                            if (vm) {
                                const data = vm.$data || vm.data || vm.setupState || {};
                                // 택배사 배열 찾기
                                for (const key of Object.keys(data)) {
                                    const val = data[key];
                                    if (Array.isArray(val) && val.length > 10) {
                                        const first = val[0];
                                        if (first && (first.deliverCode || first.courierCode || first.code)) {
                                            return val.map(item => ({
                                                name: item.deliverName || item.courierName || item.name || item.label || '',
                                                code: item.deliverCode || item.courierCode || item.code || item.value || ''
                                            })).filter(x => x.name);
                                        }
                                    }
                                }
                            }
                            el = el.parentElement;
                        }
                    }
                }
                return results;
            }
        """)

        # ── 3단계: 캡처된 네트워크 응답에서 택배사 매핑 추출 ──
        network_map = {}
        for body in captured_courier_data:
            try:
                data = json.loads(body)
                # 배열인 경우
                items = data if isinstance(data, list) else data.get("data", data.get("content", data.get("result", [])))
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            dn = item.get("deliverName") or item.get("courierName") or item.get("name") or ""
                            dc = item.get("deliverCode") or item.get("courierCode") or item.get("code") or ""
                            if dn and dc and dc != "[object Object]":
                                network_map[dn] = dc
            except: pass

        # ── 4단계: 배송완료 주문 API에서 택배사 코드 수집 (보충용) ──
        order_map = {}
        if callback: callback("배송 데이터에서 택배사 코드 보충 중...")
        for status in ["DELIVERING,FINAL_DELIVERY", "DEPARTURE", "INSTRUCT"]:
            try:
                condition = json.dumps({
                    "nextShipmentBoxId": None,
                    "startDate": (datetime.date.today() - datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
                    "endDate": datetime.date.today().strftime("%Y-%m-%d"),
                    "deliveryStatus": status, "countPerPage": 100, "page": 1,
                    "deliveryMethod": None, "detailConditionKey": "NAME", "detailConditionValue": None,
                    "selectedComplexConditionKey": None, "deliverCode": None, "storePickupStatus": None,
                    "isEsdToday": None, "isEsdIn5d": None, "isEsdTmr": None, "shipmentType": None,
                }, ensure_ascii=False)
                url = f"{BASE_URL}/tenants/sfl-portal/delivery/management/dashboard/search?condition={urllib.parse.quote(condition)}&mockingTestMode=false"
                resp = await context.request.get(url, headers={"Accept": "application/json"})
                if resp.ok:
                    raw = await resp.json()
                    items = raw if isinstance(raw, list) else (raw.get("data") if isinstance(raw.get("data"), list) else [])
                    for o in items:
                        if isinstance(o, dict):
                            dn = o.get("deliverName") or o.get("courierName") or ""
                            dc = o.get("deliverCode") or o.get("courierCode") or ""
                            if dn and dc and dc != "[object Object]":
                                order_map[dn] = dc
            except: pass

        # ── 5단계: JS 번들에서 택배사 코드 추출 시도 ──
        js_map = {}
        try:
            js_courier_data = await page.evaluate("""
                () => {
                    // 페이지의 모든 script 태그 내용 검색
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const txt = s.textContent || '';
                        // deliverCode를 포함하는 객체 배열 찾기
                        const match = txt.match(/\\[\\s*\\{[^\\]]*deliverCode[^\\]]*\\}\\s*\\]/);
                        if (match) {
                            try { return JSON.parse(match[0]); } catch(e) {}
                        }
                        const match2 = txt.match(/\\[\\s*\\{[^\\]]*courierCode[^\\]]*\\}\\s*\\]/);
                        if (match2) {
                            try { return JSON.parse(match2[0]); } catch(e) {}
                        }
                    }
                    return null;
                }
            """)
            if js_courier_data and isinstance(js_courier_data, list):
                for item in js_courier_data:
                    if isinstance(item, dict):
                        dn = item.get("deliverName") or item.get("courierName") or item.get("name") or ""
                        dc = item.get("deliverCode") or item.get("courierCode") or item.get("code") or ""
                        if dn and dc:
                            js_map[dn] = dc
        except: pass

        # ── 결과 합치기: Vue _value > 네트워크 캡처 > JS 번들 > 주문 API > 이름 사용 ──
        couriers = []
        seen = set()
        # Vue에서 가져온 이름 목록이 기본
        names_from_vue = [c["name"] for c in couriers_vue if c.get("name")]
        vue_code_map = {c["name"]: c["code"] for c in couriers_vue if c.get("name") and c.get("code") and c["code"] != "[object Object]"}

        for name in names_from_vue:
            if name in seen:
                continue
            seen.add(name)
            # 우선순위: vue _value > network > js bundle > order API > name
            code = (vue_code_map.get(name)
                    or network_map.get(name)
                    or js_map.get(name)
                    or order_map.get(name)
                    or name)
            couriers.append({"name": name, "code": code})

        # 네트워크/JS/주문에서 발견됐지만 DOM에 없는 택배사도 추가
        for src in [network_map, js_map, order_map]:
            for name, code in src.items():
                if name not in seen and code and code != "[object Object]":
                    seen.add(name)
                    couriers.append({"name": name, "code": code})

        await browser.close()
        if callback: callback(f"택배사 {len(couriers)}개 수집 완료!")
        return couriers


def get_courier_list(username, password, callback=None):
    """택배사 목록 수집 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_courier_list(username, password, callback))
    except Exception as e:
        print(f"택배사 목록 오류: {e}")
        return []
    finally:
        loop.close()


# ── 송장 등록 ──────────────────────────────────────

# Wing 송장등록 에러키 → 한글 설명
_INV_ERR_MAP = {
    "invoiceNumberRequired": "송장번호 누락",
    "invoiceNumberInvalid": "송장번호 형식 오류 (택배사 송장번호 규칙 불일치)",
    "invalidInvoiceNumber": "송장번호 형식 오류",
    "invoiceNumberDuplicated": "송장번호 중복",
    "duplicatedInvoiceNumber": "송장번호 중복",
    "invoiceNumberAlreadyExists": "이미 등록된 송장번호",
    "invoiceNumberNotFound": "송장번호 조회 불가",
    "deliverCodeRequired": "택배사 누락",
    "deliverCodeInvalid": "택배사 코드 불일치",
    "invalidDeliverCode": "택배사 코드 불일치",
    "deliverNotSupported": "지원하지 않는 택배사",
    "deliverNameInvalid": "택배사명 불일치",
    "shipmentBoxNotFound": "주문(박스)을 찾을 수 없음",
    "shipmentBoxIdRequired": "박스 ID 누락",
    "shipmentBoxIdInvalid": "박스 ID 오류",
    "orderIdInvalid": "주문 ID 오류",
    "orderNotFound": "주문을 찾을 수 없음",
    "alreadyShipped": "이미 발송 처리됨",
    "alreadyDelivered": "이미 배송완료",
    "cannotUpdate": "수정 불가 상태",
    "invalidStatus": "송장 등록 가능 상태 아님",
    "statusInvalid": "송장 등록 가능 상태 아님",
    "orderCancelled": "취소된 주문",
    "orderCanceled": "취소된 주문",
    "permissionDenied": "권한 없음",
    "plannedShippingDateRequired": "출고예정일 누락",
    "plannedShippingDateInvalid": "출고예정일 오류",
    "splitItemsInvalid": "분할발송 항목 오류",
    "splitItemsRequired": "분할발송 정보 누락",
    "invoiceNotMatched": "택배사-송장번호 불일치",
    "invalidTrackingNumber": "추적번호 검증 실패",
    "trackingNumberInvalid": "추적번호 검증 실패",
    "invalidRequest": "잘못된 요청",
    "validationFailed": "검증 실패",
}

def _trans_inv_err(msg):
    if not msg: return "실패"
    return _INV_ERR_MAP.get(msg, msg)


async def scrape_register_invoices(username, password, orders, callback=None):
    """
    Wing에 송장번호 일괄 등록 (2026 신 API)
    orders: [{"shipmentBoxId":..., "courierCode":..., "courierName":..., "invoiceNumber":..., "orderId":...}, ...]
    """
    async with async_playwright() as p:
        browser, context, page = await _login_and_get_page(p, username, password)
        if not browser:
            return {"success": 0, "fail": 0, "errors": ["로그인 실패"]}

        if callback: callback(f"{username}: 송장 등록 준비 중...")

        # 배송관리 페이지 접속 (XSRF 토큰 등 쿠키/세션 확보)
        await page.goto(
            f"{BASE_URL}/tenants/sfl-portal/delivery/management",
            wait_until="domcontentloaded"
        )
        await asyncio.sleep(1)

        # XSRF 토큰 추출
        xsrf_token = ""
        for cookie in await context.cookies():
            if cookie.get("name") == "XSRF-TOKEN":
                xsrf_token = cookie.get("value", ""); break

        success = 0
        fail = 0
        errors = []

        # 일괄 전송 (배열 형태)
        try:
            payload = []
            for order in orders:
                box_id = order.get("shipmentBoxId", "")
                courier_code = order.get("courierCode", "")
                courier_name = order.get("courierName", "") or order.get("deliverName", "")
                invoice = order.get("invoiceNumber", "")
                order_id = order.get("orderId", "")

                if not box_id or not courier_code or not invoice:
                    fail += 1
                    errors.append(f"필수값 누락: {box_id}")
                    continue

                payload.append({
                    "orderId": int(order_id) if str(order_id).isdigit() else order_id,
                    "shipmentBoxId": int(box_id) if str(box_id).isdigit() else box_id,
                    "deliverCode": courier_code,
                    "deliverName": courier_name,
                    "invoiceNumber": str(invoice),
                    "plannedShippingDate": None,
                    "splitItems": [],
                })

            if not payload:
                await browser.close()
                return {"success": 0, "fail": fail, "errors": errors}

            if callback: callback(f"송장 등록 요청 중... ({len(payload)}건)")

            resp = await context.request.post(
                f"{BASE_URL}/tenants/sfl-portal/delivery/management/update/validate/normal",
                data=json.dumps(payload),
                headers={
                    "Content-Type": "application/json;charset=UTF-8",
                    "Accept": "application/json",
                    "Origin": "https://wing.coupang.com",
                    "Referer": "https://wing.coupang.com/tenants/sfl-portal/delivery/management",
                    "x-xsrf-token": xsrf_token,
                }
            )
            body = await resp.text()
            if resp.ok:
                # 응답: 빈배열=전부성공 / 실패항목만 배열에 포함
                try:
                    rj = json.loads(body) if body.strip() else []
                    if not isinstance(rj, list): rj = []
                    failed_box_ids = set()
                    for item in rj:
                        if item.get("success") is False or item.get("errorMessage") or item.get("errorKey"):
                            failed_box_ids.add(item.get("shipmentBoxId"))
                            err_raw = item.get("errorMessage") or item.get("errorKey") or "실패"
                            err_kr = _trans_inv_err(err_raw)
                            oid = item.get("orderId","")
                            if err_kr != err_raw:
                                errors.append(f"{oid}: {err_kr} ({err_raw})")
                            else:
                                errors.append(f"{oid}: {err_kr}")
                    fail += len(failed_box_ids)
                    success += len(payload) - len(failed_box_ids)
                except Exception as e:
                    errors.append(f"응답 파싱 오류: {e}")
                    fail += len(payload)
            else:
                fail += len(payload)
                errors.append(f"HTTP {resp.status}: {body[:200]}")
        except Exception as e:
            fail += len(orders)
            errors.append(str(e))

        await browser.close()
        if callback: callback(f"송장 등록 완료! 성공:{success} 실패:{fail}")
        return {"success": success, "fail": fail, "errors": errors}


def register_invoices_on_wing(username, password, orders, callback=None):
    """송장 등록 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_register_invoices(username, password, orders, callback))
    except Exception as e:
        print(f"송장 등록 오류: {e}")
        return {"success": 0, "fail": 0, "errors": [str(e)]}
    finally:
        loop.close()


# ── 상품 옵션 크롤링 ──────────────────────────────
PRODUCT_PAGE_URL = f"{BASE_URL}/vendor-inventory/list"
PRODUCT_SEARCH_API = f"{BASE_URL}/tenants/seller-web/v2/vendor-inventory/search"


async def scrape_products(username, password, callback=None):
    """
    쿠팡 Wing 상품 조회/수정 페이지에서 상품 옵션 데이터 크롤링
    POST /tenants/seller-web/v2/vendor-inventory/search API 사용
    """
    async with async_playwright() as p:
        result = await _login_and_get_page(p, username, password)
        if not result:
            return []
        browser, context, page = result

        # 상품 페이지 접속 (세션/XSRF 토큰 확보)
        if callback:
            callback(f"{username}: 상품 페이지 접속 중...")
        try:
            await page.goto(PRODUCT_PAGE_URL, wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
        except:
            await browser.close()
            return []

        if "login" in page.url or "xauth" in page.url:
            if callback:
                callback(f"{username}: 로그인 필요")
            await browser.close()
            return []

        # XSRF 토큰
        all_cookies = await context.cookies()
        xsrf = next((c["value"] for c in all_cookies if "xsrf" in c["name"].lower()), "")

        all_products = []
        current_page = 1
        page_size = 50

        while True:
            try:
                resp = await context.request.post(
                    PRODUCT_SEARCH_API,
                    data=json.dumps({
                        "searchKeywordType": "ALL",
                        "searchKeywords": "",
                        "salesMethod": "ALL",
                        "pageSize": page_size,
                        "currentPage": current_page,
                    }),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "x-xsrf-token": xsrf,
                        "Referer": PRODUCT_PAGE_URL,
                    }
                )
                if not resp.ok:
                    break

                data = await resp.json()
                if not data.get("success"):
                    break

                product_list = data.get("data", {}).get("productList", [])
                pagination = data.get("data", {}).get("pagination", {})
                total_pages = pagination.get("totalPages", 1)
                total_count = pagination.get("totalCount", 0)

                if not product_list:
                    break

                # 상품별 옵션 추출
                for prod in product_list:
                    product_name = prod.get("productName", "")
                    product_id = str(prod.get("vendorInventoryId", ""))
                    status = prod.get("status", "")
                    product_status = prod.get("productStatus", "")

                    items = prod.get("vendorInventoryItems", [])
                    if items:
                        for item in items:
                            exposure = item.get("exposureStatuses")
                            if isinstance(exposure, list):
                                exposure = ", ".join(str(e) for e in exposure) if exposure else ""
                            elif not exposure:
                                exposure = ""

                            all_products.append({
                                "productName": product_name,
                                "productId": product_id,
                                "optionName": item.get("itemName", ""),
                                "sellerProductCode": item.get("externalSkuCode", ""),
                                "vendorItemId": str(item.get("vendorItemId") or item.get("vendorInventoryItemId") or ""),
                                "salePrice": int(item.get("salePrice") or 0),
                                "stock": int(item.get("stockQuantity") or 0),
                                "exposureStatus": exposure,
                                "status": item.get("status", status),
                                "productStatus": product_status,
                            })
                    else:
                        all_products.append({
                            "productName": product_name,
                            "productId": product_id,
                            "optionName": "",
                            "sellerProductCode": "",
                            "vendorItemId": "",
                            "salePrice": 0,
                            "stock": 0,
                            "exposureStatus": "",
                            "status": status,
                            "productStatus": product_status,
                        })

                if callback:
                    callback(f"{username}: {len(all_products)}개 옵션 수집 중... ({current_page}/{total_pages})")

                if current_page >= total_pages:
                    break
                current_page += 1

            except Exception as e:
                print(f"상품 크롤링 오류 (p{current_page}): {e}")
                break

        await browser.close()

        if callback:
            callback(f"{username}: 상품 수집 완료 ({len(all_products)}개 옵션)")
        return all_products


def get_products(username, password, callback=None):
    """상품 옵션 수집 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(scrape_products(username, password, callback))
        return {"code": 200, "data": result}
    except Exception as e:
        print(f"상품 크롤링 오류: {e}")
        return {"code": 500, "data": [], "error": str(e)}
    finally:
        loop.close()


# ── vendorItemId → 판매자상품코드 일괄 조회 ──────────────────
async def scrape_seller_codes(username, password, vendor_item_ids, callback=None):
    """
    vendorItemId 목록으로 판매자상품코드(externalSkuCode) 일괄 조회
    배송관리 → 상품 클릭 시 이동하는 URL 방식:
    /vendor-inventory/list?vendorItemIdSearch={id}&searchKeywordType=PRODUCT_ID&searchKeywords={id}
    """
    if not vendor_item_ids:
        return {}

    async with async_playwright() as p:
        result_map = await _login_and_get_page(p, username, password)
        if not result_map:
            return {}
        browser, context, page = result_map

        # 상품 페이지 접속 (세션 확보)
        await page.goto(PRODUCT_PAGE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(1)

        if "login" in page.url or "xauth" in page.url:
            await browser.close()
            return {}

        all_cookies = await context.cookies()
        xsrf = next((c["value"] for c in all_cookies if "xsrf" in c["name"].lower()), "")

        code_map = {}
        unique_ids = list(set(str(v) for v in vendor_item_ids if v))
        total = len(unique_ids)

        for i, vid in enumerate(unique_ids):
            try:
                resp = await context.request.post(
                    PRODUCT_SEARCH_API,
                    data=json.dumps({
                        "searchKeywordType": "PRODUCT_ID",
                        "searchKeywords": vid,
                        "vendorItemIdSearch": vid,
                        "salesMethod": "ALL",
                        "pageSize": 10,
                        "currentPage": 1,
                    }),
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "x-xsrf-token": xsrf,
                        "Referer": PRODUCT_PAGE_URL,
                    }
                )
                if resp.ok:
                    data = await resp.json()
                    products = data.get("data", {}).get("productList", [])
                    found_sku = ""
                    for prod in products:
                        for item in prod.get("vendorInventoryItems", []):
                            item_vid = str(item.get("vendorItemId") or "")
                            inv_id = str(item.get("vendorInventoryItemId") or "")
                            sku = item.get("externalSkuCode", "")
                            if sku:
                                found_sku = sku
                                if item_vid:
                                    code_map[item_vid] = sku
                                if inv_id:
                                    code_map[inv_id] = sku
                    # 검색한 vendorItemId 자체에도 매핑 (옵션 ID가 다를 수 있으므로)
                    if found_sku:
                        code_map[vid] = found_sku

                if callback and (i + 1) % 5 == 0:
                    callback(f"{username}: 판매자상품코드 조회 중... ({i+1}/{total})")

            except Exception as e:
                print(f"판매자상품코드 조회 오류 ({vid}): {e}")

        await browser.close()

        if callback:
            callback(f"{username}: 판매자상품코드 {len(code_map)}개 매핑 완료")
        return code_map


def get_seller_codes(username, password, vendor_item_ids, callback=None):
    """판매자상품코드 조회 동기 래퍼"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(scrape_seller_codes(username, password, vendor_item_ids, callback))
    except Exception as e:
        print(f"판매자상품코드 조회 오류: {e}")
        return {}
    finally:
        loop.close()