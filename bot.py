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

# 🕒 Change Number কুলডাউন কনফিগারেশন
user_last_change = {}  # {user_id: timestamp}
CHANGE_COOLDOWN = 3  # সেকেন্ড

# 🔗 লিংক (OTP GROUP বাটনের জন্য)
OTP_GROUP_LINK = "https://t.me/+7RobuqxsLhJlZDdl"

# 📢 OTP আসলে ইনবক্সের পাশাপাশি এই গ্রুপেও (মাস্কড নাম্বার সহ) পোস্ট করা হবে
# এটা বসাতে হবে: গ্রুপে বটকে অ্যাডমিন করুন, তারপর গ্রুপের numeric chat ID এখানে বসান
# (chat ID বের করতে @RawDataBot বা @userinfobot ব্যবহার করতে পারেন — গ্রুপে অ্যাড করে একটা মেসেজ পাঠালেই ID দেখাবে)
OTP_GROUP_CHAT_ID = -1003449804166

def mask_number(number):
    """নাম্বারের মাঝের অংশ XXX দিয়ে লুকিয়ে দেয় — পাবলিক গ্রুপে পোস্ট করার জন্য"""
    if len(number) <= 8:
        return number
    return number[:6] + "XXX" + number[-4:]

bot = telebot.TeleBot(BOT_TOKEN, num_threads=100)

# ──────────────────────────────────────────────────────────
# 🔢 প্রতিটা ইউজার কতগুলো নাম্বার একসাথে পাবে (/get1 থেকে /get10 দিয়ে সেট হয়)
# ──────────────────────────────────────────────────────────
user_get_count = {}   # {user_id: N}
DEFAULT_GET_COUNT = 10
MAX_GET_COUNT = 10

# 🎯 প্রতিটা ইউজারের স্থায়ীভাবে সেট করা রেঞ্জ (Set Range বাটন দিয়ে সেট হয়)
user_saved_range = {}  # {user_id: rid_input}
waiting_for_range_set = set()  # যারা এখন Set Range এর জন্য রেঞ্জ টাইপ করবে

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
    services = [
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
    for name, pattern in services:
        if re.search(pattern, msg):
            return name
    return "Unknown"

# ──────────────────────────────────────────────────────────
# 🔑 OTP INBOX ইঞ্জিন (আগের বট থেকে অপরিবর্তিত)
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

                            # 📢 ইনবক্সের পাশাপাশি OTP GROUP এও মাস্কড নাম্বার সহ পোস্ট করা হচ্ছে
                            try:
                                masked = mask_number(number)
                                safe_full_message = html.escape(message_text)
                                group_text = (
                                    f"{masked}\n{safe_flag}\n\n"
                                    f"OTP. {html.escape(code)}\n\n"
                                    f"{safe_full_message}"
                                )
                                group_markup = types.InlineKeyboardMarkup()
                                group_markup.add(types.InlineKeyboardButton(
                                    "📱 GET NUMBER",
                                    url="https://t.me/SMSTOSMSBOT?start=start",
                                    style="success"
                                ))
                                bot.send_message(OTP_GROUP_CHAT_ID, group_text, parse_mode="HTML", reply_markup=group_markup)
                            except Exception as group_err:
                                print(f"⚠️ OTP Group এ পোস্ট করতে ব্যর্থ: {group_err}")

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

# (ফোর্স-জয়েন সিস্টেম বাদ দেওয়া হয়েছে — এখন আর কোনো চ্যানেল/গ্রুপ জয়েন চেক নেই)

# প্রধান মেনু কিবোর্ড — GET NUMBER + Set Range
def main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(
        types.KeyboardButton("📱 GET NUMBER", style="success"),
        types.KeyboardButton("🎯 Set Range", style="primary")
    )
    return markup

def send_welcome_menu(chat_id, user_id):
    count = user_get_count.get(user_id, DEFAULT_GET_COUNT)
    saved_range = user_saved_range.get(user_id)
    range_line = f"🎯 **Saved Range:** `{saved_range}`" if saved_range else "🎯 **Saved Range:** এখনো সেট করা হয়নি — আগে 'Set Range' চাপুন"
    bot.send_message(
        chat_id,
        "⚡ **QUICK MULTI-NUMBER BOT** ⚡\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "একসাথে ১ থেকে ১০টা পর্যন্ত নাম্বার নিতে পারবেন।\n\n"
        f"🔢 **/get1** থেকে **/get10** — একবারে কতগুলো নাম্বার চান সেট করুন\n"
        f"🎯 **Set Range** — কোন রেঞ্জ থেকে নাম্বার নেবেন তা একবার সেট করে রাখুন\n"
        f"📱 **GET NUMBER** — সেভ করা রেঞ্জ থেকে সরাসরি নাম্বার(গুলো) নিন\n\n"
        f"🔢 **বর্তমান কাউন্ট:** {count}টা নাম্বার\n"
        f"{range_line}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@bot.message_handler(commands=['start'])
def send_welcome(message):
    send_welcome_menu(message.chat.id, message.from_user.id)

# ──────────────────────────────────────────────────────────
# 🔢 /get1 থেকে /get10 কমান্ড — কতগুলো নাম্বার নেবে সেট করা
# ──────────────────────────────────────────────────────────
get_count_commands = [f"get{i}" for i in range(1, MAX_GET_COUNT + 1)]

@bot.message_handler(commands=get_count_commands)
def handle_get_count(message):

    # message.text হবে যেমন "/get5" — সংখ্যাটা বের করা হচ্ছে
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

# বাটন হ্যান্ডলার — content_types দিয়ে ছবি/ভয়েস/স্টিকার ইত্যাদিও ধরা হচ্ছে
@bot.message_handler(
    func=lambda message: True,
    content_types=['text', 'photo', 'voice', 'video', 'document', 'audio', 'sticker', 'video_note', 'location', 'contact']
)
def handle_text(message):
    user_id = message.from_user.id

    # 🎯 বাটন প্রেস (Set Range / GET NUMBER) সবসময় আগে চেক হবে —
    # এতে Set Range এর অপেক্ষায় থাকা অবস্থায় অন্য বাটনে চাপ দিলে সেটা রেঞ্জ হিসেবে ভুল বোঝা যাবে না
    if message.text == "🎯 Set Range":
        waiting_for_range_set.add(user_id)
        bot.send_message(
            message.chat.id,
            "⌨️ **নতুন রেঞ্জ আইডি লিখুন (e.g., 123456XXX):**\n\n(এটা সেভ হয়ে থাকবে, পরে GET NUMBER চাপলে এই রেঞ্জ থেকেই নাম্বার আসবে)",
            parse_mode="Markdown"
        )
        return

    if message.text == "📱 GET NUMBER":
        waiting_for_range_set.discard(user_id)  # অন্য বাটনে গেলে আগের "অপেক্ষা" বাতিল

        saved_range = user_saved_range.get(user_id)
        if not saved_range:
            bot.send_message(
                message.chat.id,
                "⚠️ আগে **🎯 Set Range** বাটনে চেপে একটা রেঞ্জ সেট করে নিন।",
                parse_mode="Markdown"
            )
            return

        count = user_get_count.get(user_id, DEFAULT_GET_COUNT)
        loading = bot.send_message(message.chat.id, "🔍 Searching for number(s), please wait...")
        threading.Thread(
            target=_fetch_and_send_numbers,
            args=(message.chat.id, user_id, saved_range, loading.message_id),
            daemon=True
        ).start()
        return

    # 🎯 যদি ইউজার এখন Set Range এর জন্য রেঞ্জ টাইপ করার অপেক্ষায় থাকে
    if user_id in waiting_for_range_set:
        waiting_for_range_set.discard(user_id)

        if message.content_type != 'text':
            bot.send_message(
                message.chat.id,
                "❌ Please send the range ID as **text** (e.g., 123456XXX) — ছবি/ভয়েস/স্টিকার দিয়ে রেঞ্জ সেট করা যায় না।",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
            return

        rid_input = (message.text or "").strip()
        if not re.match(r'^[\d]{3,}[X]{3,}$', rid_input, re.IGNORECASE):
            bot.send_message(
                message.chat.id,
                "❌ Wrong input! Please enter correct range ID.",
                reply_markup=main_keyboard()
            )
            return

        user_saved_range[user_id] = rid_input
        bot.send_message(
            message.chat.id,
            f"✅ রেঞ্জ সেভ হয়ে গেছে: `{rid_input}`\n\nএখন থেকে GET NUMBER চাপলে সরাসরি এই রেঞ্জ থেকেই নাম্বার আসবে।",
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        return

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

def build_multi_number_markup(rid_input, numbers):
    """একাধিক নাম্বার বাটন + একটাই Change Number বাটন + OTP Group বাটন"""
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
            callback_data=f"change_{rid_input}_{len(numbers)}",
            style="primary"
        )
    )
    markup.row(
        types.InlineKeyboardButton("🔔 OTP GROUP", url=OTP_GROUP_LINK, style="danger")
    )
    return markup

def _fetch_and_send_numbers(chat_id, user_id, rid_input, loading_message_id):
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
        result_text = (
            f"✅ **{len(numbers)} Number(s) Assigned Successfully!**\n\n"
            f"🌐 **Country:** {get_country_flag(numbers[0])[0]} {first_num_data.get('country')} ({get_country_flag(numbers[0])[1]})\n"
            f"🎯 **Range:** `{rid_input}`\n\n"
            f"🌀 **OTP Forwarded Automatically.**"
        )
        markup = build_multi_number_markup(rid_input, numbers)

        bot.delete_message(chat_id, loading_message_id)
        bot.send_message(chat_id, result_text, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.delete_message(chat_id, loading_message_id)
        bot.send_message(chat_id, "❌ No numbers available in this range. Try a different range.", reply_markup=main_keyboard())

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

    parts = call.data.split("_")
    rid_input = parts[1]
    count = int(parts[2]) if len(parts) > 2 else DEFAULT_GET_COUNT

    bot.answer_callback_query(call.id)
    bot.edit_message_text("⏳ Requesting new number(s)...", chat_id=call.message.chat.id, message_id=call.message.message_id)

    threading.Thread(
        target=_fetch_and_send_changed_numbers,
        args=(call.from_user.id, rid_input, count, call.message.chat.id, call.message.message_id),
        daemon=True
    ).start()

def _fetch_and_send_changed_numbers(user_id, rid_input, count, chat_id, message_id):
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
        updated_text = (
            f"✅ **{len(numbers)} Number(s) Changed Successfully!**\n\n"
            f"🌐 **Country:** {get_country_flag(numbers[0])[0]} {first_num_data.get('country')} ({get_country_flag(numbers[0])[1]})\n"
            f"🎯 **Range:** `{rid_input}`\n\n"
            f"🌀 **OTP Forwarded Automatically.**"
        )
        markup = build_multi_number_markup(rid_input, numbers)
        bot.edit_message_text(updated_text, chat_id=chat_id, message_id=message_id, parse_mode="Markdown", reply_markup=markup)
    else:
        bot.edit_message_text(
            "❌ Sorry, no numbers available in this range. Try a different range.",
            chat_id=chat_id,
            message_id=message_id
        )

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
