"""
Este é um exemplo de um chat server que utiliza TCP Protocol, 
"""
import uuid
import os
import sys
import asyncio
import logging

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')) # Ir /../ para poder importar Utils file.
from Utils.utils import *
from Utils.configs import *
from Utils.errors import *

DEBUG = True

def _logging(debug=False):
    def wrapper(cls):
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', level=logging.DEBUG if debug else logging.WARNING)
        return cls
    return wrapper

@_logging(debug=DEBUG)
class ProtocolServer(EventsControler):
    """Este objeto ira ser criado para cara client."""
    def __init__(self) -> None:
        self._clients: list = []

        self.server_user = User( # User utilizado para enviar avisos no chat.
            name = "*SERVER* - [BOT]",
            id = 1,
            color_start = "\x1b[0;30;45m",
            color_end="\x1b[0m"
        )

        main_channel_id = str(uuid.uuid4())
        self._rooms: dict = {MAIN_CHANNEL_NAME: Channel(name=MAIN_CHANNEL_NAME, id=main_channel_id, users=list())}
        self._users_in_rooms: list = [] 

        self._messages_cache = {} # Formato :: {author_id: message_obj}

    async def new_client(self, r, w) -> None:
        self._clients += [w]
        await self.client_handler(r, w)
        self._clients.remove(w)

    async def client_left(self, r) -> None:
        """Função ira executar sempre que um user sair / sai forçadamente."""
        logging.debug(f"Conexão foi fechada com {r._transport.get_extra_info('peername')}.")
        for room in self._rooms.values():
            for reader in room.users:
                if reader._transport == r._transport:
                    logging.debug(f"Writer foi removido do channel {room.name}.")
                    room.users.remove(reader)

    async def _run(self) -> None:
        """Inicialização de socket server async I/O."""
        loop = asyncio.get_running_loop()

        server = await asyncio.start_server(self.new_client, IP_ADDRS, PORT)
        print("Servidor iniciado em: ",server.sockets[0].getsockname())
        self.loop = loop
        async with server:
            await server.serve_forever()

    @EventsControler.listener()
    async def on_user_login(self, username: str, writer) -> None:
        """
        Evento ira executar sempre que existe um registro de um user, ou seja quando alguem seta um userName.

        Parametros
        ----------
            user: `User`
            writer: `asyncio.StreamWriter`
        """
        logging.info(f"Cache dos rooms foi enviado para o {username}.")
        user = User(
            name=username,
            id=str(uuid.uuid4()),
            color_start="\x1b[6;30;42m",
            color_end="\x1b[0m"
        )
        self.emit([writer], "on_ready", client=user, rooms_cache={x.name: Channel(name=x.name, id=x.id, users=len(x.users)) 
                                                    for x in self._rooms.values()})

    @EventsControler.listener()
    async def on_room_join(self, user: User, channel: Channel, writer) -> None:
        """Esta evento ira executar sempre que um user entra em um room.
        
        Parametros
        ----------
            user: `User`
            channel: `Channel`
            writer: `asyncio.StreamWriter`

        Server Errors
        --------------
            `AlreadyInARoom`: Quando o user já esta em um room.
        """
        logging.info(f"{user} entrou no room {channel}.")
        if not isinstance(channel, Channel) or channel.name not in self._rooms.keys():
            return self.emit([writer], "on_server_error", err=InvalidRoom)
        elif not isinstance(user, User):
            return self.emit([writer], "on_server_error", err=UserNotFound)
        elif user.id in self._users_in_rooms:
            return self.emit([writer], "on_server_error", err=AlreadyInARoom)

        self._rooms[channel.name].users += [writer]
        self._users_in_rooms += [user.id]

        self.emit(self._rooms[channel.name].users, "on_message", message=Message(
            text=f"{user.name} Entrou neste chat.",
            author=self.server_user,
            id=1,
            channel=channel)
            )
        channel.users += 1
        self.emit(self._clients, "on_room_update", channel=channel)

    @EventsControler.listener()
    async def on_room_left(self, user: User, channel: Channel, writer) -> None:
        """Esta evento ira executar sempre que um user sair de um room.
        
        Parametros
        ----------
            user: `User`
            channel: `Channel`
            writer: `asyncio.StreamWriter`

        Server Errors
        --------------
            UserNotInChannel: Quando o user não está em nenhum room para sair.
        """
        logging.info(f"{user} saiu do room {channel}.")
        if not isinstance(channel, Channel) or channel.name not in self._rooms.keys():
            return self.emit([writer], "on_server_error", err=InvalidRoom)
        elif not isinstance(user, User):
            return self.emit([writer], "on_server_error", err=UserNotFound)
        elif user.id not in self._users_in_rooms:
            return self.emit([writer], "on_server_error", err=UserNotInChannel)

        self._users_in_rooms.remove(user.id)

        self.emit(self._rooms[channel.name].users, "on_message", message=Message(
            text=f"{user.name} Saiu deste chat.",
            author=self.server_user,
            id=1,
            channel=channel
        ))
        channel.users - 1
        self.emit(self._clients, "on_room_update", channel=channel)
        self._rooms[channel.name].users.remove(writer)

    @EventsControler.listener()
    async def on_room_created(self, channel: Channel, writer) -> None:
        """Esta evento ira executar sempre que um room é criado.
        
        Parametros
        ----------
            channel: `Channel` - Room object
            writer: `asyncio.StreamWriter` - Socket writer object
        """
        logging.info(f"{channel} foi criado.")
        if channel.name in self._rooms.keys():
            return self.emit([writer], "on_server_error", err=RoomAlreadyExist)
        self._rooms[channel.name] = Channel(
            name=channel.name,
            id=channel.id,
            users=list()
        )
        self.emit(self._clients, "on_room_created", room=channel)

    @EventsControler.listener()
    async def on_room_deleted(self, channel: Channel, writer) -> None:
        """Esta evento ira executar sempre que um room é deletado.
        
        Parametros
        ----------
            channel: `Channel`
            writer: `asyncio.StreamWriter`
        """
        logging.info(f"{channel} foi deletado.")
        self._rooms.pop(channel.name)
        self.emit(self._clients, "on_room_deleted", room=channel)

    @EventsControler.listener()
    async def on_message(self, message: Message, writer) -> None:
        """
        Esta evento ira executar cada vez que existe uma troca de dados ao utilizadores.

        Parametros
        ----------
            message: `Message`
        """
        logging.info(f"Messagem recebida de {message.author}")
        if writer not in self._rooms[message.channel.name].users:
            return self.emit([writer], "on_server_error", err=UserNotInChannel)
            
        # send message para todos os clients que estão no room.
        self.emit(self._rooms[message.channel.name].users, "on_message", message=message)

def _main():
    obj = ProtocolServer()
    asyncio.run(obj._run())

if __name__ == "__main__":
    _main()