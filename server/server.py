"""
Copyright (c) 2013, Alex O'Konski
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright
  notice, this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright
  notice, this list of conditions and the following disclaimer in the
  documentation and/or other materials provided with the distribution.
* Neither the name of ping nor the
  names of its contributors may be used to endorse or promote products
  derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
"""

import heelhook
from heelhook import Server, ServerConn, CloseCode, LogLevel
from game import PlayerType, Game, Location
import sys

try:
    import ujson as json
except:
    import json

heelhook.set_opts(loglevel=LogLevel.DEBUG_2, log_to_stdout=True)

class GameClient(ServerConn):
    """Messages received from clients:

    {
        "type": "join",
        "name": "<player name>"
    }

    {
        "type": "move",
        "direction": "<N|S|E|W>"
    }

    {
        "type": "shoot",
        "direction": "<N|S|E|W>"
    }

    {
        "type": "place",
        "shape_index": <int>,
        "origin": [<x>, <y>]
    }

    {
        "type": "ping"
    }

    Messages sent to clients:

    {
        "type": "joined",
        "board_width": <int>,
        "moves_per_turn": <int>
        "shapes": [
            [[x, y], [x, y], ...],
            [[x, y], [x, y], ...],
        ]
    }

    {
        "type": "start",
        "turn": "<white|black>",
        "turn_number": <int>,
        "moves_remaining": <int>,
        "your_color": "<white|black>",
        "opponent": <str>,
        "board": {
            "white_player": [x, y],
            "black_player": [x, y],
            "white_block" : [[x, y], [x, y], ...],
            "black_block" : [[x, y], [x, y], ...]
        }
    }

    {
        "type": "update",
        "turn": <white|black>,
        "turn_number": <int>,
        "moves_remaining": <int>,
        "ping_saw_opponent": <bool>
        "board": {
            "white_player": [x, y],
            "black_player": [x, y],
            "white_block" : [[x, y], [x, y], ...],
            "black_block" : [[x, y], [x, y], ...]
        }
    }

    {
        "type": "end",
        "result": "<win|loss>",
        "reason": <str>
    }

    {
        "type": "end",
        "result": "<win|loss>",
        "reason": <str>
    }

    """
    STATE_JOINING = 0
    STATE_WAITING = 1
    STATE_PLAYING = 2

    def on_connect(self):
        self.state = GameClient.STATE_JOINING
        self.name = ''
        self.session = None
        print 'ON CONNECT'

    def on_open(self):
        print 'ON OPEN'
        #self.send(json.dumps({'hello': 'dummy data'}), is_text=True);

    def get_type_and_parse(self, msg, is_text):
        if not is_text:
            return (None, None)

        try:
            json_dict = json.loads(msg)
        except ValueError:
            return (None, None)

        try:
            type = json_dict['type']
        except KeyError:
            return (None, None)

        return type, json_dict

    def on_message(self, msg, is_text):
        print 'RECEIVED:',msg

        if self.state == GameClient.STATE_JOINING:
            type, json_dict = self.get_type_and_parse(msg, is_text)
            if type == None:
                self.send_close(CloseCode.PROTOCOL, "invalid data")
                return

            if type != 'join':
                self.send_close(CloseCode.PROTOCOL, "invalid type")
                return
            try:
                self.name = str(json_dict['name'])
            except KeyError:
                self.send_close(CloseCode.PROTOCOL, "expected name")
                return

            print self.name, 'JOINED, WAITING:', len(self.server.waiting_clients)

            shapes = []
            for shape in Game.SHAPES:
                points = []
                for point in shape.points:
                    points.append([point.x, point.y])
                shapes.append(points)

            json_dict = {
                'type': 'joined',
                'board_width': Game.BOARD_WIDTH,
                'moves_per_turn': Game.MOVES_PER_TURN,
                'shapes': shapes
            }
            self.send(json.dumps(json_dict), is_text=True)

            if len(self.server.waiting_clients) >= 1:
                print 'PLAYING!!'
                opponent = self.server.waiting_clients.pop(0)

                session = GameSession(white=opponent, black=self)
                self.session = session
                opponent.session = session
                session.start()

                self.state = GameClient.STATE_PLAYING
                opponent.state = GameClient.STATE_PLAYING
            else:
                print 'WUT, WIATING'
                self.server.waiting_clients.append(self)
                self.state = GameClient.STATE_WAITING
        elif self.state == GameClient.STATE_WAITING:
            print 'WHAT:', msg
            self.send_close(CloseCode.PROTOCOL, "already waiting")
        elif self.state == GameClient.STATE_PLAYING:
            self.session.handle(self, msg, is_text)
        else:
            assert False

    def on_close(self, code, reason):
        try:
            self.server.waiting_clients.remove(self)
        except ValueError:
            pass

        if self.session:
            print "CLOSING SESSION:", self.session, self.session.game_over
        else:
            print "CLOSING (NO SESSION)"

        if self.session != None and not self.session.game_over:
            self.session.game_over = True
            if self.session.current_player == self:
                print 'CURRENT PLAYER SELF'
                other = self.session.next_player
            else:
                print 'CURRENT PLAYER OPPONENT'
                other = self.session.current_player

            json_dict = {'type': 'end', 'result': 'win',
                         'reason': 'opponent disconnect'}
            other.send(json.dumps(json_dict), is_text=True)
            other.send_close(CloseCode.NORMAL, reason='game over')

        del self.session

class GameSession(object):
    def __init__(self, white, black):
        assert PlayerType.WHITE == 0 and PlayerType.BLACK == 1

        self.white = white
        self.black = black
        self.game = Game()
        self.current_player = white
        self.next_player = black
        self.turn = 0
        self.game_over = False
        self.moves_remaining = Game.MOVES_PER_TURN

    def start(self):
        print 'STARTING!!!!'
        json_dict = {
            'type': 'start',
            'turn': 'white',
            'turn_number': self.turn,
            'moves_remaining': self.moves_remaining,
            'your_color': 'white',
            'opponent': self.black.name,
            'board': self.game.get_board(PlayerType.WHITE).for_json()
        }
        self.white.send(json.dumps(json_dict), is_text=True)

        json_dict = {
            'type': 'start',
            'turn': 'white',
            'turn_number': self.turn,
            'moves_remaining': self.moves_remaining,
            'your_color': 'black',
            'opponent': self.white.name,
            'board': self.game.get_board(PlayerType.BLACK).for_json()
        }
        self.black.send(json.dumps(json_dict), is_text=True)

    def send_end(self, winning_player, win_reason, lose_reason):
        print 'SENDING END'
        self.game_over = True

        if self.current_player == winning_player:
            result_current = 'win'
            reason_current = win_reason
            result_next = 'loss'
            reason_next = lose_reason
        else:
            result_next = 'win'
            reason_next = win_reason
            result_current = 'loss'
            reason_current = lose_reason

        json_dict = {'type': 'end', 'result': result_current,
                     'reason': reason_current}
        self.current_player.send(json.dumps(json_dict), is_text=True)
        self.current_player.send_close(CloseCode.NORMAL, reason='game over')

        json_dict = {'type': 'end', 'result': result_next,
                     'reason': reason_next}
        self.next_player.send(json.dumps(json_dict), is_text=True)
        self.next_player.send_close(CloseCode.NORMAL, reason='game over')

    def send_update(self, ping_saw_opponent, exclusive=None):
        player_type = self.turn % 2
        if player_type == PlayerType.WHITE:
            opponent_type = PlayerType.BLACK
            name = 'white'
        else:
            opponent_type = PlayerType.WHITE
            name = 'black'

        json_dict = {
            'type': 'update',
            'turn': name,
            'turn_number': self.turn,
            'moves_remaining': self.moves_remaining,
            'ping_saw_opponent': ping_saw_opponent
        }

        if not exclusive or exclusive == self.current_player:
            json_dict['board'] = self.game.get_board(player_type).for_json()
            self.current_player.send(json.dumps(json_dict), is_text=True)

        if not exclusive or exclusive == self.next_player:
            json_dict['board'] = self.game.get_board(opponent_type).for_json()
            self.next_player.send(json.dumps(json_dict), is_text=True)

    def handle(self, player, msg, is_text):
        if self.game_over:
            return

        if self.current_player != player:
            self.send_end(self.current_player, 'opponent disconnect',
                          'not your turn')
            return

        type, json_dict = self.current_player.get_type_and_parse(msg, is_text)
        if not type:
            self.send_end(self.next_player, 'opponent disconnect',
                          'invalid data')
            return

        directions = {
            'N': Game.DIRECTION_NORTH,
            'S': Game.DIRECTION_SOUTH,
            'E': Game.DIRECTION_EAST,
            'W': Game.DIRECTION_WEST,
        }

        player_type = self.turn % 2

        res = True
        silent_update = False
        game_over = False
        ping_saw_opponent = False
        try:
            if type == 'move':
                dir = json_dict['direction']
                res = self.game.move_player(player_type, directions[dir])
            elif type == 'place':
                shape_index = json_dict['shape_index']
                shape = Game.SHAPES[shape_index]
                x, y = json_dict['origin']
                res = self.game.place_shape(Location(x, y), shape, player_type)
            elif type == 'shoot':
                dir = json_dict['direction']
                game_over = self.game.shoot(player_type, directions[dir])
                res = True
            elif type == 'ping':
                ping_saw_opponent = self.game.ping(player_type)
                res = True
            else:
                raise ValueError("Invalid type: %s" % (type,))
        except (KeyError, ValueError) as e:
            self.send_end(self.next_player, 'opponent disconnect',
                          'invalid data')
            return

        if game_over:
            self.send_end(self.current_player, 'direct hit', 'destroyed')
            return

        if res:
            self.moves_remaining -= 1
            if self.moves_remaining == 0:
                self.turn += 1
                self.moves_remaining = Game.MOVES_PER_TURN
                temp = self.current_player
                self.current_player = self.next_player
                self.next_player = temp

            self.send_update(ping_saw_opponent)
        else:
            self.send_update(ping_saw_opponent, exclusive=self.current_player)

class GameServer(Server):
    def __init__(self, *args, **kwargs):
        super(GameServer, self).__init__(*args, **kwargs)
        self.waiting_clients = []
        self.game_sessions = []

if __name__ == "__main__":
    server = GameServer(port=int(sys.argv[1]), connection_class=GameClient,
#                        heartbeat_interval_ms=30000, heartbeat_ttl_ms=5000,
                       )
    server.listen()

