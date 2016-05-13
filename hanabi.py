import sys
import os
import random
import cmd
import cPickle as pickle
import itertools
from collections import defaultdict
from copy import deepcopy
from itertools import chain

VALUES = range(1, 6)
COLOURS = ("Blue", "Green", "Rainbow", "Red", "Yellow", "White")
COLOURS_SHORT = dict(zip(COLOURS, ["B", "G", "A", "R", "Y", "W"]))
# The number of each face value, in value order (pad a 0 so that it is
# indexable by value)
VALUES_COUNT = (0, 3, 2, 2, 2, 1)
# The number of cards dealt depending on the number of players
HAND_COUNT = {2: 5, 3: 5, 4: 4, 5: 4}
INITIAL_LIVES = 3
INITIAL_CLUES = 8
# cards need IDs so that they can be identified by players for playing a move.
# card = (colour, value, id)
# hand = [card, ...]
# player = {"id": hand}
# deck = [card, ...]
# played = [card, ...]
# discarded = [card, ...]
# game = {"players": , "deck": , "played": , "discarded": , "lives": , "clues": }
# move = {"type": "clue" | "discard" | "play", "data": }
MOVE_TYPES = ["clue", "discard", "play"]
# clue data = (player id, clue_data, [card IDs])
# clue_data = e.g. "blue" or "4"
# The card IDs above are added by the game engine, not the user
# discard data | play data = card_id

SEED_FILENAME = "hanabi_seed.dat"

MAX_SCORE = len(VALUES) * len(COLOURS)


def pct(a, b):
    return (float(a)/b) * 100

def mmm(l, n):
    """Return the min, mean, and max from the values in `l' based on a
    population size of `n'."""
    return (min(l), float(sum(l))/n, max(l))

def create_new_deck():
    """Returns all cards shuffled"""
    cards = [(c, v) for c in COLOURS for v in VALUES for i in xrange(VALUES_COUNT[v])]
    random.shuffle(cards)
    cards = [(c[0], c[1], id) for id, c in enumerate(cards)]
    return cards

def create_new_game(num_players):
    assert(num_players in HAND_COUNT.keys())
    deck = create_new_deck()
    players = defaultdict(list)
    # Deal out the cards - doesn't seem an nicer way than this to
    # remove the first n elements
    hc = HAND_COUNT[num_players]
    for i in xrange(num_players):
        players[i].extend(deck[0:hc])
        del deck[0:hc]

    return {"players": players,
            "current_player": None,
            "deck": deck,
            "deck_len": len(deck),
            "played": [],
            "discarded": [],
            "lives": INITIAL_LIVES,
            "clues": INITIAL_CLUES,
            "moves": []}

def card_str(c, print_card_id = False):
    if print_card_id:
        return "%s%d (%d)" % (COLOURS_SHORT[c[0]], c[1], c[2])
    else:
        return "%s%d" % (COLOURS_SHORT[c[0]], c[1])

def hand_str(h, print_card_id = False):
    return ", ".join([card_str(c, print_card_id) for c in h])

def sort_by_colour(d, reverse = False):
    d1 = defaultdict(list)
    d2 = {}
    for card in d:
        d1[card[0]].append(card[1])
    for colour, cards in d1.iteritems():
        d2[colour] = sorted(cards, reverse = reverse)
    return d2

def playable_value(game, colour):
    """Return the value that is playable for the `colour' or None if the
    `colour' is complete."""
    played_sorted = sort_by_colour(game["played"], True)
    # First value if no cards of the colour have been played
    if not colour in played_sorted:
        return VALUES[0]
    played_colours = played_sorted[colour]
    # Check if that colour is complete
    if played_colours[0] >= VALUES[-1]:
        return None
    # Otherwise return the next value
    return played_colours[0] + 1

def playable(game, card):
    return (card[1] == playable_value(game, card[0]))

def discardable(game, card):
    # First look at whether the card has already been played
    if hand_has(game["played"], card):
        return True
    
    # Then see if a colour is dead by looking to see if all cards
    # of the value that is playable have been discarded
    the_playable_value = playable_value(game, card[0])

    # Don't need to pass ID
    return (hand_has(game["discarded"], (card[0], the_playable_value)) >= VALUES_COUNT[the_playable_value])

def hand_has(hand, other_card):
    """Return the number of times `other_card' is in the `hand'."""
    return sum([((card[0] == other_card[0]) and (card[1] == other_card[1])) for card in hand])

def hand_has_colour(hand, colour):
    """Return the number of times `colour' is in the `hand'."""
    return sum([(card[0] == colour) for card in hand])

def hand_has_value(hand, value):
    """Return the number of times `value' is in the `hand'."""
    return sum([(card[1] == value) for card in hand])

def colours_in_hand(hand):
    return list(set([card[0] for card in hand]))

def values_in_hand(hand):
    return list(set([card[1] for card in hand]))

def get_card_ids_for_colour(hand, colour):
    return [card[2] for card in hand if card[0] == colour]

def get_card_ids_for_value(hand, value):
    return [card[2] for card in hand if card[1] == value]

# Work out whether it is a colour or value, no error checking done
# here
def get_card_ids(hand, colour_or_value):
    if isinstance(colour_or_value, str):
        return get_card_ids_for_colour(hand, colour_or_value)
    else:
        return get_card_ids_for_value(hand, colour_or_value)
    
def get_player_order(game, current_player):
    """Return a list of player IDs in the order of play from the
    `current_player'."""
    # Always play from player 0 in ascending order
    pids = sorted(game["players"].keys())
    length = len(pids)
    # We use the modulo of length + 1 so that when the current_player
    # is the last in the list, the first expression returns an empty
    # list
    return pids[(current_player + 1)%(length + 1):length] + pids[0:current_player]

def cards_given_clue(game, player):
    """Return the card IDs for which the `player' was given clues about."""
    clues = [m for from_player, m in game["moves"] if m["type"] == "clue"]
    # Flatten
    return list(chain.from_iterable([clue["data"][2] for clue in clues if clue["data"][0] == player]))

def score(game):
    return len(game["played"])

def have_won(game):
    return (score(game) == MAX_SCORE)

def have_lost(game):
    return (g["lives"] <= 0)

def print_moves(moves):
    if len(moves):
        print "<move number>: <from player ID> -> <move>"
    for i, m in enumerate(moves):
        print "%0d: P%0d -> %s" % (i, m[0], m[1])

def print_game(g, current_player, print_card_id):
    """Print out each players hand, hiding the current player's hand
    unless `current_player' is -1. Then print out the cards played,
    the cards discarded, and some stats about the game state.
    """
    for pid, hand in g["players"].iteritems():
        # Obviously, don't show the hand of the current player, which
        # will be card IDs anyway
        if pid == current_player:
            # Unless it already has been obfuscated (i.e. called from
            # within a user's function
            if isinstance(hand[0], int):
                print "P%d: %s" % (pid, ", ".join(["%d" % id for id in hand]))
            else:
                print "P%d: %s" % (pid, ", ".join(["%d" % card[2] for card in hand]))
        else:
            # Unless it already has been obfuscated (i.e. called from
            # within a user's function
            if isinstance(hand[0], int):
                print "P%d: %s" % (pid, ", ".join(["%d" % id for id in hand]))
            else:
                print "P%d: %s" % (pid, hand_str(hand, print_card_id))

    print

    # Print the highest values in each suit
    print "Played:"
    played_sorted = sort_by_colour(g["played"], True)
    for c in COLOURS:
        if c in played_sorted and len(played_sorted[c]):
            print "%s: %s" % (COLOURS_SHORT[c], played_sorted[c][0])
        else:
            print "%s: ." % COLOURS_SHORT[c]
    
    print
    print "Discarded:"
    discarded_sorted = sort_by_colour(g["discarded"])
    for c in COLOURS:
        if c in discarded_sorted and len(discarded_sorted[c]):
            print "%s: %s" % (COLOURS_SHORT[c], ", ".join(["%d" % v for v in discarded_sorted[c]]))
        else:
            print "%s: ." % COLOURS_SHORT[c]
    
    print
    print "Deck: %d remaining" % (g["deck_len"])
    print "Lives: %d" % g["lives"]
    print "Clues: %d" % g["clues"]

def game_finished(game, current_player, final_player):
    return (game["lives"] <= 0) or \
        ((game["deck_len"] <= 0) and (current_player == final_player))

def valid_move(g, p, m):
    if not isinstance(m, dict):
        return (False, "move is not a dict")
    if not "type" in m or not "data" in m:
        return (False, "move dict does not have a 'type' or 'data' key")
    if not m["type"] in MOVE_TYPES:
        return (False, "move type is invalid")
    d = m["data"]
    if m["type"] is "clue":
        if g["clues"] <= 0:
            return (False, "no clues remaining")
        if not isinstance(d, tuple) or not len(d) == 2:
            return (False, "clue data is not a tuple of length 2")
        if not d[0] in g["players"]:
            return (False, "clue is not directed at a valid player ID")
        if not isinstance(d[1], str) and not isinstance(d[1], int):
            return (False, "clue data is not a string or int")
        if isinstance(d[1], str) and not d[1] in COLOURS:
            return (False, "clue data is not a valid colour")
        if isinstance(d[1], int) and not d[1] in VALUES:
            return (False, "clue data is not a valid value")
        # Don't allow misleading clues
        if isinstance(d[1], str):
            if not hand_has_colour(g["players"][d[0]], d[1]):
                return (False, "other players hand does not have the colour given in the clue")
        if isinstance(d[1], int):
            if not hand_has_value(g["players"][d[0]], d[1]):
                return (False, "other players hand does not have the value given in the clue")
    else:
        if not isinstance(d, int):
            return (False, "discard or play move data is not an int")
        if not d in [c[2] for c in g["players"][p]]:
            return (False, "discard or play move data card ID is not in the player's hand")
    return (True, "")

def check_play_move_funcs(num_players, play_move_func):
    play_move_per_player = {}
    player_ids = range(num_players)

    # Using callable means it can be a function or class method
    if isinstance(play_move_func, dict):
        for pid, func in play_move_func.iteritems():
            if isinstance(pid, int):
                sys.exit("Error: If `play_move_func' is a dictionary then it's keys must be integers.")
            if not pid in player_ids:
                sys.exit("Error: If `play_move_func' is a dictionary then it's keys must be valid player IDs.")
            if not callable(func):
                sys.exit("Error: Function for player %d is not callable" % pid)
            play_move_per_player[pid] = func
    elif callable(play_move_func):
        for pid in player_ids:
            play_move_per_player[pid] = play_move_func
    else:
        sys.exit("Error: `play_move_func' must be a dictionary or a function.")

    return play_move_per_player

def play_one_turn(g, current_player, play_move, play_move_func_args, memory, obfuscate_game):
    # Use deep copy because of nested data structures
    new_g = deepcopy(g)
    current_players_hand = g["players"][current_player]
    if obfuscate_game:
        # Replace the current player's hand from the game state given
        # to her with just the card IDs
        new_g["players"][current_player] = [c[2] for c in current_players_hand]
        # And don't let the player see the deck!
        new_g["deck"] = []
        
    move = play_move(new_g,
                     current_player,
                     memory,
                     play_move_func_args)

    (is_valid_move, error_str) = valid_move(g, current_player, move)
    if not is_valid_move:
        print "Error %s was not a valid move by player %d because '%s'." % (move, current_player, error_str)
        print "Game state:"
        print_game(g, -1, True)
        print "Moves:"
        print_moves(g["moves"])
        sys.exit()

    if move["type"] is "clue":
        g["clues"] -= 1
        # Add the card IDs for the clue - the user doesn't have to do this
        to_player = move["data"][0]
        clue_type = move["data"][1]
        move["data"] = (to_player, clue_type, get_card_ids(g["players"][to_player], clue_type))
    elif move["type"] is "discard":
        card = [(i, c) for i, c in enumerate(current_players_hand) if c[2] == move["data"]]
        assert(len(card) == 1)
        current_players_hand.pop(card[0][0])
        card = card[0][1]
        g["discarded"].append(card)
        # Only pick up if there are cards remaining
        if g["deck_len"] > 0:
            current_players_hand.append(g["deck"].pop())
            g["clues"] += 1
    else:
        # Played
        card = [(i, c) for i, c in enumerate(current_players_hand) if c[2] == move["data"]]
        assert(len(card) == 1)
        current_players_hand.pop(card[0][0])
        card = card[0][1]
        if playable(g, card):
            g["played"].append(card)
            # Extra clue on completing a colour set
            if card[1] == 5:
                g["clues"] += 1
        else:
            g["lives"] -= 1
            g["discarded"].append(card)
            # Only pick up if there are cards remaining
        if g["deck_len"] > 0:
            current_players_hand.append(g["deck"].pop())

    g["moves"].append((current_player, move))
    g["deck_len"] = len(g["deck"])
    
    return g

def play_one_game(num_players, play_move_per_player, play_move_func_args, obfuscate_game = True):
    g = create_new_game(num_players)

    # Initial set up
    # Always play from player 0 in ascending order
    player_order = itertools.cycle(sorted(g["players"].keys()))
    # Doesn't matter if the same player always goes first
    previous_player, current_player = None, next(player_order)
    g["current_player"] = current_player
    final_player = None
    final_round = False
    # Each memory needs to be something so that a reference is passed
    # in to an empty dict. If it is left as None then updates within
    # the player's play_move function can't update a None reference,
    # so there will be no memory
    memory = dict([(pid, {}) for pid in g["players"].keys()])

    # Main loop
    while not game_finished(g, current_player, final_player):
        # Assign the final player here so she gets a final move
        if g["deck_len"] <= 0 and not final_round:
            final_player = previous_player
            final_round = True

        g = play_one_turn(g,
                          current_player,
                          play_move_per_player[current_player],
                          play_move_func_args,
                          memory[current_player],
                          obfuscate_game)
        
        previous_player, current_player = current_player, next(player_order)
        g["current_player"] = current_player

    return g

def play(num_games, num_players, play_move_func, play_move_func_args = {}, load_state = False, obfuscate_game = True):
    """Call this when you are ready to play, it is the main
    loop. `play_move_func' is either one function that gets called for
    every player, or a dictionary mapping the player ID (starting from
    0) to a play move function for that player. `play_move_func_args'
    is a dictionary of arguments for each function, they can be
    whatever you like, and are passed as `user_args' below. This can
    be used to test various options within your algorithm without
    having to edit the code.

    `load_state' allows you to re-run with the same seed as that
    written out to the file hanabi_seed.dat.

    The `play_move_func' has the following definition:

       def play_move(game, current_player, memory, user_args)
    
    Using the information given, return a valid move. Program will
    exit if not valid.

    You can't declare global variables in order to exchange
    information between players. You can use the `memory' dictionary
    which the user can put in what they want. This is only given to
    the same player.

    `obfuscate_game' means that the player will receive the same level
    of knowledge as they would in a real game, i.e. they won't see
    their own cards nor will they see the deck. Set this to False when
    you need to full state for simulating games, but don't cheat!
    """
    # Check if this is a re-run first
    if load_state:
        if os.path.exists(SEED_FILENAME):
            with open(SEED_FILENAME, "rb") as fh:
                state = pickle.load(fh)
            random.setstate(state)
        else:
            sys.exit("Error: load_state set to True, but file '%s' for reading random state not found." % SEED_FILENAME)
    else:
        with open(SEED_FILENAME, "wb") as fh:
            pickle.dump(random.getstate(), fh)
    
    # First, work out what function each player uses
    play_move_per_player = check_play_move_funcs(num_players, play_move_func)

    stats = []
    for i in xrange(num_games):
        g = play_one_game(num_players, play_move_per_player, play_move_func_args, obfuscate_game)
        stats.append((g["lives"] > 0, score(g), len(g["moves"]), g["clues"], g["lives"]))

    # Lost games are those where are lives are lost
    #
    # Finished games are those where you finish the deck without
    # losing all lives, but don't attain the full score
    #
    # Won games are those the full score has been attained
    won_games = [s for s in stats if s[0] and s[1] == MAX_SCORE]
    finished_games = [s for s in stats if s[0] and s[1] != MAX_SCORE]
    lost_games = [s for s in stats if not s[0]]
    finished_scores = [s[1] for s in finished_games]
    lost_scores = [s[1] for s in lost_games]
    won = len(won_games)
    finished = len(finished_games)
    lost = num_games - won - finished
    print "For %d game%s with %d players, stats:" % (num_games, ("s" if num_games > 1 else ""), num_players)
    print "\tWon: %d (%.2f%%)" % (won, pct(won, num_games))
    print "\tFinished: %d (%.2f%%)" % (finished, pct(finished, num_games))
    print "\tLost: %d (%.2f%%)" % (lost, pct(lost, num_games))
    if len(won_games):
        won_lives = [s[4] for s in won_games]
        won_clues = [s[3] for s in won_games]
        won_moves = [s[2] for s in won_games]
        print "\tFor won games, "
        print "  lives left: %.2f/%.2f/%.2f (min/mean/max)" % mmm(won_lives, num_games)
        print "  clues used: %.2f/%.2f/%.2f (min/mean/max)" % mmm(won_clues, num_games)
        print "  moves used: %.2f/%.2f/%.2f (min/mean/max)" % mmm(won_moves, num_games)
    if len(finished_scores):
        print "\tFor finished games, scores: %.2f/%.2f/%.2f (min/mean/max)" % mmm(finished_scores, num_games)
        #TODO: Add how many games completed and with how many lives and clues used
    if len(lost_scores):
        print "\tFor lost games, scores: %.2f/%.2f/%.2f (min/mean/max)" % mmm(lost_scores, num_games)

################################################################################        
# Some standard moves to test with
#
# play_move_manual - allows you to play all players by inputting
#                    commands at the terminal
# play_move_random - plays a random valid move. Your method should be
#                    better than this!
################################################################################        
class MoveInterpreter(cmd.Cmd):
    def __init__(self, game, current_player, memory):
        #super(MoveInterpreter, self).__init__()
        cmd.Cmd.__init__(self)
        self.prompt = "[P%d]> " % current_player
        self.game = game
        self.current_player = current_player
        self.memory = memory
        self.move = None

    def do_print(self, line):
        arg = line.strip()
        if arg == "game":
            print_game(self.game, self.current_player)
        elif arg == "hand":
            print "P%d: %s" % (self.current_player,
                               ", ".join(["%d" % cid for cid in self.game["players"][self.current_player]]))
        elif arg == "moves":
            print_moves(self.game["moves"])
        elif arg == "memory":
            print self.memory
        elif arg == "myclues":
            if len(self.game["moves"]):
                print "<move number>: <from player ID> -> <move>"
            for i, m in enumerate(self.game["moves"]):
                if m[1]["type"] == "clue" and m[1]["data"][0] == self.current_player:
                    print "%0d: P%0d -> %s" % (i, m[0], m[1])
        elif arg == "otherclues":
            if len(self.game["moves"]):
                print "<move number>: <from player ID> -> <move>"
            for i, m in enumerate(self.game["moves"]):
                if m[1]["type"] == "clue" and m[1]["data"][0] != self.current_player:
                    print "%0d: P%0d -> %s" % (i, m[0], m[1])
        else:
            print "*** unknown argument."

    def do_discard(self, card_id_s):
        try:
            card_id = int(card_id_s)
        except ValueError:
            print "*** card ID must be an int."
            return
        if not card_id in self.game["players"][self.current_player]:
            print "*** card ID of '%d' not in hand, please input a valid ID." % card_id
            return
        self.move = {"type": "discard", "data": card_id}
        # Returning True quits the interpreter and processes the above move
        return True
    
    def do_play(self, card_id_s):
        try:
            card_id = int(card_id_s)
        except ValueError:
            print "*** card ID must be an int."
            return
        if not card_id in self.game["players"][self.current_player]:
            print "*** card ID of '%d' not in hand, please input a valid ID." % card_id
            return
        self.move = {"type": "play", "data": card_id}
        return True

    def do_clue(self, _args):
        args = _args.split()

        if not len(args) == 2:
            print "*** Only two arguments can be given (player ID and clue data)."
            return

        try:
            pid = int(args[0])
        except ValueError:
            print "*** First argument must be an int for the player ID."
            return

        if not pid in self.game["players"]:
            print "*** First argument of '%d' must be a valid player ID." % pid
            return
        
        try:
            value = int(args[1])
        except ValueError:
            # Try a color
            if not args[1] in COLOURS or \
               not args[1] in COLOURS_SHORT:
                print "*** Second argument of '%s' must be either a valid colour (long or short form) or card value." % args[1]
                return

            # Convert colour to long form
            if args[1] in COLOURS_SHORT:
                colour = COLOURS_SHORT[args[1]]
            else:
                colour = args[1]

            self.move = {"type": "clue", "data": (pid, colour)}
            return True
        else:
            # Could be a value
            if not value in VALUES:
                print "*** Second argument of '%s' must be either a valid colour (long or short form) or card value." % args[1]
                return

            self.move = {"type": "clue", "data": (pid, value)}
            return True
        
    def do_EOF(self, line):
        return True
    
    def postloop(self):
        print 

def play_move_manual(game, current_player, memory, user_args):
    interp = MoveInterpreter(game, current_player, memory)
    interp.cmdloop()
    if interp.move:
        return interp.move
    else:
        sys.exit()

def create_random_clue(game, current_player, method = 0):
    # Make sure it is a valid clue
    pid = random.choice([pid for pid in game["players"].keys() if pid != current_player])
    other_hand = game["players"][pid]
    # Picking a card then a colour or value ensures an even
    # distribution, instead of getting the colours and values then
    # picking one, which would skew the distribution towards which
    # colour or value was more frequent
    if method == 0:
        card = random.choice(other_hand)
        clue_data = random.choice(card[0:1])
    else:
        clue_data = random.choice([c[0] for c in other_hand] + [c[1] for c in other_hand])

    return {"type": "clue",
            "data": (pid, clue_data)}

def play_move_random(game, current_player, memory, user_args):
    clue_method = 0
    if isinstance(user_args, dict):
        if "seed" in user_args:
            random.seed(user_args["seed"])
        if "clue_method" in user_args:
            clue_method = user_args["clue_method"]
    
    my_hand = game["players"][current_player]

    if game["clues"] > 0:
        m = random.choice(MOVE_TYPES)
    else:
        m = random.choice(["discard", "play"])

    if m == "clue":
        return create_random_clue(game, current_player, clue_method)
    else:
        # Discard or played
        return {"type": m, "data": random.choice(my_hand)}

if __name__ == "__main__":
    play(10, 3, play_move_random)
