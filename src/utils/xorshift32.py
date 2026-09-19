__all__ = (
    'Xorshift32',
)

import random
from typing import overload, Sequence, Optional, Union

class Xorshift32:
    state: int
    seed: int

    def __init__(self, seed: int = int(random.random() * 10 ** 15)) -> None:
        '''
        Implementation of Xorshift32.

        Is ~3x faster than random.random().

        Parameters
        ----------
        seed : Optional[int]
            Seed for the algorithm, by default int(random.random() * 10 ** 15)
        '''
        self.seed = seed
        self.state = self.seed
        self.magic = 0xFFFFFFFF

    def next(self) -> float:
        '''
        Returns pseudo-random value.

        Result will be stored in :attr:`~utils.Xorshift32.state`.

        Returns
        -------
        float
            Pseudo-random value generated.
        '''
        self.state ^= (self.state << 13) & self.magic
        self.state ^= (self.state >> 17) & self.magic
        self.state ^= (self.state << 5) & self.magic
        return self.state
    
    @overload
    def choice[T](self, seq: Sequence[T], *, length: None = ...) -> T:
        ...
    
    @overload
    def choice[T](self, seq: Sequence[T], *, length: int) -> list[T]:
        ...
    
    def choice[T](self, seq: Sequence[T], *, length: Optional[int] = None) -> Union[T, list[T]]:
        '''
        Chooses pseudo-random item from given sequence.

        Parameters
        ----------
        seq : Sequence[T]
            Sequence to use.
        length : Optional[int]
            Amount of items to choose, defaults to 1.

        Returns
        -------
        T
            Pseudo-random item from ``seq``.
        '''
        def next_index() -> int:
            self.next()
            return self.state % len(seq)

        if length:
            indexes = []
            for _ in range(length):
                indexes.append(next_index())
            return [seq[index] for index in indexes]
        return seq[next_index()]