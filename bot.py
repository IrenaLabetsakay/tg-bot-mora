import asyncio
import aiohttp
import feedparser
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

# ─── Новое ───────────────────────────────────────────────
from dotenv import load_dotenv
import os

load_dotenv()           # загружает .env в переменные окружения

TOKEN = os.getenv("TOKEN")
AI_API_KEY = os.getenv("AI_API_KEY")

# Проверяем, что токены загрузились (очень полезно на старте)
if not TOKEN:
    raise ValueError("TOKEN не найден в .env файле!")
if not AI_API_KEY:
    raise ValueError("AI_API_KEY не найден в .env файле!")

# ─── Дальше как было ─────────────────────────────────────
bot = Bot(token=TOKEN)   # ← теперь token=TOKEN (с маленькой буквы)
dp = Dispatcher()

BOT_USERNAME = None

SYSTEM_PROMPT = (
    "Ты полезный помощник. "
    "Всегда отвечай ТОЛЬКО на русском языке. "
    "Отвечай кратко и по делу."
)

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


# -------- /ask ----------
@dp.message(Command("ask"))
async def ask_handler(message: Message):
    question = message.text.replace("/ask", "").strip()
    if not question:
        await message.answer("❓ Напиши вопрос после команды.")
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
            await message.reply("❓ Что спросить?")
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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
