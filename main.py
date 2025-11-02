from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
import feedparser
import random
import requests
import re
import html
import os
from datetime import time
from dotenv import load_dotenv


load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")

USER_ID = None
USER_TOPICS = set()  # хранит пользовательские темы

DEVOPS_FEEDS = [
    "https://dev.to/feed/tag/devops",
    "https://medium.com/feed/tag/devops",
    "https://freecodecamp.org/news/tag/devops/rss"
]
SETUP_FEEDS = [
    "https://medium.com/feed/tag/desk-setup",
    "https://medium.com/feed/tag/workspace",
    "https://www.reddit.com/r/Workspaces/.rss"
]
GENERAL_FEEDS = [
    "https://medium.com/feed/tag/productivity",
    "https://medium.com/feed/tag/life",
    "https://medium.com/feed/tag/design",
    "https://medium.com/feed/tag/creativity",
    "https://medium.com/feed/tag/technology",
    "https://medium.com/feed/tag/self-improvement"
]

def fetch_feed(url):
    headers = {"User-Agent": "Mozilla/5.0 (AmirBot Reader)"}
    try:
        response = requests.get(url, headers=headers, timeout=8)
        response.raise_for_status()
        return feedparser.parse(response.text)
    except Exception as e:
        print(f"[WARN] Ошибка загрузки {url}: {e}")
        return None

def clean_html(raw_html):
    text = re.sub(r'<li[^>]*>', '\n• ', raw_html)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\s+', ' ', text)
    text = html.unescape(text)  # ← добавь эту строку
    return text.strip()

def get_image(entry):
    """Получает корректную обложку или ставит fallback"""
    for key in ("media_content", "media_thumbnail"):
        if key in entry and entry[key]:
            url = entry[key][0].get("url")
            # Medium CDN часто блокирует — пропускаем
            if url and not any(x in url for x in ["cdn-images-1.medium.com", "miro.medium.com"]):
                return url
    # Fallback картинки
    return random.choice([
        "https://i.imgur.com/WdL07ie.jpg",  # cozy workspace
        "https://i.imgur.com/AfEZyX9.jpg",  # minimalist desk
        "https://i.imgur.com/8j0Pb4v.jpg",  # coding atmosphere
        "https://i.imgur.com/4Z5xK3E.jpg",  # coffee + notebook
        "https://i.imgur.com/7Tv4l3S.jpg"   # cozy reading vibe
    ])


def get_article(feeds):
    random.shuffle(feeds)
    for feed_url in feeds:
        feed = fetch_feed(feed_url)
        if not feed or not feed.entries:
            continue
        entry = random.choice(feed.entries)
        title = entry.get("title", "Без названия")
        link = entry.get("link", "")
        summary = clean_html(entry.get("summary", "Нет описания"))
        image = get_image(entry)
        return title, link, summary, image
    return None, None, None, None

def escape_markdown(text):
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

# ---------- Команды ----------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global USER_ID
    USER_ID = update.message.chat_id
    keyboard = [[InlineKeyboardButton("📰 Читать", callback_data="menu")]]
    await update.message.reply_text(
        "👋 Привет,\nХочешь почитать что-то интересное?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def set_commands(app):
    commands = [
        BotCommand("start", "начать и открыть меню чтения"),
        BotCommand("addtopic", "добавить новую тему"),
        BotCommand("help", "показать список команд")
    ]
    await app.bot.set_my_commands(commands)

async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("✏️ Используй: /addtopic <название_темы>\nНапример: /addtopic ai-tools")
        return
    topic = context.args[0].lower()
    USER_TOPICS.add(topic)
    await update.message.reply_text(
        f"✅ Тема *{topic}* добавлена!\nТеперь она появится в меню 🎯", parse_mode="Markdown"
    )

async def show_menu(query):
    base_buttons = [
        [InlineKeyboardButton("🧠 DevOps", callback_data="devops")],
        [InlineKeyboardButton("🌿 Setup", callback_data="setup")],
        [InlineKeyboardButton("🎲 Random", callback_data="random")]
    ]
    if USER_TOPICS:
        base_buttons.append([InlineKeyboardButton("🎯 Мои темы", callback_data="custom")])
    base_buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back")])

    try:
        await query.edit_message_text("📚 Что читаем сегодня?", reply_markup=InlineKeyboardMarkup(base_buttons))
    except:
        await query.message.reply_text("📚 Что читаем сегодня?", reply_markup=InlineKeyboardMarkup(base_buttons))

async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "menu":
        await show_menu(query)
        return

    if query.data == "back":
        keyboard = [[InlineKeyboardButton("📰 Читать", callback_data="menu")]]
        await query.message.reply_text(
            "👋 Привет,\nХочешь почитать ещё?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if query.data == "custom":
        if not USER_TOPICS:
            await query.message.reply_text("🪄 У тебя пока нет добавленных тем. Добавь их командой /addtopic <тема>")
            return
        feeds = [f"https://medium.com/feed/tag/{t}" for t in USER_TOPICS]
    elif query.data == "devops":
        feeds = DEVOPS_FEEDS
    elif query.data == "setup":
        feeds = SETUP_FEEDS
    else:
        feeds = GENERAL_FEEDS

    title, link, summary, image = get_article(feeds)
    if not title:
        await query.message.reply_text("❌ Не удалось загрузить статью.")
        return

    title = escape_markdown(title)
    summary = escape_markdown(summary[:500])
    keyboard = [
        [InlineKeyboardButton("🔗 Читать оригинал", url=link)],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")]
    ]
    await query.message.reply_photo(
        photo=image,
        caption=f"*{title}*\n\n💡 {summary}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )



async def send_daily_article(context: ContextTypes.DEFAULT_TYPE):
    if not USER_ID:
        return
    title, link, summary, image = get_article(GENERAL_FEEDS)
    if not title:
        return
    title = escape_markdown(title)
    summary = escape_markdown(summary[:500])
    keyboard = [[InlineKeyboardButton("🔗 Читать статью", url=link)]]
    await context.bot.send_photo(
        chat_id=USER_ID,
        photo=image,
        caption=f"☀️ Доброе утро\n\n*{title}*\n\n💡 {summary}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Справка по командам*\n\n"
        "🆕 /start — начать и открыть меню чтения\n"
        "➕ /addtopic <тема> — добавить новую тему (например, `/addtopic ai-tools`)\n"
        "📚 В меню доступны категории:\n"
        "  🧠 DevOps\n"
        "  🌿 Setup\n"
        "  🎲 Random (случайная статья)\n"
        "  🎯 Мои темы — твои добавленные теги\n\n"
        "☕ Каждый день утром бот пришлёт новую статью."
    )
    await update.message.reply_text(text, parse_mode="Markdown")



def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtopic", add_topic))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_choice))

    job_queue = app.job_queue
    job_queue.run_daily(send_daily_article, time(hour=9, minute=0, second=0))

    app.post_init = set_commands

    print("🚀 Bot is running with help + commands menu ☕")
    app.run_polling()


if __name__ == "__main__":
    main()
