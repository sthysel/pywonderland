"""
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
DFA construction and minimization for Coxeter automata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
from collections import deque
import numpy as np
import pygraphviz


class DFAState(object):

    def __init__(self, subset, accept=True):
        """`subset`: a set of integers which specifies a subset of the minimal roots,
           stored in a frozenset.
        """
        self.subset = subset
        self.accept = accept
        self.index = None
        self.transitions = dict()

    def __str__(self):
        return str(self.subset)

    __repr__ = __str__

    def add_transition(self, symbol, target):
        if symbol in self.transitions:
            raise ValueError("state already has this transition")
        self.transitions[symbol] = target

    def all_transitions(self):
        return self.transitions.items()

    def draw(self, G, found, color="black"):
        if self in found:
            return
        found.add(self)
        shape = "doublecircle" if self.accept else "circle"
        G.add_node(self.index, shape=shape, color=color)
        for symbol, target in self.all_transitions():
            target.draw(G, found)
            G.add_edge(self.index, target.index, label=symbol)


class DFA(object):

    def __init__(self, start, sigma):
        """`start`: the starting state of the DFA. Unreachable states from this
           start will be automatically discarded.
           `sigma`: the tuple of symbols.
        """
        self.start = start
        self.sigma = sigma
        self.num_states = self.reindex(self.start, 0)

    def reindex(self, state, next_index):
        """Reindex the states in the automaton.
        """
        if state.index is None:
            state.index = next_index
            next_index += 1
            for _, target in state.all_transitions():
                next_index = self.reindex(target, next_index)
        return next_index

    def draw(self, filename, program="dot"):
        """Use graphviz to draw this automaton.
        """
        G = pygraphviz.AGraph(strict=False, directed=True, rankdir="LR")
        self.start.draw(G, set(), color="red")
        G.draw(filename, prog=program)
        return self

    def minimize(self):
        return Hopcroft(self)()


class Hopcroft(object):

    """Minimize a DFA using Hopcroft's algorithm.
    """

    def __init__(self, dfa):
        self.start = dfa.start
        self.sigma = dfa.sigma
        self.P = self.initial_partition()

    def __call__(self):
        try:
            s1, s2 = self.initial_partition()
            if len(s1) <= len(s2):
                W = {s1}
            else:
                W = {s2}
        except:
            W = self.initial_partition()

        while W:
            A = W.pop()
            for c in self.sigma:
                # Be careful that if we modify a set while iterating over it then unpredictable
                # things would happen, so iterate over another same partition!
                T = frozenset(self.P)
                for Y in T:
                    S = self.split(Y, c, A)
                    if S:
                        s1, s2 = S
                        self.P.remove(Y)
                        self.P.add(s1)
                        self.P.add(s2)
                        if Y in W:
                            W.remove(Y)
                            W.add(s1)
                            W.add(s2)
                        else:
                            if len(s1) <= len(s2):
                                W.add(s1)
                            else:
                                W.add(s2)
        # now self.P is our final partition
        # let's make it a DFA
        result_dfa = dict()

        def aux(subset):
            state = next(iter(subset))
            dfa_state = DFAState(state.accept)
            result_dfa[subset] = dfa_state

            for symbol, target in state.transitions.items():
                target_subset = self.current_partition_containing(target)
                if target_subset not in result_dfa:
                    aux(target_subset)
                dfa_state.add_transition(symbol, result_dfa[target_subset])

            return dfa_state

        initial_subset = self.current_partition_containing(self.start)
        return DFA(aux(initial_subset), self.sigma)

    def initial_partition(self):
        """Partition all the states into accepted and non-accepted subsets.
        """
        s1 = set()
        s2 = set()

        def aux(state):
            if state.accept:
                s1.add(state)
            else:
                s2.add(state)
            for target in state.transitions.values():
                if target not in set.union(s1, s2):
                    aux(target)

        aux(self.start)
        # be careful the case that all states are accepted
        if s1 and s2:
            return {frozenset(s1), frozenset(s2)}
        return {frozenset(s1)}

    def split(self, S, c, B):
        """Try to split set S into two subsets {s1, s2} by a pair (B, c).
           If not splitted then return None.
        """
        s1 = set()
        s2 = set()
        for x in S:
            y = x.transitions.get(c, None)
            if y in B:
                s1.add(x)
            else:
                s2.add(x)
        if s1 and s2:
            return {frozenset(s1), frozenset(s2)}
        return None

    def current_partition_containing(self, state):
        """Return the subset that contains the given state in current partition.
        """
        for p in self.P:
            if state in p:
                return p


def get_automaton(reftable, type="shortlex"):
    """Construct the automaton that recognizes the language of a Coxeter group.
    """
    if type not in ["shortlex", "reduced"]:
        raise ValueError("Unknown type of automaton, must be 'reduced' or 'shortlex'")

    table = np.asarray(reftable, dtype=object)
    rank = table.shape[1]

    def subset_transition(S, i):
        r"""`S` is a subset of the set of minimal roots, this function computes
           the transition of S by the simple reflection s_i in the automaton.
           The transition rule for the automaton of "reduced words" is:
           for s_i ∉ S,

                   s_i
                S -----> {s_i} ∪ (s_i(S) ∩ Σ)

            where Σ is the set of minimal roots.
            For the automaton of "normal forms" the transition rule is

                   s_i
                S -----> {s_i} ∪ (s_i(S) ∪ {s_i(α_j), j<i}) ∩ Σ
        """
        if i in S:
            return None

        result = set([i])
        for j in S:
            k = table[j][i]
            if k is not None:
                result.add(k)

        if type == "shortlex":
            for j in range(i):
                k = table[j][i]
                if k is not None:
                    result.add(k)

        return frozenset(result)

    start = DFAState(frozenset())
    queue = deque([start])
    states = [start]

    # this is just a breadth-first search of the automaton.
    while queue:
        S = queue.popleft()
        for i in range(rank):
            # if the transition of S by i is unknown
            if i not in S.transitions:
                # compute the transition
                t = subset_transition(S.subset, i)
                if t is not None:
                    # so t is a subset in the automaton, have we seen it yet?
                    found = False
                    for T in states:
                        if t == T.subset:  # we have seen t before, just add the transition
                            S.add_transition(i, T)
                            found = True
                            break
                    if not found:
                        # so t is a new subset, create a new state for it.
                        T = DFAState(t)
                        S.add_transition(i, T)
                        queue.append(T)
                        states.append(T)
    # return the minimized dfa
    return DFA(start, tuple(range(rank))).minimize()
