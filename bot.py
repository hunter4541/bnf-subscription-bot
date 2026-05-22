import os
import time
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask
from threading import Thread

# ---------------- KEEP ALIVE ---------------- #

app = Flask('')

@app.route('/')
def home():
    return "BNF Subscription Bot Running!"

def run_web():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    Thread(target=run_web).start()

# ---------------- CONFIG ---------------- #

BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
ADMIN_ID = int(os.getenv('ADMIN_ID'))
UPI_ID = os.getenv('UPI_ID')
CONTACT_USERNAME = os.getenv('CONTACT_USERNAME')
GROUP_ID = int(os.getenv('GROUP_ID'))

bot = telebot.TeleBot(BOT_TOKEN)

client = MongoClient(MONGO_URI)

db = client['sub_management']

channels_col = db['channels']
users_col = db['users']

# ---------------- START ---------------- #

@bot.message_handler(commands=['start'])
def start_handler(message):

    user_id = message.from_user.id
    text = message.text.split()

    if len(text) > 1:

        try:

            ch_id = int(text[1])

            ch_data = channels_col.find_one({
                "channel_id": ch_id
            })

        except:

            ch_data = channels_col.find_one({
                "admin_id": ADMIN_ID
            })

    else:

        ch_data = channels_col.find_one({
            "admin_id": ADMIN_ID
        })

    # ---------------- ADMIN PANEL ---------------- #

    if user_id == ADMIN_ID:

        markup = InlineKeyboardMarkup(row_width=1)

        markup.add(
            InlineKeyboardButton(
                "📊 Revenue Dashboard",
                callback_data="revenue_dashboard"
            )
        )

        markup.add(
            InlineKeyboardButton(
                "💳 Subscription",
                callback_data="subscription_panel"
            )
        )

        markup.add(
            InlineKeyboardButton(
                "📢 Channels",
                callback_data="show_channels"
            )
        )

        bot.send_message(
            message.chat.id,
            "✅ *BNF ADMIN PANEL*",
            parse_mode="Markdown",
            reply_markup=markup
        )

        return
        
        if ch_data:

        markup = InlineKeyboardMarkup()

        for p_time, p_price in ch_data['plans'].items():

            if int(p_time) < 1440:
                label = f"{p_time} Minutes"
            else:
                label = f"{int(p_time)//1440} Days"

            markup.add(
                InlineKeyboardButton(
                    f"💳 {label} - ₹{p_price}",
                    callback_data=f"select_{ch_data['channel_id']}_{p_time}"
                )
            )

        markup.add(
            InlineKeyboardButton(
                "📞 Contact Admin",
                url=f"https://t.me/{CONTACT_USERNAME}"
            )
        )

        # ---------------- WELCOME BANNER ---------------- #

        photo_url = "AgACAgUAAxkBAAPyahBLa4soS8L_x4xErVC6xRoLdFcAArMQaxteyIFUqkNYNrlnSPgBAAMCAAN5AAM7BA"

        bot.send_photo(
            message.chat.id,
            photo=photo_url,
            caption=
            f"🔥 *Welcome To BNF PRIVATE COMMUNITY*\n\n"
            f"📢 *{ch_data['name']}*\n\n"
            f"✅ Daily Market Analysis\n"
            f"✅ Live Trading Sessions\n"
            f"✅ MRC Strategy Setup\n"
            f"✅ Premium Trade Alerts\n"
            f"✅ Risk Management\n"
            f"✅ Private Community Access\n"
            f"✅ Q&A Support\n\n"
            f"Select your subscription plan below:",
            reply_markup=markup,
            parse_mode="Markdown"
        )

        return

    if user_id == ADMIN_ID:

        bot.send_message(
            message.chat.id,
            "✅ *BNF Admin Panel Active*\n\n"
            "/add - Add Channel\n"
            "/channels - Manage Channels\n"
            "/myplan - Check Subscription\n"
            "/report - Monthly Report",
            parse_mode="Markdown"
        )

    else:

        bot.send_message(
            message.chat.id,
            "❌ No subscription plans available."
        )

# ---------------- MY PLAN ---------------- #

@bot.message_handler(commands=['myplan'])
def my_plan(message):

    user = users_col.find_one({
        "user_id": message.from_user.id
    })

    if not user:

        bot.send_message(
            message.chat.id,
            "❌ No active subscription found."
        )

        return

    expiry = datetime.fromtimestamp(user['expiry'])

    remaining = expiry - datetime.now()

    if remaining.total_seconds() <= 0:

        bot.send_message(
            message.chat.id,
            "❌ Your subscription has expired."
        )

        return

    days = remaining.days
    hours = remaining.seconds // 3600
    minutes = (remaining.seconds % 3600) // 60

    ch_data = channels_col.find_one({
        "channel_id": user['channel_id']
    })

    bot.send_message(
        message.chat.id,
        f"📢 Your Active Plan\n\n"
        f"📢 Channel: {ch_data['name']}\n\n"
        f"📅 Expiry Date:\n"
        f"{expiry.strftime('%d %B %Y - %I:%M %p')}\n\n"
        f"⏳ Remaining Time:\n"
        f"{days} Days {hours} Hours {minutes} Minutes"
    )

# ---------------- MONTHLY REPORT ---------------- #

@bot.message_handler(commands=['report'])
def monthly_report(message):

    if message.from_user.id != ADMIN_ID:
        return

    now = datetime.now()

    month_start = datetime(
        now.year,
        now.month,
        1
    ).timestamp()

    users = list(users_col.find({
        "buy_date": {
            "$gte": month_start
        }
    }))

    total_buyers = len(users)

    total_collection = sum(
        user.get("price", 0)
        for user in users
    )

    month_name = now.strftime("%B").upper()

    bot.send_message(
        ADMIN_ID,
        f"📊 BNF MONTHLY REPORT\n\n"
        f"📅 This Month ({month_name})\n\n"
        f"👥 BUYERS: {total_buyers}\n"
        f"💰 COLLECTION: ₹{total_collection}"
    )

# ---------------- AUTO MONTHLY REPORT ---------------- #

def send_monthly_report():

    now = datetime.now()

    month_start = datetime(
        now.year,
        now.month,
        1
    ).timestamp()

    users = list(users_col.find({
        "buy_date": {
            "$gte": month_start
        }
    }))

    total_buyers = len(users)

    total_collection = sum(
        user.get("price", 0)
        for user in users
    )

    month_name = now.strftime("%B").upper()

    bot.send_message(
        ADMIN_ID,
        f"📊 MONTHLY REPORT CLOSED\n\n"
        f"📅 {month_name} {now.year}\n\n"
        f"👥 TOTAL BUYERS: {total_buyers}\n"
        f"💰 TOTAL COLLECTION: ₹{total_collection}"
    )

# ---------------- REVENUE DASHBOARD ---------------- #

@bot.callback_query_handler(func=lambda call: call.data == "revenue_dashboard")
def revenue_dashboard(call):

    if call.from_user.id != ADMIN_ID:
        return

    now = datetime.now()

    text = "📊 *REVENUE DASHBOARD*\n\n"

    for i in range(3, 0, -1):

        month = now.month - i

        year = now.year

        if month <= 0:
            month += 12
            year -= 1

        start_date = datetime(year, month, 1)

        if month == 12:
            end_date = datetime(year + 1, 1, 1)

        else:
            end_date = datetime(year, month + 1, 1)

        users = list(users_col.find({
            "buy_date": {
                "$gte": start_date.timestamp(),
                "$lt": end_date.timestamp()
            }
        }))

        buyers = len(users)

        collection = sum(
            int(user.get("price", 0))
            for user in users
        )

        text += (
            f"📊 MONTHLY REPORT CLOSED\n"
            f"📅 {start_date.strftime('%b %Y').upper()}\n"
            f"👥 TOTAL BUYERS: {buyers}\n"
            f"💰 TOTAL COLLECTION: ₹{collection}\n"
            f"__________________________________\n\n"
        )

    current_month_start = datetime(
        now.year,
        now.month,
        1
    )

    if now.month == 12:

        next_month = datetime(now.year + 1, 1, 1)

    else:

        next_month = datetime(now.year, now.month + 1, 1)

    remaining = next_month - now

    days = remaining.days

    hours = remaining.seconds // 3600

    minutes = (remaining.seconds % 3600) // 60

    current_users = list(users_col.find({
        "buy_date": {
            "$gte": current_month_start.timestamp()
        }
    }))

    current_buyers = len(current_users)

    current_collection = sum(
        int(user.get("price", 0))
        for user in current_users
    )

    text += (
        f"🔴 LIVE\n"
        f"📅 CURRENT MONTH: {now.strftime('%b %Y').upper()}\n\n"
        f"⏳ MONTH END COUNTDOWN:\n"
        f"{days} Days {hours} Hours {minutes} Minutes\n\n"
        f"👥 CURRENT BUYERS: {current_buyers}\n"
        f"💰 CURRENT COLLECTION: ₹{current_collection}"
    )

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "show_channels")
def show_channels(call):

    if call.from_user.id != ADMIN_ID:
        return

    markup = InlineKeyboardMarkup()

    cursor = channels_col.find({
        "admin_id": ADMIN_ID
    })

    for ch in cursor:

        markup.add(
            InlineKeyboardButton(
                f"📢 {ch['name']}",
                callback_data=f"manage_{ch['channel_id']}"
            )
        )

    markup.add(
        InlineKeyboardButton(
            "➕ Add New Channel",
            callback_data="add_new"
        )
    )

    bot.edit_message_text(
        "📢 *CHANNEL MANAGEMENT*",
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown",
        reply_markup=markup
    )

# ---------------- CHANNEL LIST ---------------- #

@bot.message_handler(commands=['channels'], func=lambda m: m.from_user.id == ADMIN_ID)
def list_channels(message):

    markup = InlineKeyboardMarkup()

    cursor = channels_col.find({
        "admin_id": ADMIN_ID
    })

    count = 0

    for ch in cursor:

        markup.add(
            InlineKeyboardButton(
                f"{ch['name']}",
                callback_data=f"manage_{ch['channel_id']}"
            )
        )

        count += 1

    markup.add(
        InlineKeyboardButton(
            "➕ Add New Channel",
            callback_data="add_new"
        )
    )

    if count == 0:

        bot.send_message(
            ADMIN_ID,
            "No channels found.",
            reply_markup=markup
        )

    else:

        bot.send_message(
            ADMIN_ID,
            "📢 Your Channels:",
            reply_markup=markup
        )

# ---------------- ADD CHANNEL ---------------- #

@bot.message_handler(commands=['add'], func=lambda m: m.from_user.id == ADMIN_ID)
def add_channel_start(message):

    msg = bot.send_message(
        ADMIN_ID,
        "📩 Forward any message from your private channel."
    )

    bot.register_next_step_handler(msg, get_plans)

@bot.callback_query_handler(func=lambda call: call.data == "add_new")
def cb_add_new(call):

    bot.answer_callback_query(call.id)

    msg = bot.send_message(
        ADMIN_ID,
        "📩 Forward any message from your channel."
    )

    bot.register_next_step_handler(msg, get_plans)

# ---------------- GET PLANS ---------------- #

def get_plans(message):

    if message.forward_from_chat:

        ch_id = message.forward_from_chat.id
        ch_name = message.forward_from_chat.title

        msg = bot.send_message(
            ADMIN_ID,
            f"📢 Channel Detected:\n*{ch_name}*\n\n"
            f"Enter plans:\n\n"
            f"`1440:399, 43200:999`\n\n"
            f"1440 = 1 Day\n"
            f"43200 = 30 Days",
            parse_mode="Markdown"
        )

        bot.register_next_step_handler(
            msg,
            finalize_channel,
            ch_id,
            ch_name
        )

    else:

        bot.send_message(
            ADMIN_ID,
            "❌ Forwarded message not detected."
        )

# ---------------- SAVE CHANNEL ---------------- #

def finalize_channel(message, ch_id, ch_name):

    try:

        raw_plans = message.text.split(',')

        plans_dict = {}

        for p in raw_plans:

            t, pr = p.strip().split(':')

            plans_dict[t] = pr

        channels_col.update_one(
            {
                "channel_id": ch_id
            },
            {
                "$set": {
                    "name": ch_name,
                    "plans": plans_dict,
                    "admin_id": ADMIN_ID
                }
            },
            upsert=True
        )

        bot_username = bot.get_me().username

        bot.send_message(
            ADMIN_ID,
            f"✅ Setup Successful!\n\n"
            f"🔗 Invite Link:\n\n"
            f"`https://t.me/{bot_username}?start={ch_id}`",
            parse_mode="Markdown"
        )

    except:

        bot.send_message(
            ADMIN_ID,
            "❌ Invalid format."
        )

# ---------------- PAYMENT FLOW ---------------- #

@bot.callback_query_handler(func=lambda call: call.data.startswith('select_'))
def user_pays(call):

    _, ch_id, mins = call.data.split('_')

    ch_data = channels_col.find_one({
        "channel_id": int(ch_id)
    })

    price = ch_data['plans'][mins]

    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=upi://pay?pa={UPI_ID}%26pn=BNFTRADE%26tn=Subscription%26am={price}%26cu=INR"

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ I Have Paid",
            callback_data=f"paid_{ch_id}_{mins}"
        )
    )

    markup.add(
        InlineKeyboardButton(
            "📞 Contact Admin",
            url=f"https://t.me/{CONTACT_USERNAME}"
        )
    )

    bot.send_photo(
        call.message.chat.id,
        qr_url,
        caption=
        f"💳 Payment Details\n\n"
        f"⏳ Plan: {mins} Minutes\n"
        f"💰 Price: ₹{price}\n"
        f"🏦 UPI ID: {UPI_ID}\n\n"
        f"Complete payment and click below.",
        reply_markup=markup
    )

# ---------------- ASK UPI NAME ---------------- #

@bot.callback_query_handler(func=lambda call: call.data.startswith('paid_'))
def ask_upi_name(call):

    _, ch_id, mins = call.data.split('_')

    msg = bot.send_message(
        call.message.chat.id,
        "✍️ Send your UPI payment name.\n\nExample:\nRohit Sharma"
    )

    bot.register_next_step_handler(
        msg,
        admin_notify,
        ch_id,
        mins
    )

# ---------------- ADMIN VERIFY ---------------- #

def admin_notify(message, ch_id, mins):

    upi_name = message.text

    user = message.from_user

    ch_data = channels_col.find_one({
        "channel_id": int(ch_id)
    })

    price = ch_data['plans'][mins]

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "✅ Approve",
            callback_data=f"app_{user.id}_{ch_id}_{mins}"
        ),
        InlineKeyboardButton(
            "❌ Reject",
            callback_data=f"rej_{user.id}_{ch_id}"
        )
    )

    bot.send_message(
        ADMIN_ID,
        f"🔔 Payment Verification Required!\n\n"
        f"👤 User: {user.first_name}\n"
        f"🆔 User ID: {user.id}\n"
        f"🏦 UPI Name: {upi_name}\n"
        f"📢 Channel: {ch_data['name']}\n"
        f"⏳ Plan: {mins} Minutes\n"
        f"💰 Price: ₹{price}",
        reply_markup=markup
    )

    bot.send_message(
        message.chat.id,
        "✅ Payment submitted.\nPlease wait for admin verification."
    )

# ---------------- APPROVE USER ---------------- #

@bot.callback_query_handler(func=lambda call: call.data.startswith('app_'))
def approve_now(call):

    if call.from_user.id != ADMIN_ID:
        return

    _, u_id, ch_id, mins = call.data.split('_')

    u_id = int(u_id)
    ch_id = int(ch_id)
    mins = int(mins)

    try:

        expiry_datetime = datetime.now() + timedelta(minutes=mins)

        expiry_ts = int(expiry_datetime.timestamp())

        channel_link = bot.create_chat_invite_link(
            ch_id,
            member_limit=1,
            expire_date=expiry_ts
        )

        group_link = bot.create_chat_invite_link(
            GROUP_ID,
            member_limit=1,
            expire_date=expiry_ts
        )

        plan_price = int(
            channels_col.find_one({
                "channel_id": ch_id
            })['plans'][str(mins)]
        )

        users_col.update_one(
            {
                "user_id": u_id,
                "channel_id": ch_id
            },
            {
                "$set": {
                    "expiry": expiry_datetime.timestamp(),
                    "price": plan_price,
                    "buy_date": datetime.now().timestamp()
                }
            },
            upsert=True
        )

        expiry_text = expiry_datetime.strftime("%d %B %Y - %I:%M %p")

        bot.send_message(
            u_id,
            f"🥳 Payment Approved!\n\n"
            f"📢 Main Channel:\n"
            f"{channel_link.invite_link}\n\n"
            f"💬 Chats Group:\n"
            f"{group_link.invite_link}\n\n"
            f"📅 Expiry Date:\n"
            f"{expiry_text}\n\n"
            f"⏳ Subscription activated successfully."
        )

        bot.edit_message_text(
            f"✅ Approved User {u_id}",
            call.message.chat.id,
            call.message.message_id
        )

    except Exception as e:

        bot.send_message(
            ADMIN_ID,
            f"❌ Error:\n{e}"
        )

# ---------------- REJECT PAYMENT ---------------- #

@bot.callback_query_handler(func=lambda call: call.data.startswith('rej_'))
def reject_payment(call):

    if call.from_user.id != ADMIN_ID:
        return

    _, u_id, ch_id = call.data.split('_')

    u_id = int(u_id)
    ch_id = int(ch_id)

    bot_username = bot.get_me().username

    retry_link = f"https://t.me/{bot_username}?start={ch_id}"

    markup = InlineKeyboardMarkup()

    markup.add(
        InlineKeyboardButton(
            "🔄 Pay Again",
            url=retry_link
        )
    )

    bot.send_message(
        u_id,
        "❌ Payment Rejected!\n\nPlease complete payment correctly and submit again.",
        reply_markup=markup
    )

    bot.edit_message_text(
        f"❌ Rejected User {u_id}",
        call.message.chat.id,
        call.message.message_id
    )


# ---------------- SUBSCRIPTION PANEL ---------------- #

@bot.callback_query_handler(func=lambda call: call.data == "subscription_panel")
def subscription_panel(call):

    if call.from_user.id != ADMIN_ID:
        return

    channels = list(channels_col.find({
        "admin_id": ADMIN_ID
    }))

    text = "💳 *SUBSCRIPTION PLANS*\n\n"

    for ch in channels:

        text += f"📢 {ch['name']}\n"

        for t, p in ch['plans'].items():

            if int(t) >= 1440:

                label = f"{int(t)//1440} Days"

            else:

                label = f"{t} Minutes"

            text += f"• {label} → ₹{p}\n"

        text += "\n"

    text += "⚡ Edit system coming next."

    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode="Markdown"
    )

# ---------------- MANAGE CHANNEL ---------------- #

@bot.callback_query_handler(func=lambda call: call.data.startswith('manage_'))
def manage_ch(call):

    ch_id = int(call.data.split('_')[1])

    ch_data = channels_col.find_one({
        "channel_id": ch_id
    })

    bot_username = bot.get_me().username

    link = f"https://t.me/{bot_username}?start={ch_id}"

    bot.edit_message_text(
        f"📢 {ch_data['name']}\n\n"
        f"🔗 Invite Link:\n"
        f"{link}",
        call.message.chat.id,
        call.message.message_id
    )

# ---------------- AUTO REMOVE EXPIRED USERS ---------------- #

def kick_expired_users():

    now = datetime.now().timestamp()

    expired_users = users_col.find({
        "expiry": {
            "$lte": now
        }
    })

    bot_username = bot.get_me().username

    for user in expired_users:

        try:

            bot.ban_chat_member(
                user['channel_id'],
                user['user_id']
            )

            bot.unban_chat_member(
                user['channel_id'],
                user['user_id']
            )

            bot.ban_chat_member(
                GROUP_ID,
                user['user_id']
            )

            bot.unban_chat_member(
                GROUP_ID,
                user['user_id']
            )

            rejoin_url = f"https://t.me/{bot_username}?start={user['channel_id']}"

            markup = InlineKeyboardMarkup()

            markup.add(
                InlineKeyboardButton(
                    "🔄 Renew Subscription",
                    url=rejoin_url
                )
            )

            bot.send_message(
                user['user_id'],
                "⚠️ Your subscription has expired.\n\nRenew to continue access.",
                reply_markup=markup
            )

            users_col.delete_one({
                "_id": user['_id']
            })

        except Exception as e:
            print(e)

# ---------------- AUTO DELETE JOIN/LEFT MSG ---------------- #

@bot.message_handler(
    content_types=[
        'new_chat_members',
        'left_chat_member'
    ]
)
def delete_service_messages(message):

    try:

        bot.delete_message(
            message.chat.id,
            message.message_id
        )

    except Exception as e:
        print(e)

# ---------------- START BOT ---------------- #

if __name__ == '__main__':

    keep_alive()

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        kick_expired_users,
        'interval',
        minutes=1
    )

    scheduler.add_job(
        send_monthly_report,
        'cron',
        day='last',
        hour=23,
        minute=59
    )

    scheduler.start()

    bot.remove_webhook()

    print("BNF BOT RUNNING...")

    while True:

        try:

            bot.infinity_polling(
                timeout=10,
                long_polling_timeout=5,
                skip_pending=True
            )

        except Exception as e:

            print(f"Polling Error: {e}")
            time.sleep(5)
