import telegram.error
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext
from datetime import timedelta
from common import games_in_progress, timers, user_board_message_ids, JOIN_MARKUP, tasks
import random
import asyncio

TURN_TIME_LIMIT = timedelta(seconds=20)


async def set_turn_timer(context: CallbackContext, player_id: int) -> None:
    job = context.job_queue.run_once(
        callback=turn_timeout,
        when=TURN_TIME_LIMIT,
        data={'player_id': player_id},
        name=f'timer_{player_id}'
    )
    print(f"Set turn timer for {player_id}")
    timers[player_id] = job
    task = asyncio.create_task(set_countdown(context, player_id))
    tasks.append(task)


async def turn_timeout(context: CallbackContext) -> None:
    job = context.job
    player_id = job.data['player_id']
    game = games_in_progress.get(player_id)

    if game:
        opponent_id = game['opponent_id']

        await context.bot.send_message(
            chat_id=player_id,
            text="Час на хід вичерпано! Хід передається іншому гравцю."
        )
        await context.bot.send_message(
            chat_id=opponent_id,
            text="Ваш опонент не здійснив хід вчасно. Тепер ваш хід."
        )

        board = game['board']
        empty_cells = get_empty_cells(board)
        random_index = random.choice(empty_cells)
        game['board'][random_index] = game['symbol']

        winner = check_winner(game['board'])
        if winner:
            await announce_winner(context, player_id, winner)

            del user_board_message_ids[player_id]
            del user_board_message_ids[opponent_id]

            del games_in_progress[player_id]
            del games_in_progress[opponent_id]

            if game['turn'] == player_id:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                del timers[player_id]
            else:
                del timers[opponent_id]

            await context.bot.send_message(chat_id=player_id,
                                           text='Ви повернулися до головного меню.',
                                           reply_markup=JOIN_MARKUP)
            await context.bot.send_message(chat_id=opponent_id,
                                           text='Ви повернулися до головного меню.',
                                           reply_markup=JOIN_MARKUP)
            return
        elif ' ' not in game['board']:
            await announce_draw(context, player_id)

            del user_board_message_ids[player_id]
            del user_board_message_ids[opponent_id]

            del games_in_progress[player_id]
            del games_in_progress[opponent_id]

            if game['turn'] == player_id:
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                del timers[player_id]
            else:
                del timers[opponent_id]

            await context.bot.send_message(chat_id=player_id,
                                           text='Ви повернулися до головного меню.',
                                           reply_markup=JOIN_MARKUP)
            await context.bot.send_message(chat_id=player_id,
                                           text='Ви повернулися до головного меню.',
                                           reply_markup=JOIN_MARKUP)
            return

        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        if player_id in timers:
            job = context.job_queue.get_jobs_by_name(f'timer_{player_id}')
            if job:
                job[0].schedule_removal()
            del timers[player_id]

        game['turn'] = opponent_id
        games_in_progress[opponent_id]['turn'] = game['turn']
        await show_board(context, player_id)
        await show_board(context, opponent_id)
        await set_turn_timer(context, opponent_id)


async def set_countdown(context: CallbackContext, user_id: int):
    await asyncio.sleep(12)

    countdown_message_id = None

    for i in range(7, 0, -1):
        if countdown_message_id:
            try:
                await context.bot.edit_message_text(
                    text=f"У вас залишилося {i} секунд!",
                    chat_id=user_id,
                    message_id=countdown_message_id
                )
            except telegram.error.BadRequest:
                pass
        else:
            message = await context.bot.send_message(chat_id=user_id, text=f"У вас залишилося {i} секунд!")
            countdown_message_id = message.message_id

        await asyncio.sleep(1)


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


def get_empty_cells(board):
    empty_cells = []
    for i in range(9):
        if board[i] == ' ':
            empty_cells.append(i)
    return empty_cells


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
