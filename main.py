from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import feedparser
import random
import requests
import re
import html
import os
from datetime import time
from dotenv import load_dotenv
from typing import Set

load_dotenv()

TOKEN = os.getenv("YOUR_BOT_TOKEN")

# ---------- Источники ----------

DEVOPS_FEEDS = [
    "https://dev.to/feed/tag/devops",
    "https://medium.com/feed/tag/devops",
    "https://freecodecamp.org/news/tag/devops/rss",
]
SETUP_FEEDS = [
    "https://medium.com/feed/tag/desk-setup",
    "https://medium.com/feed/tag/workspace",
    "https://www.reddit.com/r/Workspaces/.rss",
]
GENERAL_FEEDS = [
    "https://medium.com/feed/tag/productivity",
    "https://medium.com/feed/tag/life",
    "https://medium.com/feed/tag/design",
    "https://medium.com/feed/tag/creativity",
    "https://medium.com/feed/tag/technology",
    "https://medium.com/feed/tag/self-improvement",
]

# ---------- Вспомогательные функции ----------


def get_user_topics(context: ContextTypes.DEFAULT_TYPE) -> Set[str]:
    topics = context.user_data.get("topics")
    if topics is None:
        topics = set()
        context.user_data["topics"] = topics
    return topics


def slugify_tag(topic: str) -> str:
    return re.sub(r"\s+", "-", topic.strip().lower())


def build_topics_keyboard(topics: Set[str]):
    if not topics:
        return InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("➕ Добавить тему", callback_data="hint_addtopic")],
                [InlineKeyboardButton("↩️ Назад", callback_data="menu")],
            ]
        )
    buttons = []
    row = []
    for t in sorted(topics):
        row.append(InlineKeyboardButton(t, callback_data=f"topic:{t}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("↩️ В меню", callback_data="menu")])
    return InlineKeyboardMarkup(buttons)


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
    text = re.sub(r"<li[^>]*>", "\n• ", raw_html)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    text = html.unescape(text)
    return text.strip()


def get_image(entry):
    for key in ("media_content", "media_thumbnail"):
        if key in entry and entry[key]:
            url = entry[key][0].get("url")
            if url and not any(
                x in url for x in ["cdn-images-1.medium.com", "miro.medium.com"]
            ):
                return url
    return random.choice(
        [
            "https://i.imgur.com/WdL07ie.jpg",
            "https://i.imgur.com/AfEZyX9.jpg",
            "https://i.imgur.com/8j0Pb4v.jpg",
            "https://i.imgur.com/4Z5xK3E.jpg",
            "https://i.imgur.com/7Tv4l3S.jpg",
        ]
    )


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
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


# ---------- Команды ----------


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие + сохранение chat_id"""
    chat_id = update.message.chat_id
    context.user_data["chat_id"] = chat_id
    context.application.user_data[chat_id] = {"chat_id": chat_id}

    keyboard = [[InlineKeyboardButton("📰 Читать", callback_data="menu")]]
    await update.message.reply_text(
        "👋 Привет!\nХочешь почитать что-то интересное?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def set_commands(app):
    commands = [
        BotCommand("start", "начать и открыть меню чтения"),
        BotCommand("addtopic", "добавить новую тему"),
        BotCommand("help", "показать список команд"),
    ]
    await app.bot.set_my_commands(commands)


async def add_topic(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "✏️ Используй: /addtopic <название_темы>\nНапример: /addtopic ai tools"
        )
        return

    topic = " ".join(context.args).strip().lstrip("#")
    topics = get_user_topics(context)
    topics.add(topic)

    kb = [
        [InlineKeyboardButton("🎯 Мои темы", callback_data="custom")],
        [InlineKeyboardButton("↩️ Назад в меню", callback_data="menu")],
    ]
    await update.message.reply_text(
        f"✅ Тема *{escape_markdown(topic)}* добавлена!\nОна появится в списке твоих тем.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def show_menu(query, context: ContextTypes.DEFAULT_TYPE):
    base_buttons = [
        [InlineKeyboardButton("🧠 DevOps", callback_data="devops")],
        [InlineKeyboardButton("🌿 Setup", callback_data="setup")],
        [InlineKeyboardButton("🎲 Random", callback_data="random")],
    ]

    topics = get_user_topics(context)
    if topics:
        base_buttons.append([InlineKeyboardButton("🎯 Мои темы", callback_data="custom")])

    base_buttons.append([InlineKeyboardButton("↩️ Назад", callback_data="back")])

    try:
        await query.edit_message_text(
            "📚 Что читаем сегодня?", reply_markup=InlineKeyboardMarkup(base_buttons)
        )
    except:
        await query.message.reply_text(
            "📚 Что читаем сегодня?", reply_markup=InlineKeyboardMarkup(base_buttons)
        )


async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "menu":
        await show_menu(query, context)
        return

    if data == "back":
        keyboard = [[InlineKeyboardButton("📰 Читать", callback_data="menu")]]
        await query.message.reply_text(
            "👋 Привет,\nХочешь почитать ещё?",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if data == "hint_addtopic":
        await query.message.reply_text(
            "➕ Добавь тему: `/addtopic <тема>`", parse_mode="Markdown"
        )
        return

    if data == "custom":
        topics = get_user_topics(context)
        await query.edit_message_text(
            "🎯 Твои темы:", reply_markup=build_topics_keyboard(topics)
        )
        return

    if data.startswith("topic:"):
        topic = data.split(":", 1)[1]
        slug = slugify_tag(topic)
        feeds = [f"https://medium.com/feed/tag/{slug}"]

        title, link, summary, image = get_article(feeds)
        if not title:
            await query.message.reply_text(
                "❌ Не удалось загрузить статью по этой теме."
            )
            return

        title = escape_markdown(title)
        summary = escape_markdown(summary[:500])
        keyboard = [
            [InlineKeyboardButton("🔗 Читать оригинал", url=link)],
            [InlineKeyboardButton("⬅️ К списку тем", callback_data="custom")],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu")],
        ]
        await query.message.reply_photo(
            photo=image,
            caption=f"*{title}*\n\n💡 {summary}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    feeds = (
        DEVOPS_FEEDS
        if data == "devops"
        else SETUP_FEEDS
        if data == "setup"
        else GENERAL_FEEDS
    )

    title, link, summary, image = get_article(feeds)
    if not title:
        await query.message.reply_text("❌ Не удалось загрузить статью.")
        return

    title = escape_markdown(title)
    summary = escape_markdown(summary[:500])
    keyboard = [
        [InlineKeyboardButton("🔗 Читать оригинал", url=link)],
        [InlineKeyboardButton("⬅️ Назад", callback_data="menu")],
    ]
    await query.message.reply_photo(
        photo=image,
        caption=f"*{title}*\n\n💡 {summary}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def send_daily_article(context: ContextTypes.DEFAULT_TYPE):
    """Отправляет статью всем зарегистрированным пользователям"""
    if not context.application.user_data:
        return

    for chat_id, data in context.application.user_data.items():
        if not isinstance(chat_id, int):
            continue
        title, link, summary, image = get_article(GENERAL_FEEDS)
        if not title:
            continue
        title = escape_markdown(title)
        summary = escape_markdown(summary[:500])
        keyboard = [[InlineKeyboardButton("🔗 Читать статью", url=link)]]
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image,
                caption=f"☀️ Доброе утро!\n\n*{title}*\n\n💡 {summary}",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        except Exception as e:
            print(f"[WARN] Не удалось отправить пользователю {chat_id}: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📘 *Справка по командам*\n\n"
        "🆕 /start — начать и открыть меню чтения\n"
        "➕ /addtopic <тема> — добавить новую тему (например, `/addtopic ai-tools`)\n"
        "📚 В меню доступны категории:\n"
        "  🧠 DevOps\n"
        "  🌿 Setup\n"
        "  🎲 Random\n"
        "  🎯 Мои темы — твои добавленные теги\n\n"
        "☕ Каждый день утром бот пришлёт новую статью."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ---------- Запуск ----------


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addtopic", add_topic))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_choice))

    job_queue = app.job_queue
    job_queue.run_daily(send_daily_article, time(hour=9, minute=0, second=0))

    app.post_init = lambda _: app.create_task(set_commands(app))

    print("🚀 Bot is running with multi-user daily feed ☕")
    app.run_polling()


if __name__ == "__main__":
    main()
