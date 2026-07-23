import asyncio
import sqlite3
import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = "8900508271:AAHaCWyL-lGvbEn9me1jedi4P3asq7_vch4"
ADMIN_IDS = [1607756200, 906023660]
LOCAL_PHOTO = "bear.jpg"

FIXED_MESSAGE_HTML = (
    '<tg-emoji emoji-id="5208541126583136130">🎉</tg-emoji> Поздравляю!\n'
    '<tg-emoji emoji-id="4960744556103469024">🎁</tg-emoji> Ты выиграл(а) Мишку\n'
    '<tg-emoji emoji-id="5280598054901145762">🧸</tg-emoji> от @ifdox\n'
    '<tg-emoji emoji-id="5771711424711626153">✅</tg-emoji> Подарок в скором времени будет отправлен.\n\n'
    '<tg-emoji emoji-id="5807791714093502248">🌟</tg-emoji> Купить звезды дешево с любым способом оплаты: @nembuybot\n\n'
    '<tg-emoji emoji-id="5440660757194744323">🚨</tg-emoji> Пишите сообщения в чате, и получайте возможность так же залутать подарки.'
)

FIXED_MESSAGE_PLAIN = (
    "🎉 Поздравляю!\n"
    "🎁 Ты выиграл(а) Мишку\n"
    "🧸 от @ifdox\n"
    "✅ Подарок в скором времени будет отправлен.\n\n"
    "🌟 Купить звезды дешево с любым способом оплаты: @nembuybot\n\n"
    "🚨 Пишите сообщения в чате, и получайте возможность так же залутать подарки."
)

storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)

class SetThresholdStates(StatesGroup):
    waiting_for_threshold = State()

def init_db():
    conn = sqlite3.connect('counter.db')
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS stats (id INTEGER PRIMARY KEY, count INTEGER)')
    cur.execute('INSERT OR IGNORE INTO stats (id, count) VALUES (1, 0)')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            threshold INTEGER
        )
    ''')
    cur.execute('INSERT OR IGNORE INTO settings (id, threshold) VALUES (1, 2000)')
    conn.commit()
    conn.close()
    logger.info("База данных инициализирована.")

def get_count():
    conn = sqlite3.connect('counter.db')
    cur = conn.cursor()
    cur.execute('SELECT count FROM stats WHERE id=1')
    count = cur.fetchone()[0]
    conn.close()
    return count

def set_count(new_count):
    conn = sqlite3.connect('counter.db')
    cur = conn.cursor()
    cur.execute('UPDATE stats SET count=? WHERE id=1', (new_count,))
    conn.commit()
    conn.close()

def get_threshold():
    conn = sqlite3.connect('counter.db')
    cur = conn.cursor()
    cur.execute('SELECT threshold FROM settings WHERE id=1')
    row = cur.fetchone()
    conn.close()
    if row:
        return row[0]
    return 2000

def set_threshold(new_threshold):
    conn = sqlite3.connect('counter.db')
    cur = conn.cursor()
    cur.execute('UPDATE settings SET threshold=? WHERE id=1', (new_threshold,))
    conn.commit()
    conn.close()

def get_start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Изменить порог сообщений", callback_data="change_threshold")],
        [InlineKeyboardButton(text="Показать настройки", callback_data="show_settings")]
    ])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    logger.info(f"Команда /start от {message.from_user.id}")
    await message.reply(
        "👋 Привет! Я бот для розыгрыша подарков.\n\n"
        "Считаю сообщения в группе и при достижении порога отправляю поздравление с фото.\n\n"
        "🔹 Администраторы могут изменить порог через кнопку ниже.\n"
        "🔹 Для всех остальных – просто общайтесь и участвуйте!",
        reply_markup=get_start_keyboard()
    )

@dp.callback_query(lambda c: c.data == "change_threshold")
async def cb_change_threshold(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Callback change_threshold от {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав.", show_alert=True)
        return
    await callback.message.reply("Введите новое количество сообщений (целое число > 0):")
    await state.set_state(SetThresholdStates.waiting_for_threshold)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "show_settings")
async def cb_show_settings(callback: types.CallbackQuery):
    logger.info(f"Callback show_settings от {callback.from_user.id}")
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Нет прав.", show_alert=True)
        return
    threshold = get_threshold()
    await callback.message.reply(f"Текущий порог: {threshold} сообщений.\n\nТекст поздравления фиксирован.")
    await callback.answer()

@dp.message(StateFilter(SetThresholdStates.waiting_for_threshold))
async def process_new_threshold(message: types.Message, state: FSMContext):
    logger.info(f"Ввод нового порога от {message.from_user.id}: {message.text}")
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет прав.")
        await state.clear()
        return
    try:
        new_th = int(message.text)
        if new_th < 1:
            await message.reply("Порог должен быть > 0.")
            return
        set_threshold(new_th)
        await message.reply(f"Порог изменён на {new_th}.")
        await state.clear()
    except ValueError:
        await message.reply("Введите целое число.")

@dp.message()
async def handle_message(message: types.Message, state: FSMContext):
    if message.from_user.id == bot.id:
        return
    if message.text and message.text.startswith('/'):
        return

    current_state = await state.get_state()
    if current_state == SetThresholdStates.waiting_for_threshold.state:
        return

    current = get_count() + 1
    set_count(current)
    threshold = get_threshold()
    logger.info(f"Сообщение от {message.from_user.id}. Счётчик: {current}/{threshold}")

    if current >= threshold:
        logger.info(f"Порог достигнут! Поздравляем {message.from_user.id}")
        try:
            if os.path.exists(LOCAL_PHOTO):
                photo = FSInputFile(LOCAL_PHOTO)
               
                try:
                    await message.reply_photo(
                        photo=photo,
                        caption=FIXED_MESSAGE_HTML,
                        parse_mode="HTML"
                    )
                    logger.info("Фото с премиум-эмодзи отправлено.")
                except Exception as e:
                    logger.error(f"Ошибка при отправке с HTML: {e}")
                    
                    await message.reply_photo(
                        photo=photo,
                        caption=FIXED_MESSAGE_PLAIN
                    )
                    logger.info("Отправлен обычный текст (без премиум-эмодзи).")
            else:
                
                try:
                    await message.reply(FIXED_MESSAGE_HTML, parse_mode="HTML")
                except:
                    await message.reply(FIXED_MESSAGE_PLAIN)
                logger.info("Отправлен только текст (фото отсутствует).")
        except Exception as e:
            logger.error(f"Общая ошибка: {e}")
            await message.reply(FIXED_MESSAGE_PLAIN)
        set_count(0)
        logger.info("Счётчик сброшен.")

@dp.message(Command("set_threshold"))
async def cmd_set_threshold(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет прав.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply("Укажите число, например: /set_threshold 3000")
        return
    try:
        new_th = int(args[1])
        if new_th < 1:
            await message.reply("Порог должен быть > 0.")
            return
        set_threshold(new_th)
        await message.reply(f"Порог изменён на {new_th}.")
    except ValueError:
        await message.reply("Введите число.")

@dp.message(Command("show_settings"))
async def cmd_show_settings(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет прав.")
        return
    threshold = get_threshold()
    await message.reply(f"Текущий порог: {threshold} сообщений.\n\nТекст фиксирован.")

@dp.message(Command("reset"))
async def cmd_reset(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("Нет прав.")
        return
    set_count(0)
    await message.reply("Счётчик сброшен.")

async def main():
    logger.info("Запуск бота...")
    init_db()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")
    finally:
        await bot.session.close()
        logger.info("Бот остановлен.")

if __name__ == "__main__":
    asyncio.run(main())