import uuid
import os
import sys
import asyncio
import logging

from aioconsole import ainput, aprint
from typing import Dict
from datetime import datetime
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')) # Ir /../ para poder importar Utils file.
from Utils.utils import *
from Utils.configs import *
from Utils.errors import *

DEBUG = False

def _logging(debug=False):
    """Decorator para configurar o logging.
    
    Parametros
    ----------
        debug: `bool`
            Ativa ou desativa DEBUG level."""
    def wrapper(cls):
        logging.basicConfig(format='%(asctime)s [%(levelname)s] - %(message)s', level=logging.DEBUG if debug else logging.WARNING)
        return cls
    return wrapper

@_logging(debug=DEBUG)
class ClientTCP(asyncio.Protocol, EventsControler, SpecialCommands):
    def __init__(self, loop) -> None:
        self.loop = loop

        self._prefix = "!" # prefix dos special commands.

        self.username: str = input("Nome?\n\n: >> ")
        self.client: User = None

        self._rooms_cache = dict()
        self._channel_atual = None

    def connection_made(self, transport) -> None:
        """Esta função ira executar sempre que uma conexão é feita."""
        self.transport = transport
        logging.info(f"Conectado com o servidor {transport.get_extra_info('peername')}.")
        self.emit([self.transport],"on_user_login", username=self.username)
        self.invoke_scmd("help")

    def data_received(self, data: bytes) -> None:
        """Esta função ira executar sempre que o client receber dados do servidor.
        
        Parametros
        ----------
            data: `bytes`
                datos recebidos em bytes."""
        logging.debug("Data recebida do servidor.")
        return self.process_message(data)

    def connection_lost(self, exc) -> None:
        """Esta função ira executar sempre que uma conexão é fechada ou perdida."""
        logging.error("Conexão com o servidor foi perdida.")
        exit()

    @EventsControler.listener()
    async def on_ready(self, client: User, rooms_cache: Dict[str, Channel], writer) -> None:
        """Este evento ira executar sempre que o client inserir o name.
        
        Parametros
        ----------
            rooms_cache: `Dict[str, Channel]`"""
        self.client = client
        self._rooms_cache = rooms_cache

    @EventsControler.listener()
    async def on_message(self, message: Message, writer) -> None:
        """Este evento ira executar sempre que uma messagem é enviada no room atual
        
        Parametros
        ----------
            message: `Message`
                Messagem recebida."""
        await aprint(f"{datetime.now().strftime('%H:%M')} {message.author.color[0]}< {message.author.name} >{message.author.color[1]} {message.text}") # executa print em outra thread, para não causar blocking.

    @EventsControler.listener()
    async def on_server_error(self, err: Exception, writer) -> None:
        """Este evento ira executar sempre que o servidor emitir um error para o client.
        
        Parametros
        ---------
            err: `Exception`
                Error recebido do server."""
        logging.error(f"{err.__cause__}")

    @EventsControler.listener()
    async def on_room_created(self, room: Channel, writer) -> None:
        """Este evento ira executar sempre que um room é criado.
        
        Parametros
        ----------
            room: `Channel`
                Room criado."""
        self._rooms_cache[room.name] = room
        logging.debug(f"{room} adicionado a cache de rooms.")

    @EventsControler.listener()
    async def on_room_deleted(self, room: Channel, writer) -> None:
        """Este evento ira executar sempre que um room é deletado.
        
        Parametros
        ----------
            room: `Channel`
                Room deletado."""
        self._rooms_cache.pop(room.name)
        logging.debug(f"{room} deletado da cache de rooms.")

    @EventsControler.listener()
    async def on_room_update(self, channel: Channel, writer) -> None:
        """Este evento ira executar sempre que um room é updeitado, por exemplo user updeite (Quando um user entra no room).
        
        Parametros
        ----------
            room: `Channel`
                Room updeitado."""
        self._rooms_cache[channel.name] = channel
        logging.debug(f"{channel} updeitado na cache de rooms.")

    def get_channel(self, name: str) -> Channel:
        return self._rooms_cache.get(name)

    async def _main(self) -> None:

        while 1:
            message = await ainput("")

            try:
                self._process_command(message)
                continue
            except ChatException as e:
                logging.error(f"{e.__cause__}")
                continue
            except AssertionError:
                pass

            if self._channel_atual and message:
                self.emit([self.transport], "on_message", message=Message(
                    text=message,
                    id=str(uuid.uuid4()),
                    author=self.client,
                    channel=self._channel_atual
                ))
                continue

async def _connect_server_forever() -> None:
    """Esta função ira fazer a conecxão ao servdor / main function"""
    loop = asyncio.get_running_loop()

    Server_obj = ClientTCP(loop)

    await loop.create_connection(
        lambda: Server_obj,
        host=IP_ADDRS,
        port=PORT
    )

    await Server_obj._main()

if __name__ == "__main__":
    asyncio.run(_connect_server_forever())