"""
tests/test_watchlist.py — CineLog

Tests for the watchlist service.
Follows the fixture and assertion patterns in tests/test_collection.py.
"""

import pytest
from app import create_app, db
from models import User, Film, WatchlistEntry
from services.collection_service import FilmNotFoundError
from services.watchlist_service import (
    add_to_watchlist,
    get_watchlist,
    AlreadyInWatchlistError,
)


@pytest.fixture
def app():
    """Create an isolated test app with an in-memory database."""
    app = create_app(config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def sample_user(app):
    """A user to use in tests."""
    with app.app_context():
        user = User(username="testuser", email="test@example.com")
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture
def sample_film(app):
    """A film to use in tests."""
    with app.app_context():
        film = Film(title="Paddington 2", year=2017, genre="Comedy")
        db.session.add(film)
        db.session.commit()
        return film.id


# ── Basic add ───────────────────────────────────────────────────────────────

def test_add_to_watchlist_creates_entry(app, sample_user, sample_film):
    """
    Adding a valid film should create a WatchlistEntry in the database.
    """
    with app.app_context():
        entry = add_to_watchlist(user_id=sample_user, film_id=sample_film)

        assert entry is not None
        assert entry.user_id == sample_user
        assert entry.film_id == sample_film

        # Verify it persisted
        in_db = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).first()
        assert in_db is not None


# ── Deduplication ────────────────────────────────────────────────────────────

def test_add_to_watchlist_duplicate_raises(app, sample_user, sample_film):
    """
    Adding the same film twice should raise AlreadyInWatchlistError,
    not silently create a duplicate entry.
    """
    with app.app_context():
        add_to_watchlist(user_id=sample_user, film_id=sample_film)

        with pytest.raises(AlreadyInWatchlistError):
            add_to_watchlist(user_id=sample_user, film_id=sample_film)

        # Confirm only one entry exists
        count = WatchlistEntry.query.filter_by(
            user_id=sample_user, film_id=sample_film
        ).count()
        assert count == 1


# ── Nonexistent film ─────────────────────────────────────────────────────────

def test_add_to_watchlist_nonexistent_film_raises(app, sample_user):
    """
    Adding a film_id that doesn't exist in the database should raise
    FilmNotFoundError, not a database integrity error.
    """
    with app.app_context():
        fake_film_id = "00000000-0000-0000-0000-000000000000"

        with pytest.raises(FilmNotFoundError):
            add_to_watchlist(user_id=sample_user, film_id=fake_film_id)

        # Confirm nothing was written
        assert WatchlistEntry.query.filter_by(user_id=sample_user).count() == 0


# ── get_watchlist sort order ─────────────────────────────────────────────────

def _add_two_films_on_different_days(user_id):
    """Alien added 5 days ago, Blade Runner added now."""
    from datetime import datetime, timezone, timedelta

    film_a = Film(title="Alien", year=1979, genre="Horror")
    film_b = Film(title="Blade Runner", year=1982, genre="Sci-Fi")
    db.session.add_all([film_a, film_b])
    db.session.commit()

    earlier = datetime.now(timezone.utc) - timedelta(days=5)
    later = datetime.now(timezone.utc)

    # Insert the later entry first so insertion order can't fake a pass
    db.session.add_all([
        WatchlistEntry(user_id=user_id, film_id=film_b.id, date_added=later),
        WatchlistEntry(user_id=user_id, film_id=film_a.id, date_added=earlier),
    ])
    db.session.commit()


def test_get_watchlist_returns_newest_first(app, sample_user):
    """
    get_watchlist() should default to date_added descending, matching
    get_collection(). The films are chosen so date order and alphabetical
    order disagree — a title sort would fail this test.
    """
    with app.app_context():
        _add_two_films_on_different_days(sample_user)

        titles = [f["title"] for f in get_watchlist(sample_user)]

        # Blade Runner was added later → first, even though "Alien" < "Blade Runner"
        assert titles == ["Blade Runner", "Alien"]


def test_get_watchlist_sort_by_title(app, sample_user):
    """sort="title" should return the watchlist alphabetically."""
    with app.app_context():
        _add_two_films_on_different_days(sample_user)

        titles = [f["title"] for f in get_watchlist(sample_user, sort="title")]

        assert titles == ["Alien", "Blade Runner"]


def test_get_watchlist_invalid_sort_raises(app, sample_user):
    """An unknown sort key should raise ValueError, not silently pick one."""
    with app.app_context():
        with pytest.raises(ValueError):
            get_watchlist(sample_user, sort="rating")
