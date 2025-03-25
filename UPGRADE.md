# Upgrade Instructions

## Chat Sharing Feature (March 2023)

### Database Migration

To apply the necessary database changes for the chat sharing feature, run the following command:

```bash
alembic upgrade head
```

This will add the `is_shared` column to the `chats` table.

### New API Endpoints

The following new API endpoints have been added:

1. `POST /api/chats/{chat_id}/share` - Share a chat (authenticated users)
2. `POST /api/share-anonymous-chat` - Share an anonymous chat
3. `GET /api/shared/{chat_id}` - Get a publicly shared chat (no authentication required)

### Frontend Changes

The frontend now includes:

1. A share button in the chat interface
2. A dialog for copying the shareable link
3. A new page at `/shared-chat` for viewing shared chats

### Testing

Run the test suite to ensure everything is working correctly:

```bash
./run_tests.sh
```

## Troubleshooting

If you encounter any issues:

1. Verify the database migration has been applied successfully
2. Check that the frontend is correctly communicating with the backend
3. Ensure Redis is running for anonymous chat functionality
4. Review the server logs for any errors

For support, contact the development team. 