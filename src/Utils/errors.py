class ChatException(Exception):
    """
    Base exception class do CHATAPP-GUI
    """
    pass

class UserNotFound(ChatException):
    pass

class ChannelNotFound(ChatException):
    __cause__ = "Parece que esse room é invalido."
    pass

class MessageNotFound(ChatException):
    pass

class UserNotInChannel(ChatException):
    __cause__ = "Não estas em nenhum room."
    pass

class CommandNotFound(ChatException):
    __cause__ = "Comando invalido."
    pass

class AlreadyInARoom(ChatException):
    __cause__ = "Já estás em um room."
    pass

class InvalidRoom(ChatException):
    __cause__ = "Esse room não é valido."
    pass

class RoomAlreadyExist(ChatException):
    __cause__ = "Já existe um room com o mesmo nome."
    pass