# -*- coding: utf-8 -*-
"""پارسر کانال‌های مشهد — پروتوتایپ قابل استفاده در پروژه"""
import urllib.request, re, ssl, html as H

ZWNJ='\u200c'; TSEP='\u066c'  # ‌ و ٬
ctx=ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

def fetch_msgs(channel):
    raw=urllib.request.urlopen(urllib.request.Request(f"https://t.me/s/{channel}",headers=UA),timeout=15,context=ctx).read().decode("utf-8","replace")
    msgs=re.findall(r'tgme_widget_message_text[^>]*>([\s\S]*?)</div>',raw)
    times=re.findall(r'<time datetime="([^"]+)"',raw)
    ids=re.findall(r'data-post="[^/]*/(\d+)"',raw)
    out=[]
    for i,m in enumerate(msgs):
        t=re.sub(r'<br\s*/?>','\n',m); t=re.sub(r'<[^>]+>','',t); t=H.unescape(t).strip()
        tm=times[i] if i<len(times) else ""
        mid=ids[i] if i<len(ids) else "0"
        out.append((int(mid) if mid.isdigit() else 0, tm, t))
    return out

def to_int(s):
    s=s.translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹','0123456789'))
    s=re.sub(r'[.,\s٬]','',s)
    return int(s) if s.isdigit() else None

# --- پارسر MARKIZ_ARG (طلای آبشده مارکیز مشهد) ---
RE_BUY=re.compile(r'قیمت\s+خرید\s+آبشده[^\n:]*:\s*\n?\s*([\d۰-۹.,٬\s]+?)\s*ریال')
RE_SELL=re.compile(r'قیمت\s+فروش\s+آبشده[^\n:]*:\s*\n?\s*([\d۰-۹.,٬\s]+?)\s*ریال')

def parse_markiz(msgs):
    buy=sell=None; ts_buy=ts_sell=""; last_id=0
    for mid,tm,t in msgs:  # از قدیمی به جدید؛ آخرین برنده
        m=RE_BUY.search(t)
        if m: buy,to_int(m.group(1)) and None or to_int(m.group(1)); buy=to_int(m.group(1)); ts_buy=tm; last_id=max(last_id,mid)
        m=RE_SELL.search(t)
        if m: sell=to_int(m.group(1)); ts_sell=tm; last_id=max(last_id,mid)
    return {"gold_ab_mashhad":{"buy_rial":buy,"sell_rial":sell,"buy_time":ts_buy,"sell_time":ts_sell,"msg_id":last_id}}

# --- پارسر dolarmashad ---
RE_USD=re.compile(r'^کف[\s'+ZWNJ+r']*مشهد\s+([\d۰-۹]+)$')
RE_G18=re.compile(r'هرگرم\s+طلای\s+۱۸عیار\s*کف['+ZWNJ+r'\s]*مشهد\s+([\d۰-۹.,٬]+)')
def parse_dolarmashad(msgs):
    usd=g18=None; tu=tg=""
    for mid,tm,t in msgs:
        for line in t.split('\n'):
            line=line.strip()
            if RE_USD.match(line): usd=to_int(RE_USD.match(line).group(1)); tu=tm
            m=RE_G18.search(line)
            if m: g18=to_int(m.group(1)); tg=tm
    return {"mashhad":{"usd_kaf_toman":usd,"usd_time":tu,"gold18_gram_toman":g18,"gold18_time":tg}}

if __name__=="__main__":
    mk=fetch_msgs("MARKIZ_ARG"); dm=fetch_msgs("dolarmashad")
    import json
    print(json.dumps(parse_markiz(mk),ensure_ascii=False,indent=2))
    print(json.dumps(parse_dolarmashad(dm),ensure_ascii=False,indent=2))
