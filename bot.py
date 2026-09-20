import os
import requests
import telebot
import re
import time
import threading
import html
from concurrent.futures import ThreadPoolExecutor
from telebot import types

# ──────────────────────────────────────────────────────────
# কনফিগারেশন
# ──────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
API_KEY = "M7ZGAANAJK4"
API_URL = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/getnum"
OTP_API_URL = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/success-otp"
LIVE_TRAFFIC_API = "https://api.2oo9.cloud/MXS47FLFX0U/tnevs/@public/api/console"

ADMIN_ID = 6625019627

# 🕒 Change Number কুলডাউন কনফিগারেশন
user_last_change = {}  # {user_id: timestamp}
CHANGE_COOLDOWN = 3  # সেকেন্ড

bot = telebot.TeleBot(BOT_TOKEN, num_threads=100)

# ──────────────────────────────────────────────────────────
# 🔢 প্রতিটা ইউজার কতগুলো নাম্বার একসাথে পাবে (/get1 থেকে /get10 দিয়ে সেট হয়)
# ──────────────────────────────────────────────────────────
user_get_count = {}   # {user_id: N}
DEFAULT_GET_COUNT = 5
MAX_GET_COUNT = 10

# ──────────────────────────────────────────────────────────
# 🛠 এডমিন-ম্যানেজড সার্ভিস সিস্টেম
# services = {"Facebook": {"BD": "224655XXX", "IN": "919876XXX"}, "WhatsApp": {}}
# প্রতিটা সার্ভিসের ভেতরে একাধিক দেশ থাকতে পারে, প্রতিটা দেশের নিজস্ব রেঞ্জ
# ──────────────────────────────────────────────────────────
services = {}
admin_waiting = {}  # {ADMIN_ID: "add_service" | "set_range:<service_name>" | "remove_range:<service_name>"}

# 🔗 Support বাটনের লিংক
SUPPORT_LINK = "https://t.me/sourav539171"

# 🔥 Live Traffic এ শুধু এই সার্ভিসগুলোই দেখানো হবে (case-insensitive ম্যাচ)
ALLOWED_TRAFFIC_SERVICES = ["Facebook", "WhatsApp", "Instagram", "Telegram", "Imo"]

def normalize_service_name(sid):
    """API থেকে আসা sid টা allowed লিস্টের সাথে মিললে ক্যানোনিকাল নাম রিটার্ন করে, না মিললে None"""
    for allowed in ALLOWED_TRAFFIC_SERVICES:
        if sid.strip().lower() == allowed.lower():
            return allowed
    return None

# 🔁 Change Number বাটনের জন্য সেশন ট্র্যাকিং (service/country নাম callback_data এ সরাসরি না বসিয়ে)
change_sessions = {}  # {session_id: (service_name, country_iso, count)}
_session_counter = 0
_session_lock = threading.Lock()

def new_session(service_name, country_iso, count):
    global _session_counter
    with _session_lock:
        _session_counter += 1
        sid = _session_counter
    change_sessions[sid] = (service_name, country_iso, count)
    return sid

SERVICE_EMOJI = {
    "facebook": "📘", "whatsapp": "💚", "instagram": "📷", "telegram": "✈️",
    "google": "🔴", "gmail": "🔴", "tiktok": "🎵", "twitter": "🐦", "x": "🐦",
    "snapchat": "👻", "discord": "🎮", "amazon": "📦", "paypal": "💳",
    "netflix": "🎬", "apple": "🍎", "microsoft": "🪟", "linkedin": "💼",
    "yahoo": "🟣", "binance": "🟡", "line": "💬", "wechat": "💬", "viber": "💜",
    "signal": "🔵",
}

def service_emoji(name):
    key = name.strip().lower()
    return SERVICE_EMOJI.get(key, "📨")

# ──────────────────────────────────────────────────────────
# 🌍 Country Flag + Service Detect
# ──────────────────────────────────────────────────────────
COUNTRY_FLAGS = {
    "1": ("🇺🇸", "US"), "20": ("🇪🇬", "EG"), "27": ("🇿🇦", "ZA"), "30": ("🇬🇷", "GR"), "31": ("🇳🇱", "NL"),
    "32": ("🇧🇪", "BE"), "33": ("🇫🇷", "FR"), "34": ("🇪🇸", "ES"), "36": ("🇭🇺", "HU"), "39": ("🇮🇹", "IT"),
    "40": ("🇷🇴", "RO"), "41": ("🇨🇭", "CH"), "43": ("🇦🇹", "AT"), "44": ("🇬🇧", "GB"), "45": ("🇩🇰", "DK"),
    "46": ("🇸🇪", "SE"), "47": ("🇳🇴", "NO"), "48": ("🇵🇱", "PL"), "49": ("🇩🇪", "DE"), "51": ("🇵🇪", "PE"),
    "52": ("🇲🇽", "MX"), "53": ("🇨🇺", "CU"), "54": ("🇦🇷", "AR"), "55": ("🇧🇷", "BR"), "56": ("🇨🇱", "CL"),
    "57": ("🇨🇴", "CO"), "58": ("🇻🇪", "VE"), "60": ("🇲🇾", "MY"), "61": ("🇦🇺", "AU"), "62": ("🇮🇩", "ID"),
    "63": ("🇵🇭", "PH"), "64": ("🇳🇿", "NZ"), "65": ("🇸🇬", "SG"), "66": ("🇹🇭", "TH"), "7": ("🇷🇺", "RU"),
    "81": ("🇯🇵", "JP"), "82": ("🇰🇷", "KR"), "84": ("🇻🇳", "VN"), "86": ("🇨🇳", "CN"), "90": ("🇹🇷", "TR"),
    "91": ("🇮🇳", "IN"), "92": ("🇵🇰", "PK"), "93": ("🇦🇫", "AF"), "94": ("🇱🇰", "LK"), "95": ("🇲🇲", "MM"),
    "98": ("🇮🇷", "IR"), "211": ("🇸🇸", "SS"), "212": ("🇲🇦", "MA"), "213": ("🇩🇿", "DZ"), "216": ("🇹🇳", "TN"),
    "218": ("🇱🇾", "LY"), "220": ("🇬🇲", "GM"), "221": ("🇸🇳", "SN"), "222": ("🇲🇷", "MR"), "223": ("🇲🇱", "ML"),
    "224": ("🇬🇳", "GN"), "225": ("🇨🇮", "CI"), "226": ("🇧🇫", "BF"), "227": ("🇳🇪", "NE"), "228": ("🇹🇬", "TG"),
    "229": ("🇧🇯", "BJ"), "230": ("🇲🇺", "MU"), "231": ("🇱🇷", "LR"), "232": ("🇸🇱", "SL"), "233": ("🇬🇭", "GH"),
    "234": ("🇳🇬", "NG"), "235": ("🇹🇩", "TD"), "236": ("🇨🇫", "CF"), "237": ("🇨🇲", "CM"), "238": ("🇨🇻", "CV"),
    "239": ("🇸🇹", "ST"), "240": ("🇬🇶", "GQ"), "241": ("🇬🇦", "GA"), "242": ("🇨🇬", "CG"), "243": ("🇨🇩", "CD"),
    "244": ("🇦🇴", "AO"), "245": ("🇬🇼", "GW"), "246": ("🇮🇴", "IO"), "248": ("🇸🇨", "SC"), "249": ("🇸🇩", "SD"),
    "250": ("🇷🇼", "RW"), "251": ("🇪🇹", "ET"), "252": ("🇸🇴", "SO"), "253": ("🇩🇯", "DJ"), "254": ("🇰🇪", "KE"),
    "255": ("🇹🇿", "TZ"), "256": ("🇺🇬", "UG"), "257": ("🇧🇮", "BI"), "258": ("🇲🇿", "MZ"), "260": ("🇿🇲", "ZM"),
    "261": ("🇲🇬", "MG"), "262": ("🇷🇪", "RE"), "263": ("🇿🇼", "ZW"), "264": ("🇳🇦", "NA"), "265": ("🇲🇼", "MW"),
    "266": ("🇱🇸", "LS"), "267": ("🇧🇼", "BW"), "268": ("🇸🇿", "SZ"), "269": ("🇰🇲", "KM"), "290": ("🇸🇭", "SH"),
    "291": ("🇪🇷", "ER"), "297": ("🇦🇼", "AW"), "298": ("🇫🇴", "FO"), "299": ("🇬🇱", "GL"), "350": ("🇬🇮", "GI"),
    "351": ("🇵🇹", "PT"), "352": ("🇱🇺", "LU"), "353": ("🇮🇪", "IE"), "354": ("🇮🇸", "IS"), "355": ("🇦🇱", "AL"),
    "356": ("🇲🇹", "MT"), "357": ("🇨🇾", "CY"), "358": ("🇫🇮", "FI"), "359": ("🇧🇬", "BG"), "370": ("🇱🇹", "LT"),
    "371": ("🇱🇻", "LV"), "372": ("🇪🇪", "EE"), "373": ("🇲🇩", "MD"), "374": ("🇦🇲", "AM"), "375": ("🇧🇾", "BY"),
    "376": ("🇦🇩", "AD"), "377": ("🇲🇨", "MC"), "378": ("🇸🇲", "SM"), "379": ("🇻🇦", "VA"), "380": ("🇺🇦", "UA"),
    "381": ("🇷🇸", "RS"), "382": ("🇲🇪", "ME"), "383": ("🇽🇰", "XK"), "385": ("🇭🇷", "HR"), "386": ("🇸🇮", "SI"),
    "387": ("🇧🇦", "BA"), "389": ("🇲🇰", "MK"), "420": ("🇨🇿", "CZ"), "421": ("🇸🇰", "SK"), "423": ("🇱🇮", "LI"),
    "500": ("🇫🇰", "FK"), "501": ("🇧🇿", "BZ"), "502": ("🇬🇹", "GT"), "503": ("🇸🇻", "SV"), "504": ("🇭🇳", "HN"),
    "505": ("🇳🇮", "NI"), "506": ("🇨🇷", "CR"), "507": ("🇵🇦", "PA"), "508": ("🇵🇲", "PM"), "509": ("🇭🇹", "HT"),
    "590": ("🇬🇵", "GP"), "591": ("🇧🇴", "BO"), "592": ("🇬🇾", "GY"), "593": ("🇪🇨", "EC"), "594": ("🇬🇫", "GF"),
    "595": ("🇵🇾", "PY"), "596": ("🇲🇶", "MQ"), "597": ("🇸🇷", "SR"), "598": ("🇺🇾", "UY"), "599": ("🇧🇶", "BQ"),
    "670": ("🇹🇱", "TL"), "673": ("🇧🇳", "BN"), "674": ("🇳🇷", "NR"), "675": ("🇵🇬", "PG"), "676": ("🇹🇴", "TO"),
    "677": ("🇸🇧", "SB"), "678": ("🇻🇺", "VU"), "679": ("🇫🇯", "FJ"), "680": ("🇵🇼", "PW"), "681": ("🇼🇫", "WF"),
    "682": ("🇨🇰", "CK"), "683": ("🇳🇺", "NU"), "685": ("🇼🇸", "WS"), "686": ("🇰🇮", "KI"), "687": ("🇳🇨", "NC"),
    "688": ("🇹🇻", "TV"), "689": ("🇵🇫", "PF"), "690": ("🇹🇰", "TK"), "691": ("🇫🇲", "FM"), "692": ("🇲🇭", "MH"),
    "850": ("🇰🇵", "KP"), "852": ("🇭🇰", "HK"), "853": ("🇲🇴", "MO"), "855": ("🇰🇭", "KH"), "856": ("🇱🇦", "LA"),
    "880": ("🇧🇩", "BD"), "886": ("🇹🇼", "TW"), "960": ("🇲🇻", "MV"), "961": ("🇱🇧", "LB"), "962": ("🇯🇴", "JO"),
    "963": ("🇸🇾", "SY"), "964": ("🇮🇶", "IQ"), "965": ("🇰🇼", "KW"), "966": ("🇸🇦", "SA"), "967": ("🇾🇪", "YE"),
    "968": ("🇴🇲", "OM"), "970": ("🇵🇸", "PS"), "971": ("🇦🇪", "AE"), "972": ("🇮🇱", "IL"), "973": ("🇧🇭", "BH"),
    "974": ("🇶🇦", "QA"), "975": ("🇧🇹", "BT"), "976": ("🇲🇳", "MN"), "977": ("🇳🇵", "NP"), "992": ("🇹🇯", "TJ"),
    "993": ("🇹🇲", "TM"), "994": ("🇦🇿", "AZ"), "995": ("🇬🇪", "GE"), "996": ("🇰🇬", "KG"), "998": ("🇺🇿", "UZ"),
    "1242": ("🇧🇸", "BS"), "1246": ("🇧🇧", "BB"), "1264": ("🇦🇮", "AI"), "1268": ("🇦🇬", "AG"), "1284": ("🇻🇬", "VG"),
    "1340": ("🇻🇮", "VI"), "1441": ("🇧🇲", "BM"), "1473": ("🇬🇩", "GD"), "1649": ("🇹🇨", "TC"), "1664": ("🇲🇸", "MS"),
    "1671": ("🇬🇺", "GU"), "1684": ("🇦🇸", "AS"), "1721": ("🇸🇽", "SX"), "1758": ("🇱🇨", "LC"), "1767": ("🇩🇲", "DM"),
    "1784": ("🇻🇨", "VC"), "1809": ("🇩🇴", "DO"), "1868": ("🇹🇹", "TT"), "1869": ("🇰🇳", "KN"), "1876": ("🇯🇲", "JM"),
    "1939": ("🇵🇷", "PR"),
}

def get_country_flag(phone_number):
    for i in [4, 3, 2, 1]:
        code = phone_number[:i]
        if code in COUNTRY_FLAGS:
            return COUNTRY_FLAGS[code]
    return ("🌍", "")

def detect_service(message):
    msg = message.lower()
    services_list = [
        ("Instagram", r"\b(instagram|ig|insta)\b"),
        ("Face-Book", r"\b(facebook|fb|meta)\b"),
        ("Messenger", r"\b(messenger)\b"),
        ("WhatsApp", r"\b(whatsapp|wa)\b"),
        ("Telegram", r"\b(telegram|tg)\b"),
        ("Discord", r"\b(discord)\b"),
        ("Google", r"\b(google|gmail|g-)\b"),
        ("TikTok", r"\b(tiktok)\b"),
        ("Twitter", r"\b(twitter|x\.com)\b"),
        ("Snapchat", r"\b(snapchat)\b"),
        ("Amazon", r"\b(amazon)\b"),
        ("PayPal", r"\b(paypal)\b"),
        ("Uber", r"\b(uber)\b"),
        ("Netflix", r"\b(netflix)\b"),
        ("Apple", r"\b(apple|icloud)\b"),
        ("Microsoft", r"\b(microsoft|outlook|hotmail|live)\b"),
        ("LinkedIn", r"\b(linkedin)\b"),
        ("Yahoo", r"\b(yahoo)\b"),
        ("Binance", r"\b(binance)\b"),
        ("Coinbase", r"\b(coinbase)\b"),
        ("Steam", r"\b(steam)\b"),
        ("PlayStation", r"\b(playstation|psn)\b"),
        ("Xbox", r"\b(xbox)\b"),
        ("Airbnb", r"\b(airbnb)\b"),
        ("Booking", r"\b(booking)\b"),
        ("Spotify", r"\b(spotify)\b"),
        ("LINE", r"\b(line)\b"),
        ("WeChat", r"\b(wechat)\b"),
        ("Viber", r"\b(viber)\b"),
        ("Signal", r"\b(signal)\b"),
    ]
    for name, pattern in services_list:
        if re.search(pattern, msg):
            return name
    return "Unknown"

# ──────────────────────────────────────────────────────────
# 🔑 OTP INBOX ইঞ্জিন
# ──────────────────────────────────────────────────────────
active_numbers = {}
user_range_number = {}
otp_lock = threading.Lock()
seen_otp_ids = set()

def save_new_number(user_id, rid_input, number):
    with otp_lock:
        active_numbers[number] = {"user_id": user_id, "time": time.time()}
        user_range_number[(user_id, rid_input)] = number

def replace_number_for_range(user_id, rid_input, number):
    with otp_lock:
        active_numbers[number] = {"user_id": user_id, "time": time.time()}
        user_range_number[(user_id, rid_input)] = number

def extract_otp_code(message_text):
    match = re.search(r'\b\d{2,5}[\s-]\d{2,5}\b|\b\d{3,10}\b', message_text)
    if match:
        return re.sub(r'[\s-]', '', match.group(0))
    return "N/A"

def poll_otps():
    headers = {"mauthapi": API_KEY, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    while True:
        try:
            response = requests.get(OTP_API_URL, headers=headers, timeout=10)
            if response.status_code == 200:
                res_data = response.json()
                if res_data.get("meta", {}).get("code") == 200:
                    otps = res_data.get("data", {}).get("otps", [])
                    for otp in otps:
                        otp_id = otp.get("otp_id")
                        number = str(otp.get("number", ""))
                        message_text = otp.get("message", "")

                        if not otp_id or otp_id in seen_otp_ids:
                            continue

                        with otp_lock:
                            entry = active_numbers.get(number)

                        if entry:
                            code = extract_otp_code(message_text)
                            service = detect_service(message_text)
                            flag = get_country_flag(number)[0]

                            safe_service = html.escape(service)
                            safe_number = html.escape(number)
                            safe_flag = html.escape(flag)
                            title_service = "Your" if safe_service == "Unknown" else safe_service

                            otp_text = (
                                f"🔔 <b>{title_service} OTP Received</b>\n\n"
                                f"📱 <b>{safe_service}</b> | <code>{safe_number}</code> | {safe_flag}\n"
                                f"🔐 <b>Code:</b> <code>{code}</code>"
                            )

                            otp_markup = types.InlineKeyboardMarkup()
                            key_button = types.InlineKeyboardButton(
                                text="Copy Code",
                                copy_text=types.CopyTextButton(text=code),
                                style="success"
                            )
                            otp_markup.row(key_button)

                            max_retries = 3
                            for attempt in range(max_retries):
                                try:
                                    bot.send_message(entry["user_id"], otp_text, parse_mode="HTML", reply_markup=otp_markup)
                                    print(f"✅ OTP পাঠানো হয়েছে ইউজার {entry['user_id']} কে, নাম্বার: {number}")
                                    break
                                except Exception as send_err:
                                    err_text = str(send_err)
                                    m = re.search(r"retry after (\d+)", err_text)
                                    if m:
                                        wait_s = int(m.group(1)) + 1
                                        print(f"⏳ Flood control — {wait_s}s অপেক্ষা")
                                        time.sleep(wait_s)
                                        continue
                                    else:
                                        print(f"⚠️ OTP পাঠাতে ব্যর্থ: {send_err}")
                                        break

                        seen_otp_ids.add(otp_id)

                    if len(seen_otp_ids) > 500:
                        for old_id in list(seen_otp_ids)[:200]:
                            seen_otp_ids.discard(old_id)
            else:
                print(f"⚠️ OTP API Status Error: {response.status_code}")
        except Exception as e:
            print(f"❌ OTP পোলিং এরর: {e}")

        with otp_lock:
            cutoff = time.time() - 1200
            expired = [num for num, v in active_numbers.items() if v["time"] < cutoff]
            for num in expired:
                del active_numbers[num]
                stale_keys = [k for k, v in user_range_number.items() if v == num]
                for k in stale_keys:
                    del user_range_number[k]

        time.sleep(2)

# ──────────────────────────────────────────────────────────
# 🎛 মেনু কিবোর্ড
# ──────────────────────────────────────────────────────────
def main_keyboard(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📱 GET NUMBER", style="success"),
        types.KeyboardButton("🔥 Live Traffic", style="primary")
    )
    markup.add(types.KeyboardButton("💬 Support", style="primary"))
    if user_id == ADMIN_ID:
        markup.add(types.KeyboardButton("🛠 Admin Panel", style="danger"))
    return markup

def send_welcome_menu(chat_id, user_id):
    count = user_get_count.get(user_id, DEFAULT_GET_COUNT)
    bot.send_message(
        chat_id,
        "⚡ **QUICK MULTI-NUMBER BOT** ⚡\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "সার্ভিস বেছে নিয়ে সরাসরি নাম্বার নিন।\n\n"
        f"🔢 **/get1** থেকে **/get10** — একবারে কতগুলো নাম্বার চান সেট করুন\n"
        f"📱 **GET NUMBER** — সার্ভিস বেছে নিয়ে নাম্বার(গুলো) নিন\n"
        f"🔥 **Live Traffic** — সাম্প্রতিক লাইভ হিট দেখুন\n\n"
        f"🔢 **বর্তমান কাউন্ট:** {count}টা নাম্বার",
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id)
    )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    admin_waiting.pop(message.from_user.id, None)
    send_welcome_menu(message.chat.id, message.from_user.id)

# ──────────────────────────────────────────────────────────
# 🔢 /get1 থেকে /get10 কমান্ড
# ──────────────────────────────────────────────────────────
get_count_commands = [f"get{i}" for i in range(1, MAX_GET_COUNT + 1)]

@bot.message_handler(commands=get_count_commands)
def handle_get_count(message):
    match = re.match(r'^/get(\d+)', message.text)
    if not match:
        return
    n = int(match.group(1))
    if n < 1 or n > MAX_GET_COUNT:
        bot.send_message(message.chat.id, f"❌ শুধু /get1 থেকে /get{MAX_GET_COUNT} পর্যন্ত ব্যবহার করা যাবে।")
        return

    user_get_count[message.from_user.id] = n
    bot.send_message(
        message.chat.id,
        f"✅ সেট হয়ে গেছে! এখন থেকে GET NUMBER চাপলে একবারে **{n}টা নাম্বার** পাবেন।",
        parse_mode="Markdown"
    )

# ──────────────────────────────────────────────────────────
# 🛠 এডমিন প্যানেল
# ──────────────────────────────────────────────────────────
def admin_panel_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ Add Service", callback_data="admin_add_service", style="success"))
    markup.add(types.InlineKeyboardButton("🗑 Remove Service", callback_data="admin_remove_service", style="danger"))
    markup.add(types.InlineKeyboardButton("🎯 Set Range", callback_data="admin_set_range", style="primary"))
    markup.add(types.InlineKeyboardButton("❌ Remove Range", callback_data="admin_remove_range", style="danger"))
    return markup

def send_admin_panel(chat_id):
    bot.send_message(
        chat_id,
        "🛠 **Admin Panel**\n━━━━━━━━━━━━━━━━━━\nনিচের অপশন থেকে বেছে নিন:",
        parse_mode="Markdown",
        reply_markup=admin_panel_markup()
    )

def service_list_markup(callback_prefix):
    """সব সার্ভিসের লিস্ট বাটন আকারে দেখায় (দেশ থাকুক বা না থাকুক)"""
    markup = types.InlineKeyboardMarkup()
    for name in services.keys():
        label = f"{service_emoji(name)} {name}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"{callback_prefix}_{name}"))
    return markup

def country_list_markup(service_name, callback_prefix):
    """একটা সার্ভিসের ভেতরের দেশগুলোর লিস্ট বাটন আকারে দেখায়"""
    markup = types.InlineKeyboardMarkup()
    countries = services.get(service_name, {})
    for iso in countries.keys():
        flag = next((f for f, i in COUNTRY_FLAGS.values() if i == iso), "🌍")
        markup.add(types.InlineKeyboardButton(f"{flag} {iso}", callback_data=f"{callback_prefix}|{service_name}|{iso}"))
    return markup

@bot.callback_query_handler(func=lambda call: call.data == "admin_add_service")
def admin_add_service(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    admin_waiting[ADMIN_ID] = "add_service"
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "⌨️ নতুন সার্ভিসের নাম লিখুন (যেমন: Facebook):")

@bot.callback_query_handler(func=lambda call: call.data == "admin_remove_service")
def admin_remove_service(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if not services:
        bot.send_message(call.message.chat.id, "ℹ️ কোনো সার্ভিস নেই।")
        return
    bot.send_message(call.message.chat.id, "🗑 কোন সার্ভিসটা মুছবেন?", reply_markup=service_list_markup("rmsvc"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("rmsvc_"))
def handle_remove_service(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    name = call.data[len("rmsvc_"):]
    services.pop(name, None)
    bot.answer_callback_query(call.id, text=f"✅ {name} মুছে ফেলা হয়েছে")
    bot.send_message(call.message.chat.id, f"✅ সার্ভিস **{name}** (সব দেশ/রেঞ্জসহ) সম্পূর্ণ মুছে ফেলা হয়েছে।", parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "admin_set_range")
def admin_set_range(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if not services:
        bot.send_message(call.message.chat.id, "ℹ️ আগে **Add Service** দিয়ে একটা সার্ভিস তৈরি করুন।", parse_mode="Markdown")
        return
    bot.send_message(call.message.chat.id, "🎯 কোন সার্ভিসে নতুন দেশ/রেঞ্জ যোগ করবেন?", reply_markup=service_list_markup("setrange"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("setrange_"))
def handle_select_service_for_range(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    name = call.data[len("setrange_"):]
    admin_waiting[ADMIN_ID] = f"set_range:{name}"
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        f"⌨️ **{name}** এর জন্য রেঞ্জ আইডি লিখুন (e.g., 123456XXX):\n\n(দেশটা রেঞ্জ থেকেই স্বয়ংক্রিয়ভাবে শনাক্ত হয়ে যাবে)",
        parse_mode="Markdown"
    )

@bot.callback_query_handler(func=lambda call: call.data == "admin_remove_range")
def admin_remove_range(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    if not services:
        bot.send_message(call.message.chat.id, "ℹ️ কোনো সার্ভিস নেই।")
        return
    bot.send_message(call.message.chat.id, "❌ কোন সার্ভিস থেকে রেঞ্জ মুছবেন?", reply_markup=service_list_markup("rmrangesvc"))

@bot.callback_query_handler(func=lambda call: call.data.startswith("rmrangesvc_"))
def handle_select_service_for_remove_range(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    name = call.data[len("rmrangesvc_"):]
    countries = services.get(name, {})
    bot.answer_callback_query(call.id)
    if not countries:
        bot.send_message(call.message.chat.id, f"ℹ️ **{name}** এ কোনো দেশ/রেঞ্জ নেই।", parse_mode="Markdown")
        return
    bot.send_message(
        call.message.chat.id,
        f"❌ **{name}** এর কোন দেশের রেঞ্জ মুছবেন?",
        parse_mode="Markdown",
        reply_markup=country_list_markup(name, "rmrange")
    )

@bot.callback_query_handler(func=lambda call: call.data.startswith("rmrange|"))
def handle_remove_range(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, text="❌ Unauthorized.", show_alert=True)
        return
    _, name, iso = call.data.split("|")
    if name in services:
        services[name].pop(iso, None)
    bot.answer_callback_query(call.id, text=f"✅ {name} থেকে {iso} মুছে ফেলা হয়েছে")
    bot.send_message(call.message.chat.id, f"✅ **{name}** থেকে **{iso}** এর রেঞ্জ মুছে ফেলা হয়েছে।", parse_mode="Markdown")

# ──────────────────────────────────────────────────────────
# বাটন হ্যান্ডলার — GET NUMBER / Live Traffic / Admin Panel / এডমিনের টেক্সট ইনপুট
# ──────────────────────────────────────────────────────────
@bot.message_handler(
    func=lambda message: True,
    content_types=['text', 'photo', 'voice', 'video', 'document', 'audio', 'sticker', 'video_note', 'location', 'contact']
)
def handle_text(message):
    user_id = message.from_user.id

    if message.text == "🛠 Admin Panel" and user_id == ADMIN_ID:
        admin_waiting.pop(ADMIN_ID, None)
        send_admin_panel(message.chat.id)
        return

    if message.text == "🔥 Live Traffic":
        if user_id == ADMIN_ID:
            admin_waiting.pop(ADMIN_ID, None)
        send_live_traffic(message.chat.id)
        return

    if message.text == "💬 Support":
        if user_id == ADMIN_ID:
            admin_waiting.pop(ADMIN_ID, None)
        support_markup = types.InlineKeyboardMarkup()
        support_markup.add(types.InlineKeyboardButton("💬 Contact Support", url=SUPPORT_LINK, style="primary"))
        bot.send_message(message.chat.id, "যেকোনো সাহায্যের জন্য নিচের বাটনে ক্লিক করুন:", reply_markup=support_markup)
        return

    if message.text == "📱 GET NUMBER":
        if user_id == ADMIN_ID:
            admin_waiting.pop(ADMIN_ID, None)
        if not services:
            bot.send_message(message.chat.id, "⚠️ এই মুহূর্তে কোনো সার্ভিস নেই। একটু পরে চেষ্টা করুন।")
            return
        bot.send_message(
            message.chat.id,
            "📱 কোন সার্ভিসের নাম্বার চান, বেছে নিন:",
            reply_markup=service_list_markup("getsvc")
        )
        return

    # 🛠 এডমিনের পেন্ডিং টেক্সট-ইনপুট প্রসেস করা (বাটন প্রেসের পরেই চেক হয়, যাতে বাটন কখনো এখানে আটকে না যায়)
    if user_id == ADMIN_ID and user_id in admin_waiting:
        state = admin_waiting[ADMIN_ID]

        if message.content_type != 'text':
            bot.send_message(message.chat.id, "❌ Please send this as text.")
            return

        if state == "add_service":
            admin_waiting.pop(ADMIN_ID, None)
            name = message.text.strip()
            if not name:
                bot.send_message(message.chat.id, "❌ খালি নাম দেওয়া যাবে না।")
                return
            if name in services:
                bot.send_message(message.chat.id, f"⚠️ **{name}** সার্ভিসটা আগে থেকেই আছে।", parse_mode="Markdown")
                return
            services[name] = {}
            bot.send_message(
                message.chat.id,
                f"✅ নতুন সার্ভিস **{name}** যোগ হয়েছে।\n\nএখন **Set Range** দিয়ে এতে দেশ/রেঞ্জ যোগ করুন।",
                parse_mode="Markdown"
            )
            return

        if state.startswith("set_range:"):
            name = state[len("set_range:"):]
            rid_input = message.text.strip()
            if not re.match(r'^[\d]{3,}[X]{3,}$', rid_input, re.IGNORECASE):
                bot.send_message(message.chat.id, "❌ Wrong input! Please enter correct range ID.")
                return

            flag, iso = get_country_flag(rid_input)
            if not iso:
                bot.send_message(message.chat.id, "❌ এই রেঞ্জ থেকে দেশ শনাক্ত করা গেল না। সঠিক কান্ট্রি কোড দিয়ে রেঞ্জ দিন।")
                return

            admin_waiting.pop(ADMIN_ID, None)
            if name not in services:
                services[name] = {}
            services[name][iso] = rid_input
            bot.send_message(
                message.chat.id,
                f"✅ **{name}** এ {flag} **{iso}** যোগ/আপডেট হয়ে গেছে — রেঞ্জ: `{rid_input}`",
                parse_mode="Markdown"
            )
            return

# ──────────────────────────────────────────────────────────
# 📱 ইউজার একটা সার্ভিস বেছে নিলে — সেই সার্ভিসের দেশগুলো দেখানো হয়
# ──────────────────────────────────────────────────────────
@bot.callback_query_handler(func=lambda call: call.data.startswith("getsvc_"))
def handle_get_service_countries(call):
    name = call.data[len("getsvc_"):]
    countries = services.get(name)
    if countries is None:
        bot.answer_callback_query(call.id, text="⚠️ এই সার্ভিসটা আর নেই।", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    if not countries:
        bot.send_message(call.message.chat.id, f"❌ No country available for {name}.")
        return

    bot.send_message(
        call.message.chat.id,
        f"{service_emoji(name)} **{name}** — কোন দেশের নাম্বার চান?",
        parse_mode="Markdown",
        reply_markup=country_list_markup(name, "getcountry")
    )

# 🌍 ইউজার একটা দেশ বেছে নিলে — নাম্বার আনা শুরু হয়
@bot.callback_query_handler(func=lambda call: call.data.startswith("getcountry|"))
def handle_get_country_numbers(call):
    _, name, iso = call.data.split("|")
    rid_input = services.get(name, {}).get(iso)
    if not rid_input:
        bot.answer_callback_query(call.id, text="⚠️ এই দেশের রেঞ্জ এখন আর সেট নেই।", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    user_id = call.from_user.id
    flag = next((f for f, i in COUNTRY_FLAGS.values() if i == iso), "🌍")
    loading = bot.send_message(call.message.chat.id, f"🔍 {service_emoji(name)} {name} ({flag} {iso}) থেকে নাম্বার খোঁজা হচ্ছে...")
    threading.Thread(
        target=_fetch_and_send_numbers,
        args=(call.message.chat.id, user_id, rid_input, loading.message_id, name, iso),
        daemon=True
    ).start()

# নাম্বার তুলে আনার মেইন ফাংশন — একবার চেষ্টা করে, রিট্রাই নিজে করে না
# (রিট্রাই এখন request_n_numbers_parallel এ একটা শেয়ার্ড বাজেট হিসেবে হয়)
def request_number_once(rid_input):
    headers = {"mauthapi": API_KEY, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        response = requests.post(API_URL, json={"rid": rid_input}, headers=headers, timeout=12)
        if response.status_code == 200:
            data = response.json()
            if data.get("meta", {}).get("code") == 200:
                return data
        print(f"⚠️ নাম্বার রিকোয়েস্ট ব্যর্থ (status: {response.status_code})")
    except Exception as e:
        print(f"⚠️ নাম্বার রিকোয়েস্ট এরর: {e}")
    return None

MAX_TOTAL_ATTEMPTS = 20  # ১টা থেকে ১০টা নাম্বার আনতে সবমিলিয়ে সর্বোচ্চ এতবারই চেষ্টা হবে

def request_n_numbers_parallel(rid_input, n):
    """n সংখ্যক নাম্বার আনার চেষ্টা করে, কিন্তু সবমিলিয়ে সর্বোচ্চ MAX_TOTAL_ATTEMPTS বার
    API হিট করবে (n যা-ই হোক, ১ থেকে ১০) — যাতে API তে অতিরিক্ত চাপ না পড়ে।
    n-টা নাম্বার পাওয়া গেলে বা attempt বাজেট শেষ হয়ে গেলে, যেটা আগে হয় সেখানেই থেমে যাবে।"""
    results = []
    attempts_used = 0

    while len(results) < n and attempts_used < MAX_TOTAL_ATTEMPTS:
        remaining_needed = n - len(results)
        remaining_budget = MAX_TOTAL_ATTEMPTS - attempts_used
        batch_size = min(remaining_needed, remaining_budget)

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            futures = [executor.submit(request_number_once, rid_input) for _ in range(batch_size)]
            batch_results = [f.result() for f in futures]

        attempts_used += batch_size
        for r in batch_results:
            if r:
                results.append(r)

    print(f"ℹ️ মোট {attempts_used}/{MAX_TOTAL_ATTEMPTS} বার চেষ্টা করে {len(results)}/{n} টা নাম্বার পাওয়া গেছে")
    return results

def build_multi_number_markup(numbers, session_id):
    """একাধিক নাম্বার বাটন + একটাই Change Number বাটন (সেশন আইডি দিয়ে service/country/count ট্র্যাক করা)"""
    markup = types.InlineKeyboardMarkup()
    for num in numbers:
        display = f"+{num}"
        markup.add(types.InlineKeyboardButton(
            text=display,
            copy_text=types.CopyTextButton(text=display),
            style="success"
        ))
    markup.row(
        types.InlineKeyboardButton(
            "🔄 Change Number",
            callback_data=f"change_{session_id}",
            style="primary"
        )
    )
    return markup

def _fetch_and_send_numbers(chat_id, user_id, rid_input, loading_message_id, service_name, country_iso):
    count = user_get_count.get(user_id, DEFAULT_GET_COUNT)
    try:
        results = request_n_numbers_parallel(rid_input, count)
    except Exception as e:
        print(f"❌ _fetch_and_send_numbers এরর: {e}")
        try:
            bot.delete_message(chat_id, loading_message_id)
        except:
            pass
        bot.send_message(chat_id, "❌ Something went wrong. Please try again.")
        return

    valid_results = [r["data"] for r in results if r and r.get("meta", {}).get("code") == 200]

    if valid_results:
        numbers = []
        for idx, num_data in enumerate(valid_results):
            number = num_data.get("no_plus_number", "")
            suffix = "" if idx == 0 else f"_{idx+1}"
            save_new_number(user_id, rid_input + suffix, number)
            numbers.append(number)

        first_num_data = valid_results[0]
        flag = get_country_flag(numbers[0])[0]
        result_text = (
            f"✅ **{len(numbers)} Number(s) Assigned Successfully!**\n\n"
            f"📱 **Service:** {service_emoji(service_name)} {service_name}\n"
            f"🌐 **Country:** {flag} {first_num_data.get('country')} ({country_iso})\n\n"
            f"🌀 **OTP Forwarded Automatically.**"
        )
        session_id = new_session(service_name, country_iso, len(numbers))
        markup = build_multi_number_markup(numbers, session_id)

        bot.delete_message(chat_id, loading_message_id)
        bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.delete_message(chat_id, loading_message_id)
        bot.send_message(chat_id, "❌ No numbers available in this range right now. Try again later.")

# 🔥 Change Number ইনলাইন বাটন (সবগুলো নাম্বার একসাথে রিফ্রেশ করবে)
@bot.callback_query_handler(func=lambda call: call.data.startswith("change_"))
def handle_change_number(call):
    user_id = call.from_user.id
    now = time.time()
    last_time = user_last_change.get(user_id, 0)

    if now - last_time < CHANGE_COOLDOWN:
        remaining = round(CHANGE_COOLDOWN - (now - last_time), 1)
        bot.answer_callback_query(call.id, text=f"⏳ Try again after {remaining} seconds.", show_alert=True)
        return
    user_last_change[user_id] = now

    session_id = int(call.data[len("change_"):])
    session = change_sessions.get(session_id)
    if not session:
        bot.answer_callback_query(call.id, text="⚠️ Session expired. Please get a new number.", show_alert=True)
        return
    service_name, country_iso, count = session

    rid_input = services.get(service_name, {}).get(country_iso)
    if not rid_input:
        bot.answer_callback_query(call.id, text="⚠️ এই দেশের রেঞ্জ এখন আর সেট নেই।", show_alert=True)
        return

    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Requesting new number(s)...", chat_id=call.message.chat.id, message_id=call.message.message_id)

    threading.Thread(
        target=_fetch_and_send_changed_numbers,
        args=(call.from_user.id, rid_input, count, call.message.chat.id, call.message.message_id, service_name, country_iso),
        daemon=True
    ).start()

def _fetch_and_send_changed_numbers(user_id, rid_input, count, chat_id, message_id, service_name, country_iso):
    try:
        results = request_n_numbers_parallel(rid_input, count)
    except Exception as e:
        print(f"❌ _fetch_and_send_changed_numbers এরর: {e}")
        try:
            bot.edit_message_text("❌ Something went wrong. Please try again.", chat_id=chat_id, message_id=message_id)
        except:
            pass
        return

    valid_results = [r["data"] for r in results if r and r.get("meta", {}).get("code") == 200]

    if valid_results:
        numbers = []
        for idx, num_data in enumerate(valid_results):
            number = num_data.get("no_plus_number", "")
            suffix = "" if idx == 0 else f"_{idx+1}"
            replace_number_for_range(user_id, rid_input + suffix, number)
            numbers.append(number)

        first_num_data = valid_results[0]
        flag = get_country_flag(numbers[0])[0]
        updated_text = (
            f"✅ **{len(numbers)} Number(s) Changed Successfully!**\n\n"
            f"📱 **Service:** {service_emoji(service_name)} {service_name}\n"
            f"🌐 **Country:** {flag} {first_num_data.get('country')} ({country_iso})\n\n"
            f"🌀 **OTP Forwarded Automatically.**"
        )
        session_id = new_session(service_name, country_iso, len(numbers))
        markup = build_multi_number_markup(numbers, session_id)
        bot.edit_message_text(updated_text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.edit_message_text(
            "❌ Sorry, no numbers available right now. Try again later.",
            chat_id=chat_id,
            message_id=message_id

        )

# ──────────────────────────────────────────────────────────
# 🔥 Live Traffic
# ──────────────────────────────────────────────────────────
def fetch_live_traffic_text():
    headers = {"mauthapi": API_KEY, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(LIVE_TRAFFIC_API, headers=headers, timeout=10)
        if response.status_code != 200:
            return "❌ Live Traffic ডেটা আনতে ব্যর্থ (API এরর)।"

        data = response.json()
        if data.get("meta", {}).get("code") != 200:
            return "❌ Live Traffic ডেটা আনতে ব্যর্থ (API এরর)।"

        hits = data.get("data", {}).get("hits", [])
        now_ms = time.time() * 1000
        window_ms = 5 * 60 * 1000  # গত ৫ মিনিট

        recent = []
        for h in hits:
            if (now_ms - h.get("time", 0)) > window_ms:
                continue
            canonical = normalize_service_name(h.get("sid", ""))
            if canonical is None:
                continue  # শুধু Facebook/WhatsApp/Instagram/Telegram/Imo — বাকি সব বাদ
            h["_canonical_sid"] = canonical
            recent.append(h)

        if not recent:
            return "📊 **Live Traffic**\n━━━━━━━━━━━━━━━━━━\n\n🕐 Window: Last 5 minutes\n\nℹ️ এই মুহূর্তে কোনো নতুন হিট নেই।"

        # প্রতিটা hit থেকে দেশ + সার্ভিস বের করে গোনা হচ্ছে
        combo_counts = {}    # {(country_iso, flag, sid): count}
        country_counts = {}  # {(country_iso, flag): count}

        for h in recent:
            rng = h.get("range", "")
            sid = h["_canonical_sid"]
            flag, iso = get_country_flag(rng)
            if not iso:
                iso, flag = "UNKNOWN", "🌍"
            combo_key = (iso, flag, sid)
            combo_counts[combo_key] = combo_counts.get(combo_key, 0) + 1
            country_key = (iso, flag)
            country_counts[country_key] = country_counts.get(country_key, 0) + 1

        total = len(recent)

        # সবচেয়ে বেশি হিট হওয়া কম্বো (Top) — শতাংশসহ
        top_combo, top_count = max(combo_counts.items(), key=lambda x: x[1])
        (top_iso, top_flag, top_sid) = top_combo
        top_pct = round((top_count / total) * 100)

        # দেশ অনুযায়ী র‍্যাংক (বেশি থেকে কম)
        ranked_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)

        lines = [
            "📊 **Live Traffic**",
            "━━━━━━━━━━━━━━━━━━",
            "",
            "🕐 **Window:** Last 5 minutes",
            f"📩 **Top:** {top_flag} {top_iso}-{top_sid} {top_pct}%",
            "",
            "🌐 **Top Countries:**"
        ]
        for idx, ((iso, flag), cnt) in enumerate(ranked_countries[:10], start=1):
            pct = round((cnt / total) * 100)
            lines.append(f"{idx}. {flag} {iso} — {pct}%")

        return "\n".join(lines)

    except Exception as e:
        print(f"❌ Live Traffic এরর: {e}")
        return "❌ Live Traffic ডেটা আনতে ব্যর্থ। একটু পরে চেষ্টা করুন।"

def live_traffic_markup():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Refresh", callback_data="refresh_traffic", style="primary"))
    return markup

def send_live_traffic(chat_id):
    text = fetch_live_traffic_text()
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=live_traffic_markup())

@bot.callback_query_handler(func=lambda call: call.data == "refresh_traffic")
def handle_refresh_traffic(call):
    bot.answer_callback_query(call.id, text="🔄 Refreshed")
    text = fetch_live_traffic_text()
    try:
        bot.edit_message_text(
            text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            parse_mode="Markdown",
            reply_markup=live_traffic_markup()
        )
    except Exception as e:
        print(f"⚠️ Live Traffic রিফ্রেশ এরর: {e}")

# 🔑 OTP INBOX ব্যাকগ্রাউন্ড থ্রেড
threading.Thread(target=poll_otps, daemon=True).start()

def run_keep_alive_server():
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class PingHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is alive")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, format, *args):
            pass

    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), PingHandler)
    server.serve_forever()

threading.Thread(target=run_keep_alive_server, daemon=True).start()
bot.infinity_polling()
