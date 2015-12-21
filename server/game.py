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

from collections import namedtuple
import copy
import math

try:
    import ujson as json
except:
    import json

class Location(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Location(self.x + other.x, self.y + other.y)

    def __str__(self):
        return "(%d, %d)" % (self.x, self.y)

    def __repr__(self):
        return "Location(%d, %d)" % (self.x, self.y)

    def __eq__(self, other):
        return (self.x == other.x and self.y == other.y)

    def __ne__(self, other):
        return not (self == other)

# Alias for Location
Offset = Location

ShapeOffset = namedtuple('ShapeOffset', ['x', 'y', 'corner'])
Shape = namedtuple('Shape', ['points'])
Player = namedtuple('Player', ['board', 'invis_tiles', 'block_tile',
                               'player_tile',
                               'player_type'])

class PlayerType(object):
    WHITE = 0
    BLACK = 1

#
# XXXX
#
LONG_SHAPE_0 = Shape(
    points = [
        Offset(0, 0),
        Offset(1, 0),
        Offset(2, 0),
        Offset(3, 0)
    ]
)

#
#  X
#  X
#  X
#  X
#
LONG_SHAPE_1 = Shape(
    points = [
        Offset(0, 0),
        Offset(0, 1),
        Offset(0, 2),
        Offset(0, 3)
    ]
)

#
# XX
# XX
#
BOX_SHAPE = Shape(
    points = [
        Offset(0, 0),
        Offset(0, 1),
        Offset(1, 1),
        Offset(1, 0)
    ]
)

SHAPES_STR =\
"""
      (1)
       1   (2)
(0)    X   2X
0XXX   X   XX
       X
"""[1:]

class Board(object):
    TILE_CLEAR              = 0
    TILE_BLOCK_BLACK        = 1
    TILE_BLOCK_WHITE        = 2
    TILE_PLAYER_BLACK       = 3
    TILE_PLAYER_WHITE       = 4
    TILE_PLAYER_BOTH        = 5

    def __init__(self):
        self._tiles =\
                [[Board.TILE_CLEAR] * Game.BOARD_WIDTH for i in range(Game.BOARD_WIDTH)]
        middle = Game.BOARD_WIDTH / 2
        self._black_loc = Location(middle, 0)
        self._white_loc = Location(middle, Game.BOARD_WIDTH - 1)
        self.set_tile(self._white_loc, Board.TILE_PLAYER_WHITE)
        self.set_tile(self._black_loc, Board.TILE_PLAYER_BLACK)

    def valid(self, loc):
        return (loc.x >= 0 and loc.x < Game.BOARD_WIDTH and
                loc.y >= 0 and loc.y < Game.BOARD_WIDTH)

    def get_player_loc(self, player_type):
        if player_type == PlayerType.WHITE:
            return self._white_loc
        else:
            return self._black_loc

    def set_player_loc(self, player_type, new_loc, old_loc_value):
        if player_type == PlayerType.WHITE:
            tile = self.get_tile(self._white_loc)

            self.set_tile(self._white_loc, old_loc_value)
            if new_loc == self._black_loc:
                self.set_tile(new_loc, Board.TILE_PLAYER_BOTH)
            else:
                self.set_tile(new_loc, Board.TILE_PLAYER_WHITE)
            self._white_loc = new_loc
        elif player_type == PlayerType.BLACK:
            tile = self.get_tile(self._black_loc)

            self.set_tile(self._black_loc, old_loc_value)
            if new_loc == self._white_loc:
                self.set_tile(new_loc, Board.TILE_PLAYER_BOTH)
            else:
                self.set_tile(new_loc, Board.TILE_PLAYER_BLACK)
            self._black_loc = new_loc

    def set_tile(self, loc, value):
        self._tiles[loc.x][loc.y] = value

    def get_tile(self, loc):
        return self._tiles[loc.x][loc.y]

    def is_block(self, loc):
        return (self._tiles[loc.x][loc.y] == Board.TILE_BLOCK_BLACK or
                self._tiles[loc.x][loc.y] == Board.TILE_BLOCK_WHITE)

    def is_player(self, loc):
        return (self._tiles[loc.x][loc.y] == Board.TILE_PLAYER_BLACK or
                self._tiles[loc.x][loc.y] == Board.TILE_PLAYER_WHITE or
                self._tiles[loc.x][loc.y] == Board.TILE_PLAYER_BOTH)

    def for_json(self):
        json_dict = {
            'black_block': [],
            'white_block': []
        }
        for x in xrange(Game.BOARD_WIDTH):
            for y in xrange(Game.BOARD_WIDTH):
                tile = self._tiles[x][y]
                if tile == Board.TILE_CLEAR:
                    continue
                elif tile == Board.TILE_BLOCK_BLACK:
                    json_dict.setdefault('black_block', []).append([x, y])
                elif tile == Board.TILE_BLOCK_WHITE:
                    json_dict.setdefault('white_block', []).append([x, y])
                elif tile == Board.TILE_PLAYER_BLACK:
                    json_dict['black_player'] = [x, y]
                elif tile == Board.TILE_PLAYER_WHITE:
                    json_dict['white_player'] = [x, y]
                else:
                    assert tile == Board.TILE_PLAYER_BOTH
                    json_dict['black_player'] = [x, y]
                    json_dict['white_player'] = [x, y]

        return json_dict

    def __repr__(self):
        extra_spaces = int(math.log(Game.BOARD_WIDTH, 10)) + 1
        r = ' ' * (extra_spaces + 1)
        col = 'A'
        row = 1
        for i in xrange(Game.BOARD_WIDTH):
            r += col + ' '
            col = chr(ord(col) + 1)

        r += '\n'
        for y in xrange(Game.BOARD_WIDTH):
            r += '%*.d ' % (extra_spaces, row)
            row += 1
            for x in xrange(Game.BOARD_WIDTH):
                c = ''
                tile = self._tiles[x][y]
                if tile == Board.TILE_CLEAR:
                    c = '.'
                elif tile == Board.TILE_BLOCK_BLACK:
                    c = 'b'
                elif tile == Board.TILE_BLOCK_WHITE:
                    c = 'B'
                elif tile == Board.TILE_PLAYER_BLACK:
                    c = 'p'
                elif tile == Board.TILE_PLAYER_WHITE:
                    c = 'P'
                else:
                    c = 'Q'
                r += c + ' '
            r += '\n'
        return r

    def __str__(self):
        return repr(self)


class Game(object):
    BOARD_WIDTH = 13
    SHOOT_RADIUS = 3
    MOVES_PER_TURN = 2

    DIRECTION_NORTH = 0
    DIRECTION_SOUTH = 1
    DIRECTION_EAST  = 2
    DIRECTION_WEST  = 3

    DIRECTION_OFFSETS = {
        DIRECTION_NORTH: Offset(0, -1),
        DIRECTION_SOUTH: Offset(0, 1),
        DIRECTION_EAST: Offset(1, 0),
        DIRECTION_WEST: Offset(-1, 0)
    }

    SHAPES = [LONG_SHAPE_0, LONG_SHAPE_1, BOX_SHAPE]

    def __init__(self):
        # master board
        self._board = Board()

        # players, with their own view of the world
        self._players = [
            Player(
                board=Board(),
                invis_tiles=set(),
                block_tile=Board.TILE_BLOCK_WHITE,
                player_tile=Board.TILE_PLAYER_WHITE,
                player_type=PlayerType.WHITE
            ),
            Player(
                board=Board(),
                invis_tiles=set(),
                block_tile=Board.TILE_BLOCK_BLACK,
                player_tile=Board.TILE_PLAYER_BLACK,
                player_type=PlayerType.BLACK
            )
        ]

        self._turn = 0

        last = Game.BOARD_WIDTH - 1
        self._corners = [Location(0, 0), Location(last, 0),
                         Location(last, last), Location(0, last)]

    def _get_player(self, player_type):
        return self._players[player_type]

    def _get_opponent(self, player_type):
        return self._players[not player_type]

    def is_opaque(self, x, y):
        loc = Location(x, y)
        #res = True
        #if not self._board.is_block(loc) and not self._board.is_player(loc):
        #    res = False
        #    self._board.set_tile(loc, Board.TILE_PLAYER_BOTH)
        return not self._board.valid(loc) or\
               self._board.is_block(loc) or\
               self._board.is_player(loc)
        #return res

    def cast_line(self, point0, point1, path=None):
        def octant0(origin, offset, x_dir, y_dir):
            #print "OCTANT 0 (%d, %d) offset (%d, %d)" % (origin.x, origin.y, offset.x, offset.y)
            delta_y = offset.y
            delta_x = offset.x
            cur_x = origin.x
            cur_y = origin.y

            delta_y_x2 = delta_y * 2
            delta_y_x2_minus_delta_x_x2 = delta_y_x2 - (delta_x * 2)
            error_term = delta_y_x2 - delta_x

            if path != None:
                path.append(Location(cur_x, cur_y))

            tile = self._board.get_tile(origin)
            if tile == Board.TILE_PLAYER_BOTH:
                return origin

            while delta_x > 0:
                delta_x -= 1

                if error_term >= 0:
                    cur_y += y_dir
                    error_term += delta_y_x2_minus_delta_x_x2
                else:
                    error_term += delta_y_x2
                cur_x += x_dir

                if path != None:
                    path.append(Location(cur_x, cur_y))

                if self.is_opaque(cur_x, cur_y):
                    return Location(cur_x, cur_y)

            return Location(cur_x, cur_y)

        def octant1(origin, offset, x_dir, y_dir):
            #print "OCTANT 1 (%d, %d) offset (%d, %d)" % (origin.x, origin.y, offset.x, offset.y)
            delta_y = offset.y
            delta_x = offset.x
            cur_x = origin.x
            cur_y = origin.y

            delta_x_x2 = delta_x * 2
            delta_x_x2_minus_delta_y_x2 = delta_x_x2 - (delta_y * 2)
            error_term = delta_x_x2 - delta_y

            if path != None:
                path.append(Location(cur_x, cur_y))

            tile = self._board.get_tile(origin)
            if tile == Board.TILE_PLAYER_BOTH:
                return origin

            while delta_y > 0:
                delta_y -= 1
                if error_term >= 0:
                    cur_x += x_dir
                    error_term += delta_x_x2_minus_delta_y_x2
                else:
                    error_term += delta_x_x2
                cur_y += y_dir

                if path != None:
                    path.append(Location(cur_x, cur_y))

                if self.is_opaque(cur_x, cur_y):
                    return Location(cur_x, cur_y)

            return Location(cur_x, cur_y)

        #print "CAST:", point0, point1
        x0 = point0.x
        y0 = point0.y
        x1 = point1.x
        y1 = point1.y

        delta_x = x1 - x0
        delta_y = y1 - y0

        x_dir = 1
        if delta_x < 0:
            x_dir = -1
            delta_x = abs(delta_x)

        y_dir = 1
        if delta_y < 0:
            y_dir = -1
            delta_y = abs(delta_y)

        if delta_x > delta_y:
            return octant0(Location(x0, y0), Offset(delta_x, delta_y),
                           x_dir, y_dir)
        else:
            return octant1(Location(x0, y0), Offset(delta_x, delta_y),
                           x_dir, y_dir)

    def ping(self, player_type):
        player_loc = self._board.get_player_loc(player_type)
        player = self._get_player(player_type)
        opponent = self._get_opponent(player_type)
        opponent_type = opponent.player_type
        opponent_loc = self._board.get_player_loc(opponent_type)

        saw_opponent = False
        endpoint = self.cast_line(opponent_loc, player_loc)
        if endpoint == player_loc:
            saw_opponent = True
            #print "REVEALING", opponent_loc, "TO", player_type
            last_seen_loc = player.board.get_player_loc(opponent_type)
            player.board.set_player_loc(opponent_type, opponent_loc, Board.TILE_CLEAR)

            # if player sees opponent, opponent also sees player
            #print "REVEALING", player_loc, "TO", opponent_type
            opponent_last_seen_loc = opponent.board.get_player_loc(player_type)
            opponent.board.set_player_loc(player_type, player_loc, Board.TILE_CLEAR)
        else:
            #player.board.set_player_ghost(opponent_type)
            opponent_loc = player.board.get_player_loc(opponent_type)
            player.board.set_tile(opponent_loc, Board.TILE_CLEAR)

        #print "INVIS:", player.invis_tiles
        for loc in copy.copy(player.invis_tiles):
            endpoint = self.cast_line(loc, player_loc)
            if endpoint == player_loc:
                player.board.set_tile(loc, self._board.get_tile(loc))
                player.invis_tiles.remove(loc)

        return saw_opponent

    def place_shape(self, origin, shape, player_type):
        player = self._get_player(player_type)
        opponent = self._get_opponent(player_type)

        tile_placed = False
        for offset in shape.points:
            loc = origin + offset
            if self._board.valid(loc):
                tile_placed = True
                tile = self._board.get_tile(loc)
                see_tile = player.board.get_tile(loc)
                if tile == player.player_tile:
                    assert player_tile == tile
                    continue
                elif tile == opponent.player_tile:
                    if see_tile == tile:
                        continue
                    else:
                        # Fake tile!
                        player.board.set_tile(loc, player.block_tile)
                        player.invis_tiles.add(loc)
                else:
                    self._board.set_tile(loc, player.block_tile)
                    player.board.set_tile(loc, player.block_tile)
                    opponent.invis_tiles.add(loc)

        return tile_placed


    def move_player(self, player_type, direction):
        dir = Game.DIRECTION_OFFSETS[direction]
        player = self._get_player(player_type)
        opponent = self._get_opponent(player_type)
        cur_loc = self._board.get_player_loc(player_type)
        new_loc = cur_loc + dir

        #print player_type, "FROM:", cur_loc, "TO:", new_loc
        if self._board.valid(new_loc):
            old_value = self._board.get_tile(cur_loc)
            player_old_value = player.board.get_tile(cur_loc)

            if old_value == Board.TILE_PLAYER_BOTH:
                old_value = opponent.player_tile
            else:
                old_value = Board.TILE_CLEAR

            if player_old_value == Board.TILE_PLAYER_BOTH:
                player_old_value = opponent.player_tile
            else:
                player_old_value = Board.TILE_CLEAR

            value = self._board.get_tile(new_loc)
            player_value = player.board.get_tile(new_loc)

            #if player_value == player.fake_tile:
            #    player.board.set_tile(new_loc, self._board.get_tile(new_loc))
            #    return False
            if player.board.is_block(new_loc) and\
               not self._board.is_block(new_loc):
                player.board.set_tile(new_loc, self._board.get_tile(new_loc))
                return False
            elif value == opponent.block_tile:
                player.board.set_tile(new_loc, opponent.block_tile)
                return False
            elif value == player.block_tile:
                return False
            else:
                self._board.set_player_loc(player_type, new_loc, old_value)
                player.board.set_player_loc(player_type, new_loc,
                                            player_old_value)
                return True
        else:
            return False

    def shoot(self, player_type, direction):
        dir = Game.DIRECTION_OFFSETS[direction]
        dir = Offset(dir.x * Game.SHOOT_RADIUS, dir.y * Game.SHOOT_RADIUS)
        player = self._get_player(player_type)
        opponent = self._get_opponent(player_type)
        player_loc = self._board.get_player_loc(player_type)

        path = []
        #print 'SHOOTING FROM', player_loc, 'TO', player_loc + dir
        endpoint = self.cast_line(player_loc, player_loc + dir, path=path)

        # clear out any fake tiles we passed through
        for loc in path:
            if not self._board.valid(loc):
                continue

            if player.board.is_block(loc) and not self._board.is_block(loc):
                player.board.set_tile(loc, self._board.get_tile(loc))
                player.invis_tiles.remove(loc)

        # see if we hit anything interesting
        if not self._board.valid(endpoint):
            return False
        if self._board.is_player(endpoint):
            return True
        elif self._board.is_block(endpoint):
            self._board.set_tile(loc, Board.TILE_CLEAR)
            player.board.set_tile(loc, Board.TILE_CLEAR)
            opponent.invis_tiles.add(loc)
            return False
        else:
            return False

    def get_board(self, player_type):
        player = self._get_player(player_type)
        return player.board

    def __str__(self):
        s = "BOARD:\n"
        s += repr(self._board)
        s += "\nWHITE BOARD:\n"
        s += repr(self._players[PlayerType.WHITE].board)
        s += "\nBLACK BOARD:\n"
        s += repr(self._players[PlayerType.BLACK].board)
        return s

if __name__ == '__main__':
    import sys
    from optparse import OptionParser
    usage = 'usage: masterserver.py [options]'
    parser = OptionParser(usage)
    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="enable debug mode")
    (options, args) = parser.parse_args()

    game = Game()
    mid = Game.BOARD_WIDTH / 2

    i = 0
    while True:
        cur_player = i % 2

        if options.debug:
            print game
        else:
            board = game.get_board(cur_player)
            print board

        if cur_player == PlayerType.WHITE:
            player_name = 'White'
        else:
            player_name = 'Black'

        print SHAPES_STR

        print "[!]N S E W | p | s,x,y (%s):" % (player_name,),
        answer = raw_input()

        dir = None
        res = True

        shoot = False
        if len(answer) == 2:
            if answer[0] == '!':
                shoot = True
                answer = answer[1:]
            else:
                continue
        if len(answer) == 0:
            continue
        elif answer[0] == 'N':
            dir = Game.DIRECTION_NORTH
        elif answer[0] == 'S':
            dir = Game.DIRECTION_SOUTH
        elif answer[0] == 'E':
            dir = Game.DIRECTION_EAST
        elif answer[0] == 'W':
            dir = Game.DIRECTION_WEST
        elif answer[0] == 'p':
            game.ping(cur_player)
        elif len(answer) > 1:
            stuff = answer.split(',')
            if len(stuff) != 3:
                continue

            stuff = [s.strip() for s in stuff]

            if len(stuff[2]) == 1 and ord(stuff[2]) >= ord('A') and\
               ord(stuff[2]) <= ord('Z'):
                temp = stuff[1]
                stuff[1] = stuff[2]
                stuff[2] = temp

            def convert(s):
                try:
                    return int(s)
                except ValueError:
                    return -1
            shape = convert(stuff[0])
            try:
                x = ord(stuff[1]) - ord('A')
            except ValueError,TypeError:
                continue
            y = convert(stuff[2]) - 1

            if shape < 0 or x < 0 or y < 0 or shape >= len(game.SHAPES):
                continue

            res = game.place_shape(
                Location(x, y),
                game.SHAPES[shape],
                cur_player
            )
        else:
            continue

        if dir != None:
            if shoot:
                game_over = game.shoot(cur_player, dir)
                if game_over:
                    print "GAME OVER!!! %s WINS!!" % (player_name,)
                    break
                else:
                    res = True
            else:
                res = game.move_player(cur_player, dir)

        if not options.debug:
            if res:
                print
                print "RESULT:"
                print board
                print "Press enter and pass to opponent"
                raw_input()
                print '\n' * 80
                print "Press enter to begin turn"
                raw_input()
            else:
                continue

        if res:
            i += 1

