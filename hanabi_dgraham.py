from hanabi import *
from itertools import chain, repeat
from operator import itemgetter
from simpleai.search import SearchProblem, breadth_first
from simpleai.search.viewers import *
from copy import deepcopy


FULL_SET = [(c, v) for c in COLOURS for v in VALUES]
CARDS_PER_VALUE = [v for v in VALUES for i in xrange(VALUES_COUNT[v - 1])]
NUM_ALGORITHMS = 4

def get_from(d, key, default):
    if not key in d:
        if callable(default):
            d[key] = default()
        else:
            d[key] = default

    return d[key]

def rule_out(my_hand, colour, value):
    for id in my_hand.keys():
        # Only remove it if it hasn't already been removed
        if (colour, value) in my_hand[id]:
            my_hand[id].remove((colour, value))

def prune(my_hand, ids, colour_or_value):
    my_ids = my_hand.keys()
    for id in my_ids:
        if id in ids:
            # If the clue is for this card, then remove all cards that
            # are not the indicated colour or value
            if isinstance(colour_or_value, str):
                my_hand[id] = [c for c in my_hand[id] if c[0] == colour_or_value]
            else:
                my_hand[id] = [c for c in my_hand[id] if c[1] == colour_or_value]                    
        else:
            # Else if the clue is not for this card, then we know it
            # is not the indicated colour or value
            if isinstance(colour_or_value, str):
                my_hand[id] = [c for c in my_hand[id] if c[0] != colour_or_value]
            else:
                my_hand[id] = [c for c in my_hand[id] if c[1] != colour_or_value]

def build_possible_hands(game, current_player):
    """Return the possibilities for each card in every other player's
    hand from the perspective of the `current_player'.
    """
    hand_possibilities = {}
    whats_left = {}
    for p, h in game["players"].iteritems():
        # Initialise what each of the players cards could be
        hand_possibilities[p] = dict([(id, list(FULL_SET)) for id in h])

        # Initialise all the possible cards which we will then update
        # as we assess the game
        whats_left[p] = dict([(c, list(CARDS_PER_VALUE)) for c in COLOURS])

        # Remove what's in other players' hands and what's been played
        # or discarded. Since we don't know the current player's hand
        # then we have to make an inexact picture of what *other*
        # players know
        all_cards = list(chain(chain.from_iterable([h1 for p1, h1 in game["players"].iteritems() \
                                                    if (p1 != p and p1 != current_player)]),
                               game["played"], game["discarded"]))
        for (colour, value, id) in all_cards:
            whats_left[p][colour].remove(value)

        # Rule out from each player's hand any card not possible from
        # what's left
        for colour, values in whats_left[p].iteritems():
            for v in VALUES:
                if not v in values:
                    rule_out(hand_possibilities[p], colour, v)

        # Update the hand with any clues given to this player
        for clue_data in [m[1]["data"] for m in game["moves"] if m[1]["type"] == "clue" and \
                          m[1]["data"][0] == p]:
            prune(hand_possibilities[p], clue_data[2], clue_data[1])

    return hand_possibilities

def all_moves(game, current_player):
    """Return all moves for the current player."""
    moves = []

    # Played and discard moves are easy
    # Remember that our cards may be obfuscated
    hand = game["players"][current_player]

    if isinstance(hand[0], int):
        card_ids = hand
    else:
        card_ids = [c[2] for c in hand]

    for card_id in card_ids:
        moves.append({"type": "play", "data": card_id})
        moves.append({"type": "discard", "data": card_id})

    # Want every possible clue
    for pid, hand in game["players"].iteritems():
        if pid != current_player:
            for c in colours_in_hand(hand):
                moves.append({"type": "clue", "data": (pid, c)})
            for v in values_in_hand(hand):
                moves.append({"type": "clue", "data": (pid, v)})

    return moves

def simulate(game, move):
    """Simulate the given `move' on the current game to see if it is worth
    making. This does not modify the game passed in, it returns a
    modified copy.
    """

    def play_one_move(game, current_player, memory, user_args):
        return move

    # Make a copy
    new_game = deepcopy(game)
    new_game = play_one_turn(new_game,
                             new_game["current_player"],
                             play_one_move,
                             None,
                             None,
                             False)

    return new_game

class HanabiProblem(SearchProblem):
    def __init__(self, initial_game):
        # Can't use the game as the state that gets passed around
        # because it is a dictionary and that's not hashable. Can make
        # it hashable but a hash would be too long, so it is easier to
        # index into a list of game objects
        super(HanabiProblem, self).__init__(0)
        self.game_states = [initial_game]

    def actions(self, game_id):
        """this method receives the index into the list of game states
        (`game_id'), and must return the list of moves that can be
        performed from that particular game state.
        """
        game = self.game_states[game_id]
        return all_moves(game, game["current_player"])

    def result(self, game_id, move):
        """this method receives the index into the list of game states and a
        move, and must return the resulting state of applying that
        particular move from that particular game state.
        """
        game = self.game_states[game_id]
        next_game = simulate(game, move)
        self.game_states.append(next_game)
        return (len(self.game_states) - 1)

    def is_goal(self, game_id):
        """this method receives the index into the list of game states, and
        must return True if the game state is a goal state, or False
        if don't.
        """
        game = self.game_states[game_id]
        return have_won(game)

def play_move(game, current_player, memory, user_args):
    hand = game["players"][current_player]
    
    # This stores the possible cards that each card in my hand could
    # be. Need to use this syntax so we get a copy of FULL_SET iso a
    # reference
    my_hand = get_from(memory, "my_hand", dict([(id, list(FULL_SET)) for id in hand]))

    # This stores what possible cards are left in the deck
    whats_left = get_from(memory, "whats_left", dict([(c, list(CARDS_PER_VALUE)) for c in COLOURS]))

    # Keep track of what cards have been analysed
    seen = get_from(memory, "seen", {})

    # Use this to work out what new clues I need to process
    last_clue = get_from(memory, "last_clue", -1)

    # A way to try out different algorithms
    algorithm = get_from(user_args, "algorithm", 0)

    # Remove any cards I don't have anymore
    old_ids = my_hand.keys()
    for oid in old_ids:
        if not oid in hand:
            del my_hand[oid]

    # Initialise any new cards
    for id in hand:
        if not id in my_hand:
            my_hand[id] = list(FULL_SET)   # take a copy

    # Update what's left by first checking other player's hands,
    # making sure not to look at my hand and to only examine those
    # I've not seen.
    # I do have to look at the discarded and played piles because I
    # may have put a card there.
    # chain.from_iterable flattens all the hands into one list and
    # chain joins the lists into one iterator
    all_cards = list(chain(chain.from_iterable([h for p, h in game["players"].iteritems() if p != current_player]),
                      game["played"], game["discarded"]))
    for (colour, value, id) in all_cards:
        if not id in seen:
            whats_left[colour].remove(value)
            seen[id] = True

    # Rule out from my hand any card not possible from what's left
    for colour, values in whats_left.iteritems():
        for v in VALUES:
            if not v in values:
                rule_out(my_hand, colour, v)

    # Update my hand with any clues given to me since last time
    for clue_data in [m[1]["data"] for i, m in enumerate(game["moves"]) if m[1]["type"] == "clue" and \
                 m[1]["data"][0] == current_player and \
                 i > last_clue]:
        prune(my_hand, clue_data[2], clue_data[1])

    # Easiest to just set it to the last move as we only process clues
    # above
    last_clue = len(game["moves"]) - 1

    # Now we have worked out what cards I might have, let's see if any
    # are playable
    my_playable = {}
    for id, possible_cards in my_hand.iteritems():
        l = [c for c in possible_cards if playable(game, c)]
        # Keep a recording of how many are playable
        if len(l):
            my_playable[id] = (len(l), len(possible_cards), l)

    # Find if any are a dead certain
    definitely_playable = [id for id, data in my_playable.iteritems() if data[0] == data[1]]
    
    if len(definitely_playable):
        #TODO: Don't need to play it!
        #TODO: Probably a bit of smarts in working out which is best to play, e.g. a 1
        m = {"type": "play", "data": definitely_playable[0]}
    else:
        #TODO: Don't need to give a clue, could discard
        #TODO: Could play based on probability
        # Can then discard or give a clue
        if game["clues"] > 0:
            #TODO: This won't work very well because you have to pick a colour or value
            player_order = get_player_order(game, current_player)
            # List of lists (with empty lists removed)
            other_players_playable_cards = filter(None, [[(p, c) for c in game["players"][p] if playable(game, c)] for p in player_order])
            # Flattened
            other_players_playable_cards_f = list(chain.from_iterable(other_players_playable_cards))

            if len(other_players_playable_cards_f):
                if algorithm == 1:
                    # Give a clue to the first playable card
                    (player, card) = other_players_playable_cards_f[0]
                    clue_data = random.choice(card[0:1])
                    m = {"type": "clue", "data": (player, clue_data)}
                elif algorithm == 2:
                    # Find the first instance of the lowest value (x[1][1] is the value)
                    (player, card) = sorted(other_players_playable_cards_f, key = lambda x: x[1][1])[0]
                    clue_data = random.choice(card[0:1])
                    m = {"type": "clue", "data": (player, clue_data)}
                elif algorithm == 3:
                    # Give a clue to the first player with a playable
                    # card and for the lowest value card in her hand
                    (player, card) = sorted(other_players_playable_cards[0], key = lambda x: x[1][1])[0]
                    clue_data = random.choice(card[0:1])
                    m = {"type": "clue", "data": (player, clue_data)}
                elif algorithm == 4:
                    # Find the clue that leads to the highest number
                    # of definitely playable cards
                    #TODO: This doesn't take into account anything that the players know already (need to simulate)
                    for p in player_order:
                        for c in game["players"][p]:
                            for clue_data in card[0:1]:
                                m = {"type": "clue", "data": (p, clue_data)}
                                def_playable_move.append((m, ))
                else:
                    # Covers the default algorithm 0
                    m = create_random_clue(game, current_player)
            else:
                m = create_random_clue(game, current_player)

        else:
            # Definitely have to discard
            #TODO: Discard only those that are not needed anymore
            #TODO: Don't do a random discard
            m = {"type": "discard", "data": random.choice(hand)}

    # Returning the move here instead of in the code above makes it
    # easier to debug
    return m

def play_move_ai(game, current_player, memory, user_args):
    my_viewer = ConsoleViewer()
    my_problem = HanabiProblem(game)
    result = breadth_first(my_problem, viewer=my_viewer)
    #result = breadth_first(my_problem)
    print result.state
    print print_game(result.game_states[result.state], -1, True)
    print result.path()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", type = str, choices = ["default", "ai"],
                        default = "default", help = "Which move function to use.")
    parser.add_argument("-a", type = int, default = 0,
                        help = "Which algorithm to use of the move function. Default is to permute all.")
    parser.add_argument("-n", type = int, default = 1,
                        help = "How many times to play.")
    parser.add_argument("-p", type = int, default = 3, choices = [2, 3, 4, 5],
                        help = "How many players.")
    parser.add_argument("-r", action = "store_true",
                        help = "Re-run from the previous random seed.")
    args = parser.parse_args()

    if args.f == "ai":
        play(args.n, args.p, play_move_ai, {}, load_state = args.r, obfuscate_game = False)
    else:
        if args.a == 0:
            # Iterate the algorithms to compare
            for i in range(NUM_ALGORITHMS):
                print "For algorithm %0d:" % i
                play(args.n, args.p, play_move, {"algorithm": i}, load_state = args.r)
                print "-" * 80
        else:
                print "For algorithm %0d:" % args.a
                play(args.n, args.p, play_move, {"algorithm": args.a}, load_state = args.r)
