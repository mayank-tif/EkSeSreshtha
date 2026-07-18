from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed
from APIS.models import User


class CustomJWTAuthentication(JWTAuthentication):
    """
    Custom JWT authentication that uses APIS.User model instead of Django's default User.
    """
    
    def get_user(self, validated_token):
        """
        Attempts to find and return a user using the given validated token.
        Uses APIS.User model instead of get_user_model().
        """
        try:
            user_id = validated_token.get('user_id')
            if not user_id:
                raise InvalidToken('Token contained no recognizable user identification')
            
            user = User.objects.filter(id=user_id, status=True).first()
            if not user:
                raise AuthenticationFailed('User not found', code='user_not_found')
            
            return user
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found', code='user_not_found')
        except Exception as e:
            raise AuthenticationFailed(str(e), code='authentication_failed')


class CustomAccessToken(AccessToken):
    """
    Custom AccessToken that uses our custom user model.
    """
    pass