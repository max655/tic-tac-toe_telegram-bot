import logging
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, CallbackContext, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

KEYBOARD_JOIN = [
            [InlineKeyboardButton("Перейти в зал очікування", callback_data='join_waiting')],
            [InlineKeyboardButton("Знайти гравця", callback_data='find_player')]
        ]
JOIN_MARKUP = InlineKeyboardMarkup(KEYBOARD_JOIN)
KEYBOARD_LEAVE = [
                [InlineKeyboardButton("Вийти із залу очікування", callback_data='leave_waiting')],
                [InlineKeyboardButton("Знайти гравця", callback_data='find_player')]
            ]
LEAVE_MARKUP = InlineKeyboardMarkup(KEYBOARD_LEAVE)

waiting_room = {}
games_in_progress = {}
user_messages = {}
user_states = {}
user_board_message_ids = {}


async def waiting_room_check(query, user_id) -> None:
    if user_id in waiting_room:
        reply_markup = LEAVE_MARKUP
    else:
        reply_markup = JOIN_MARKUP

    await query.edit_message_text(text="Зал очікування пустий.", reply_markup=reply_markup)


async def start(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    if user_states.get(user_id):
        await update.message.reply_text("Ви вже почали користуватися ботом.")
    else:
        user_states[user_id] = True
        await send_start_message(update.message, user_id)


async def send_start_message(message, user_id):
    sent_message = await message.reply_text("Привіт! Це гра в хрестики-нулики. "
                                            "Ви можете перейти в зал очікування або шукати гравця.",
                                            reply_markup=JOIN_MARKUP)
    track_user_message(user_id, sent_message)


async def handle_message(update: Update, context: CallbackContext) -> None:
    await update.message.reply_text("Неправильна команда.")


def track_user_message(user_id, message):
    if user_id not in user_messages:
        user_messages[user_id] = []
    user_messages[user_id].append(message.message_id)


async def clear_previous_message(user_id, context):
    await context.bot.delete_message(chat_id=user_id, message_id=user_messages[user_id][-1])


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
        if waiting_room:
            if not (user_id in waiting_room and len(waiting_room) == 1):
                keyboard = [
                    [InlineKeyboardButton(uname, callback_data=f'select_player_{uid}')] for uid, uname in
                    waiting_room.items() if uid != user_id
                ]
                if keyboard:
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    message = await query.edit_message_text(text="Оберіть гравця, з ким бажаєте почати гру:",
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
            await start_game(user_id, username, opponent_id, opponent_name, context)
        else:
            await query.edit_message_text(text="Обраний гравець більше недоступний.")

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
        await show_board(context, opponent_id)

    elif query.data.startswith('move'):
        await handle_move(update, context)


async def start_game(user_id, username, opponent_id, opponent_name, context):
    if opponent_id in waiting_room:
        del waiting_room[opponent_id]
    if user_id in waiting_room:
        del waiting_room[user_id]

    games_in_progress[user_id] = {
        'username': username,
        'opponent_id': opponent_id,
        'board': [' ' for _ in range(9)],
        'turn': user_id,
        'symbol': None
    }

    games_in_progress[opponent_id] = {
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


async def show_board(context, user_id):
    game = games_in_progress[user_id]
    board = game['board']
    turn = game['turn']
    text = "Ваш хід." if user_id == turn else "Хід суперника."
    keyboard = [
        [InlineKeyboardButton(board[i * 3 + j], callback_data=f'move{i * 3 + j}') for j in range(3)] for i in range(3)
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if user_id not in user_board_message_ids:
        message = await context.bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup)
        user_board_message_ids[user_id] = message.message_id
    else:
        await context.bot.edit_message_text(chat_id=user_id, message_id=user_board_message_ids[user_id], text=text,
                                            reply_markup=reply_markup)


async def handle_move(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    move_index = int(data[4:])
    game = games_in_progress[user_id]
    opponent_id = game['opponent_id']

    if user_id != game['turn']:
        await query.answer(text="Зараз не ваш хід!")
        return

    if game['board'][move_index] != ' ':
        await query.answer(text="Неправильний хід!")
        return

    user_symbol = game['symbol']
    opponent_symbol = games_in_progress[opponent_id]['symbol']
    game['board'][move_index] = user_symbol if user_id == game['turn'] else opponent_symbol

    winner = check_winner(game['board'])
    if winner:
        await announce_winner(context, user_id, winner)

        del user_board_message_ids[user_id]
        del user_board_message_ids[opponent_id]

        del games_in_progress[user_id]
        del games_in_progress[opponent_id]

        del user_states[user_id]
        del user_states[opponent_id]
        return
    elif ' ' not in game['board']:
        await announce_draw(context, user_id)

        del user_board_message_ids[user_id]
        del user_board_message_ids[opponent_id]

        del games_in_progress[user_id]
        del games_in_progress[opponent_id]

        del user_states[user_id]
        del user_states[opponent_id]
        return

    game['turn'] = opponent_id if user_id == game['turn'] else user_id
    games_in_progress[opponent_id]['turn'] = game['turn']

    await show_board(context, user_id)
    await show_board(context, opponent_id)

    await query.answer()


def check_winner(board):
    winning_combinations = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6)
    ]
    for combo in winning_combinations:
        if board[combo[0]] == board[combo[1]] == board[combo[2]] != ' ':
            return board[combo[0]]
    return None


async def announce_winner(context, user_id, winner):
    game = games_in_progress[user_id]
    opponent_id = game['opponent_id']
    board = game['board']
    board_str = "\n".join(["".join(board[i * 3:(i + 1) * 3]) for i in range(3)])
    board_str = board_str.replace(' ', '⬜')
    if winner == game['symbol']:
        await context.bot.send_message(chat_id=user_id, text=f"{game['username']} виграє!\n\n{board_str}")
        await context.bot.send_message(chat_id=opponent_id, text=f"{game['username']} виграє!\n\n{board_str}")
    else:
        await context.bot.send_message(chat_id=user_id, text=f"{games_in_progress[opponent_id]['username']}"
                                                             f" виграє!\n\n{board_str}")
        await context.bot.send_message(chat_id=opponent_id, text=f"{games_in_progress[opponent_id]['username']}"
                                                                 f" виграє!\n\n{board_str}")


async def announce_draw(context, user_id):
    game = games_in_progress[user_id]
    opponent_id = game['opponent_id']
    board = game['board']
    board_str = "\n".join(["".join(board[i * 3:(i + 1) * 3]) for i in range(3)])
    board_str = board_str.replace(' ', '⬜')
    await context.bot.send_message(chat_id=user_id, text=f"Нічия!\n\n{board_str}")
    await context.bot.send_message(chat_id=opponent_id, text=f"Нічия!\n\n{board_str}")


def main() -> None:
    print(f'Starting bot...')
    with open('credentials.json', 'r') as f:
        credentials = json.load(f)

    TOKEN = credentials["TOKEN"]

    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()


if __name__ == '__main__':
    main()