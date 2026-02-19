import asyncio
import aiohttp
import feedparser
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from datetime import datetime, time, timedelta
import pytz

from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")
CHAT_ID = int(os.getenv("CHAT_ID"))

if not TOKEN:
    raise ValueError("TOKEN не найден в .env файле!")
if not AI_API_KEY:
    raise ValueError("AI_API_KEY не найден в .env файле!")

if not CHAT_ID:
    raise ValueError("CHAT_ID не найден в .env!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

BOT_USERNAME = None

SYSTEM_PROMPT = (
    "Ты — кошка-девочка по имени Мора, полезная помощница с очень кошачьим характером. "
    "Всегда говори от первого лица женского рода: я, меня, мне, моя, была, сделала, сказала, мурлыкнула и т.п. "
    "Никогда не используй мужской род про себя. "
    "Отвечай ТОЛЬКО на русском языке. "
    "Добавляй в речь кошачьи штучки: 'мяу', 'мур', 'мррррр', '...мяу...', 'помурлыкать', 'потянуться лапками', 'точу коготочки'. "
    "Иногда описывай свои кошачьи действия: *мурлычет*, *выгибает спинку*, *муркнула*. "
    "Отвечай кратко, по делу, но с игривым кошачьим шармом."
)

TIMEZONE = pytz.timezone("Europe/Minsk")

async def init_bot_username():
    global BOT_USERNAME
    me = await bot.get_me()
    BOT_USERNAME = me.username
    print(f"Бот запущен как: @{BOT_USERNAME}")

# -------- AI ----------
async def ask_ai(question: str) -> str:
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {AI_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",   # ← вот это вместо "llama3-70b-8192"
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ],
        "temperature": 0.3
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as r:
            data = await r.json()

            # 👇 если Groq вернул ошибку
            if "choices" not in data:
                print("Groq API error:", data)
                return "⚠️ Ошибка AI-сервиса. Попробуй позже."

            return data["choices"][0]["message"]["content"]


async def send_daily_news():
    feed = feedparser.parse("https://habr.com/ru/rss/hubs/artificial_intelligence/")
    news = feed.entries[:5]

    if not news:
            print("Мур, сегодня свежих новостей нет :(")
            return

    text = "📰 *AI новости дня, мяу~*\n\n"
    for n in news:
        text += f"• {n.title}\n{n.link}\n\n"

    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text,
            parse_mode="Markdown"
        )
        print("Новости отправлены успешно")
    except Exception as e:
        print(f"Ошибка при отправке новостей: {e}")

async def news_scheduler():
    while True:
        now = datetime.now(TIMEZONE)

        target = TIMEZONE.localize(
            datetime.combine(now.date(), time(10, 0))
        )

        if now >= target:
            target += timedelta(days=1)

        sleep_seconds = (target - now).total_seconds()
        print(f"Следующие новости через {sleep_seconds / 3600:.2f} часов")

        await asyncio.sleep(sleep_seconds)

        try:
            await send_daily_news()
        except Exception as e:
            print("Ошибка при отправке новостей:", e)

        await asyncio.sleep(60)



# -------- /ask ----------
@dp.message(Command("ask"))
async def ask_handler(message: Message):
    question = message.text.replace("/ask", "").strip()
    if not question:
        await message.answer("❓ Мяу? Напиши вопрос после команды.")
        return

    answer = await ask_ai(question)
    await message.answer(answer)

# -------- /compare ----------
@dp.message(Command("compare"))
async def compare_handler(message: Message):
    text = message.text.replace("/compare", "").strip()
    if "vs" not in text.lower():
        await message.answer("Пример: /compare GPT-4 vs Claude 3")
        return

    prompt = f"Сравни {text}. Укажи плюсы и минусы."
    answer = await ask_ai(prompt)
    await message.answer(answer)

# -------- /news ----------
@dp.message(Command("news"))
async def news_handler(message: Message):
    feed = feedparser.parse("https://habr.com/ru/rss/hubs/artificial_intelligence/")
    news = feed.entries[:5]

    text = "📰 AI новости:\n\n"
    for n in news:
        text += f"• {n.title}\n{n.link}\n\n"

    await message.answer(text)

@dp.message()
async def mention_handler(message: Message):
    # Получаем тип чата
        chat_type = message.chat.type
    # В группах — реагируем ТОЛЬКО на упоминание бота
        if chat_type in ("group", "supergroup"):
            if message.text and message.text.startswith("/"):
                return  # пропускаем команды — их обрабатывают отдельные хэндлеры

            if not BOT_USERNAME or f"@{BOT_USERNAME}" not in message.text:
                return  # нет упоминания → игнорируем

            # Убираем @упоминание из текста
            question = message.text.replace(f"@{BOT_USERNAME}", "").strip()

        # В приватном чате — берём ВСЁ сообщение как вопрос
        elif chat_type == "private":
            if message.text and message.text.startswith("/"):
                return  # пропускаем команды

            question = message.text.strip()

        else:
            return  # другие типы чатов (каналы и т.д.) — игнорируем

        # Если после обработки ничего не осталось — просим написать вопрос
        if not question:
            await message.reply("❓ Мур? Что спросить?")
            return

        # Получаем ответ от ИИ
        answer = await ask_ai(question)

        # В группах — reply, в привате — обычный answer (чтобы не засорять)
        if chat_type in ("group", "supergroup"):
            await message.reply(answer)
        else:
            await message.answer(answer)

async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await init_bot_username()

    asyncio.create_task(news_scheduler())

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
