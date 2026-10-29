"""
services/watchlist_service.py — CineLog (feature/watchlist branch)

Business logic for the watchlist feature.
"""

from app import db
from models import Film, WatchlistEntry
from services.collection_service import FilmNotFoundError


class AlreadyInWatchlistError(Exception):
    """Raised when a film is already on the user's watchlist."""
    pass


def add_to_watchlist(user_id, film_id, public=False):
    """
    Add a film to a user's watchlist.

    Args:
        user_id (str): UUID of the user.
        film_id (int): ID of the film. (Note: integer — pre-refactor)
        public (bool, optional): Whether other users may see this entry.
            Defaults to False (private) — see pr-response.md, Comment 4.

    Returns:
        WatchlistEntry: The newly created entry.

    Raises:
        FilmNotFoundError: If film_id does not exist.
        AlreadyInWatchlistError: If the film is already on the user's watchlist.
    """
    film = db.session.get(Film, film_id)
    if film is None:
        raise FilmNotFoundError(f"No film found with id '{film_id}'")

    existing = WatchlistEntry.query.filter_by(
        user_id=user_id, film_id=film_id
    ).first()
    if existing:
        raise AlreadyInWatchlistError(
            f"Film '{film_id}' is already on this user's watchlist"
        )

    entry = WatchlistEntry(user_id=user_id, film_id=film_id, public=public)
    db.session.add(entry)
    db.session.commit()
    return entry


WATCHLIST_SORTS = ("date_added", "title")


def get_watchlist(user_id, sort="date_added"):
    """
    Return all films on a user's watchlist.

    By default the list is sorted by date added, newest first — the same
    order get_collection() uses. Pass sort="title" for an alphabetical list.

    Args:
        user_id (str): UUID of the user.
        sort (str, optional): "date_added" (default) or "title".

    Returns:
        list[dict]: List of film dicts with watchlist metadata attached.

    Raises:
        ValueError: If sort is not one of WATCHLIST_SORTS.
    """
    if sort not in WATCHLIST_SORTS:
        raise ValueError(
            f"Invalid sort '{sort}'. Expected one of: {', '.join(WATCHLIST_SORTS)}"
        )

    if sort == "title":
        order = Film.title.asc()
    else:
        order = WatchlistEntry.date_added.desc()

    entries = (
        WatchlistEntry.query
        .filter_by(user_id=user_id)
        .join(Film)
        .order_by(order)
        .all()
    )

    result = []
    for entry in entries:
        film_dict = entry.film.to_dict()
        film_dict["date_added"] = entry.date_added.isoformat()
        film_dict["public"] = entry.public
        result.append(film_dict)

    return result
