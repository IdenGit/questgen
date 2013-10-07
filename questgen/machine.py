# coding: utf-8
import random

from questgen import facts
from questgen import exceptions

EMPTY_LAMBDA = lambda *argv, **kwargs: None

class Machine(object):

    def __init__(self, knowledge_base, on_state=EMPTY_LAMBDA, on_jump_start=EMPTY_LAMBDA, on_jump_end=EMPTY_LAMBDA):
        self.knowledge_base = knowledge_base
        self.on_state = on_state
        self.on_jump_start = on_jump_start
        self.on_jump_end = on_jump_end

    @property
    def pointer(self):
        if facts.Pointer.UID not in self.knowledge_base:
            self.knowledge_base += facts.Pointer()
        return self.knowledge_base[facts.Pointer.UID]

    def _has_jumps(self, fact):
        return bool([jump for jump in self.knowledge_base.filter(facts.Jump) if jump.state_from == fact.uid])

    @property
    def is_processed(self): # TODO: tests
        finish = self.current_state

        if not isinstance(finish, facts.Finish):
            return False

        return not self._has_jumps(finish)

    @property
    def current_state(self):
        if self.pointer.state is None:
            return None
        return self.knowledge_base[self.pointer.state]

    def get_start_state(self):
        jump_ends = set((jump.state_to for jump in self.knowledge_base.filter(facts.Jump)))
        return (start for start in self.knowledge_base.filter(facts.Start) if start.uid not in jump_ends).next()

    @property
    def next_state(self):
        if self.current_state is None:
            return self.get_start_state()

        if self.pointer.jump is None:
            return None

        return self.knowledge_base[self.knowledge_base[self.pointer.jump].state_to]

    def step(self):
        next_state = self.next_state

        if next_state:
            new_pointer = self.pointer.change(state=next_state.uid, jump=None)

            if self.pointer.jump is not None:
                self.on_jump_end(jump=self.knowledge_base[self.pointer.jump])

            self.on_state(state=next_state)
        else:
            next_jump = None

            if not self._has_jumps(self.current_state):
                raise exceptions.NoJumpsFromLastStateError(state=self.current_state)

            next_jump = self.get_next_jump(self.current_state)

            new_pointer = self.pointer.change(jump=next_jump.uid if next_jump else None)

            if next_jump is not None:
                self.on_jump_start(jump=next_jump)

        self.knowledge_base -= self.pointer
        self.knowledge_base += new_pointer


    def can_do_step(self):
        if self.is_processed:
            return False

        if self.pointer.jump is None:
            return True

        return self.next_state is not None and all(requirement.check(self.knowledge_base) for requirement in self.next_state.require)

    def step_until_can(self):
        while self.can_do_step():
            self.step()

    def sync_pointer(self):
        if self.current_state is None:
            return

        new_pointer = self.pointer.change(jump=self.get_next_jump(self.current_state).uid)

        if new_pointer.jump is not None and self.pointer.jump != new_pointer.jump:
            self.on_jump_start(jump=self.knowledge_base[new_pointer.jump])

            self.knowledge_base -= self.pointer
            self.knowledge_base += new_pointer


    def get_next_jump(self, state, single=True):
        jumps = self.get_available_jumps(state)
        if not jumps:
            raise exceptions.NoJumpsAvailableError(state=state)
        if single and len(jumps) > 1:
            raise exceptions.MoreThenOneJumpsAvailableError(state=state)
        return random.choice(jumps)

    def get_available_jumps(self, state):
        if isinstance(state, facts.Choice):
            defaults = [default for default in self.knowledge_base.filter(facts.ChoicePath) if default.choice == state.uid]
            return [self.knowledge_base[default.option] for default in defaults]

        return [jump
                for jump in self.knowledge_base.filter(facts.Jump)
                if jump.state_from == state.uid]

    def get_nearest_choice(self):
        current_state = self.current_state

        if current_state is None:
            current_state = self.get_start_state()

        first_step = True

        while not isinstance(current_state, facts.Finish) and (first_step or not isinstance(current_state, facts.Start)):

            first_step = False

            if isinstance(current_state, facts.Choice):
                options = [option for option in self.knowledge_base.filter(facts.Option) if option.state_from == current_state.uid]
                defaults = [default for default in self.knowledge_base.filter(facts.ChoicePath) if default.choice == current_state.uid]
                return (current_state, options, defaults)

            current_state = self.knowledge_base[self.get_next_jump(current_state, single=True).state_to]

        return (None, None, None)
