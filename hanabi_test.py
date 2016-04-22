import unittest
from hanabi import *
import random

class PlayMoveTest(unittest.TestCase):

    #def setUp(self):
        
    def testMemoryRetained(self):
        first_call = {}

        def move(game, current_player, memory, user_args):
            #global first_call
            if not current_player in first_call:
                self.assertEqual(memory, {})
                memory["pid"] = current_player
                first_call[current_player] = True
            else:
                self.assertEqual(memory["pid"], current_player)

            # Need to do this to avoid game errors
            my_hand = game["players"][current_player]
            return {"type": "discard", "data": random.choice(my_hand)}


        play(1, 3, move, load_state = True)

if __name__ == '__main__':
    unittest.main()
