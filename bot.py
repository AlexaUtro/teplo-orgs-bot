# -*- coding: utf-8 -*-
"""Telegram-бот Тёплого места для организаторов мероприятий.

Что делает:
  /start            приветствие (фото + текст) и три блока кнопок как в прежнем боте
  "Я у вас впервые"            ссылка на https://teplo.moscow/terms
  "Я уже работал(а) с вами"    ссылка на https://teplo.moscow/rules
  "Изменить мероприятие"       ссылка на https://teplo.moscow/event_request_change
  "Повторно провести"          бот спрашивает, какое мероприятие и на какие даты, и пересылает ответ ивент-менеджеру
  "Отменить мероприятие"       текст про отмену по телефону
  "Помощь"                     контакты менеджера, почта и телефон
  /id               показывает числовой номер чата (нужен один раз, чтобы настроить MANAGER_CHAT_ID)

Настройки берутся из файла .env (см. .env.example). Токен бота в код не вписывается.
Запуск: python bot.py
"""
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (Application, CallbackQueryHandler, CommandHandler, ContextTypes,
                          MessageHandler, filters)

HERE = Path(__file__).parent
load_dotenv(HERE / '.env')
TOKEN = os.environ['BOT_TOKEN']                                  # токен от @BotFather
MANAGER_CHAT_ID = os.environ.get('MANAGER_CHAT_ID', '').strip()  # номер чата менеджера (узнать командой /id)
SITE = 'https://teplo.moscow'
PHOTO = HERE / 'welcome.jpg'                                     # фото для приветствия (если файла нет, шлётся только текст)

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.INFO)
log = logging.getLogger('teplo-bot')

# ---------- тексты ----------
# Корпоративные премиум-эмодзи (подставляются тегом <tg-emoji>; если Telegram не примет, покажется обычный эмодзи внутри тега).
HELP_EMOJI = '<tg-emoji emoji-id="5352589626701818843">⭐</tg-emoji>'
LOGO_ID = os.environ.get('LOGO_EMOJI_ID', '').strip()   # номер премиум-эмодзи с логотипом (для приветствия), см. README
LOGO_EMOJI = f'<tg-emoji emoji-id="{LOGO_ID}">🔸</tg-emoji>' if LOGO_ID else '🔸'
WELCOME = ('<b>Привет!</b> Это бот Тёплого места, культурного пространства и коворкинга рядом с метро '
           '«Новокузнецкая» и «Третьяковская».\n\n'
           'Здесь организаторы могут:\n'
           f'{LOGO_EMOJI} подать заявку на мероприятие, впервые или повторно;\n'
           f'{LOGO_EMOJI} внести изменения в уже запланированное мероприятие.')
NEW_TEXT = ('Если вы хотите провести мероприятие, которое ранее в Тёплом месте не проводили, '
            'выберите одну из опций ниже')
EDIT_TEXT = ('Если вы хотите изменить запланированное мероприятие или повторно провести мероприятие '
             'в Тёплом месте, выберите одну из опций ниже')
ACTION_TEXT = 'Выберите нужное действие:'
CANCEL_TEXT = ('<b>Рекомендуем не отменять мероприятие, если есть зарегистрированные участники.</b>\n\n'
               'При возникновении обстоятельств непреодолимой силы, для отмены мероприятия позвоните '
               'в Тёплое место по телефону: +7 (910) 000-49-92.')
HELP_TEXT = ('Если у Вас остались вопросы, используйте один из следующих способов, чтобы получить на них ответы:\n\n'
             f'{HELP_EMOJI} написать менеджеру по организации мероприятий по адресу @event_teploemesto,\n\n'
             f'{HELP_EMOJI} написать на почтовый адрес vsem@teplo.moscow,\n\n'
             f'{HELP_EMOJI} позвонить в Тёплое место по телефону +7 910 000-49-92.')
REPEAT_ASK = ('Укажите, какое из ранее проведённых вами мероприятий вы хотите провести повторно '
              'в Тёплом месте и в какие даты.')
REPEAT_OK = ('Спасибо! Мы передали ваше сообщение ивент-менеджеру. Он свяжется с вами в Telegram '
             'в течение 3 рабочих дней.')
REPEAT_FAIL = ('Не удалось передать сообщение автоматически. Напишите, пожалуйста, ивент-менеджеру '
               'напрямую: @event_teploemesto')


def kb_new():
    return InlineKeyboardMarkup([[InlineKeyboardButton('Я у вас впервые ↗', url=f'{SITE}/terms'),
                                  InlineKeyboardButton('Я уже работал(а) с вами ↗', url=f'{SITE}/rules')]])

def kb_edit():
    return InlineKeyboardMarkup([[InlineKeyboardButton('Изменить мероприятие ↗', url=f'{SITE}/event_request_change'),
                                  InlineKeyboardButton('Повторно провести', callback_data='repeat')]])

def kb_action():
    return InlineKeyboardMarkup([[InlineKeyboardButton('Отменить мероприятие', callback_data='cancel'),
                                  InlineKeyboardButton('Помощь', callback_data='help')]])


# ---------- обработчики ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('wait_repeat', None)  # /start сбрасывает ожидание ответа про повтор
    chat = update.effective_chat.id
    if PHOTO.exists():
        with open(PHOTO, 'rb') as f:
            await context.bot.send_photo(chat, f, caption=WELCOME, parse_mode=ParseMode.HTML)
    else:
        await context.bot.send_message(chat, WELCOME, parse_mode=ParseMode.HTML)
    await context.bot.send_message(chat, NEW_TEXT, reply_markup=kb_new())
    await context.bot.send_message(chat, EDIT_TEXT, reply_markup=kb_edit())
    await context.bot.send_message(chat, ACTION_TEXT, reply_markup=kb_action())


async def my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Менеджер отправляет /id боту, получает номер чата и вписывает его в .env как MANAGER_CHAT_ID."""
    await update.message.reply_text(f'Номер этого чата: {update.effective_chat.id}')


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat = q.message.chat_id
    if q.data == 'cancel':
        await context.bot.send_message(chat, CANCEL_TEXT, parse_mode=ParseMode.HTML)
    elif q.data == 'help':
        await context.bot.send_message(chat, HELP_TEXT, parse_mode=ParseMode.HTML)
    elif q.data == 'repeat':
        context.user_data['wait_repeat'] = True
        await context.bot.send_message(chat, REPEAT_ASK)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сообщение организатора после нажатия «Повторно провести» пересылается ивент-менеджеру."""
    if not context.user_data.get('wait_repeat'):
        await update.message.reply_text('Чтобы начать, нажмите /start и выберите нужное действие.')
        return
    user = update.effective_user
    who = user.full_name + (f' (@{user.username})' if user.username else '')
    link = f'tg://user?id={user.id}'
    ok = False
    if MANAGER_CHAT_ID:
        try:
            await context.bot.send_message(
                int(MANAGER_CHAT_ID),
                'Повторное проведение мероприятия. Сообщение от организатора:\n'
                f'{who}\n{link}\n\n{update.message.text}')
            ok = True
        except Exception as e:  # менеджер не запускал бота или неверный номер чата
            log.error('Не удалось отправить менеджеру: %s', e)
    context.user_data.pop('wait_repeat', None)
    await update.message.reply_text(REPEAT_OK if ok else REPEAT_FAIL)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('id', my_id))
    app.add_handler(CallbackQueryHandler(on_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info('Бот запущен')
    app.run_polling()


if __name__ == '__main__':
    main()
