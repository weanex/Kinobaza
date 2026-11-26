
import sqlite3
from dataclasses import dataclass
from typing import List, Optional

DB_PATH = "kinobaza.db"


@dataclass
class Movie:
    """Модель фильма."""
    id: Optional[int]
    title: str
    year: int
    genre_id: int
    rating: float
    poster_path: str
    audio_path: str
    description: str


class Database:
    """Обёртка над sqlite3 с двумя таблицами: genres и movies."""

    def __init__(self, path: str = DB_PATH) -> None:
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()
        self._seed()

    # ---------- инициализация ----------
    def _create_tables(self) -> None:
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS genres (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                year        INTEGER NOT NULL,
                genre_id    INTEGER NOT NULL REFERENCES genres(id),
                rating      REAL DEFAULT 0,
                poster_path TEXT DEFAULT '',
                audio_path  TEXT DEFAULT '',
                description TEXT DEFAULT ''
            )
        """)
        self.conn.commit()

    def _seed(self) -> None:
        """Заполняет жанры при первом запуске."""
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM genres")
        if cur.fetchone()[0] == 0:
            self.conn.executemany(
                "INSERT INTO genres(name) VALUES (?)",
                [("Боевик",), ("Комедия",), ("Драма",), ("Фантастика",), ("Ужасы",)],
            )
            self.conn.commit()

    # ---------- жанры ----------
    def genres(self) -> List[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM genres ORDER BY name").fetchall()

    def add_genre(self, name: str) -> int:
        cur = self.conn.execute("INSERT INTO genres(name) VALUES (?)", (name,))
        self.conn.commit()
        return cur.lastrowid

    # ---------- фильмы (CRUD) ----------
    def list_movies(self, search: str = "", genre_id: Optional[int] = None) -> List[sqlite3.Row]:
        sql = ("SELECT m.*, g.name AS genre_name "
               "FROM movies m JOIN genres g ON g.id = m.genre_id WHERE 1=1")
        params: list = []
        if search:
            sql += " AND m.title LIKE ?"
            params.append(f"%{search}%")
        if genre_id:
            sql += " AND m.genre_id = ?"
            params.append(genre_id)
        sql += " ORDER BY m.title"
        return self.conn.execute(sql, params).fetchall()

    def get_movie(self, movie_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM movies WHERE id = ?", (movie_id,)
        ).fetchone()

    def add_movie(self, m: Movie) -> int:
        cur = self.conn.execute(
            "INSERT INTO movies(title, year, genre_id, rating, poster_path, audio_path, description) "
            "VALUES (?,?,?,?,?,?,?)",
            (m.title, m.year, m.genre_id, m.rating, m.poster_path, m.audio_path, m.description),
        )
        self.conn.commit()
        return cur.lastrowid

    def update_movie(self, m: Movie) -> None:
        self.conn.execute(
            "UPDATE movies SET title=?, year=?, genre_id=?, rating=?, "
            "poster_path=?, audio_path=?, description=? WHERE id=?",
            (m.title, m.year, m.genre_id, m.rating, m.poster_path,
             m.audio_path, m.description, m.id),
        )
        self.conn.commit()

    def delete_movie(self, movie_id: int) -> None:
        self.conn.execute("DELETE FROM movies WHERE id = ?", (movie_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()