from flask import Flask, request, render_template_string, redirect, url_for, session, abort
from werkzeug.security import check_password_hash
from urllib.parse import quote
import sqlite3, os, secrets, uuid, re
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
DB_PATH = os.environ.get("DB_PATH", "red_zone_orders.db")

STORE_NAME = "RED ZONE UC"
WHATSAPP = "201224773745"
WALLET = "01224773745"

PACKAGES = [
    {"uc": 60, "price": 60},
    {"uc": 325, "price": 250},
    {"uc": 660, "price": 500},
    {"uc": 1800, "price": 1500},
]
STATUSES = ["في انتظار الدفع", "تم تأكيد الدفع", "تم الشحن", "ملغي"]

def get_db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with get_db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            player_id TEXT NOT NULL,
            phone TEXT NOT NULL,
            uc INTEGER NOT NULL,
            price INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )""")
init_db()

def token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(24)
    return session["csrf"]

def verify_token():
    if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "")):
        abort(400, "طلب غير صالح. أعد تحميل الصفحة وحاول مرة أخرى.")

def admin_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

STYLE = """
<style>
*{box-sizing:border-box}body{margin:0;background:#000;color:#fff;font-family:Arial,sans-serif}
header{background:#080808;text-align:center;padding:24px 10px;border-bottom:1px solid #333}
.logo{font-size:29px;font-weight:900;letter-spacing:1px}
main{width:min(850px,100%);margin:auto;padding:18px}
h1,h2{text-align:center}.muted{color:#aaa;line-height:1.9}
.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:22px 0}
.card,.panel,form{background:#101010;border:1px solid #333;border-radius:12px;padding:16px;margin:14px 0}
.card{text-align:center}.uc{font-size:23px;font-weight:bold}.price{font-size:19px;margin-top:10px}
label{display:block;margin-top:14px}input,select{display:block;width:100%;margin-top:8px;padding:13px;border-radius:8px;border:1px solid #444;background:#1a1a1a;color:white;font-size:16px}
button,.btn{display:block;width:100%;padding:14px;margin-top:16px;border:0;border-radius:8px;background:white;color:black;text-align:center;text-decoration:none;font-size:16px;font-weight:bold;cursor:pointer}
.btn2{background:#222;color:white;border:1px solid #555}.note{background:#141414;border:1px solid #333;border-radius:10px;padding:14px;line-height:2;overflow-wrap:anywhere}
footer{text-align:center;color:#999;border-top:1px solid #222;padding:24px 12px;margin-top:25px}
.small{font-size:13px;color:#aaa;overflow-wrap:anywhere}a{color:#fff}
@media(max-width:360px){.grid{grid-template-columns:1fr}}
</style>
"""

HOME = """<!doctype html><html lang="ar" dir="rtl"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#000"><title>RED ZONE UC | متجر شدات PUBG</title>""" + STYLE + """
</head><body><header><div class="logo">RED ZONE UC</div><div class="muted">متجر شدات PUBG MOBILE</div></header>
<main><h1>اشحن شداتك بسهولة</h1>
<p class="muted" style="text-align:center">اختار الباقة، اكتب ID اللاعب، وبعدها اتواصل معانا لتأكيد الطلب.</p>
<h2>باقات الشدات</h2><div class="grid">{% for p in packages %}
<div class="card"><div class="uc">{{p.uc}} UC</div><div class="price">{{p.price}} جنيه</div></div>{% endfor %}</div>
<h2>اطلب الشدات</h2><form method="post">
<input type="hidden" name="csrf" value="{{csrf}}">
<label for="uc">اختار الباقة</label><select name="uc" id="uc" required>{% for p in packages %}
<option value="{{p.uc}}">{{p.uc}} UC — {{p.price}} جنيه</option>{% endfor %}</select>
<label for="player_id">ID اللاعب في اللعبة</label><input id="player_id" name="player_id" inputmode="numeric" pattern="[0-9]+" maxlength="25" required placeholder="اكتب ID اللاعب">
<label for="phone">رقمك للتواصل</label><input id="phone" name="phone" type="tel" maxlength="20" required placeholder="رقم الموبايل">
<button type="submit">إنشاء الطلب</button></form>
{% if order %}<section class="panel"><h2>تفاصيل طلبك</h2>
<div class="note">رقم الطلب: <b>{{order.id}}</b><br>الباقة: {{order.uc}} UC<br>المبلغ: {{order.price}} جنيه<br>ID اللاعب: {{order.player_id}}<br>الحالة: {{order.status}}</div>
<div class="note"><b>الدفع بفودافون كاش</b><br>رقم المحفظة: <b dir="ltr">{{wallet}}</b><br>حوّل المبلغ، ثم ابعت رقم الطلب على واتساب.<br><b>لا ترسل الرقم السري أو كود OTP لأي شخص.</b></div>
<a class="btn" href="{{wa_link}}" target="_blank" rel="noopener">متابعة الطلب على واتساب</a>
<p class="muted">لا يتم الشحن إلا بعد التأكد من وصول المبلغ فعليًا. إنشاء الطلب لا يعني تأكيد الدفع.</p></section>{% endif %}
<section class="panel"><h2>التواصل والدفع</h2><p>واتساب: <span dir="ltr">01224773745</span></p><p>فودافون كاش: <span dir="ltr">{{wallet}}</span></p>
<a class="btn" href="https://wa.me/{{whatsapp}}" target="_blank" rel="noopener">تواصل معنا على واتساب</a></section>
<p class="muted">تأكد من صحة ID اللاعب ومن تفاصيل التحويل قبل الدفع.</p></main><footer>RED ZONE UC © 2026</footer></body></html>"""

LOGIN = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>دخول الإدارة</title>""" + STYLE + """
</head><body><header><div class="logo">RED ZONE UC</div><div class="muted">لوحة الإدارة</div></header><main><form method="post">
<h2>دخول صاحب المتجر</h2><input type="hidden" name="csrf" value="{{csrf}}">
<label>كلمة مرور الإدارة</label><input type="password" name="password" required>
<button>دخول</button>{% if error %}<p>{{error}}</p>{% endif %}
</form></main></body></html>"""

ADMIN = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>إدارة الطلبات</title>""" + STYLE + """
</head><body><header><div class="logo">RED ZONE UC</div><div class="muted">إدارة الطلبات</div></header><main>
<a class="btn btn2" href="{{url_for('logout')}}">تسجيل الخروج</a><h2>طلبات العملاء ({{orders|length}})</h2>
{% for o in orders %}<section class="panel"><b>طلب {{o.id}}</b><div class="note">الباقة: {{o.uc}} UC — {{o.price}} جنيه<br>ID اللاعب: {{o.player_id}}<br>رقم العميل: {{o.phone}}<br>التاريخ: {{o.created_at}}<br>الحالة: {{o.status}}</div>
<form method="post" action="{{url_for('update_order', oid=o.id)}}"><input type="hidden" name="csrf" value="{{csrf}}"><label>تغيير الحالة</label><select name="status">{% for s in statuses %}<option value="{{s}}" {% if s==o.status %}selected{% endif %}>{{s}}</option>{% endfor %}</select><button>حفظ الحالة</button></form></section>
{% else %}<p class="muted">مفيش طلبات لسه.</p>{% endfor %}</main></body></html>"""

@app.route("/", methods=["GET", "POST"])
def home():
    order = None
    wa_link = ""
    if request.method == "POST":
        verify_token()
        player_id = request.form.get("player_id", "").strip()
        phone = request.form.get("phone", "").strip()
        try:
            uc = int(request.form.get("uc", "0"))
        except ValueError:
            uc = 0
        package = next((p for p in PACKAGES if p["uc"] == uc), None)
        if package and player_id.isdigit() and re.fullmatch(r"[0-9+ ()-]{7,20}", phone):
            order = {"id": uuid.uuid4().hex[:8].upper(), "uc": uc,
                     "price": package["price"], "player_id": player_id,
                     "phone": phone, "status": STATUSES[0]}
            with get_db() as con:
                con.execute("INSERT INTO orders(id,player_id,phone,uc,price,status) VALUES(?,?,?,?,?,?)",
                            (order["id"], player_id, phone, uc, package["price"], order["status"]))
            message = (f"طلب جديد من {STORE_NAME}\\nرقم الطلب: {order['id']}\\n"
                       f"الباقة: {uc} UC\\nالسعر: {package['price']} جنيه\\n"
                       f"ID اللاعب: {player_id}\\nرقم العميل: {phone}\\nالدفع لم يتم تأكيده بعد")
            wa_link = f"https://wa.me/{WHATSAPP}?text={quote(message)}"
        else:
            abort(400, "البيانات غير صحيحة. ارجع وتأكد من الباقة وID اللاعب ورقم الهاتف.")
    return render_template_string(HOME, packages=PACKAGES, order=order, wa_link=wa_link,
                                  wallet=WALLET, whatsapp=WHATSAPP, csrf=token())

@app.route("/admin/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        verify_token()
        password_hash = os.environ.get("ADMIN_PASSWORD_HASH", "")
        if password_hash and check_password_hash(password_hash, request.form.get("password", "")):
            session.clear()
            session["admin"] = True
            session["csrf"] = secrets.token_hex(24)
            return redirect(url_for("admin"))
        error = "كلمة السر غير صحيحة أو لم يتم إعداد ADMIN_PASSWORD_HASH."
    return render_template_string(LOGIN, csrf=token(), error=error)

@app.route("/admin")
@admin_required
def admin():
    with get_db() as con:
        orders = con.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
    return render_template_string(ADMIN, orders=orders, statuses=STATUSES, csrf=token())

@app.route("/admin/order/<oid>", methods=["POST"])
@admin_required
def update_order(oid):
    verify_token()
    status = request.form.get("status", "")
    if status not in STATUSES:
        abort(400)
    with get_db() as con:
        con.execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
    return redirect(url_for("admin"))

@app.route("/admin/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False)
