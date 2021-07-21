# Info
Um chat app com rooms.

Este codigo foi feito por Martim Martins.

Exercício pedido por Vitor Rego

## Explicação de algumas partes do codigo

#### Carregamento de Coroutines events / Super Commands
    Os decorators iram meter attr (__chat_app_listener__ / __special_command__) na função que esta a utilizar o decorator.

    magik method `__new__` ira passar por todas as funções, e ira tentar ter attr __chat_app_listener__ / __special_command__, se ele conseguir ira contar como um super command e ira guardar as informações que tinha na attr e no final ira meter um attr na main class como __chat_app_listener__ / __special_cmds__ que contem a cache dos special commands / eventos.

## Eventos

Todos as trocas de dados têm de ter o event_name e *params, 
event_name sera o nome do evento a ser executado.
*params sera os parametros dos evento a ser executado.

Todos os dados são recebido em forma de eventos, ou seja todas as trocas de dados ativarão sempre um evento.
O Client/user podera usar o methodo `emit` para emitir eventos para x clients.

## Server

#### Data process
    Utilizando o modulo pickle, os bytes serão convertidos para object `Data` e depois ira executar x evento.

#### Server errors
    Quando é emitido um server error ao client, significa que os dados recebido do evento não são corretos,
    exemplo, Quando o client tenta entrar em um room que não existe.

    Como se fosse um feedback do servidor mas apenas quando o feedback é negativo o evento será emitido.

#### Rooms
    Quando o servidor iniciar ira ser criado o room MAIN_CHANNEL_NAME (Que esta setado no config.py).
    Um room tem (name, id, users), parametro users é utilizado para guardar socket objects, ou seja quando um user entrar em um room, servidor ira guardar socket object do client (Quem entrou) no room (Que esta na cache _rooms)
    name é o nome do room e o id é o unique id do room.

#### Quando existe um novo client
    O servidor ira criar um tasks que ficara infinitamente a ler dados (de até 4028 bytes), todos os dados recebido irão ser processados(.Data process), ate o client enviar bytes object empty que significa que o client fechou a conexão, e o socket object sera removido do room.

    Servidor começa por enviar rooms cache (Dict[str, Channel]), que contem todo os rooms disponíveis,
    que o client ira utilizar para ver quais servidores estão disponiveis e é enviado o User object (DO CLIENT) para o client,
    é enviado o user object quando existe um novo client para o client não conseguir fazer User object, sempre que o client tentar criar outro objecto falso com as mesma propriedades o servidor vai estar sempre a verificar se o objecto é do tipo `User`.

#### Quando existe um novo room criado
    É updeitado a cache _rooms e emitido evento on_room_created para todos os client que estão conectados ao server.

#### Quando existe um novo room updeitado
    É enviado o channel object (COM AS ALTERAÇÕES) para todos os clients que estiverem conectados ao servidor.

#### Quando existe um messagem
    É verificado se o user que enviou a messagem esta realmente no room, se não ira emitir um server_error,
    se sim, ira emitir on_message para todos os users que estiverem no room.

## Client

#### Server connection
    O client começa por criar uma coneção ao servidor utilizando `asyncio.Protocol` (obtei por utlizar asyncio.Protocol para ficar mais organizado.), que ira inciar connection_made, e o clieent ira enviar on_user_login, para depois receber evento emitido do servidor que envia rooms cahce e o User object do client.

#### Data receive
    asyncio Protocol facilita o trabalho, e têm um event de `Protocol.data_received` que ira executar sempre que dados são recebidos, esses dados ira passar pelo mesmo processo do servidor `.Data process`

#### Rooms & Cache update
    O Client podera entrar em um room, e client recebera updeites sempre que um room é updeitado (Por exemplo, alguem criar um room, ou algum joim em um room), se o client tentar entrar / sair em um room que não é valido (Ou seja que não esta na cache do servidor) ou se já tiver em algum outro room (e tiver mudado o client para no client-side parecer que não esta em nenhum) ou se tiver um client User object falso (Ou seja criado no client-side e não no server-side), o client ira receber um server_error.
    
#### Super Commands
    Super comandos é como se fosse uma forma de o client interagir com o servidor ou apenas com o client.

    Um Super Command pode ser criado utilizando um decorator `_special_command` que ira criar um attr na função, mas para funcionar SpecialCommands tem de dar na subclass na class `ClientTCP` no client-side,
    para a subclass conseguir ter acesso as funções/attrs que existem no client-side, e o client-side ter acesso as funções/attrs na subclass (Os Super Commands iram ser carregados na mesma se o class `SpecialCommands` for instanciada normalmente, mas o client-side/SpecialCommands não iram ter acesso a funções que o client-side/SpecialCommands utilizam!).