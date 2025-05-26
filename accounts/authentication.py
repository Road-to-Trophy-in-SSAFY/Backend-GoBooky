import logging
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

logger = logging.getLogger(__name__)


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        logger.debug("CustomJWTAuthentication: Attempting to authenticate request...")
        try:
            # Get the raw token
            header = self.get_header(request)
            if header is None:
                logger.debug("CustomJWTAuthentication: Authorization header not found.")
                return None

            raw_token = self.get_raw_token(header)
            if raw_token is None:
                logger.debug("CustomJWTAuthentication: Raw token not found in header.")
                return None

            logger.debug(
                f"CustomJWTAuthentication: Raw token found: {raw_token.decode()[:10]}..."
            )

            # Validate the token
            validated_token = self.get_validated_token(raw_token)
            logger.debug("CustomJWTAuthentication: Token validated successfully.")

            # Get the user
            user = self.get_user(validated_token)
            logger.debug(f"CustomJWTAuthentication: User retrieved: {user}")

            logger.debug("CustomJWTAuthentication: Authentication successful.")
            return user, validated_token

        except InvalidToken as e:
            logger.error(
                f"CustomJWTAuthentication: Invalid token exception: {e}", exc_info=True
            )
            # Authentication failed, return None or raise AuthenticationFailed depending on desired behavior
            # Raising AuthenticationFailed will result in a 401 response
            raise AuthenticationFailed(
                {"detail": "Invalid token", "code": "token_not_valid"},
                code="token_not_valid",
            )
        except AuthenticationFailed as e:
            logger.error(
                f"CustomJWTAuthentication: Authentication failed exception: {e}",
                exc_info=True,
            )
            raise e  # Re-raise the exception caught by DRF
        except Exception as e:
            # Catch any other unexpected errors during authentication
            logger.error(
                f"CustomJWTAuthentication: Unexpected authentication error: {e}",
                exc_info=True,
            )
            raise AuthenticationFailed(
                {"detail": "Unexpected authentication error"},
                code="authentication_error",
            )

        # If none of the above exceptions were raised, it means authentication failed for another reason
        # (e.g., get_user returned None after validation)
        logger.debug(
            "CustomJWTAuthentication: Authentication failed for unknown reason."
        )
        return None
