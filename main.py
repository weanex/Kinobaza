"""КиноБаза — точка входа приложения."""
import os
import sys

from PyQt5 import uic
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QPixmap, QKeySequence
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDialog, QMessageBox,
    QFileDialog, QInputDialog, QTableWidgetItem, QShortcut,
)

from database import Database, Movie

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")


# ----------------------------- Диалог фильма -----------------------------
class MovieDialog(QDialog):
    """Диалог добавления/редактирования фильма (MovieDialog.ui)."""

    def __init__(self, db: Database, movie: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        uic.loadUi(os.path.join(UI_DIR, "movie_dialog.ui"), self)
        self.db = db

        # ВАЖНО: подключаем стандартные кнопки Ok/Cancel диалога
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self._fill_genres()
        self._bind()
        if movie:
            self._load(movie)

    def _fill_genres(self) -> None:
        for row in self.db.genres():
            self.combo_genre.addItem(row["name"], row["id"])

    def _bind(self) -> None:
        self.btn_poster.clicked.connect(self._choose_poster)
        self.btn_audio.clicked.connect(self._choose_audio)

    def _choose_poster(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите постер", "", "Images (*.png *.jpg *.jpeg)"
        )
        if path:
            self.edit_poster.setText(path)

    def _choose_audio(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите трейлер", "", "Audio (*.mp3 *.wav)"
        )
        if path:
            self.edit_audio.setText(path)

    def _load(self, m: dict) -> None:
        self.setWindowTitle(f"Редактирование: {m['title']}")
        self.edit_title.setText(m["title"])
        self.spin_year.setValue(m["year"])
        idx = self.combo_genre.findData(m["genre_id"])
        if idx >= 0:
            self.combo_genre.setCurrentIndex(idx)
        self.spin_rating.setValue(m["rating"])
        self.edit_poster.setText(m["poster_path"] or "")
        self.edit_audio.setText(m["audio_path"] or "")
        self.edit_desc.setPlainText(m["description"] or "")

    def data(self) -> Movie:
        return Movie(
            id=None,
            title=self.edit_title.text().strip(),
            year=self.spin_year.value(),
            genre_id=self.combo_genre.currentData(),
            rating=self.spin_rating.value(),
            poster_path=self.edit_poster.text().strip(),
            audio_path=self.edit_audio.text().strip(),
            description=self.edit_desc.toPlainText().strip(),
        )

    def accept(self) -> None:
        if not self.edit_title.text().strip():
            QMessageBox.warning(self, "Ошибка", "Название не может быть пустым.")
            return
        if self.combo_genre.currentData() is None:
            QMessageBox.warning(self, "Ошибка", "Выберите жанр.")
            return
        super().accept()


# ----------------------------- Главное окно -----------------------------
class MainWindow(QMainWindow):
    """Главное окно (MainWindow.ui)."""

    def __init__(self) -> None:
        super().__init__()
        uic.loadUi(os.path.join(UI_DIR, "main_window.ui"), self)
        self.db = Database()
        self.player = QMediaPlayer(self)
        self.current_movie_id: int | None = None

        self._populate_genres()
        self._bind()
        self._bind_hotkeys()
        self.refresh_table()

    # ---------- инициализация ----------
    def _populate_genres(self) -> None:
        self.combo_genre.addItem("Все жанры", None)
        for row in self.db.genres():
            self.combo_genre.addItem(row["name"], row["id"])

    def _bind(self) -> None:
        self.btn_refresh.clicked.connect(self.refresh_table)
        self.btn_add.clicked.connect(self.add_movie)
        self.btn_edit.clicked.connect(self.edit_movie)
        self.btn_delete.clicked.connect(self.delete_movie)
        self.btn_play.clicked.connect(self.play_trailer)
        self.btn_stop.clicked.connect(self.player.stop)

        self.edit_search.textChanged.connect(self.refresh_table)
        self.combo_genre.currentIndexChanged.connect(self.refresh_table)

        self.table_movies.doubleClicked.connect(self.edit_movie)
        self.table_movies.cellClicked.connect(self._on_cell_clicked)

        self.slider_volume.valueChanged.connect(self.player.setVolume)

        self.action_quit.triggered.connect(self.close)
        self.action_export.triggered.connect(self.export_list)
        self.action_about.triggered.connect(self.show_about)

    def _bind_hotkeys(self) -> None:
        QShortcut(QKeySequence("Ctrl+N"), self, activated=self.add_movie)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.edit_movie)
        QShortcut(QKeySequence("Delete"), self, activated=self.delete_movie)
        QShortcut(QKeySequence("F5"), self, activated=self.refresh_table)
        QShortcut(QKeySequence("Ctrl+F"), self, activated=self.edit_search.setFocus)

    # ---------- таблица ----------
    def refresh_table(self) -> None:
        rows = self.db.list_movies(
            search=self.edit_search.text().strip(),
            genre_id=self.combo_genre.currentData(),
        )
        self.table_movies.setRowCount(len(rows))
        for r, row in enumerate(rows):
            self.table_movies.setItem(r, 0, QTableWidgetItem(row["title"]))
            self.table_movies.setItem(r, 1, QTableWidgetItem(str(row["year"])))
            self.table_movies.setItem(r, 2, QTableWidgetItem(row["genre_name"]))
            self.table_movies.setItem(r, 3, QTableWidgetItem(f'{row["rating"]:.1f}'))
            self.table_movies.item(r, 0).setData(Qt.UserRole, row["id"])
        self.statusbar.showMessage(f"Найдено: {len(rows)}")

    def _selected_id(self) -> int | None:
        row = self.table_movies.currentRow()
        if row < 0:
            return None
        item = self.table_movies.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    def _on_cell_clicked(self, row: int, _col: int) -> None:
        """Клик мышью по строке — показываем постер и описание."""
        item = self.table_movies.item(row, 0)
        if not item:
            return
        self.current_movie_id = item.data(Qt.UserRole)
        movie = self.db.get_movie(self.current_movie_id)
        if not movie:
            return
        self._show_poster(movie["poster_path"])
        self.label_info.setText(
            f"<b>{movie['title']}</b> ({movie['year']})<br>"
            f"Рейтинг: {movie['rating']:.1f}<br><br>"
            f"{movie['description']}"
        )

    def _show_poster(self, path: str) -> None:
        if path and os.path.exists(path):
            pix = QPixmap(path).scaled(
                self.label_poster.width(), self.label_poster.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation,
            )
            self.label_poster.setPixmap(pix)
        else:
            self.label_poster.setText("Нет постера")

    # ---------- CRUD ----------
    def add_movie(self) -> None:
        dlg = MovieDialog(self.db, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            self.db.add_movie(dlg.data())
            self.refresh_table()
            QMessageBox.information(self, "Готово", "Фильм добавлен.")

    def edit_movie(self) -> None:
        mid = self._selected_id()
        if not mid:
            QMessageBox.information(self, "Внимание", "Выберите фильм в таблице.")
            return
        row = self.db.get_movie(mid)
        dlg = MovieDialog(self.db, movie=dict(row), parent=self)
        if dlg.exec_() == QDialog.Accepted:
            m = dlg.data()
            m.id = mid
            self.db.update_movie(m)
            self.refresh_table()

    def delete_movie(self) -> None:
        mid = self._selected_id()
        if not mid:
            return
        ans = QMessageBox.question(
            self, "Удаление", "Удалить выбранный фильм?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self.db.delete_movie(mid)
            self.refresh_table()

    # ---------- мультимедиа ----------
    def play_trailer(self) -> None:
        mid = self._selected_id() or self.current_movie_id
        if not mid:
            QMessageBox.information(self, "Внимание", "Выберите фильм.")
            return
        movie = self.db.get_movie(mid)
        path = movie["audio_path"] if movie else ""
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Аудио", "Трейлер не найден.")
            return
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self.player.setVolume(self.slider_volume.value())
        self.player.play()

    # ---------- меню ----------
    def export_list(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Экспорт", "movies.csv", "CSV (*.csv)"
        )
        if not path:
            return
        rows = self.db.list_movies()
        with open(path, "w", encoding="utf-8") as f:
            f.write("Title,Year,Genre,Rating\n")
            for r in rows:
                f.write(f"{r['title']},{r['year']},{r['genre_name']},{r['rating']}\n")
        QMessageBox.information(self, "Экспорт", f"Сохранено в {path}")

    def show_about(self) -> None:
        name, ok = QInputDialog.getText(
            self, "О программе", "Как вас зовут?", text="Студент"
        )
        if ok:
            QMessageBox.about(
                self, "КиноБаза",
                f"<h3>КиноБаза</h3><p>Менеджер коллекции фильмов.</p>"
                f"<p>Привет, {name}!</p>",
            )

    def closeEvent(self, event) -> None:  # noqa: N802
        self.db.close()
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()