from flask import Flask, render_template, redirect, url_for, request, jsonify
from config import Config
from models import db, User, Asset, Transaction
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import time
from datetime import datetime
import json
import os
import random

from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "index"

#Use threading (recommended)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# simple in-memory price cache to reduce API calls
_PRICE_CACHE_PATH = os.path.join(app.instance_path, "price_cache.json")
_price_cache = {"ts": 0.0, "prices": {}}
_PRICE_TTL_SECONDS = 30
_markets_cache = {"ts": 0.0, "data": []}
_MARKETS_TTL_SECONDS = 30
_DEFAULT_PRICE_MAP = {
    "USDT": 1.0,
    "USDC": 1.0,
    "CAD": 1.0,
    "BTC": 43000.0,
    "ETH": 2300.0,
    "SOL": 100.0,
    "XRP": 0.55,
    "BNB": 600.0,
    "LTC": 85.0,
    "DOGE": 0.12,
    "TRX": 0.12,
}

def _load_price_cache():
    try:
        if os.path.exists(_PRICE_CACHE_PATH):
            with open(_PRICE_CACHE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    _price_cache["ts"] = float(data.get("ts") or 0.0)
                    _price_cache["prices"] = dict(data.get("prices") or {})
    except Exception:
        pass

def _save_price_cache():
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        with open(_PRICE_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump({"ts": _price_cache["ts"], "prices": _price_cache["prices"]}, f)
    except Exception:
        pass

_load_price_cache()

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# -----------------------------
# Helpers
# -----------------------------
def is_admin():
    return current_user.is_authenticated and current_user.username.lower() == "admin"

def now_utc():
    return datetime.utcnow()

def log_tx(user_id, tx_type, coin, amount, status="CONFIRMED", note="", network=None):
    """
    Writes a Transaction row (this powers History + Deposit tables).
    """
    t = Transaction(
        user_id=user_id,
        type=tx_type,
        coin=coin.upper(),
        amount=float(amount),
        status=status,
        note=note or "",
        network=(network.upper() if network else None),
        created_at=now_utc()
    )
    db.session.add(t)
    db.session.commit()
    return t


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json() or {}

    firstname = (data.get("firstname") or "").strip()
    lastname  = (data.get("lastname") or "").strip()
    email     = (data.get("email") or "").strip().lower()
    username  = (data.get("username") or "").strip()
    password  = data.get("password") or ""
    confirm   = data.get("confirm_password") or ""

    if not all([firstname, lastname, email, username, password, confirm]):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if password != confirm:
        return jsonify({"success": False, "message": "Passwords do not match"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"success": False, "message": "Username already exists"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"success": False, "message": "Email already exists"}), 400

    hashed_password = generate_password_hash(password)

    user = User(
        username=username,
        firstname=firstname,
        lastname=lastname,
        email=email,
        password=hashed_password
    )

    db.session.add(user)
    db.session.commit()

    login_user(user)
    return jsonify({"success": True})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        login_user(user)
        return jsonify({"success": True})

    return jsonify({"success": False, "message": "Invalid username or password"}), 400


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=current_user.username)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))


# -----------------------------
# Markets
# -----------------------------
@app.route("/api/markets")
def get_markets_api():
    now = time.time()
    cache_fresh = (now - _markets_cache["ts"]) < _MARKETS_TTL_SECONDS
    if cache_fresh and _markets_cache["data"]:
        return jsonify(_markets_cache["data"])

    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {"vs_currency": "usd", "order": "market_cap_desc", "per_page": 10, "page": 1}
        res = requests.get(url, params=params, timeout=10)
        data = res.json() if res.ok else []

        coins = []
        for coin in (data or []):
            coins.append({
                "id": coin.get("id"),
                "name": coin.get("name"),
                "symbol": coin.get("symbol"),
                "image": coin.get("image"),
                "current_price": coin.get("current_price"),
                "high_24h": coin.get("high_24h"),
                "low_24h": coin.get("low_24h")
            })
        if coins:
            _markets_cache["data"] = coins
            _markets_cache["ts"] = now
        elif _markets_cache["data"]:
            return jsonify(_markets_cache["data"])
        else:
            fallback = []
            for sym in ("BTC", "ETH", "SOL", "XRP", "BNB"):
                price = _price_cache["prices"].get(sym) or _DEFAULT_PRICE_MAP.get(sym)
                fallback.append({
                    "id": sym.lower(),
                    "name": sym,
                    "symbol": sym.lower(),
                    "image": "",
                    "current_price": price,
                    "high_24h": None,
                    "low_24h": None
                })
            return jsonify(fallback)
        return jsonify(coins)
    except Exception:
        if _markets_cache["data"]:
            return jsonify(_markets_cache["data"])
        fallback = []
        for sym in ("BTC", "ETH", "SOL", "XRP", "BNB"):
            price = _price_cache["prices"].get(sym) or _DEFAULT_PRICE_MAP.get(sym)
            fallback.append({
                "id": sym.lower(),
                "name": sym,
                "symbol": sym.lower(),
                "image": "",
                "current_price": price,
                "high_24h": None,
                "low_24h": None
            })
        return jsonify(fallback)


# -----------------------------
# Assets (DB-backed)
# -----------------------------
@app.route("/api/assets")
@login_required
def api_assets():
    rows = Asset.query.filter_by(user_id=current_user.id).all()

    # Live price lookup via CoinGecko (no API key required)
    symbol_to_id = {
        "BTC": "bitcoin",
        "ETH": "ethereum",
        "SOL": "solana",
        "XRP": "ripple",
        "USDT": "tether",
        "USDC": "usd-coin",
        "BNB": "binancecoin",
        "LTC": "litecoin",
        "DOGE": "dogecoin",
        "TRX": "tron",
    }

    price_map = {}
    ids = []
    for r in rows:
        sym = (r.coin or "").upper()
        if sym in ("USD", "CAD"):
            price_map[sym] = 1.0
        elif sym in symbol_to_id:
            ids.append(symbol_to_id[sym])

    now = time.time()
    cache_fresh = (now - _price_cache["ts"]) < _PRICE_TTL_SECONDS
    if _price_cache["prices"]:
        price_map.update(_price_cache["prices"])

    if ids and (not cache_fresh or not _price_cache["prices"]):
        try:
            url = "https://api.coingecko.com/api/v3/simple/price"
            res = requests.get(url, params={"ids": ",".join(sorted(set(ids))), "vs_currencies": "usd"}, timeout=10)
            data = res.json() if res.ok else {}
            for sym, cid in symbol_to_id.items():
                if cid in data and "usd" in data[cid]:
                    price_map[sym] = float(data[cid]["usd"])
            _price_cache["prices"] = {
                k: v for k, v in price_map.items()
                if k in symbol_to_id or k in ("USD", "CAD")
            }
            _price_cache["ts"] = now
            _save_price_cache()
        except Exception:
            pass

    # final fallback to avoid zero values when rate-limited
    for r in rows:
        sym = (r.coin or "").upper()
        if sym not in price_map:
            price_map[sym] = _DEFAULT_PRICE_MAP.get(sym, 0.0)

    assets = []
    total = 0.0
    available = 0.0

    for r in rows:
        px = float(price_map.get(r.coin.upper(), 0))
        value = float(r.amount) * px
        if r.coin.upper() in ("USDT", "USD", "USDC", "CAD"):
            available += float(r.amount)

        assets.append({
            "coin": r.coin.upper(),
            "amount": float(r.amount),
            "value_usd": round(value, 2)
        })
        total += value

    return jsonify({
        "available_usd": round(available, 2),
        "total_usd": round(total, 2),
        "assets": assets
    })


# -----------------------------
# Orders (empty until real wiring)
# -----------------------------
@app.route("/api/orders")
@login_required
def api_orders():
    return jsonify([])


# -----------------------------
# Transactions (REAL: from DB)
# -----------------------------
@app.route("/api/transactions")
@login_required
def api_transactions():
    rows = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.created_at.asc())
        .all()
    )

    txs = []
    for t in rows:
        raw_type = (t.type or "").strip()
        tx_type = "DEPOSIT" if raw_type.lower() == "admin_adjust" else raw_type
        txs.append({
            "type": tx_type,
            "asset": t.coin,
            "coin": t.coin,
            "amount": float(t.amount),
            "status": t.status,
            "note": t.note or "",
            "network": t.network,
            "timestamp": t.created_at.isoformat() + "Z"
        })

    return jsonify(txs)


# -----------------------------
# Deposit address (custodial display)
# -----------------------------
@app.route("/api/deposit_address")
@login_required
def api_deposit_address():
    coin = (request.args.get("coin") or "USDT").upper().strip()
    network = (request.args.get("network") or "TRC20").upper().strip()

    book = app.config.get("DEPOSIT_ADDRESSES", {})
    addr = book.get(coin, {}).get(network)

    if not addr or "YOUR_" in addr:
        return jsonify({
            "success": False,
            "message": f"Deposit address not configured for {coin} on {network}."
        }), 400

    return jsonify({
        "success": True,
        "coin": coin,
        "network": network,
        "address": addr
    })


# -----------------------------
# Admin UI upgrade endpoints
# -----------------------------
@app.route("/api/admin/users")
@login_required
def admin_users():
    if not is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    users = User.query.order_by(User.username.asc()).all()
    return jsonify([{"username": u.username, "email": u.email} for u in users])


@app.route("/api/admin/user_assets")
@login_required
def admin_user_assets():
    if not is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    username = (request.args.get("username") or "").strip()
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    rows = Asset.query.filter_by(user_id=user.id).all()
    return jsonify({
        "success": True,
        "assets": [{"coin": r.coin.upper(), "amount": float(r.amount)} for r in rows]
    })


# -----------------------------
# Admin Set/Adjust (NOW logs into Transaction History)
# ✅ CHANGE: admin set/adjust should appear as DEPOSIT (per your request)
# -----------------------------
@app.route("/api/admin/set_asset", methods=["POST"])
@login_required
def admin_set_asset():
    if not is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    coin = (data.get("coin") or "").upper().strip()
    amount = float(data.get("amount") or 0)

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    row = Asset.query.filter_by(user_id=user.id, coin=coin).first()
    if not row:
        row = Asset(user_id=user.id, coin=coin, amount=0.0)
        db.session.add(row)

    row.amount = amount
    db.session.commit()

    # log history as DEPOSIT
    log_tx(
        user_id=user.id,
        tx_type="DEPOSIT",
        coin=coin,
        amount=amount,
        status="CONFIRMED",
        note=f"Admin set balance to {amount}"
    )

    return jsonify({"success": True, "coin": coin, "amount": row.amount})


@app.route("/api/admin/adjust_asset", methods=["POST"])
@login_required
def admin_adjust_asset():
    if not is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    coin = (data.get("coin") or "").upper().strip()
    delta = float(data.get("delta") or 0)

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    row = Asset.query.filter_by(user_id=user.id, coin=coin).first()
    if not row:
        row = Asset(user_id=user.id, coin=coin, amount=0.0)
        db.session.add(row)

    row.amount = float(row.amount) + delta
    db.session.commit()

    # log history as DEPOSIT (amount = delta)
    log_tx(
        user_id=user.id,
        tx_type="DEPOSIT",
        coin=coin,
        amount=delta,
        status="CONFIRMED",
        note="Admin adjusted balance"
    )

    return jsonify({"success": True, "coin": coin, "new_amount": row.amount})


# -----------------------------
# Deposit confirmations (admin creates a pending deposit)
# - Creates PENDING transaction
# - Background worker auto-confirms + credits asset
# -----------------------------
_deposit_worker_started = False

def deposit_worker():
    while True:
        try:
            with app.app_context():
                pendings = Transaction.query.filter_by(status="PENDING").all()
                for t in pendings:
                    # simple simulated confirmations: after 15 seconds → confirm
                    age = (now_utc() - t.created_at).total_seconds()
                    if age >= 15:
                        # credit user
                        row = Asset.query.filter_by(user_id=t.user_id, coin=t.coin).first()
                        if not row:
                            row = Asset(user_id=t.user_id, coin=t.coin, amount=0.0)
                            db.session.add(row)
                        row.amount = float(row.amount) + float(t.amount)

                        t.status = "CONFIRMED"
                        t.note = (t.note or "") + " | Auto-confirmed"
                        db.session.commit()
        except Exception:
            pass

        time.sleep(3)


@app.route("/api/admin/create_deposit", methods=["POST"])
@login_required
def admin_create_deposit():
    """
    Body:
    {
      "username": "patrick",
      "coin": "USDT",
      "amount": 50,
      "network": "TRC20"
    }
    Creates a PENDING deposit. Worker confirms after ~15s and credits balance.
    """
    if not is_admin():
        return jsonify({"success": False, "message": "Forbidden"}), 403

    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    coin = (data.get("coin") or "").upper().strip()
    amount = float(data.get("amount") or 0)
    network = (data.get("network") or "").upper().strip() or None

    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    t = log_tx(
        user_id=user.id,
        tx_type="DEPOSIT",
        coin=coin,
        amount=amount,
        status="PENDING",
        note="Awaiting confirmations",
        network=network
    )

    global _deposit_worker_started
    if not _deposit_worker_started:
        _deposit_worker_started = True
        socketio.start_background_task(deposit_worker)

    return jsonify({"success": True, "message": "Deposit created", "tx_id": t.id})


# -----------------------------
# /admin/assets (your existing form page) - keep it
# ✅ CHANGE: log as DEPOSIT too
# -----------------------------
@app.route("/admin/assets", methods=["GET", "POST"])
@login_required
def admin_assets_page():
    if current_user.username.lower() != "admin":
        return "Forbidden", 403

    if request.method == "GET":
        return render_template("admin_assets.html", message=None)

    username = (request.form.get("username") or "").strip()
    coin = (request.form.get("coin") or "").upper().strip()
    mode = (request.form.get("mode") or "set").strip()
    amount = float(request.form.get("amount") or 0)

    user = User.query.filter_by(username=username).first()
    if not user:
        return render_template("admin_assets.html", success=False, message="User not found.")

    row = Asset.query.filter_by(user_id=user.id, coin=coin).first()
    if not row:
        row = Asset(user_id=user.id, coin=coin, amount=0.0)
        db.session.add(row)

    if mode == "set":
        row.amount = amount
        db.session.commit()
        log_tx(user.id, "DEPOSIT", coin, amount, "CONFIRMED", f"Admin set balance to {amount}")
        return render_template("admin_assets.html", success=True, message=f"Set {username}'s {coin} to {row.amount}.")
    else:
        row.amount = float(row.amount) + amount
        db.session.commit()
        log_tx(user.id, "DEPOSIT", coin, amount, "CONFIRMED", "Admin adjusted balance")
        return render_template("admin_assets.html", success=True, message=f"Adjusted {username}'s {coin}. New balance: {row.amount}.")


# -----------------------------
# LIVE STREAM (SocketIO)
# -----------------------------
_streaming_started = False

def price_streamer():
    ids = ["bitcoin", "ethereum", "solana", "ripple"]
    url = "https://api.coingecko.com/api/v3/simple/price"

    while True:
        try:
            res = requests.get(
                url,
                params={"ids": ",".join(ids), "vs_currencies": "usd"},
                timeout=10
            )
            data = res.json()

            payload = {
                "BTC": float(data.get("bitcoin", {}).get("usd", 0)),
                "ETH": float(data.get("ethereum", {}).get("usd", 0)),
                "SOL": float(data.get("solana", {}).get("usd", 0)),
                "XRP": float(data.get("ripple", {}).get("usd", 0)),
                "ts": int(time.time() * 1000),
            }

            socketio.emit("ticker_update", payload)
        except Exception:
            pass

        socketio.sleep(1.5)


@socketio.on("connect")
def on_connect():
    global _streaming_started
    if not _streaming_started:
        _streaming_started = True
        socketio.start_background_task(price_streamer)

    emit("connected", {"ok": True})


if __name__ == "__main__":
    with app.app_context():
        db.create_all()

    socketio.run(app, debug=True)
