import secrets
import string
import pyodbc
import json
import pymssql
from contextlib import closing

with open('credentials.json', 'r') as f:
    credentials = json.load(f)

server = credentials.get("SERVER")
database = credentials.get("DATABASE")
login = credentials.get("LOGIN")
password = credentials.get("PASSWORD")
driver = credentials.get("DRIVER")

connection_string = f'DRIVER={driver};SERVER={server};DATABASE={database};UID={login};PWD={password}'


def connect_db():
    return pymssql.connect(server=server,
                           database=database,
                           user=login,
                           password=password)


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
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM players')
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
            cursor = conn.cursor()
            cursor.execute('SELECT player_id FROM players WHERE user_id = %s', (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None


def get_player_name_from_player_id(player_id):
    with closing(connect_db()) as db:
        with db as conn:
            row = conn.execute('SELECT first_name FROM players WHERE player_id = ?', (player_id,)).fetchone()
            return row[0] if row else None


def get_player_name_from_user_id(user_id):
    with closing(connect_db()) as db:
        with db as conn:
            row = conn.execute('SELECT first_name FROM players WHERE user_id = ?', (user_id,)).fetchone()
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
    get_player_id(685837376)
    view_table()
