import logging
import json
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, filters
from database import get_or_create_player, get_player_id, get_player_name_from_player_id, get_player_name_from_user_id
from functions import set_turn_timer, show_board, check_winner, announce_winner, announce_draw, tasks, set_confirm_timer, clear_previous_message
from common import games_in_progress, timers, user_board_message_ids, JOIN_MARKUP, LEAVE_MARKUP, user_messages
from telegram.constants import ParseMode

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

waiting_room = {}
user_states = {}


async def waiting_room_check(query, user_id) -> None:
    if user_id in waiting_room:
        reply_markup = LEAVE_MARKUP
    else:
        reply_markup = JOIN_MARKUP

    await query.edit_message_text(text="Зал очікування пустий.", reply_markup=reply_markup)


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    first_name = update.message.from_user.first_name
    username = update.message.from_user.username

    user_state = user_states.setdefault(user_id, {'awaiting_id': False,
                                                  'started': False})
    get_or_create_player(user_id, first_name, username)

    if user_state.get('started'):
        await update.message.reply_text("Ви вже почали користуватися ботом.")
    else:
        user_state['started'] = True
        await send_start_message(context, user_id)


async def send_start_message(context, user_id: int):
    sent_message = await context.bot.send_message(
        chat_id=user_id,
        text="Привіт! Вітаємо вас в грі хрестики-нулики!\n\n"
             "<b>Керування</b>\n"
             "Взаємодійте з ботом тільки за допомогою кнопок. "
             "Лише в функції пошуку гравця по його ігровому ID можете вводити текст в чат.\n\n"
             "<b>Зал очікування</b>\n"
             "Для початку гри знайдіть гравця в залі очікування або самі зайдіть в зал очікування. "
             "На підтвердження гри дається максимум 5 хвилин.\n\n"
             "<b>Ігровий процес</b>\n"
             "Після підтвердження гри символ обирає той, хто знайшов вас в залі очікування. "
             "Після вибору символу починається гра. На хід дається 20 секунд. Якщо за виділений "
             "час ви не зробите хід, система зробить хід за вас у випадковій клітинці.\n\n"
             "Бажаємо вам вдачної гри!",
        reply_markup=JOIN_MARKUP,
        parse_mode=ParseMode.HTML
    )
    track_user_message(user_id, sent_message)


async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    username = update.message.from_user.first_name

    if user_states.get(user_id, {}).get('awaiting_id'):
        player_id = update.message.text.strip()

        player_name = get_player_name_from_player_id(player_id)
        if player_name:
            if player_name != username:
                keyboard = [
                    [InlineKeyboardButton(player_name, callback_data=f'select_player_{uid}')] for uid, player_name in
                    waiting_room.items() if uid != user_id
                ]
                keyboard.append([InlineKeyboardButton("Назад", callback_data='go_back')])
                reply_markup = InlineKeyboardMarkup(keyboard)
                await context.bot.send_message(chat_id=user_id, text=f'Гравця знайдено.',
                                               reply_markup=reply_markup)
            else:
                await context.bot.send_message(chat_id=user_id, text=f'Ви не можете грати самі з собою.')
        else:
            await context.bot.send_message(chat_id=user_id, text=f'Гравця з ID ({player_id}) не знайдено '
                                                                 f'або він ще не перейшов в зал очікування.')
    else:
        await update.message.reply_text("Неправильна команда.")


def track_user_message(user_id, message):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message.message_id)


async def button(update: Update, context: CallbackContext) -> None:
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    username = query.from_user.first_name

    if query.data == 'join_waiting':
        if user_id not in waiting_room:
            waiting_room[user_id] = username
            message = await query.edit_message_text(text='Ви перейшли в зал очікування.', reply_markup=LEAVE_MARKUP)
            track_user_message(user_id, message)
        else:
            await query.edit_message_text(text="Ви вже перебуваєте в залі очікування.", reply_markup=LEAVE_MARKUP)

    elif query.data == 'leave_waiting':
        if user_id in waiting_room:
            del waiting_room[user_id]
            message = await query.edit_message_text(text='Ви вийшли із залу очікування.', reply_markup=JOIN_MARKUP)
            track_user_message(user_id, message)
        else:
            message = await query.edit_message_text(text="Ви не зайшли в зал очікування.",
                                                    reply_markup=JOIN_MARKUP)
            track_user_message(user_id, message)

    elif query.data == 'find_player':
        current_markup = update.effective_message.reply_markup

        if user_id not in user_states:
            user_states[user_id] = {'started': True}

        user_states[user_id]['reply_markup'] = current_markup
        if waiting_room:
            if not (user_id in waiting_room and len(waiting_room) == 1):
                keyboard = [
                    [InlineKeyboardButton(uname, callback_data=f'select_player_{uid}')] for uid, uname in
                    waiting_room.items() if uid != user_id
                ]
                keyboard.append([InlineKeyboardButton("Пошук гравця по ID", callback_data='find_player_by_id')])
                keyboard.append([InlineKeyboardButton("Назад", callback_data='go_back')])
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message = await query.edit_message_text(text="Список доступних гравців:",
                                                            reply_markup=reply_markup)
                    track_user_message(user_id, message)
            else:
                await waiting_room_check(query, user_id)

        else:
            await waiting_room_check(query, user_id)

    elif query.data.startswith('select_player_'):
        opponent_id = int(query.data.split('_')[-1])
        opponent_name = waiting_room.get(opponent_id)
        if opponent_name:
            keyboard = [[InlineKeyboardButton("Підтвердити гру", callback_data=f'confirm_game_{user_id}')],
                        [InlineKeyboardButton("Відхилити гру", callback_data=f'deny_game_{user_id}')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            msg_user = await context.bot.send_message(chat_id=user_id,
                                                      text=f"Очікуємо відповідь гравця {opponent_name}...\n"
                                                           f"Максимальний час очікування - 5 хвилин.")
            msg_opponent = await context.bot.send_message(chat_id=opponent_id,
                                                          text=f"Гравець {username} хоче почати з вами гру!",
                                                          reply_markup=reply_markup)
            track_user_message(user_id, msg_user)
            track_user_message(opponent_id, msg_opponent)
            await set_confirm_timer(context, opponent_id, opponent_name, user_id, username)
        else:
            reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='go_back')]])
            await query.edit_message_text(text="Обраний гравець більше недоступний.", reply_markup=reply_markup)

    elif query.data.startswith('symbol_choice_'):
        _, _, user_id_str, symbol = query.data.split('_')
        user_id = int(user_id_str)
        opponent_id = games_in_progress[user_id]['opponent_id']

        if symbol == '❌':
            games_in_progress[user_id]['symbol'] = '❌'
            games_in_progress[opponent_id]['symbol'] = '⭕'
            await clear_previous_message(user_id, context)
            await context.bot.send_message(chat_id=user_id, text="Ваш символ ❌.")
            await context.bot.send_message(chat_id=opponent_id, text="Ваш символ ⭕.")
        else:
            games_in_progress[user_id]['symbol'] = '⭕'
            games_in_progress[opponent_id]['symbol'] = '❌'
            await clear_previous_message(user_id, context)
            await context.bot.send_message(chat_id=user_id, text="Ваш символ ⭕.")
            await context.bot.send_message(chat_id=opponent_id, text="Ваш символ ❌.")

        await show_board(context, user_id)
        await set_turn_timer(context, user_id)
        await show_board(context, opponent_id)

    elif query.data.startswith('move'):
        await handle_move(update, context)

    elif query.data == 'check_id':
        player_id = get_player_id(user_id)
        keyboard = [[InlineKeyboardButton("Назад", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=f"Ваш ігровий ID:\n{player_id}", reply_markup=reply_markup)

    elif query.data == 'go_back':
        if user_id not in user_states:
            previous_markup = JOIN_MARKUP
        elif 'reply_markup' in user_states[user_id]:
            previous_markup = user_states[user_id]['reply_markup']
        else:
            previous_markup = JOIN_MARKUP

        if user_id in user_states:
            if 'awaiting_id' in user_states[user_id]:
                del user_states[user_id]['awaiting_id']
        await query.edit_message_text(text='Ви повернулися до головного меню.',
                                      reply_markup=previous_markup)

    elif query.data == 'find_player_by_id':
        updated_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton("Назад", callback_data='go_back')]])

        await query.edit_message_text(text='Введіть ID гравця:', reply_markup=updated_markup)
        user_states[user_id]['awaiting_id'] = True

    elif query.data == 'settings':
        if user_id in user_states:
            current_markup = update.effective_message.reply_markup
            user_states[user_id]['reply_markup'] = current_markup

        keyboard = [[InlineKeyboardButton("Мій ігровий ID", callback_data='check_id')],
                    [InlineKeyboardButton("Правила", callback_data='check_rules')],
                    [InlineKeyboardButton("Назад", callback_data='go_back')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Налаштування:", reply_markup=reply_markup)

    elif query.data == 'check_rules':
        if user_id not in user_states:
            reply_markup = JOIN_MARKUP
        elif 'reply_markup' in user_states[user_id]:
            reply_markup = user_states[user_id]['reply_markup']
        else:
            reply_markup = JOIN_MARKUP

        await query.edit_message_text(
            text="<b>Керування</b>\n"
                 "Взаємодійте з ботом тільки за допомогою кнопок. "
                 "Лише в функції пошуку гравця по його ігровому ID можете вводити текст в чат.\n\n"
                 "<b>Зал очікування</b>\n"
                 "Для початку гри знайдіть гравця в залі очікування або самі зайдіть в зал очікування. "
                 "На підтвердження гри дається максимум 5 хвилин.\n\n"
                 "<b>Ігровий процес</b>\n"
                 "Після підтвердження гри символ обирає той, хто знайшов вас в залі очікування. "
                 "Після вибору символу починається гра. На хід дається 20 секунд. Якщо за виділений "
                 "час ви не зробите хід, система зробить хід за вас у випадковій клітинці.\n\n",
            reply_markup=reply_markup, parse_mode=ParseMode.HTML)

    elif query.data.startswith('confirm_game_'):
        opponent_id = int(query.data.split('_')[-1])
        opponent_name = get_player_name_from_user_id(opponent_id)

        if user_id in timers:
            job = context.job_queue.get_jobs_by_name(f'confirm_timer_{user_id}')
            if job:
                job[0].schedule_removal()
            del timers[user_id]

        await start_game(user_id, username, opponent_id, opponent_name, context)

    elif query.data.startswith('deny_game_'):
        opponent_id = int(query.data.split('_')[-1])
        opponent_name = get_player_name_from_user_id(opponent_id)

        if user_id in timers:
            job = context.job_queue.get_jobs_by_name(f'confirm_timer_{user_id}')
            if job:
                job[0].schedule_removal()
            del timers[user_id]

        await clear_previous_message(user_id, context)
        await context.bot.send_message(chat_id=user_id, text=f'Ви відхилили гру з {opponent_name}.')
        await clear_previous_message(opponent_id, context)
        await context.bot.send_message(chat_id=opponent_id, text=f'Гравець {username} відхилив з вами гру.')
        return


async def start_game(user_id, username, opponent_id, opponent_name, context):
    if opponent_id in waiting_room:
        del waiting_room[opponent_id]
    if user_id in waiting_room:
        del waiting_room[user_id]

    games_in_progress[user_id] = {
        'player_id': user_id,
        'username': username,
        'opponent_id': opponent_id,
        'board': [' ' for _ in range(9)],
        'turn': user_id,
        'symbol': None
    }

    games_in_progress[opponent_id] = {
        'player_id': opponent_id,
        'username': opponent_name,
        'opponent_id': user_id,
        'board': games_in_progress[user_id]['board'],
        'turn': user_id,
        'symbol': None
    }
    await clear_previous_message(user_id, context)
    message = await context.bot.send_message(chat_id=user_id, text=f"Починаємо гру з {opponent_name}.")
    track_user_message(user_id, message)

    await clear_previous_message(opponent_id, context)
    message = await context.bot.send_message(chat_id=opponent_id, text=f"{username} почав(-ла) з вами гру.")
    track_user_message(user_id, message)

    await ask_symbol_choice(user_id, username, opponent_id, context)


async def ask_symbol_choice(user_id, username, opponent_id, context):
    keyboard = [
        [InlineKeyboardButton("❌", callback_data=f'symbol_choice_{user_id}_❌')],
        [InlineKeyboardButton("⭕", callback_data=f'symbol_choice_{user_id}_⭕')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    msg = await context.bot.send_message(chat_id=user_id, text="Виберіть ваш символ:", reply_markup=reply_markup)
    track_user_message(user_id, msg)
    await context.bot.send_message(chat_id=opponent_id, text=f"{username} вибирає свій символ...")


async def handle_move(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    move_index = int(data[4:])
    game = games_in_progress[user_id]
    opponent_id = game['opponent_id']

    if user_id != game['turn']:
        return

    if game['board'][move_index] != ' ':
        return

    user_symbol = game['symbol']
    opponent_symbol = games_in_progress[opponent_id]['symbol']
    game['board'][move_index] = user_symbol if user_id == game['turn'] else opponent_symbol

    winner = check_winner(game['board'])
    if winner:
        await announce_winner(context, user_id, winner)

        del user_board_message_ids[user_id]
        del user_board_message_ids[opponent_id]

        if game['turn'] == user_id:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            del timers[user_id]
        else:
            del timers[opponent_id]

        del games_in_progress[user_id]
        del games_in_progress[opponent_id]

        await context.bot.send_message(chat_id=user_id,
                                       text='Ви повернулися до головного меню.',
                                       reply_markup=JOIN_MARKUP)
        await context.bot.send_message(chat_id=opponent_id,
                                       text='Ви повернулися до головного меню.',
                                       reply_markup=JOIN_MARKUP)
        return
    elif ' ' not in game['board']:
        await announce_draw(context, user_id)

        del user_board_message_ids[user_id]
        del user_board_message_ids[opponent_id]

        del games_in_progress[user_id]
        del games_in_progress[opponent_id]

        if game['turn'] == user_id:
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            del timers[user_id]
        else:
            del timers[opponent_id]

        await context.bot.send_message(chat_id=user_id,
                                       text='Ви повернулися до головного меню.',
                                       reply_markup=JOIN_MARKUP)
        await context.bot.send_message(chat_id=opponent_id,
                                       text='Ви повернулися до головного меню.',
                                       reply_markup=JOIN_MARKUP)
        return

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    if user_id in timers:
        job = context.job_queue.get_jobs_by_name(f'timer_{user_id}')
        if job:
            job[0].schedule_removal()
        del timers[user_id]

    game['turn'] = opponent_id if user_id == game['turn'] else user_id
    games_in_progress[opponent_id]['turn'] = game['turn']

    await show_board(context, user_id)
    await show_board(context, opponent_id)
    await set_turn_timer(context, opponent_id)

    await query.answer()


def main() -> None:
    print(f'Starting bot...')

    with open('credentials.json', 'r') as f:
        credentials = json.load(f)

    TOKEN = credentials.get('TOKEN')

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == '__main__':
    main()
