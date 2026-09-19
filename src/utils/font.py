__all__ = (
    'FontGen',
    'PhraseGen',
    'fmt_phrases'
)

import string
from utils.state import State

class FontGen:
    def __init__(self, fonts: str) -> None:
        self.fonts = self.parse_fonts(fonts)
        available = list(self.fonts.keys())
        for name in available.copy():
            if isinstance(name, str) and name[:5] == '_meta':
                available.remove(name)
        self.available_fonts = available

    def parse_fonts(self, fonts: str) -> dict[str, dict[str, str]]:
        '''
        Parses a font.

        Format of font file:
            {font_name}:{font}
        {font} must include all english letters, and no extra characters.
        {font_name} is optional.

        Parameters
        ----------
        fonts : str
            Content of font file.

        Returns
        -------
        dict[str, dict[str, str]]
            _description_
        '''
        parsed = {}
        for font_index, font in enumerate(fonts.split('\n')):
            font = font.strip()
            if font.startswith('#'):
                # Is a comment
                continue
            name, font = font.split(':', maxsplit=1)
            # Number of characters in font / the amount of characters
            coefficient = len(font) / len(string.ascii_lowercase)
            parsed[f'_meta_{name}'] = coefficient
            if not coefficient.is_integer():
                # Can't parse because the coefficient is a float,
                # which is the amount of characters per letter
                continue
            coefficient = int(coefficient)
            if not name:
                name = font_index
            parsed[name] = {}
            for i, char in enumerate(font):
                actual = string.ascii_letters[i//coefficient]
                parsed[name][actual] = parsed[name].get(actual, '') + char
        return parsed
    
    def fmt(self, text: str, font_name: str) -> str:
        '''Formats text with specified font.'''
        font = self.fonts[font_name]
        formatted = ''
        for char in text:
            if char in font:
                formatted += font[char]
            else:
                formatted += char
        return formatted
    

class PhraseGen:
    def __init__(self, phrases: str, name: str, emoji_wrapper: list[str] = ['「', '」']) -> None:
        if len(emoji_wrapper) != 2 and emoji_wrapper:
            raise ValueError('emoji_wrapper must be of length 2 or 0')
        self.name = name
        self.emoji_wrapper = emoji_wrapper
        self.raw_phrases = phrases
        self.phrases = self.parse_phrases(phrases)

    def parse_phrases(self, phrases: str) -> list[str]:
        '''
        Parses phrases.

        Must be in format {emoji}:{phrase}.
        {name} in phrase will be replaced with :attr:`~utils.PhraseGen.name`.
        {emoji} is optional.

        Parameters
        ----------
        phrases : str
            Phrases.

        Returns
        -------
        list[str]
            Parsed phrases.
        '''
        new_phrases = ''
        for phrase in phrases.split('\n'):
            phrase = phrase.strip()
            if phrase.startswith('#'):
                # Comment
                continue
            emoji, phrase = phrase.split(':', maxsplit=1)
            if len(self.emoji_wrapper):
                wrapper = self.emoji_wrapper.copy()
                wrapper.insert(1, emoji)
                wrapped = ''.join(wrapper)
            else:
                wrapped = emoji
            new_phrases += wrapped + phrase + '\n'
        new_phrases = new_phrases.strip()
        formatted = new_phrases.format(name=self.name)
        return formatted.split('\n')
    
    def fmt_all(self, gen: FontGen, font: str) -> list[str]:
        '''Formats all phrases with specific font.'''
        phrases = self.phrases
        formatted = []
        for phrase in phrases:
            new = gen.fmt(phrase, font)
            formatted.append(new)
        return formatted
    
def fmt_phrases(phrases: PhraseGen, fonts: FontGen) -> list[str]:
    '''Formats all phrases with random fonts.'''
    formatted = []
    for phrase in phrases.phrases:
        font = State.xs32.choice(fonts.available_fonts)
        formatted_phrase = fonts.fmt(phrase, font)
        formatted.append(formatted_phrase)
    return formatted