import secrets
import string
import json
import pymssql
from contextlib import closing

with open('credentials.json', 'r') as f:
    credentials = json.load(f)

server = credentials.get("SERVER")
database = credentials.get("DATABASE")
login = credentials.get("LOGIN")
password = credentials.get("PASSWORD")


def connect_db():
    conn = pymssql.connect(server=server,
                           database=database,
                           user=login,
                           password=password)
    conn.autocommit(True)
    return conn


def generate_unique_player_id():
    alphabet = string.ascii_letters + string.digits
    while True:
        player_id = ''.join(secrets.choice(alphabet) for _ in range(6))
        return player_id


def create_table():
    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.cursor()
            cursor.execute('''
            IF NOT EXISTS ( 
                SELECT * FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_NAME = 'players'
            )
            BEGIN
                CREATE TABLE players (
                    user_id INT UNIQUE,
                    first_name NVARCHAR(20),
                    username NVARCHAR(20),
                    player_id CHAR(6) PRIMARY KEY          
                )
            END
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

    while get_player_name_from_player_id(player_id):
        player_id = generate_unique_player_id()

    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO players (user_id, first_name, username, player_id)
                VALUES (%s, %s, %s, %s)
            ''', (user_id, first_name, username, player_id))
            conn.commit()


def delete_player(user_id):
    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM players WHERE user_id = %s', (user_id,))


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
            cursor = conn.cursor()
            cursor.execute('SELECT first_name FROM players WHERE player_id = %s', (player_id,))
            row = cursor.fetchone()
            return row[0] if row else None


def get_player_name_from_user_id(user_id):
    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT first_name FROM players WHERE user_id = %s', (user_id,))
            row = cursor.fetchone()
            return row[0] if row else None


def get_or_create_player(user_id, first_name, username):
    if not username:
        username = '-'

    player_id = get_player_id(user_id)
    if not player_id:
        insert_player(user_id, first_name, username)

    player_id = get_player_id(user_id)
    return player_id


def drop_table():
    with closing(connect_db()) as db:
        with db as conn:
            cursor = conn.cursor()
            cursor.execute('DROP TABLE players')


if __name__ == "__main__":
    view_table()
