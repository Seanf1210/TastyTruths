from __future__ import annotations

from sqlalchemy import and_, func, or_

from services.db import db
from services.models import FriendRequest, Friendship, User


FRIEND_REQUEST_PENDING = "pending"
FRIEND_REQUEST_ACCEPTED = "accepted"
FRIEND_REQUEST_DECLINED = "declined"
FRIEND_REQUEST_CANCELED = "canceled"
VALID_FRIEND_REQUEST_STATUSES = {
    FRIEND_REQUEST_PENDING,
    FRIEND_REQUEST_ACCEPTED,
    FRIEND_REQUEST_DECLINED,
    FRIEND_REQUEST_CANCELED,
}


class FriendshipError(ValueError):
    def __init__(self, message: str, status_code: int, error_code: str):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


def canonical_friend_pair(user_a_id: int, user_b_id: int) -> tuple[int, int]:
    if not user_a_id or not user_b_id:
        raise FriendshipError("Both users are required.", 400, "invalid_request")
    if user_a_id == user_b_id:
        raise FriendshipError("You cannot friend yourself.", 400, "self_friendship")
    return tuple(sorted((int(user_a_id), int(user_b_id))))


def get_friendship(user_a_id: int, user_b_id: int) -> Friendship | None:
    try:
        canonical_user_id, canonical_friend_id = canonical_friend_pair(user_a_id, user_b_id)
    except FriendshipError:
        return None
    return Friendship.query.filter_by(
        user_id=canonical_user_id,
        friend_id=canonical_friend_id,
    ).first()


def get_friend_ids(user_id: int | None) -> set[int]:
    if not user_id:
        return set()
    rows = Friendship.query.filter(
        or_(Friendship.user_id == user_id, Friendship.friend_id == user_id)
    ).all()
    friend_ids = set()
    for row in rows:
        friend_ids.add(row.friend_id if row.user_id == user_id else row.user_id)
    return friend_ids


def get_friends_for_user(user_id: int | None) -> list[User]:
    friend_ids = get_friend_ids(user_id)
    if not friend_ids:
        return []
    return (
        User.query.filter(User.id.in_(sorted(friend_ids)))
        .order_by(func.lower(User.username))
        .all()
    )


def get_friend_count(user_id: int | None) -> int:
    if not user_id:
        return 0
    return (
        Friendship.query.filter(
            or_(Friendship.user_id == user_id, Friendship.friend_id == user_id)
        ).count()
    )


def are_friends(user_id: int | None, friend_id: int | None) -> bool:
    if not user_id or not friend_id or user_id == friend_id:
        return False
    return get_friendship(user_id, friend_id) is not None


def add_friendship(user_a: User | int, user_b: User | int) -> Friendship:
    user_a_id = getattr(user_a, "id", user_a)
    user_b_id = getattr(user_b, "id", user_b)
    canonical_user_id, canonical_friend_id = canonical_friend_pair(user_a_id, user_b_id)

    friendship = Friendship.query.filter_by(
        user_id=canonical_user_id,
        friend_id=canonical_friend_id,
    ).first()
    if friendship is not None:
        raise FriendshipError("You are already friends.", 409, "already_friends")

    friendship = Friendship(
        user_id=canonical_user_id,
        friend_id=canonical_friend_id,
    )
    db.session.add(friendship)
    db.session.flush()
    return friendship


def remove_friendship(user_a: User | int, user_b: User | int) -> bool:
    user_a_id = getattr(user_a, "id", user_a)
    user_b_id = getattr(user_b, "id", user_b)
    if not user_a_id or not user_b_id or user_a_id == user_b_id:
        return False

    friendship = get_friendship(user_a_id, user_b_id)
    if friendship is None:
        return False

    db.session.delete(friendship)
    db.session.flush()
    return True


def get_pending_request_between(user_id: int, other_user_id: int) -> FriendRequest | None:
    if not user_id or not other_user_id:
        return None
    return (
        FriendRequest.query.filter(
            FriendRequest.status == FRIEND_REQUEST_PENDING,
            or_(
                and_(
                    FriendRequest.requester_id == user_id,
                    FriendRequest.recipient_id == other_user_id,
                ),
                and_(
                    FriendRequest.requester_id == other_user_id,
                    FriendRequest.recipient_id == user_id,
                ),
            ),
        )
        .order_by(FriendRequest.created_at.desc(), FriendRequest.id.desc())
        .first()
    )


def get_relationship_summary(viewer_user_id: int | None, profile_user_id: int) -> dict:
    summary = {
        "friend_count": get_friend_count(profile_user_id),
        "relationship_state": "none",
        "request_id": None,
    }

    if viewer_user_id is None:
        return summary
    if viewer_user_id == profile_user_id:
        summary["relationship_state"] = "self"
        return summary
    if are_friends(viewer_user_id, profile_user_id):
        summary["relationship_state"] = "friends"
        return summary

    pending_request = get_pending_request_between(viewer_user_id, profile_user_id)
    if pending_request is None:
        return summary

    summary["request_id"] = pending_request.id
    if pending_request.requester_id == viewer_user_id:
        summary["relationship_state"] = "outgoing_pending"
    else:
        summary["relationship_state"] = "incoming_pending"
    return summary


def create_friend_request(requester_id: int, recipient_id: int) -> FriendRequest:
    canonical_friend_pair(requester_id, recipient_id)
    if are_friends(requester_id, recipient_id):
        raise FriendshipError("You are already friends.", 409, "already_friends")

    pending_request = get_pending_request_between(requester_id, recipient_id)
    if pending_request is not None:
        if pending_request.requester_id == requester_id:
            raise FriendshipError("You already sent this friend request.", 409, "duplicate_request")
        raise FriendshipError(
            "This user already sent you a friend request.",
            409,
            "reverse_pending_request",
        )

    friend_request = FriendRequest(
        requester_id=requester_id,
        recipient_id=recipient_id,
        status=FRIEND_REQUEST_PENDING,
    )
    db.session.add(friend_request)
    db.session.flush()
    return friend_request


def ensure_bidirectional_friendship(user_id: int, friend_id: int) -> None:
    if not are_friends(user_id, friend_id):
        try:
            add_friendship(user_id, friend_id)
        except FriendshipError as exc:
            if exc.error_code != "already_friends":
                raise


def respond_to_friend_request(friend_request: FriendRequest, acting_user_id: int, action: str) -> str:
    normalized_action = (action or "").strip().lower()
    if normalized_action not in {"accept", "decline"}:
        raise FriendshipError("Action must be 'accept' or 'decline'.", 400, "invalid_action")
    if friend_request.recipient_id != acting_user_id:
        raise FriendshipError(
            "Only the recipient can respond to this request.",
            403,
            "forbidden",
        )
    if friend_request.status != FRIEND_REQUEST_PENDING:
        raise FriendshipError(
            f"This friend request is already {friend_request.status}.",
            409,
            "invalid_request_state",
        )

    if normalized_action == "accept":
        friend_request.status = FRIEND_REQUEST_ACCEPTED
        add_friendship(friend_request.requester_id, friend_request.recipient_id)
        db.session.flush()
        return FRIEND_REQUEST_ACCEPTED

    friend_request.status = FRIEND_REQUEST_DECLINED
    db.session.flush()
    return FRIEND_REQUEST_DECLINED
