"""
Telegram Shop Bot (single file) - FINAL
- python-telegram-bot v20+ (async)
- Python 3.11/3.12 compatible (Termux, VPS, etc.)
- Features:
  * Button-only User panel: View Catalog, My Orders
  * Button-only Admin panel: Add/Delete/List Products, Add/List Payments,
    Ban/Unban, Pending Orders, All Orders, Complete Order
  * Buy flow: user selects product -> chooses payment -> uploads payment screenshot -> sends link (e.g., YouTube channel)
  * When user uploads BOTH screenshot + link, admin receives the screenshot (forwarded) with caption containing:
      User ID, Order ID, Product, Payment method, Link
    and an inline "☑️ Complete Order" button to mark order completed.
  * Admin notified when an order is created (awaiting proof) as well.
  * All data persisted to data.json
USAGE:
  - Set BOT_TOKEN and ADMIN_ID below
  - Install: pip install python-telegram-bot
  - Run: python telegram_shop_bot.py
"""

import os
import json
import logging
from uuid import uuid4
from functools import wraps
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    ConversationHandler,
    filters,
)

# --------------- CONFIG ---------------
BOT_TOKEN = "8291608976:AAEeii9LVk-fIGN9nkR7_7gBNPB-fhEDmjM"
ADMIN_ID = 7715257236  # replace with your Telegram numeric id
DATA_FILE = "data.json"
# ---------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ---------------- Data helpers ----------------
def load_data():
    if not os.path.exists(DATA_FILE):
        d = {"products": {}, "payments": {}, "orders": {}, "banned": []}
        save_data(d)
        return d
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(d):
    with open(DATA_FILE, "w") as f:
        json.dump(d, f, indent=2)

data = load_data()

def gen_id(prefix):
    return f"{prefix}_{uuid4().hex[:8]}"

# ---------------- Decorators ----------------
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        uid = update.effective_user.id if update.effective_user else None
        if uid != ADMIN_ID:
            if update.message:
                await update.message.reply_text("⚠️ Admin-only.")
            elif update.callback_query:
                await update.callback_query.answer("⚠️ Admin-only.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def check_banned(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        uid = update.effective_user.id if update.effective_user else None
        if uid and str(uid) in map(str, data.get("banned", [])):
            if update.message:
                await update.message.reply_text("🚫 You are banned. Contact admin.")
            elif update.callback_query:
                await update.callback_query.answer("🚫 You are banned.", show_alert=True)
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

# ---------------- User interface ----------------
@check_banned
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("🛒 View Catalog", callback_data="user_catalog")],
        [InlineKeyboardButton("📦 My Orders", callback_data="user_orders")],
    ]
    await update.message.reply_text("👋 Welcome — choose:", reply_markup=InlineKeyboardMarkup(kb))

@check_banned
async def user_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data
    uid_str = str(update.effective_user.id)

    if action == "user_catalog":
        if not data["products"]:
            await query.message.reply_text("📦 Catalog is empty.")
            return
        for pid, p in data["products"].items():
            text = f"*{p['title']}*\n💵 {p['price']}\n📝 {p['desc']}\n\nID: `{pid}`"
            kb = [[InlineKeyboardButton("🛒 Buy", callback_data=f"buy|{pid}")]]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN)

    elif action == "user_orders":
        lines = []
        for oid, o in data["orders"].items():
            if str(o.get("user")) == uid_str:
                prod = data["products"].get(o.get("product_id"), {}).get("title", o.get("product_name", "-"))
                link = o.get("link") or "-"
                status = o.get("status")
                lines.append(f"🆔 {oid} | {prod} | status: {status} | link: {link}")
        if not lines:
            await query.message.reply_text("You have no orders.")
        else:
            # chunking if long
            for i in range(0, len(lines), 30):
                await query.message.reply_text("\n".join(lines[i:i+30]))

# ---------------- Buy flow ----------------
@check_banned
async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User pressed Buy on a product."""
    query = update.callback_query
    await query.answer()
    _, pid = query.data.split("|", 1)
    product = data["products"].get(pid)
    if not product:
        await query.message.reply_text("❌ Product not found.")
        return
    if not data["payments"]:
        await query.message.reply_text("❌ No payment methods available. Contact admin.")
        return
    # show payment methods
    kb = [[InlineKeyboardButton(pay['name'], callback_data=f"pay|{pid}|{payid}")] for payid, pay in data["payments"].items()]
    await query.message.reply_text(
        f"You chose *{product['title']}* — {product['price']}\nChoose payment method:",
        reply_markup=InlineKeyboardMarkup(kb), parse_mode=ParseMode.MARKDOWN
    )

async def pay_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User chose a payment method -> create order and ask for screenshot."""
    query = update.callback_query
    await query.answer()
    _, pid, payid = query.data.split("|")
    product = data["products"].get(pid)
    pay = data["payments"].get(payid)
    if not product or not pay:
        await query.message.reply_text("❌ Invalid selection.")
        return
    oid = gen_id("ord")
    data["orders"][oid] = {
        "user": update.effective_user.id,
        "product_id": pid,
        "product_name": product.get("title"),
        "payment_id": payid,
        "payment_name": pay.get("name"),
        "status": "pending",         # pending -> awaiting proof & link
        "proof_file_id": None,
        "link": None,
        "ts": int(__import__("time").time()),
    }
    save_data(data)
    # instruct user
    await query.message.reply_text(
        f"💳 Payment method: *{pay.get('name')}*\n{pay.get('instructions')}\n\n"
        "1) Please pay using the above method.\n"
        "2) Upload a *photo* (payment screenshot) here as proof.\n"
        "3) After uploading photo, send the *link* (e.g., your YouTube channel URL).\n\n"
        f"Order ID: `{oid}`\n\n(We will notify admin after you upload both photo and link.)",
        parse_mode=ParseMode.MARKDOWN
    )
    # notify admin that a new order is created awaiting proof
    try:
        admin_text = (
            f"🆕 New order created (awaiting proof/link):\n"
            f"Order ID: `{oid}`\nUser: `{update.effective_user.id}`\n"
            f"Product: *{product.get('title')}*\nPayment: *{pay.get('name')}*"
        )
        await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.warning("Failed to notify admin about new order: %s", e)

# ---------------- Photo handler (payment screenshot) ----------------
@check_banned
async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User uploads photo proof. Save and prompt for link."""
    photos = update.message.photo
    if not photos:
        await update.message.reply_text("Please send a photo as proof.")
        return
    uid = str(update.effective_user.id)
    # find earliest pending order for this user
    pending_oid = None
    pending_ts = None
    for oid, o in data["orders"].items():
        if str(o.get("user")) == uid and o.get("status") == "pending":
            if pending_oid is None or o.get("ts", 0) < pending_ts:
                pending_oid = oid
                pending_ts = o.get("ts", 0)
    if not pending_oid:
        await update.message.reply_text("No pending orders found. Start a purchase from the catalog.")
        return
    file_id = photos[-1].file_id  # highest quality
    data["orders"][pending_oid]["proof_file_id"] = file_id
    # change status to awaiting_link
    data["orders"][pending_oid]["status"] = "awaiting_link"
    save_data(data)
    await update.message.reply_text(
        f"✅ Photo received for order `{pending_oid}`.\nNow please send the link (e.g., your YouTube channel URL) for this order.",
        parse_mode=ParseMode.MARKDOWN
    )

# ---------------- Link handler (user sends link after photo) ----------------
@check_banned
async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User sends the link (text). If there's an order awaiting_link, save link and forward to admin with photo."""
    txt = (update.message.text or "").strip()
    if not txt or txt.startswith("/"):
        # ignore commands or empty
        return
    uid = str(update.effective_user.id)
    # find earliest order in awaiting_link for this user
    awaiting_oid = None
    awaiting_ts = None
    for oid, o in data["orders"].items():
        if str(o.get("user")) == uid and o.get("status") == "awaiting_link":
            if awaiting_oid is None or o.get("ts", 0) < awaiting_ts:
                awaiting_oid = oid
                awaiting_ts = o.get("ts", 0)
    if not awaiting_oid:
        await update.message.reply_text("No order is awaiting a link. If you just paid, ensure you uploaded the photo first.")
        return
    # Save link and mark proof_uploaded
    data["orders"][awaiting_oid]["link"] = txt
    data["orders"][awaiting_oid]["status"] = "proof_uploaded"
    save_data(data)
    await update.message.reply_text(f"✅ Link received for order `{awaiting_oid}`. Admin will be notified.", parse_mode=ParseMode.MARKDOWN)

    # Forward photo and details to admin with inline Complete button
    order = data["orders"][awaiting_oid]
    prod_title = data["products"].get(order.get("product_id"), {}).get("title", order.get("product_name"))
    payment_name = data["payments"].get(order.get("payment_id"), {}).get("name", order.get("payment_name"))
    caption = (
        f"📸 Payment proof + link received\nOrder ID: `{awaiting_oid}`\nUser ID: `{order.get('user')}`\n"
        f"Product: *{prod_title}*\nPayment: *{payment_name}*\nLink: {order.get('link')}\n\n"
        "If everything is correct, press ✅ Complete Order."
    )
    kb = InlineKeyboardMarkup([[InlineKeyboardButton("☑️ Complete Order", callback_data=f"admin_complete|{awaiting_oid}")]])
    try:
        # send photo to admin
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=order.get("proof_file_id"), caption=caption, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
    except Exception as e:
        # fallback: send text if photo forward fails
        logger.warning("Could not forward photo to admin: %s", e)
        try:
            await context.bot.send_message(chat_id=ADMIN_ID, text=caption, parse_mode=ParseMode.MARKDOWN)
        except Exception as ee:
            logger.warning("Could not notify admin: %s", ee)

# ---------------- Admin panel & actions ----------------
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton("➕ Add Product", callback_data="admin_addprod")],
        [InlineKeyboardButton("❌ Delete Product", callback_data="admin_delprod")],
        [InlineKeyboardButton("📦 List Products", callback_data="admin_listprod")],
        [InlineKeyboardButton("💳 Add Payment", callback_data="admin_addpay")],
        [InlineKeyboardButton("🧾 List Payments", callback_data="admin_listpay")],
        [InlineKeyboardButton("🚫 Ban User", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Unban User", callback_data="admin_unban")],
        [InlineKeyboardButton("📋 Pending Orders", callback_data="admin_pending")],
        [InlineKeyboardButton("📊 All Orders", callback_data="admin_allorders")],
    ]
    if update.message:
        await update.message.reply_text("⚙️ Admin Panel", reply_markup=InlineKeyboardMarkup(kb))
    elif update.callback_query:
        await update.callback_query.message.reply_text("⚙️ Admin Panel", reply_markup=InlineKeyboardMarkup(kb))

# Conversation states for admin text inputs
ASK_ADDPROD, ASK_ADDPAY, ASK_BAN, ASK_UNBAN = range(4)

async def admin_actions_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data_cb = query.data

    # Add product: ask admin to send Title|Price|Description
    if data_cb == "admin_addprod":
        await query.message.reply_text("Send product as: Title|Price|Description")
        return ASK_ADDPROD

    # Delete product: show inline delete buttons
    if data_cb == "admin_delprod":
        if not data["products"]:
            await query.message.reply_text("No products to delete.")
            return ConversationHandler.END
        kb = [[InlineKeyboardButton(f"Delete: {p['title']}", callback_data=f"admin_del|{pid}")] for pid, p in data["products"].items()]
        await query.message.reply_text("Choose a product to delete:", reply_markup=InlineKeyboardMarkup(kb))
        return ConversationHandler.END

    # List products
    if data_cb == "admin_listprod":
        if not data["products"]:
            await query.message.reply_text("No products.")
        else:
            lines = [f"{pid} — {p['title']} | {p['price']}" for pid, p in data["products"].items()]
            for i in range(0, len(lines), 30):
                await query.message.reply_text("\n".join(lines[i:i+30]))
        return ConversationHandler.END

    # Add payment method
    if data_cb == "admin_addpay":
        await query.message.reply_text("Send payment as: Name|Instructions (e.g., UPI|upiid@bank - send and upload screenshot)")
        return ASK_ADDPAY

    # List payments
    if data_cb == "admin_listpay":
        if not data["payments"]:
            await query.message.reply_text("No payment methods.")
        else:
            lines = [f"{pid} — {p['name']} : {p['instructions']}" for pid, p in data["payments"].items()]
            await query.message.reply_text("\n".join(lines))
        return ConversationHandler.END

    # Ban user
    if data_cb == "admin_ban":
        await query.message.reply_text("Send user_id to ban:")
        return ASK_BAN

    # Unban user
    if data_cb == "admin_unban":
        await query.message.reply_text("Send user_id to unban:")
        return ASK_UNBAN

    # Pending orders (pending or proof_uploaded)
    if data_cb == "admin_pending":
        pending = []
        for oid, o in data["orders"].items():
            if o.get("status") in ("pending", "awaiting_link", "proof_uploaded"):
                prod_title = data["products"].get(o.get("product_id"), {}).get("title", o.get("product_name"))
                pending.append((oid, o.get("status"), o.get("user"), prod_title))
        if not pending:
            await query.message.reply_text("No pending orders.")
            return ConversationHandler.END
        for oid, status, user_id, prod_title in pending:
            text = f"🆔 {oid}\nUser: `{user_id}`\nProduct: *{prod_title}*\nStatus: `{status}`"
            kb = []
            if data["orders"][oid].get("status") == "proof_uploaded":
                kb = [[InlineKeyboardButton("☑️ Complete", callback_data=f"admin_complete|{oid}")]]
            await query.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb) if kb else None, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    # All orders
    if data_cb == "admin_allorders":
        if not data["orders"]:
            await query.message.reply_text("No orders yet.")
            return ConversationHandler.END
        lines = []
        for oid, o in data["orders"].items():
            prod = data["products"].get(o.get("product_id"), {}).get("title", o.get("product_name"))
            lines.append(f"{oid} | user:{o.get('user')} | product:{prod} | status:{o.get('status')}")
        for i in range(0, len(lines), 30):
            await query.message.reply_text("\n".join(lines[i:i+30]))
        return ConversationHandler.END

    await query.message.reply_text("Unknown admin action.")
    return ConversationHandler.END

# Admin text handlers
@admin_only
async def addprod_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if "|" not in txt:
        await update.message.reply_text("❌ Wrong format. Use: Title|Price|Description")
        return ConversationHandler.END
    title, price, desc = txt.split("|", 2)
    pid = gen_id("p")
    data["products"][pid] = {"title": title.strip(), "price": price.strip(), "desc": desc.strip()}
    save_data(data)
    await update.message.reply_text(f"✅ Product added: `{pid}`", parse_mode=ParseMode.MARKDOWN)
    return ConversationHandler.END

@admin_only
async def addpay_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if "|" not in txt:
        await update.message.reply_text("❌ Wrong format. Use: Name|Instructions")
        return ConversationHandler.END
    name, instr = txt.split("|", 1)
    payid = gen_id("pay")
    data["payments"][payid] = {"name": name.strip(), "instructions": instr.strip()}
    save_data(data)
    await update.message.reply_text(f"✅ Payment added: {name.strip()} (id: {payid})")
    return ConversationHandler.END

@admin_only
async def ban_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        uid = int(txt)
    except:
        await update.message.reply_text("❌ Send numeric user id.")
        return ConversationHandler.END
    if uid not in data["banned"]:
        data["banned"].append(uid)
        save_data(data)
    await update.message.reply_text(f"🚫 Banned {uid}")
    return ConversationHandler.END

@admin_only
async def unban_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.strip()
    try:
        uid = int(txt)
    except:
        await update.message.reply_text("❌ Send numeric user id.")
        return ConversationHandler.END
    if uid in data["banned"]:
        data["banned"].remove(uid)
        save_data(data)
    await update.message.reply_text(f"✅ Unbanned {uid}")
    return ConversationHandler.END

# Admin: delete product button handler (admin_del|pid)
@admin_only
async def admin_delete_product_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, pid = query.data.split("|", 1)
    if pid in data["products"]:
        title = data["products"][pid]["title"]
        del data["products"][pid]
        save_data(data)
        await query.message.reply_text(f"🗑 Deleted product {title} ({pid})")
    else:
        await query.message.reply_text("Product not found.")

# Admin: complete order (admin_complete|oid)
@admin_only
async def admin_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, oid = query.data.split("|", 1)
    if oid not in data["orders"]:
        await query.message.reply_text("Order not found.")
        retur