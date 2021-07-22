import asyncio
import inspect
import logging
import pickle
import uuid

from typing import Coroutine, Union, List, Any
from .errors import AlreadyInARoom, CommandNotFound, ChannelNotFound, UserNotInChannel
from .configs import *
from sys import platform
from os import system
from subprocess import call

class SpecialCommands:
    """Subclass para criar special commandos que podem ser executados pelo client."""
    def __new__(cls) -> Any:
        special_cmds = {}
        for _, e in inspect.getmembers(cls):
            try:
                cmds_kwargs = getattr(e, "__special_command__")
            except AttributeError:
                continue

            special_cmds[e.__name__] = {"func_obj": e, **cmds_kwargs}
        
        self = super().__new__(cls)
        cls.__special_cmds__ = special_cmds
        return self

    def _special_command(*args, **kwargs):
        """Decorator que ira adiconar um special command.
        
        Parametros
        ----------
            func: `Coroutine`
                função que ira ser executado quando o comando for chamado.
            **kwargs:
                argumentos para a função do comando.
        """
        def wrapper(func):
            func.__special_command__ = kwargs
            return func
        return wrapper

    def _process_command(self, message: str) -> None:
        """Função que ira processar input do client e verificar se é um comando valido.
        
        Parametros
        ----------
            message: `str`
                Input do client.
        
        Errors
        ------
            `AssertionError`
                Quando o input não é um comando ou seja não começa com o prefix setado
                ou o comando é apenas o prefix.
                
            `Exception`
                Quando o comando executado raises error.
        """
        assert message.startswith(self._prefix) or message == self._prefix, "Não existe nenhum comando na messagem."

        message = message.split()
        cmd = message[0].strip(self._prefix).lower()

        if cmd in list(self.__special_cmds__):
            try:
                self.__special_cmds__[cmd]["func_obj"](self, *message[1:])
            except Exception as e:
                logging.error(f"[{e.__class__.__name__}], Comando deu error, {e.__cause__}\n\n{e.with_traceback(e.__traceback__)}")
            return
        raise CommandNotFound

    def invoke_scmd(self, cmd: str, **kwargs):
        """Função ira executar comando pelo comand_name.
        
        Parametros
        ----------
            cmd: `str`
                Nome do comando a ser executado."""
        logging.debug(f"{cmd} foi invocado.")
        return self.__special_cmds__[cmd]["func_obj"](self, **kwargs)

    @_special_command(name="exit", description="Este comando ira sair do chat app.", usage="exit")
    def exit(self) -> None:
        logging.info("A sair...")
        exit()

    @_special_command(name="join", description="Este comando ira entrar em um chat room escolhido.", usage="join <room_name>")
    def join(self, channel_name: str) -> None:
        channel = self.get_channel(channel_name)

        if not channel:
            raise ChannelNotFound
        elif self._channel_atual: # se o client já estiver em um channel.
            raise AlreadyInARoom

        self.emit([self.transport], "on_room_join", user=self.client, channel=channel)
        self._channel_atual = channel

    @_special_command(name="leave", description="Este comando ira sair do room atual.", usage="leave")
    def leave(self) -> None:
        if self._channel_atual:
            logging.info(f"Saiste do {self._channel_atual.name}")
            self.emit([self.transport], "on_room_left", user=self.client, channel=self._channel_atual)
            self._channel_atual = None
            return
        raise UserNotInChannel

    @_special_command(name="list", description="Este comando ira listar todos os rooms disponivels atualmente.", usage="list")
    def list(self) -> None:
        message_formated = ""

        for channel in self._rooms_cache.values():
            message_formated += f"- {channel.name} | Users: `{channel.users}`\n"

        print(message_formated or "Parece que ainda não existe nenhum room disponivel :c")

    @_special_command(name="list", description="Este comando ira criar um novo room.", usage="create <channel_name>")
    def create(self, channel_name: str) -> None:
        self.emit([self.transport], "on_room_created", channel=Channel(
            name=channel_name,
            id=str(uuid.uuid4()))
        )
        print(f"[!] Criaste {channel_name} com sucesso!")

    @_special_command(name="help", description="Este comando ira mostrar este menu.", usage="help")
    def help(self) -> None:
        help_formated = "\n\n\tBem Vindo ao Chat-app, aqui podes criar rooms e falares com os teus amigos,\n\taqui tens todos os comandos que poderas utilizar para entrar em o room.\n\n"

        for cmd in self.__special_cmds__.values():
            help_formated += f"\t{self._prefix}{cmd['name']}\t | {cmd.get('description') or 'Não foi encontrado nada :c'} | Usage: {cmd.get('usage') or 'Não foi encontrado nada :c'}\n"

        print(help_formated)

    @_special_command(name="clear", description="Este comando ira limpa o terminal utilizando comando `clear | cls`.", usage="clear")
    def clear(self) -> None:
        if platform == "win32": # se for windows ..
            return system("cls")
        return system("clear")

    @_special_command(name="terminal", description="Este comando ira executar comandos no terminal.", usage="terminal <command arg arg2>")
    def terminal(self, *cmd) -> None:
        return call(list(cmd), timeout=30)

    @_special_command(name="eval", description="Debug tool para executar codigo.", usage="eval <code>")
    def eval(self, *code) -> None:
        exec(*code)
        
class Data:
    """class usado na troca de dados no socket server.
    
    Parametros
    ----------
        method_name: `str`
        kwargs: `Any`"""

    def __init__(self, method_name:str, **kwargs) -> None:
        self._method_name = method_name
        self._params = kwargs

class EventsControler:
    """Subclass usado para defenir eventos na class"""
    def __new__(cls, *args, **kwargs) -> Any:
        listeners: dict = {}

        for _, e in inspect.getmembers(cls):
            try:
                getattr(e, "__chat_app_listener__")
            except AttributeError:
                continue

            try:
                listeners[e.__name__].append(e) # lista para supportar multiplos events functions
            except (AttributeError, KeyError):
                listeners[e.__name__] = [e]
        
        self = super().__new__(cls)
        cls.__chat_app_listeners__ = listeners

        return self

    def emit(self, clients: List[asyncio.streams.StreamWriter], event_name: str, **kwargs) -> bool:
        """Função que ira emitir um evento.
        
        Parametros
        ----------
            clients: `List[asyncio.streams.StreamWriter]`
                Evento ira ser emitido para todos os clients que tiverem na clients list.
                
            event_name: `str`
                Nome do evento a ser emitido
                
            **kwargs: `Any`
                Argumentos do evento a ser emitido."""
        if not clients:
            clients = self._clients

        for client in clients:
            client.write(
                pickle.dumps(
                    Data(
                        method_name=event_name,
                        **kwargs)))
        logging.debug(f"Foi emitido evento {event_name} para {len(clients)} users.")
        return True

    async def client_handler(self, r, w) -> None:
        """Função executada sempre que um user se conectar ao servidor."""
        logging.debug(f"Conexão foi estabelecida com {w._transport.get_extra_info('peername')}.")
        while True:
            data: bytes = await r.read(4028)

            if not data: #SE DATA FOR NONE (empty object bytes), Significa que o client deu CTRL + C ou saiu forçadamente.
                await self.client_left(r)
                break

            logging.debug(f"Data recebida de {w._transport.get_extra_info('peername')}.")
            
            self.process_message(data, w)
            await w.drain()
        w.close()

    @staticmethod
    def listener():
        """Decorator para adicionar coroutine function como um listener de eventos emitidos pelo servidor.
        
        Errors
        ------
            `TypeError`: Listener function não é coroutine"""
        def wrapper(func):
            if not inspect.iscoroutinefunction(func):
                raise TypeError("Listener function deve ser coroutine.")

            func.__chat_app_listener__ = func.__name__

            return func
        return wrapper

    def _run_event(self, event_func, **args) -> None:
        """
        Isto ira iniciar (criar uma task em backgroud) o evento, a função que receve o evento ira executar,

        Returns
        -------
            None >> Quando não existe nenhuma função que recebe o tipo de evento recebido, ou seja não foi registado.
        """
        if event_func:
            asyncio.create_task(event_func(self,**args))

    def process_message(self, data: bytes, writer=None) -> None:
        """Função que ira processar data e executar evento que esta indicado na data recebida."""
        try:
            data: Data = pickle.loads(data) # Ira carregar o objecto enviado em bytes, class `Data`
        except EOFError:
            return
        except Exception as e:
            print(type(e), "Deu error.")
            return

        for event in self.get_listener(data._method_name):
            logging.debug(f"Evento {event.__name__} foi recebido.")
            self._run_event(event, **data._params, writer=writer)

    def get_listener(self, name: str) -> Union[Coroutine, None]:
        """Função que ira yield listeners pelo nome.
        
        Parametros
        ----------
            name: `str`
                nome do/s listener/s que iram ser yield"""
        try:
            yield from self.__chat_app_listeners__[name] # yield todos os items que tiverem na lista do listenerEvents[name]
        except (AttributeError, KeyError):
            return None

class User():
    def __init__(self, **data) -> None:
        self.__data = data

    def __repr__(self) -> str:
        return self.__data.get("name")

    @property
    def name(self) -> str:
        return self.__data.get("name")

    @property
    def id(self) -> str:
        return self.__data.get("id")

    @property
    def color(self) -> str:
        return self.__data.get("color_start") or "\x1b[6;30;42m", self.__data.get("color_end") or "\x1b[0m"

class Message():
    def __init__(self, **kwargs) -> None:
        self.__data = kwargs

    def __repr__(self) -> str:
        return self.__data.get("text")

    @property
    def text(self):
        return self.__data.get("text")

    @property
    def id(self):
        return self.__data.get("_id")

    @property
    def author(self):
        return self.__data.get("author")

    @property
    def channel(self):
        return self.__data.get("channel")

class Channel():
    def __init__(self, **kwargs) -> None:
        self.__data = kwargs
        self.users = self.__data.get("users") if self.__data.get("users") is not None else int()

    @property
    def name(self):
        return self.__data.get("name")

    @property
    def id(self):
        return self.__data.get("id")
