class TokenHandlerMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class TokenHandler(metaclass=TokenHandlerMeta):
    session_tokens = []

    def save_session_token(self, token):
        self.session_tokens.append(token)

    def is_token_present(self, token):
        return token in self.session_tokens

    def delete_token(self, token):
        self.session_tokens = [
            entry for entry in self.session_tokens if entry != token]
