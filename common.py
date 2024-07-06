from telegram import InlineKeyboardButton, InlineKeyboardMarkup

user_messages = {}
games_in_progress = {}
timers = {}
user_board_message_ids = {}
start_messages = {}
KEYBOARD_JOIN = [
            [InlineKeyboardButton("Перейти в зал очікування", callback_data='join_waiting')],
            [InlineKeyboardButton("Знайти гравця", callback_data='find_player')],
            [InlineKeyboardButton("Налаштування", callback_data='settings')]
        ]
JOIN_MARKUP = InlineKeyboardMarkup(KEYBOARD_JOIN)
KEYBOARD_LEAVE = [
                [InlineKeyboardButton("Вийти із залу очікування", callback_data='leave_waiting')],
                [InlineKeyboardButton("Знайти гравця", callback_data='find_player')],
                [InlineKeyboardButton("Налаштування", callback_data='settings')]
            ]
LEAVE_MARKUP = InlineKeyboardMarkup(KEYBOARD_LEAVE)
tasks = []
