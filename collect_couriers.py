# -*- coding: utf-8 -*-
"""
쿠팡 Wing 택배사 코드 수집 (배송 데이터에서 추출)
배송지시/배송중/배송완료 주문의 deliverName + deliverCode 조합을 모음
"""
import json
from coupang_auth import load_all_accounts, _data_path
from coupang_crawl import get_all_orders_only
from main import load_pw
import datetime

def main():
    accs=load_all_accounts()
    if not accs:
        print("연동된 쿠팡 계정 없음"); return
    pws=load_pw()
    cmap={}

    # 90일치 데이터에서 deliverName/deliverCode 추출
    sd=(datetime.date.today()-datetime.timedelta(days=90)).isoformat()
    ed=datetime.date.today().isoformat()

    for acc in accs:
        uid=acc["username"]; pw=pws.get(uid,"")
        print(f"[{uid}] 90일치 주문 수집 중...")
        try:
            res=get_all_orders_only(uid,pw,sd,ed,callback=lambda m:print(f"  {m}"))
            if res and res.get("code")==200:
                data=res.get("data",{})
                for status,orders in data.items():
                    for o in orders:
                        nm=o.get("deliverName","")
                        cd=o.get("deliverCode","")
                        if nm and cd and nm not in ("None","null") and cd not in ("None","null","[object Object]"):
                            cmap[nm]=cd
                print(f"  {uid}: 누적 {len(cmap)}개 택배사 코드")
        except Exception as e:
            print(f"  오류: {e}")

    if not cmap:
        print("\n수집된 택배사 코드 없음")
        return

    # 저장
    path=_data_path("courier_map.json")
    with open(path,"w",encoding="utf-8") as f:
        json.dump(cmap,f,ensure_ascii=False,indent=2)
    print(f"\n저장 완료: {path}")
    print(f"총 {len(cmap)}개")
    for k,v in cmap.items():
        print(f"  {k}: {v}")

if __name__=="__main__":
    main()
