from hanabi_old import *
from itertools import chain, repeat
from operator import itemgetter

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

# Iterate the algorithms to compare
for i in range(NUM_ALGORITHMS):
    print "For algorithm %0d:" % i
    play(100, 3, play_move, {"algorithm": i}, load_state = True)
    print "-" * 80

