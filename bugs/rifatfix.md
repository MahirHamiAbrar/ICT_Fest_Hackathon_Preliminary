# Authentication Bug Fixes

Here is a human-friendly breakdown of all the authentication-related bugs that were discovered and fixed during testing.

## 1. The Duplicate Username Bug (Impersonation)
**File:** `app/routers/auth.py`
**Function:** `register`

**What it was before:** 
When someone tried to register an account with a username that already existed in their organization, the code just queried the database to find that existing user and quietly returned their information back with a `201 Created` status code. This was a critical security flaw because it essentially logged the attacker into the existing user's account (impersonation) instead of rejecting the registration.

**How it was fixed:** 
We changed the logic so that if the user already exists (`existing is not None`), the system completely rejects the request by raising an `AppError` with a `409` status code and a "USERNAME_TAKEN" message.

## 2. The Very Long Token Lifetime Bug
**File:** `app/auth.py`
**Function:** `create_access_token`

**What it was before:** 
Access tokens are supposed to expire in 15 minutes (900 seconds) according to the business rules. However, the `timedelta` calculation was mistakenly doing `minutes=ACCESS_TOKEN_EXPIRE_MINUTES * 60`. Since `ACCESS_TOKEN_EXPIRE_MINUTES` is 15, multiplying by 60 caused the token to last for 900 *minutes* (15 hours) instead!

**How it was fixed:** 
We removed the `* 60` multiplication. The calculation is now simply `timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)`, which accurately sets the lifespan to exactly 15 minutes.

## 3. The Flawed Token Revocation Bug (Logout Issues)
**File:** `app/auth.py`
**Functions:** `get_token_payload` and `decode_token`

**What it was before:** 
When a user logged out, their access token's unique ID (`jti`) was placed into a `_revoked_tokens` list. But when checking if a token was revoked on subsequent requests, the `get_token_payload` function accidentally checked if the user's ID (`sub`) was on that list, rather than the token's ID (`jti`). Because of this mix-up, the revocation check never actually worked properly, and worse, if it did match, it would revoke *all* tokens for that user ID. Furthermore, this check was completely bypassed for refresh tokens.

**How it was fixed:** 
We removed the broken check from `get_token_payload`. We then added a reliable check directly into the `decode_token` function that correctly checks if the token's unique ID is revoked: `if payload.get("jti") in _revoked_tokens`. Now, any token that is decoded—whether it's an access token or a refresh token—is properly checked against the blacklist.

## 4. The Infinite Refresh Token Bug
**File:** `app/routers/auth.py`
**Function:** `refresh`

**What it was before:** 
The business rules strictly state that refresh tokens are single-use. They should give you a new pair of tokens and instantly self-destruct. However, after decoding a valid refresh token and sending back the new pair, the code simply left the old refresh token untouched. You could reuse the same refresh token infinitely.

**How it was fixed:** 
We added a call to `revoke_access_token(data)` immediately after verifying the presented refresh token. Despite the function's specific name, this function adds the token's `jti` to the `_revoked_tokens` blacklist. Because we previously updated `decode_token` to check this blacklist, that refresh token is immediately invalidated and can never be reused.
