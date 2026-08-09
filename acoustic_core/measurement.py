"""Pure-stdlib acoustic measurement baselines for bounded inputs."""

import cmath
import math
import struct
from numbers import Real
from typing import Iterable, Optional

from .models import BANDAS_OCTAVA, Room


C = 343.0
_MAX_AUDIO_FRAMES = 10_000_000
_MAX_ANALYSIS_SAMPLES = 1_000_000


def _next_pow2(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()


def _fft(x: list[complex]) -> list[complex]:
    """Radix-2 FFT used by the bounded pure-Python analysis functions."""
    n = len(x)
    if n <= 1:
        return x.copy()
    if n & (n - 1):
        raise ValueError("FFT length must be a power of two")
    even = _fft(x[0::2])
    odd = _fft(x[1::2])
    step = cmath.exp(-2j * math.pi / n)
    twiddle = 1.0 + 0.0j
    output = [0j] * n
    half = n // 2
    for index in range(half):
        product = twiddle * odd[index]
        output[index] = even[index] + product
        output[index + half] = even[index] - product
        twiddle *= step
    return output


def _ifft(x: list[complex]) -> list[complex]:
    if not x:
        return []
    conjugated = [value.conjugate() for value in x]
    transformed = _fft(conjugated)
    return [value.conjugate() / len(x) for value in transformed]


def _convolve_fft(a: list[float], b: list[float]) -> list[float]:
    if not a or not b:
        return []
    result_length = len(a) + len(b) - 1
    fft_length = _next_pow2(result_length)
    spectrum_a = _fft([complex(value) for value in a] + [0j] * (fft_length - len(a)))
    spectrum_b = _fft([complex(value) for value in b] + [0j] * (fft_length - len(b)))
    result = _ifft([
        spectrum_a[index] * spectrum_b[index] for index in range(fft_length)
    ])
    return [value.real for value in result[:result_length]]


def _finite_signal(signal: Iterable[float], label: str = "signal") -> list[float]:
    values = []
    for value in signal:
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValueError(f"{label} must contain real samples")
        converted = float(value)
        if not math.isfinite(converted):
            raise ValueError(f"{label} must contain finite samples")
        values.append(converted)
    return values


class ESSSignal(list):
    """List-compatible sweep carrying the parameters required by its inverse."""

    def __init__(
        self,
        samples: Iterable[float],
        *,
        f1_hz: float,
        f2_hz: float,
        sample_rate: int,
        sweep_duration_s: float,
    ) -> None:
        super().__init__(samples)
        self.f1_hz = f1_hz
        self.f2_hz = f2_hz
        self.sample_rate = sample_rate
        self.sweep_duration_s = sweep_duration_s


def _validate_ess_parameters(
    f1_hz: float,
    f2_hz: float,
    duration_s: float,
    sample_rate: int,
) -> None:
    values = (f1_hz, f2_hz, duration_s)
    if any(isinstance(value, bool) or not isinstance(value, Real) for value in values):
        raise ValueError("ESS frequencies and duration must be real numbers")
    if not all(math.isfinite(float(value)) for value in values):
        raise ValueError("ESS frequencies and duration must be finite")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if f1_hz <= 0:
        raise ValueError("f1_hz must be positive")
    if f2_hz <= f1_hz:
        raise ValueError("f2_hz must be greater than f1_hz")
    if f2_hz >= sample_rate / 2:
        raise ValueError("f2_hz must be strictly below Nyquist")
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")


def generate_ess(
    f1_hz: float = 20.0,
    f2_hz: float = 20000.0,
    duration_s: float = 5.0,
    sample_rate: int = 44100,
    amplitude: float = 0.9,
    *,
    fade_in_s: float = 0.01,
    fade_out_s: float = 0.01,
    headroom_db: float = 0.0,
) -> list[float]:
    """Generate a deterministic complete exponential sine sweep.

    The first and last discrete instants correspond to ``f1_hz`` and ``f2_hz``
    before the raised-cosine fades are applied.  ``amplitude=0.9`` supplies
    approximately 0.92 dB of default headroom; ``headroom_db`` can reduce it
    further.
    """
    _validate_ess_parameters(f1_hz, f2_hz, duration_s, sample_rate)
    if (
        isinstance(amplitude, bool)
        or not isinstance(amplitude, Real)
        or not math.isfinite(amplitude)
        or not 0 < amplitude <= 1
    ):
        raise ValueError("amplitude must be in (0, 1]")
    if not math.isfinite(headroom_db) or headroom_db < 0:
        raise ValueError("headroom_db must be finite and non-negative")
    if not math.isfinite(fade_in_s) or not math.isfinite(fade_out_s):
        raise ValueError("fade durations must be finite")
    if fade_in_s < 0 or fade_out_s < 0:
        raise ValueError("fade durations must be non-negative")

    sample_count = int(round(sample_rate * duration_s))
    if sample_count < 2:
        raise ValueError("duration_s must contain at least two samples")
    if sample_count > _MAX_AUDIO_FRAMES:
        raise ValueError("ESS exceeds the bounded pure-Python sample limit")
    discrete_duration = (sample_count - 1) / sample_rate
    logarithmic_ratio = math.log(f2_hz / f1_hz)
    phase_scale = 2.0 * math.pi * f1_hz * discrete_duration / logarithmic_ratio
    gain = min(float(amplitude), 10.0 ** (-headroom_db / 20.0))
    fade_in_samples = min(int(round(fade_in_s * sample_rate)), sample_count // 2)
    fade_out_samples = min(int(round(fade_out_s * sample_rate)), sample_count // 2)

    samples = []
    for index in range(sample_count):
        time_s = index / sample_rate
        phase = phase_scale * (
            math.exp(time_s * logarithmic_ratio / discrete_duration) - 1.0
        )
        envelope = 1.0
        if fade_in_samples and index < fade_in_samples:
            envelope *= 0.5 - 0.5 * math.cos(math.pi * index / fade_in_samples)
        remaining = sample_count - 1 - index
        if fade_out_samples and remaining < fade_out_samples:
            envelope *= 0.5 - 0.5 * math.cos(math.pi * remaining / fade_out_samples)
        samples.append(gain * envelope * math.sin(phase))
    return ESSSignal(
        samples,
        f1_hz=float(f1_hz),
        f2_hz=float(f2_hz),
        sample_rate=sample_rate,
        sweep_duration_s=discrete_duration,
    )


def inverse_filter(
    ess: list[float],
    sample_rate: int,
    f1_hz: Optional[float] = None,
    f2_hz: Optional[float] = None,
) -> list[float]:
    """Construct Farina's time-reversed, exponentially weighted ESS inverse."""
    samples = _finite_signal(ess, "ess")
    if len(samples) < 2:
        raise ValueError("ess must contain at least two samples")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    f1_hz = f1_hz if f1_hz is not None else getattr(ess, "f1_hz", None)
    f2_hz = f2_hz if f2_hz is not None else getattr(ess, "f2_hz", None)
    if f1_hz is None or f2_hz is None:
        raise ValueError("f1_hz and f2_hz are required for a plain ESS sample list")
    duration = getattr(ess, "sweep_duration_s", (len(samples) - 1) / sample_rate)
    _validate_ess_parameters(f1_hz, f2_hz, duration, sample_rate)
    logarithmic_ratio = math.log(f2_hz / f1_hz)
    inverse = [
        samples[-1 - index] * math.exp(
            -(index / sample_rate) * logarithmic_ratio / duration
        )
        for index in range(len(samples))
    ]

    # At convolution index N-1 this normalization gives unity for an identity
    # system while retaining the relative amplitudes of recovered IR arrivals.
    reference_peak = sum(
        samples[index] * inverse[len(samples) - 1 - index]
        for index in range(len(samples))
    )
    if abs(reference_peak) <= 1e-20:
        raise ValueError("ESS has insufficient energy for inverse filtering")
    return [value / reference_peak for value in inverse]


def _spectral_deconvolution(
    response: list[float], ess: list[float], regularization: float,
) -> list[float]:
    """Legacy fallback when a plain sweep list has lost its frequency metadata."""
    output_length = max(1, len(response) - len(ess) + 1)
    fft_length = _next_pow2(max(len(response), len(ess) + output_length - 1))
    response_spectrum = _fft(
        [complex(value) for value in response] + [0j] * (fft_length - len(response))
    )
    sweep_spectrum = _fft(
        [complex(value) for value in ess] + [0j] * (fft_length - len(ess))
    )
    maximum_power = max((abs(value) ** 2 for value in sweep_spectrum), default=0.0)
    floor = max(maximum_power * regularization, 1e-30)
    transfer = [
        response_spectrum[index] * sweep_spectrum[index].conjugate()
        / (abs(sweep_spectrum[index]) ** 2 + floor)
        for index in range(fft_length)
    ]
    return [value.real for value in _ifft(transfer)[:output_length]]


def ess_deconvolution(
    response: list[float],
    ess: list[float],
    sample_rate: int,
    *,
    f1_hz: Optional[float] = None,
    f2_hz: Optional[float] = None,
    align: bool = True,
    regularization: float = 1e-10,
) -> list[float]:
    """Deconvolve an ESS recording and optionally align the linear IR at zero.

    Metadata-carrying sweeps from :func:`generate_ess` use Farina's inverse.
    For legacy plain lists without frequency bounds, a regularized frequency-
    domain division is used because the required Farina weighting is otherwise
    not identifiable.
    """
    recorded = _finite_signal(response, "response")
    sweep = _finite_signal(ess, "ess")
    if not recorded or not sweep:
        raise ValueError("response and ess must not be empty")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if not math.isfinite(regularization) or not 0 < regularization < 1:
        raise ValueError("regularization must be in (0, 1)")

    lower = f1_hz if f1_hz is not None else getattr(ess, "f1_hz", None)
    upper = f2_hz if f2_hz is not None else getattr(ess, "f2_hz", None)
    if lower is None or upper is None:
        return _spectral_deconvolution(recorded, sweep, regularization)

    inverse = inverse_filter(ess, sample_rate, lower, upper)
    deconvolved = _convolve_fft(recorded, inverse)
    if not align:
        return deconvolved
    linear_peak_index = len(sweep) - 1
    estimated_ir_length = max(1, len(recorded) - len(sweep) + 1)
    return deconvolved[linear_peak_index:linear_peak_index + estimated_ir_length]


def harmonic_separation_offsets(
    f1_hz: float,
    f2_hz: float,
    duration_s: float,
    sample_rate: int,
    max_order: int = 5,
) -> dict[int, int]:
    """Return Farina harmonic offsets in samples before the linear impulse.

    Harmonic ``k`` is separated by ``T*ln(k)/ln(f2/f1)`` from the linear peak.
    """
    _validate_ess_parameters(f1_hz, f2_hz, duration_s, sample_rate)
    if not isinstance(max_order, int) or isinstance(max_order, bool) or max_order < 2:
        raise ValueError("max_order must be an integer of at least two")
    ratio_log = math.log(f2_hz / f1_hz)
    return {
        order: int(round(duration_s * sample_rate * math.log(order) / ratio_log))
        for order in range(2, max_order + 1)
    }


def harmonic_impulse_positions(
    linear_peak_index: int,
    f1_hz: float,
    f2_hz: float,
    duration_s: float,
    sample_rate: int,
    max_order: int = 5,
) -> dict[int, int]:
    """Return expected deconvolved indices for linear and harmonic responses."""
    if not isinstance(linear_peak_index, int) or linear_peak_index < 0:
        raise ValueError("linear_peak_index must be a non-negative integer")
    offsets = harmonic_separation_offsets(
        f1_hz, f2_hz, duration_s, sample_rate, max_order,
    )
    positions = {1: linear_peak_index}
    positions.update({order: linear_peak_index - offset for order, offset in offsets.items()})
    return positions


farina_harmonic_offsets = harmonic_separation_offsets


def _normalise_channels(signal: Iterable) -> list[list[float]]:
    values = list(signal)
    if values and isinstance(values[0], (list, tuple)):
        channels = [_finite_signal(channel, "channel") for channel in values]
        if not channels or any(len(channel) != len(channels[0]) for channel in channels):
            raise ValueError("all WAV channels must have the same frame count")
    else:
        channels = [_finite_signal(values)]
    if len(channels) > 64:
        raise ValueError("WAV channel count exceeds 64")
    if channels and len(channels[0]) > _MAX_AUDIO_FRAMES:
        raise ValueError("WAV exceeds the bounded frame limit")
    return channels


def _encode_pcm_sample(value: float, bit_depth: int) -> bytes:
    clipped = max(-1.0, min(1.0, value))
    maximum = (1 << (bit_depth - 1)) - 1
    minimum = -(1 << (bit_depth - 1))
    integer = minimum if clipped <= -1.0 else int(round(clipped * maximum))
    if bit_depth == 16:
        return struct.pack("<h", integer)
    if bit_depth == 24:
        return integer.to_bytes(3, "little", signed=True)
    return struct.pack("<i", integer)


def generate_wav_bytes(
    signal: list[float],
    sample_rate: int = 44100,
    bit_depth: int = 16,
    *,
    encoding: str = "pcm",
) -> bytes:
    """Write mono or channel-major RIFF/WAVE PCM16/24/32 or IEEE float32."""
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool):
        raise ValueError("sample_rate must be an integer")
    if not 1 <= sample_rate <= 768000:
        raise ValueError("sample_rate is outside supported bounds")
    encoding = encoding.lower()
    if encoding in ("float", "float32", "ieee_float"):
        format_tag = 3
        bit_depth = 32
        encoding = "float32"
    elif encoding == "pcm":
        format_tag = 1
        if bit_depth not in (16, 24, 32):
            raise ValueError("PCM bit_depth must be 16, 24, or 32")
    else:
        raise ValueError("encoding must be 'pcm' or 'float32'")

    channels = _normalise_channels(signal)
    channel_count = len(channels)
    frame_count = len(channels[0]) if channels else 0
    bytes_per_sample = bit_depth // 8
    block_align = channel_count * bytes_per_sample
    byte_rate = sample_rate * block_align
    data = bytearray()
    for frame in range(frame_count):
        for channel in channels:
            value = channel[frame]
            if format_tag == 3:
                data.extend(struct.pack("<f", value))
            else:
                data.extend(_encode_pcm_sample(value, bit_depth))

    fmt_payload = struct.pack(
        "<HHIIHH",
        format_tag,
        channel_count,
        sample_rate,
        byte_rate,
        block_align,
        bit_depth,
    )
    data_padding = b"\x00" if len(data) % 2 else b""
    riff_size = 4 + 8 + len(fmt_payload) + 8 + len(data) + len(data_padding)
    return b"".join((
        b"RIFF",
        struct.pack("<I", riff_size),
        b"WAVE",
        b"fmt ",
        struct.pack("<I", len(fmt_payload)),
        fmt_payload,
        b"data",
        struct.pack("<I", len(data)),
        bytes(data),
        data_padding,
    ))


def _decode_pcm_sample(data: bytes, bit_depth: int) -> float:
    if bit_depth == 16:
        integer = struct.unpack("<h", data)[0]
    elif bit_depth == 24:
        integer = int.from_bytes(data, "little", signed=True)
    else:
        integer = struct.unpack("<i", data)[0]
    return integer / float(1 << (bit_depth - 1))


def read_wav_bytes(
    wav_data: bytes,
    channel: Optional[int | str] = 0,
    *,
    max_frames: int = _MAX_AUDIO_FRAMES,
) -> dict:
    """Parse bounded RIFF/WAVE data and select one channel, a mix, or all.

    ``channel`` may be a zero-based integer, ``"mix"`` for an arithmetic mono
    mix, or ``None`` to return channel-major arrays.  Unknown RIFF chunks and
    odd-byte padding are skipped with strict chunk-bound checks.
    """
    if not isinstance(wav_data, (bytes, bytearray, memoryview)):
        raise ValueError("wav_data must be bytes-like")
    data = bytes(wav_data)
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise ValueError("not a little-endian RIFF/WAVE file")
    riff_size = struct.unpack_from("<I", data, 4)[0]
    riff_end = 8 + riff_size
    if riff_size < 4 or riff_end > len(data):
        raise ValueError("truncated RIFF container")
    if not isinstance(max_frames, int) or max_frames <= 0:
        raise ValueError("max_frames must be a positive integer")

    fmt_payload = None
    data_parts = []
    offset = 12
    while offset < riff_end:
        if offset + 8 > riff_end:
            raise ValueError("truncated RIFF chunk header")
        chunk_id = data[offset:offset + 4]
        chunk_size = struct.unpack_from("<I", data, offset + 4)[0]
        payload_start = offset + 8
        payload_end = payload_start + chunk_size
        if payload_end > riff_end:
            raise ValueError(f"truncated {chunk_id!r} chunk")
        payload = data[payload_start:payload_end]
        if chunk_id == b"fmt " and fmt_payload is None:
            fmt_payload = payload
        elif chunk_id == b"data":
            data_parts.append(payload)
        offset = payload_end + (chunk_size & 1)
        if offset > riff_end:
            raise ValueError("missing RIFF odd-chunk padding byte")

    if fmt_payload is None or len(fmt_payload) < 16:
        raise ValueError("WAV fmt chunk is missing or truncated")
    if not data_parts:
        raise ValueError("WAV data chunk is missing")
    format_tag, channel_count, sample_rate, byte_rate, block_align, bit_depth = (
        struct.unpack_from("<HHIIHH", fmt_payload, 0)
    )
    if format_tag == 0xFFFE:
        if len(fmt_payload) < 40:
            raise ValueError("truncated WAVE_FORMAT_EXTENSIBLE fmt chunk")
        format_tag = struct.unpack_from("<H", fmt_payload, 24)[0]
    if format_tag == 1 and bit_depth not in (16, 24, 32):
        raise ValueError("only PCM16, PCM24, and PCM32 are supported")
    if format_tag == 3 and bit_depth != 32:
        raise ValueError("only IEEE float32 WAV is supported")
    if format_tag not in (1, 3):
        raise ValueError(f"unsupported WAV format tag {format_tag}")
    if not 1 <= channel_count <= 64 or not 1 <= sample_rate <= 768000:
        raise ValueError("WAV channel count or sample rate is outside supported bounds")
    expected_align = channel_count * (bit_depth // 8)
    if block_align != expected_align or byte_rate != sample_rate * block_align:
        raise ValueError("inconsistent WAV block alignment or byte rate")

    audio_data = b"".join(data_parts)
    if len(audio_data) % block_align:
        raise ValueError("WAV data size is not a whole number of frames")
    frame_count = len(audio_data) // block_align
    if frame_count > min(max_frames, _MAX_AUDIO_FRAMES):
        raise ValueError("WAV frame count exceeds the configured bound")
    bytes_per_sample = bit_depth // 8
    channels = [[0.0] * frame_count for _ in range(channel_count)]
    cursor = 0
    for frame in range(frame_count):
        for channel_index in range(channel_count):
            raw = audio_data[cursor:cursor + bytes_per_sample]
            cursor += bytes_per_sample
            if format_tag == 3:
                value = struct.unpack("<f", raw)[0]
                if not math.isfinite(value):
                    raise ValueError("IEEE float WAV contains a non-finite sample")
            else:
                value = _decode_pcm_sample(raw, bit_depth)
            channels[channel_index][frame] = value

    if channel is None:
        selected = channels
        selected_channel = None
    elif channel == "mix":
        selected = [
            sum(channels[index][frame] for index in range(channel_count)) / channel_count
            for frame in range(frame_count)
        ]
        selected_channel = "mix"
    elif isinstance(channel, int) and not isinstance(channel, bool):
        if not 0 <= channel < channel_count:
            raise ValueError("requested WAV channel is outside the file")
        selected = channels[channel]
        selected_channel = channel
    else:
        raise ValueError("channel must be an integer, 'mix', or None")

    return {
        "samples": selected,
        "signal": selected,
        "sample_rate": sample_rate,
        "num_channels": channel_count,
        "channels": channel_count,
        "num_frames": frame_count,
        "bits_per_sample": bit_depth,
        "audio_format": "PCM" if format_tag == 1 else "IEEE_FLOAT",
        "selected_channel": selected_channel,
    }


parse_wav_bytes = read_wav_bytes
write_wav_bytes = generate_wav_bytes


def _biquad_bp(
    fc: float, fs: float, q: float = 4.0,
) -> tuple[float, float, float, float, float]:
    """Legacy single RBJ bandpass section; new analysis uses the cascade below."""
    if not 0 < fc < fs / 2 or q <= 0:
        raise ValueError("bandpass center, sample rate, or Q is invalid")
    omega = 2.0 * math.pi * fc / fs
    alpha = math.sin(omega) / (2.0 * q)
    a0 = 1.0 + alpha
    return (
        alpha / a0,
        0.0,
        -alpha / a0,
        -2.0 * math.cos(omega) / a0,
        (1.0 - alpha) / a0,
    )


def _apply_biquad(
    signal: list[float],
    b0: float,
    b1: float,
    b2: float,
    a1: float,
    a2: float,
) -> list[float]:
    x1 = x2 = y1 = y2 = 0.0
    output = [0.0] * len(signal)
    for index, value in enumerate(signal):
        filtered = b0 * value + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        if not math.isfinite(filtered):
            raise ValueError("biquad became unstable for this input")
        output[index] = filtered
        x2, x1 = x1, value
        y2, y1 = y1, filtered
    return output


def fractional_octave_edges(center_hz: float, fraction: int = 1) -> tuple[float, float]:
    """Return exact geometric -3 dB band edges for octave fraction ``fraction``."""
    if not isinstance(center_hz, Real) or not math.isfinite(center_hz) or center_hz <= 0:
        raise ValueError("center_hz must be finite and positive")
    if not isinstance(fraction, int) or isinstance(fraction, bool) or fraction <= 0:
        raise ValueError("fraction must be a positive integer")
    edge_ratio = 2.0 ** (1.0 / (2.0 * fraction))
    return center_hz / edge_ratio, center_hz * edge_ratio


def design_fractional_octave_filter(
    center_hz: float,
    sample_rate: int,
    fraction: int = 1,
) -> list[tuple[float, float, float, float, float]]:
    """Design a fourth-order digital Butterworth bandpass as two biquads.

    A second-order analog Butterworth prototype is bandpass-transformed and
    bilinear-transformed with each requested edge prewarped.  Consequently the
    complete fourth-order response is -3 dB at the geometric fractional-octave
    edges (apart from floating-point error), not merely at arbitrary biquad Q.
    """
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    lower_hz, upper_hz = fractional_octave_edges(center_hz, fraction)
    if upper_hz >= sample_rate / 2:
        raise ValueError("fractional-octave upper edge must be below Nyquist")

    scale = 2.0 * sample_rate
    lower = scale * math.tan(math.pi * lower_hz / sample_rate)
    upper = scale * math.tan(math.pi * upper_hz / sample_rate)
    bandwidth = upper - lower
    analog_center = math.sqrt(lower * upper)
    prototype_poles = (
        complex(-math.sqrt(0.5), math.sqrt(0.5)),
        complex(-math.sqrt(0.5), -math.sqrt(0.5)),
    )
    analog_poles = []
    for pole in prototype_poles:
        root = cmath.sqrt((bandwidth * pole) ** 2 - 4.0 * analog_center ** 2)
        analog_poles.extend(((bandwidth * pole + root) / 2.0, (bandwidth * pole - root) / 2.0))
    digital_poles = [(scale + pole) / (scale - pole) for pole in analog_poles]

    positive_poles = sorted(
        (pole for pole in digital_poles if pole.imag > 0), key=lambda pole: abs(pole)
    )
    if len(positive_poles) != 2:
        raise ValueError("failed to form stable conjugate filter sections")
    sections = []
    for pole in positive_poles:
        a1 = -2.0 * pole.real
        a2 = abs(pole) ** 2
        if not 0 <= a2 < 1:
            raise ValueError("designed filter pole is unstable")
        sections.append([1.0, 0.0, -1.0, a1, a2])

    digital_center = sample_rate / math.pi * math.atan(analog_center / scale)
    omega = 2.0 * math.pi * digital_center / sample_rate
    z_inverse = cmath.exp(-1j * omega)
    response = 1.0 + 0.0j
    for b0, b1, b2, a1, a2 in sections:
        response *= (b0 + b1 * z_inverse + b2 * z_inverse ** 2) / (
            1.0 + a1 * z_inverse + a2 * z_inverse ** 2
        )
    section_gain = math.sqrt(1.0 / abs(response))
    return [
        (b0 * section_gain, b1 * section_gain, b2 * section_gain, a1, a2)
        for b0, b1, b2, a1, a2 in sections
    ]


def fractional_octave_filter(
    signal: list[float],
    sample_rate: int,
    center_hz: float,
    fraction: int = 1,
) -> list[float]:
    """Apply the stable fourth-order Butterworth fractional-octave baseline."""
    output = _finite_signal(signal)
    for section in design_fractional_octave_filter(center_hz, sample_rate, fraction):
        output = _apply_biquad(output, *section)
    return output


def octave_band_filter(
    signal: list[float], sample_rate: int, center_hz: float,
) -> list[float]:
    return fractional_octave_filter(signal, sample_rate, center_hz, 1)


def third_octave_band_filter(
    signal: list[float], sample_rate: int, center_hz: float,
) -> list[float]:
    return fractional_octave_filter(signal, sample_rate, center_hz, 3)


apply_octave_filter = octave_band_filter
apply_third_octave_filter = third_octave_band_filter


def fractional_octave_frequency_response(
    center_hz: float,
    sample_rate: int,
    frequencies_hz: Iterable[float],
    fraction: int = 1,
) -> list[float]:
    """Return linear magnitudes of the designed cascade for verification/UI."""
    sections = design_fractional_octave_filter(center_hz, sample_rate, fraction)
    magnitudes = []
    for frequency in frequencies_hz:
        if not isinstance(frequency, Real) or not 0 <= frequency <= sample_rate / 2:
            raise ValueError("response frequency is outside [0, Nyquist]")
        z_inverse = cmath.exp(-2j * math.pi * frequency / sample_rate)
        response = 1.0 + 0.0j
        for b0, b1, b2, a1, a2 in sections:
            response *= (b0 + b1 * z_inverse + b2 * z_inverse ** 2) / (
                1.0 + a1 * z_inverse + a2 * z_inverse ** 2
            )
        magnitudes.append(abs(response))
    return magnitudes


def compute_waterfall(
    ir: list[float],
    sample_rate: int,
    duration_s: float = 1.0,
    *,
    fraction: int = 1,
    centers_hz: Optional[Iterable[float]] = None,
    time_step_s: float = 0.01,
    floor_db: float = -120.0,
) -> dict:
    """Compute frequency-banded reverse-energy decay (waterfall) curves."""
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if not isinstance(duration_s, Real) or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be finite and positive")
    if not math.isfinite(time_step_s) or time_step_s <= 0:
        raise ValueError("time_step_s must be finite and positive")
    if not math.isfinite(floor_db) or floor_db >= 0:
        raise ValueError("floor_db must be finite and negative")
    sample_count = int(round(sample_rate * duration_s))
    if sample_count <= 0 or sample_count > _MAX_ANALYSIS_SAMPLES:
        raise ValueError("waterfall duration is outside bounded analysis limits")
    values = _finite_signal(ir, "ir")[:sample_count]
    values.extend([0.0] * (sample_count - len(values)))
    centers = (
        [float(value) for value in centers_hz]
        if centers_hz is not None
        else [float(value) for value in BANDAS_OCTAVA]
    )
    if not centers:
        raise ValueError("at least one waterfall center frequency is required")
    step = max(1, int(round(sample_rate * time_step_s)))
    indices = list(range(0, sample_count, step))
    times_ms = [index / sample_rate * 1000.0 for index in indices]

    waterfall: dict[str, list[float]] = {}
    edges: dict[str, list[float]] = {}
    for center in centers:
        key = str(int(center)) if center.is_integer() else f"{center:g}"
        lower, upper = fractional_octave_edges(center, fraction)
        if upper >= sample_rate / 2:
            continue
        filtered = fractional_octave_filter(values, sample_rate, center, fraction)
        cumulative = [0.0] * (sample_count + 1)
        for index in range(sample_count - 1, -1, -1):
            cumulative[index] = cumulative[index + 1] + filtered[index] ** 2
        total = cumulative[0]
        floor_ratio = 10.0 ** (floor_db / 10.0)
        if total <= 0:
            decay = [floor_db] * len(indices)
        else:
            decay = [
                10.0 * math.log10(max(cumulative[index] / total, floor_ratio))
                for index in indices
            ]
            decay[0] = 0.0
        waterfall[key] = decay
        edges[key] = [lower, upper]

    return {
        "time_ms": times_ms,
        "bands": waterfall,
        "band_edges_hz": edges,
        "sample_rate": sample_rate,
        "duration_s": duration_s,
        "fraction": fraction,
        "floor_db": floor_db,
        "representation": "fractional-octave banded Schroeder energy decay",
    }


def compute_spectrogram(
    signal: list[float],
    sample_rate: int,
    window_size: int = 1024,
    hop_size: Optional[int] = None,
    *,
    floor_db: float = -120.0,
    max_frames: int = 4096,
) -> dict:
    """Compute a Hann-windowed, one-sided pure-Python STFT spectrogram."""
    values = _finite_signal(signal)
    if not values:
        raise ValueError("signal must not be empty")
    if len(values) > _MAX_ANALYSIS_SAMPLES:
        raise ValueError("spectrogram signal exceeds the bounded sample limit")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if (
        not isinstance(window_size, int)
        or isinstance(window_size, bool)
        or not 2 <= window_size <= 16384
    ):
        raise ValueError("window_size must be an integer in [2, 16384]")
    hop_size = window_size // 2 if hop_size is None else hop_size
    if not isinstance(hop_size, int) or isinstance(hop_size, bool) or hop_size <= 0:
        raise ValueError("hop_size must be a positive integer")
    if not math.isfinite(floor_db) or floor_db >= 0:
        raise ValueError("floor_db must be finite and negative")
    fft_size = _next_pow2(window_size)
    if len(values) < window_size:
        starts = [0]
    else:
        starts = list(range(0, len(values) - window_size + 1, hop_size))
    if len(starts) > max_frames:
        raise ValueError("spectrogram frame count exceeds max_frames")

    window = [
        0.5 - 0.5 * math.cos(2.0 * math.pi * index / (window_size - 1))
        for index in range(window_size)
    ]
    coherent_gain = max(sum(window) / 2.0, 1e-30)
    frequencies = [
        index * sample_rate / fft_size for index in range(fft_size // 2 + 1)
    ]
    times = [(start + (window_size - 1) / 2.0) / sample_rate for start in starts]
    magnitude_db = []
    magnitude = []
    floor_amplitude = 10.0 ** (floor_db / 20.0)
    for start in starts:
        frame = values[start:start + window_size]
        frame.extend([0.0] * (window_size - len(frame)))
        transformed = _fft(
            [complex(frame[index] * window[index]) for index in range(window_size)]
            + [0j] * (fft_size - window_size)
        )
        frame_magnitude = [
            abs(transformed[index]) / coherent_gain for index in range(fft_size // 2 + 1)
        ]
        magnitude.append(frame_magnitude)
        magnitude_db.append([
            20.0 * math.log10(max(value, floor_amplitude))
            for value in frame_magnitude
        ])
    return {
        "times_s": times,
        "frequencies_hz": frequencies,
        "magnitude": magnitude,
        "magnitude_db": magnitude_db,
        "sample_rate": sample_rate,
        "window_size": window_size,
        "fft_size": fft_size,
        "hop_size": hop_size,
        "window": "periodic-symmetric Hann",
        "floor_db": floor_db,
    }


stft_spectrogram = compute_spectrogram


def _linear_fit(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    count = len(points)
    mean_x = sum(point[0] for point in points) / count
    mean_y = sum(point[1] for point in points) / count
    denominator = sum((point[0] - mean_x) ** 2 for point in points)
    if denominator <= 0:
        return 0.0, mean_y, 0.0
    slope = sum(
        (point[0] - mean_x) * (point[1] - mean_y) for point in points
    ) / denominator
    intercept = mean_y - slope * mean_x
    residual = sum(
        (value - (slope * time + intercept)) ** 2 for time, value in points
    )
    total = sum((value - mean_y) ** 2 for _, value in points)
    r2 = 1.0 - residual / total if total > 0 else 1.0
    return slope, intercept, r2


def estimate_modal_q(
    signal: list[float],
    sample_rate: int,
    target_frequency_hz: Optional[float] = None,
    *,
    cycles_per_window: float = 4.0,
    dynamic_range_db: float = 30.0,
) -> dict:
    """Estimate modal Q from a damped sinusoidal ring-down.

    A sliding sinusoidal projection estimates the modal amplitude envelope.  A
    log-linear fit then uses ``Q = -pi*f0/slope_nepers_per_s``.  This baseline
    assumes one dominant, approximately exponentially decaying mode.
    """
    values = _finite_signal(signal)
    if len(values) < 32:
        raise ValueError("modal Q estimation requires at least 32 samples")
    if len(values) > _MAX_ANALYSIS_SAMPLES:
        raise ValueError("modal Q signal exceeds the bounded sample limit")
    if not isinstance(sample_rate, int) or isinstance(sample_rate, bool) or sample_rate <= 0:
        raise ValueError("sample_rate must be a positive integer")
    if not math.isfinite(cycles_per_window) or cycles_per_window < 2:
        raise ValueError("cycles_per_window must be at least two")
    if not math.isfinite(dynamic_range_db) or not 10 <= dynamic_range_db <= 80:
        raise ValueError("dynamic_range_db must be in [10, 80]")

    if target_frequency_hz is None:
        fft_size = _next_pow2(len(values))
        mean = sum(values) / len(values)
        windowed = [
            (values[index] - mean)
            * (0.5 - 0.5 * math.cos(2.0 * math.pi * index / (len(values) - 1)))
            for index in range(len(values))
        ]
        spectrum = _fft([complex(value) for value in windowed] + [0j] * (fft_size - len(values)))
        peak_bin = max(range(1, fft_size // 2), key=lambda index: abs(spectrum[index]))
        frequency = peak_bin * sample_rate / fft_size
    else:
        if (
            isinstance(target_frequency_hz, bool)
            or not isinstance(target_frequency_hz, Real)
            or not math.isfinite(target_frequency_hz)
            or not 0 < target_frequency_hz < sample_rate / 2
        ):
            raise ValueError("target_frequency_hz must be inside (0, Nyquist)")
        frequency = float(target_frequency_hz)

    window_size = int(round(cycles_per_window * sample_rate / frequency))
    window_size = max(16, min(window_size, len(values)))
    if window_size == len(values):
        raise ValueError("signal is too short for the requested modal frequency")
    hop = max(1, window_size // 4)
    window = [
        0.5 - 0.5 * math.cos(2.0 * math.pi * index / (window_size - 1))
        for index in range(window_size)
    ]
    window_sum = sum(window)
    amplitudes = []
    times = []
    for start in range(0, len(values) - window_size + 1, hop):
        real = imaginary = 0.0
        for offset in range(window_size):
            phase = 2.0 * math.pi * frequency * (start + offset) / sample_rate
            weighted = values[start + offset] * window[offset]
            real += weighted * math.cos(phase)
            imaginary -= weighted * math.sin(phase)
        amplitudes.append(2.0 * math.hypot(real, imaginary) / window_sum)
        times.append((start + (window_size - 1) / 2.0) / sample_rate)

    peak_index = max(range(len(amplitudes)), key=amplitudes.__getitem__)
    peak_amplitude = amplitudes[peak_index]
    threshold = peak_amplitude * 10.0 ** (-dynamic_range_db / 20.0)
    points = []
    for index in range(peak_index, len(amplitudes)):
        amplitude = amplitudes[index]
        if amplitude < threshold:
            if len(points) >= 4:
                break
            continue
        points.append((times[index], math.log(max(amplitude, 1e-300))))
    if len(points) < 4:
        raise ValueError("insufficient modal decay dynamic range for Q estimation")
    slope, intercept, r2 = _linear_fit(points)
    if slope >= 0:
        raise ValueError("modal envelope does not decay")
    q_value = -math.pi * frequency / slope
    return {
        "Q": q_value,
        "q": q_value,
        "frequency_hz": frequency,
        "decay_slope_nepers_per_s": slope,
        "intercept_log_amplitude": intercept,
        "r2": r2,
        "fit_points": len(points),
        "dynamic_range_db": dynamic_range_db,
        "method": "sinusoidal-projection ring-down fit; Q=-pi*f0/slope",
    }


def calibrate_alpha(
    room: Room,
    measured_rt60: dict[str, float],
    iterations: int = 30,
    learning_rate: float = 0.05,
) -> dict:
    """Calibrate one identifiable room-wide alpha offset per measured band.

    Sabine RT identifies area-weighted total absorption, not six independent
    surface coefficients.  The fitted parameter is therefore one bounded common
    offset per band, preserving differences between the starting materials.
    Diagnostics include accepted objective history, convergence, and bounds.
    ``learning_rate`` remains accepted for API compatibility; bisection is used
    because the one-dimensional objective is monotonic and bounded.
    """
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations <= 0:
        raise ValueError("iterations must be a positive integer")
    if not isinstance(learning_rate, Real) or not math.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be finite and positive")
    if not isinstance(measured_rt60, dict) or not measured_rt60:
        raise ValueError("measured_rt60 must contain at least one measured band")

    lower_bound = 0.0
    upper_bound = 0.999
    sabine_constant = 0.161 * room.volumen
    calibrated: dict[str, dict[str, float] | dict] = {}
    diagnostics = {}

    for band, measured_value in measured_rt60.items():
        if band not in BANDAS_OCTAVA:
            raise ValueError(f"unknown measured octave band {band!r}")
        if (
            isinstance(measured_value, bool)
            or not isinstance(measured_value, Real)
            or not math.isfinite(measured_value)
            or measured_value <= 0
        ):
            raise ValueError(f"measured RT60 for band {band} must be finite and positive")
        measured = float(measured_value)
        base = []
        for surface in room.superficies:
            alpha = surface.material.alpha.get(band)
            if alpha is None:
                raise ValueError(
                    f"surface {surface.nombre!r} has no absorption for measured band {band}"
                )
            base.append((surface, float(alpha)))

        def state(delta: float) -> tuple[list[float], float, float]:
            alphas = [
                max(lower_bound, min(upper_bound, alpha + delta))
                for _, alpha in base
            ]
            absorption = sum(
                surface.area * alpha for (surface, _), alpha in zip(base, alphas)
            )
            predicted = sabine_constant / absorption if absorption > 0 else float("inf")
            objective = (predicted - measured) ** 2
            return alphas, predicted, objective

        initial_alphas, initial_predicted, initial_objective = state(0.0)
        target_absorption = sabine_constant / measured
        minimum_absorption = lower_bound * room.superficie_total
        maximum_absorption = upper_bound * room.superficie_total
        low_delta, high_delta = -1.0, 1.0
        best_delta = 0.0
        best_alphas = initial_alphas
        best_predicted = initial_predicted
        best_objective = initial_objective
        objective_history = [initial_objective]
        absolute_error_history = [abs(initial_predicted - measured)]
        bounded_target = not minimum_absorption <= target_absorption <= maximum_absorption

        if bounded_target:
            candidate_delta = low_delta if target_absorption < minimum_absorption else high_delta
            candidate_alphas, candidate_predicted, candidate_objective = state(candidate_delta)
            if candidate_objective <= best_objective:
                best_delta = candidate_delta
                best_alphas = candidate_alphas
                best_predicted = candidate_predicted
                best_objective = candidate_objective
                objective_history.append(candidate_objective)
                absolute_error_history.append(abs(candidate_predicted - measured))
        else:
            for _ in range(iterations):
                candidate_delta = (low_delta + high_delta) / 2.0
                candidate_alphas, candidate_predicted, candidate_objective = state(candidate_delta)
                candidate_absorption = sum(
                    surface.area * alpha
                    for (surface, _), alpha in zip(base, candidate_alphas)
                )
                if candidate_objective <= best_objective + 1e-24:
                    best_delta = candidate_delta
                    best_alphas = candidate_alphas
                    best_predicted = candidate_predicted
                    best_objective = candidate_objective
                    if candidate_objective <= objective_history[-1] + 1e-24:
                        objective_history.append(candidate_objective)
                        absolute_error_history.append(abs(candidate_predicted - measured))
                if candidate_absorption < target_absorption:
                    low_delta = candidate_delta
                else:
                    high_delta = candidate_delta
                if abs(candidate_predicted - measured) <= max(1e-6, measured * 1e-5):
                    break

        calibrated[band] = {
            surface.nombre: best_alphas[index]
            for index, (surface, _) in enumerate(base)
        }
        converged = not bounded_target and abs(best_predicted - measured) <= max(
            1e-5, measured * 1e-4,
        )
        diagnostics[band] = {
            "converged": converged,
            "reason": "target outside alpha bounds" if bounded_target else (
                None if converged else "iteration limit reached"
            ),
            "iterations": len(objective_history) - 1,
            "objective_history": objective_history,
            "absolute_error_history_s": absolute_error_history,
            "initial_predicted_rt60_s": initial_predicted,
            "predicted_rt60_s": best_predicted,
            "measured_rt60_s": measured,
            "target_absorption_m2_sabins": target_absorption,
            "common_alpha_offset": best_delta,
            "alpha_bounds": [lower_bound, upper_bound],
            "grouping": "single room-wide area-weighted alpha offset",
            "identifiable_parameters": 1,
            "surface_coefficients_reported": len(base),
        }

    calibrated["diagnostics"] = diagnostics
    return calibrated
