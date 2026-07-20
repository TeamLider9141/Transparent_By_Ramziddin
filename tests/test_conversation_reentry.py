from datetime import datetime, timezone

import pytest
from telegram import Chat, Message, PhotoSize, Update, User

import transparent


def make_photo_update(user_id, update_id=1, message_id=1):
    """Build a real Update: user sends a fresh photo in a private chat."""
    chat = Chat(id=user_id, type=Chat.PRIVATE)
    from_user = User(id=user_id, first_name="Test", is_bot=False)
    photo = (
        PhotoSize(
            file_id="file_id_small",
            file_unique_id="unique_small",
            width=90,
            height=90,
        ),
        PhotoSize(
            file_id="file_id_large",
            file_unique_id="unique_large",
            width=800,
            height=800,
        ),
    )
    message = Message(
        message_id=message_id,
        date=datetime.now(timezone.utc),
        chat=chat,
        from_user=from_user,
        photo=photo,
    )
    return Update(update_id=update_id, message=message)


def test_new_photo_reenters_conversation_when_stuck_in_size_state():
    user_id = 555
    key = (user_id,)

    # Simulate the user being stuck in the SIZE state from a previous,
    # never-completed photo flow (e.g. they tapped the "🏠 /start" button
    # instead of answering the bot's prompt, leaving their conversation
    # state dangling).
    transparent.conv._conversations[key] = transparent.SIZE
    try:
        update = make_photo_update(user_id)

        result = transparent.conv.check_update(update)

        # With allow_reentry=True, the entry_points (the photo handler)
        # must be re-checked even though the user's state is still SIZE,
        # so a fresh photo restarts the flow instead of being silently
        # dropped.
        assert result
    finally:
        del transparent.conv._conversations[key]
