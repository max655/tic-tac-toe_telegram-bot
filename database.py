import secrets
import string
import pyodbc
from contextlib import closing

server = '94.131.5.213,1433'
database = 'TicTacToeBot'
username = 'tictac'
password = 'tic1tac2toe3M'

connection_string = f'DRIVER={{SQL Server}};SERVER={server};DATABASE={database};UID={username};PWD={password}'


def connect_db():
    return pyodbc.connect(connection_string)


def generate_unique_player_id():
    alphabet = string.ascii_letters + string.digits
    while True:
        player_id = ''.join(secrets.choice(alphabet) for _ in range(6))
        return player_id


def create_table():
    with closing(connect_db()) as db:
        with db as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS players (
                    user_id INTEGER UNIQUE,
                    first_name VARCHAR(20),
                    username VARCHAR(20),
                    player_id VARCHAR(6) PRIMARY KEY          
                );
            ''')


def view_table():
    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.execute('SELECT * FROM players')
            rows = cursor.fetchall()
            for row in rows:
                print(row)


def insert_player(user_id, first_name, username):
    player_id = generate_unique_player_id()
    with closing(connect_db()) as db:
        with db as conn:
            conn.execute('''
                INSERT INTO players (user_id, first_name, username, player_id)
                VALUES (?, ?, ?, ?)
            ''', (user_id, first_name, username, player_id))
        db.commit()


def delete_player(user_id):
    with closing(connect_db()) as db:
        with db as conn:
            conn.execute('DELETE FROM players WHERE user_id = ?', (user_id,))


def get_player_id(user_id):
    with closing(connect_db()) as db:
        with db as conn:
            row = conn.execute('SELECT player_id FROM players WHERE user_id = ?', (user_id,)).fetchone()
            return row[0] if row else None


def get_player_name(player_id):
    with closing(connect_db()) as db:
        with db as conn:
            row = conn.execute('SELECT first_name FROM players WHERE player_id = ?', (player_id,)).fetchone()
            return row[0] if row else None


def get_or_create_player(user_id, first_name, username):
    if not username:
        username = '-'

    player_id = get_player_id(user_id)
    if not player_id:
        insert_player(user_id, first_name, username)

    player_id = get_player_id(user_id)
    return player_id


if __name__ == "__main__":
    view_table()
