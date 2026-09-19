from __future__ import annotations
__all__ = (
    'BaseFlags',
    'Flag'
)

from typing import Callable, Union, Optional, Self, overload

class BaseFlags:
    def __init__(self, value: Optional[int] = None, **kwargs: bool) -> None:
        # 0 = all flags disabled
        self.flags: dict[str, Flag] = {}
        cls = type(self)
        for name in dir(cls):
            attr = getattr(cls, name)
            if isinstance(attr, Flag):
                for key, flag in self.flags.items():
                    if flag == attr:
                        name = key
                        raise RuntimeError(f'Flag {name} with bit {attr.bit} has already been registered as {name}')
                self.flags[name] = attr
        for name, flag_value in kwargs.items():
            flag = self.flags.get(name)
            if not flag:
                raise RuntimeError(f'{name} is not a valid flag of {cls.__name__}')
            self._set(flag.bit, flag_value)
        flags = self.flags.values()
        self.value = value or 0

    def _is_enabled(self, bit: int) -> bool:
        '''
        Checks if the given bit is enabled.

        Parameters
        ----------
        bit : int
            Bit to check.

        Returns
        -------
        bool
            Whether ``bit`` is enabled.
        '''
        return bool(self.value & bit)
    
    def _is_disabled(self, bit: int) -> bool:
        '''Alias to `not self._is_enabled(bit)`'''
        return not self._is_enabled(bit)
    
    def _enable(self, bit: int):
        '''Enabled the given bit.'''
        self._set(bit, True)

    def _disable(self, bit: int):
        '''Disables the specified bit.'''
        self._set(bit, False)

    def _set(self, bit: int, enabled: bool):
        '''Sets value for specified bit.'''
        if enabled:
            # Bitwise OR
            self.value |= bit
        else:
            # Bitwise AND
            self.value &= ~bit
        return self.value
    

class Flag:
    def __init__(self, bit: Union[int, Callable[..., int]]) -> None:
        '''
        Constructs value of ``BaseFlags`` value

        _extended_summary_

        Parameters
        ----------
        bit : Union[int, Callable[..., int]]
            _description_
        '''
        name = None
        if isinstance(bit, Callable):
            # Bit is callable, get value
            name = bit.__name__
            bit = bit()
        self.name: Optional[str] = name
        self.bit: int = bit

    @overload
    def __get__(self, instance: None, *args) -> Self:
        ...

    @overload
    def __get__(self, instance: BaseFlags, *args) -> bool:
        ...

    def __get__(self, instance: Optional[BaseFlags], *args) -> ...:
        if not instance:
            # This flag has not been registered to base class,
            # return the object instead
            return self
        return instance._is_enabled(self.bit)
    
    def __set__(self, instance: BaseFlags, value: bool):
        instance._set(self.bit, value)

    def __eq__(self, other):
        return isinstance(other, Flag) and other.bit == self.bit