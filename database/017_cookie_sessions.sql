UPDATE auth_sessions SET revoked_at = CURRENT_TIMESTAMP(6) WHERE revoked_at IS NULL;
ALTER TABLE auth_sessions
    DROP COLUMN refresh_jti_hash,
    MODIFY COLUMN session_id CHAR(64) NOT NULL;
