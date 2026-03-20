class CacheMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class Cache(metaclass=CacheMeta):
    records = {}

    def hit(self, username):
        if username in self.records.keys():
            return self.records[username]
        else:
            return None

    def store(self, username, values_tuple):
        if len(self.records.keys()) > 1000:
            self.records.pop(self.records.keys()[0])
        self.records[username] = values_tuple

    def clean(self, username=None):
        if username:
            # Use pop with default to avoid KeyError if username doesn't exist
            self.records.pop(username, None)
        else:
            self.records.clear()

cache = Cache()
