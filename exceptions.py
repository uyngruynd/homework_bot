class IncorrectResponseException(TypeError):
    """В ответе не обнаружены ожидаемые ключи"""
    pass


class UnknownStatusException(KeyError):
    """В ответе не обнаружены ожидаемые ключи"""
    pass
