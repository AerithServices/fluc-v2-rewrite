__all__ = (
    'eval_node',
    'compile_expression',
    'c_cast',
    'render_bytebeat',
    'save_wav'
)

import ast
import operator
import math
import wave
import io
import numpy as np
from numpy.typing import DTypeLike, NDArray
from typing import Any, Callable, TypeAlias, Union

Number: TypeAlias = int | float
PI = 3.141592653589793
TABLE_SIZE = 4096
SHRT_MAX = 32767
TIME = 30
OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.BitOr: operator.or_,
    ast.BitAnd: operator.and_,
    ast.BitXor: operator.xor,
    ast.LShift: operator.lshift,
    ast.RShift: operator.rshift,
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
    ast.Invert: operator.invert,
}

sin_vals = [
    math.sin(2.0 * PI * i / TABLE_SIZE)
    for i in range(TABLE_SIZE)
]

def sin(f: float) -> float:
    i = int(f / (2.0 * PI) * TABLE_SIZE)
    return sin_vals[i % TABLE_SIZE]

def cos(f: float) -> float:
    return sin(f + PI / 2.0)

def sine_wave(t: float, freq: float, sample_rate: float) -> float:
    return sin(2.0 * PI * freq * t / sample_rate)

def square_wave(t: float, freq: float, sample_rate: float) -> float:
    return 1.0 if sine_wave(t, freq, sample_rate) >= 0.0 else -1.0

def triangle_wave(t: float, freq: float, sample_rate: float) -> float:
    phase = (t * freq / sample_rate) % 1.0
    return 4.0 * abs(phase - 0.5) - 1.0

def sawtooth_wave(t: float, freq: float, sample_rate: float) -> float:
    phase = (t * freq / sample_rate) % 1.0
    return 2.0 * phase - 1.0

FUNCS = {
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'sqrt': math.sqrt,
    'abs': abs,
    'min': min,
    'max': max,
    'fastSin': sin,
    'fastCos': cos,
    'sineWave': sine_wave,
    'squareWave': square_wave,
    'triangleWave': triangle_wave,
    'sawtoothWave': sawtooth_wave,
    'int': int,
    'float': float,
    'str': str,
    'bytes': bytes,
    'complex': complex
}

CONSTS = {
    'pi': PI,
    'e': math.e,
}

def eval_node(node: ast.AST, vars: dict[str, Any]) -> Number:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        raise TypeError("Only numeric constants are allowed")
    if isinstance(node, ast.Name):
        if node.id in vars:
            return vars[node.id]
        if node.id in CONSTS:
            return CONSTS[node.id]
        raise NameError(node.id)
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](
            eval_node(node.left, vars),
            eval_node(node.right, vars)
        )
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](
            eval_node(node.operand, vars)
        )
    if isinstance(node, ast.Call):
        assert isinstance(node.func, ast.Name)
        fn = FUNCS[node.func.id]
        args = [eval_node(a, vars) for a in node.args]
        return fn(*args)
    raise ValueError(type(node).__name__)

def compile_expression(expression: str) -> Callable[..., Number]:
    def f(**vars) -> Number:
        return eval_node(body, vars)

    body = ast.parse(expression, mode='eval').body
    return f

def c_cast(value: Number, dtype: DTypeLike) -> Number:
    # Handles overflow the way C does it I guess
    if np.issubdtype(dtype, np.floating):
        return float(value)
    value = int(value)
    bits = np.dtype(dtype).itemsize * 8
    if np.issubdtype(dtype, np.unsignedinteger):
        return value & ((1 << bits) - 1)
    elif np.issubdtype(dtype, np.signedinteger):
        value &= (1 << bits) - 1
        if value >= (1 << (bits - 1)):
            value -= (1 << bits)
        return value
    else:
        return value

async def render_bytebeat(expression: str, sample_rate: int, seconds: int, dtype: DTypeLike = np.uint8) -> NDArray:
    dtype = np.dtype(dtype)
    count = sample_rate * seconds
    raw = np.empty(count, dtype=dtype)
    f = compile_expression(expression)
    for t in range(count):
        try:
            raw[t] = c_cast(f(t=t), dtype)
        except ZeroDivisionError:
            raw[t] = 0
    if dtype == np.uint8:
        return raw.view(np.int16)
    elif dtype == np.int16:
        return raw
    elif dtype == np.float32:
        return raw
    else:
        return raw.astype(np.int16)

def save_wav(writeable: Union[str, io.BytesIO], samples: NDArray, sample_rate: int):
    with wave.open(writeable, 'wb') as wav:
        wav.setnchannels(1)
        if samples.dtype == np.float32:
            wav.setsampwidth(4)
        else:
            wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())
