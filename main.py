# -*- coding: utf-8 -*-
"""
MYSHOP 통합관리 v2 — 완전 새 코드
상단 네비게이션 바 + 카드 기반 화이트 미니멀 UI
"""
import sys, os, ssl, json, hashlib, asyncio, datetime
import urllib.request, urllib.parse

ssl._create_default_https_context = ssl._create_unverified_context
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Playwright 브라우저 셋업
if getattr(sys, 'frozen', False):
    _base = os.path.dirname(sys.executable)
    _pw = os.path.join(_base, "ms-playwright")
    if os.path.isdir(_pw):
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = _pw
else:
    import subprocess, shutil
    if not shutil.which("playwright"):
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], capture_output=True)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p: p.chromium.executable_path
    except:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], capture_output=True)

import openpyxl
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from coupang_auth import (do_login, save_account, delete_account,
    load_all_accounts, load_cookies, save_ip, get_public_ip, _data_path,
    verify_cookies)
from coupang_crawl import (get_all_with_returns, register_invoices_on_wing, get_seller_codes)
from naver_crawl import (do_naver_login, load_naver_cookies, delete_naver_cookies,
    verify_naver_cookies, register_invoices_on_naver)

# ═══════════════════════════════════════════
# 설정
# ═══════════════════════════════════════════
VER = "1.0.1"
ADMIN = "admin0904"
SB = "https://nzacpbeodeqdotbkbepo.supabase.co"
SK = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im56YWNwYmVvZGVxZG90YmtiZXBvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzUxODUyMTYsImV4cCI6MjA5MDc2MTIxNn0.9hytdZfOAUCchS8K0LFXaXBSRjzqWXLilR7FhNw8K1c"

def _sbh(post=False):
    h = {"apikey": SK, "Authorization": f"Bearer {SK}"}
    if post: h["Content-Type"] = "application/json"; h["Prefer"] = "return=minimal"
    return h

def _sbget(tbl, q, sel="*"):
    r = urllib.request.Request(f"{SB}/rest/v1/{tbl}?{q}&select={sel}", headers=_sbh())
    with urllib.request.urlopen(r, timeout=5) as resp: return json.loads(resp.read())

def _sbmut(tbl, body, method="POST", where=""):
    url = f"{SB}/rest/v1/{tbl}" + (f"?{where}" if where else "")
    data = json.dumps(body).encode() if body else None
    urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=_sbh(True)), timeout=5)

OSTATUS = {"결제완료":"ACCEPT_PAYMENT","발송대기":"ACCEPT_READY","배송지시":"INSTRUCT","배송중":"DEPARTURE","배송완료":"DELIVERING,FINAL_DELIVERY"}
CSTATUS = {"출고중지요청":"CANCEL","출고중지완료":"CANCEL_DONE","반품요청":"RETURN","반품완료":"RETURN_DONE","교환요청":"EXCHANGE","교환완료":"EXCHANGE_DONE"}
NAV_MAP = {"NEW_ORDER":"결제완료","PAYED":"결제완료","PLACE_ORDER":"발송대기","PREPARING":"발송대기","DISPATCHED":"배송중","DELIVERING":"배송중","DELIVERED":"배송완료","PURCHASE_DECIDED":"배송완료"}

COURIER_LIST=["CJ 대한통운","롯데택배","한진택배","우체국","로젠택배","경동택배","대신택배","일양로지스","합동택배","자체배송","직접전달","방문수령"]

def _tts(text):
    """OS별 음성 알림"""
    import subprocess, platform
    if platform.system()=="Darwin":
        subprocess.Popen(["say","-v","Yuna","-r","170",text])
    else:
        # Windows SAPI
        try:
            vbs=os.path.join(os.environ.get("TEMP","."),"_tts.vbs")
            with open(vbs,"w",encoding="utf-8") as f:
                f.write(f'CreateObject("SAPI.SpVoice").Speak "{text}"')
            subprocess.Popen(["cscript","//nologo",vbs],creationflags=0x08000000)
        except: pass
TINTS = ["#F8FAFC","#F0FDF4","#FFFBEB","#FEF2F2","#F5F3FF","#FFF7ED"]
SCOLORS = {"결제완료":("#EF4444","#FEF2F2"),"발송대기":("#F59E0B","#FFFBEB"),"배송지시":("#3B82F6","#EFF6FF"),"배송중":("#10B981","#ECFDF5"),"배송완료":("#8B5CF6","#F5F3FF")}
CCOLORS = {"출고중지요청":("#DC2626","#FEF2F2"),"출고중지완료":("#9CA3AF","#F9FAFB"),"반품요청":("#7C3AED","#F5F3FF"),"반품완료":("#6B7280","#F9FAFB"),"교환요청":("#2563EB","#EFF6FF"),"교환완료":("#6B7280","#F9FAFB")}

# ═══════════════════════════════════════════
# 파일 유틸
# ═══════════════════════════════════════════
def dp(n): return _data_path(n)
def jload(p, d=None):
    if os.path.exists(p):
        try:
            with open(p,"r",encoding="utf-8") as f: return json.load(f)
        except: pass
    return d if d is not None else {}
def jsave(p, obj):
    with open(p,"w",encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def load_pw(): return jload(dp("wing_passwords.json"), {})
def save_pw(u,p): d=load_pw(); d[u]=p; jsave(dp("wing_passwords.json"),d)
def load_nav_pw(): return jload(dp("naver_passwords.json"), {})
def save_nav_pw(aid,p): d=load_nav_pw(); d[aid]=p; jsave(dp("naver_passwords.json"),d)
def del_nav_pw(aid):
    d=load_nav_pw()
    if aid in d: d.pop(aid); jsave(dp("naver_passwords.json"),d)
def load_nav(): return jload(dp("naver_accounts.json"), [])
def save_nav(aid, mno="", store="", login_type=None):
    lst=load_nav()
    hit=next((a for a in lst if str(a.get("account_id",""))==str(aid)),None)
    if not hit and mno: hit=next((a for a in lst if a.get("merchant_no","")==mno),None)
    if not hit:
        rec={"account_id":str(aid),"merchant_no":mno,"store_name":store,"market":"naver"}
        if login_type: rec["login_type"]=login_type
        lst.append(rec)
    else:
        if mno: hit["merchant_no"]=mno
        if store: hit["store_name"]=store
        if login_type: hit["login_type"]=login_type
    jsave(dp("naver_accounts.json"),lst)
def del_nav(aid): jsave(dp("naver_accounts.json"),[a for a in load_nav() if str(a.get("account_id",""))!=str(aid)])
def load_saved(): return jload(dp("saved_accounts.json"), [])
def add_saved(u, biz=""):
    lst=load_saved(); hit=next((a for a in lst if a["username"]==u),None)
    if not hit: lst.append({"username":u,"market":"coupang","bizName":biz})
    elif biz: hit["bizName"]=biz
    jsave(dp("saved_accounts.json"),lst)
def del_saved(u): jsave(dp("saved_accounts.json"),[a for a in load_saved() if a.get("username")!=u])
def load_memos(): return jload(dp("cs_memos.json"),{})
def save_memo(oid,memo):
    d=load_memos(); d[str(oid)]={"memo":memo,"updated":datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}; jsave(dp("cs_memos.json"),d)
def load_cmap(): return jload(dp("courier_map.json"),{})
def save_cmap(d): jsave(dp("courier_map.json"),d)
# 사유코드(택배사 아닌 항목) — 콤보박스에서 제외
_REASON_NAMES={"배송지연","주문제작","해외배송","고객부재","입고지연","기상악화","세관대기중","출고불가","주문취소","설치상품 배송안내","배송불가지역 안내"}
def courier_names(cm=None):
    if cm is None: cm=load_cmap()
    return [k for k in cm.keys() if k and k not in _REASON_NAMES and k not in ('주문번호','주문자명','수취인명','NONE','None') and '보기' not in k and not str(cm.get(k,"")).startswith('[object')]
def load_codemap(): return jload(dp("product_code_map.json"),{})
def save_codemap(d): jsave(dp("product_code_map.json"),d)
def load_logincfg(): return jload(dp("login_settings.json"),{"save_id":False,"auto_login":False,"username":"","password_hash":""})
def save_logincfg(save_id=False,auto_login=False,username="",pw_hash=""):
    jsave(dp("login_settings.json"),{"save_id":save_id,"auto_login":auto_login,"username":username if save_id else "","password_hash":pw_hash if auto_login else ""})
def load_tmpls():
    d=jload("excel_templates_v3.json")
    if d: return d
    default=[{"name":"기본 전체 양식","mapping":[{"header":k,"formula":"{"+k+"}"} for k in ["주문일시","마켓","아이디","주문번호","상품명","수령인","연락처","주소","배송메모","결제금액","정산금액"]]}]
    jsave("excel_templates_v3.json",default); return default
def save_tmpls(t): jsave("excel_templates_v3.json",t)

def dl_cmap():
    try:
        r=urllib.request.Request(f"{SB}/rest/v1/courier_list?select=name,code&order=id",headers=_sbh())
        with urllib.request.urlopen(r,timeout=5) as resp:
            d=json.loads(resp.read())
            if d: m={x["name"]:x["code"] for x in d}; save_cmap(m); return m
    except: pass
    return {}

# ═══════════════════════════════════════════
# 인증
# ═══════════════════════════════════════════
def _ph(pw): return hashlib.sha256(pw.encode()).hexdigest()

def do_verify(uid, pw):
    try:
        rows=_sbget("users",f"username=eq.{urllib.parse.quote(uid)}&is_active=eq.true")
        if not rows: return False,"존재하지 않는 아이디입니다.",""
        u=rows[0]
        if u.get("password_hash")!=_ph(pw): return False,"비밀번호가 일치하지 않습니다.",""
        exp=u.get("expired_at","")
        if exp:
            try:
                if datetime.datetime.now()>datetime.datetime.fromisoformat(exp.replace("Z","")): return False,"이용기간 만료. 관리자 문의.",""
            except: pass
        return True, u.get("user_name","사용자"), exp
    except Exception as e: return False, f"서버 오류: {e}", ""

def do_verify_hash(uid, ph):
    try:
        rows=_sbget("users",f"username=eq.{urllib.parse.quote(uid)}&is_active=eq.true")
        if not rows: return False,"존재하지 않는 아이디.",""
        u=rows[0]
        if u.get("password_hash")!=ph: return False,"자동 로그인 실패.",""
        exp=u.get("expired_at","")
        if exp:
            try:
                if datetime.datetime.now()>datetime.datetime.fromisoformat(exp.replace("Z","")): return False,"이용기간 만료.",""
            except: pass
        return True, u.get("user_name","사용자"), exp
    except Exception as e: return False, f"서버 오류: {e}", ""

def do_signup(uid,pw,name,birth="",phone="",email="",referrer=""):
    try:
        if _sbget("users",f"username=eq.{urllib.parse.quote(uid)}","id"): return False,"이미 사용 중인 아이디."
        if phone and _sbget("users",f"phone=eq.{urllib.parse.quote(phone)}","id"): return False,"이미 사용 중인 연락처."
        if email and _sbget("users",f"email=eq.{urllib.parse.quote(email)}","id"): return False,"이미 사용 중인 이메일."
        if name and phone and birth:
            if _sbget("users",f"user_name=eq.{urllib.parse.quote(name)}&phone=eq.{urllib.parse.quote(phone)}&birth_date=eq.{urllib.parse.quote(birth)}","id"):
                return False,"동일 정보로 이미 가입됨."
        if referrer and not _sbget("users",f"username=eq.{urllib.parse.quote(referrer)}","id"):
            return False,"없는 추천인입니다."
        exp=(datetime.datetime.now()+datetime.timedelta(days=7)).strftime("%Y-%m-%dT23:59:59")
        row={"username":uid,"password_hash":_ph(pw),"user_name":name,"birth_date":birth,"phone":phone,"email":email,"expired_at":exp}
        if referrer: row["referrer"]=referrer
        _sbmut("users",row)
        return True,"회원가입 완료!"
    except Exception as e: return False, f"오류: {e}"

def do_resetpw(uid,name,phone,email,birth):
    try:
        q=f"username=eq.{urllib.parse.quote(uid)}&user_name=eq.{urllib.parse.quote(name)}&phone=eq.{urllib.parse.quote(phone)}&email=eq.{urllib.parse.quote(email)}&birth_date=eq.{urllib.parse.quote(birth)}"
        if not _sbget("users",q,"username"): return False,"일치하는 정보 없음."
        _sbmut("users",{"password_hash":_ph("000000")},"PATCH",f"username=eq.{urllib.parse.quote(uid)}")
        try: delete_account(uid)
        except: pass
        try: del_saved(uid)
        except: pass
        return True,"비밀번호 000000으로 초기화 완료."
    except Exception as e: return False,f"오류: {e}"

def fetch_notices():
    try:
        rows=_sbget("notices","is_active=eq.true&order=created_at.desc","title,content")
        return [(r["title"],r["content"]) for r in rows] if rows else None
    except: return None

# ═══════════════════════════════════════════
# 스타일
# ═══════════════════════════════════════════
FG="#111827"; FG2="#6B7280"; FG3="#9CA3AF"
BG="#FAFAFA"; WHITE="#FFFFFF"; BD="#E5E7EB"; BD2="#F3F4F6"
ACCENT="#2563EB"; GREEN="#059669"; RED="#DC2626"; AMBER="#D97706"

S_BTN=f"QPushButton{{background:{FG};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:0 20px}}QPushButton:hover{{background:#374151}}QPushButton:disabled{{background:#D1D5DB;color:#9CA3AF}}"
S_BTN2=f"QPushButton{{background:transparent;color:{FG};border:1px solid {BD};border-radius:8px;font-weight:600;font-size:13px;padding:0 18px}}QPushButton:hover{{background:#F9FAFB}}"
S_BTN_OK=f"QPushButton{{background:{GREEN};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:0 20px}}QPushButton:hover{{background:#10B981}}"
S_BTN_ERR=f"QPushButton{{background:{RED};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:0 20px}}QPushButton:hover{{background:#EF4444}}"
S_BTN_WARN=f"QPushButton{{background:{AMBER};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:0 20px}}QPushButton:hover{{background:#F59E0B}}"
S_INP=f"QLineEdit,QComboBox,QSpinBox{{border:1px solid {BD};border-radius:8px;padding:0 12px;background:#fff;font-size:13px;color:{FG}}}QLineEdit:focus,QComboBox:focus{{border:1px solid {ACCENT}}}"
S_TBL=f"QTableWidget{{background:#fff;border:1px solid {BD};border-radius:8px;gridline-color:{BD2};font-size:14px;color:{FG}}}QTableWidget::item{{padding:12px 14px;border-bottom:1px solid {BD2}}}QTableWidget::item:selected{{background:#EFF6FF;color:{FG}}}QHeaderView::section{{background:#F9FAFB;color:{FG2};font-weight:600;font-size:13px;padding:14px;border:none;border-bottom:2px solid {BD};border-right:1px solid {BD2}}}QHeaderView::section:last{{border-right:none}}"
S_TAB=f"QTabWidget::pane{{border:1px solid {BD};border-radius:8px;background:#fff;margin-top:-1px}}QTabBar::tab{{background:transparent;color:{FG2};padding:10px 24px;font-weight:600;font-size:13px;border:none;border-bottom:2px solid transparent;margin-right:4px}}QTabBar::tab:selected{{color:{FG};border-bottom:2px solid {FG}}}QTabBar::tab:hover:!selected{{color:{FG}}}"
S_PROG=f"QProgressBar{{border:1px solid {BD};border-radius:6px;background:#F9FAFB;text-align:center;font-weight:600;font-size:12px;color:#fff;height:22px}}QProgressBar::chunk{{background:{ACCENT};border-radius:5px}}"
_ARROW=os.path.join(os.path.dirname(os.path.abspath(__file__)),"arrow_down.png").replace("\\","/")
S_CAL=f"QDateEdit{{border:1px solid {BD};border-radius:8px;padding:0 12px;background:#fff;font-size:13px;color:{FG}}}QDateEdit:focus{{border:1px solid {ACCENT}}}QDateEdit::drop-down{{subcontrol-origin:padding;subcontrol-position:top right;width:28px;background:#fff;border:none}}QDateEdit::down-arrow{{image:url({_ARROW});width:12px;height:12px}}"
S_SCROLL=f"QScrollArea{{border:none;background:transparent}}QScrollBar:vertical{{background:transparent;width:6px;border-radius:3px}}QScrollBar::handle:vertical{{background:#D1D5DB;border-radius:3px;min-height:30px}}QScrollBar::handle:vertical:hover{{background:#9CA3AF}}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0}}"

# ═══════════════════════════════════════════
# 워커 스레드
# ═══════════════════════════════════════════
class LoginWorker(QThread):
    sig = pyqtSignal(str)
    done = pyqtSignal(dict)
    def __init__(s,u,p): super().__init__(); s.u,s.p=u,p
    def run(s):
        lp=asyncio.new_event_loop(); asyncio.set_event_loop(lp)
        try: r=lp.run_until_complete(do_login(s.u,s.p,callback=lambda m:s.sig.emit(m))); s.done.emit(r)
        except Exception as e: s.done.emit({"success":False,"message":str(e)})
        finally: lp.close()

class CollectWorker(QThread):
    prog=pyqtSignal(int,str)
    done=pyqtSignal(dict)
    def __init__(s,accs,pws,sd,ed): super().__init__(); s.accs,s.pws,s.sd,s.ed=accs,pws,sd,ed; s._stop=False
    def stop(s): s._stop=True
    def run(s):
        ad={k:[] for k in list(OSTATUS)+list(CSTATUS)}
        st={k:0 for k in ad}; ast=[]
        cpg=[a for a in s.accs if a.get("market")!="naver"]
        for i,a in enumerate(cpg):
            if s._stop: break
            pct=int(i/max(len(cpg),1)*80); uid=a["username"]; pw=s.pws.get(uid,"")
            s.prog.emit(pct,f"{uid} 수집 중...")
            row={"username":uid,"market":"coupang"}; row.update({k:0 for k in ad})
            collected_vids=set()
            try:
                res=get_all_with_returns(uid,pw,s.sd,s.ed,callback=lambda m:s.prog.emit(pct,m))
                if res and res.get("code")==200:
                    for nm in ad:
                        items=res["data"].get(nm,[])
                        ad[nm].extend(items); st[nm]+=len(items); row[nm]=len(items)
                        for it in items:
                            if it.get("market")=="naver" or it.get("linked_username")!=uid: continue
                            for oit in it.get("orderItems",[]) or []:
                                vid=str(oit.get("vendorItemId") or "")
                                if vid and not oit.get("sellerProductCode"):
                                    collected_vids.add(vid)
            except Exception as e: print(f"수집오류({uid}):{e}")
            # 판매자상품코드 일괄 조회 → cmap 업데이트 + ad 항목 채워넣기
            if collected_vids and not s._stop:
                try:
                    s.prog.emit(pct,f"{uid} 판매자상품코드 조회 중... ({len(collected_vids)}개)")
                    code_res=get_seller_codes(uid,pw,list(collected_vids),callback=lambda m:s.prog.emit(pct,m))
                    # get_seller_codes 는 {vid: sku, ...} 딕트 직접 반환
                    code_map=code_res if isinstance(code_res,dict) else {}
                    if code_map:
                        cur_cmap=load_codemap(); cur_cmap.update({str(k):str(v) for k,v in code_map.items() if v})
                        save_codemap(cur_cmap)
                        for nm in ad:
                            for it in ad[nm]:
                                if it.get("linked_username")!=uid: continue
                                for oit in it.get("orderItems",[]) or []:
                                    if oit.get("sellerProductCode"): continue
                                    vid=str(oit.get("vendorItemId") or "")
                                    if vid and code_map.get(vid):
                                        oit["sellerProductCode"]=code_map[vid]
                except Exception as e:
                    print(f"판매자상품코드 조회 오류({uid}):{e}")
            ast.append(row)
        if not s._stop:
            navs=[a for a in s.accs if a.get("market")=="naver"]
            for na in navs:
                if s._stop: break
                aid=na.get("account_id",na.get("username",""))
                mno=na.get("merchant_no","") or None  # 비어있으면 scrape 함수가 자동 추출
                s.prog.emit(85,f"네이버 {aid} 수집 중...")
                nrow={"username":aid,"market":"naver"}; nrow.update({k:0 for k in ad})
                try:
                    from naver_crawl import scrape_naver_orders
                    lp=asyncio.new_event_loop(); asyncio.set_event_loop(lp)
                    orders=lp.run_until_complete(scrape_naver_orders(aid,mno,s.sd,s.ed,"ALL",callback=lambda m:s.prog.emit(85,m)))
                    lp.close()
                    if orders:
                        for o in orders:
                            ps=o.get("productOrderStatus") or o.get("deliveryStatusCode") or ""
                            sn=NAV_MAP.get(ps,"결제완료")
                            if sn in ad: ad[sn].append(o); st[sn]+=1; nrow[sn]=nrow.get(sn,0)+1
                except Exception as e:
                    import traceback
                    print(f"네이버 주문오류 ({aid}): {e}")
                    traceback.print_exc()
                # 반품 수집 시 최신 merchant_no 사용 (주문 수집에서 채워졌을 수 있음)
                try:
                    navs_updated = load_nav()
                    mno2 = next((a.get("merchant_no","") for a in navs_updated if str(a.get("account_id"))==str(aid)), "") or mno
                    if not mno2:
                        print(f"네이버 {aid}: merchant_no 없음, 반품 수집 건너뜀")
                    else:
                        s.prog.emit(90,f"네이버 {aid} 반품 수집 중...")
                        from naver_crawl import scrape_naver_claims
                        lp2=asyncio.new_event_loop(); asyncio.set_event_loop(lp2)
                        cl=lp2.run_until_complete(scrape_naver_claims(aid,mno2,s.sd,s.ed,callback=lambda m:s.prog.emit(90,m)))
                        lp2.close()
                        for k,v in cl.items():
                            if k in ad: ad[k].extend(v); st[k]+=len(v); nrow[k]=nrow.get(k,0)+len(v)
                except Exception as e:
                    import traceback
                    print(f"네이버 반품오류 ({aid}): {e}")
                    traceback.print_exc()
                ast.append(nrow)
        for k in ad: ad[k].sort(key=lambda x:x.get("orderedAt",""),reverse=True)
        tot=sum(st[s] for s in OSTATUS)
        s.prog.emit(100,f"완료! 총 {tot}건")
        s.done.emit({"data":ad,"stats":st,"acc_stats":ast})

# ═══════════════════════════════════════════
# 로그인 다이얼로그
# ═══════════════════════════════════════════
class CheckBox(QWidget):
    """네모 안에 ✓ 체크마크 커스텀 위젯"""
    toggled=pyqtSignal(bool)
    def __init__(s,checked=True,parent=None):
        super().__init__(parent)
        s._on=checked; s.setCursor(Qt.CursorShape.PointingHandCursor)
        s.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
    def isChecked(s): return s._on
    def setChecked(s,v): s._on=v; s.update()
    def mousePressEvent(s,e): s._on=not s._on; s.update(); s.toggled.emit(s._on)
    def paintEvent(s,e):
        from PyQt6.QtGui import QPainter,QPen,QColor as _QC
        p=QPainter(s); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz=min(s.width(),s.height()); m=max((s.width()-sz)//2,0); mt=max((s.height()-sz)//2,0)
        p.setPen(QPen(_QC(FG),max(sz//12,1))); p.setBrush(_QC("#FFFFFF"))
        p.drawRoundedRect(m+1,mt+1,sz-2,sz-2,sz//6,sz//6)
        if s._on:
            p.setPen(QPen(_QC(FG),max(sz//8,2),Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            x1=m+sz*27//100; y1=mt+sz*50//100
            x2=m+sz*42//100; y2=mt+sz*68//100
            x3=m+sz*73//100; y3=mt+sz*32//100
            p.drawLine(x1,y1,x2,y2); p.drawLine(x2,y2,x3,y3)
        p.end()

class CheckBoxHeader(QHeaderView):
    """0번 컬럼에 체크박스 그리는 헤더"""
    toggled=pyqtSignal(bool)
    sortClicked=pyqtSignal(int)  # 정렬용 클릭 신호
    def __init__(s,parent=None):
        super().__init__(Qt.Orientation.Horizontal,parent)
        s._checked=True
        s.setSectionsClickable(True)
        s.setHighlightSections(False)
    def isChecked(s): return s._checked
    def setChecked(s,v): s._checked=v; s.viewport().update()
    def paintSection(s,painter,rect,logicalIndex):
        painter.save()
        super().paintSection(painter,rect,logicalIndex)
        painter.restore()
        if logicalIndex!=0: return
        from PyQt6.QtGui import QPainter,QPen,QColor as _QC
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        sz=18
        cx=rect.x()+(rect.width()-sz)//2
        cy=rect.y()+(rect.height()-sz)//2
        painter.setPen(QPen(_QC(FG),2))
        painter.setBrush(_QC("#FFFFFF"))
        painter.drawRoundedRect(cx,cy,sz,sz,3,3)
        if s._checked:
            painter.setPen(QPen(_QC(FG),2,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap,Qt.PenJoinStyle.RoundJoin))
            x1=cx+sz*27//100; y1=cy+sz*50//100
            x2=cx+sz*42//100; y2=cy+sz*68//100
            x3=cx+sz*73//100; y3=cy+sz*32//100
            painter.drawLine(x1,y1,x2,y2); painter.drawLine(x2,y2,x3,y3)
    def mousePressEvent(s,e):
        idx=s.logicalIndexAt(e.pos())
        if idx==0:
            s._checked=not s._checked
            s.viewport().update()
            s.toggled.emit(s._checked)
            return
        if idx >= 0:
            s.sortClicked.emit(idx)
        super().mousePressEvent(e)

class ToggleSwitch(QWidget):
    """iOS 스타일 온오프 스위치"""
    toggled=pyqtSignal(bool)
    def __init__(s,checked=True,parent=None):
        super().__init__(parent)
        s._on=checked; s._anim_pos=1.0 if checked else 0.0
        s.setFixedSize(36,20); s.setCursor(Qt.CursorShape.PointingHandCursor)
        s._anim=QPropertyAnimation(s,b"pos_ratio"); s._anim.setDuration(120)
    def isChecked(s): return s._on
    def setChecked(s,v):
        s._on=v; s._anim_pos=1.0 if v else 0.0; s.update()
    @pyqtProperty(float)
    def pos_ratio(s): return s._anim_pos
    @pos_ratio.setter
    def pos_ratio(s,v): s._anim_pos=v; s.update()
    def mousePressEvent(s,e):
        s._on=not s._on
        s._anim.setStartValue(s._anim_pos)
        s._anim.setEndValue(1.0 if s._on else 0.0)
        s._anim.start()
        s.toggled.emit(s._on)
    def paintEvent(s,e):
        from PyQt6.QtGui import QPainter,QColor as _QC
        p=QPainter(s); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w,h=s.width(),s.height(); r=h/2
        # 배경
        bg=_QC(ACCENT) if s._anim_pos>0.5 else _QC(BD)
        p.setBrush(bg); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0,0,w,h,r,r)
        # 원
        margin=2; dia=h-margin*2
        x=margin+s._anim_pos*(w-dia-margin*2)
        p.setBrush(_QC("#FFFFFF"))
        p.drawEllipse(int(x),margin,dia,dia)
        p.end()

class _DragInsertTable(QTableWidget):
    """드래그하면 행 사이에 삽입되는 테이블"""
    def __init__(s,*a,**kw):
        super().__init__(*a,**kw)
        s.setDragEnabled(True); s.setAcceptDrops(True); s.setDragDropOverwriteMode(False)
        s.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        s.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        s._drag_row=None; s._drop_row=-1
    def startDrag(s,actions):
        s._drag_row=s.currentRow()
        drag=QDrag(s); mime=QMimeData(); mime.setText(str(s._drag_row))
        drag.setMimeData(mime); drag.exec(Qt.DropAction.MoveAction)
        s._drop_row=-1; s.viewport().update()
    def dragEnterEvent(s,e):
        if e.mimeData().hasText(): e.acceptProposedAction()
    def dragMoveEvent(s,e):
        if e.mimeData().hasText():
            idx=s.indexAt(e.position().toPoint())
            s._drop_row=idx.row() if idx.isValid() else s.rowCount()
            s.viewport().update(); e.acceptProposedAction()
    def dragLeaveEvent(s,e): s._drop_row=-1; s.viewport().update()
    def paintEvent(s,e):
        super().paintEvent(e)
        if s._drop_row>=0:
            from PyQt6.QtGui import QPainter,QPen
            p=QPainter(s.viewport()); p.setPen(QPen(QColor(ACCENT),2))
            if s._drop_row<s.rowCount():
                y=s.visualRect(s.model().index(s._drop_row,0)).top()
            else:
                y=s.visualRect(s.model().index(s.rowCount()-1,0)).bottom()
            p.drawLine(0,y,s.viewport().width(),y); p.end()
    def dropEvent(s,e):
        s._drop_row=-1; s.viewport().update()
        if s._drag_row is None: return
        dr=s.indexAt(e.position().toPoint()).row()
        if dr==-1: dr=s.rowCount()-1
        if dr==s._drag_row: return
        cols=s.columnCount()
        rd=[]
        for c in range(cols):
            it=s.item(s._drag_row,c); rd.append(it.text() if it else "")
        s.removeRow(s._drag_row)
        if dr>s._drag_row: dr-=1
        s.insertRow(dr)
        for c in range(cols): s.setItem(dr,c,QTableWidgetItem(rd[c]))
        s.selectRow(dr); s._drag_row=None; e.acceptProposedAction()

class ModalDlg(QDialog):
    """항상 위 + 모달 다이얼로그 베이스"""
    def __init__(s,parent=None,**kw):
        super().__init__(parent,**kw)
        s.setWindowModality(Qt.WindowModality.ApplicationModal)
        s.setWindowFlags(s.windowFlags()|Qt.WindowType.WindowStaysOnTopHint)

class AuthDialog(QDialog):
    def __init__(s):
        super().__init__()
        s.setWindowModality(Qt.WindowModality.ApplicationModal)
        s.setWindowFlags(s.windowFlags()|Qt.WindowType.WindowStaysOnTopHint)
        s.setWindowTitle("ORDERMASTER")
        s.setFixedSize(360,400)
        s.setStyleSheet(f"QDialog{{background:#fff}}QLabel{{color:{FG}}}")
        s.uname=""; s.exp_at=""; s.uid=""
        ly=QVBoxLayout(s); ly.setContentsMargins(40,36,40,28); ly.setSpacing(14)

        t=QLabel("ORDERMASTER"); t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t.setStyleSheet(f"font-size:22px;font-weight:800;color:{FG};letter-spacing:2px")
        ly.addWidget(t)
        sub=QLabel("주문 통합관리"); sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"font-size:12px;color:{FG2}")
        ly.addWidget(sub); ly.addSpacing(8)

        s.inp_id=QLineEdit(); s.inp_id.setPlaceholderText("아이디"); s.inp_id.setFixedHeight(42); s.inp_id.setStyleSheet(S_INP)
        s.inp_pw=QLineEdit(); s.inp_pw.setPlaceholderText("비밀번호"); s.inp_pw.setEchoMode(QLineEdit.EchoMode.Password); s.inp_pw.setFixedHeight(42); s.inp_pw.setStyleSheet(S_INP)
        s.inp_pw.returnPressed.connect(s._login)
        ly.addWidget(s.inp_id); ly.addWidget(s.inp_pw)

        cr=QHBoxLayout(); cr.setSpacing(16)
        s.chk_save=QCheckBox("아이디 저장"); s.chk_save.setStyleSheet(f"color:{FG2};font-size:12px")
        s.chk_auto=QCheckBox("자동 로그인"); s.chk_auto.setStyleSheet(f"color:{FG2};font-size:12px")
        cr.addWidget(s.chk_save); cr.addWidget(s.chk_auto); cr.addStretch()
        ly.addLayout(cr)

        s.btn_go=QPushButton("로그인"); s.btn_go.setFixedHeight(44); s.btn_go.setStyleSheet(S_BTN)
        s.btn_go.clicked.connect(s._login)
        ly.addWidget(s.btn_go)

        s.btn_reg=QPushButton("회원가입"); s.btn_reg.setFixedHeight(38); s.btn_reg.setStyleSheet(S_BTN2)
        s.btn_reg.clicked.connect(s._register)
        ly.addWidget(s.btn_reg)

        fp=QPushButton("비밀번호를 잊으셨나요?")
        fp.setStyleSheet(f"QPushButton{{background:transparent;border:none;color:{ACCENT};font-size:12px;text-decoration:underline}}QPushButton:hover{{color:{FG}}}")
        fp.setCursor(Qt.CursorShape.PointingHandCursor); fp.clicked.connect(s._forgot)
        ly.addWidget(fp,alignment=Qt.AlignmentFlag.AlignCenter)
        ly.addStretch()

        s.msg=QLabel(""); s.msg.setStyleSheet(f"color:{RED};font-size:12px"); s.msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(s.msg)

        # 저장된 설정
        cfg=load_logincfg()
        if cfg.get("save_id"): s.chk_save.setChecked(True); s.inp_id.setText(cfg.get("username",""))
        if cfg.get("auto_login"): s.chk_auto.setChecked(True)
        if cfg.get("auto_login") and cfg.get("username") and cfg.get("password_hash"):
            s._auto_uid=cfg["username"]; s._auto_hash=cfg["password_hash"]
            QTimer.singleShot(200,s._auto)

    def _auto(s):
        s.inp_id.setText(s._auto_uid); s.msg.setText("자동 로그인 중..."); s.btn_go.setEnabled(False)
        class W(QThread):
            r=pyqtSignal(bool,str,str)
            def __init__(w,u,h): super().__init__(); w.u,w.h=u,h
            def run(w): ok,m,e=do_verify_hash(w.u,w.h); w.r.emit(ok,m,e)
        s._aw=W(s._auto_uid,s._auto_hash)
        def d(ok,m,e):
            if ok: s.uname=m; s.exp_at=e; s.uid=s._auto_uid; s.accept()
            else: s.msg.setText(m); s.btn_go.setEnabled(True)
        s._aw.r.connect(d); s._aw.start()

    def _login(s):
        uid=s.inp_id.text().strip(); pw=s.inp_pw.text()
        if not uid or not pw: s.msg.setText("아이디와 비밀번호를 입력하세요."); return
        s.btn_go.setEnabled(False); s.msg.setText("확인 중...")
        class W(QThread):
            r=pyqtSignal(bool,str,str)
            def __init__(w,u,p): super().__init__(); w.u,w.p=u,p
            def run(w): ok,m,e=do_verify(w.u,w.p); w.r.emit(ok,m,e)
        s._lw=W(uid,pw)
        def d(ok,m,e):
            if ok:
                save_logincfg(s.chk_save.isChecked(),s.chk_auto.isChecked(),uid,_ph(pw))
                s.uname=m; s.exp_at=e; s.uid=uid; s.accept()
            else: s.msg.setText(m); s.btn_go.setEnabled(True)
        s._lw.r.connect(d); s._lw.start()

    def _register(s):
        dlg=ModalDlg(s); dlg.setWindowTitle("회원가입"); dlg.setFixedSize(400,580); dlg.setStyleSheet(f"QDialog{{background:#fff}}QLabel{{color:{FG}}}")
        ly=QVBoxLayout(dlg); ly.setContentsMargins(36,28,36,24); ly.setSpacing(10)
        ly.addWidget(QLabel("회원가입",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        fields={}
        for ph,key,echo in [("아이디 (8자 이상)","id",False),("비밀번호 (6자 이상)","pw",True),("비밀번호 확인","pw2",True),("이름","name",False),("생년월일 (예: 19900101)","birth",False),("연락처 (예: 01000000000)","phone",False),("이메일","email",False),("추천인 (선택)","ref",False)]:
            inp=QLineEdit(); inp.setPlaceholderText(ph); inp.setFixedHeight(40); inp.setStyleSheet(S_INP)
            if echo: inp.setEchoMode(QLineEdit.EchoMode.Password)
            ly.addWidget(inp); fields[key]=inp
        msg=QLabel(""); msg.setStyleSheet(f"color:{RED};font-size:12px"); msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(msg)
        btn=QPushButton("가입하기"); btn.setFixedHeight(44); btn.setStyleSheet(S_BTN_OK); ly.addWidget(btn)
        cb=QPushButton("닫기"); cb.setFixedHeight(36); cb.setStyleSheet(S_BTN2); cb.clicked.connect(dlg.reject); ly.addWidget(cb)

        def _fmt_birth(t):
            d=''.join(c for c in t if c.isdigit())[:8]
            if len(d)>=5: f=f"{d[:4]}-{d[4:]}"
            else: f=d
            if len(d)>=7: f=f"{d[:4]}-{d[4:6]}-{d[6:]}"
            fields["birth"].blockSignals(True); fields["birth"].setText(f); fields["birth"].blockSignals(False)
        def _fmt_phone(t):
            d=''.join(c for c in t if c.isdigit())[:11]
            if len(d)>=8: f=f"{d[:3]}-{d[3:7]}-{d[7:]}"
            elif len(d)>=4: f=f"{d[:3]}-{d[3:]}"
            else: f=d
            fields["phone"].blockSignals(True); fields["phone"].setText(f); fields["phone"].blockSignals(False)
        fields["birth"].textChanged.connect(_fmt_birth)
        fields["phone"].textChanged.connect(_fmt_phone)

        def _go():
            uid=fields["id"].text().strip(); pw=fields["pw"].text(); pw2=fields["pw2"].text()
            nm=fields["name"].text().strip(); br=fields["birth"].text().strip()
            ph=fields["phone"].text().strip(); em=fields["email"].text().strip(); rf=fields["ref"].text().strip()
            if len(uid)<8: msg.setText("아이디 8자 이상"); return
            if len(pw)<6: msg.setText("비밀번호 6자 이상"); return
            if pw!=pw2: msg.setText("비밀번호 불일치"); return
            if not nm: msg.setText("이름 입력 필요"); return
            btn.setEnabled(False); msg.setText("가입 중...")
            class W(QThread):
                r=pyqtSignal(bool,str)
                def run(w): ok,m=do_signup(uid,pw,nm,br,ph,em,rf); w.r.emit(ok,m)
            s._rw=W()
            def d(ok,m):
                if ok: QMessageBox.information(dlg,"완료",m); s.inp_id.setText(uid); dlg.accept()
                else: msg.setText(m); btn.setEnabled(True)
            s._rw.r.connect(d); s._rw.start()
        btn.clicked.connect(_go); dlg.exec()

    def _forgot(s):
        dlg=ModalDlg(s); dlg.setWindowTitle("비밀번호 찾기"); dlg.setFixedSize(400,440); dlg.setStyleSheet(f"QDialog{{background:#fff}}QLabel{{color:{FG}}}")
        ly=QVBoxLayout(dlg); ly.setContentsMargins(36,28,36,24); ly.setSpacing(10)
        ly.addWidget(QLabel("비밀번호 찾기",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        ly.addWidget(QLabel("가입 정보 입력 시 000000으로 초기화됩니다.",styleSheet=f"color:{FG2};font-size:12px"))
        fields={}
        for ph,key in [("아이디","id"),("이름","name"),("연락처","phone"),("이메일","email"),("생년월일","birth")]:
            inp=QLineEdit(); inp.setPlaceholderText(ph); inp.setFixedHeight(40); inp.setStyleSheet(S_INP)
            ly.addWidget(inp); fields[key]=inp
        msg=QLabel(""); msg.setStyleSheet(f"color:{RED};font-size:12px")
        ly.addWidget(msg)
        btn=QPushButton("비밀번호 초기화"); btn.setFixedHeight(44); btn.setStyleSheet(S_BTN_WARN); ly.addWidget(btn)
        cb=QPushButton("닫기"); cb.setFixedHeight(36); cb.setStyleSheet(S_BTN2); cb.clicked.connect(dlg.reject); ly.addWidget(cb)
        def _go():
            btn.setEnabled(False); msg.setText("확인 중...")
            class W(QThread):
                r=pyqtSignal(bool,str)
                def run(w): ok,m=do_resetpw(fields["id"].text().strip(),fields["name"].text().strip(),fields["phone"].text().strip(),fields["email"].text().strip(),fields["birth"].text().strip()); w.r.emit(ok,m)
            s._fw=W()
            def d(ok,m):
                if ok: msg.setStyleSheet(f"color:{GREEN};font-size:12px;font-weight:600"); msg.setText(m); QMessageBox.information(dlg,"완료",m)
                else: msg.setText(m)
                btn.setEnabled(True)
            s._fw.r.connect(d); s._fw.start()
        btn.clicked.connect(_go); dlg.exec()

# ═══════════════════════════════════════════
# 메인 윈도우 — 상단 탭바 네비게이션
# ═══════════════════════════════════════════
class App(QMainWindow):
    def __init__(s, uname, exp_at, uid):
        super().__init__()
        s.setWindowTitle(f"ORDERMASTER  |  {uname}")
        s.setMinimumSize(1200,800)
        s.uname=uname; s.exp_at=exp_at; s.uid=uid
        s.order_data={k:[] for k in list(OSTATUS)+list(CSTATUS)}
        s.color_map={}

        cw=QWidget(); s.setCentralWidget(cw)
        root=QVBoxLayout(cw); root.setContentsMargins(0,0,0,0); root.setSpacing(0)

        # ── 최상단 헤더 ──
        top=QFrame(); top.setFixedHeight(56)
        top.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        tl=QHBoxLayout(top); tl.setContentsMargins(24,0,24,0); tl.setSpacing(16)
        logo=QLabel("ORDERMASTER"); logo.setStyleSheet(f"font-size:16px;font-weight:800;color:{FG};letter-spacing:1px")
        tl.addWidget(logo); tl.addSpacing(32)

        # 탭 네비게이션
        s.nav_btns=[]
        tabs=["대시보드","주문","반품/교환","마켓연동","통계","CS메모","엑셀양식","설정"]
        if uid==ADMIN: tabs+=["회원관리","공지관리"]
        for i,nm in enumerate(tabs):
            b=QPushButton(nm); b.setFixedHeight(56); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-bottom:2px solid transparent;color:{FG2};font-size:13px;font-weight:600;padding:0 16px}}QPushButton:hover{{color:{FG}}}")
            b.clicked.connect(lambda _,idx=i:s._go(idx))
            tl.addWidget(b); s.nav_btns.append(b)

        tl.addStretch()
        # 만료일
        s.exp_lbl=QLabel()
        s.exp_lbl.setStyleSheet(f"font-size:12px;color:{FG2}")
        if exp_at:
            try:
                ed=datetime.datetime.fromisoformat(exp_at.replace("Z","")).date()
                rem=(ed-datetime.date.today()).days
                s.exp_lbl.setText(f"{ed} ({rem}일)" if rem>=0 else f"만료 ({abs(rem)}일초과)")
                s.exp_lbl.setStyleSheet(f"font-size:12px;color:{GREEN if rem>=0 else RED};font-weight:600")
            except: s.exp_lbl.setText("무제한")
        else: s.exp_lbl.setText("무제한")
        tl.addWidget(s.exp_lbl)

        lo=QPushButton("로그아웃"); lo.setFixedHeight(32); lo.setStyleSheet(S_BTN2)
        lo.clicked.connect(s._logout)
        tl.addWidget(lo)
        root.addWidget(top)

        # OS 판별
        import platform as _pf
        s._is_mac=_pf.system()=="Darwin"

        # ── 스택 ──
        s.stack=QStackedWidget(); s.stack.setStyleSheet(f"background:{BG}")
        root.addWidget(s.stack)

        # 페이지 생성
        s.stack.addWidget(s._mk_dash())
        s.stack.addWidget(s._mk_orders())
        s.stack.addWidget(s._mk_returns())
        s.stack.addWidget(s._mk_market())
        s.stack.addWidget(s._mk_stats())
        s.stack.addWidget(s._mk_memo())
        s.stack.addWidget(s._mk_excel())
        s.stack.addWidget(s._mk_settings())
        if uid==ADMIN:
            s.stack.addWidget(s._mk_admin())
            s.stack.addWidget(s._mk_notice_admin())
            QTimer.singleShot(500,s._admin_load)
            QTimer.singleShot(600,s._notice_load)

        s._go(0)
        s._setup_tray()

        # 단축키
        QShortcut(QKeySequence("Ctrl+W"),s,s.close)
        QShortcut(QKeySequence("Ctrl+Q"),s,s.close)
        if s._is_mac:
            QShortcut(QKeySequence("Ctrl+1"),s,s._dash_fetch)
            QShortcut(QKeySequence("Ctrl+2"),s,s._dash_fetch_sel)
            QShortcut(QKeySequence("Ctrl+3"),s,s._dash_stop)
            QShortcut(QKeySequence("Ctrl+4"),s,s._mkt_popup)
        else:
            QShortcut(QKeySequence("F5"),s,s._dash_fetch)
            QShortcut(QKeySequence("F6"),s,s._dash_fetch_sel)
            QShortcut(QKeySequence("F7"),s,s._dash_stop)
            QShortcut(QKeySequence("F8"),s,s._mkt_popup)

    def eventFilter(s,obj,event):
        if isinstance(obj,QTableWidget) and event.type()==QEvent.Type.Wheel:
            sb=obj.horizontalScrollBar()
            if sb and sb.maximum()>0:
                delta=event.angleDelta().y()
                sb.setValue(sb.value()-delta)
                return True
        return super().eventFilter(obj,event)

    def _go(s,idx):
        s.stack.setCurrentIndex(idx)
        for i,b in enumerate(s.nav_btns):
            if i==idx: b.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-bottom:2px solid {FG};color:{FG};font-size:13px;font-weight:600;padding:0 16px}}")
            else: b.setStyleSheet(f"QPushButton{{background:transparent;border:none;border-bottom:2px solid transparent;color:{FG2};font-size:13px;font-weight:600;padding:0 16px}}QPushButton:hover{{color:{FG}}}")

    def _logout(s):
        if QMessageBox.question(s,"로그아웃","로그아웃 하시겠습니까?")!=QMessageBox.StandardButton.Yes: return
        save_logincfg()
        QMessageBox.information(s,"로그아웃","프로그램을 다시 시작합니다.")
        os.execl(sys.executable,sys.executable,*sys.argv)

    def closeEvent(s,e):
        dlg=ModalDlg(s); dlg.setWindowTitle("종료")
        dlg.setFixedWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        v=QVBoxLayout(dlg); v.setContentsMargins(28,24,28,22); v.setSpacing(14)

        # 헤더
        head=QHBoxLayout(); head.setSpacing(10)
        ic=QLabel("●"); ic.setFixedWidth(14); ic.setStyleSheet(f"color:{ACCENT};font-size:14px;background:transparent")
        ttl=QLabel("ORDERMASTER 종료"); ttl.setStyleSheet(f"font-size:17px;font-weight:700;color:{FG};background:transparent")
        head.addWidget(ic); head.addWidget(ttl); head.addStretch()
        v.addLayout(head)

        sub=QLabel("창을 닫는 대신 트레이로 숨길 수도 있습니다.")
        sub.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent"); sub.setWordWrap(True)
        v.addWidget(sub)
        v.addSpacing(4)

        # 버튼 3개 세로 배치 (각 버튼에 설명 문구 포함)
        def _make_btn(title, desc, style):
            b=QPushButton()
            b.setFixedHeight(54); b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(style)
            bl=QVBoxLayout(b); bl.setContentsMargins(16,6,16,6); bl.setSpacing(2)
            t=QLabel(title); t.setStyleSheet("font-size:13px;font-weight:700;background:transparent;border:none;color:inherit")
            d=QLabel(desc); d.setStyleSheet("font-size:11px;background:transparent;border:none;color:inherit")
            bl.addWidget(t); bl.addWidget(d)
            b.setLayout(bl)
            return b

        choice=[None]
        btn_hide=_make_btn("창 숨김 (트레이)", "백그라운드에서 계속 실행",
            f"QPushButton{{background:{WHITE};color:{FG};border:1px solid {BD};border-radius:10px;text-align:left;padding-left:6px}}QPushButton:hover{{background:#F9FAFB;border-color:#9CA3AF}}")
        btn_quit=_make_btn("완전 종료", "프로그램을 완전히 닫습니다",
            f"QPushButton{{background:{WHITE};color:{RED};border:1px solid #FCA5A5;border-radius:10px;text-align:left;padding-left:6px}}QPushButton:hover{{background:#FEF2F2;border-color:{RED}}}")
        btn_cancel=_make_btn("취소", "창을 그대로 둡니다",
            f"QPushButton{{background:transparent;color:{FG2};border:1px solid {BD};border-radius:10px;text-align:left;padding-left:6px}}QPushButton:hover{{background:#F9FAFB}}")

        def _set(c): choice[0]=c; dlg.accept()
        btn_hide.clicked.connect(lambda: _set("hide"))
        btn_quit.clicked.connect(lambda: _set("quit"))
        btn_cancel.clicked.connect(lambda: _set("cancel"))

        v.addWidget(btn_hide); v.addWidget(btn_quit); v.addWidget(btn_cancel)

        dlg.exec()

        if choice[0]=="quit":
            e.accept(); QApplication.quit()
        elif choice[0]=="hide":
            e.ignore(); s.hide()
            if hasattr(s,"_tray"): s._tray.showMessage("ORDERMASTER","백그라운드에서 실행 중입니다.",QSystemTrayIcon.MessageIcon.Information,2000)
        else:
            e.ignore()

    def _setup_tray(s):
        s._tray=QSystemTrayIcon(s)
        icon_path=os.path.join(os.path.dirname(os.path.abspath(__file__)),"icon_1024.png")
        if os.path.exists(icon_path): s._tray.setIcon(QIcon(icon_path))
        else: s._tray.setIcon(s.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon))
        menu=QMenu()
        menu.addAction("열기",s._tray_show)
        menu.addAction("종료",lambda:(QApplication.quit()))
        s._tray.setContextMenu(menu)
        s._tray.activated.connect(lambda reason:s._tray_show() if reason==QSystemTrayIcon.ActivationReason.DoubleClick else None)
        s._tray.show()

    def _tray_show(s):
        s.show(); s.raise_(); s.activateWindow()

    # ── 유틸 ──
    def _hdr(s,title,sub=""):
        f=QFrame(); f.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        ly=QVBoxLayout(f); ly.setContentsMargins(28,14,28,14); ly.setSpacing(6)
        r=QHBoxLayout()
        r.addWidget(QLabel(title,styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        if sub: r.addWidget(QLabel(sub,styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        r.addStretch()
        ly.addLayout(r)
        return f,ly

    def _date_row(s,prefix):
        r=QHBoxLayout(); r.setSpacing(8)
        for label,days in [("오늘",0),("7일",-6),("30일",-29),("90일",-89)]:
            b=QPushButton(label); b.setFixedSize(44,28)
            b.setStyleSheet(f"QPushButton{{background:transparent;color:{FG2};border:1px solid {BD};border-radius:6px;font-size:12px;font-weight:600}}QPushButton:hover{{background:#F3F4F6}}")
            b.clicked.connect(lambda _,d=days,p=prefix: (getattr(s,f"{p}_s").setDate(QDate.currentDate().addDays(d)),getattr(s,f"{p}_e").setDate(QDate.currentDate())))
            r.addWidget(b)
        sd=QDateEdit(); sd.setCalendarPopup(True); sd.setDate(QDate.currentDate().addDays(-7)); sd.setFixedHeight(32); sd.setStyleSheet(S_CAL)
        ed=QDateEdit(); ed.setCalendarPopup(True); ed.setDate(QDate.currentDate()); ed.setFixedHeight(32); ed.setStyleSheet(S_CAL)
        setattr(s,f"{prefix}_s",sd); setattr(s,f"{prefix}_e",ed)
        r.addWidget(QLabel("기간",styleSheet=f"color:{FG2};font-size:12px")); r.addWidget(sd)
        r.addWidget(QLabel("~",styleSheet=f"color:{FG2};font-size:12px")); r.addWidget(ed)
        return r

    def _stat_card(s,name,color,bg):
        f=QFrame(); f.setFixedHeight(72)
        f.setStyleSheet(f"QFrame{{background:{bg};border:1px solid {color}22;border-left:4px solid {color};border-radius:10px}}")
        cl=QVBoxLayout(f); cl.setContentsMargins(14,10,14,10); cl.setSpacing(2)
        cl.addWidget(QLabel(name,styleSheet=f"color:{color};font-weight:600;font-size:11px;border:none;background:transparent"))
        v=QLabel("0건"); v.setObjectName("v")
        v.setStyleSheet(f"color:{color};font-size:20px;font-weight:700;border:none;background:transparent")
        cl.addWidget(v); return f

    # ═══════════════════════════════════════════
    # 대시보드
    # ═══════════════════════════════════════════
    def _mk_dash(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr,hl=s._hdr("대시보드","주문 + 반품/교환 한번에 수집")
        dr=s._date_row("d"); dr.addStretch()
        k1,k2,k3,k4=("⌘1","⌘2","⌘3","⌘4") if s._is_mac else ("F5","F6","F7","F8")
        s.d_fetchall=QPushButton(f"전체수집({k1})"); s.d_fetchall.setFixedHeight(32); s.d_fetchall.setStyleSheet(S_BTN); s.d_fetchall.clicked.connect(s._dash_fetch)
        s.d_fetchsel=QPushButton(f"개별수집({k2})"); s.d_fetchsel.setFixedHeight(32); s.d_fetchsel.setStyleSheet(S_BTN2); s.d_fetchsel.clicked.connect(s._dash_fetch_sel)
        s.d_stop=QPushButton(f"중지({k3})"); s.d_stop.setFixedHeight(32); s.d_stop.setEnabled(False); s.d_stop.setStyleSheet(S_BTN_ERR); s.d_stop.clicked.connect(s._dash_stop)
        s.d_mkt=QPushButton(f"마켓연동하기({k4})"); s.d_mkt.setFixedHeight(32); s.d_mkt.setStyleSheet(S_BTN_OK); s.d_mkt.clicked.connect(s._mkt_popup)
        dr.addWidget(s.d_fetchall); dr.addWidget(s.d_fetchsel); dr.addWidget(s.d_stop); dr.addWidget(s.d_mkt)
        hl.addLayout(dr); ly.addWidget(hdr)

        s.d_prog=QProgressBar(); s.d_prog.setFixedHeight(22); s.d_prog.setValue(0); s.d_prog.setFormat("대기 중"); s.d_prog.setStyleSheet(S_PROG)
        pf=QFrame(); pf.setStyleSheet(f"background:{WHITE}"); pfl=QVBoxLayout(pf); pfl.setContentsMargins(28,6,28,6); pfl.addWidget(s.d_prog)
        ly.addWidget(pf)

        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(S_SCROLL)
        inner=QWidget(); inner.setStyleSheet(f"background:{BG}")
        il=QVBoxLayout(inner); il.setContentsMargins(28,20,28,20); il.setSpacing(20)

        # 연동 현황 (맨 위)
        il.addWidget(QLabel("연동 현황",styleSheet=f"font-size:14px;font-weight:600;color:{FG};background:transparent"))
        s.conn_frame=QFrame()
        s.conn_frame.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:12px")
        s.conn_ly=QHBoxLayout(s.conn_frame); s.conn_ly.setContentsMargins(20,12,20,12); s.conn_ly.setSpacing(16)
        s._refresh_conn()
        il.addWidget(s.conn_frame)

        # 주문 현황
        il.addWidget(QLabel("주문 현황",styleSheet=f"font-size:14px;font-weight:600;color:{FG};background:transparent"))
        or_=QHBoxLayout(); or_.setSpacing(12)
        s.scards={}
        for nm,(c,bg) in SCOLORS.items():
            cd=s._stat_card(nm,c,bg); or_.addWidget(cd); s.scards[nm]=cd.findChild(QLabel,"v")
            cd.setCursor(Qt.CursorShape.PointingHandCursor)
            def _mk_order_click(name):
                def handler(e): s._go(1); QTimer.singleShot(50,lambda:s.o_tabs.setCurrentIndex(list(OSTATUS).index(name)))
                return handler
            cd.mousePressEvent=_mk_order_click(nm)
        il.addLayout(or_)

        # 반품 현황
        il.addWidget(QLabel("반품/교환 현황",styleSheet=f"font-size:14px;font-weight:600;color:{FG};background:transparent"))
        cr_=QHBoxLayout(); cr_.setSpacing(12)
        s.ccards={}
        for nm,(c,bg) in CCOLORS.items():
            cd=s._stat_card(nm,c,bg); cr_.addWidget(cd); s.ccards[nm]=cd.findChild(QLabel,"v")
            cd.setCursor(Qt.CursorShape.PointingHandCursor)
            def _mk_claim_click(name):
                def handler(e): s._go(2); QTimer.singleShot(50,lambda:s.r_tabs.setCurrentIndex(list(CSTATUS).index(name)))
                return handler
            cd.mousePressEvent=_mk_claim_click(nm)
        il.addLayout(cr_)

        # 매출 요약
        sf=QFrame(); sf.setFixedHeight(76)
        sf.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:12px")
        sl=QHBoxLayout(sf); sl.setContentsMargins(24,0,24,0); sl.setSpacing(32)
        s.sales={}
        for key,c in [("오늘 결제금액",FG),("오늘 주문건수",FG),("어제 결제금액",FG2),("어제 주문건수",FG2),("7일 결제금액",GREEN),("7일 주문건수",GREEN)]:
            col=QVBoxLayout(); col.setSpacing(2)
            col.addWidget(QLabel(key,styleSheet=f"font-size:11px;color:{FG2}"))
            v=QLabel("0원" if "금액" in key else "0건"); v.setStyleSheet(f"font-size:18px;font-weight:700;color:{c}")
            col.addWidget(v); sl.addLayout(col); s.sales[key]=v
        sl.addStretch()
        il.addWidget(sf)

        # 공지사항
        il.addWidget(QLabel("공지사항",styleSheet=f"font-size:14px;font-weight:600;color:{FG};background:transparent"))
        s.ntc_frame=QFrame()
        s.ntc_frame.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:12px")
        s.ntc_inner=QVBoxLayout(s.ntc_frame); s.ntc_inner.setContentsMargins(20,14,20,14); s.ntc_inner.setSpacing(8)
        s.ntc_inner.addWidget(QLabel("공지사항을 불러오는 중...",styleSheet=f"font-size:13px;color:{FG2}"))
        il.addWidget(s.ntc_frame)
        QTimer.singleShot(800,s._load_dash_notices)

        il.addStretch()
        sc.setWidget(inner); ly.addWidget(sc)
        return pg

    def _load_dash_notices(s):
        """대시보드 공지사항 로드"""
        class W(QThread):
            done=pyqtSignal(object)
            def run(w):
                try:
                    rows=_sbget("notices","is_active=eq.true&order=created_at.desc","title,content")
                    w.done.emit([(r["title"],r["content"]) for r in rows] if rows else None)
                except: w.done.emit(None)
        s._ntc_w=W()
        def _on(data):
            # 기존 위젯 제거
            while s.ntc_inner.count():
                it=s.ntc_inner.takeAt(0)
                if it and it.widget(): it.widget().deleteLater()
            if not data:
                s.ntc_inner.addWidget(QLabel("공지사항이 없습니다.",styleSheet=f"font-size:13px;color:{FG3}"))
                return
            for title,content in data:
                row=QFrame(); row.setStyleSheet(f"background:#F9FAFB;border:1px solid {BD2};border-radius:8px")
                rl=QVBoxLayout(row); rl.setContentsMargins(14,10,14,10); rl.setSpacing(4)
                tl=QLabel(title); tl.setStyleSheet(f"font-size:13px;font-weight:600;color:{FG}")
                rl.addWidget(tl)
                preview=content[:100]+("..." if len(content)>100 else "")
                cl=QLabel(preview); cl.setWordWrap(True); cl.setStyleSheet(f"font-size:12px;color:{FG2}")
                rl.addWidget(cl)
                row.setCursor(Qt.CursorShape.PointingHandCursor)
                def _mk_click(t,c):
                    def handler(e): s._show_notice(t,c)
                    return handler
                row.mousePressEvent=_mk_click(title,content)
                s.ntc_inner.addWidget(row)
        s._ntc_w.done.connect(_on); s._ntc_w.start()

    def _show_notice(s,title,content):
        dlg=ModalDlg(s); dlg.setWindowTitle("공지사항"); dlg.setFixedSize(500,350)
        dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(12)
        dl.addWidget(QLabel(title,styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        lbl=QLabel(content); lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color:{FG2};font-size:13px;background:#F9FAFB;border-radius:8px;padding:14px")
        lbl.setAlignment(Qt.AlignmentFlag.AlignTop)
        dl.addWidget(lbl,1)
        cb=QPushButton("닫기"); cb.setFixedHeight(34); cb.setStyleSheet(S_BTN2); cb.clicked.connect(dlg.accept)
        dl.addWidget(cb)
        dlg.exec()

    def _refresh_conn(s):
        """연동 현황 라벨 갱신"""
        # 기존 라벨 제거
        while s.conn_ly.count():
            it=s.conn_ly.takeAt(0)
            if it and it.widget(): it.widget().deleteLater()
        cpg=load_all_accounts() or []; nav=load_nav()
        if not cpg and not nav:
            lbl=QLabel("연동된 계정이 없습니다."); lbl.setStyleSheet(f"font-size:12px;color:{FG3}"); s.conn_ly.addWidget(lbl)
            return
        for a in cpg:
            uid=a["username"]; ok=bool(load_cookies(uid))
            icon="●" if ok else "○"; color=GREEN if ok else RED
            lbl=QLabel(f"{icon} 쿠팡 {uid}")
            lbl.setStyleSheet(f"font-size:12px;font-weight:600;color:{color};background:transparent")
            s.conn_ly.addWidget(lbl)
        for n in nav:
            aid=n.get("account_id",""); ok=bool(load_naver_cookies(aid))
            icon="●" if ok else "○"; color=GREEN if ok else RED
            store=n.get("store_name",aid)
            lbl=QLabel(f"{icon} 네이버 {store}")
            lbl.setStyleSheet(f"font-size:12px;font-weight:600;color:{color};background:transparent")
            s.conn_ly.addWidget(lbl)
        s.conn_ly.addStretch()
        # 연동된 계정 하나라도 있으면 자동새로고침 켜기
        has_any=False
        for a in cpg:
            if load_cookies(a["username"]): has_any=True; break
        if not has_any:
            for n in nav:
                if load_naver_cookies(n.get("account_id","")): has_any=True; break
        if has_any and hasattr(s,"auto_refresh_cb") and not s.auto_refresh_cb.isChecked():
            s.auto_refresh_cb.setChecked(True)

    def _get_all_accs(s):
        accs=load_all_accounts() or []
        for n in load_nav():
            accs.append({"username":n.get("account_id",""),"market":"naver","account_id":n.get("account_id",""),"merchant_no":n.get("merchant_no",""),"store_name":n.get("store_name","")})
        return accs

    def _dash_fetch(s,selected=None):
        accs=selected or s._get_all_accs()
        if not accs: QMessageBox.warning(s,"알림","연동 계정 없음"); return
        pws=load_pw()
        s.color_map={a["username"]:TINTS[i%len(TINTS)] for i,a in enumerate(accs)}
        sd=s.d_s.date().toString("yyyy-MM-dd"); ed=s.d_e.date().toString("yyyy-MM-dd")
        s.d_fetchall.setEnabled(False); s.d_fetchsel.setEnabled(False); s.d_stop.setEnabled(True)
        s.d_prog.setValue(0); s.d_prog.setFormat("수집 시작...")
        s._cw=CollectWorker(accs,pws,sd,ed)
        s._cw.prog.connect(lambda p,m:(s.d_prog.setValue(p),s.d_prog.setFormat(f"{m} {p}%")))
        s._cw.done.connect(s._dash_done)
        s._cw.finished.connect(lambda:(s.d_fetchall.setEnabled(True),s.d_fetchsel.setEnabled(True),s.d_stop.setEnabled(False)))
        s._cw.start()

    def _dash_fetch_sel(s):
        accs=s._pick_accs()
        if accs: s._dash_fetch(accs)

    def _dash_stop(s):
        if hasattr(s,"_cw") and s._cw.isRunning():
            s._cw.stop(); s.d_prog.setFormat("중지됨")
            s.d_fetchall.setEnabled(True); s.d_fetchsel.setEnabled(True); s.d_stop.setEnabled(False)

    def _mkt_popup(s):
        """마켓연동하기 팝업 — 쿠팡/네이버 개별 연동"""
        dlg=ModalDlg(s); dlg.setWindowTitle("마켓 연동"); dlg.setFixedSize(380,280)
        dlg.setStyleSheet(f"QDialog{{background:#fff}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(28,24,28,24); dl.setSpacing(14)
        dl.addWidget(QLabel("마켓 연동",styleSheet=f"font-size:18px;font-weight:700;color:{FG}"))
        dl.addWidget(QLabel("연동할 마켓을 선택하세요.",styleSheet=f"font-size:12px;color:{FG2}"))
        dl.addSpacing(8)
        # 쿠팡 버튼
        cpg_btn=QPushButton("쿠팡 Wing 연동"); cpg_btn.setFixedHeight(48)
        cpg_btn.setStyleSheet(f"QPushButton{{background:{WHITE};color:{FG};border:1px solid {BD};border-radius:10px;font-size:14px;font-weight:600;text-align:left;padding-left:20px}}QPushButton:hover{{background:#F9FAFB;border-color:#D1D5DB}}")
        cpg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cpg_btn.clicked.connect(lambda:(dlg.accept(),s._add_cpg()))
        dl.addWidget(cpg_btn)
        # 네이버 버튼
        nav_btn=QPushButton("네이버 스마트스토어 연동"); nav_btn.setFixedHeight(48)
        nav_btn.setStyleSheet(f"QPushButton{{background:{WHITE};color:{GREEN};border:1px solid {BD};border-radius:10px;font-size:14px;font-weight:600;text-align:left;padding-left:20px}}QPushButton:hover{{background:#F0FDF4;border-color:#A7F3D0}}")
        nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        nav_btn.clicked.connect(lambda:(dlg.accept(),s._add_nav()))
        dl.addWidget(nav_btn)
        dl.addStretch()
        # 마켓연동 페이지로 이동
        go_btn=QPushButton("마켓연동 페이지로 이동"); go_btn.setFixedHeight(36); go_btn.setStyleSheet(S_BTN2)
        go_btn.clicked.connect(lambda:(dlg.accept(),s._go(3)))
        dl.addWidget(go_btn)
        dlg.exec()

    def _pick_accs(s):
        cpg=load_all_accounts() or []; nav=load_nav()
        if not cpg and not nav: QMessageBox.warning(s,"알림","연동 계정 없음"); return None
        dlg=ModalDlg(s); dlg.setWindowTitle("계정 선택"); dlg.setMinimumWidth(360); dlg.setStyleSheet(f"QDialog{{background:#fff}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(10)
        dl.addWidget(QLabel("수집할 계정 선택",styleSheet=f"font-size:15px;font-weight:600;color:{FG}"))
        cbs={}
        for a in cpg:
            cb=QCheckBox(f"쿠팡 | {a['username']}"); cb.setStyleSheet(f"font-size:13px;color:{FG};padding:6px"); dl.addWidget(cb); cbs[a["username"]]=(cb,a)
        for n in nav:
            aid=n.get("account_id",""); cb=QCheckBox(f"네이버 | {aid}"); cb.setStyleSheet(f"font-size:13px;color:{GREEN};padding:6px"); dl.addWidget(cb)
            cbs[f"nv:{aid}"]=(cb,{"username":aid,"market":"naver","account_id":aid,"merchant_no":n.get("merchant_no","")})
        dl.addStretch()
        br=QHBoxLayout()
        ok=QPushButton("수집"); ok.setFixedHeight(36); ok.setStyleSheet(S_BTN); ok.clicked.connect(dlg.accept)
        cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        br.addStretch(); br.addWidget(cn); br.addWidget(ok); dl.addLayout(br)
        if dlg.exec()!=QDialog.DialogCode.Accepted: return None
        sel=[info for cb,info in cbs.values() if cb.isChecked()]
        if not sel: QMessageBox.warning(s,"알림","선택 필요"); return None
        return sel

    def _dash_done(s,res):
        ad=res["data"]; st=res["stats"]
        s.order_data=ad
        for nm in OSTATUS:
            if nm in s.scards: s.scards[nm].setText(f"{st.get(nm,0)}건")
        for nm in CSTATUS:
            if nm in s.ccards: s.ccards[nm].setText(f"{st.get(nm,0)}건")
        # 매출
        today=datetime.date.today().isoformat(); yest=(datetime.date.today()-datetime.timedelta(1)).isoformat(); ws=(datetime.date.today()-datetime.timedelta(6)).isoformat()
        ta=tc=ya=yc=wa=wc=0
        for st2 in OSTATUS:
            for o in ad.get(st2,[]):
                d=o.get("orderedAt","")[:10]; p=int(o.get("totalPrice") or 0)
                if d==today: ta+=p; tc+=1
                if d==yest: ya+=p; yc+=1
                if d>=ws: wa+=p; wc+=1
        s.sales["오늘 결제금액"].setText(f"{ta:,}원"); s.sales["오늘 주문건수"].setText(f"{tc}건")
        s.sales["어제 결제금액"].setText(f"{ya:,}원"); s.sales["어제 주문건수"].setText(f"{yc}건")
        s.sales["7일 결제금액"].setText(f"{wa:,}원"); s.sales["7일 주문건수"].setText(f"{wc}건")
        # 주문 테이블 갱신
        for nm,items in ad.items():
            if nm in OSTATUS and nm in s.otbls: s._fill_order(nm,items)
            elif nm in CSTATUS and nm in s.rtbls: s._fill_return(nm,items)
        to=sum(st.get(k,0) for k in OSTATUS); tc2=sum(st.get(k,0) for k in CSTATUS)
        s.d_prog.setValue(100); s.d_prog.setFormat(f"완료! 주문 {to}건 | 반품 {tc2}건")
        # 통계 갱신
        if hasattr(s,"stat_tbls"): s._refresh_stats()
        # 만료된 계정 있으면 재연동 → 이어서 수집
        expired_cpg=[]; expired_nav=[]
        cpg=load_all_accounts() or []; navs=load_nav()
        for a in cpg:
            if not load_cookies(a["username"]): expired_cpg.append(a)
        for n in navs:
            if not load_naver_cookies(n.get("account_id","")): expired_nav.append(n)
        if expired_cpg or expired_nav:
            names=[f"쿠팡: {a['username']}" for a in expired_cpg]+[f"네이버: {n.get('store_name',n.get('account_id',''))}" for n in expired_nav]
            reply=QMessageBox.question(s,"연동 만료",f"다음 계정의 연동이 만료되었습니다.\n\n"+"\n".join(names)+"\n\n지금 재연동 하시겠습니까?")
            if reply==QMessageBox.StandardButton.Yes:
                s._relink_and_fetch(expired_cpg,expired_nav)

    def _relink_and_fetch(s,cpg_list,nav_list):
        """만료 계정 순차 재연동 후 이어서 수집"""
        pws=load_pw()
        pending=[]
        for a in cpg_list: pending.append(("cpg",a["username"]))
        for n in nav_list: pending.append(("nav",n.get("account_id","")))
        if not pending: return

        dlg=ModalDlg(s); dlg.setWindowTitle("재연동 진행 중")
        dlg.setFixedWidth(400); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(10)
        dl.addWidget(QLabel("재연동 중...",styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        status_lbl=QLabel(""); status_lbl.setStyleSheet(f"font-size:13px;color:{FG2}")
        dl.addWidget(status_lbl)
        dlg.show(); QApplication.processEvents()

        def _ask_password(uid, prev_msg=""):
            """비번 재입력 모달. 입력한 비번 반환, 취소면 None."""
            pdlg=ModalDlg(s); pdlg.setWindowTitle("비밀번호 재입력")
            pdlg.setFixedWidth(380)
            pdlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
            pv=QVBoxLayout(pdlg); pv.setContentsMargins(28,22,28,20); pv.setSpacing(10)
            head=QLabel(f"쿠팡 비밀번호 재입력")
            head.setStyleSheet(f"font-size:16px;font-weight:700;color:{FG};background:transparent")
            pv.addWidget(head)
            sub=QLabel(f"계정: {uid}")
            sub.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent")
            pv.addWidget(sub)
            if prev_msg:
                err=QLabel(f"이전 시도 실패: {prev_msg}")
                err.setStyleSheet(f"font-size:11px;color:{RED};background:#FEF2F2;border:1px solid #FCA5A5;border-radius:6px;padding:6px 10px")
                err.setWordWrap(True)
                pv.addWidget(err)
            pv.addSpacing(4)
            pi=QLineEdit(); pi.setPlaceholderText("비밀번호"); pi.setEchoMode(QLineEdit.EchoMode.Password)
            pi.setFixedHeight(40); pi.setStyleSheet(S_INP)
            pv.addWidget(pi)
            br=QHBoxLayout(); br.setSpacing(8)
            cn=QPushButton("건너뜀"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok=QPushButton("재시도"); ok.setFixedHeight(36); ok.setStyleSheet(S_BTN); ok.setCursor(Qt.CursorShape.PointingHandCursor)
            cn.clicked.connect(pdlg.reject); ok.clicked.connect(pdlg.accept)
            pi.returnPressed.connect(pdlg.accept)
            br.addStretch(); br.addWidget(cn); br.addWidget(ok)
            pv.addLayout(br)
            pi.setFocus()
            if pdlg.exec() != QDialog.DialogCode.Accepted: return None
            new_pw=pi.text()
            if not new_pw: return None
            save_pw(uid, new_pw)
            return new_pw

        def _try_cpg_login(idx, uid, pw):
            status_lbl.setText(f"쿠팡 {uid} 재연동 중...")
            QApplication.processEvents()
            wkr=LoginWorker(uid, pw)
            def _done(r, i=idx, u=uid):
                if r.get("success"):
                    save_account(u); save_ip(get_public_ip())
                    status_lbl.setText(f"쿠팡 {u} 연동 완료!")
                    QTimer.singleShot(500, lambda:_do_next(i+1))
                    return
                # 실패 → 비번 재입력 모달
                msg=r.get("message","로그인 실패")
                status_lbl.setText(f"쿠팡 {u} 실패: {msg}")
                QApplication.processEvents()
                new_pw=_ask_password(u, msg)
                if not new_pw:
                    status_lbl.setText(f"쿠팡 {u}: 건너뜀")
                    QTimer.singleShot(500, lambda:_do_next(i+1))
                    return
                pws[u]=new_pw
                _try_cpg_login(i, u, new_pw)
            wkr.done.connect(_done)
            if not hasattr(s,'_rlink_ws'): s._rlink_ws=[]
            s._rlink_ws.append(wkr); wkr.start()

        def _do_next(idx=0):
            if idx>=len(pending):
                status_lbl.setText("재연동 완료! 수집을 이어서 시작합니다.")
                QTimer.singleShot(1000,lambda:(dlg.accept(),s._refresh_conn(),s._dash_fetch()))
                return
            typ,uid=pending[idx]
            if typ=="cpg":
                pw=pws.get(uid,"")
                if not pw:
                    status_lbl.setText(f"쿠팡 {uid}: 비밀번호 입력 필요")
                    QApplication.processEvents()
                    new_pw=_ask_password(uid, "저장된 비밀번호 없음")
                    if not new_pw:
                        status_lbl.setText(f"쿠팡 {uid}: 건너뜀")
                        QTimer.singleShot(500,lambda:_do_next(idx+1)); return
                    pws[uid]=new_pw; pw=new_pw
                _try_cpg_login(idx, uid, pw)
            else:
                status_lbl.setText(f"네이버 {uid} 재연동 중... (브라우저 열기)")
                QApplication.processEvents()
                nav_pw = load_nav_pw().get(uid, "")
                nav_ltype = next((a.get("login_type","seller") for a in load_nav() if str(a.get("account_id"))==str(uid)),"seller")
                class NW(QThread):
                    done2=pyqtSignal(object)
                    def run(self2):
                        try: self2.done2.emit(do_naver_login(uid, naver_id=uid, naver_pw=nav_pw, login_type=nav_ltype))
                        except: self2.done2.emit(None)
                w=NW()
                def _done2(r,i=idx):
                    if r and isinstance(r,dict) and r.get("success") is not False and r.get("account_id"):
                        save_nav(r.get("account_id",uid),mno=r.get("merchant_no",""),store="스마트스토어")
                        status_lbl.setText(f"네이버 {uid} 연동 완료!")
                    else:
                        msg = r.get("message","실패") if isinstance(r,dict) else "실패"
                        status_lbl.setText(f"네이버 {uid} 실패: {msg}")
                    QTimer.singleShot(500,lambda:_do_next(i+1))
                w.done2.connect(_done2)
                if not hasattr(s,'_rlink_ws'): s._rlink_ws=[]
                s._rlink_ws.append(w); w.start()
        _do_next(0)
        dlg.exec()

    # ═══════════════════════════════════════════
    # 주문관리
    # ═══════════════════════════════════════════
    def _mk_orders(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr,hl=s._hdr("주문 관리","주문 조회 · 엑셀 다운로드")
        dr=s._date_row("o"); dr.addStretch()
        # 토글 버튼
        dr.addWidget(QLabel("판매자상품코드",styleSheet=f"font-size:12px;color:{FG}"))
        s.sw_scode=ToggleSwitch(True); s.sw_scode.toggled.connect(lambda on:s._toggle_col(7,on))
        dr.addWidget(s.sw_scode)
        dr.addSpacing(8)
        dr.addWidget(QLabel("구매처",styleSheet=f"font-size:12px;color:{FG}"))
        s.sw_purchase=ToggleSwitch(False); s.sw_purchase.toggled.connect(lambda on:s._toggle_col(17,on))
        dr.addWidget(s.sw_purchase)
        fb=QPushButton("전체수집"); fb.setFixedHeight(32); fb.setStyleSheet(S_BTN); fb.clicked.connect(s._ord_fetch)
        dr.addWidget(fb)
        fs=QPushButton("개별수집"); fs.setFixedHeight(32); fs.setStyleSheet(S_BTN2); fs.clicked.connect(s._ord_fetch_sel)
        dr.addWidget(fs)
        xl=QPushButton("엑셀"); xl.setFixedHeight(32); xl.setStyleSheet(S_BTN_OK); xl.clicked.connect(s._ord_excel)
        dr.addWidget(xl)
        hl.addLayout(dr); ly.addWidget(hdr)

        s.o_prog=QProgressBar(); s.o_prog.setFixedHeight(22); s.o_prog.setValue(0); s.o_prog.setFormat("대기 중"); s.o_prog.setStyleSheet(S_PROG)
        pf=QFrame(); pf.setStyleSheet(f"background:{WHITE}"); pfl=QVBoxLayout(pf); pfl.setContentsMargins(28,6,28,6); pfl.addWidget(s.o_prog)
        ly.addWidget(pf)

        s.o_tabs=QTabWidget(); s.o_tabs.setStyleSheet(S_TAB)
        s.otbls={}
        cols=["","주문일시","마켓","아이디","택배사","송장번호","주문번호","판매자상품코드","상품명","옵션","수량","수령인","연락처","주소","배송메모","결제금액","정산금액","구매처","구매가","마진","마진률","CS 메모"]
        for nm in OSTATUS:
            t=QTableWidget(); t.setColumnCount(len(cols))
            _hdr=CheckBoxHeader(t); t.setHorizontalHeader(_hdr)
            t.setHorizontalHeaderLabels(cols); t.setStyleSheet(S_TBL)
            t.verticalHeader().setVisible(False); _hdr.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            _hdr.setStretchLastSection(True)
            t.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked|QAbstractItemView.EditTrigger.AnyKeyPressed)
            t.setColumnWidth(0,60); t.setColumnWidth(4,180); t.setColumnWidth(5,140); t.setColumnWidth(7,140)
            t.verticalHeader().setDefaultSectionSize(40)
            t._all_checked=True
            t._sort_state={}  # {col: 'asc'|'desc'}
            _hdr.toggled.connect(lambda checked,tbl=t:s._toggle_all_v(tbl,checked))
            # 주문일시(1), 아이디(3) 클릭 시 정렬
            def _mk_sort(name):
                def _h(idx):
                    if idx not in (1,3): return
                    s._sort_order(name, idx)
                return _h
            _hdr.sortClicked.connect(_mk_sort(nm))
            # 더블클릭 → 주문 상세
            def _mk_dblclick(name):
                def handler(idx):
                    c=idx.column()
                    if c not in (1,2,3,6,8,9,10,15,16): return  # 주문일시/마켓/아이디/주문번호/상품명/옵션/수량/결제금액/정산금액만 상세팝업
                    s._order_detail(name,idx.row())
                return handler
            t.doubleClicked.connect(_mk_dblclick(nm))
            t.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            t.installEventFilter(s)
            s.otbls[nm]=t; s.o_tabs.addTab(t,nm)
        # 구매처(21) 기본 숨김
        for t in s.otbls.values(): t.setColumnHidden(17,True)
        ly.addWidget(s.o_tabs)

        # 송장등록 바
        s.inv_bar=QFrame(); s.inv_bar.setFixedHeight(52)
        s.inv_bar.setStyleSheet(f"background:{WHITE};border-top:1px solid {BD}")
        ib=QHBoxLayout(s.inv_bar); ib.setContentsMargins(20,0,20,0); ib.setSpacing(10)
        ib.addWidget(QLabel("택배사:",styleSheet=f"font-weight:600;color:{FG};font-size:13px"))
        # 택배사 콤보 - 기존 마이샵 courier_map에서 이름 가져옴
        s.o_courier=QComboBox(); s.o_courier.setEditable(True)
        s.o_courier.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        _cm=load_cmap()
        _cnames=courier_names(_cm) if _cm else COURIER_LIST
        s.o_courier.addItems(_cnames); s.o_courier.setCurrentIndex(-1)
        s.o_courier.lineEdit().setPlaceholderText("검색...")
        _comp=QCompleter(_cnames); _comp.setFilterMode(Qt.MatchFlag.MatchContains); _comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        s.o_courier.setCompleter(_comp)
        s.o_courier.setFixedHeight(36); s.o_courier.setFixedWidth(200)
        s.o_courier.setStyleSheet(S_INP+f"QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:center right;width:28px;border:none;border-left:1px solid {BD}}}QComboBox::down-arrow{{image:url({_ARROW});width:12px;height:12px}}")
        ib.addWidget(s.o_courier)
        ib.addWidget(QLabel("체크된 주문에 송장번호를 등록합니다.",styleSheet=f"color:{FG2};font-size:12px"))
        ib.addStretch()
        bulk_btn=QPushButton("송장 일괄입력"); bulk_btn.setFixedHeight(38); bulk_btn.setFixedWidth(120)
        bulk_btn.setStyleSheet(S_BTN); bulk_btn.clicked.connect(s._bulk_invoice_dlg)
        ib.addWidget(bulk_btn)
        s.inv_reg_btn=QPushButton("선택물품배송"); s.inv_reg_btn.setFixedHeight(38); s.inv_reg_btn.setFixedWidth(140)
        s.inv_reg_btn.setStyleSheet(S_BTN_WARN); s.inv_reg_btn.clicked.connect(s._register_invoices)
        ib.addWidget(s.inv_reg_btn)
        ly.addWidget(s.inv_bar)
        s.inv_bar.setVisible(False)
        s.o_tabs.currentChanged.connect(s._on_order_tab)
        return pg

    def _on_order_tab(s,idx):
        nm=list(OSTATUS)[idx]
        if nm in ("발송대기","배송지시","배송중"):
            s.inv_bar.setVisible(True)
            s.inv_reg_btn.setText("선택물품배송" if nm=="발송대기" else "선택송장수정")
        else:
            s.inv_bar.setVisible(False)

    def _toggle_col(s,col,show):
        for t in s.otbls.values(): t.setColumnHidden(col,not show)

    def _order_detail(s,status,row):
        """주문 상세 팝업"""
        data=s.order_data.get(status,[])
        if row>=len(data): return
        d=data[row]; items=d.get("orderItems",[])
        rcv=d.get("receiver",{})
        tot=int(d.get("totalPrice") or 0) or sum(i.get("orderPrice",0) for i in items)
        is_nav=d.get("market")=="naver"
        stl=int(d.get("settlementPrice") or 0) if is_nav else int(tot*0.8845)
        rate=round((tot-stl)/tot*100,2) if tot>0 else 0

        dlg=ModalDlg(s); dlg.setWindowTitle(f"주문 상세 — {d.get('orderId','')}")
        dlg.setFixedSize(640,560); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG};font-size:13px}}")
        ly=QVBoxLayout(dlg); ly.setContentsMargins(24,20,24,20); ly.setSpacing(12)
        ly.addWidget(QLabel("주문 상세",styleSheet=f"font-size:18px;font-weight:700;color:{FG}"))

        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(S_SCROLL)
        inner=QWidget(); il=QVBoxLayout(inner); il.setSpacing(10)

        def _sec(title,rows):
            f=QFrame(); f.setStyleSheet(f"background:#F9FAFB;border:1px solid {BD};border-radius:8px")
            fl=QVBoxLayout(f); fl.setContentsMargins(16,10,16,10); fl.setSpacing(6)
            fl.addWidget(QLabel(title,styleSheet=f"font-weight:600;font-size:13px;color:{ACCENT}"))
            for k,v in rows:
                r=QHBoxLayout()
                kl=QLabel(k); kl.setFixedWidth(100); kl.setStyleSheet(f"color:{FG2};font-size:12px")
                vl=QLabel(str(v or "")); vl.setStyleSheet(f"color:{FG};font-size:13px;font-weight:600")
                vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                r.addWidget(kl); r.addWidget(vl,1); fl.addLayout(r)
            il.addWidget(f)

        pn=items[0].get("vendorItemPackageName","") if items else ""
        _sec("주문 정보",[
            ("주문번호",d.get("orderId","")),("주문일시",(d.get("orderedAt","") or "").replace("T"," ")[:19]),
            ("마켓","네이버" if is_nav else "쿠팡"),("아이디",d.get("linked_username","")),
            ("주문자",d.get("memberName","")),("주문자연락처",d.get("memberPhoneNumber","")),
        ])
        _sec("수령인 정보",[
            ("수령인",rcv.get("name","")),("연락처",rcv.get("safeNumber","")),
            ("주소",f"{rcv.get('addr1','')} {rcv.get('addr2','')}".strip()),
            ("배송메모",d.get("deliveryMemo","") or d.get("parcelPrintMessage","")),
        ])
        _sec("금액 정보",[
            ("결제금액",f"{tot:,}원"),("정산금액{'(추정)' if not is_nav else ''}",f"{stl:,}원"),
            ("수수료율",f"{rate}%"),
        ])
        if items:
            prod_rows=[]
            for i,item in enumerate(items):
                prod_rows.append((f"상품{i+1}",item.get("vendorItemPackageName","")))
                sc2=item.get("sellerProductCode","")
                if sc2: prod_rows.append(("품번",sc2))
            _sec("상품 정보",prod_rows)

        il.addStretch(); sc.setWidget(inner); ly.addWidget(sc)
        # 하단 버튼
        br=QHBoxLayout()
        cs_btn=QPushButton("CS 메모"); cs_btn.setFixedHeight(36); cs_btn.setStyleSheet(S_BTN)
        cs_btn.clicked.connect(lambda:s._cs_memo_dlg(str(d.get("orderId",""))))
        br.addWidget(cs_btn); br.addStretch()
        close=QPushButton("닫기"); close.setFixedHeight(36); close.setStyleSheet(S_BTN2)
        close.clicked.connect(dlg.reject)
        br.addWidget(close)
        ly.addLayout(br)
        dlg.exec()

    def _cs_memo_dlg(s,oid):
        """CS 메모 팝업"""
        dlg=ModalDlg(s); dlg.setWindowTitle(f"CS 메모 — {oid}")
        dlg.setFixedSize(460,340); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(12)
        dl.addWidget(QLabel(f"주문번호: {oid}",styleSheet=f"font-weight:600;font-size:14px;color:{FG}"))
        te=QTextEdit()
        te.setStyleSheet(f"border:1px solid {BD};border-radius:8px;padding:10px;font-size:13px;color:{FG}")
        memos=load_memos()
        if oid in memos: te.setText(memos[oid].get("memo",""))
        dl.addWidget(te)
        br=QHBoxLayout()
        sv=QPushButton("저장"); sv.setFixedHeight(36); sv.setStyleSheet(S_BTN)
        def _save():
            save_memo(oid,te.toPlainText())
            if hasattr(s,"memo_tbl"): s._refresh_memo_tbl(s.memo_search.text() if hasattr(s,"memo_search") else "")
            QMessageBox.information(dlg,"저장","CS 메모 저장 완료.")
            dlg.accept()
        sv.clicked.connect(_save)
        cn=QPushButton("닫기"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        br.addWidget(sv); br.addStretch(); br.addWidget(cn)
        dl.addLayout(br)
        dlg.exec()

    def _bulk_invoice_dlg(s):
        """체크된 주문에 송장번호 일괄 입력"""
        idx=s.o_tabs.currentIndex(); nm=list(OSTATUS)[idx]
        t=s.otbls[nm]
        # 체크된 행 수집
        checked_rows=[]
        for r in range(t.rowCount()):
            w=t.cellWidget(r,0)
            cb=w if isinstance(w,CheckBox) else (w.findChild(CheckBox) if w else None)
            if cb and cb.isChecked():
                oid_it=t.item(r,6)
                rcv_it=t.item(r,11)
                checked_rows.append((r, oid_it.text() if oid_it else "", rcv_it.text() if rcv_it else ""))
        if not checked_rows:
            QMessageBox.warning(s,"알림","체크된 주문이 없습니다."); return

        dlg=ModalDlg(s); dlg.setWindowTitle(f"송장번호 일괄입력 ({len(checked_rows)}건)")
        dlg.setFixedSize(600,500); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(10)
        dl.addWidget(QLabel(f"체크된 주문 {len(checked_rows)}건",styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        dl.addWidget(QLabel("아래 텍스트 영역에 송장번호를 한 줄에 하나씩 입력하세요.\n순서대로 매칭됩니다.",styleSheet=f"color:{FG2};font-size:12px"))

        # 체크된 주문 미리보기
        info_lbl=QLabel("\n".join([f"{i+1}. {oid} - {rcv}" for i,(_,oid,rcv) in enumerate(checked_rows)]))
        info_lbl.setStyleSheet(f"background:#F9FAFB;border:1px solid {BD};border-radius:6px;padding:10px;font-size:12px;color:{FG}")
        info_lbl.setWordWrap(True)
        sa=QScrollArea(); sa.setWidget(info_lbl); sa.setWidgetResizable(True); sa.setMaximumHeight(120); sa.setStyleSheet(S_SCROLL)
        dl.addWidget(sa)

        dl.addWidget(QLabel("송장번호 (한 줄에 하나씩):",styleSheet=f"font-weight:600;color:{FG};font-size:13px"))
        te=QTextEdit()
        te.setStyleSheet(f"border:1px solid {BD};border-radius:8px;padding:10px;font-size:14px;color:{FG};font-family:monospace")
        te.setPlaceholderText("9999999999\n8888888888\n...")
        dl.addWidget(te,1)

        br=QHBoxLayout()
        ok=QPushButton("적용"); ok.setFixedHeight(40); ok.setStyleSheet(S_BTN)
        cn=QPushButton("취소"); cn.setFixedHeight(40); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        def _apply():
            lines=[ln.strip() for ln in te.toPlainText().splitlines() if ln.strip()]
            if len(lines)!=len(checked_rows):
                if QMessageBox.question(dlg,"확인",f"송장번호 {len(lines)}개, 주문 {len(checked_rows)}건.\n계속 진행하시겠습니까?\n(앞에서부터 매칭)")!=QMessageBox.StandardButton.Yes:
                    return
            for i,(row,_,_) in enumerate(checked_rows):
                if i>=len(lines): break
                inv_item=t.item(row,5)
                if inv_item: inv_item.setText(lines[i])
            dlg.accept()
            QMessageBox.information(s,"완료",f"{min(len(lines),len(checked_rows))}건 송장번호 입력 완료")
        ok.clicked.connect(_apply)
        br.addStretch(); br.addWidget(cn); br.addWidget(ok)
        dl.addLayout(br)
        dlg.exec()

    def _register_invoices(s):
        """체크된 주문의 송장번호를 Wing에 등록"""
        idx=s.o_tabs.currentIndex(); nm=list(OSTATUS)[idx]
        t=s.otbls[nm]; data=s.order_data.get(nm,[])
        courier_text=s.o_courier.currentText().strip()
        cm=load_cmap()
        orders=[]
        for r in range(t.rowCount()):
            w=t.cellWidget(r,0)
            if not w: continue
            cb=w if isinstance(w,CheckBox) else w.findChild(CheckBox)
            if not cb or not cb.isChecked(): continue
            inv_item=t.item(r,5)  # 송장번호
            if not inv_item or not inv_item.text().strip(): continue
            # 택배사: 셀 콤보박스 우선, 없으면 하단 콤보값
            cr_w=t.cellWidget(r,4)  # 택배사 콤보박스
            row_courier=(cr_w.currentText().strip() if cr_w and hasattr(cr_w,'currentText') else "") or courier_text
            if not row_courier: continue
            courier_code=cm.get(row_courier,"")
            if not courier_code:
                QMessageBox.warning(s,"알림",f"'{row_courier}' 택배사 코드를 찾을 수 없습니다.")
                return
            order_data=data[r] if r<len(data) else {}
            box_id=order_data.get("shipmentBoxId","")
            order_id=order_data.get("orderId","")
            product_order_no=order_data.get("productOrderNo","")
            market=order_data.get("market","coupang")
            uid_item=t.item(r,3)  # 아이디 컬럼
            orders.append({
                "market":market,
                "shipmentBoxId":box_id,
                "orderId":order_id,
                "productOrderNo":product_order_no,
                "invoiceNumber":inv_item.text().strip(),
                "courierCode":courier_code,
                "courierName":row_courier,
                "deliveryCompanyCode":courier_code,
                "username":uid_item.text() if uid_item else "",
            })
        if not orders:
            QMessageBox.warning(s,"알림","송장번호가 입력된 주문을 선택해주세요.")
            return
        if QMessageBox.question(s,"송장 등록",f"총 {len(orders)}건 등록하시겠습니까?")!=QMessageBox.StandardButton.Yes:
            return
        # 마켓별 + 계정별 그룹핑
        ok_cnt=fail_cnt=0; errs=[]
        pws=load_pw()
        navs=load_nav()
        cpg_orders=[o for o in orders if o["market"]!="naver"]
        by_user={}
        for o in cpg_orders: by_user.setdefault(o["username"],[]).append(o)
        for uid,uorders in by_user.items():
            pw=pws.get(uid,"")
            res=register_invoices_on_wing(uid,pw,uorders)
            ok_cnt+=res.get("success",0); fail_cnt+=res.get("fail",0)
            errs.extend(res.get("errors",[]))
        nav_orders=[o for o in orders if o["market"]=="naver"]
        by_nav={}
        for o in nav_orders: by_nav.setdefault(o["username"],[]).append(o)
        for aid,uorders in by_nav.items():
            mno=next((n.get("merchant_no","") for n in navs if str(n.get("account_id"))==str(aid)), "")
            res=register_invoices_on_naver(aid, mno, uorders)
            ok_cnt+=res.get("success",0); fail_cnt+=res.get("fail",0)
            errs.extend(res.get("errors",[]))
        msg=f"성공: {ok_cnt}건  |  실패: {fail_cnt}건"
        if errs: msg+="\n\n"+"\n".join(errs[:5])
        QMessageBox.information(s,"송장 등록 결과",msg)

    def _toggle_all(s,tbl):
        checked=getattr(tbl,'_all_checked',True)
        s._toggle_all_v(tbl,not checked)
        hdr=tbl.horizontalHeader()
        if isinstance(hdr,CheckBoxHeader): hdr.setChecked(not checked)
    def _toggle_all_v(s,tbl,checked):
        for r in range(tbl.rowCount()):
            w=tbl.cellWidget(r,0)
            if isinstance(w,CheckBox): w.setChecked(checked)
            elif w:
                cb=w.findChild(CheckBox)
                if cb: cb.setChecked(checked)
        tbl._all_checked=checked

    def _mk_courier_combo(s):
        """셀용 택배사 검색 콤보박스 — 하단 검색양식과 동일 스타일"""
        cb=QComboBox(); cb.setEditable(True); cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        _cm=load_cmap()
        _cn=courier_names(_cm) if _cm else COURIER_LIST
        cb._all=_cn
        cb.addItems(_cn); cb.setCurrentIndex(-1)
        cb.lineEdit().setPlaceholderText("택배사 검색...")
        cb.setMaxVisibleItems(15)
        cp=QCompleter(_cn); cp.setFilterMode(Qt.MatchFlag.MatchContains); cp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive); cp.setMaxVisibleItems(12)
        cb.setCompleter(cp)
        cb.setStyleSheet(f"""
            QComboBox{{border:1px solid {BD};border-radius:6px;padding:0 24px 0 6px;
              font-size:12px;background:white;color:{FG};min-height:0}}
            QComboBox::drop-down{{subcontrol-origin:padding;subcontrol-position:center right;
              width:22px;border:none;border-left:1px solid {BD}}}
            QComboBox::down-arrow{{
              image:url({_ARROW});width:10px;height:10px}}
            QComboBox QAbstractItemView{{
              font-size:13px;background:white;color:{FG};
              border:1px solid {BD};min-width:200px;
              selection-background-color:#EFF6FF;selection-color:{FG}}}
            QComboBox QAbstractItemView::item{{padding:6px 10px}}
            QComboBox QLineEdit{{color:{FG};font-size:12px;padding-left:4px}}
        """)
        cb.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        return cb

    def _sort_order(s, nm, col):
        """주문 테이블 정렬: col=1(주문일시), col=3(아이디). 같은 컬럼 재클릭 시 방향 토글."""
        t = s.otbls.get(nm)
        if t is None: return
        data = s.order_data.get(nm, [])
        if not data: return
        key_fn = {
            1: lambda d: (d.get("orderedAt") or ""),
            3: lambda d: (d.get("linked_username") or ""),
        }.get(col)
        if key_fn is None: return
        # 방향 토글
        cur = t._sort_state.get(col, None)
        new_dir = "asc" if cur != "asc" else "desc"
        # 다른 컬럼 상태 초기화
        t._sort_state = {col: new_dir}
        reverse = (new_dir == "desc")
        try:
            data.sort(key=key_fn, reverse=reverse)
        except Exception as e:
            print(f"정렬 오류: {e}"); return
        s.order_data[nm] = data
        s._fill_order(nm, data)

    def _fill_order(s,nm,data):
        t=s.otbls[nm]; t.setRowCount(0)
        cmap=load_codemap()
        memos=load_memos()
        for ri,d in enumerate(data):
            t.insertRow(ri)
            chk_box=CheckBox(True)
            t.setCellWidget(ri,0,chk_box)
            bg=s.color_map.get(d.get("linked_username",""),"#fff")
            # 데이터
            items=d.get("orderItems",[])
            pn=items[0].get("vendorItemPackageName","") if items else ""
            if len(items)>1: pn+=f" 외 {len(items)-1}건"
            tot=int(d.get("totalPrice") or 0) or sum(i.get("orderPrice",0) for i in items)
            stl=int(d.get("settlementPrice") or 0) if d.get("market")=="naver" else int(tot*0.8845)
            opt=d.get("productOptionContents","")
            if not opt:
                pp=pn.split(", ",1); opt=pp[1] if len(pp)>1 else ""
            qty=str(items[0].get("orderQuantity",1)) if items else "1"
            rcv=d.get("receiver",{})
            oid=str(d.get("orderId",""))
            vid=str(items[0].get("vendorItemId","")) if items else ""
            scode=items[0].get("sellerProductCode","") if items else ""
            if not scode and vid: scode=cmap.get(vid,"")
            memo_data=memos.get(oid,{})
            cost=memo_data.get("cost","")
            cs_memo=memo_data.get("memo","")
            try: cost_num=int(str(cost).replace(",","").replace("원","")) if cost else 0
            except: cost_num=0
            margin=stl-cost_num if cost else 0
            margin_rate=f"{margin/tot*100:.1f}%" if tot>0 and cost else "0%"

            def _v(val):
                if val is None: return ""
                s2=str(val).strip()
                if s2 in ("None","null"): return ""
                return s2

            vals=[
                _v(d.get("orderedAt","")).replace("T"," ")[:19],
                "네이버" if d.get("market")=="naver" else "쿠팡",
                _v(d.get("linked_username","")),
                None,  # 택배사 → 콤보박스로 대체
                _v(d.get("invoiceNumber","")),
                _v(oid), _v(scode), _v(pn), _v(opt), _v(qty),
                _v(rcv.get("name","")), _v(rcv.get("safeNumber","")),
                f"{_v(rcv.get('addr1',''))} {_v(rcv.get('addr2',''))}".strip(),
                _v(d.get("deliveryMemo","") or d.get("parcelPrintMessage","")),
                f"{tot:,}", f"{stl:,}",
                _v(memo_data.get("purchase","")),  # 구매처
                _v(cost), f"{margin:,}" if cost else "",
                margin_rate if cost else "",
                _v(cs_memo),
            ]
            for ci,v in enumerate(vals):
                col=ci+1  # +1 체크박스 오프셋
                if ci==3:  # 택배사 → 콤보박스
                    combo=s._mk_courier_combo()
                    dn=str(d.get("deliverName","") or "").strip()
                    if dn and dn not in ("None","null",""):
                        idx_c=combo.findText(str(dn),Qt.MatchFlag.MatchContains)
                        if idx_c>=0: combo.setCurrentIndex(idx_c)
                        else: combo.lineEdit().setText(str(dn))
                    t.setCellWidget(ri,col,combo)
                else:
                    it=QTableWidgetItem(v if v else ""); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); it.setBackground(QColor(bg))
                    # 송장번호(5), 구매처(17), CS메모(21)만 편집 가능
                    if col in (1,2,3,6,8,9,10,15,16):
                        it.setFlags(it.flags()&~Qt.ItemFlag.ItemIsEditable)
                    t.setItem(ri,col,it)
        idx=list(OSTATUS).index(nm)
        s.o_tabs.setTabText(idx,f"{nm} ({len(data)})")
        t._all_checked=True
        hdr=t.horizontalHeader()
        if isinstance(hdr,CheckBoxHeader): hdr.setChecked(True)
        # 셀 편집 시 자동 저장
        def _mk_save(tbl,status):
            def handler(item):
                col=item.column(); row=item.row()
                dt=s.order_data.get(status,[])
                if row>=len(dt): return
                oid=str(dt[row].get("orderId",""))
                if col==17:  # 구매처
                    m=load_memos(); m.setdefault(oid,{})["purchase"]=item.text()
                    m[oid]["updated"]=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    jsave(dp("cs_memos.json"),m)
                elif col==18:  # 구매가 → 마진/마진률 자동 계산
                    m=load_memos(); m.setdefault(oid,{})["cost"]=item.text()
                    m[oid]["updated"]=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    jsave(dp("cs_memos.json"),m)
                    # 마진/마진률 갱신
                    tbl.blockSignals(True)
                    try:
                        cost_val=item.text().replace(",","").replace("원","").strip()
                        cost_num=int(cost_val) if cost_val else 0
                        stl_it=tbl.item(row,16)  # 정산금액
                        tot_it=tbl.item(row,15)  # 결제금액
                        stl=int(stl_it.text().replace(",","")) if stl_it else 0
                        tot=int(tot_it.text().replace(",","")) if tot_it else 0
                        margin=stl-cost_num if cost_val else 0
                        rate=f"{margin/tot*100:.1f}%" if tot>0 and cost_val else ""
                        mi=tbl.item(row,19)  # 마진
                        ri=tbl.item(row,20)  # 마진률
                        if mi: mi.setText(f"{margin:,}" if cost_val else "")
                        if ri: ri.setText(rate)
                    except: pass
                    tbl.blockSignals(False)
                elif col==21:  # CS메모
                    save_memo(oid,item.text())
                    if hasattr(s,"memo_tbl"): s._refresh_memo_tbl(s.memo_search.text() if hasattr(s,"memo_search") else "")
            return handler
        try: t.itemChanged.disconnect()
        except: pass
        t.itemChanged.connect(_mk_save(t,nm))

    def _ord_fetch(s, accs=None):
        if accs is None: accs=s._get_all_accs()
        if not accs: return
        pws=load_pw(); sd=s.o_s.date().toString("yyyy-MM-dd"); ed=s.o_e.date().toString("yyyy-MM-dd")
        s.o_prog.setValue(0); s.o_prog.setFormat("수집 시작...")
        s._ow=CollectWorker(accs,pws,sd,ed)
        s._ow.prog.connect(lambda p,m:(s.o_prog.setValue(p),s.o_prog.setFormat(m)))
        def done(r):
            for nm,items in r["data"].items():
                s.order_data[nm]=items
                if nm in s.otbls: s._fill_order(nm,items)
            s.o_prog.setValue(100); s.o_prog.setFormat("완료!")
        s._ow.done.connect(done); s._ow.start()

    def _ord_fetch_sel(s):
        accs=s._pick_accs()
        if accs: s._ord_fetch(accs)

    def _ord_excel(s):
        idx=s.o_tabs.currentIndex(); nm=list(OSTATUS)[idx]
        data=s.order_data.get(nm,[])
        if not data: QMessageBox.warning(s,"알림","데이터 없음"); return
        # 양식 선택
        tmpls=load_tmpls()
        if len(tmpls)>1:
            names=[t["name"] for t in tmpls]
            chosen,ok=QInputDialog.getItem(s,"엑셀 양식","양식 선택:",names,0,False)
            if not ok: return
            tmpl=next(t for t in tmpls if t["name"]==chosen)
        else:
            tmpl=tmpls[0]
        now=datetime.datetime.now().strftime("%Y%m%d_%H%M")
        p,_=QFileDialog.getSaveFileName(s,"저장",os.path.join(os.path.expanduser("~"),"Desktop",f"{nm}_{now}.xlsx"),"Excel (*.xlsx)")
        if not p: return
        wb=openpyxl.Workbook(); ws=wb.active
        mapping=tmpl["mapping"]
        # 헤더
        ws.append([m["header"] for m in mapping])
        # 데이터
        memos=load_memos(); cmap=load_codemap()
        for d in data:
            items=d.get("orderItems",[])
            rcv=d.get("receiver",{})
            tot=int(d.get("totalPrice") or 0) or sum(i.get("orderPrice",0) for i in items)
            is_nav=d.get("market")=="naver"
            stl=int(d.get("settlementPrice") or 0) if is_nav else int(tot*0.8845)
            pn=items[0].get("vendorItemPackageName","") if items else ""
            opt=d.get("productOptionContents","")
            if not opt:
                pp=pn.split(", ",1); opt=pp[1] if len(pp)>1 else ""
            vid=str(items[0].get("vendorItemId","")) if items else ""
            scode=items[0].get("sellerProductCode","") if items else ""
            if not scode and vid: scode=cmap.get(vid,"")
            oid=str(d.get("orderId",""))
            vars_map={
                "주문일시":(d.get("orderedAt","") or "").replace("T"," ")[:19],
                "마켓":"네이버" if is_nav else "쿠팡",
                "아이디":d.get("linked_username",""),
                "주문번호":oid,"판매자상품코드":scode,"상품명":pn,"옵션":opt,
                "수량":str(items[0].get("orderQuantity",1)) if items else "1",
                "수령인":rcv.get("name",""),"연락처":rcv.get("safeNumber",""),
                "주소":f"{rcv.get('addr1','')} {rcv.get('addr2','')}".strip(),
                "구매처":memos.get(oid,{}).get("purchase",""),
                "배송메모":d.get("deliveryMemo","") or d.get("parcelPrintMessage",""),
                "결제금액":tot,"정산금액":stl,
                "택배사":str(d.get("deliverName","") or "").replace("None",""),"송장번호":str(d.get("invoiceNumber","") or "").replace("None",""),
                "상품번호":vid,"구매자번호":d.get("memberPhoneNumber","") or "",
                "우편번호":d.get("receiver",{}).get("postCode","") or d.get("receiver",{}).get("zipCode","") or "",
            }
            row=[]
            for m in mapping:
                formula=m.get("formula","")
                if not formula: row.append(""); continue
                val=formula
                for k,v in vars_map.items():
                    val=val.replace("{"+k+"}",str(v) if v else "")
                # 숫자 변환 시도
                try: val=int(val)
                except:
                    try: val=float(val)
                    except: pass
                row.append(val)
            ws.append(row)
        wb.save(p)
        reply=QMessageBox.question(s,"완료","저장 완료! 파일 열까요?")
        if reply==QMessageBox.StandardButton.Yes:
            import subprocess
            if s._is_mac: subprocess.Popen(["open",p])
            else: os.startfile(p)

    # ═══════════════════════════════════════════
    # 반품/교환
    # ═══════════════════════════════════════════
    def _mk_returns(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr,hl=s._hdr("반품/교환","취소 · 반품 · 교환 조회")
        dr=s._date_row("r"); dr.addStretch()
        fb=QPushButton("전체수집"); fb.setFixedHeight(32); fb.setStyleSheet(S_BTN_ERR); fb.clicked.connect(s._ret_fetch)
        dr.addWidget(fb)
        fs=QPushButton("개별수집"); fs.setFixedHeight(32); fs.setStyleSheet(S_BTN2); fs.clicked.connect(s._ret_fetch_sel)
        dr.addWidget(fs)
        hl.addLayout(dr); ly.addWidget(hdr)

        s.r_prog=QProgressBar(); s.r_prog.setFixedHeight(22); s.r_prog.setValue(0); s.r_prog.setFormat("대기 중"); s.r_prog.setStyleSheet(S_PROG)
        pf=QFrame(); pf.setStyleSheet(f"background:{WHITE}"); pfl=QVBoxLayout(pf); pfl.setContentsMargins(28,6,28,6); pfl.addWidget(s.r_prog)
        ly.addWidget(pf)

        s.r_tabs=QTabWidget(); s.r_tabs.setStyleSheet(S_TAB)
        s.rtbls={}
        cols=["주문일시","마켓","아이디","주문번호","상품명","수량","수령인","사유","금액","상태"]
        for nm in CSTATUS:
            t=QTableWidget(); t.setColumnCount(len(cols)); t.setHorizontalHeaderLabels(cols); t.setStyleSheet(S_TBL)
            t.verticalHeader().setVisible(False); t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            t.horizontalHeader().setStretchLastSection(True); t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            s.rtbls[nm]=t; s.r_tabs.addTab(t,nm)
        ly.addWidget(s.r_tabs)
        return pg

    def _fill_return(s,nm,data):
        t=s.rtbls[nm]; t.setRowCount(0)
        for ri,d in enumerate(data):
            t.insertRow(ri)
            items=d.get("orderItems",[]) or d.get("returnItems",[]) or []
            pn=items[0].get("vendorItemPackageName","") if items else ""
            qty=str(items[0].get("orderQuantity",1)) if items else "1"
            amt=int(d.get("amount",0)); st=d.get("refundStatus","") or d.get("deliveryStatusCode","") or d.get("shipmentStopStatus","")
            rcv=d.get("receiver",{})
            vals=[d.get("orderedAt","")[:19],"네이버" if d.get("market")=="naver" else "쿠팡",d.get("linked_username",""),str(d.get("orderId","")),pn,qty,rcv.get("name",""),d.get("returnReason",""),f"{amt:,}" if amt else "",st]
            for ci,v in enumerate(vals):
                it=QTableWidgetItem(str(v)); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(ri,ci,it)
        idx=list(CSTATUS).index(nm); s.r_tabs.setTabText(idx,f"{nm} ({len(data)})")

    def _ret_fetch(s, accs=None):
        if accs is None: accs=s._get_all_accs()
        if not accs: return
        pws=load_pw(); sd=s.r_s.date().toString("yyyy-MM-dd"); ed=s.r_e.date().toString("yyyy-MM-dd")
        s.r_prog.setValue(0)
        s._rw2=CollectWorker(accs,pws,sd,ed)
        s._rw2.prog.connect(lambda p,m:(s.r_prog.setValue(p),s.r_prog.setFormat(m)))
        def done(r):
            for nm,items in r["data"].items():
                if nm in s.rtbls: s._fill_return(nm,items)
            s.r_prog.setValue(100); s.r_prog.setFormat("완료!")
        s._rw2.done.connect(done); s._rw2.start()

    def _ret_fetch_sel(s):
        accs=s._pick_accs()
        if accs: s._ret_fetch(accs)

    # ═══════════════════════════════════════════
    # 마켓연동
    # ═══════════════════════════════════════════
    def _mk_market(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr,hl=s._hdr("마켓 연동","쇼핑몰 계정 관리")
        ac=QPushButton("쿠팡 연동 추가"); ac.setFixedHeight(36); ac.setMinimumWidth(140); ac.setStyleSheet(S_BTN); ac.clicked.connect(s._add_cpg); hl.itemAt(0).layout().addWidget(ac)
        an=QPushButton("네이버 연동 추가"); an.setFixedHeight(36); an.setMinimumWidth(160); an.setStyleSheet(S_BTN_OK); an.clicked.connect(s._add_nav); hl.itemAt(0).layout().addWidget(an)
        ly.addWidget(hdr)
        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(S_SCROLL)
        inner=QWidget(); inner.setStyleSheet(f"background:{BG}")
        s.mkt_ly=QVBoxLayout(inner); s.mkt_ly.setContentsMargins(28,20,28,20); s.mkt_ly.setSpacing(12); s.mkt_ly.addStretch()
        sc.setWidget(inner); ly.addWidget(sc)
        s._refresh_mkt()
        return pg

    def _refresh_mkt(s):
        while s.mkt_ly.count()>1:
            it=s.mkt_ly.takeAt(0)
            if it and it.widget(): it.widget().deleteLater()
        saved=load_saved(); nav=load_nav()
        for a in saved:
            uid=a["username"]; has=bool(load_cookies(uid))
            c=s._mkt_card(f"쿠팡 | {uid}","C",FG,has,market="cpg",uid=uid)
            s.mkt_ly.insertWidget(s.mkt_ly.count()-1,c)
        for n in nav:
            aid=n.get("account_id",""); has=bool(load_naver_cookies(aid))
            c=s._mkt_card(f"네이버 | {aid}","N",GREEN,has,market="nav",uid=aid)
            s.mkt_ly.insertWidget(s.mkt_ly.count()-1,c)
        if not saved and not nav:
            s.mkt_ly.insertWidget(0,QLabel("연동된 계정이 없습니다.",styleSheet=f"color:{FG2};font-size:14px",alignment=Qt.AlignmentFlag.AlignCenter))
        # 대시보드 연동현황도 갱신
        if hasattr(s,"conn_ly"): s._refresh_conn()

    def _mkt_card(s,title,icon,ic,ok,market="",uid=""):
        f=QFrame(); f.setMinimumHeight(72)
        bc=GREEN if ok else BD
        f.setStyleSheet(f"QFrame{{background:{WHITE};border:1px solid {BD};border-left:4px solid {bc};border-radius:10px}}QPushButton{{border:none}}")
        hl=QHBoxLayout(f); hl.setContentsMargins(20,10,16,10); hl.setSpacing(14)
        hl.addWidget(QLabel(icon,styleSheet=f"font-size:20px;font-weight:700;color:{ic};background:transparent;border:none"))
        vl=QVBoxLayout(); vl.setSpacing(2)
        vl.addWidget(QLabel(title,styleSheet=f"font-weight:600;font-size:13px;color:{FG};background:transparent;border:none"))
        vl.addWidget(QLabel("연동됨" if ok else "해제됨",styleSheet=f"font-size:12px;color:{GREEN if ok else FG3};background:transparent;border:none"))
        hl.addLayout(vl,1)
        # 액션 버튼
        if market and uid:
            btn_relink=QPushButton("재연동")
            btn_relink.setFixedHeight(30); btn_relink.setMinimumWidth(72)
            btn_relink.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_relink.setStyleSheet(f"QPushButton{{background:{WHITE};color:{FG};border:1px solid {BD};border-radius:6px;font-size:12px;font-weight:600;padding:0 10px}}QPushButton:hover{{background:#F9FAFB;border-color:#9CA3AF}}")
            btn_relink.clicked.connect(lambda _,m=market,u=uid: s._relink_one(m,u))
            hl.addWidget(btn_relink)

            btn_del=QPushButton("연동삭제")
            btn_del.setFixedHeight(30); btn_del.setMinimumWidth(76)
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setStyleSheet(f"QPushButton{{background:{WHITE};color:{RED};border:1px solid #FCA5A5;border-radius:6px;font-size:12px;font-weight:600;padding:0 10px}}QPushButton:hover{{background:#FEF2F2;border-color:{RED}}}")
            btn_del.clicked.connect(lambda _,m=market,u=uid: s._del_acc(m,u))
            hl.addWidget(btn_del)
        return f

    def _relink_one(s, market, uid):
        """단일 계정 재연동"""
        if market == "cpg":
            saved_pw = load_pw().get(uid, "")
            # 비번 입력 모달
            pdlg=ModalDlg(s); pdlg.setWindowTitle("쿠팡 재연동")
            pdlg.setFixedWidth(380)
            pdlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
            pv=QVBoxLayout(pdlg); pv.setContentsMargins(28,22,28,20); pv.setSpacing(10)
            pv.addWidget(QLabel("쿠팡 재연동",styleSheet=f"font-size:16px;font-weight:700;color:{FG};background:transparent"))
            pv.addWidget(QLabel(f"계정: {uid}",styleSheet=f"font-size:12px;color:{FG2};background:transparent"))
            pi=QLineEdit(); pi.setPlaceholderText("비밀번호"); pi.setEchoMode(QLineEdit.EchoMode.Password)
            pi.setFixedHeight(40); pi.setStyleSheet(S_INP)
            if saved_pw: pi.setText(saved_pw)
            pv.addWidget(pi)
            err=QLabel(""); err.setStyleSheet(f"font-size:11px;color:{RED};background:transparent"); pv.addWidget(err)
            br=QHBoxLayout(); br.setSpacing(8)
            cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok=QPushButton("연동"); ok.setFixedHeight(36); ok.setStyleSheet(S_BTN); ok.setCursor(Qt.CursorShape.PointingHandCursor)
            cn.clicked.connect(pdlg.reject)
            def _do():
                pwv=pi.text()
                if not pwv: err.setText("비밀번호 입력"); return
                ok.setEnabled(False); err.setText("로그인 중..."); err.setStyleSheet(f"font-size:11px;color:{FG2};background:transparent")
                wkr=LoginWorker(uid, pwv)
                def d(r):
                    if r.get("success"):
                        save_account(uid); save_pw(uid, pwv); save_ip(get_public_ip())
                        pdlg.accept(); s._refresh_mkt()
                        QMessageBox.information(s,"완료","재연동 완료!")
                    else:
                        err.setText(r.get("message","실패"))
                        err.setStyleSheet(f"font-size:11px;color:{RED};background:transparent")
                        ok.setEnabled(True)
                wkr.done.connect(d)
                if not hasattr(s,'_relink_one_ws'): s._relink_one_ws=[]
                s._relink_one_ws.append(wkr); wkr.start()
            ok.clicked.connect(_do); pi.returnPressed.connect(_do)
            br.addStretch(); br.addWidget(cn); br.addWidget(ok)
            pv.addLayout(br)
            pi.setFocus(); pdlg.exec()
        else:
            # Naver: 저장된 ID/PW + 저장된 로그인 방식으로 자동 로그인
            saved_pw = load_nav_pw().get(uid, "")
            saved_ltype = next((a.get("login_type","seller") for a in load_nav() if str(a.get("account_id"))==str(uid)),"seller")
            class NW(QThread):
                done=pyqtSignal(object)
                def run(w):
                    try: w.done.emit(do_naver_login(uid, naver_id=uid, naver_pw=saved_pw, login_type=saved_ltype))
                    except Exception as e: print(f"네이버 로그인 에러: {e}"); w.done.emit(None)
            wkr=NW()
            def d(r):
                if r and isinstance(r,dict) and r.get("success") is not False and r.get("account_id"):
                    save_nav(r.get("account_id",uid), mno=r.get("merchant_no",""), store="스마트스토어")
                    QMessageBox.information(s,"완료","네이버 재연동 완료!"); s._refresh_mkt()
                else:
                    msg = r.get("message","로그인 실패") if isinstance(r,dict) else "로그인 실패"
                    QMessageBox.warning(s,"실패",msg)
            wkr.done.connect(d)
            if not hasattr(s,'_relink_one_ws'): s._relink_one_ws=[]
            s._relink_one_ws.append(wkr); wkr.start()

    def _del_acc(s, market, uid):
        """단일 계정 연동삭제 (확인 모달)"""
        cdlg=ModalDlg(s); cdlg.setWindowTitle("연동 삭제 확인")
        cdlg.setFixedWidth(380)
        cdlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        cv=QVBoxLayout(cdlg); cv.setContentsMargins(28,22,28,20); cv.setSpacing(10)
        cv.addWidget(QLabel("연동을 삭제하시겠습니까?",styleSheet=f"font-size:16px;font-weight:700;color:{FG};background:transparent"))
        mname = "쿠팡" if market=="cpg" else "네이버"
        cv.addWidget(QLabel(f"{mname}: {uid}",styleSheet=f"font-size:13px;color:{FG2};background:transparent"))
        cv.addWidget(QLabel("저장된 쿠키와 계정 정보가 삭제됩니다.",styleSheet=f"font-size:11px;color:{FG3};background:transparent"))
        br=QHBoxLayout(); br.setSpacing(8)
        cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.setCursor(Qt.CursorShape.PointingHandCursor)
        ok=QPushButton("삭제"); ok.setFixedHeight(36)
        ok.setStyleSheet(f"QPushButton{{background:{RED};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:0 18px}}QPushButton:hover{{background:#B91C1C}}")
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        cn.clicked.connect(cdlg.reject); ok.clicked.connect(cdlg.accept)
        br.addStretch(); br.addWidget(cn); br.addWidget(ok)
        cv.addLayout(br)
        if cdlg.exec() != QDialog.DialogCode.Accepted: return
        if market == "cpg":
            delete_account(uid); del_saved(uid)
            # 비번도 삭제
            try:
                pwd=load_pw(); pwd.pop(uid, None); jsave(dp("wing_passwords.json"), pwd)
            except: pass
        else:
            delete_naver_cookies(uid); del_nav(uid)
        s._refresh_mkt()

    def _add_cpg(s):
        dlg=ModalDlg(s); dlg.setWindowTitle("쿠팡 연동"); dlg.setFixedSize(420,380); dlg.setStyleSheet(f"QDialog{{background:#fff}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(32,24,32,24); dl.setSpacing(12)
        dl.addWidget(QLabel("쿠팡 Wing 연동",styleSheet=f"font-size:18px;font-weight:700;color:{FG}"))
        biz=QLineEdit(); biz.setPlaceholderText("별칭"); biz.setFixedHeight(42); biz.setStyleSheet(S_INP)
        uid=QLineEdit(); uid.setPlaceholderText("아이디"); uid.setFixedHeight(42); uid.setStyleSheet(S_INP)
        pw=QLineEdit(); pw.setPlaceholderText("비밀번호"); pw.setEchoMode(QLineEdit.EchoMode.Password); pw.setFixedHeight(42); pw.setStyleSheet(S_INP)
        st=QLabel(""); st.setWordWrap(True); st.setMinimumHeight(36)
        st.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent")
        go=QPushButton("연동"); go.setFixedHeight(44); go.setStyleSheet(S_BTN)
        dl.addWidget(biz); dl.addWidget(uid); dl.addWidget(pw); dl.addWidget(st); dl.addWidget(go)
        def _show_err(msg):
            st.setText(msg)
            st.setStyleSheet(f"font-size:12px;color:{RED};background:#FEF2F2;border:1px solid #FCA5A5;border-radius:6px;padding:8px 10px")
        def _show_info(msg):
            st.setText(msg); st.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent;padding:0")
        def _run():
            if not uid.text().strip(): _show_err("아이디를 입력하세요."); return
            go.setEnabled(False); _show_info("로그인 중...")
            s._lt=LoginWorker(uid.text().strip(),pw.text())
            s._lt.sig.connect(_show_info)
            def d(r):
                if r.get("success"):
                    save_account(r["username"]); add_saved(r["username"],biz.text().strip()); save_pw(uid.text().strip(),pw.text())
                    save_ip(get_public_ip()); s._refresh_mkt(); dlg.accept()
                    QMessageBox.information(s,"성공","연동 완료!")
                else:
                    _show_err(r.get("message") or "로그인 실패"); go.setEnabled(True)
            s._lt.done.connect(d); s._lt.start()
        go.clicked.connect(_run); pw.returnPressed.connect(_run); dlg.exec()

    def _add_nav(s):
        dlg=ModalDlg(s); dlg.setWindowTitle("네이버 연동"); dlg.setFixedSize(440,480)
        dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(32,24,32,24); dl.setSpacing(12)
        dl.addWidget(QLabel("네이버 스마트스토어 연동",styleSheet=f"font-size:18px;font-weight:700;color:{FG}"))
        dl.addWidget(QLabel("로그인 방식을 선택하세요.",
                            styleSheet=f"font-size:11px;color:{FG2};background:transparent"))

        # 로그인 방식 선택 (이메일/판매자 아이디 vs 네이버 아이디)
        login_type=["seller"]  # 기본값
        tab_row=QHBoxLayout(); tab_row.setSpacing(8)
        tab_seller=QPushButton("이메일/판매자 아이디")
        tab_naver=QPushButton("네이버 아이디")
        def _restyle():
            sel_st=f"QPushButton{{background:{FG};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:12px;padding:10px 0}}"
            un_st=f"QPushButton{{background:{WHITE};color:{FG};border:1px solid {BD};border-radius:8px;font-weight:600;font-size:12px;padding:10px 0}}QPushButton:hover{{background:#F9FAFB}}"
            tab_seller.setStyleSheet(sel_st if login_type[0]=="seller" else un_st)
            tab_naver.setStyleSheet(sel_st if login_type[0]=="naver" else un_st)
        for b in (tab_seller, tab_naver): b.setFixedHeight(38); b.setCursor(Qt.CursorShape.PointingHandCursor)
        tab_seller.clicked.connect(lambda: (login_type.__setitem__(0,"seller"), _restyle()))
        tab_naver.clicked.connect(lambda: (login_type.__setitem__(0,"naver"), _restyle()))
        _restyle()
        tab_row.addWidget(tab_seller,1); tab_row.addWidget(tab_naver,1)
        dl.addLayout(tab_row)

        uid=QLineEdit(); uid.setPlaceholderText("아이디"); uid.setFixedHeight(42); uid.setStyleSheet(S_INP)
        pw=QLineEdit(); pw.setPlaceholderText("비밀번호"); pw.setEchoMode(QLineEdit.EchoMode.Password); pw.setFixedHeight(42); pw.setStyleSheet(S_INP)
        st=QLabel(""); st.setWordWrap(True); st.setMinimumHeight(36)
        st.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent")
        go=QPushButton("연동"); go.setFixedHeight(44); go.setStyleSheet(S_BTN_OK)
        dl.addWidget(uid); dl.addWidget(pw); dl.addWidget(st); dl.addWidget(go)
        def _show_err(msg):
            st.setText(msg)
            st.setStyleSheet(f"font-size:12px;color:{RED};background:#FEF2F2;border:1px solid #FCA5A5;border-radius:6px;padding:8px 10px")
        def _show_info(msg):
            st.setText(msg); st.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent;padding:0")

        def _run():
            nid=uid.text().strip(); npw=pw.text(); ltype=login_type[0]
            if not nid: _show_err("아이디를 입력하세요."); return
            go.setEnabled(False); _show_info("브라우저 열기...")
            class W(QThread):
                done=pyqtSignal(object)
                def run(w):
                    try: w.done.emit(do_naver_login(nid, naver_id=nid, naver_pw=npw, login_type=ltype))
                    except Exception as e: print(f"네이버 로그인 에러: {e}"); w.done.emit(None)
            s._nw=W()
            def d(r):
                if r and isinstance(r,dict) and r.get("success") is not False and r.get("account_id"):
                    aid=r.get("account_id", nid)
                    save_nav(aid, mno=r.get("merchant_no",""), store="스마트스토어", login_type=ltype)
                    if npw: save_nav_pw(aid, npw)
                    dlg.accept(); s._refresh_mkt()
                    QMessageBox.information(s,"완료","네이버 연동 완료!")
                else:
                    msg = r.get("message") if isinstance(r, dict) else None
                    _show_err(msg or "로그인 실패"); go.setEnabled(True)
            s._nw.done.connect(d); s._nw.start()
        go.clicked.connect(_run); pw.returnPressed.connect(_run)
        dlg.exec()

    # ═══════════════════════════════════════════
    # 나머지 페이지 (간단 스텁 → 동작함)
    # ═══════════════════════════════════════════
    def _mk_stats(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("통계",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addWidget(QLabel("주문 · 매출 · 정산 통계",styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        hdr_ly.addStretch()
        ly.addWidget(hdr)
        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(S_SCROLL)
        inner=QWidget(); inner.setStyleSheet(f"background:{BG}")
        il=QVBoxLayout(inner); il.setContentsMargins(28,20,28,20); il.setSpacing(16)
        notice=QLabel("대시보드에서 '전체수집'을 먼저 실행하면 통계가 자동으로 갱신됩니다.")
        notice.setStyleSheet(f"color:{ACCENT};font-size:12px;background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:12px")
        il.addWidget(notice)
        tabs=QTabWidget(); tabs.setStyleSheet(S_TAB)
        s.stat_tbls={}
        defs={"일별 통계":["날짜","주문건수","송장수","총주문금액","수수료","공급금액"],
              "월별 통계":["월","주문건수","송장수","총주문금액","수수료","공급금액"],
              "쇼핑몰별":["구분","주문건수","총주문금액","수수료율","공급금액"],
              "계정별":["계정","주문건수","총주문금액","수수료율","공급금액"],
              "상품별":["상품명","주문건수","총금액","공급금액"]}
        for name,cols in defs.items():
            t=QTableWidget(); t.setColumnCount(len(cols)); t.setHorizontalHeaderLabels(cols)
            t.setStyleSheet(S_TBL); t.verticalHeader().setVisible(False)
            t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            s.stat_tbls[name]=t
            w=QWidget(); wl=QVBoxLayout(w); wl.addWidget(t)
            tabs.addTab(w,name)
        il.addWidget(tabs); il.addStretch()
        sc.setWidget(inner); ly.addWidget(sc)
        return pg

    def _refresh_stats(s):
        from collections import defaultdict
        orders=[]
        for st in OSTATUS:
            for o in s.order_data.get(st,[]):
                o["_st"]=st; orders.append(o)
        if not orders: return
        def _price(o):
            p=int(o.get("totalPrice") or 0)
            return p if p else sum(i.get("orderPrice",0) for i in o.get("orderItems",[]))
        # 일별
        daily=defaultdict(lambda:{"cnt":0,"inv":0,"tot":0})
        for o in orders:
            d=o.get("orderedAt","")[:10]
            if not d: continue
            p=_price(o); daily[d]["cnt"]+=1; daily[d]["tot"]+=p
            if o.get("invoiceNumber"): daily[d]["inv"]+=1
        t=s.stat_tbls.get("일별 통계")
        if t:
            t.setRowCount(0)
            for d in sorted(daily,reverse=True):
                v=daily[d]; fee=int(v["tot"]*0.1155); sup=v["tot"]-fee
                r=t.rowCount(); t.insertRow(r)
                for c,val in enumerate([d,f'{v["cnt"]:,}',f'{v["inv"]:,}',f'{v["tot"]:,}원',f'{fee:,}원',f'{sup:,}원']):
                    it=QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(r,c,it)
        # 월별
        monthly=defaultdict(lambda:{"cnt":0,"inv":0,"tot":0})
        for o in orders:
            m=o.get("orderedAt","")[:7]
            if not m: continue
            p=_price(o); monthly[m]["cnt"]+=1; monthly[m]["tot"]+=p
            if o.get("invoiceNumber"): monthly[m]["inv"]+=1
        t=s.stat_tbls.get("월별 통계")
        if t:
            t.setRowCount(0)
            for m in sorted(monthly,reverse=True):
                v=monthly[m]; fee=int(v["tot"]*0.1155); sup=v["tot"]-fee
                r=t.rowCount(); t.insertRow(r)
                for c,val in enumerate([m,f'{v["cnt"]:,}',f'{v["inv"]:,}',f'{v["tot"]:,}원',f'{fee:,}원',f'{sup:,}원']):
                    it=QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(r,c,it)
        # 계정별
        by_acc=defaultdict(lambda:{"cnt":0,"tot":0,"stl":0})
        for o in orders:
            u=o.get("linked_username","?"); p=_price(o)
            stl=int(o.get("settlementPrice") or int(p*0.8845))
            by_acc[u]["cnt"]+=1; by_acc[u]["tot"]+=p; by_acc[u]["stl"]+=stl
        t=s.stat_tbls.get("계정별")
        if t:
            t.setRowCount(0)
            for u in sorted(by_acc,key=lambda x:by_acc[x]["tot"],reverse=True):
                v=by_acc[u]; rate=f"{round((v['tot']-v['stl'])/v['tot']*100,2)}%" if v["tot"]>0 else "0%"
                r=t.rowCount(); t.insertRow(r)
                for c,val in enumerate([u,f'{v["cnt"]:,}',f'{v["tot"]:,}원',rate,f'{v["stl"]:,}원']):
                    it=QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(r,c,it)
        # 쇼핑몰별
        by_mkt=defaultdict(lambda:{"cnt":0,"tot":0,"stl":0})
        for o in orders:
            mk="네이버" if o.get("market")=="naver" else "쿠팡"; p=_price(o)
            stl=int(o.get("settlementPrice") or int(p*0.8845))
            by_mkt[mk]["cnt"]+=1; by_mkt[mk]["tot"]+=p; by_mkt[mk]["stl"]+=stl
        t=s.stat_tbls.get("쇼핑몰별")
        if t:
            t.setRowCount(0)
            for mk in sorted(by_mkt):
                v=by_mkt[mk]; rate=f"{round((v['tot']-v['stl'])/v['tot']*100,2)}%" if v["tot"]>0 else "0%"
                r=t.rowCount(); t.insertRow(r)
                for c,val in enumerate([mk,f'{v["cnt"]:,}',f'{v["tot"]:,}원',rate,f'{v["stl"]:,}원']):
                    it=QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(r,c,it)
        # 상품별
        by_prod=defaultdict(lambda:{"cnt":0,"tot":0})
        for o in orders:
            items=o.get("orderItems",[])
            op=_price(o)
            if len(items)==1:
                nm=items[0].get("vendorItemPackageName","?")
                by_prod[nm]["cnt"]+=1; by_prod[nm]["tot"]+=op
            elif len(items)>1:
                for item in items:
                    nm=item.get("vendorItemPackageName","?")
                    pr=int(item.get("orderPrice",0)) or op
                    by_prod[nm]["cnt"]+=1; by_prod[nm]["tot"]+=pr
            else:
                by_prod["알수없음"]["cnt"]+=1; by_prod["알수없음"]["tot"]+=op
        t=s.stat_tbls.get("상품별")
        if t:
            t.setRowCount(0)
            for nm in sorted(by_prod,key=lambda x:by_prod[x]["tot"],reverse=True):
                v=by_prod[nm]; sup=int(v["tot"]*0.8845)
                r=t.rowCount(); t.insertRow(r)
                for c,val in enumerate([nm,f'{v["cnt"]:,}',f'{v["tot"]:,}원',f'{sup:,}원']):
                    it=QTableWidgetItem(val); it.setTextAlignment(Qt.AlignmentFlag.AlignCenter); t.setItem(r,c,it)

    def _mk_memo(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("CS 메모",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addStretch()
        s.memo_search=QLineEdit(); s.memo_search.setPlaceholderText("주문번호 또는 메모 검색")
        s.memo_search.setFixedHeight(34); s.memo_search.setFixedWidth(250); s.memo_search.setStyleSheet(S_INP)
        s.memo_search.textChanged.connect(s._refresh_memo_tbl)
        hdr_ly.addWidget(s.memo_search)
        ly.addWidget(hdr)
        s.memo_tbl=QTableWidget(); s.memo_tbl.setColumnCount(4)
        s.memo_tbl.setHorizontalHeaderLabels(["주문번호","메모","수정일시","관리"])
        s.memo_tbl.setStyleSheet(S_TBL)
        s.memo_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        s.memo_tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Fixed); s.memo_tbl.setColumnWidth(0,160)
        s.memo_tbl.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.Stretch)
        s.memo_tbl.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Fixed); s.memo_tbl.setColumnWidth(2,160)
        s.memo_tbl.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed); s.memo_tbl.setColumnWidth(3,80)
        s.memo_tbl.verticalHeader().setVisible(False)
        s.memo_tbl.verticalHeader().setDefaultSectionSize(44)
        s.memo_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ly.addWidget(s.memo_tbl,1)
        s._refresh_memo_tbl()
        return pg

    def _refresh_memo_tbl(s,filt=""):
        memos=load_memos(); s.memo_tbl.setRowCount(0)
        for oid,d in memos.items():
            txt=d.get("memo","")
            if not txt: continue
            if filt and filt.lower() not in oid.lower() and filt.lower() not in txt.lower(): continue
            r=s.memo_tbl.rowCount(); s.memo_tbl.insertRow(r)
            it0=QTableWidgetItem(oid); it0.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            s.memo_tbl.setItem(r,0,it0)
            it1=QTableWidgetItem(txt); it1.setTextAlignment(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft)
            s.memo_tbl.setItem(r,1,it1)
            it2=QTableWidgetItem(d.get("updated","")); it2.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            s.memo_tbl.setItem(r,2,it2)
            def _mk_del(o):
                def handler():
                    if QMessageBox.question(s,"삭제","삭제하시겠습니까?")!=QMessageBox.StandardButton.Yes: return
                    memos2=load_memos(); memos2.pop(o,None); jsave(dp("cs_memos.json"),memos2)
                    s._refresh_memo_tbl(s.memo_search.text() if hasattr(s,"memo_search") else "")
                return handler
            db=QPushButton("삭제"); db.setStyleSheet(S_BTN_ERR+"QPushButton{font-size:11px;border-radius:4px;padding:2px 6px}")
            db.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
            db.clicked.connect(_mk_del(oid))
            s.memo_tbl.setCellWidget(r,3,db)

    def _mk_excel(s):
        VARS=["주문일시","마켓","아이디","주문번호","판매자상품코드","상품명","옵션","수량","수령인","연락처","주소","구매처","배송메모","결제금액","정산금액","택배사","송장번호","상품번호","구매자번호","우편번호"]
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        # 헤더
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("엑셀 양식",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addWidget(QLabel("엑셀 다운로드 양식 설정",styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        hdr_ly.addStretch()
        ly.addWidget(hdr)

        body=QWidget(); body.setStyleSheet(f"background:{BG}")
        bl=QHBoxLayout(body); bl.setContentsMargins(28,20,28,20); bl.setSpacing(16)

        # ── 좌: 양식 목록 ──
        left=QFrame(); left.setFixedWidth(240)
        left.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:10px")
        ll=QVBoxLayout(left); ll.setContentsMargins(14,14,14,14); ll.setSpacing(8)
        ll.addWidget(QLabel("저장된 양식",styleSheet=f"font-weight:600;font-size:14px;color:{FG}"))
        s.xl_list=QListWidget()
        s.xl_list.setStyleSheet(f"""
            QListWidget{{background:#F9FAFB;border:1px solid {BD};border-radius:6px;padding:4px}}
            QListWidget::item{{padding:10px 12px;border-radius:6px}}
            QListWidget::item:selected{{background:{FG};color:white}}
            QListWidget::item:hover:!selected{{background:#F3F4F6}}
        """)
        s.xl_list.itemClicked.connect(lambda item:s._xl_load(item.text()))
        ll.addWidget(s.xl_list,1)
        nb=QPushButton("새 양식"); nb.setFixedHeight(34); nb.setStyleSheet(S_BTN2)
        nb.clicked.connect(lambda:(s.xl_name.clear(),s.xl_tbl.setRowCount(0)))
        ll.addWidget(nb)
        db=QPushButton("양식 삭제"); db.setFixedHeight(34); db.setStyleSheet(S_BTN_ERR)
        db.clicked.connect(s._xl_del)
        ll.addWidget(db)
        bl.addWidget(left)

        # ── 우: 편집기 ──
        right=QFrame()
        right.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:10px")
        rl=QVBoxLayout(right); rl.setContentsMargins(20,16,20,16); rl.setSpacing(10)
        rl.addWidget(QLabel("양식 편집",styleSheet=f"font-weight:600;font-size:14px;color:{FG}"))
        # 이름
        nr=QHBoxLayout()
        nr.addWidget(QLabel("양식 이름:",styleSheet=f"font-weight:600;color:{FG2}"))
        s.xl_name=QLineEdit(); s.xl_name.setFixedHeight(36); s.xl_name.setPlaceholderText("양식 이름 입력"); s.xl_name.setStyleSheet(S_INP)
        nr.addWidget(s.xl_name,1)
        rl.addLayout(nr)
        # 변수 힌트
        hint=QFrame(); hint.setStyleSheet(f"background:#F0F9FF;border:1px solid #BAE6FD;border-radius:8px")
        hfl=QVBoxLayout(hint); hfl.setContentsMargins(12,8,12,8); hfl.setSpacing(4)
        hfl.addWidget(QLabel("사용 가능 변수:",styleSheet=f"font-weight:600;color:{FG};font-size:12px"))
        hfl.addWidget(QLabel("  ".join(["{"+v+"}" for v in VARS]),styleSheet=f"color:{ACCENT};font-size:11px"))
        hfl.addWidget(QLabel("수식 예: {결제금액}*0.8845",styleSheet=f"color:{GREEN};font-size:11px;font-weight:600"))
        rl.addWidget(hint)
        # 매핑 테이블 + 좌측 화살표
        tbl_row=QHBoxLayout(); tbl_row.setSpacing(8)
        # 좌측 ▲▼ 버튼
        arrow_col=QVBoxLayout(); arrow_col.setSpacing(6)
        arrow_col.addStretch()
        up_btn=QPushButton("▲"); up_btn.setFixedSize(48,90)
        up_btn.setStyleSheet(f"QPushButton{{background:#F3F4F6;color:{FG};border:1px solid {BD};border-radius:8px;font-size:28px;font-weight:700}}QPushButton:hover{{background:#E5E7EB}}")
        up_btn.clicked.connect(lambda:s._xl_move(-1))
        down_btn=QPushButton("▼"); down_btn.setFixedSize(48,90)
        down_btn.setStyleSheet(f"QPushButton{{background:#F3F4F6;color:{FG};border:1px solid {BD};border-radius:8px;font-size:28px;font-weight:700}}QPushButton:hover{{background:#E5E7EB}}")
        down_btn.clicked.connect(lambda:s._xl_move(1))
        arrow_col.addWidget(up_btn); arrow_col.addWidget(down_btn)
        arrow_col.addStretch()
        tbl_row.addLayout(arrow_col)
        # 테이블
        s.xl_tbl=_DragInsertTable(); s.xl_tbl.setColumnCount(2)
        s.xl_tbl.setHorizontalHeaderLabels(["엑셀 헤더명","내용 또는 수식"])
        s.xl_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        s.xl_tbl.verticalHeader().setVisible(True)
        s.xl_tbl.setStyleSheet(S_TBL)
        s.xl_tbl.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        s.xl_tbl.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        tbl_row.addWidget(s.xl_tbl,1)
        rl.addLayout(tbl_row,1)
        # 버튼
        br=QHBoxLayout()
        ab=QPushButton("행 추가"); ab.setFixedHeight(32); ab.setStyleSheet(S_BTN2)
        ab.clicked.connect(lambda:s.xl_tbl.insertRow(s.xl_tbl.rowCount()))
        rb_=QPushButton("행 삭제"); rb_.setFixedHeight(32); rb_.setStyleSheet(S_BTN_ERR)
        rb_.clicked.connect(lambda:[s.xl_tbl.removeRow(r) for r in sorted({i.row() for i in s.xl_tbl.selectedItems()},reverse=True)])
        br.addWidget(ab); br.addWidget(rb_); br.addStretch()
        rl.addLayout(br)
        sv=QPushButton("양식 저장"); sv.setFixedHeight(42); sv.setStyleSheet(S_BTN)
        sv.clicked.connect(s._xl_save)
        rl.addWidget(sv)
        bl.addWidget(right,1)
        ly.addWidget(body,1)
        s._xl_refresh()
        return pg

    def _xl_refresh(s):
        s.xl_list.clear()
        for t in load_tmpls(): s.xl_list.addItem(t["name"])

    def _xl_load(s,name):
        t=next((x for x in load_tmpls() if x["name"]==name),None)
        if not t: return
        s.xl_name.setText(t["name"]); s.xl_tbl.setRowCount(0)
        for m in t["mapping"]:
            r=s.xl_tbl.rowCount(); s.xl_tbl.insertRow(r)
            s.xl_tbl.setItem(r,0,QTableWidgetItem(m["header"]))
            s.xl_tbl.setItem(r,1,QTableWidgetItem(m["formula"]))

    def _xl_save(s):
        name=s.xl_name.text().strip()
        if not name: QMessageBox.warning(s,"알림","양식 이름을 입력해주세요."); return
        mapping=[]
        for r in range(s.xl_tbl.rowCount()):
            h=s.xl_tbl.item(r,0); f=s.xl_tbl.item(r,1)
            if h and h.text(): mapping.append({"header":h.text(),"formula":f.text() if f else ""})
        tmpls=load_tmpls(); found=False
        for t in tmpls:
            if t["name"]==name: t["mapping"]=mapping; found=True; break
        if not found: tmpls.append({"name":name,"mapping":mapping})
        save_tmpls(tmpls); s._xl_refresh()
        QMessageBox.information(s,"저장","양식이 저장되었습니다.")

    def _xl_del(s):
        cur=s.xl_list.currentItem()
        if not cur: return
        if "기본" in cur.text(): QMessageBox.warning(s,"알림","기본 양식은 삭제할 수 없습니다."); return
        save_tmpls([t for t in load_tmpls() if t["name"]!=cur.text()])
        s._xl_refresh()

    def _xl_move(s,direction):
        """양식 테이블 행 이동. direction: -1=위, 1=아래"""
        row=s.xl_tbl.currentRow()
        if row<0: return
        new_row=row+direction
        if new_row<0 or new_row>=s.xl_tbl.rowCount(): return
        cols=s.xl_tbl.columnCount()
        rd=[]
        for c in range(cols):
            it=s.xl_tbl.item(row,c); rd.append(it.text() if it else "")
        s.xl_tbl.removeRow(row)
        s.xl_tbl.insertRow(new_row)
        for c in range(cols): s.xl_tbl.setItem(new_row,c,QTableWidgetItem(rd[c]))
        s.xl_tbl.selectRow(new_row)

    def _mk_settings(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("설정",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addWidget(QLabel("프로그램 설정",styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        hdr_ly.addStretch()
        ly.addWidget(hdr)
        sc=QScrollArea(); sc.setWidgetResizable(True); sc.setStyleSheet(S_SCROLL)
        inner=QWidget(); inner.setStyleSheet(f"background:{BG}")
        il=QVBoxLayout(inner); il.setContentsMargins(28,20,28,20); il.setSpacing(16)

        # 알림 설정 카드
        nc=QFrame(); nc.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:10px")
        nl=QVBoxLayout(nc); nl.setContentsMargins(20,16,20,16); nl.setSpacing(10)
        nl.addWidget(QLabel("알림 설정",styleSheet=f"font-size:14px;font-weight:600;color:{FG}"))
        s.notif_sw={}
        for label,key in [("신규주문 알림","결제완료"),("출고중지요청 알림","출고중지요청"),("반품요청 알림","반품요청"),("교환요청 알림","교환요청")]:
            row=QHBoxLayout()
            row.addWidget(QLabel(label,styleSheet=f"font-size:13px;color:{FG}"))
            row.addStretch()
            sw=ToggleSwitch(True); row.addWidget(sw)
            s.notif_sw[key]=sw
            nl.addLayout(row)
        il.addWidget(nc)

        # 수집 설정 카드
        fc=QFrame(); fc.setStyleSheet(f"background:{WHITE};border:1px solid {BD};border-radius:10px")
        fl=QVBoxLayout(fc); fl.setContentsMargins(20,16,20,16); fl.setSpacing(10)
        fl.addWidget(QLabel("수집 설정",styleSheet=f"font-size:14px;font-weight:600;color:{FG}"))
        ar=QHBoxLayout()
        ar.addWidget(QLabel("자동 새로고침",styleSheet=f"font-size:13px;color:{FG}"))
        ar.addStretch(); s.auto_refresh_cb=ToggleSwitch(False)
        s.auto_refresh_cb.toggled.connect(s._toggle_auto_refresh)
        ar.addWidget(s.auto_refresh_cb)
        fl.addLayout(ar)
        sr=QHBoxLayout()
        sr.addWidget(QLabel("새로고침 간격 (분)",styleSheet=f"font-size:13px;color:{FG}"))
        sr.addStretch()
        s.auto_spin=QSpinBox(); s.auto_spin.setRange(1,60); s.auto_spin.setValue(5); s.auto_spin.setFixedHeight(34); s.auto_spin.setFixedWidth(80); s.auto_spin.setStyleSheet(S_INP)
        sr.addWidget(s.auto_spin)
        fl.addLayout(sr)
        il.addWidget(fc)
        s._auto_timer=QTimer(s)
        s._auto_timer.timeout.connect(s._auto_fetch)

        il.addStretch()
        sc.setWidget(inner); ly.addWidget(sc)
        return pg

    def _toggle_auto_refresh(s,on):
        if on:
            mins=s.auto_spin.value()
            s._auto_timer.start(mins*60*1000)
        else:
            s._auto_timer.stop()

    def _auto_fetch(s):
        """자동 새로고침 — 수집 후 알림만 (팝업 없이 음성만)"""
        accs=s._get_all_accs()
        if not accs: return
        pws=load_pw()
        s.color_map={a["username"]:TINTS[i%len(TINTS)] for i,a in enumerate(accs)}
        sd=s.d_s.date().toString("yyyy-MM-dd"); ed=s.d_e.date().toString("yyyy-MM-dd")
        s.d_prog.setValue(0); s.d_prog.setFormat("자동 수집 중...")
        s._auto_cw=CollectWorker(accs,pws,sd,ed)
        s._auto_cw.prog.connect(lambda p,m:(s.d_prog.setValue(p),s.d_prog.setFormat(f"{m} {p}%")))
        def _auto_done(res):
            ad=res["data"]; st2=res["stats"]
            s.order_data=ad
            for nm in OSTATUS:
                if nm in s.scards: s.scards[nm].setText(f"{st2.get(nm,0)}건")
            for nm in CSTATUS:
                if nm in s.ccards: s.ccards[nm].setText(f"{st2.get(nm,0)}건")
            for nm,items in ad.items():
                if nm in OSTATUS and nm in s.otbls: s._fill_order(nm,items)
                elif nm in CSTATUS and nm in s.rtbls: s._fill_return(nm,items)
            s.d_prog.setValue(100); s.d_prog.setFormat("자동 수집 완료")
            if hasattr(s,"stat_tbls"): s._refresh_stats()
            # 음성 알림만 (팝업 없음)
            if hasattr(s,"notif_sw"):
                nmap={"결제완료":"신규주문이 있습니다","출고중지요청":"출고중지 요청이 있습니다","반품요청":"반품 요청이 있습니다","교환요청":"교환 요청이 있습니다"}
                for key,sw in s.notif_sw.items():
                    if sw.isChecked() and st2.get(key,0)>0:
                        _tts(nmap.get(key,""))
                        break
        s._auto_cw.done.connect(_auto_done)
        s._auto_cw.start()

    def _mk_admin(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        # 헤더
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("회원 관리",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addWidget(QLabel("가입 회원 조회 · 기간 설정 · 삭제",styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        hdr_ly.addStretch()
        sa_btn=QPushButton("전체선택"); sa_btn.setFixedHeight(34); sa_btn.setStyleSheet(S_BTN2); sa_btn.clicked.connect(s._admin_toggle_all)
        hdr_ly.addWidget(sa_btn)
        se_btn=QPushButton("선택 기간설정"); se_btn.setFixedHeight(34); se_btn.setStyleSheet(S_BTN_WARN); se_btn.clicked.connect(s._admin_bulk_expiry)
        hdr_ly.addWidget(se_btn)
        ref=QPushButton("새로고침"); ref.setFixedHeight(34); ref.setStyleSheet(S_BTN); ref.clicked.connect(s._admin_load)
        hdr_ly.addWidget(ref)
        ly.addWidget(hdr)
        # 테이블
        s.adm_tbl=QTableWidget(); s.adm_tbl.setColumnCount(8)
        s.adm_tbl.setHorizontalHeaderLabels(["선택","아이디","이름","생년월일","연락처","가입일","만료일","관리"])
        s.adm_tbl.horizontalHeader().sectionClicked.connect(lambda col:s._admin_toggle_all() if col==0 else None)
        s.adm_tbl._all_checked=False
        s.adm_tbl.setStyleSheet(S_TBL)
        s.adm_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        s.adm_tbl.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Fixed); s.adm_tbl.setColumnWidth(0,50)
        s.adm_tbl.horizontalHeader().setSectionResizeMode(7,QHeaderView.ResizeMode.Fixed); s.adm_tbl.setColumnWidth(7,170)
        s.adm_tbl.verticalHeader().setDefaultSectionSize(44)
        s.adm_tbl.verticalHeader().setVisible(False)
        s.adm_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ly.addWidget(s.adm_tbl,1)
        return pg

    def _admin_load(s):
        try:
            data=_sbget("users","order=created_at.desc")
        except Exception as e:
            QMessageBox.warning(s,"오류",f"회원 로드 실패: {e}"); return
        s.adm_tbl.setRowCount(0)
        for ri,row in enumerate(data):
            s.adm_tbl.insertRow(ri)
            # 체크박스
            chk_w=QWidget(); chk_ly2=QHBoxLayout(chk_w); chk_ly2.setContentsMargins(0,0,0,0); chk_ly2.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chk=CheckBox(False)
            chk_ly2.addWidget(chk)
            s.adm_tbl.setCellWidget(ri,0,chk_w)
            s.adm_tbl.setItem(ri,1,QTableWidgetItem(row.get("username","")))
            s.adm_tbl.setItem(ri,2,QTableWidgetItem(row.get("user_name","")))
            s.adm_tbl.setItem(ri,3,QTableWidgetItem(row.get("birth_date","") or ""))
            s.adm_tbl.setItem(ri,4,QTableWidgetItem(row.get("phone","") or ""))
            created=(row.get("created_at","") or "")[:10]
            s.adm_tbl.setItem(ri,5,QTableWidgetItem(created))
            # 만료일
            exp=row.get("expired_at","")
            txt=exp[:10] if exp else "무제한"
            it=QTableWidgetItem(txt)
            if exp:
                try:
                    ed=datetime.datetime.fromisoformat(exp.replace("Z","")).date()
                    rem=(ed-datetime.date.today()).days
                    if rem<0: it.setForeground(QColor(RED)); it.setText(f"{txt} (만료)")
                    elif rem<=7: it.setForeground(QColor(AMBER)); it.setText(f"{txt} ({rem}일)")
                    else: it.setForeground(QColor(GREEN)); it.setText(f"{txt} ({rem}일)")
                except: pass
            it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            s.adm_tbl.setItem(ri,6,it)
            # 관리 (기간설정+삭제 한 셀에)
            uid=row.get("username","")
            bw=QWidget(); bl2=QHBoxLayout(bw); bl2.setContentsMargins(2,0,2,0); bl2.setSpacing(2)
            sb2=QPushButton("기간설정"); sb2.setStyleSheet(S_BTN+"QPushButton{font-size:11px;border-radius:4px;padding:2px 6px}")
            sb2.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
            def _mk_exp(u): return lambda:s._admin_expiry(u)
            sb2.clicked.connect(_mk_exp(uid))
            db2=QPushButton("삭제"); db2.setStyleSheet(S_BTN_ERR+"QPushButton{font-size:11px;border-radius:4px;padding:2px 6px}")
            db2.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
            def _mk_del(u): return lambda:s._admin_del(u)
            db2.clicked.connect(_mk_del(uid))
            bl2.addWidget(sb2); bl2.addWidget(db2)
            s.adm_tbl.setCellWidget(ri,7,bw)

    def _admin_toggle_all(s):
        t=s.adm_tbl; checked=getattr(t,'_all_checked',True)
        for r in range(t.rowCount()):
            w=t.cellWidget(r,0)
            if w:
                cb=w.findChild(CheckBox)
                if cb: cb.setChecked(not checked)
        t._all_checked=not checked
        h=t.horizontalHeaderItem(0)
        if h: h.setText("해제" if checked else "전체")

    def _admin_bulk_expiry(s):
        """선택된 회원 일괄 기간설정"""
        uids=[]
        for r in range(s.adm_tbl.rowCount()):
            w=s.adm_tbl.cellWidget(r,0)
            if w:
                cb=w.findChild(CheckBox)
                if cb and cb.isChecked():
                    it=s.adm_tbl.item(r,1)
                    if it: uids.append(it.text())
        if not uids:
            QMessageBox.warning(s,"알림","선택된 회원이 없습니다.")
            return
        dlg=ModalDlg(s); dlg.setWindowTitle(f"일괄 기간설정 ({len(uids)}명)")
        dlg.setFixedSize(360,240); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(28,20,28,20); dl.setSpacing(12)
        dl.addWidget(QLabel(f"{len(uids)}명 선택됨",styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        de=QDateEdit(); de.setCalendarPopup(True); de.setDate(QDate.currentDate().addMonths(1))
        de.setFixedHeight(38); de.setStyleSheet(S_CAL)
        dl.addWidget(de)
        qr=QHBoxLayout(); qr.setSpacing(6)
        for label,m in [("1개월",1),("3개월",3),("6개월",6),("1년",12)]:
            b=QPushButton(label); b.setFixedHeight(28); b.setStyleSheet(S_BTN2)
            b.clicked.connect(lambda _,mo=m:de.setDate(QDate.currentDate().addMonths(mo)))
            qr.addWidget(b)
        dl.addLayout(qr)
        br=QHBoxLayout()
        sv=QPushButton("일괄 설정"); sv.setFixedHeight(36); sv.setStyleSheet(S_BTN)
        ul=QPushButton("일괄 무제한"); ul.setFixedHeight(36); ul.setStyleSheet(S_BTN_OK)
        cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        def _save():
            exp=de.date().toString("yyyy-MM-dd")+"T23:59:59"
            for u in uids: _sbmut("users",{"expired_at":exp},"PATCH",f"username=eq.{urllib.parse.quote(u)}")
            dlg.accept(); s._admin_load(); QMessageBox.information(s,"완료",f"{len(uids)}명 기간 설정 완료!")
        def _unlim():
            for u in uids: _sbmut("users",{"expired_at":None},"PATCH",f"username=eq.{urllib.parse.quote(u)}")
            dlg.accept(); s._admin_load(); QMessageBox.information(s,"완료",f"{len(uids)}명 무제한 설정!")
        sv.clicked.connect(_save); ul.clicked.connect(_unlim)
        br.addWidget(ul); br.addWidget(sv); br.addWidget(cn)
        dl.addLayout(br); dlg.exec()

    def _admin_expiry(s,uid):
        dlg=ModalDlg(s); dlg.setWindowTitle(f"기간설정 — {uid}"); dlg.setFixedSize(360,260)
        dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(28,20,28,20); dl.setSpacing(12)
        dl.addWidget(QLabel(uid,styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        dl.addWidget(QLabel("만료일 선택:",styleSheet=f"font-size:13px;color:{FG2}"))
        de=QDateEdit(); de.setCalendarPopup(True); de.setDate(QDate.currentDate().addMonths(1))
        de.setFixedHeight(38); de.setStyleSheet(S_CAL)
        dl.addWidget(de)
        qr=QHBoxLayout(); qr.setSpacing(6)
        for label,m in [("1개월",1),("3개월",3),("6개월",6),("1년",12)]:
            b=QPushButton(label); b.setFixedHeight(28); b.setStyleSheet(S_BTN2)
            b.clicked.connect(lambda _,mo=m:de.setDate(QDate.currentDate().addMonths(mo)))
            qr.addWidget(b)
        dl.addLayout(qr)
        br=QHBoxLayout()
        sv=QPushButton("저장"); sv.setFixedHeight(36); sv.setStyleSheet(S_BTN)
        ul=QPushButton("무제한"); ul.setFixedHeight(36); ul.setStyleSheet(S_BTN_OK)
        cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        def _save():
            _sbmut("users",{"expired_at":de.date().toString("yyyy-MM-dd")+"T23:59:59"},"PATCH",f"username=eq.{urllib.parse.quote(uid)}")
            dlg.accept(); s._admin_load(); QMessageBox.information(s,"완료","설정 완료!")
        def _unlim():
            _sbmut("users",{"expired_at":None},"PATCH",f"username=eq.{urllib.parse.quote(uid)}")
            dlg.accept(); s._admin_load(); QMessageBox.information(s,"완료","무제한 설정!")
        sv.clicked.connect(_save); ul.clicked.connect(_unlim)
        br.addWidget(ul); br.addWidget(sv); br.addWidget(cn)
        dl.addLayout(br); dlg.exec()

    def _admin_del(s,uid):
        if uid==ADMIN: QMessageBox.warning(s,"알림","관리자 삭제 불가"); return
        if QMessageBox.question(s,"확인",f"'{uid}' 삭제?")!=QMessageBox.StandardButton.Yes: return
        try:
            _sbmut("users",None,"DELETE",f"username=eq.{urllib.parse.quote(uid)}")
            s._admin_load(); QMessageBox.information(s,"완료","삭제 완료!")
        except Exception as e: QMessageBox.warning(s,"오류",str(e))

    def _mk_notice_admin(s):
        pg=QWidget(); ly=QVBoxLayout(pg); ly.setContentsMargins(0,0,0,0); ly.setSpacing(0)
        hdr=QFrame(); hdr.setStyleSheet(f"background:{WHITE};border-bottom:1px solid {BD}")
        hdr_ly=QHBoxLayout(hdr); hdr_ly.setContentsMargins(28,14,28,14)
        hdr_ly.addWidget(QLabel("공지 관리",styleSheet=f"font-size:20px;font-weight:700;color:{FG}"))
        hdr_ly.addWidget(QLabel("공지사항 작성 · 수정 · 삭제",styleSheet=f"font-size:12px;color:{FG2};margin-left:10px"))
        hdr_ly.addStretch()
        ref=QPushButton("새로고침"); ref.setFixedHeight(34); ref.setStyleSheet(S_BTN); ref.clicked.connect(s._notice_load)
        hdr_ly.addWidget(ref)
        nw=QPushButton("새 공지 작성"); nw.setFixedHeight(34); nw.setStyleSheet(S_BTN_OK); nw.clicked.connect(lambda:s._notice_edit(None))
        hdr_ly.addWidget(nw)
        ly.addWidget(hdr)
        s.ntc_tbl=QTableWidget(); s.ntc_tbl.setColumnCount(5)
        s.ntc_tbl.setHorizontalHeaderLabels(["제목","내용","활성","작성일","관리"])
        s.ntc_tbl.setStyleSheet(S_TBL)
        s.ntc_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        s.ntc_tbl.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.Fixed); s.ntc_tbl.setColumnWidth(2,60)
        s.ntc_tbl.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Fixed); s.ntc_tbl.setColumnWidth(3,100)
        s.ntc_tbl.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Fixed); s.ntc_tbl.setColumnWidth(4,150)
        s.ntc_tbl.verticalHeader().setVisible(False); s.ntc_tbl.verticalHeader().setDefaultSectionSize(44)
        s.ntc_tbl.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        ly.addWidget(s.ntc_tbl,1)
        return pg

    def _notice_load(s):
        try: data=_sbget("notices","order=created_at.desc")
        except Exception as e: QMessageBox.warning(s,"오류",str(e)); return
        s.ntc_tbl.setRowCount(0)
        for ri,row in enumerate(data):
            s.ntc_tbl.insertRow(ri)
            s.ntc_tbl.setItem(ri,0,QTableWidgetItem(row.get("title","")))
            c=row.get("content","")
            s.ntc_tbl.setItem(ri,1,QTableWidgetItem(c[:50]+("..." if len(c)>50 else "")))
            ac=QTableWidgetItem("O" if row.get("is_active") else "X")
            ac.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            s.ntc_tbl.setItem(ri,2,ac)
            s.ntc_tbl.setItem(ri,3,QTableWidgetItem((row.get("created_at","") or "")[:10]))
            # 수정+삭제 버튼
            bw=QWidget(); bl3=QHBoxLayout(bw); bl3.setContentsMargins(2,0,2,0); bl3.setSpacing(2)
            eb=QPushButton("수정"); eb.setStyleSheet(S_BTN+"QPushButton{font-size:11px;border-radius:4px;padding:2px 6px}")
            eb.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
            def _mk_edit(r): return lambda:s._notice_edit(r)
            eb.clicked.connect(_mk_edit(row))
            db=QPushButton("삭제"); db.setStyleSheet(S_BTN_ERR+"QPushButton{font-size:11px;border-radius:4px;padding:2px 6px}")
            db.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
            def _mk_del(nid): return lambda:s._notice_del(nid)
            db.clicked.connect(_mk_del(row.get("id")))
            bl3.addWidget(eb); bl3.addWidget(db)
            s.ntc_tbl.setCellWidget(ri,4,bw)

    def _notice_edit(s,row_data):
        is_edit=row_data is not None
        dlg=ModalDlg(s); dlg.setWindowTitle("공지 수정" if is_edit else "새 공지 작성")
        dlg.setFixedSize(500,380); dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(10)
        dl.addWidget(QLabel("공지 수정" if is_edit else "새 공지 작성",styleSheet=f"font-size:18px;font-weight:700;color:{FG}"))
        ti=QLineEdit(); ti.setFixedHeight(38); ti.setStyleSheet(S_INP); ti.setPlaceholderText("제목")
        if is_edit: ti.setText(row_data.get("title",""))
        dl.addWidget(ti)
        ci=QTextEdit(); ci.setStyleSheet(f"border:1px solid {BD};border-radius:8px;font-size:13px;padding:8px;color:{FG}")
        if is_edit: ci.setText(row_data.get("content",""))
        dl.addWidget(ci)
        ac=QCheckBox("활성화 (사용자에게 표시)"); ac.setStyleSheet(f"font-size:13px;color:{FG}")
        ac.setChecked(row_data.get("is_active",True) if is_edit else True)
        dl.addWidget(ac)
        br=QHBoxLayout()
        sv=QPushButton("저장"); sv.setFixedHeight(36); sv.setStyleSheet(S_BTN)
        cn=QPushButton("취소"); cn.setFixedHeight(36); cn.setStyleSheet(S_BTN2); cn.clicked.connect(dlg.reject)
        br.addWidget(sv); br.addWidget(cn); dl.addLayout(br)
        def _save():
            if not ti.text().strip(): QMessageBox.warning(dlg,"알림","제목을 입력해주세요."); return
            body={"title":ti.text().strip(),"content":ci.toPlainText().strip(),"is_active":ac.isChecked()}
            try:
                if is_edit: _sbmut("notices",body,"PATCH",f"id=eq.{row_data.get('id')}")
                else: _sbmut("notices",body)
                dlg.accept(); s._notice_load()
                QMessageBox.information(s,"완료","공지사항이 저장되었습니다.")
            except Exception as e: QMessageBox.warning(dlg,"오류",str(e))
        sv.clicked.connect(_save); dlg.exec()

    def _notice_del(s,nid):
        if QMessageBox.question(s,"확인","이 공지를 삭제하시겠습니까?")!=QMessageBox.StandardButton.Yes: return
        try: _sbmut("notices",None,"DELETE",f"id=eq.{nid}"); s._notice_load(); QMessageBox.information(s,"완료","삭제 완료!")
        except Exception as e: QMessageBox.warning(s,"오류",str(e))

# ═══════════════════════════════════════════
# 실행
# ═══════════════════════════════════════════
if __name__=="__main__":
    app=QApplication(sys.argv)
    app.setStyle("Fusion")
    dlg=AuthDialog()
    if dlg.exec()!=QDialog.DialogCode.Accepted: sys.exit(0)
    w=App(dlg.uname,dlg.exp_at,dlg.uid)
    w.show()
    # 연동 체크 — 실제 API 호출로 쿠키 유효성 검증
    def _chk():
        cpg=load_all_accounts() or []; navs=load_nav()
        if not cpg and not navs: return

        dlg=ModalDlg(w); dlg.setWindowTitle("연동 상태"); dlg.setFixedWidth(400)
        dlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG};font-size:13px}}")
        dl=QVBoxLayout(dlg); dl.setContentsMargins(24,20,24,20); dl.setSpacing(8)
        dl.addWidget(QLabel("연동 상태",styleSheet=f"font-size:16px;font-weight:700;color:{FG}"))
        dl.addSpacing(4)

        status_labels={}
        for a in cpg:
            uid=a["username"]
            row=QHBoxLayout(); row.addWidget(QLabel(f"쿠팡: {uid}")); row.addStretch()
            st=QLabel("● 확인 중...")
            st.setStyleSheet(f"font-size:12px;font-weight:600;color:{FG3}")
            row.addWidget(st); dl.addLayout(row)
            status_labels[("cpg",uid)]=st
        for n in navs:
            aid=n.get("account_id",""); store=n.get("store_name",aid)
            row=QHBoxLayout(); row.addWidget(QLabel(f"네이버: {store}")); row.addStretch()
            st=QLabel("● 확인 중...")
            st.setStyleSheet(f"font-size:12px;font-weight:600;color:{FG3}")
            row.addWidget(st); dl.addLayout(row)
            status_labels[("nav",aid)]=st

        # 검증 결과 모음
        results={"cpg":{}, "nav":{}}

        class VerifyWorker(QThread):
            result=pyqtSignal(str,str,bool)
            done=pyqtSignal()
            def run(self):
                for a in cpg:
                    uid=a["username"]
                    try: ok=verify_cookies(uid)
                    except: ok=False
                    self.result.emit("cpg",uid,ok)
                for n in navs:
                    aid=n.get("account_id","")
                    try: ok=verify_naver_cookies(aid)
                    except: ok=False
                    self.result.emit("nav",aid,ok)
                self.done.emit()

        def _on_result(market,key,ok):
            results[market][key]=ok
            lbl=status_labels.get((market,key))
            if lbl:
                lbl.setText("● 정상" if ok else "● 만료")
                lbl.setStyleSheet(f"font-size:12px;font-weight:600;color:{GREEN if ok else RED}")

        def _after_verify():
            QTimer.singleShot(1200, dlg.accept)

        w._verify_worker=VerifyWorker()
        w._verify_worker.result.connect(_on_result)
        w._verify_worker.done.connect(_after_verify)
        w._verify_worker.start()

        dlg.exec()

        # 검증 끝난 뒤: 만료된 거 있으면 재연동 묻고 → 수집. 다 정상이면 바로 수집.
        expired_cpg=[a for a in cpg if not results["cpg"].get(a["username"], False)]
        expired_nav=[n for n in navs if not results["nav"].get(n.get("account_id",""), False)]

        if expired_cpg or expired_nav:
            # 커스텀 모달 (앱 디자인 톤)
            edlg=ModalDlg(w); edlg.setWindowTitle("연동 만료")
            edlg.setFixedWidth(440)
            edlg.setStyleSheet(f"QDialog{{background:{WHITE}}}QLabel{{color:{FG}}}")
            ev=QVBoxLayout(edlg); ev.setContentsMargins(28,24,28,22); ev.setSpacing(12)

            # 헤더 (붉은 점 아이콘 + 타이틀)
            header=QHBoxLayout(); header.setSpacing(10)
            dot=QLabel("●"); dot.setStyleSheet(f"color:{RED};font-size:14px;background:transparent")
            dot.setFixedWidth(14)
            ttl=QLabel("연동이 만료되었습니다")
            ttl.setStyleSheet(f"font-size:17px;font-weight:700;color:{FG};background:transparent")
            header.addWidget(dot); header.addWidget(ttl); header.addStretch()
            ev.addLayout(header)

            sub=QLabel("아래 계정의 세션이 끊어졌습니다. 재연동 후 수집을 이어서 진행할 수 있습니다.")
            sub.setStyleSheet(f"font-size:12px;color:{FG2};background:transparent")
            sub.setWordWrap(True)
            ev.addWidget(sub)
            ev.addSpacing(2)

            # 만료 계정 카드
            card=QFrame()
            card.setStyleSheet(f"QFrame{{background:#FEF2F2;border:1px solid #FCA5A5;border-radius:10px}}")
            cv=QVBoxLayout(card); cv.setContentsMargins(16,12,16,12); cv.setSpacing(6)
            for a in expired_cpg:
                row=QHBoxLayout(); row.setSpacing(8)
                tag=QLabel("쿠팡"); tag.setFixedWidth(46); tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tag.setStyleSheet(f"background:#fff;color:{FG};border:1px solid {BD};border-radius:5px;font-size:11px;font-weight:700;padding:2px 0")
                name=QLabel(a["username"])
                name.setStyleSheet(f"font-size:13px;color:{FG};background:transparent;font-weight:600")
                row.addWidget(tag); row.addWidget(name); row.addStretch()
                cv.addLayout(row)
            for n in expired_nav:
                row=QHBoxLayout(); row.setSpacing(8)
                tag=QLabel("네이버"); tag.setFixedWidth(46); tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
                tag.setStyleSheet(f"background:#fff;color:{GREEN};border:1px solid #A7F3D0;border-radius:5px;font-size:11px;font-weight:700;padding:2px 0")
                name=QLabel(n.get('store_name', n.get('account_id','')))
                name.setStyleSheet(f"font-size:13px;color:{FG};background:transparent;font-weight:600")
                row.addWidget(tag); row.addWidget(name); row.addStretch()
                cv.addLayout(row)
            ev.addWidget(card)

            note=QLabel("취소 시 만료된 계정은 이번 수집에서 제외됩니다.")
            note.setStyleSheet(f"font-size:11px;color:{FG3};background:transparent")
            ev.addWidget(note)

            # 버튼
            br=QHBoxLayout(); br.setSpacing(10)
            cn=QPushButton("취소"); cn.setFixedHeight(38); cn.setStyleSheet(S_BTN2); cn.setCursor(Qt.CursorShape.PointingHandCursor)
            ok=QPushButton("재연동"); ok.setFixedHeight(38); ok.setStyleSheet(S_BTN); ok.setCursor(Qt.CursorShape.PointingHandCursor)
            cn.clicked.connect(edlg.reject); ok.clicked.connect(edlg.accept)
            br.addStretch(); br.addWidget(cn); br.addWidget(ok)
            ev.addLayout(br)

            accepted = edlg.exec() == QDialog.DialogCode.Accepted
            if accepted:
                w._relink_and_fetch(expired_cpg, expired_nav)
                return
            # 취소 → 정상 계정만으로 수집
            valid_cpg=[a for a in cpg if results["cpg"].get(a["username"], False)]
            valid_nav=[n for n in navs if results["nav"].get(n.get("account_id",""), False)]
            if not valid_cpg and not valid_nav:
                return
            accs=list(valid_cpg)
            for n in valid_nav:
                accs.append({"username":n.get("account_id",""),"market":"naver",
                             "account_id":n.get("account_id",""),"merchant_no":n.get("merchant_no",""),
                             "store_name":n.get("store_name","")})
            QTimer.singleShot(300, lambda: w._dash_fetch(accs))
        else:
            QTimer.singleShot(300, w._dash_fetch)

    QTimer.singleShot(1000,_chk)
    sys.exit(app.exec())
