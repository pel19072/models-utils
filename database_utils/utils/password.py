import bcrypt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain-text password against a hashed password using bcrypt.

    :param plain_password: The plain-text password provided by the user.
    :param hashed_password: The hashed password stored in the database.
    :return: True if the password matches, False otherwise.
    """
    plain_password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)

def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    :param password: The plain-text password to hash.
    :return: The hashed password as a string.
    """
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed_password.decode('utf-8')